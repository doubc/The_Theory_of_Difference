"""
exp_215_p4_narrative_recursion_v2.py — Phase 23 P4 叙事递归实验 (修复版)

关键修复:
1. 叙事递归在创建下一层之前运行 (而非之后)
2. 正确调整下一层的初始状态
3. 增加能量预算确保 m9 能执行

测试 H23-4 假设
"""

from __future__ import annotations
import sys
import os
import numpy as np
import json
from datetime import datetime
from typing import Optional, Dict, List

# 确保能导入 engine_v2
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from diffsim.world_v2 import RecursiveWorld, Params, Layer
from diffsim import mechanisms as M
from diffsim.energy_v2 import EnergyConfig, EnergyManager
from diffsim.entropy import EntropyConfig, EntropyTracker
from diffsim.narrative_recursion import RecursiveNarrativeLoop, NarrativeState


class NarrativeRecursiveWorld(RecursiveWorld):
    """扩展 RecursiveWorld，集成叙事递归能力
    
    在 m9 自指密封时，先运行叙事递归螺旋，再创建下一层。
    叙事递归改变可能性空间拓扑，使能量注入更有效。
    """
    
    def __init__(self, N0: int, n_colors: int = 6,
                 params: Optional[Params] = None,
                 energy_cfg: Optional[EnergyConfig] = None,
                 entropy_cfg: Optional[EntropyConfig] = None,
                 seed: Optional[int] = None,
                 self_encapsulate: bool = True,
                 narrative_rounds: int = 3,
                 injection_rate: float = 0.2):
        """
        Args:
            narrative_rounds: 每层密封后执行的叙事递归轮数
            injection_rate: 能量注入率 (叙事递归动作4)
        """
        super().__init__(
            N0=N0,
            n_colors=n_colors,
            params=params,
            energy_cfg=energy_cfg,
            entropy_cfg=entropy_cfg,
            seed=seed,
            self_encapsulate=self_encapsulate
        )
        
        self.narrative_rounds = narrative_rounds
        self.injection_rate = injection_rate
        self.narrative_loop: Optional[RecursiveNarrativeLoop] = None
        self.narrative_history: List[Dict] = []
        
    def _m9_seal_and_create_next(self, current_layer, verbose: bool = False) -> bool:
        """重写 m9: 先执行叙事递归，再创建下一层
        
        关键修复: 叙事递归必须在创建下一层之前运行，
        这样才能调整下一层的初始条件。
        """
        # 先调用 m9_self_reference 获取下一层的字段 (但不创建 Layer)
        f_next = M.m9_self_reference(
            current_layer, 
            self_encapsulate=self.self_encapsulate
        )
        
        if f_next is None:
            if verbose:
                print(f"  [m9] Layer {current_layer.field.layer}: no organizations to encapsulate, stopping")
            return False
        
        # === 关键: 在创建 Layer 之前，运行叙事递归 ===
        # 使用当前层作为系统，执行叙事递归螺旋
        if self.narrative_loop is None:
            # 首次初始化 - 使用当前层的能量管理器
            energy_field = current_layer.energy
            if energy_field is None:
                # 创建默认能量管理器
                energy_field = EnergyManager(EnergyConfig(initial_budget=100.0))
            
            self.narrative_loop = RecursiveNarrativeLoop(
                system=current_layer,
                energy_field=energy_field,
                entropy_threshold=0.5,
                coupling_strength=0.3,
                injection_rate=self.injection_rate
            )
        
        # 运行叙事递归螺旋 (调整 f_next 的状态)
        spiral_history = self.narrative_loop.run_spiral(
            n_rounds=self.narrative_rounds,
            verbose=verbose
        )
        
        # 根据叙事递归结果调整 f_next
        self._adjust_next_field(f_next, spiral_history, verbose)
        
        # 记录叙事递归结果
        spiral_analysis = self.narrative_loop.get_spiral_trajectory()
        self.narrative_history.append({
            'layer': current_layer.field.layer,
            'spiral': spiral_analysis,
            'history': [{
                'round': s.round,
                'delta': s.delta,
                'high_entropy': s.constraint_params['high_entropy_count']
            } for s in spiral_history]
        })
        
        if verbose:
            print(f"  [Narrative] Layer {current_layer.field.layer}: "
                  f"spiral_trajectory={spiral_analysis}")
        
        # 现在创建下一层 (使用调整后的 f_next)
        energy_mgr_next = None
        entropy_mgr_next = None
        if self.energy_cfg:
            energy_mgr_next = EnergyManager(self.energy_cfg)
        if self.entropy_cfg:
            entropy_mgr_next = EntropyTracker(self.entropy_cfg)
        
        next_layer = Layer(f_next, self.params, energy_mgr_next, entropy_mgr_next)
        self.layers.append(next_layer)
        
        if verbose:
            mode = "self_reference" if self.self_encapsulate else "passive_projection"
            print(f"  [m9] Created Layer {len(self.layers)-1}: N={f_next.N}, "
                  f"active={f_next.n_active()}, mode={mode}")
        
        return True
    
    def _adjust_next_field(self, f_next, spiral_history: List[NarrativeState], verbose: bool = False):
        """根据叙事递归结果调整下一层的字段
        
        关键: 叙事递归改变可能性空间拓扑，使下一层涌现不同结构。
        """
        if not spiral_history:
            return
        
        # 计算平均 delta (非重复性指标)
        deltas = [s.delta for s in spiral_history]
        avg_delta = np.mean(deltas) if deltas else 0.0
        
        # 根据 delta 调整 f_next 的初始状态
        # 高 delta → 大幅改变初始条件 (打破循环)
        # 低 delta → 小幅改变初始条件 (保持连续性)
        adjustment_strength = min(0.3, avg_delta * 1.5)  # 限制调整幅度
        
        N = f_next.N
        n_adjust = int(N * adjustment_strength)
        
        if n_adjust > 0:
            # 随机翻转一些位 (改变可能性空间拓扑)
            rng = np.random.RandomState(self.seed + len(self.layers) * 997)
            adjust_indices = rng.choice(N, size=n_adjust, replace=False)
            
            for idx in adjust_indices:
                f_next.state[idx] = 1 - f_next.state[idx]  # 翻转
            
            if verbose:
                print(f"  [Narrative] Adjusted {n_adjust} bits in next layer")
        
        # 记录调整
        if self.narrative_history:
            self.narrative_history[-1]['adjustment'] = {
                'n_adjust': n_adjust,
                'strength': adjustment_strength,
                'new_active': f_next.n_active()
            }


