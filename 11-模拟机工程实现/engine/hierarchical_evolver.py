"""
engine/hierarchical_evolver.py — 跨层级演化器

将 SpatialLongRangeEvolver 与 HierarchyManager 整合，
实现封口后自动封装并继续在新层演化的完整流程。

核心流程：
1. 在第 0 层运行 SpatialLongRangeEvolver
2. A9 触发封口 → HierarchyManager 执行封装 → 创建第 1 层
3. 在第 1 层继续运行（N 更小）
4. 重复直到达到最大层数或系统稳定

跨层级交互：
- 基底引力调制：冻结比特作为质量分布影响高层级源/汇权重
- 封装比特更新：基底状态变化时更新封装比特值
"""

import torch
import numpy as np
from typing import List, Optional, Dict, Tuple
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver, SpatialSnapshot
from engine.hierarchy_manager import HierarchyManager, LayerState
from engine.encapsulation_engine import EncapsulationEngine
from layers.three_dim_hamming import ThreeDimHammingLattice


class HierarchicalSnapshot:
    """跨层级快照"""
    def __init__(self, step: int, layer: int, state: torch.Tensor,
                 w: int, n_active: int, n_frozen: int,
                 n_inject: int, n_absorb: int, n_lateral: int,
                 sealed: bool, coords_3d: Optional[np.ndarray] = None):
        self.step = step
        self.layer = layer
        self.state = state.clone()
        self.w = w
        self.n_active = n_active
        self.n_frozen = n_frozen
        self.n_inject = n_inject
        self.n_absorb = n_absorb
        self.n_lateral = n_lateral
        self.sealed = sealed
        self.coords_3d = coords_3d.copy() if coords_3d is not None else None


