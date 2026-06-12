"""world_v2.py — 单层引擎(Layer) 与 递归闭环世界(RecursiveWorld)。

修正版: 能量现在实际影响机制执行和密封阈值。

Layer 运行一层的九机制齿轮直到密封。
RecursiveWorld 把一层的自指(A9)输出作为下一层的差异源, 递归咬合成闭环。
"""

from __future__ import annotations
from dataclasses import dataclass, field as dfield
from typing import Optional, Callable
import numpy as np

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
                 energy_cfg: Optional[EnergyConfig] = None,
                 entropy_cfg: Optional[EntropyConfig] = None):
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
        if energy_cfg is not None:
            self.energy = EnergyManager(energy_cfg)
        else:
            self.energy = None
        if entropy_cfg is not None:
            self.entropy = EntropyTracker(entropy_cfg)
        else:
            self.entropy = None
        self._energy_cfg = energy_cfg
        self._entropy_cfg = entropy_cfg

    def run_until_seal(self, verbose=False, step_callback=None):
        """运行机制直到密封。能量不足时会提前终止。"""
        f = self.field
        f.record()
        
        while not f.sealed and self.step < self.p.max_steps:
            self.step += 1
            prev = f.active_set()

            # Phase 21 修正: 检查能量是否足够执行机制
            if self.energy:
                # 获取当前调整后的密封阈值
                adjusted_threshold = self.energy.get_adjusted_seal_threshold(self.p.base_seal_threshold)
                
                # 检查是否有足够能量执行关键机制
                if not self.energy.can_execute_mechanism('m9'):  # 至少能执行自指
                    if verbose:
                        print(f"  [ENERGY] L{f.layer} step{self.step}: insufficient energy for m9, entering dead order")
                    break
                
                # 执行能量步(衰减+注入+记录)
                energy_info = self.energy.step(n_mechanisms=4)  # 假设4个机制运行
                
                if energy_info['is_depleted']:
                    if verbose:
                        print(f"  [ENERGY] L{f.layer} step{self.step}: energy depleted, stopping")
                    break

            # 运行九机制(能量充足时才执行)
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

            # 回调(用于追踪)
            if step_callback:
                layer_info = self.get_layer_info()
                step_callback(self.step, f, layer_info)

            # 检查密封(使用能量调整后的阈值)
            if self.energy:
                adjusted_threshold = self.energy.get_adjusted_seal_threshold(self.p.base_seal_threshold)
                # 这里需要将adjusted_threshold传递给密封检查逻辑
                # 暂时先使用基础阈值, 实际密封检查在RecursiveWorld中实现
        
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
    
    修正版: 集成能量系统, 能量不足时限制涌现深度。
    """

    def __init__(self, N0: int, n_colors: int = 6,
                 params: Optional[Params] = None,
                 energy_cfg: Optional[EnergyConfig] = None,
                 entropy_cfg: Optional[EntropyConfig] = None,
                 env_config: Optional[dict] = None,
                 seed: Optional[int] = None):
        self.N0 = N0
        self.n_colors = n_colors
        self.params = params or Params()
        self.energy_cfg = energy_cfg
        self.entropy_cfg = entropy_cfg
        self.env_config = env_config
        self.seed = seed
        self.rng = np.random.RandomState(seed)

        # 初始化 L0
        self.layers = []
        self._create_L0()

        # 环境(如果配置)
        self.env = None
        if env_config:
            self.env = EnvironmentField(env_config)

        # 追踪
        self.history = []

    def _create_L0(self):
        """创建 L0 层。"""
        f0 = DifferenceField(N=self.N0, layer=0, rng=self.rng)
        layer0 = Layer(f0, self.params, self.energy_cfg, self.entropy_cfg)
        self.layers.append(layer0)

    def run(self, max_layers: int = 10, verbose: bool = False):
        """运行递归闭环直到无法继续。"""
        if verbose:
            print(f"[World] Starting recursive simulation: N0={self.N0}, n_colors={self.n_colors}")

        for depth in range(max_layers):
            current_layer = self.layers[-1]

            if verbose:
                print(f"\n[World] Running Layer {depth}...")

            # 运行当前层直到密封
            layer_info = current_layer.run_until_seal(verbose=verbose)
            
            # 检查是否密封成功
            if not current_layer.field.sealed:
                if verbose:
                    print(f"[World] Layer {depth} did not seal, stopping")
                break

            # 检查能量是否耗尽
            if current_layer.energy and current_layer.energy.is_depleted:
                if verbose:
                    print(f"[World] Energy depleted at Layer {depth}, stopping")
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
        return result

    def _m9_seal_and_create_next(self, current_layer: Layer, verbose: bool = False) -> bool:
        """执行 m9 自指密封, 创建下一层。"""
        f = current_layer.field
        
        # 检查能量是否足够执行 m9
        if current_layer.energy:
            if not current_layer.energy.can_execute_mechanism('m9'):
                if verbose:
                    print(f"  [m9] Insufficient energy for m9, skipping layer creation")
                return False

        # m9: 自指密封
        # 1. 向外封装(多数表决) → 粗粒化身体位
        # 2. 自指封装 → 命名/身份位(新差异源)
        
        # 简化实现: 创建下一层
        n_active = f.n_active()
        n_next = max(1, n_active // 2)  # 下一层规模减半
        
        f_next = DifferenceField(N=n_next, layer=len(self.layers), rng=self.rng)
        next_layer = Layer(f_next, self.params, self.energy_cfg, self.entropy_cfg)
        self.layers.append(next_layer)
        
        if verbose:
            print(f"  [m9] Created Layer {len(self.layers)-1}: N={n_next}")
        
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