def run_single_experiment(group: str, config: Dict, n_seeds: int = 5) -> Dict:
    """运行单个实验组"""
    results = []
    
    for seed in range(n_seeds):
        # 创建配置
        params = Params(
            max_steps=config.get('max_steps', 400),
            base_seal_threshold=config.get('seal_threshold', 0.8)
        )
        
        energy_cfg = None
        if config.get('use_energy', False):
            energy_cfg = EnergyConfig(
                initial_budget=config.get('energy_budget', 100.0),
                injection_rate=config.get('injection_rate', 0.5),
                m1_cost=2.0, m3_cost=1.0, m6_cost=1.5, m9_cost=3.0
            )
        
        entropy_cfg = None
        if config.get('use_entropy', False):
            entropy_cfg = EntropyConfig(
                temperature=1.0,
                use_log2=True
            )
        
        # 创建世界
        if group == 'G5':
            # G5: 叙事递归 + 自指 + 能量
            world = NarrativeRecursiveWorld(
                N0=config['N0'],
                n_colors=config.get('n_colors', 6),
                params=params,
                energy_cfg=energy_cfg,
                entropy_cfg=entropy_cfg,
                seed=seed,
                self_encapsulate=True,  # 自指闭环
                narrative_rounds=config.get('narrative_rounds', 3),
                injection_rate=config.get('narrative_injection_rate', 0.2)
            )
        else:
            # G3/G4: 标准 RecursiveWorld
            world = RecursiveWorld(
                N0=config['N0'],
                n_colors=config.get('n_colors', 6),
                params=params,
                energy_cfg=energy_cfg,
                entropy_cfg=entropy_cfg,
                seed=seed,
                self_encapsulate=config.get('self_encapsulate', True)
            )
        
        # 运行
        result = world.run(max_layers=10, verbose=False)
        
        # 收集结果
        result['seed'] = seed
        result['group'] = group
        
        # 计算 flux 均值
        fluxes = []
        for layer_info in result['layers']:
            if 'flux' in layer_info and layer_info['flux'] > 0:
                fluxes.append(layer_info['flux'])
        result['mean_flux'] = np.mean(fluxes) if fluxes else 0.0
        result['max_flux'] = np.max(fluxes) if fluxes else 0.0
        
        # G5 特有: 叙事递归统计
        if group == 'G5' and hasattr(world, 'narrative_history'):
            result['narrative_history'] = world.narrative_history
            
            # 计算非重复性指标
            deltas = []
            for nh in world.narrative_history:
                for h in nh.get('history', []):
                    deltas.append(h.get('delta', 0))
            result['narrative_non_repetition'] = np.mean(deltas) if deltas else 0.0
        
        results.append(result)
    
    # 汇总统计
    summary = {
        'group': group,
        'n_seeds': n_seeds,
        'depths': [r['depth'] for r in results],
        'mean_depth': float(np.mean([r['depth'] for r in results])),
        'std_depth': float(np.std([r['depth'] for r in results])),
        'mean_fluxes': [r['mean_flux'] for r in results],
        'mean_flux': float(np.mean([r['mean_flux'] for r in results])),
        'max_flux': float(np.max([r['max_flux'] for r in results])),
        'results': results
    }
    
    if group == 'G5':
        non_reps = [r.get('narrative_non_repetition', 0) for r in results]
        summary['narrative_non_repetition'] = float(np.mean(non_reps))
    
    return summary


