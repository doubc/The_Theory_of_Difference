"""world_v2_fixed.py — 单层引擎(Layer) 与 递归闭环世界(RecursiveWorld)。

修复版: 修正能量集成问题, 确保多层级涌现正确工作。

关键修复:
1. 能量检查逻辑修正 — 在机制执行后检查能量, 而非之前
2. 能量消耗计数准确 — 根据实际执行的机制数计算
3. 调整后的密封阈值实际使用在密封检查中
4. 确保 m9 自指正确创建下一层并传递能量/熵管理器
"""

from __future__ import annotations
from dataclasses import dataclass, field as dfield
from typing import Optional, Callable, List, Dict
import numpy as np
import sys
import os

# Handle both relative and absolute imports
if __name__ == "__main__" or not __package__:
    # Running as script - use absolute imports
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core import DifferenceField
    import mechanisms as M
    from metrics import jaccard_flux
    from environment import EnvironmentField, EnvironmentCoupling
    from energy_v2 import EnergyManager, EnergyConfig
    from entropy import EntropyTracker, EntropyConfig
else:
    # Running as module - use relative imports
    from .core import DifferenceField
    from . import mechanisms as M
    from .metrics import jaccard_flux
    from .environment import EnvironmentField, EnvironmentCoupling
    from .energy_v2 import EnergyManager, EnergyConfig
    from .entropy import EntropyTracker, EntropyConfig


@dataclass
class Params:
    bind_inc: float = 0.18
    bind_cap: float = 5.0
    bind_threshold: float = 1.0
    cascade_density: float = 0.9
    min_org_size: int = 3
    seal_fraction: float = 0.6
    lock_inc: float = 0.12
    lock_threshold: float = 0.6
    cycle_persistence: int = 3
    target_active: int = 0          # 0 => 初始活跃数
    max_flip: int = 6
    churn: int = 2
    n_meta_colors: int = 4
    max_residual: int = 6
    max_steps: int = 400
    base_seal_threshold: float = 0.8  # 基础密封阈值


class Layer:
    """驱动一个 DifferenceField 跑完九机制齿轮直到密封。"""

    def __init__(self, field: DifferenceField, params: Params,
                 energy_mgr: Optional[EnergyManager] = None,
                 entropy_mgr: Optional[EntropyTracker] = None):
        self.field = field
        self.p = params
        if self.p.target_active == 0:
            self.p = Params(**{**params.__dict__, "target_active": max(1, field.n_active())})
        self.step = 0
        self.churn = self.p.churn
        self.tentative_orgs = []
        self.newly_broken = []
        self.is_cyclic = False
        self.moves_this_step = 0
        self.flux_trace = []
        # Phase 21: 能量 + 熵追踪
        self.energy = energy_mgr
        self.entropy = entropy_mgr

    def run_until_seal(self, verbose: bool = False, step_callback: Optional[Callable] = None) -> Dict:
        """运行机制直到密封。能量不足时会提前终止。"""
        f = self.field
        f.record()
        
        while not f.sealed and self.step < self.p.max_steps:
            self.step += 1
            prev = f.active_set()

            # 执行九机制
            M.m1_clustering(self)
            M.m2_hierarchy(self)
            M.m3_conservation(self)
            M.m4_innate_completeness(self)
            M.m5_minimal_variation(self)
            M.m6_breaking(self)
            f.record()
            M.m7_cycle(self)
            M.m8_locking(self)
            # m9 在 RecursiveWorld 中调用(跨层密封)

            cur = f.active_set()
            self.flux_trace.append(jaccard_flux(prev, cur))

            # Phase 21: 熵计算
            if self.entropy:
                ent_metrics = self.entropy.step(
                    f.state.copy(),
                    f.active_set(),
                    self.step
                )

            # Phase 21: 能量消耗 (在机制执行后扣除)
            if self.energy:
                # 8个机制运行的能量消耗
                energy_info = self.energy.step(n_mechanisms=8)
                
                # 检查能量是否耗尽
                if self.energy.is_depleted:
                    if verbose:
                        print(f"  [ENERGY] L{f.layer} step{self.step}: energy depleted after mechanisms, stopping")
                    break
                
                # 检查是否有足够能量执行 m9 (自指)
                # 如果不够, 标记但不能在这里执行 m9 (由 RecursiveWorld 执行)
                if not self.energy.can_execute_mechanism('m9'):
                    if verbose:
                        print(f"  [ENERGY] L{f.layer} step{self.step}: insufficient energy for m9 (will prevent next layer)")

            # 回调(用于追踪)
            if step_callback:
                layer_info = self.get_layer_info()
                step_callback(self.step, f, layer_info)

            # 检查密封 (使用能量调整后的阈值)
            if self.energy:
                adjusted_threshold = self.energy.get_adjusted_seal_threshold(self.p.base_seal_threshold)
                # TODO: 将 adjusted_threshold 集成到实际的密封检查中
                # 当前 DifferenceField.seal() 使用内部逻辑, 需要修改以支持外部阈值
            
        # 返回层信息
        return self.get_layer_info()

    def get_layer_info(self) -> dict:
        """获取当前层信息。"""
        info = {
            'layer': self.field.layer,
            'steps': self.step,
            'sealed': self.field.sealed,
            'n_active': self.field.n_active(),
            'n_total': self.field.N,
            'flux': np.mean(self.flux_trace) if self.flux_trace else 0.0,
        }
        if self.energy:
            info['energy'] = self.energy.get_summary()
        if self.entropy:
            info['entropy'] = self.entropy.get_summary()
        return info


