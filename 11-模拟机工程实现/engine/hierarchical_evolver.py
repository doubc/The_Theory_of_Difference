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
from typing import List, Optional, Dict, Tuple, Callable
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver, SpatialSnapshot
from engine.hierarchy_manager import HierarchyManager, LayerState, BiasField
from engine.encapsulation_engine import EncapsulationEngine
from engine.xiang_detector import XiàngDetector
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from layers.three_dim_hamming import ThreeDimHammingLattice


class HierarchicalSnapshot:
    """跨层级快照"""
    def __init__(self, step: int, layer: int, state: torch.Tensor,
                 w: int, n_active: int, n_frozen: int,
                 n_inject: int, n_absorb: int, n_lateral: int,
                 sealed: bool, coords_3d: Optional[np.ndarray] = None,
                 gravity_potential: Optional[torch.Tensor] = None):
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
        self.gravity_potential = gravity_potential.clone() if gravity_potential is not None else None


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
                 auto_encapsulate: bool = True,
                 verbose_gravity: bool = False,
                 # Phase 2 P0 组件（可选，用于演化时实时检测）
                 xiang_detector: Optional[XiàngDetector] = None,
                 persistent_bias_memory: Optional[PersistentBiasMemory] = None,
                 cumulative_selector: Optional[CumulativeSelector] = None,
                 # Phase 2 P1 组件（可选，用于演化时实时检测）
                 six_threshold_detector: Optional[SixThresholdDetector] = None,
                 pre_subjectivity_convergence: Optional[PreSubjectivityConvergence] = None,
                 # P1 评估间隔（每多少个 P0 检测周期执行一次 P1 评估）
                 p1_eval_interval: int = 5,
                 phase2_verbose: bool = False):
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
            verbose_gravity: 是否打印引力调制详情
        """
        self.N0 = N0
        self.steps_per_layer = steps_per_layer
        self.sample_interval = sample_interval
        self.max_layers = max_layers
        self.device = device
        self.auto_encapsulate = auto_encapsulate
        self._verbose_gravity = verbose_gravity

        # Phase 2 P0 组件
        self.xiang_detector = xiang_detector
        self.persistent_bias_memory = persistent_bias_memory
        self.cumulative_selector = cumulative_selector
        # Phase 2 P1 组件
        self.six_threshold_detector = six_threshold_detector
        self.pre_subjectivity_convergence = pre_subjectivity_convergence
        self._p1_eval_interval = p1_eval_interval
        self._phase2_verbose = phase2_verbose
        self._phase2_layer_results: Dict[int, List[Dict]] = {}  # layer -> [step_results]

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

    def _compute_cross_layer_gravity(self, source_layer_id: int,
                                     target_layer_id: int) -> torch.Tensor:
        """计算跨层级引力势

        冻结比特作为质量分布，通过封装映射影响上层创建引力势场。
        每个上层比特接收来自其源比特的引力贡献。

        Args:
            source_layer_id: 源层（包含冻结比特的层）
            target_layer_id: 目标层（受引力影响的层）

        Returns:
            引力势向量 Φ[0..N_target-1]，值越高表示该位置越"深"
        """
        source_layer = self.hierarchy.get_layer(source_layer_id)
        target_layer = self.hierarchy.get_layer(target_layer_id)

        N_target = target_layer.n_bits
        if N_target == 0:
            return torch.zeros(1, device=self.device)

        # 获取冻结比特索引
        frozen_indices = list(source_layer.constraints.sealed_bits)
        if not frozen_indices:
            return torch.zeros(N_target, device=self.device)

        # 构建源层比特到质量的映射
        # 冻结比特值=1的为"正质量"，值=0的为"负质量"
        source_masses = source_layer.state.cpu()  # [N_source]

        # 获取封装信息：每个目标比特对应哪些源比特
        enc_bits = self.hierarchy.encap_engine.encapsulated_bits.get(source_layer_id + 1, [])

        # 计算每个目标比特的引力势
        # Φ[i] = Σ_{j in source_bits_of_target[i]} mass[j] / (d_H(i,j) + eps)
        # 使用软化核避免除零
        epsilon = 0.5  # 软化参数（离散空间需要更大的软化）

        potentials = torch.zeros(N_target, device=self.device)

        # 计算目标层中活跃比特数：N_target = n_active + n_enc
        # 封装比特在高层中的实际索引 = n_active + enc_bit.bit_id
        n_enc = len(enc_bits)
        n_active = N_target - n_enc

        # 遍历每个封装比特
        for enc_bit in enc_bits:
            # enc_bit.bit_id 是封装比特在 [0, 1, 2, ...] 中的顺序
            # 实际在目标层的索引 = n_active + enc_bit.bit_id
            target_idx = n_active + enc_bit.bit_id
            source_bits = enc_bit.source_bits

            if not source_bits or target_idx >= N_target:
                continue

            # 计算到每个源比特的汉明距离（离散空间，距离=1）
            # 由于跨层映射，每个源比特到目标比特所属的簇的距离为1
            # 势能 = Σ mass[j] * (1 / (1 + eps)) = Σ mass[j] / (1 + eps)
            total_mass = sum(source_masses[j] for j in source_bits)

            # 引力势 = -total_mass / (1 + eps) （负号表示吸引）
            potentials[target_idx] = -total_mass / (1.0 + epsilon)

        # 归一化势能范围到 [0, 1]
        potential_min = potentials.min()
        potential_max = potentials.max()
        if potential_max > potential_min:
            potentials = (potentials - potential_min) / (potential_max - potential_min)
        else:
            potentials = torch.zeros_like(potentials)

        return potentials

    def _apply_cross_layer_gravity_modulation(self, target_layer_id: int):
        """应用跨层级引力调制

        基于下层的冻结比特分布，计算引力势并存储供后续分析。
        引力势表示下层质量分布对上层动力学的影响程度。

        这实现了"质量弯曲时空"的离散版本：
        - 冻结比特（质量）弯曲层级空间
        - 弯曲的空间调制上层粒子的动力学

        注意：目前版本计算并存储势能，实际的源/汇调制需要后续
        在 SpatialLongRangeEvolver 中检查 gravity_potential 属性。
        """
        if target_layer_id == 0:
            return  # 第0层没有下层

        source_layer_id = target_layer_id - 1

        # 计算引力势
        gravity_potential = self._compute_cross_layer_gravity(
            source_layer_id, target_layer_id
        )

        target_layer = self.hierarchy.get_layer(target_layer_id)

        # 计算平均势能
        mean_potential = gravity_potential.mean().item()
        max_potential = gravity_potential.max().item()

        # 存储引力势信息到layer供后续分析和可视化
        target_layer.gravity_potential = gravity_potential
        target_layer.gravity_mean = mean_potential
        target_layer.gravity_max = max_potential

        # 将势能存储到constraints供演化器查询
        # 格式：[Φ_0, Φ_1, ..., Φ_{N-1}]
        target_layer.constraints.gravity_potential = gravity_potential
        target_layer.constraints.gravity_mean = mean_potential
        target_layer.constraints.gravity_modulation = True  # 标记是否启用调制

        if hasattr(self, '_verbose_gravity') and self._verbose_gravity:
            source_layer = self.hierarchy.get_layer(source_layer_id)
            print(f"    [GRAVITY] L{source_layer_id}→L{target_layer_id}: "
                  f"Φ_mean={mean_potential:.4f}, Φ_max={max_potential:.4f}, "
                  f"N_target={target_layer.n_bits}, "
                  f"frozen_source={len(source_layer.constraints.sealed_bits)}")

    def _make_phase2_callback(self, layer_id: int, N: int) -> Optional[Callable]:
        """构建 Phase 2 步骤回调

        在演化器每 sample_interval 步调用一次，执行：
        P0（每步执行）:
          1. XiàngDetector — 底象检测（基于状态构建差异矩阵）
          2. PersistentBiasMemory — 记录当前步的偏置
          3. CumulativeSelector — 记录延续结果
        P1（每 p1_eval_interval 步执行）:
          4. SixThresholdDetector — 六阈值同步检测
          5. PreSubjectivityConvergence — 前主体态收束判定

        Args:
            layer_id: 当前层 ID
            N: 当前层比特数

        Returns:
            callback 函数，如果没有任何 Phase 2 组件则返回 None
        """
        has_p2 = (self.xiang_detector is not None or
                 self.persistent_bias_memory is not None or
                 self.cumulative_selector is not None or
                 self.six_threshold_detector is not None or
                 self.pre_subjectivity_convergence is not None)
        if not has_p2:
            return None

        # 为每个层初始化检测结果列表
        if layer_id not in self._phase2_layer_results:
            self._phase2_layer_results[layer_id] = []

        # P1 评估计数器（按层独立计数）
        p1_counter = {'value': 0}

        def callback(step: int, state: torch.Tensor,
                     snapshot: 'SpatialSnapshot',
                     constraints) -> None:
            """Phase 2 步骤回调"""
            result_entry = {'step': step, 'layer': layer_id}

            # ── P0: 每步执行 ──

            # 1. XiàngDetector: 从当前状态构建差异矩阵并检测底象
            if self.xiang_detector is not None:
                # 构建差异矩阵: D[i,j] = |state[i] - state[j]|
                D = (state.float().unsqueeze(1) - state.float().unsqueeze(0)).abs()
                D = (D + D.T) / 2  # 确保对称
                D.fill_diagonal_(0)
                # 归一化
                D_max = D.max()
                if D_max > 1e-8:
                    D = D / D_max

                xiang_result = self.xiang_detector.detect(
                    D, timestamp=layer_id * 10000 + step)
                result_entry['xiang'] = {
                    'formed': xiang_result.xiang_formed,
                    'density': xiang_result.organization_density,
                    'trace': xiang_result.traceability_score,
                    'continuity': xiang_result.continuity_length,
                }
                if self._phase2_verbose and xiang_result.xiang_formed:
                    print(f"    [Xiàng] L{layer_id} step={step}: "
                          f"density={xiang_result.organization_density:.3f}, "
                          f"trace={xiang_result.traceability_score:.3f}, "
                          f"continuity={xiang_result.continuity_length}")

            # 2. PersistentBiasMemory: 记录当前步的偏置
            if self.persistent_bias_memory is not None:
                # 使用方向场作为偏置向量
                direction = constraints.direction.clone()
                bf = BiasField(
                    source_layer=layer_id,
                    target_layer=layer_id + 1,
                    bias_vector=direction.float(),
                    strength=min(1.0, len(constraints.active_bits) / max(1, N)),
                    origin_step=layer_id * 10000 + step,
                )
                self.persistent_bias_memory.record(
                    bf, timestamp=layer_id * 10000 + step,
                    metadata={'layer': layer_id, 'step': step}
                )
                result_entry['bias_memory'] = {
                    'entries': self.persistent_bias_memory.n_entries,
                    'strength': bf.strength,
                }

            # 3. CumulativeSelector: 记录活跃比特的延续
            if self.cumulative_selector is not None:
                active_bits = list(constraints.active_bits)
                frozen_bits = list(constraints.sealed_bits)
                # 活跃变体: 记录为保留
                for bit_id in active_bits[:10]:  # 限制数量避免过多记录
                    variant_id = f"L{layer_id}_b{bit_id}"
                    self.cumulative_selector.record_continuation(
                        variant_id, retained=True)
                # 冻结变体: 记录为不再延续
                for bit_id in frozen_bits[:10]:
                    variant_id = f"L{layer_id}_b{bit_id}"
                    self.cumulative_selector.record_continuation(
                        variant_id, retained=False)
                result_entry['cumulative_selection'] = {
                    'active_tracked': min(len(active_bits), 10),
                    'frozen_tracked': min(len(frozen_bits), 10),
                }

            # ── P1: 每隔 p1_eval_interval 步执行 ──
            p1_counter['value'] += 1
            if p1_counter['value'] >= self._p1_eval_interval:
                p1_counter['value'] = 0

                # 收集六阈值检测所需的参数
                active_count = len(constraints.active_bits)
                frozen_count = len(constraints.sealed_bits)
                total_bits = max(1, active_count + frozen_count)
                ts = layer_id * 10000 + step

                # 从 PersistentBiasMemory 获取保持深度（条目数作为代理）
                bias_depth = 0.0
                if self.persistent_bias_memory is not None:
                    bias_depth = float(self.persistent_bias_memory.n_entries)

                # 从 CumulativeSelector 收集各变体的延续概率
                variant_probs = None
                if self.cumulative_selector is not None:
                    active_bits = list(constraints.active_bits)
                    probs = {}
                    for bit_id in active_bits[:10]:
                        vid = f"L{layer_id}_b{bit_id}"
                        t = self.cumulative_selector.get_trend(vid)
                        if t is not None:
                            probs[vid] = max(0.0, min(1.0, t))
                    if len(probs) >= 2:
                        variant_probs = probs

                # 界面调节度: 活跃比特比例
                interface_regulation = active_count / total_bits

                # 自维持稳健性: 方向一致性
                self_sustaining = 0.0
                if active_count > 0 and hasattr(constraints, 'direction'):
                    dir_vals = constraints.direction.float()
                    active_indices = list(constraints.active_bits)
                    if len(active_indices) > 0:
                        active_dir = dir_vals[active_indices]
                        mean_dir = active_dir.mean().item()
                        if abs(mean_dir) > 1e-8:
                            agreement = (active_dir.sign() * np.sign(mean_dir)).mean().item()
                            self_sustaining = max(0.0, (agreement + 1) / 2)

                # 4. SixThresholdDetector: 六阈值同步检测
                if self.six_threshold_detector is not None:
                    threshold_result = self.six_threshold_detector.detect(
                        active_exchanges=active_count,
                        total_boundary_edges=total_bits,
                        rebuild_success_count=int(self_sustaining * 10),
                        perturbation_count=10,
                        bias_recursion_depth=bias_depth,
                        replicated_pattern=state if active_count > 0 else None,
                        original_pattern=state,
                        variant_continuation_probs=variant_probs,
                        component_contributions=None,
                        timestamp=ts,
                    )
                    result_entry['six_threshold'] = {
                        'all_met': threshold_result.all_met,
                        'n_met': threshold_result.n_met,
                        'bottleneck': threshold_result.bottleneck,
                    }
                    if self._phase2_verbose:
                        status = "PASS" if threshold_result.all_met else f"{threshold_result.n_met}/6"
                        bn = f" bottleneck={threshold_result.bottleneck}" if not threshold_result.all_met else ""
                        print(f"    [6Threshold] L{layer_id} step={step}: {status}{bn}")

                # 5. PreSubjectivityConvergence: 前主体态收束判定
                if self.pre_subjectivity_convergence is not None:
                    threshold_params = {
                        'active_exchanges': active_count,
                        'total_boundary_edges': total_bits,
                        'rebuild_success_count': int(self_sustaining * 10),
                        'perturbation_count': 10,
                        'bias_recursion_depth': bias_depth,
                        'variant_continuation_probs': variant_probs,
                    }

                    conv_result = self.pre_subjectivity_convergence.evaluate(
                        threshold_params=threshold_params,
                        structure_state=state.float(),
                        timestamp=ts,
                    )
                    result_entry['convergence'] = {
                        'converged': conv_result.converged,
                        'thresholds_met': conv_result.six_thresholds_met,
                        'coupling_met': conv_result.coupling_strength_met,
                        'stability_met': conv_result.stability_met,
                        'firewall_passed': conv_result.semantic_firewall_passed,
                        'n_coupled_pairs': conv_result.n_coupled_pairs,
                        'stability_score': conv_result.stability_score,
                    }
                    if self._phase2_verbose:
                        if conv_result.converged:
                            print(f"    [Convergence] L{layer_id} step={step}: "
                                  f"*** PRE-SUBJECTIVE CONVERGED ***")
                        else:
                            missing = []
                            if not conv_result.six_thresholds_met:
                                missing.append('thresholds')
                            if not conv_result.coupling_strength_met:
                                missing.append('coupling')
                            if not conv_result.stability_met:
                                missing.append('stability')
                            print(f"    [Convergence] L{layer_id} step={step}: "
                                  f"not converged, missing={','.join(missing)}")

            self._phase2_layer_results[layer_id].append(result_entry)

        return callback

    def _run_layer(self, layer_id: int, steps: int,
                   initial_state: Optional[torch.Tensor] = None,
                   verbose: bool = True) -> Dict:
        """在指定层运行空间演化

        使用 SpatialLongRangeEvolver 的完整逻辑。
        如果演化过程中 A9 触发封口，立即封装并创建新层。

        Phase 2: 如果提供了 xiang_detector / persistent_bias_memory /
        cumulative_selector，会通过 step_callback 在演化过程中实时检测。
        """
        layer = self.hierarchy.get_layer(layer_id)
        N = layer.n_bits

        # 确保空间嵌入层存在
        if layer_id not in self.spatial_layers:
            self._init_spatial_layer(layer_id, N, L=1.0)

        # 【跨层级引力调制】
        # 在层 > 0 时，基于下层冻结比特的引力势调制当前层源/汇动力学
        if layer_id > 0:
            self._apply_cross_layer_gravity_modulation(layer_id)

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

        # Phase 2: 构建 step_callback
        step_callback = self._make_phase2_callback(layer_id, evolver.N)

        # 设置初始状态
        if initial_state is not None:
            # pad initial_state 如果需要
            if evolver.N > initial_state.shape[0]:
                pad_size = evolver.N - initial_state.shape[0]
                initial_state = torch.cat([
                    initial_state,
                    torch.zeros(pad_size, device=self.device)
                ])
            result = evolver.run(initial_state=initial_state, verbose=verbose,
                                 step_callback=step_callback)
        else:
            result = evolver.run(verbose=verbose,
                                 step_callback=step_callback)

        # 同步回层级状态
        layer.state = result['final_state']
        layer.constraints = evolver.constraints

        # 记录快照
        gravity_potential = getattr(layer, 'gravity_potential', None)
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
                coords_3d=snap.coords_3d,
                gravity_potential=gravity_potential
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
        layer_results = []
        for i in range(self.hierarchy.n_layers):
            lr = {
                'layer': i,
                'N': self.hierarchy.get_layer(i).n_bits,
                'w': self.hierarchy.get_layer(i).hamming_weight,
                'sealed': self.hierarchy.get_layer(i).is_sealed,
                'steps': self.hierarchy.get_layer(i).step_count,
                'inj': self.hierarchy.get_layer(i).constraints.total_injected,
                'abs': self.hierarchy.get_layer(i).constraints.total_absorbed,
                'cycles': len(self.hierarchy.get_layer(i).constraints.cycle_states),
                'clusters': self.hierarchy.get_layer(i).constraints.get_clusters(),
                'binding_strength': self.hierarchy.get_layer(i).constraints.binding_strength.clone(),
                'direction': self.hierarchy.get_layer(i).constraints.direction.clone(),
                'active_bits': self.hierarchy.get_layer(i).constraints.active_bits.copy(),
                'snapshots': [s.state.clone() for s in self.snapshots if s.layer == i],
            }
            # Phase 2: 附加实时检测结果
            if i in self._phase2_layer_results:
                lr['phase2_step_results'] = self._phase2_layer_results[i]
                # 汇总 XiàngDetector 结果
                xiang_results = [r['xiang'] for r in self._phase2_layer_results[i]
                                 if 'xiang' in r]
                if xiang_results:
                    lr['phase2_xiang_summary'] = {
                        'first_formed_step': next(
                            (r['step'] for r in self._phase2_layer_results[i]
                             if r.get('xiang', {}).get('formed')), None),
                        'max_density': max(r['density'] for r in xiang_results),
                        'max_trace': max(r['trace'] for r in xiang_results),
                        'max_continuity': max(r['continuity'] for r in xiang_results),
                        'n_checks': len(xiang_results),
                        'n_formed': sum(1 for r in xiang_results if r['formed']),
                    }
            layer_results.append(lr)

        return {
            'n_layers': self.hierarchy.n_layers,
            'current_layer': self.hierarchy.current_layer,
            'encapsulation_events': self.encapsulation_events,
            'hierarchy_summary': self.hierarchy.get_hierarchy_summary(),
            'snapshots': self.snapshots,
            'layer_results': layer_results,
            'phase2_summary': {
                # P0
                'xiang_detector_active': self.xiang_detector is not None,
                'bias_memory_entries': (self.persistent_bias_memory.n_entries
                                        if self.persistent_bias_memory else 0),
                'cumulative_selector_active': self.cumulative_selector is not None,
                # P1
                'six_threshold_detector_active': self.six_threshold_detector is not None,
                'pre_subjectivity_convergence_active': self.pre_subjectivity_convergence is not None,
                'pre_subjectivity_converged': (self.pre_subjectivity_convergence.has_converged
                                                if self.pre_subjectivity_convergence else False),
                'convergence_step': (self.pre_subjectivity_convergence.convergence_step
                                      if self.pre_subjectivity_convergence else None),
                # common
                'layers_with_results': list(self._phase2_layer_results.keys()),
            },
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