def main():
    """主实验"""
    print("=" * 60)
    print("Phase 23 P4: Narrative Recursion Experiment (exp_215) v2")
    print("Testing H23-4 hypotheses (fixed implementation)")
    print("=" * 60)
    
    # 实验配置
    base_config = {
        'N0': 50,
        'n_colors': 6,
        'max_steps': 400,
        'seal_threshold': 0.8,
    }
    
    experiments = {
        # G3: 封闭系统/自指闭环 (baseline)
        'G3': {
            **base_config,
            'use_energy': False,
            'use_entropy': False,
            'self_encapsulate': True,
        },
        
        # G4: 开放系统/自指闭环/无叙事递归 (能量截断涌现)
        'G4': {
            **base_config,
            'use_energy': True,
            'energy_budget': 2000.0,  # 大幅增加预算
            'injection_rate': 10.0,  # 大幅增加注入率
            'use_entropy': False,
            'self_encapsulate': True,
        },
        
        # G5: 开放系统/自指闭环/叙事递归 (full V1.7)
        'G5': {
            **base_config,
            'use_energy': True,
            'energy_budget': 2000.0,  # 大幅增加预算
            'injection_rate': 10.0,  # 大幅增加注入率
            'use_entropy': False,
            'self_encapsulate': True,
            'narrative_rounds': 3,
            'narrative_injection_rate': 0.5,
        },
    }
    
    # 运行实验
    n_seeds = 5
    all_results = {}
    
    for group, config in experiments.items():
        print(f"\n{'='*60}")
        print(f"Running {group} (seed 0-{n_seeds-1})...")
        print(f"{'='*60}")
        
        summary = run_single_experiment(group, config, n_seeds=n_seeds)
        all_results[group] = summary
        
        print(f"\n{group} Results:")
        print(f"  Mean Depth: {summary['mean_depth']:.2f} +/- {summary['std_depth']:.2f}")
        print(f"  Mean Flux:  {summary['mean_flux']:.4f}")
        print(f"  Max Flux:   {summary['max_flux']:.4f}")
        if group == 'G5':
            print(f"  Narrative Non-repetition: {summary.get('narrative_non_repetition', 0):.4f}")
    
    # 验证假设
    print(f"\n{'='*60}")
    print("Hypothesis Verification:")
    print(f"{'='*60}")
    
    g3 = all_results['G3']
    g4 = all_results['G4']
    g5 = all_results['G5']
    
    # H23-4a: 叙事递归突破循环陷阱
    h4a_pass = g5['mean_depth'] > g3['mean_depth']
    print(f"\nH23-4a: Narrative recursion breaks cyclic traps")
    print(f"  G3 depth: {g3['mean_depth']:.2f}")
    print(f"  G5 depth: {g5['mean_depth']:.2f}")
    print(f"  Result: {'PASS' if h4a_pass else 'FAIL'}")
    
    # H23-4b: 能量注入改变可能性空间拓扑
    h4b_pass = g5['mean_flux'] > g3['mean_flux']
    print(f"\nH23-4b: Energy injection changes possibility space topology")
    print(f"  G3 flux: {g3['mean_flux']:.4f}")
    print(f"  G5 flux: {g5['mean_flux']:.4f}")
    print(f"  Result: {'PASS' if h4b_pass else 'FAIL'}")
    
    # H23-4c: 差异化选择避免奖励 hacking
    h4c_pass = g5.get('narrative_non_repetition', 0) > 0.1
    print(f"\nH23-4c: Differentiated selection avoids reward hacking")
    print(f"  G5 non-repetition: {g5.get('narrative_non_repetition', 0):.4f}")
    print(f"  Result: {'PASS' if h4c_pass else 'FAIL'}")
    
    # H23-4d: 可持续涌现
    h4d_pass = g5['mean_depth'] >= 3 and g5['mean_flux'] > 0
    print(f"\nH23-4d: Sustainable emergence")
    print(f"  G5 depth: {g5['mean_depth']:.2f} (threshold >= 3)")
    print(f"  G5 flux:  {g5['mean_flux']:.4f} (threshold > 0)")
    print(f"  Result: {'PASS' if h4d_pass else 'FAIL'}")
    
    # 总结
    n_pass = sum([h4a_pass, h4b_pass, h4c_pass, h4d_pass])
    print(f"\n{'='*60}")
    print(f"Total: {n_pass}/4 hypotheses PASS")
    print(f"{'='*60}")
    
    # 保存结果
    output = {
        'experiment': 'exp_215_p4_narrative_recursion_v2',
        'date': datetime.now().isoformat(),
        'hypotheses': {
            'H23-4a': {'pass': h4a_pass, 'G3': g3['mean_depth'], 'G5': g5['mean_depth']},
            'H23-4b': {'pass': h4b_pass, 'G3': g3['mean_flux'], 'G5': g5['mean_flux']},
            'H23-4c': {'pass': h4c_pass, 'G5': g5.get('narrative_non_repetition', 0)},
            'H23-4d': {'pass': h4d_pass, 'G5_depth': g5['mean_depth'], 'G5_flux': g5['mean_flux']},
        },
        'results': all_results
    }
    
    output_path = os.path.join(os.path.dirname(__file__), '../results/exp_215_p4_narrative_v2.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\nResults saved to: {output_path}")
    
    return output


if __name__ == "__main__":
    results = main()