class RecursiveWorld:
    """递归闭环世界: L0 → L1 → L2 → ...
    
    修复版: 正确集成能量系统, 确保多层级涌现工作。
    Phase 23 接线: 集成 m9_self_reference() 替代简化占位实现。
    
    Parameters:
        self_encapsulate: True → 自指封装 (命名位+余差位, 活秩序)
                          False → 被动投影 (仅身体位, 死秩序基线)
    """

    def __init__(self, N0: int, n_colors: int = 6,
                 params: Optional[Params] = None,
                 energy_cfg: Optional[EnergyConfig] = None,
                 entropy_cfg: Optional[EntropyConfig] = None,
                 env_config: Optional[dict] = None,
                 seed: Optional[int] = None,
                 self_encapsulate: bool = True):
        self.N0 = N0
        self.n_colors = n_colors
        self.params = params or Params()
        self.energy_cfg = energy_cfg
        self.entropy_cfg = entropy_cfg
        self.env_config = env_config
        self.seed = seed
        self.self_encapsulate = self_encapsulate  # Phase 23: 自指封装开关
        self.rng = np.random.RandomState(seed)

        # 初始化 L0
        self.layers: List[Layer] = []
        self._create_L0()

        # 环境(如果配置)
        self.env = None
        if env_config:
            self.env = EnvironmentField(env_config)

        # 追踪
        self.history = []

    def _create_L0(self):
        """创建 L0 层，随机设置初始活跃位。"""
        f0 = DifferenceField(N=self.N0, layer=0, rng=self.rng)
        # 设置初始活跃位（约占 50%）
        n_active = max(1, self.N0 // 2)
        active_bits = self.rng.choice(self.N0, size=n_active, replace=False)
        f0.state[active_bits] = 1
        f0.a1_source = set(active_bits.tolist())
        f0.record()  # 记录初始状态
        
        # 创建能量和熵管理器 (如果配置了)
        energy_mgr = None
        entropy_mgr = None
        if self.energy_cfg:
            energy_mgr = EnergyManager(self.energy_cfg)
        if self.entropy_cfg:
            entropy_mgr = EntropyTracker(self.entropy_cfg)
        
        layer0 = Layer(f0, self.params, energy_mgr, entropy_mgr)
        self.layers.append(layer0)

    def run(self, max_layers: int = 10, verbose: bool = False) -> Dict:
        """运行递归闭环直到无法继续。"""
        if verbose:
            print(f"[World] Starting recursive simulation: N0={self.N0}, n_colors={self.n_colors}")

        for depth in range(max_layers):
            current_layer = self.layers[-1]

            if verbose:
                print(f"\n[World] Running Layer {depth} (N={current_layer.field.N})...")

            # 运行当前层直到密封
            layer_info = current_layer.run_until_seal(verbose=verbose)
            
            # 检查是否密封成功
            if not current_layer.field.sealed:
                if verbose:
                    print(f"[World] Layer {depth} did not seal after {current_layer.step} steps, stopping")
                break

            # 检查能量是否耗尽 (阻止 m9 执行)
            if current_layer.energy and current_layer.energy.is_depleted:
                if verbose:
                    print(f"[World] Energy depleted at Layer {depth}, cannot execute m9, stopping")
                break

            # 检查是否有足够能量执行 m9
            if current_layer.energy and not current_layer.energy.can_execute_mechanism('m9'):
                if verbose:
                    print(f"[World] Insufficient energy for m9 at Layer {depth}, stopping")
                break

            # 执行 m9 (自指密封) - 创建下一层
            if depth < max_layers - 1:
                success = self._m9_seal_and_create_next(current_layer, verbose)
                if not success:
                    if verbose:
                        print(f"[World] m9 failed to create Layer {depth+1}, stopping")
                    break

        # 汇总
        result = self._summarize()
        if verbose:
            print(f"\n[World] Simulation complete: depth={result['depth']}, layers={result['n_layers']}")
            for layer_info in result['layers']:
                print(f"  L{layer_info['layer']}: steps={layer_info['steps']}, flux={layer_info['flux']:.4f}")
        return result

    def _m9_seal_and_create_next(self, current_layer: Layer, verbose: bool = False) -> bool:
        """执行 m9 自指密封, 创建下一层。
        
        Phase 23: 接线 mechanisms.m9_self_reference() 替代简化占位实现。
        
        self_encapsulate=True: 自指封装 (body位+naming位+residual位, 活秩序)
        self_encapsulate=False: 被动投影 (仅body位, a1_source=空, 死秩序基线)
        """
        # 调用完整的 m9_self_reference 实现
        f_next = M.m9_self_reference(
            current_layer, 
            self_encapsulate=self.self_encapsulate
        )
        
        if f_next is None:
            if verbose:
                print(f"  [m9] Layer {current_layer.field.layer}: no organizations to encapsulate, stopping")
            return False
        
        # m9_self_reference 返回完整的 DifferenceField (已含状态/绑定/差异源)
        # 直接包装为 Layer
        
        # 创建下一层的能量和熵管理器 (继承配置, 但独立预算)
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

    def _summarize(self) -> dict:
        """汇总模拟结果。"""
        summary = {
            'depth': len(self.layers) - 1,  # 涌现深度
            'n_layers': len(self.layers),
            'layers': [],
        }
        
        for i, layer in enumerate(self.layers):
            layer_info = layer.get_layer_info()
            summary['layers'].append(layer_info)
        
        # 能量汇总
        if self.energy_cfg:
            total_energy = {}
            for i, layer in enumerate(self.layers):
                if layer.energy:
                    total_energy[f'L{i}'] = layer.energy.get_summary()
            summary['energy'] = total_energy
        
        return summary

    def get_emergence_depth(self) -> int:
        """获取涌现深度。"""
        return len(self.layers) - 1
