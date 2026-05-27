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
from engine.cross_layer_gravity import CrossLayerGravityModulator, GravityField
from engine.xiang_detector import XiàngDetector
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.unsealing_mechanism import UnsealingMechanism, UnsealingEvent
from engine.return_flow_channel import ReturnFlowChannel, HighSemanticPayload, AnchorPoint, ReturnFlowEvent
from engine.organizational_density_index import OrganizationalDensityIndex, DensityIndexResult
from engine.seventh_threshold_detector import SeventhThresholdDetector, SeventhThresholdResult
from engine.cooperative_emergence_detector import CooperativeEmergenceDetector, CooperativeEmergenceResult
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
                 # Phase 2 P0 解封与回流（可选，依赖 pre_subjectivity_convergence）
                 unsealing_mechanism: Optional[UnsealingMechanism] = None,
                 return_flow_channel: Optional[ReturnFlowChannel] = None,
                 # Phase 2 P1 密度/涌现检测器（可选）
                 organizational_density_index: Optional[OrganizationalDensityIndex] = None,
                 seventh_threshold_detector: Optional[SeventhThresholdDetector] = None,
                 cooperative_emergence_detector: Optional[CooperativeEmergenceDetector] = None,
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
        # Phase 2 解封与回流
        self.unsealing_mechanism = unsealing_mechanism
        self.return_flow_channel = return_flow_channel
        # Phase 2 P1 密度/涌现检测器
        self.organizational_density_index = organizational_density_index
        self.seventh_threshold_detector = seventh_threshold_detector
        self.cooperative_emergence_detector = cooperative_emergence_detector
        self._p1_eval_interval = p1_eval_interval
        self._phase2_verbose = phase2_verbose
        self._phase2_layer_results: Dict[int, List[Dict]] = {}  # layer -> [step_results]
        # 解封事件记录
        self._unsealing_events: List[UnsealingEvent] = []
        # 回流事件记录
        self._return_flow_events: List[ReturnFlowEvent] = []

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

        # 跨层级引力调制器（替代原有的 duplicated _compute_cross_layer_gravity）
        self.gravity_modulator = CrossLayerGravityModulator(
            n_layers=max_layers,
            gravity_decay=0.5,
            modulation_strength=0.1,
            distance_exponent=2.0
        )

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
        """计算跨层级引力势（委托给 CrossLayerGravityModulator）

        原实现为手写简化版，仅对封装比特计算质量求和。
        现改用 CrossLayerGravityModulator 的完整引力场模型：
        - 冻结且激活的比特作为质量源
        - 逆距离平方律计算引力势
        - 通过封装映射投影到目标层
        - 应用层间衰减
        """
        source_layer = self.hierarchy.get_layer(source_layer_id)
        target_layer = self.hierarchy.get_layer(target_layer_id)

        N_target = target_layer.n_bits
        if N_target == 0:
            return torch.zeros(1, device=self.device)

        # 质量源 = 源层中冻结且激活的比特
        frozen_indices = list(source_layer.constraints.sealed_bits)
        active_masses = [
            i for i in frozen_indices
            if i < len(source_layer.state) and source_layer.state[i].item() > 0.5
        ]
        if not active_masses:
            return torch.zeros(N_target, device=self.device)

        # 使用 modulator 计算源层的引力场
        state_cpu = source_layer.state.cpu()
        field = self.gravity_modulator.compute_gravity_field(
            layer_id=source_layer_id,
            state=state_cpu,
            frozen_bits=set(frozen_indices),
            active_bits=set(range(len(state_cpu))),
            binding_strength=None,
            step=0
        )

        # 通过封装映射投影到目标层
        encap_engine = self.hierarchy.encap_engine
        projected = self.gravity_modulator.project_gravity_up(
            source_layer_id=source_layer_id,
            source_field=field,
            target_N=N_target,
            encap_engine=encap_engine,
            source_layer=source_layer_id
        )

        return projected

    def _apply_cross_layer_gravity_modulation(self, target_layer_id: int):
        """应用跨层级引力调制（多层聚合）

        收集所有下层引力场（向上牵引）和上层引力场（向下约束），
        通过 CrossLayerGravityModulator.compute_modulation() 聚合为综合调制向量，
        替代原有的单层单向引力计算。

        关键修复：在读取 gravity_fields 之前，先为所有层计算引力场。
        此前 gravity_fields 始终为空，导致调制向量恒为零。
        """
        if target_layer_id == 0:
            return

        # ── 修复：先清理过期引力场，再为所有层计算新引力场 ──
        # 不清理会导致 fields 无限累积， stale 场干扰调制结果并占用内存
        total_steps = sum(
            self.hierarchy.get_layer(lid).step_count
            for lid in range(self.max_layers)
            if self.hierarchy.get_layer(lid).state is not None
        )
        self.gravity_modulator.clear_old_fields(
            max_age_steps=200, current_step=total_steps
        )

        for lid in range(self.max_layers):
            layer = self.hierarchy.get_layer(lid)
            if layer.state is None or layer.state.numel() == 0:
                continue
            frozen_indices = list(layer.constraints.sealed_bits)
            # 引力场的质量源 = 冻结且激活的比特
            state_cpu = layer.state.cpu()
            field = self.gravity_modulator.compute_gravity_field(
                layer_id=lid,
                state=state_cpu,
                frozen_bits=set(frozen_indices),
                active_bits=set(range(len(state_cpu))),
                binding_strength=layer.constraints.binding_strength,
                step=layer.step_count,
            )
            if self._verbose_gravity:
                print(f"    [GRAVITY] L{lid} field computed: mass={field.total_mass}, "
                      f"Φ_mean={field.potential.mean().item():.4f}, "
                      f"Φ_max={field.potential.max().item():.4f}")

        target_layer = self.hierarchy.get_layer(target_layer_id)
        device = self.device
        N = target_layer.n_bits

        # 收集所有下层引力场（向上牵引）和上层引力场（向下约束）
        lower_fields = []
        upper_fields = []
        for lid in range(self.max_layers):
            fields = self.gravity_modulator.gravity_fields.get(lid, [])
            # 只取非空场
            active_fields = [f for f in fields if f.total_mass > 0]
            if lid < target_layer_id:
                lower_fields.extend(active_fields)
            elif lid > target_layer_id:
                upper_fields.extend(active_fields)

        # 构造目标层当前状态（用于调制计算）
        target_state = target_layer.state.clone() if target_layer.state is not None \
            else torch.zeros(N, device=device)
        if len(target_state) < N:
            target_state = torch.cat([target_state, torch.zeros(N - len(target_state), device=device)])
        target_state = target_state[:N]

        # 调用多层调制计算
        mod_result = self.gravity_modulator.compute_modulation(
            layer_id=target_layer_id,
            lower_fields=lower_fields,
            upper_fields=upper_fields,
            target_state=target_state,
        )

        # 综合调制向量 = 向上牵引 - 向下约束
        gravity_potential = mod_result['modulation_vector']
        mean_potential = gravity_potential.mean().item()
        max_potential = gravity_potential.abs().max().item()

        target_layer.gravity_potential = gravity_potential
        target_layer.gravity_mean = mean_potential
        target_layer.gravity_max = max_potential
        target_layer.constraints.gravity_potential = gravity_potential
        target_layer.constraints.gravity_mean = mean_potential
        target_layer.constraints.gravity_modulation = True

        if self._verbose_gravity:
            n_lower = len(lower_fields)
            n_upper = len(upper_fields)
            lower_mass = sum(f.total_mass for f in lower_fields)
            upper_mass = sum(f.total_mass for f in upper_fields)
            print(f"    [GRAVITY] L{target_layer_id} multi-layer modulation: "
                  f"up={n_lower} fields(mass={lower_mass}), "
                  f"down={n_upper} fields(mass={upper_mass}), "
                  f"Φ_mean={mean_potential:.4f}, Φ_max={max_potential:.4f}, "
                  f"N={N}")

    def _make_phase2_callback(self, layer_id: int, N: int) -> Optional[Callable]:
        """构建 Phase 2 步骤回调

        P0（每步执行）:
          1. XiàngDetector — 底象检测
          2. PersistentBiasMemory — 记录偏置
          3. CumulativeSelector — 记录延续结果
        P1（每 p1_eval_interval 步执行）:
          4. SixThresholdDetector — 六阈值同步检测
          5. PreSubjectivityConvergence — 前主体态收束判定
          6. OrganizationalDensityIndex — 组织密度指数（基于六阈值结果）
          7. SeventhThresholdDetector — 第七阈值相变检测（基于 ODI 时间序列）
          8. CooperativeEmergenceDetector — 协同涌现检测（基于六阈值+耦合矩阵）
        """
        has_p2 = (self.xiang_detector is not None or
                 self.persistent_bias_memory is not None or
                 self.cumulative_selector is not None or
                 self.six_threshold_detector is not None or
                 self.pre_subjectivity_convergence is not None or
                 self.unsealing_mechanism is not None or
                 self.return_flow_channel is not None or
                 self.organizational_density_index is not None or
                 self.seventh_threshold_detector is not None or
                 self.cooperative_emergence_detector is not None)
        if not has_p2:
            return None

        if layer_id not in self._phase2_layer_results:
            self._phase2_layer_results[layer_id] = []

        p1_counter = {'value': 0}

        def callback(step: int, state: torch.Tensor,
                     snapshot: 'SpatialSnapshot',
                     constraints) -> None:
            """Phase 2 步骤回调"""
            result_entry = {'step': step, 'layer': layer_id}

            # ── P0: 每步执行 ──

            # 1. XiàngDetector
            if self.xiang_detector is not None:
                D = (state.float().unsqueeze(1) - state.float().unsqueeze(0)).abs()
                D = (D + D.T) / 2
                D.fill_diagonal_(0)
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

            # 2. PersistentBiasMemory
            if self.persistent_bias_memory is not None:
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

            # 3. CumulativeSelector
            if self.cumulative_selector is not None:
                active_bits = list(constraints.active_bits)
                frozen_bits = list(constraints.sealed_bits)
                for bit_id in active_bits[:10]:
                    variant_id = f"L{layer_id}_b{bit_id}"
                    self.cumulative_selector.record_continuation(
                        variant_id, retained=True)
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

                active_count = len(constraints.active_bits)
                frozen_count = len(constraints.sealed_bits)
                total_bits = max(1, active_count + frozen_count)
                ts = layer_id * 10000 + step

                # 保持深度
                bias_depth = 0.0
                if self.persistent_bias_memory is not None:
                    bias_depth = float(self.persistent_bias_memory.n_entries)

                # ── 3.5 选择压力：活跃与冻结变体的保留率差异 ──
                # 注意：constraints.active_bits 可能包含已封口比特
                # 真正活跃的 = active_bits - sealed_bits
                variant_probs = None
                if self.cumulative_selector is not None:
                    sealed_set = constraints.sealed_bits
                    all_active = constraints.active_bits
                    truly_active = sorted(all_active - sealed_set)
                    frozen_bits = sorted(sealed_set)
                    probs = {}
                    # 活跃变体（真正活跃的，非封口）
                    for bit_id in truly_active[:10]:
                        vid = f"L{layer_id}_b{bit_id}"
                        rec = self.cumulative_selector._variants.get(vid)
                        if rec is not None and rec.n_observations > 0:
                            probs[vid] = rec.retention_rate()
                    # 冻结变体
                    has_frozen_data = False
                    for bit_id in frozen_bits[:10]:
                        vid = f"L{layer_id}_b{bit_id}"
                        rec = self.cumulative_selector._variants.get(vid)
                        if rec is not None and rec.n_observations > 0:
                            probs[vid] = rec.retention_rate()
                            has_frozen_data = True
                    # 如果没有冻结变体数据但有冻结比特，补充合成值
                    if not has_frozen_data and len(frozen_bits) > 0:
                        for bit_id in frozen_bits[:5]:
                            probs[f"frozen_{bit_id}"] = 0.0
                    # 如果仍然不足2个，用状态值分化
                    if len(probs) < 2 and len(truly_active) >= 2:
                        for bit_id in truly_active[:5]:
                            probs[f"active_{bit_id}"] = 1.0
                        for bit_id in truly_active[-5:]:
                            probs[f"inactive_{bit_id}"] = 0.0
                    if len(probs) >= 2:
                        variant_probs = probs

                # 界面调节度
                interface_regulation = active_count / total_bits

                # 自维持稳健性
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

                # 功能分化代理
                component_contributions = None
                active_indices = sorted(constraints.active_bits)
                if len(active_indices) >= 2 and hasattr(constraints, 'direction'):
                    dir_vals = constraints.direction.float()
                    contributions = {}
                    for bit_id in active_indices:
                        contributions[f"bit_{bit_id}"] = float(dir_vals[bit_id].abs().item()) + 0.01
                    frozen_indices = sorted(constraints.sealed_bits)
                    for bit_id in frozen_indices:
                        contributions[f"frozen_{bit_id}"] = 0.01
                    if len(contributions) >= 2:
                        component_contributions = contributions

                # ── 耦合矩阵：从方向场相关性计算机制间耦合强度 ──
                coupling_matrix = None
                if hasattr(constraints, 'direction') and active_count >= 2:
                    dir_vals = constraints.direction.float()
                    active_idx = sorted(constraints.active_bits)
                    mech_names = [
                        'interface_regulation', 'self_sustaining', 'retention',
                        'replication', 'selection', 'functional_differentiation'
                    ]
                    # 将活跃比特按索引模6分组，每组代表一个机制
                    mechanism_signals = {name: [] for name in mech_names}
                    for bit_id in active_idx:
                        group = bit_id % 6
                        name = mech_names[group]
                        mechanism_signals[name].append(dir_vals[bit_id].item())
                    # 计算每对机制的耦合强度
                    # 使用组间方向场均值的余弦相似度
                    coupling_matrix = {}
                    for ma in mech_names:
                        coupling_matrix[ma] = {}
                        for mb in mech_names:
                            if ma == mb:
                                coupling_matrix[ma][mb] = 1.0
                            else:
                                sig_a = mechanism_signals[ma] if mechanism_signals[ma] else [0.0]
                                sig_b = mechanism_signals[mb] if mechanism_signals[mb] else [0.0]
                                mean_a = sum(sig_a) / len(sig_a)
                                mean_b = sum(sig_b) / len(sig_b)
                                # 使用归一化的乘积作为耦合强度
                                # 映射到 [0, 1]：当两个机制偏向方向一致时耦合强
                                abs_a = abs(mean_a)
                                abs_b = abs(mean_b)
                                if abs_a < 1e-6 or abs_b < 1e-6:
                                    coupling_matrix[ma][mb] = 0.05
                                else:
                                    # 符号相同 → 正耦合，符号相反 → 负耦合（取绝对值）
                                    sign = 1.0 if mean_a * mean_b > 0 else -1.0
                                    # 几何平均归一化
                                    geo_mean = (abs_a * abs_b) ** 0.5
                                    max_abs = max(abs_a, abs_b)
                                    coupling_matrix[ma][mb] = abs(sign * geo_mean / (max_abs + 0.01))

                # ── 结构保持函数：汉明重量 ±20% ──
                _orig_weight = state.float().sum().item()
                _w_lo = _orig_weight * 0.8
                _w_hi = _orig_weight * 1.2
                def _structure_fn(perturbed_state):
                    w = perturbed_state.float().sum().item()
                    return _w_lo <= w <= _w_hi

                # 4. SixThresholdDetector
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
                        component_contributions=component_contributions,
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

                # 5. PreSubjectivityConvergence
                conv_result = None
                if self.pre_subjectivity_convergence is not None:
                    threshold_params = {
                        'active_exchanges': active_count,
                        'total_boundary_edges': total_bits,
                        'rebuild_success_count': int(self_sustaining * 10),
                        'perturbation_count': 10,
                        'bias_recursion_depth': bias_depth,
                        'variant_continuation_probs': variant_probs,
                        'component_contributions': component_contributions,
                    }

                    conv_result = self.pre_subjectivity_convergence.evaluate(
                        threshold_params=threshold_params,
                        coupling_matrix=coupling_matrix,
                        structure_state=state.float(),
                        structure_fn=_structure_fn,
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

                # 6. UnsealingMechanism — 基于收束结果评估解封等级
                unsealing_event = None
                if self.unsealing_mechanism is not None and conv_result is not None:
                    unsealing_event = self.unsealing_mechanism.evaluate(
                        structure_id=layer_id,
                        convergence_result=conv_result,
                        timestamp=ts,
                    )
                    if unsealing_event is not None:
                        self._unsealing_events.append(unsealing_event)
                        result_entry['unsealing'] = {
                            'level': unsealing_event.unsealing_level,
                            'previous_level': unsealing_event.previous_level,
                            'capacity': unsealing_event.high_semantic_capacity,
                            'reason': unsealing_event.reason,
                        }
                        if self._phase2_verbose:
                            print(f"    [Unsealing] L{layer_id} step={step}: "
                                  f"{unsealing_event.reason}, capacity={unsealing_event.high_semantic_capacity:.3f}")
                    else:
                        # 无等级变化，但仍记录当前等级
                        current_level = self.unsealing_mechanism.get_current_level(layer_id)
                        result_entry['unsealing'] = {
                            'level': current_level,
                            'changed': False,
                            'level_name': self.unsealing_mechanism.get_level_name(layer_id),
                        }

                # 7. ReturnFlowChannel — 每步执行锚定强度衰减与剥离检测
                if self.return_flow_channel is not None:
                    detach_events = self.return_flow_channel.step(timestamp=ts)
                    for evt in detach_events:
                        self._return_flow_events.append(evt)
                    if detach_events and self._phase2_verbose:
                        for evt in detach_events:
                            print(f"    [ReturnFlow] L{layer_id} step={step}: "
                                  f"detached {evt.payload.payload_id} — {evt.reason}")
                    # 记录当前锚定状态摘要
                    anchored = self.return_flow_channel.get_anchored_contents()
                    if anchored:
                        result_entry['return_flow'] = {
                            'anchored_count': len(anchored),
                            'anchored': anchored,
                            'detach_events_this_step': len(detach_events),
                        }

                # 8. OrganizationalDensityIndex — 基于六阈值结果计算 ODI
                odi_result = None
                if self.organizational_density_index is not None:
                    threshold_result_for_odi = locals().get('threshold_result')
                    odi_result = self.organizational_density_index.compute(
                        threshold_result=threshold_result_for_odi,
                        coupling_matrix=coupling_matrix,
                        stability_score=self_sustaining if self_sustaining > 0 else None,
                        timestamp=ts,
                    )
                    result_entry['odi'] = {
                        'value': odi_result.value,
                        'zone': odi_result.zone,
                        'base_zone': odi_result.base_zone,
                        'densification_rate': odi_result.densification_rate,
                    }
                    if odi_result.zone_boundary is not None:
                        result_entry['odi']['zone_boundary'] = {
                            'depth': odi_result.zone_boundary.depth,
                            'transition_proximity': odi_result.zone_boundary.transition_proximity,
                            'is_near_boundary': odi_result.zone_boundary.is_near_boundary,
                        }
                    if self._phase2_verbose:
                        zb_info = ""
                        if odi_result.zone_boundary is not None:
                            zb = odi_result.zone_boundary
                            if zb.is_near_boundary:
                                zb_info = f" [near boundary, tp={zb.transition_proximity:.2f}]"
                        print(f"    [ODI] L{layer_id} step={step}: "
                              f"value={odi_result.value:.3f}, zone={odi_result.zone}"
                              f"{zb_info}")

                # 9. SeventhThresholdDetector — 基于 ODI 时间序列检测相变
                seventh_result = None
                if self.seventh_threshold_detector is not None and odi_result is not None:
                    seventh_result = self.seventh_threshold_detector.feed(
                        odi_result=odi_result,
                    )
                    result_entry['seventh_threshold'] = {
                        'detected': seventh_result.detected,
                        'confidence': seventh_result.confidence,
                        'n_signals': seventh_result.n_active_signals,
                        'signals': seventh_result.active_signal_types,
                    }
                    if self._phase2_verbose and seventh_result.detected:
                        print(f"    [7thThreshold] L{layer_id} step={step}: "
                              f"*** PHASE TRANSITION DETECTED *** "
                              f"confidence={seventh_result.confidence:.2f}, "
                              f"signals={seventh_result.active_signal_types}")

                # 10. CooperativeEmergenceDetector — 检测六条件协同涌现
                ce_result = None
                if self.cooperative_emergence_detector is not None:
                    # 需要六阈值结果和耦合矩阵
                    if threshold_result_for_odi is not None:
                        ce_result = self.cooperative_emergence_detector.feed(
                            threshold_result=threshold_result_for_odi,
                            coupling_matrix=coupling_matrix,
                            odi_result=odi_result,
                            timestamp=ts,
                        )
                        result_entry['cooperative_emergence'] = {
                            'detected': ce_result.cooperative_emergence_detected,
                            'confidence': ce_result.confidence,
                            'emergence_type': ce_result.emergence_type,
                        }
                        if self._phase2_verbose and ce_result.cooperative_emergence_detected:
                            print(f"    [CoopEmergence] L{layer_id} step={step}: "
                                  f"*** COOPERATIVE EMERGENCE *** "
                                  f"type={ce_result.emergence_type}, "
                                  f"confidence={ce_result.confidence:.2f}")

            self._phase2_layer_results[layer_id].append(result_entry)

        return callback

    def _run_layer(self, layer_id: int, steps: int,
                   initial_state: Optional[torch.Tensor] = None,
                   verbose: bool = True) -> Dict:
        """在指定层运行空间演化"""
        layer = self.hierarchy.get_layer(layer_id)
        N = layer.n_bits

        if layer_id not in self.spatial_layers:
            self._init_spatial_layer(layer_id, N, L=1.0)

        if layer_id > 0:
            self._apply_cross_layer_gravity_modulation(layer_id)

        evolver = SpatialLongRangeEvolver(
            N=N,
            total_steps=steps,
            sample_interval=self.sample_interval,
            device=self.device,
            n_hierarchy_bits=layer.constraints.n_hierarchy,
            L=self.spatial_layers[layer_id].L
        )

        evolver.constraints = layer.constraints

        if evolver.N > layer.n_bits:
            pad_size = evolver.N - layer.n_bits
            padded_state = torch.cat([
                layer.state,
                torch.zeros(pad_size, device=self.device)
            ])
            layer.state = padded_state
            layer.n_bits = evolver.N

        step_callback = self._make_phase2_callback(layer_id, evolver.N)

        if initial_state is not None:
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

        layer.state = result['final_state']
        layer.constraints = evolver.constraints

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

        just_sealed = evolver.constraints.sealed and not layer.is_sealed

        if self.auto_encapsulate and just_sealed:
            enc_info = self.hierarchy.check_and_encapsulate()
            if enc_info is not None:
                self.encapsulation_events.append(enc_info)
                if verbose:
                    print(f"  [ENCAP] L{enc_info['from_layer']} -> "
                          f"L{enc_info['to_layer']}: "
                          f"{enc_info['n_bits_before']} -> {enc_info['n_bits_after']} bits")
                new_layer = self.hierarchy.get_layer(enc_info['to_layer'])
                self._init_spatial_layer(
                    enc_info['to_layer'], new_layer.n_bits, L=1.0)
                self.hierarchy.update_base_encapsulated_values()

        layer.is_sealed = evolver.constraints.sealed

        return result

    def run(self, verbose: bool = True) -> Dict:
        """运行完整的跨层级演化"""
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
            if i in self._phase2_layer_results:
                lr['phase2_step_results'] = self._phase2_layer_results[i]
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
                'xiang_detector_active': self.xiang_detector is not None,
                'bias_memory_entries': (self.persistent_bias_memory.n_entries
                                        if self.persistent_bias_memory else 0),
                'cumulative_selector_active': self.cumulative_selector is not None,
                'six_threshold_detector_active': self.six_threshold_detector is not None,
                'pre_subjectivity_convergence_active': self.pre_subjectivity_convergence is not None,
                'pre_subjectivity_converged': (self.pre_subjectivity_convergence.has_converged
                                                if self.pre_subjectivity_convergence else False),
                'convergence_step': (self.pre_subjectivity_convergence.convergence_step
                                      if self.pre_subjectivity_convergence else None),
                'unsealing_mechanism_active': self.unsealing_mechanism is not None,
                'unsealing_events': [str(e) for e in self._unsealing_events],
                'unsealing_summary': (
                    self.unsealing_mechanism.get_all_structures_status()
                    if self.unsealing_mechanism else {}),
                'return_flow_channel_active': self.return_flow_channel is not None,
                'return_flow_anchored_count': (
                    self.return_flow_channel.get_anchored_count()
                    if self.return_flow_channel else 0),
                'return_flow_success_rate': (
                    self.return_flow_channel.get_success_rate()
                    if self.return_flow_channel else 0.0),
                'organizational_density_index_active': self.organizational_density_index is not None,
                'seventh_threshold_detector_active': self.seventh_threshold_detector is not None,
                'seventh_threshold_detected': (
                    self.seventh_threshold_detector.detected
                    if self.seventh_threshold_detector else False),
                'seventh_threshold_confidence': (
                    self.seventh_threshold_detector.confidence
                    if self.seventh_threshold_detector else 0.0),
                'cooperative_emergence_detector_active': self.cooperative_emergence_detector is not None,
                'cooperative_emergence_detected': (
                    self.cooperative_emergence_detector.cooperative_emergence_detected
                    if self.cooperative_emergence_detector else False),
                'cooperative_emergence_confidence': (
                    self.cooperative_emergence_detector.confidence
                    if self.cooperative_emergence_detector else 0.0),
                'layers_with_results': list(self._phase2_layer_results.keys()),
            },
        }

    # ─── Phase 2 查询接口 ───

    def get_unsealing_events(self, structure_id: Optional[int] = None) -> List[UnsealingEvent]:
        """获取解封事件历史"""
        if structure_id is not None and self.unsealing_mechanism is not None:
            return self.unsealing_mechanism.get_event_history(structure_id)
        return list(self._unsealing_events)

    def get_return_flow_events(self, limit: int = 100) -> List[ReturnFlowEvent]:
        """获取回流事件历史"""
        if self.return_flow_channel is not None:
            return self.return_flow_channel.get_flow_history(limit)
        return list(self._return_flow_events)

    def get_unsealing_status(self) -> Dict:
        """获取解封状态摘要"""
        if self.unsealing_mechanism is not None:
            return self.unsealing_mechanism.get_all_structures_status()
        return {}

    def get_return_flow_status(self) -> Dict:
        """获取回流通道状态摘要"""
        if self.return_flow_channel is not None:
            return {
                'anchored_count': self.return_flow_channel.get_anchored_count(),
                'anchored_contents': self.return_flow_channel.get_anchored_contents(),
                'success_rate': self.return_flow_channel.get_success_rate(),
                'total_events': self.return_flow_channel.get_total_events(),
            }
        return {}

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
