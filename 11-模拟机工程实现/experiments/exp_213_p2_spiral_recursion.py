"""
exp_213_p2_spiral_recursion.py
=============================
Phase 23 P2: 螺旋递归验证 (H23-2)

假设: 能量驱动螺旋递归——多轮能量脉冲+自指修正使P_t产生非重复、不可逆的变化

设计:
- 多轮迭代: 每个seed运行5轮RecursiveWorld, 每轮记录状态指纹P_t
- G1_control: self_encapsulate=False (无自指) + 无能量 → 应收敛/重复
- G2_energy_only: self_encapsulate=False + 有能量 → 应有限改进
- G3_selfref_only: self_encapsulate=True + 无能量 → 应有基础非重复
- G4_spiral: self_encapsulate=True + 有能量 → 应有最强非重复性

P_t状态指纹:
- f_jaccard[round_t]: 深层活跃位集合与初始位的Jaccard距离
- f_entropy[round_t]: 深层活跃位分布熵
- f_depth[round_t]: 涌现深度
- f_flux[round_t]: 层内活跃度
- f_pattern[round_t]: 状态模式哈希

核心指标:
- 非重复性: 状态指纹在不同轮次间的方差 Var(f_t) > 阈值
- 不可逆性: 指纹变化方向的单调趋势
- 螺旋性: 相邻轮次f_t不回归早期值
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import json
from engine_v2.diffsim import RecursiveWorld, Params
from engine_v2.diffsim.energy_v2 import EnergyConfig


def compute_state_fingerprint(world):
    """计算RecursiveWorld的状态指纹P_t"""
    if not world.layers:
        return None
    
    deepest = world.layers[-1]
    f = deepest.field
    
    # f1: 深层活跃位集合
    active_set = f.active_set()
    
    # f2: 深层活跃位分布熵
    n_active = len(active_set)
    if n_active > 0 and f.N > 0:
        p = n_active / f.N
        if 0 < p < 1:
            entropy = -p * np.log2(p) - (1-p) * np.log2(1-p)
        else:
            entropy = 0.0
    else:
        entropy = 0.0
    
    # f3: 涌现深度
    depth = len(world.layers) - 1
    
    # f4: 层内活跃度
    flux = np.mean(deepest.flux_trace) if deepest.flux_trace else 0.0
    
    # f5: 深层活跃位数
    n_active_bits = f.n_active()
    
    # f6: 活跃位分布均匀性
    if n_active_bits > 1:
        positions = np.array(sorted(active_set))
        pos_std = np.std(np.diff(positions))
    else:
        pos_std = 0.0
    
    # f7: 跨层能量利用
    total_energy_steps = 0
    for layer in world.layers:
        if layer.energy:
            total_energy_steps += len(layer.energy.history.steps)
    
    return {
        'f_jaccard': None,
        'f_entropy': entropy,
        'f_depth': depth,
        'f_flux': flux,
        'f_n_active': n_active_bits,
        'f_pos_std': pos_std,
        'f_energy_steps': total_energy_steps,
        'f_n_layers': len(world.layers),
        'f_steps_per_layer': [layer.step for layer in world.layers],
        'f_flux_per_layer': [np.mean(layer.flux_trace) if layer.flux_trace else 0.0 for layer in world.layers],
    }


def compute_jaccard_distance(set_a, set_b):
    """Jaccard距离: 1 - |A∩B|/|A∪B|"""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 1.0
    return 1.0 - intersection / union


def run_single_round(seed, group, N0=48, max_layers=8, verbose=False):
    """运行单轮RecursiveWorld"""
    rng = np.random.RandomState(seed)
    
    has_self_ref = group in ('G3_selfref_only', 'G4_spiral')
    has_energy = group in ('G2_energy_only', 'G4_spiral')
    
    energy_cfg = None
    if has_energy:
        energy_cfg = EnergyConfig(
            initial_budget=200.0,
            decay_rate=0.01,
            injection_rate=1.5,
            m9_cost=1.0,
            m3_cost=0.5,
            m6_cost=0.5,
            m1_cost=0.3,
            dead_order_threshold=2.0,
        )
    
    params = Params(n_meta_colors=6, max_steps=400)
    
    world = RecursiveWorld(
        N0=N0,
        n_colors=6,
        params=params,
        energy_cfg=energy_cfg,
        seed=seed,
        self_encapsulate=has_self_ref,
    )
    
    result = world.run(max_layers=max_layers, verbose=verbose)
    
    fp = compute_state_fingerprint(world)
    
    # Jaccard: 对比L0初始活跃位与最终深层活跃位
    # 为确保可复现, 用固定方式重建L0初始位
    rng2 = np.random.RandomState(seed)
    initial_active = set(rng2.choice(N0, size=N0//2, replace=False).tolist())
    final_active = world.layers[-1].field.active_set()
    fp['f_jaccard'] = compute_jaccard_distance(initial_active, final_active)
    
    return {
        'seed': seed,
        'group': group,
        'fingerprint': fp,
        'world': world,
    }


def compute_non_repeat_metrics(fingerprints):
    """计算非重复性指标"""
    n_rounds = len(fingerprints)
    if n_rounds < 2:
        return None
    
    depth_seq = [fp['fingerprint']['f_depth'] for fp in fingerprints]
    entropy_seq = [fp['fingerprint']['f_entropy'] for fp in fingerprints]
    flux_seq = [fp['fingerprint']['f_flux'] for fp in fingerprints]
    n_active_seq = [fp['fingerprint']['f_n_active'] for fp in fingerprints]
    energy_seq = [fp['fingerprint']['f_energy_steps'] for fp in fingerprints]
    
    # 方差(非重复性)
    depth_var = np.var(depth_seq) if len(set(depth_seq)) > 1 else 0.0
    entropy_var = np.var(entropy_seq) if len(set(entropy_seq)) > 1 else 0.0
    flux_var = np.var(flux_seq) if len(set(flux_seq)) > 1 else 0.0
    n_active_var = np.var(n_active_seq) if len(set(n_active_seq)) > 1 else 0.0
    
    # 相邻轮次差异
    depth_diffs = [abs(depth_seq[i+1] - depth_seq[i]) for i in range(n_rounds-1)]
    entropy_diffs = [abs(entropy_seq[i+1] - entropy_seq[i]) for i in range(n_rounds-1)]
    flux_diffs = [abs(flux_seq[i+1] - flux_seq[i]) for i in range(n_rounds-1)]
    
    avg_depth_diff = np.mean(depth_diffs) if depth_diffs else 0.0
    avg_entropy_diff = np.mean(entropy_diffs) if entropy_diffs else 0.0
    avg_flux_diff = np.mean(flux_diffs) if flux_diffs else 0.0
    
    # 早期vs后期漂移(不可逆性)
    early_depth = np.mean(depth_seq[:2]) if n_rounds >= 2 else depth_seq[0]
    late_depth = np.mean(depth_seq[-2:]) if n_rounds >= 2 else depth_seq[-1]
    depth_drift = abs(late_depth - early_depth)
    
    early_entropy = np.mean(entropy_seq[:2]) if n_rounds >= 2 else entropy_seq[0]
    late_entropy = np.mean(entropy_seq[-2:]) if n_rounds >= 2 else entropy_seq[-1]
    entropy_drift = abs(late_entropy - early_entropy)
    
    # 螺旋性: 轮次t与t-2的距离(不应回归)
    spiral_jaccards = []
    for t in range(2, n_rounds):
        fp_t = fingerprints[t]['fingerprint']
        fp_prev = fingerprints[t-2]['fingerprint']
        d_depth = abs(fp_t['f_depth'] - fp_prev['f_depth'])
        d_energy = abs(fp_t['f_energy_steps'] - fp_prev['f_energy_steps'])
        spiral_jaccards.append(d_depth + d_energy * 0.01)
    
    avg_spiral = np.mean(spiral_jaccards) if spiral_jaccards else 0.0
    
    # 总非重复性分数
    non_repeat_score = (
        depth_var * 2.0 +
        entropy_var * 10.0 +
        flux_var * 5.0 +
        avg_entropy_diff * 3.0 +
        depth_drift * 1.0 +
        avg_spiral * 2.0
    )
    
    return {
        'n_rounds': n_rounds,
        'depth_var': depth_var,
        'entropy_var': entropy_var,
        'flux_var': flux_var,
        'n_active_var': n_active_var,
        'avg_depth_diff': avg_depth_diff,
        'avg_entropy_diff': avg_entropy_diff,
        'avg_flux_diff': avg_flux_diff,
        'depth_drift': depth_drift,
        'entropy_drift': entropy_drift,
        'avg_spiral': avg_spiral,
        'non_repeat_score': non_repeat_score,
        'depth_seq': depth_seq,
        'entropy_seq': entropy_seq,
        'flux_seq': flux_seq,
        'energy_seq': energy_seq,
    }


def run_group(group, seeds, N0=48, max_layers=8, n_rounds=5, verbose=False):
    """运行一组(多轮多seed)"""
    group_results = []
    
    for seed in seeds:
        round_results = []
        for r in range(n_rounds):
            round_seed = seed + r * 10000
            if verbose:
                print(f"  [{group}] seed={round_seed} round={r+1}/{n_rounds}")
            
            result = run_single_round(round_seed, group, N0=N0, max_layers=max_layers, verbose=False)
            round_results.append(result)
        
        metrics = compute_non_repeat_metrics(round_results)
        group_results.append({
            'seed': seed,
            'rounds': round_results,
            'metrics': metrics,
        })
    
    return group_results


def main():
    print("=" * 60)
    print("exp_213_p2_spiral_recursion: H23-2 螺旋递归验证")
    print("=" * 60)
    
    N0 = 48
    seeds = [42, 123, 256, 789, 1024]
    n_rounds = 5
    max_layers = 8
    
    all_results = {}
    
    for group_key in ['G1_control', 'G2_energy_only', 'G3_selfref_only', 'G4_spiral']:
        print(f"\n[exp_213] 运行组 {group_key}...")
        results = run_group(group_key, seeds, N0=N0, max_layers=max_layers, 
                           n_rounds=n_rounds, verbose=False)
        
        non_repeat_scores = [r['metrics']['non_repeat_score'] for r in results if r['metrics']]
        depth_vars = [r['metrics']['depth_var'] for r in results if r['metrics']]
        entropy_vars = [r['metrics']['entropy_var'] for r in results if r['metrics']]
        avg_depth_diffs = [r['metrics']['avg_depth_diff'] for r in results if r['metrics']]
        entropy_drifts = [r['metrics']['entropy_drift'] for r in results if r['metrics']]
        spiral_scores = [r['metrics']['avg_spiral'] for r in results if r['metrics']]
        
        avg_nr = np.mean(non_repeat_scores) if non_repeat_scores else 0.0
        std_nr = np.std(non_repeat_scores) if non_repeat_scores else 0.0
        avg_dv = np.mean(depth_vars) if depth_vars else 0.0
        avg_ev = np.mean(entropy_vars) if entropy_vars else 0.0
        avg_add = np.mean(avg_depth_diffs) if avg_depth_diffs else 0.0
        avg_ed = np.mean(entropy_drifts) if entropy_drifts else 0.0
        avg_sp = np.mean(spiral_scores) if spiral_scores else 0.0
        
        all_results[group_key] = {
            'seeds': seeds,
            'n_seeds': len(seeds),
            'n_rounds': n_rounds,
            'avg_non_repeat_score': avg_nr,
            'std_non_repeat_score': std_nr,
            'avg_depth_var': avg_dv,
            'avg_entropy_var': avg_ev,
            'avg_depth_diff': avg_add,
            'avg_entropy_drift': avg_ed,
            'avg_spiral_score': avg_sp,
            'per_seed': results,
        }
        
        print(f"  [{group_key}] 非重复性分数={avg_nr:.4f}±{std_nr:.4f}, "
              f"深度方差={avg_dv:.3f}, 熵方差={avg_ev:.4f}, "
              f"深度漂移={avg_add:.3f}, 熵漂移={avg_ed:.4f}, "
              f"螺旋分={avg_sp:.3f}")
    
    # ============ H23-2 假设验证 ============
    print("\n" + "=" * 60)
    print("H23-2 假设验证: 能量驱动螺旋递归")
    print("=" * 60)
    
    g4_nr = all_results['G4_spiral']['avg_non_repeat_score']
    g3_nr = all_results['G3_selfref_only']['avg_non_repeat_score']
    g1_nr = all_results['G1_control']['avg_non_repeat_score']
    g2_nr = all_results['G2_energy_only']['avg_non_repeat_score']
    
    # 阈值
    h23_2a_pass = g4_nr > g3_nr * 1.3  # 能量提升30%以上
    h23_2b_pass = g4_nr > g1_nr * 2.0  # 相比基线翻倍
    g4_ed = all_results['G4_spiral']['avg_entropy_drift']
    h23_2c_pass = g4_ed > 0.05          # 熵漂移显著
    
    g4_sp = all_results['G4_spiral']['avg_spiral_score']
    g3_sp = all_results['G3_selfref_only']['avg_spiral_score']
    h23_2d_pass = g4_sp > g3_sp * 1.2  # 螺旋性增强
    
    print(f"\nH23-2a: G4_spiral非重复性 > G3_selfref_only×1.3?")
    print(f"  G4={g4_nr:.4f}, G3={g3_nr:.4f}, 比值={g4_nr/max(g3_nr,0.001):.3f} → {'✅ PASS' if h23_2a_pass else '❌ FAIL'}")
    
    print(f"\nH23-2b: G4_spiral非重复性 > G1_control×2?")
    print(f"  G4={g4_nr:.4f}, G1={g1_nr:.4f}, 比值={g4_nr/max(g1_nr,0.001):.3f} → {'✅ PASS' if h23_2b_pass else '❌ FAIL'}")
    
    print(f"\nH23-2c: G4熵漂移 > 0.05?")
    print(f"  G4_entropy_drift={g4_ed:.4f} → {'✅ PASS' if h23_2c_pass else '❌ FAIL'}")
    
    print(f"\nH23-2d: G4螺旋性 > G3螺旋性×1.2?")
    print(f"  G4_spiral={g4_sp:.3f}, G3_spiral={g3_sp:.3f} → {'✅ PASS' if h23_2d_pass else '❌ FAIL'}")
    
    # 核心洞察
    print(f"\n{'='*60}")
    print("核心洞察")
    print(f"{'='*60}")
    print(f"G1_control (无自指无能量) 非重复性={g1_nr:.4f}")
    print(f"G2_energy_only (能量)        非重复性={g2_nr:.4f}")
    print(f"G3_selfref_only (自指)      非重复性={g3_nr:.4f}")
    print(f"G4_spiral (能量+自指)       非重复性={g4_nr:.4f}")
    print(f"\n如果 G3 > G1+G2: 自指是涌现驱动力, 能量增强其螺旋性")
    print(f"如果 G4 > G3×1.3: 能量将自指增强为螺旋递归")
    print(f"如果 G2 ≈ G1: 能量在无自指时无效果 (与P1一致)")
    
    # 组间对比表
    print(f"\n{'='*60}")
    print("组间对比")
    print(f"{'='*60}")
    print(f"{'组':<20} {'非重复分':>10} {'深度方差':>10} {'熵方差':>10} {'熵漂移':>10} {'螺旋分':>10}")
    for gk in ['G1_control', 'G2_energy_only', 'G3_selfref_only', 'G4_spiral']:
        g = all_results[gk]
        print(f"{gk:<20} {g['avg_non_repeat_score']:>10.4f} {g['avg_depth_var']:>10.3f} "
              f"{g['avg_entropy_var']:>10.4f} {g['avg_entropy_drift']:>10.4f} {g['avg_spiral_score']:>10.3f}")
    
    n_pass = sum([h23_2a_pass, h23_2b_pass, h23_2c_pass, h23_2d_pass])
    
    # 保存结果
    output = {
        'experiment': 'exp_213_p2_spiral_recursion',
        'hypothesis': 'H23-2: 能量驱动螺旋递归 (非重复性+不可逆性)',
        'timestamp': __import__('datetime').datetime.now().isoformat(),
        'config': {
            'N0': N0, 'seeds': seeds, 'n_rounds': n_rounds, 'max_layers': max_layers,
        },
        'groups': {gk: {
            'avg_non_repeat_score': all_results[gk]['avg_non_repeat_score'],
            'std_non_repeat_score': all_results[gk]['std_non_repeat_score'],
            'avg_depth_var': all_results[gk]['avg_depth_var'],
            'avg_entropy_var': all_results[gk]['avg_entropy_var'],
            'avg_depth_diff': all_results[gk]['avg_depth_diff'],
            'avg_entropy_drift': all_results[gk]['avg_entropy_drift'],
            'avg_spiral_score': all_results[gk]['avg_spiral_score'],
            'n_seeds': all_results[gk]['n_seeds'],
            'n_rounds': all_results[gk]['n_rounds'],
        } for gk in all_results},
        'hypothesis_results': {
            'H23-2a': {'pass': h23_2a_pass, 'g4': g4_nr, 'g3': g3_nr, 'ratio': g4_nr/max(g3_nr,0.001)},
            'H23-2b': {'pass': h23_2b_pass, 'g4': g4_nr, 'g1': g1_nr, 'ratio': g4_nr/max(g1_nr,0.001)},
            'H23-2c': {'pass': h23_2c_pass, 'g4_entropy_drift': g4_ed, 'threshold': 0.05},
            'H23-2d': {'pass': h23_2d_pass, 'g4_spiral': g4_sp, 'g3_spiral': g3_sp},
        },
        'summary': {
            'n_pass': n_pass,
            'n_total': 4,
            'overall_pass': n_pass >= 3,
        },
    }
    
    out_path = os.path.join(PROJECT_ROOT, 'engine_v2', 'results', 'exp_213_p2_spiral.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n✅ 结果已保存: {out_path}")
    print(f"H23-2 结果: {n_pass}/4 PASS → {'✅ 假设通过' if n_pass >= 3 else '⚠️ 部分通过' if n_pass >= 2 else '❌ 假设失败'}")
    
    return output


if __name__ == '__main__':
    main()