class HierarchicalEvolver:
    """跨层级演化器

    整合 SpatialLongRangeEvolver 的空间演化能力
    和 HierarchyManager 的层级管理能力。

    每层内部使用完整的空间演化逻辑（A1-A9），
    层间通过封装/解封机制交互。
    """

    def __init__(self, N0: int = 48,
                 steps_per_layer: int = 5000,
                 sample_interval: int = 500,
                 max_layers: int = 3,
                 device: str = "cpu",
                 binding_threshold: float = 0.1,
                 min_group_size: int = 2,
                 n_hierarchy_bits: int = None,
                 L: float = 1.0,
                 auto_encapsulate: bool = True):
        """
        Args:
            N0: 第 0 层比特数
            steps_per_layer: 每层运行的步数
            sample_interval: 采样间隔
            max_layers: 最大层数
            device: 设备
            binding_threshold: 封装绑定强度阈值
            min_group_size: 最小组大小
            n_hierarchy_bits: 层级比特数
            L: 空间嵌入尺寸
            auto_encapsulate: A9 触发时是否自动封装
        """
        self.N0 = N0
        self.steps_per_layer = steps_per_layer
        self.sample_interval = sample_interval
        self.max_layers = max_layers
        self.device = device
        self.auto_encapsulate = auto_encapsulate

        # 层级管理器
        self.hierarchy = HierarchyManager(
            N0=N0,
            device=device,
            binding_threshold=binding_threshold,
            min_group_size=min_group_size,
            n_hierarchy_bits=n_hierarchy_bits
        )

        # 空间嵌入层（每层一个）
        self.spatial_layers: Dict[int, ThreeDimHammingLattice] = {}
        self._init_spatial_layer(0, N0, L)

        # 轨迹记录
        self.snapshots: List[HierarchicalSnapshot] = []
        self.encapsulation_events: List[Dict] = []

    def _init_spatial_layer(self, layer_id: int, N: int, L: float):
        """初始化指定层的空间嵌入"""
        if N % 3 != 0:
            N = N + (3 - N % 3)  # 向上取整到 3 的倍数
        self.spatial_layers[layer_id] = ThreeDimHammingLattice(
            N=N, L=L, device=self.device)

    def _get_spatial_coords(self, state: torch.Tensor,
                            layer_id: int) -> np.ndarray:
        """获取状态的 3D 坐标"""
        if layer_id in self.spatial_layers:
            return self.spatial_layers[layer_id].embed_3d(state).cpu().numpy()
        return np.zeros(3)

    def _run_layer(self, layer_id: int, steps: int,
                   initial_state: Optional[torch.Tensor] = None,
                   verbose: bool = True) -> Dict:
        """在指定层运行空间演化

        使用 SpatialLongRangeEvolver 的完整逻辑。
        如果演化过程中 A9 触发封口，立即封装并创建新层。
        """
        layer = self.hierarchy.get_layer(layer_id)
        N = layer.n_bits

        # 确保空间嵌入层存在
        if layer_id not in self.spatial_layers:
            self._init_spatial_layer(layer_id, N, L=1.0)

        # 创建该层的演化器（N 自动对齐到 3 的倍数）
        evolver = SpatialLongRangeEvolver(
            N=N,
            total_steps=steps,
            sample_interval=self.sample_interval,
            device=self.device,
            n_hierarchy_bits=layer.constraints.n_hierarchy,
            L=self.spatial_layers[layer_id].L
        )

        # 同步约束状态
        evolver.constraints = layer.constraints

        # 如果 N 被 pad 了，需要 pad state
        if evolver.N > layer.n_bits:
            pad_size = evolver.N - layer.n_bits
            padded_state = torch.cat([
                layer.state,
                torch.zeros(pad_size, device=self.device)
            ])
            layer.state = padded_state
            layer.n_bits = evolver.N

        # 设置初始状态
        if initial_state is not None:
            # pad initial_state 如果需要
            if evolver.N > initial_state.shape[0]:
                pad_size = evolver.N - initial_state.shape[0]
                initial_state = torch.cat([
                    initial_state,
                    torch.zeros(pad_size, device=self.device)
                ])
            result = evolver.run(initial_state=initial_state, verbose=verbose)
        else:
            result = evolver.run(verbose=verbose)

        # 同步回层级状态
        layer.state = result['final_state']
        layer.constraints = evolver.constraints

        # 记录快照
        for snap in result.get('snapshots', []):
            h_snap = HierarchicalSnapshot(
                step=snap.step + layer.step_count,
                layer=layer_id,
                state=snap.state,
                w=snap.w,
                n_active=len(evolver.constraints.active_bits),
                n_frozen=len(evolver.constraints.sealed_bits),
                n_inject=snap.n_inject,
                n_absorb=snap.n_absorb,
                n_lateral=snap.n_lateral,
                sealed=evolver.constraints.sealed,
                coords_3d=snap.coords_3d
            )
            self.snapshots.append(h_snap)

        layer.step_count += steps

        # 检测 A9 封口（在设置 layer.is_sealed 之前）
        just_sealed = evolver.constraints.sealed and not layer.is_sealed

        # 如果 A9 刚触发封口，立即执行封装（在设置 layer.is_sealed 之前）
        if self.auto_encapsulate and just_sealed:
            enc_info = self.hierarchy.check_and_encapsulate()
            if enc_info is not None:
                self.encapsulation_events.append(enc_info)
                if verbose:
                    print(f"  [ENCAP] L{enc_info['from_layer']} -> "
                          f"L{enc_info['to_layer']}: "
                          f"{enc_info['n_bits_before']} -> {enc_info['n_bits_after']} bits")
                # 初始化新层的空间嵌入
                new_layer = self.hierarchy.get_layer(enc_info['to_layer'])
                self._init_spatial_layer(
                    enc_info['to_layer'], new_layer.n_bits, L=1.0)
                # 更新基底封装值
                self.hierarchy.update_base_encapsulated_values()

        # 同步封口状态
        layer.is_sealed = evolver.constraints.sealed

        return result

    def run(self, verbose: bool = True) -> Dict:
        """运行完整的跨层级演化

        Returns:
            结果字典，包含每层的信息
        """
        self.snapshots = []
        self.encapsulation_events = []

        if verbose:
            print("=" * 70)
            print(f"HierarchicalEvolver: N0={self.N0}, "
                  f"steps_per_layer={self.steps_per_layer}, "
                  f"max_layers={self.max_layers}")
            print("=" * 70)

        for layer_id in range(self.max_layers):
            layer = self.hierarchy.get_layer(layer_id)

            if verbose:
                print(f"\n  --- Layer {layer_id}: N={layer.n_bits}, "
                      f"active={len(layer.active_bits)}, "
                      f"frozen={len(layer.frozen_bits)} ---")

            # 运行该层
            result = self._run_layer(
                layer_id, self.steps_per_layer,
                initial_state=layer.state if layer.step_count > 0 else None,
                verbose=verbose
            )

            if verbose:
                print(f"  Layer {layer_id} done: "
                      f"w={result['final_state'].sum().item():.0f}, "
                      f"sealed={result['sealed']}, "
                      f"inj={result['total_injected']}, "
                      f"abs={result['total_absorbed']}, "
                      f"cycles={result['cycle_states']}")

            # 封装已在 _run_layer 内部处理
            # 如果当前层未封口，额外运行一轮
            if not layer.constraints.sealed:
                if verbose:
                    print(f"  Layer {layer_id} not sealed after "
                          f"{self.steps_per_layer} steps, running extra...")
                extra_steps = self.steps_per_layer // 2
                if extra_steps > 0:
                    result2 = self._run_layer(
                        layer_id, extra_steps, verbose=verbose)
                    if verbose:
                        print(f"  Extra {extra_steps} steps: "
                              f"sealed={result2['sealed']}")

        # 收集结果
        return {
            'n_layers': self.hierarchy.n_layers,
            'current_layer': self.hierarchy.current_layer,
            'encapsulation_events': self.encapsulation_events,
            'hierarchy_summary': self.hierarchy.get_hierarchy_summary(),
            'snapshots': self.snapshots,
            'layer_results': [
                {
                    'layer': i,
                    'N': self.hierarchy.get_layer(i).n_bits,
                    'w': self.hierarchy.get_layer(i).hamming_weight,
                    'sealed': self.hierarchy.get_layer(i).is_sealed,
                    'steps': self.hierarchy.get_layer(i).step_count,
                    'inj': self.hierarchy.get_layer(i).constraints.total_injected,
                    'abs': self.hierarchy.get_layer(i).constraints.total_absorbed,
                    'cycles': len(self.hierarchy.get_layer(i).constraints.cycle_states),
                    'clusters': self.hierarchy.get_layer(i).constraints.get_clusters(),
                }
                for i in range(self.hierarchy.n_layers)
            ]
        }

    def print_results(self, results: Dict):
        """打印结果摘要"""
        print("\n" + "=" * 70)
        print("HIERARCHICAL EVOLUTION RESULTS")
        print("=" * 70)

        for lr in results['layer_results']:
            status = "[SEALED]" if lr['sealed'] else "[OPEN]"
            n_clusters = len(lr['clusters'])
            print(f"\n  Layer {lr['layer']}: {status}")
            print(f"    N={lr['N']}, w={lr['w']}, steps={lr['steps']}")
            print(f"    inj={lr['inj']}, abs={lr['abs']}, "
                  f"cycles={lr['cycles']}, clusters={n_clusters}")

        print(f"\n  Encapsulation events: {len(results['encapsulation_events'])}")
        for i, ev in enumerate(results['encapsulation_events']):
            print(f"    Event {i + 1}: L{ev['from_layer']} → L{ev['to_layer']}, "
                  f"{ev['n_bits_before']} → {ev['n_bits_after']} bits "
                  f"({ev['n_active_preserved']} active + "
                  f"{ev['n_encapsulated']} enc)")

        print("\n" + "=" * 70)
