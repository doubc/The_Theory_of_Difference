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
from engine.lateral_coupling import LateralCoupler, LateralCouplingReport
from engine.minimal_self_detector import MinimalSelfDetector, MinimalSelfResult
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine, AnticipationResult
from engine.counterfactual_engine import CounterfactualEngine, CounterfactualResult
from models.narrative_self import NarrativeRecursionOperator, DifferenceSignal
from engine.global_bias_constraint import GlobalBiasConstraint, GlobalBiasConstraintResult
from layers.three_dim_hamming import ThreeDimHammingLattice
from engine.functional_signal_coupling import extract_functional_signals
from engine.adaptive_momentum_controller import AdaptiveMomentumController, DEFAULT_ADAPTIVE_MOMENTUM_CONFIG
from engine.institutional_layer_protector import InstitutionalLayerProtector, DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG
from engine.cross_scale_coupling import CrossScaleCoupling, DEFAULT_CROSS_SCALE_COUPLING_CONFIG
from engine.narrative_self_emergence import NarrativeSelfEmergence, DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG


# ──────────────────────────────────────────────────────────
# 回流通道辅助函数（Phase 2 第二阶段：象界 → 前主体态）
# ──────────────────────────────────────────────────────────

def _generate_payload_from_unsealing(
    unsealing_event: UnsealingEvent,
    structure_state: torch.Tensor,
    layer_id: int,
    step: int,
) -> Optional[HighSemanticPayload]:
    """从解封事件生成高语义载荷。

    将解封时的结构状态压缩为内容向量，作为回流通道锚定的原始载荷。
    """
    if unsealing_event.high_semantic_capacity <= 0:
        return None

    # 从结构状态中提取与解封结构相关的特征子向量
    structure_id = unsealing_event.structure_id
    # 取结构状态中对应结构 ID 的切片（若超出维度则取整体）
    dim = structure_state.dim()
    if dim == 2:
        # (w, w) 平面状态：取对应行/列的均值作为特征
        if 0 <= structure_id < structure_state.size(0):
            content_vec = structure_state[structure_id].clone().float()
        else:
            content_vec = structure_state.mean(dim=0).clone().float()
    elif dim == 3:
        # (N, N, N) 立方体状态：取对应切片
        if 0 <= structure_id < structure_state.size(0):
            content_vec = structure_state[structure_id].clone().float()
        else:
            content_vec = structure_state.mean(dim=(1, 2)).clone().float()
    else:
        content_vec = structure_state.clone().float()

    # 归一化到 [-1, 1]
    max_val = content_vec.abs().max().item()
    if max_val > 0:
        content_vec = content_vec / max_val

    payload_id = f"unseal_L{layer_id}_s{step}_id{structure_id}"
    # 将解封原因映射为合法的内容类型
    _TYPE_MAP = {
        'coherence': 'meaning',
        'stability': 'institution',
        'emergence': 'narrative',
        'identity': 'identity',
        'convergence': 'meaning',
    }
    content_type = _TYPE_MAP.get(unsealing_event.reason, 'meaning')
    anchor_strength = min(unsealing_event.high_semantic_capacity, 1.0)

    return HighSemanticPayload(
        payload_id=payload_id,
        content_type=content_type,
        content_vector=content_vec,
        anchor_strength=anchor_strength,
        created_at=unsealing_event.timestamp,
    )


def _build_available_structures(
    hierarchy: HierarchyManager,
    current_layer: int,
    max_layers: int,
    unsealing_mechanism: Optional[UnsealingMechanism] = None,
    coupling_matrix: Optional[Dict[str, Dict[str, float]]] = None,
    layer_state: Optional[torch.Tensor] = None,
) -> Tuple[List[Dict], Optional[Dict[int, int]]]:
    """Build available structures for return flow anchoring.

    Uses layer_state to estimate coupling for all bits.
    """
    available = []
    unsealing_levels: Dict[int, int] = {}
    mechanism_names = [
        'boundary', 'self_sustaining', 'retention',
        'replication', 'selection', 'function',
    ]
    n_mechanisms = len(mechanism_names)

    # Determine number of bits from layer_state or default
    if layer_state is not None:
        n_bits = layer_state.size(0)
    else:
        n_bits = 72

    # Use all bits as anchor candidates
    for sid in range(n_bits):
        # Estimate coupling from layer_state
        if layer_state is not None and 0 <= sid < layer_state.size(0):
            if layer_state.dim() == 1:
                total_coupling = float(torch.abs(layer_state[sid].float()).item())
            elif layer_state.dim() == 2:
                total_coupling = float(torch.abs(layer_state[sid].float()).sum().item())
                max_norm = layer_state.size(1)
                if max_norm > 0:
                    total_coupling /= max_norm
            else:
                total_coupling = 0.0
        else:
            total_coupling = 0.0

        per_mechanism = total_coupling / n_mechanisms if n_mechanisms > 0 else 0.0
        mechanisms = {name: per_mechanism for name in mechanism_names}

        # Unsealing level
        level = 0
        if unsealing_mechanism is not None:
            stored = unsealing_mechanism.get_current_level(sid)
            if stored > 0:
                level = stored

        unsealing_levels[sid] = level

        available.append({
            'structure_id': sid,
            'unsealing_level': level,
            'mechanisms': mechanisms,
            'total_coupling': total_coupling,
        })

    return available, unsealing_levels if unsealing_levels else None

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
                 # Phase 2 P2 横向耦合（可选，同层结构间耦合）
                 lateral_coupler: Optional[LateralCoupler] = None,
                 # Phase 3 组件（可选，前主体态 → 现象意识的结构条件）
                 minimal_self_detector: Optional[MinimalSelfDetector] = None,
                 anticipatory_bias_engine: Optional[AnticipatoryBiasEngine] = None,
                 counterfactual_engine: Optional[CounterfactualEngine] = None,
                 narrative_recursion_operator: Optional[NarrativeRecursionOperator] = None,
                 global_bias_constraint: Optional[GlobalBiasConstraint] = None,
                 # GBC 软约束：对违反机制施加温和偏置旋转（0=关闭，0.1=轻度，0.3=中度）
                 gbc_soft_nudge: float = 0.0,
                 # P1 评估间隔（每多少个 P0 检测周期执行一次 P1 评估）
                 p1_eval_interval: int = 5,
                 phase2_verbose: bool = False,
                 phase3_verbose: bool = False,
                 # Phase 4 P0 组件（可选，H4 修复）
                 adaptive_momentum_controller: Optional[AdaptiveMomentumController] = None,
                 institutional_layer_protector: Optional[InstitutionalLayerProtector] = None,
                 cross_scale_coupling: Optional[CrossScaleCoupling] = None,
                 narrative_self_emergence: Optional[NarrativeSelfEmergence] = None,
                 # Phase 4 配置（可选，覆盖默认配置）
                 adaptive_momentum_config: Optional[Dict] = None,
                 institutional_protector_config: Optional[Dict] = None,
                 cross_scale_coupling_config: Optional[Dict] = None,
                 narrative_self_emergence_config: Optional[Dict] = None,
                 phase4_verbose: bool = False):
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
        self.lateral_coupler = lateral_coupler
        # Phase 3 组件
        self.minimal_self_detector = minimal_self_detector
        self.anticipatory_bias_engine = anticipatory_bias_engine
        self.counterfactual_engine = counterfactual_engine
        self.narrative_recursion_operator = narrative_recursion_operator
        self.global_bias_constraint = global_bias_constraint
        self._gbc_soft_nudge = gbc_soft_nudge
        self._p1_eval_interval = p1_eval_interval
        self._phase2_verbose = phase2_verbose
        self._phase3_verbose = phase3_verbose
        self._phase4_verbose = phase4_verbose
        # Phase 4 P0 组件
        self.adaptive_momentum_controller = adaptive_momentum_controller
        self.institutional_layer_protector = institutional_layer_protector
        # Phase 4 P1 组件
        self.cross_scale_coupling = cross_scale_coupling
        self.narrative_self_emergence = narrative_self_emergence
        self._adaptive_momentum_config = adaptive_momentum_config
        self._institutional_protector_config = institutional_protector_config
        self._cross_scale_coupling_config = cross_scale_coupling_config
        self._narrative_self_emergence_config = narrative_self_emergence_config
        self._phase2_layer_results: Dict[int, List[Dict]] = {}  # layer -> [step_results]
        # 解封事件记录
        self._unsealing_events: List[UnsealingEvent] = []
        # 回流事件记录
        self._return_flow_events: List[ReturnFlowEvent] = []
        # P1 fix (2026-05-30): ODI 滑动窗口（用于 p3_active 门控）
        self._odi_window: List[float] = []
        self._last_odi_value: float = 0.0
        # Phase 2 自维持环路 & 复制模式（可选，未实现时默认为 None）
        self.self_sustaining_circulation = None
        self.replicate_pattern = None
        # Phase 2 功能分化（可选，未实现时默认为 None）
        self.functional_differentiation = None

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
                 self.cooperative_emergence_detector is not None or
                 self.lateral_coupler is not None)
        has_p3 = (self.minimal_self_detector is not None or
                  self.anticipatory_bias_engine is not None or
                  self.counterfactual_engine is not None or
                  self.narrative_recursion_operator is not None)
        has_p4 = (self.adaptive_momentum_controller is not None or
                  self.institutional_layer_protector is not None)
        if not has_p2 and not has_p3 and not has_p4:
            return None

        if layer_id not in self._phase2_layer_results:
            self._phase2_layer_results[layer_id] = []

        p1_counter = {'value': 0}

        def callback(step: int, state: torch.Tensor,
                     snapshot: 'SpatialSnapshot',
                     constraints) -> None:
            """Phase 2 步骤回调"""
            result_entry = {'step': step, 'layer': layer_id}

            # Ensure odi_result is always defined (used by Phase 3 components)
            odi_result = None

            # ── 重建循环开始：追踪保持深度的可重调用性 ──
            if self.persistent_bias_memory is not None:
                self.persistent_bias_memory.begin_reconstruction_cycle()

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
                    target_layer=layer_id,
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

            # 4. NarrativeRecursionOperator (Phase 3)
            if self.narrative_recursion_operator is not None:
                # 构建差异信号列表
                ts = layer_id * 10000 + step
                diff_signals = []
                # 从状态重建差异矩阵
                state_float = state.float()
                D = (state_float.unsqueeze(0) - state_float.unsqueeze(1)).abs()
                D_max = D.max().item()
                if D_max > 1e-8:
                    D = D / D_max
                D.fill_diagonal_(0)

                # 采样差异信号（避免信号过多）
                N_bits = state.shape[0]
                sample_step = max(1, N_bits // 32)  # 最多 32 个信号
                signal_idx = 0
                for i in range(0, N_bits, sample_step):
                    for j in range(i + 1, N_bits, sample_step):
                        mag = D[i, j].item()
                        if mag > 0.05:  # 幅度阈值
                            # Fix: encode (i,j) pair as a unique direction vector
                            # so novelty computation works (scalar diff -> cos_sim
                            # always 1.0 -> novelty=0 -> filter rejects all)
                            direction = torch.zeros(1, N_bits, device=state.device)
                            direction[0, i] = state_float[i]
                            direction[0, j] = state_float[j]
                            diff_signals.append(DifferenceSignal(
                                signal_id=f"sig_L{layer_id}_{step}_{signal_idx:03d}",
                                source_layer=layer_id,
                                target_layer=layer_id,
                                magnitude=mag,
                                direction=direction,
                                timestamp=ts,
                            ))
                            signal_idx += 1
                            if signal_idx >= 32:  # 上限
                                break
                    if signal_idx >= 32:
                        break

                # 获取当前偏置
                current_bias = constraints.direction.clone() if hasattr(constraints, 'direction') else torch.zeros(N, device=self.device)

                # 获取当前 ODI（使用最近一次 P1 评估的值）
                current_odi = getattr(self, '_last_odi_value', 0.0)

                # 执行叙事递归步骤
                narrative_correction = self.narrative_recursion_operator.step(
                    signals=diff_signals,
                    current_bias=current_bias,
                    current_odi=current_odi,
                    timestamp=ts,
                )

                # 将叙事偏置修正反馈到偏置场
                if narrative_correction is not None and narrative_correction.norm().item() > 1e-8:
                    # 修正方向场
                    if hasattr(constraints, 'direction'):
                        # Fix: handle dimension mismatch between narrative_correction
                        # (bias_dimension) and constraints.direction (N)
                        dir_shape = constraints.direction.shape
                        corr = narrative_correction
                        if corr.shape != dir_shape:
                            # Project to matching dimension via interpolation
                            corr_flat = corr.flatten()
                            dir_len = dir_shape[0] if len(dir_shape) > 0 else 1
                            if len(corr_flat) != dir_len:
                                # Use linear interpolation to match dimensions
                                corr_1d = corr_flat.float()
                                target = torch.zeros(dir_len, device=corr_1d.device)
                                # Simple repeat or truncate
                                if len(corr_1d) >= dir_len:
                                    indices = torch.linspace(0, len(corr_1d) - 1, dir_len).long()
                                    target = corr_1d[indices]
                                else:
                                    repeat_times = (dir_len + len(corr_1d) - 1) // len(corr_1d)
                                    extended = corr_1d.repeat(repeat_times)
                                    target = extended[:dir_len]
                                corr = target
                            else:
                                corr = corr_flat
                        new_direction = constraints.direction + corr
                        norm_val = new_direction.norm().item()
                        if norm_val > 1e-8:
                            constraints.direction = new_direction / norm_val

                    # 获取叙事层级信息
                    # 从当前步骤的行动中提取最高叙事层级
                    latest_level_name = 'MINI_NARRATIVE'
                    is_civ = False
                    level_dist = {}
                    try:
                        narr_history = self.narrative_recursion_operator.get_narrative_history(n=1)
                        if narr_history:
                            latest_level_name = narr_history[-1].get('narrative_level', 'MINI_NARRATIVE')
                            is_civ = latest_level_name == 'CIVILIZATION'
                        narr_summary = self.narrative_recursion_operator.get_summary()
                        level_dist = narr_summary.get('narrative_level_distribution', {})
                    except Exception:
                        pass

                    # 记录到结果
                    result_entry['narrative_recursion'] = {
                        'signals_processed': len(diff_signals),
                        'bias_correction_applied': True,
                        'correction_norm': narrative_correction.norm().item(),
                        'narrative_level': latest_level_name,
                        'is_civilization': is_civ,
                        'level_distribution_snapshot': level_dist,
                    }

            # 5. AdaptiveMomentumController (Phase 4 P0)
            if self.adaptive_momentum_controller is not None:
                # 获取当前叙事层级计数
                inst_count = 0
                civ_count = 0
                category_heats = {}
                try:
                    if self.narrative_recursion_operator is not None:
                        narr_summary = self.narrative_recursion_operator.get_summary()
                        level_dist = narr_summary.get('narrative_level_distribution', {})
                        inst_count = level_dist.get('INSTITUTIONAL', 0)
                        civ_count = level_dist.get('CIVILIZATION', 0)
                        category_heats = level_dist
                except Exception:
                    pass

                amc_result = self.adaptive_momentum_controller.step(
                    category_heats=category_heats,
                    institutional_count=inst_count,
                    civilization_count=civ_count,
                )

                result_entry['adaptive_momentum'] = {
                    'momentum_bonus': round(amc_result.momentum_bonus, 4),
                    'entropy': round(amc_result.entropy, 4),
                    'institutional_count': amc_result.institutional_count,
                    'institutional_rate': round(amc_result.institutional_rate, 4),
                    'adjustment': round(amc_result.adjustment, 4),
                    'mode': amc_result.mode,
                    'should_diffuse': amc_result.should_diffuse,
                    'should_focus': amc_result.should_focus,
                }

                # Propagate AMC momentum bonus to narrative connector
                if self.narrative_recursion_operator is not None:
                    connector = self.narrative_recursion_operator.connector
                    if hasattr(connector, 'set_momentum_bonus'):
                        connector.set_momentum_bonus(amc_result.momentum_bonus)

                if self._phase4_verbose:
                    print(f"    [AMC] L{layer_id} step={step}: "
                          f"bonus={amc_result.momentum_bonus:.3f} "
                          f"mode={amc_result.mode} "
                          f"entropy={amc_result.entropy:.3f}")

            # 6. InstitutionalLayerProtector (Phase 4 P0)
            if self.institutional_layer_protector is not None:
                # 获取 INSTITUTIONAL 类别分布
                inst_categories = {}
                current_odi = getattr(self, '_last_odi_value', 0.0)
                inst_count_for_protector = 0
                try:
                    if self.narrative_recursion_operator is not None:
                        narr_summary = self.narrative_recursion_operator.get_summary()
                        level_dist = narr_summary.get('narrative_level_distribution', {})
                        inst_count_for_protector = level_dist.get('INSTITUTIONAL', 0)
                        # 使用 level_dist 作为类别分布的代理
                        inst_categories = {
                            k: v for k, v in level_dist.items()
                            if k != 'CIVILIZATION'
                        }
                    # Fallback: 如果 narrative level_dist 全为 0，尝试从 AMC 获取 institutional count
                    # AMC 通过熵检测识别 institutional 级代理，是更可靠的 institutional 信号源
                    if inst_count_for_protector <= 0 and self.adaptive_momentum_controller is not None:
                        amc_hist = self.adaptive_momentum_controller.get_history()
                        inst_count_for_protector = amc_hist.get('institutional_count', 0)
                        # AMC 的类别分布基于熵聚类
                        if inst_count_for_protector > 0:
                            inst_categories = {'amc_entropy_cluster': inst_count_for_protector}
                except Exception:
                    pass

                ilp_result = self.institutional_layer_protector.step(
                    institutional_count=inst_count_for_protector,
                    institutional_categories=inst_categories if inst_categories else None,
                    current_odi=current_odi,
                )

                result_entry['institutional_protector'] = {
                    'institutional_count': ilp_result.institutional_count,
                    'institutional_floor': round(ilp_result.institutional_floor, 2),
                    'consumption_rate_limit': round(ilp_result.consumption_rate_limit, 4),
                    'transition_allowed': ilp_result.transition_allowed,
                    'transition_openness': round(ilp_result.transition_openness, 4),
                    'n_categories': ilp_result.n_categories,
                    'diversity_sufficient': ilp_result.diversity_sufficient,
                    'protection_level': ilp_result.protection_level,
                    'should_consume': ilp_result.should_consume,
                }

                if self._phase4_verbose:
                    print(f"    [ILP] L{layer_id} step={step}: "
                          f"level={ilp_result.protection_level} "
                          f"floor={ilp_result.institutional_floor:.1f} "
                          f"openness={ilp_result.transition_openness:.3f}")

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

                # functional_signals: 为 GBC 的 function 机制提取功能信号
                # 注意：此处提取不依赖 coupling_mode，专为 GBC 提供 function 偏置
                functional_signals = None
                if self.global_bias_constraint is not None:
                    # 从已有组件提取功能信号（不依赖 pre_subjectivity_convergence 的 coupling_mode）
                    dir_vals = constraints.direction.float()
                    active_indices_list = list(constraints.active_bits)
                    if len(active_indices_list) > 0:
                        active_dir = dir_vals[active_indices_list]
                        direction_agreement = float(active_dir.abs().mean().item())
                    else:
                        direction_agreement = 0.0
                    functional_signals = {
                        'direction_agreement': direction_agreement,
                        'active_count': active_count if 'active_count' in dir() else 0,
                        'total_bits': total_bits if 'total_bits' in dir() else N,
                    }

                # ── GlobalBiasConstraint: 全局偏置一致性检测 ──
                # 在 P1 周期内执行，收集各机制局部偏置并评估全局一致性
                if self.global_bias_constraint is not None:
                    local_biases = {}
                    coupling_strengths = {}

                    # 1. boundary: 从 constraints.direction 提取
                    if hasattr(constraints, 'direction') and constraints.direction is not None:
                        boundary_vec = constraints.direction.float().clone()
                        if boundary_vec.norm() > 1e-8:
                            local_biases['boundary'] = boundary_vec
                            coupling_strengths['boundary'] = float(active_count / max(1, total_bits))

                    # 2. self_sustaining: 从 active bits 的方向一致性提取
                    if self_sustaining > 0 and hasattr(constraints, 'direction'):
                        dir_vals = constraints.direction.float()
                        active_indices_list = list(constraints.active_bits)
                        if len(active_indices_list) > 0:
                            active_dir = dir_vals[active_indices_list]
                            # 构建与 direction 同维度的偏置：active bits 设为平均方向，其余为 0
                            ss_vec = torch.zeros_like(dir_vals)
                            ss_vec[active_indices_list] = active_dir.mean().item()
                            if ss_vec.norm() > 1e-8:
                                local_biases['self_sustaining'] = ss_vec.clone()
                                coupling_strengths['self_sustaining'] = self_sustaining

                    # 3. memory: 从 PersistentBiasMemory 获取当前层的累积偏置场
                    if self.persistent_bias_memory is not None:
                        memory_field = self.persistent_bias_memory.get_accumulated(layer_id, n_bits=N)
                        if memory_field is not None:
                            memory_field = memory_field.float()
                            if memory_field.norm() > 1e-8:
                                local_biases['memory'] = memory_field.clone()
                                coupling_strengths['memory'] = min(1.0, self.persistent_bias_memory.n_entries / 50.0)

                    # 4. replication: 从当前状态模式提取
                    # 复制机制的偏置 = 当前活跃比特的模式（哪些比特是活跃的）
                    # 使用 state 向量本身作为复制偏好：正值=应激活，负值=应抑制
                    if state is not None:
                        rep_vec = state.float().clone()
                        if rep_vec.norm() > 1e-8:
                            # 中心化：减去均值使偏置向量以 0 为中心
                            rep_vec = rep_vec - rep_vec.mean()
                            if rep_vec.norm() > 1e-8:
                                local_biases['replication'] = rep_vec
                                coupling_strengths['replication'] = float(rep_vec.abs().mean().item())

                    # 5. selection: 从 CumulativeSelector 的保留率构建偏置
                    if self.cumulative_selector is not None and variant_probs is not None:
                        sel_vec = torch.zeros(N, device=self.device, dtype=torch.float)
                        for vid, prob in variant_probs.items():
                            if vid.startswith('L' + str(layer_id) + '_b'):
                                try:
                                    bit_id = int(vid.split('_b')[1])
                                    if 0 <= bit_id < N:
                                        sel_vec[bit_id] = float(prob)
                                except (IndexError, ValueError):
                                    pass
                        if sel_vec.norm() > 1e-8:
                            # 中心化：0.5 表示无偏好，>0.5 正偏好，<0.5 负偏好
                            sel_vec = sel_vec - 0.5
                            if sel_vec.norm() > 1e-8:
                                local_biases['selection'] = sel_vec.clone()
                                coupling_strengths['selection'] = float(sel_vec.abs().mean().item())

                    # 6. function: 从 functional_signals 提取
                    if functional_signals is not None:
                        fs = functional_signals
                        if fs.get('direction_agreement', 0) > 0:
                            func_vec = torch.zeros(N, device=self.device, dtype=torch.float)
                            active_indices_sorted = sorted(constraints.active_bits)
                            if len(active_indices_sorted) > 0:
                                dir_vals = constraints.direction.float()
                                func_vec[active_indices_sorted] = dir_vals[active_indices_sorted] * fs['direction_agreement']
                            if func_vec.norm() > 1e-8:
                                local_biases['function'] = func_vec.clone()
                                coupling_strengths['function'] = float(fs['direction_agreement'])

                    # 评估全局偏置约束
                    if local_biases:
                        gbc_result = self.global_bias_constraint.evaluate(
                            local_biases=local_biases,
                            coupling_strengths=coupling_strengths or None,
                        )
                        result_entry['global_bias_constraint'] = {
                            'passed': gbc_result.passed,
                            'coherence': round(gbc_result.coherence, 4),
                            'balance': round(gbc_result.balance, 4),
                            'violating_mechanisms': gbc_result.violating_mechanisms,
                            'n_mechanisms': len(local_biases),
                        }
                        if self._phase2_verbose:
                            status = "PASS" if gbc_result.passed else "FAIL"
                            print(f"    [GBC] L{layer_id} step={step}: {status} "
                                  f"coh={gbc_result.coherence:.3f} bal={gbc_result.balance:.3f} "
                                  f"n={len(local_biases)}")
                        if not gbc_result.passed and gbc_result.violating_mechanisms:
                            if self._phase2_verbose:
                                print(f"    [GBC] 违反机制: {', '.join(gbc_result.violating_mechanisms)}")
                            # GBC 软约束：对负相干机制施加温和旋转
                            if self._gbc_soft_nudge > 0 and gbc_result.global_bias is not None:
                                gb = gbc_result.global_bias
                                gb_norm = gb / (gb.norm() + 1e-10)
                                for vname in gbc_result.violating_mechanisms:
                                    vcoh = gbc_result.coherence_by_mechanism.get(vname, 0.0)
                                    if vcoh < 0 and vname in local_biases:
                                        vb = local_biases[vname]
                                        vb_norm = vb / (vb.norm() + 1e-10)
                                        # 向全局方向旋转：v' = v + nudge * gb
                                        nudged = vb + self._gbc_soft_nudge * gb_norm * vb.norm()
                                        local_biases[vname] = nudged
                                        if self._phase2_verbose:
                                            new_coh = float(torch.dot(nudged, gb).item() / (nudged.norm() * gb.norm() + 1e-10))
                                            print(f"    [GBC-Nudge] {vname}: coh {vcoh:.3f} -> {new_coh:.3f}")

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
                # 使用实际扰动-重建测试结果作为3.2阈值输入（而非方向一致性代理）
                _actual_rebuild_count = int(self_sustaining * 10)
                _actual_perturbation_n = 10
                if active_count > 0 and total_bits > 0:
                    _perturb_success = 0
                    _perturb_n = min(10, max(5, active_count // 4))
                    for _p in range(_perturb_n):
                        _noise = torch.randn_like(state.float()) * 0.1
                        _perturbed = state.float() + _noise
                        _w = _perturbed.sum().item()
                        if _w_lo <= _w <= _w_hi:
                            _perturb_success += 1
                    _actual_rebuild_count = _perturb_success
                    _actual_perturbation_n = _perturb_n
                if self.six_threshold_detector is not None:
                    threshold_result = self.six_threshold_detector.detect(
                        active_exchanges=active_count,
                        total_boundary_edges=total_bits,
                        rebuild_success_count=_actual_rebuild_count,
                        perturbation_count=_actual_perturbation_n,
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
                        'statuses': [
                            {
                                'id': s.threshold_id,
                                'name': s.name,
                                'value': round(s.value, 6),
                                'threshold': s.threshold,
                                'is_met': s.is_met,
                                'gap': round(s.threshold - s.value, 6),
                                'ratio': round(s.value / max(s.threshold, 1e-10), 4),
                            }
                            for s in threshold_result.threshold_statuses
                        ],
                    }
                    if self._phase2_verbose:
                        status = "PASS" if threshold_result.all_met else f"{threshold_result.n_met}/6"
                        bn = f" bottleneck={threshold_result.bottleneck}" if not threshold_result.all_met else ""
                        print(f"    [6Threshold] L{layer_id} step={step}: {status}{bn}")

                # 4.5 Functional signals extraction (for functional coupling mode)
                functional_signals = None
                if (self.pre_subjectivity_convergence is not None and
                        self.pre_subjectivity_convergence.coupling_mode == "functional"):
                    # Extract functional signals from Phase 2 components
                    variant_retention_rates = []
                    if variant_probs is not None:
                        variant_retention_rates = [float(v) for v in variant_probs.values()]

                    selection_trend_scores = []
                    if self.cumulative_selector is not None:
                        for vid, rec in self.cumulative_selector._variants.items():
                            if rec.n_observations > 0:
                                selection_trend_scores.append(rec.retention_rate())

                    agg_retention_depth = 0.0
                    if self.persistent_bias_memory is not None:
                        agg_retention_depth = self.persistent_bias_memory.get_aggregate_retention_depth()

                    functional_signals = {
                        'active_count': active_count,
                        'total_bits': total_bits,
                        'direction_agreement': self_sustaining,
                        'aggregate_retention_depth': agg_retention_depth,
                        'variant_retention_rates': variant_retention_rates if variant_retention_rates else None,
                        'selection_trend_scores': selection_trend_scores if selection_trend_scores else None,
                        'component_contributions': component_contributions,
                    }
                    # Store computed signal values in result_entry for diagnostics
                    _sig = extract_functional_signals(
                        active_count=functional_signals['active_count'],
                        total_bits=functional_signals['total_bits'],
                        direction_agreement=functional_signals['direction_agreement'],
                        aggregate_retention_depth=functional_signals['aggregate_retention_depth'],
                        variant_retention_rates=functional_signals['variant_retention_rates'],
                        selection_trend_scores=functional_signals['selection_trend_scores'],
                        component_contributions=functional_signals['component_contributions'],
                    )
                    result_entry['functional_signals'] = _sig.to_dict()

                # 5. PreSubjectivityConvergence
                conv_result = None
                if self.pre_subjectivity_convergence is not None:
                    threshold_params = {
                        'active_exchanges': active_count,
                        'total_boundary_edges': total_bits,
                        'rebuild_success_count': int(self_sustaining * 10),
                        'perturbation_count': 10,
                        'bias_recursion_depth': bias_depth,
                        'replicated_pattern': state if active_count > 0 else None,
                        'original_pattern': state,
                        'variant_continuation_probs': variant_probs,
                        'component_contributions': component_contributions,
                    }

                    conv_result = self.pre_subjectivity_convergence.evaluate(
                        threshold_params=threshold_params,
                        coupling_matrix=coupling_matrix,
                        structure_state=state.float(),
                        structure_fn=_structure_fn,
                        timestamp=ts,
                        n_active=active_count,
                        functional_signals=functional_signals,
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
                    # 7a. 先处理衰减与剥离
                    detach_events = self.return_flow_channel.step(timestamp=ts)
                    for evt in detach_events:
                        self._return_flow_events.append(evt)
                    if detach_events and self._phase2_verbose:
                        for evt in detach_events:
                            print(f"    [ReturnFlow] L{layer_id} step={step}: "
                                  f"detached {evt.payload.payload_id} — {evt.reason}")

                    # 7b. 如果本步有解封事件且容量>0，生成高语义载荷并尝试锚定
                    if unsealing_event is not None and unsealing_event.high_semantic_capacity > 0:
                        payload = _generate_payload_from_unsealing(
                            unsealing_event=unsealing_event,
                            structure_state=state.float(),
                            layer_id=layer_id,
                            step=step,
                        )
                        if payload is not None:
                            # 构建可用结构列表：优先包含解封结构本身（作为主要锚点）
                            available_structures, unsealing_levels = _build_available_structures(
                                hierarchy=self.hierarchy,
                                current_layer=layer_id,
                                max_layers=self.max_layers,
                                unsealing_mechanism=self.unsealing_mechanism,
                                coupling_matrix=coupling_matrix,
                                layer_state=state,
                            )
                            # 将解封结构插入到列表头部，并赋予高耦合强度
                            unseal_sid = unsealing_event.structure_id
                            # 检查是否已存在
                            existing = [s for s in available_structures if s['structure_id'] == unseal_sid]
                            if existing:
                                # 更新其耦合强度为高值（基于解封容量）
                                existing[0]['total_coupling'] = min(unsealing_event.high_semantic_capacity * 2, 1.0)
                                existing[0]['mechanisms'] = {
                                    k: min(unsealing_event.high_semantic_capacity * 2, 1.0) / 6
                                    for k in existing[0]['mechanisms']
                                }
                                # 移到列表头部
                                available_structures.remove(existing[0])
                                available_structures.insert(0, existing[0])
                            else:
                                # 添加解封结构
                                cap = min(unsealing_event.high_semantic_capacity * 2, 1.0)
                                available_structures.insert(0, {
                                    'structure_id': unseal_sid,
                                    'unsealing_level': unsealing_event.unsealing_level,
                                    'mechanisms': {k: cap / 6 for k in ['boundary', 'self_sustaining', 'retention', 'replication', 'selection', 'function']},
                                    'total_coupling': cap,
                                })
                            anchor_event = self.return_flow_channel.attempt_anchor(
                                payload=payload,
                                available_structures=available_structures,
                                timestamp=ts,
                                unsealing_levels=unsealing_levels,
                            )
                            self._return_flow_events.append(anchor_event)
                            if self._phase2_verbose:
                                status = "ANCHORED" if anchor_event.success else "FAILED"
                                print(f"    [ReturnFlow] L{layer_id} step={step}: "
                                      f"payload={payload.payload_id} type={payload.content_type} "
                                      f"capacity={unsealing_event.high_semantic_capacity:.3f} "
                                      f"→ {status}: {anchor_event.reason}")

                    # 记录当前锚定状态摘要
                    anchored = self.return_flow_channel.get_anchored_contents()
                    if anchored:
                        result_entry['return_flow'] = {
                            'anchored_count': len(anchored),
                            'anchored': anchored,
                            'detach_events_this_step': len(detach_events),
                        }

                # 8. OrganizationalDensityIndex — 基于六阈值结果计算 ODI
                if self.organizational_density_index is not None:
                    threshold_result_for_odi = locals().get('threshold_result')
                    odi_result = self.organizational_density_index.compute(
                        threshold_result=threshold_result_for_odi,
                        coupling_matrix=coupling_matrix,
                        stability_score=self_sustaining if self_sustaining > 0 else None,
                        timestamp=ts,
                    )
                    result_entry['odi'] = {
                        'value': odi_result.odi,
                        'zone': odi_result.zone,
                        'base_zone': odi_result.base_zone,
                        'densification_rate': odi_result.densification_rate,
                        'threshold_proximity': odi_result.subindices.threshold_proximity,
                        'coupling_density': odi_result.subindices.coupling_density,
                        'stability_margin': odi_result.subindices.stability_margin,
                        'firewall_purity': odi_result.subindices.firewall_purity,
                        'temporal_consistency': odi_result.subindices.temporal_consistency,
                        'cross_mechanism_resonance': odi_result.subindices.cross_mechanism_resonance,
                        'subindices': {
                            'threshold_proximity': odi_result.subindices.threshold_proximity,
                            'coupling_density': odi_result.subindices.coupling_density,
                            'stability_margin': odi_result.subindices.stability_margin,
                            'firewall_purity': odi_result.subindices.firewall_purity,
                            'temporal_consistency': odi_result.subindices.temporal_consistency,
                            'cross_mechanism_resonance': odi_result.subindices.cross_mechanism_resonance,
                        },
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
                              f"value={odi_result.odi:.3f}, zone={odi_result.zone}"
                              f"{zb_info}")

                # P1 fix (2026-05-30): 更新 ODI 滑动窗口（无论 verbose 是否开启）
                if odi_result is not None:
                    self._odi_window.append(odi_result.odi)
                    if len(self._odi_window) > 100:
                        self._odi_window.pop(0)
                    self._last_odi_value = odi_result.odi

                # 9. SeventhThresholdDetector — 基于 ODI 时间序列检测相变
                seventh_result = None
                if self.seventh_threshold_detector is not None and odi_result is not None:
                    seventh_result = self.seventh_threshold_detector.feed(
                        odi_result=odi_result,
                    )
                    result_entry['seventh_threshold'] = {
                        'detected': seventh_result.transition_detected,
                        'confidence': seventh_result.transition_confidence,
                        'n_signals': seventh_result.n_observations,
                        'transition_type': seventh_result.transition_type,
                    }
                    if self._phase2_verbose and seventh_result.transition_detected:
                        print(f"    [7thThreshold] L{layer_id} step={step}: "
                              f"*** PHASE TRANSITION DETECTED *** "
                              f"confidence={seventh_result.transition_confidence:.2f}, "
                              f"type={seventh_result.transition_type}")

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

                # 11. LateralCoupler — 同层结构间横向耦合
                lateral_report = None
                if self.lateral_coupler is not None:
                    # 注册当前层结构（以 layer_id 为结构 ID）
                    active_count = len(constraints.active_bits)
                    frozen_count = len(constraints.sealed_bits)
                    total_bits = max(1, active_count + frozen_count)
                    # 使用 ODI 作为密度值（如果已计算），否则用活跃比例
                    current_odi = odi_result.odi if odi_result is not None else (active_count / total_bits)
                    # 从空间坐标获取位置（取质心）
                    coords_3d = snapshot.coords_3d if hasattr(snapshot, 'coords_3d') and snapshot.coords_3d is not None else np.zeros(3)
                    centroid = coords_3d.mean(axis=0) if coords_3d.ndim == 2 else coords_3d
                    self.lateral_coupler.register_structure(
                        structure_id=layer_id,
                        position=centroid,
                        odi=current_odi,
                        boundary_radius=float(active_count) / max(1, total_bits) * 2.0,
                        coupling_field_strength=current_odi,
                    )
                    lateral_report = self.lateral_coupler.compute_step(timestamp=ts)
                    result_entry['lateral_coupling'] = {
                        'n_structures': lateral_report.n_structures,
                        'n_active_pairs': lateral_report.n_active_pairs,
                        'mean_coupling_strength': lateral_report.mean_coupling_strength,
                        'net_effects': lateral_report.net_effects,
                        'selection_pressure_deltas': lateral_report.selection_pressure_deltas,
                    }
                    if self._phase2_verbose and lateral_report.n_active_pairs > 0:
                        print(f"    [LateralCouple] L{layer_id} step={step}: "
                              f"structures={lateral_report.n_structures}, "
                              f"pairs={lateral_report.n_active_pairs}, "
                              f"mean_strength={lateral_report.mean_coupling_strength:.3f}")

            # ── Phase 3: 前主体态 → 现象意识的结构条件 ──
            # Phase 3 组件在 Phase 2 P1 评估的同一个 P1 周期内执行
            # 但仅在 ODI > 0.5（前主体态地板）之后才激活
            if has_p3:
                # 获取当前 ODI 值（用于门控）
                # odi_result 是 P1 块内的局部变量，可能未定义（如果 ODI 组件未注册）
                # 从 result_entry 中安全提取
                _odi_val = 0.0
                if 'odi' in result_entry and result_entry['odi'] is not None:
                    _odi_val = result_entry['odi'].get('value', 0.0)
                current_odi = _odi_val
                p3_active = current_odi >= 0.5  # 前主体态地板
                # P1 fix (2026-05-30): 滑动窗口门控补充
                # 单步门控易受 ODI 波动影响，用最近 10 步滑动窗口作为补充判断
                p3_active_window = False
                if hasattr(self, '_odi_window') and len(self._odi_window) >= 5:
                    window_mean = np.mean(list(self._odi_window)[-10:])
                    p3_active_window = window_mean >= 0.35  # 窗口均值阈值略低于单步阈值
                    # 单步或窗口任一满足即激活（宽松模式，确保 Phase 3 能收集数据）
                    p3_active = p3_active or p3_active_window

                # 12. MinimalSelfDetector — 最小自我检测
                msi_result = None
                if self.minimal_self_detector is not None and p3_active:
                    # P2 fix (2026-05-30): 改进敏感度图构建 — 解决密封后 Gini=0 问题
                    # 根因：旧代码只使用 18 个活跃比特（密封后），且 bind_sens*100 使分布同质化
                    # 修复：(a) 使用全部 72 比特 (b) 移除 *100 同质化 (c) Z-score 归一化
                    #       (d) 冻结比特使用绑定模式偏差作为结构性不对称信号
                    sensitivity_map = {}
                    if hasattr(constraints, 'direction') and constraints.direction is not None:
                        dir_vals = constraints.direction.float()
                        state_float = state.float()
                        n_bits = constraints.N
                        active_set = set(constraints.active_bits) if hasattr(constraints, 'active_bits') else set()

                        # 使用全部比特（含冻结比特），计算高维敏感度分布
                        for bit_id in range(n_bits):
                            part_name = f"bit_{bit_id}"
                            dir_sens = float(dir_vals[bit_id].abs().item()) if bit_id < len(dir_vals) else 0.0
                            state_sens = float(state_float[bit_id].item()) if bit_id < len(state_float) else 0.0

                            # 绑定敏感度：该比特与所有其他比特的平均绑定强度
                            if hasattr(constraints, 'binding_strength') and bit_id < constraints.binding_strength.size(0):
                                all_others = [j for j in range(min(n_bits, constraints.binding_strength.size(0))) if j != bit_id]
                                if all_others:
                                    bs_vals = [float(constraints.binding_strength[bit_id, j].abs().item()) for j in all_others]
                                    bind_sens = float(np.mean(bs_vals)) if bs_vals else 0.0
                                else:
                                    bind_sens = 0.0
                            else:
                                bind_sens = 0.0

                            # 分情况计算敏感度（移除 * 100.0 同质化因子）
                            if bit_id in active_set:
                                # 活跃比特：状态值 + 方向 + 绑定
                                sensitivity = 0.25 * dir_sens + 0.45 * state_sens + 0.30 * bind_sens
                            else:
                                # 冻结比特：绑定模式偏离度作为结构性不对称信号
                                # 计算该比特的绑定向量与其他比特的平均余弦距离
                                if hasattr(constraints, 'binding_strength') and bit_id < constraints.binding_strength.size(0):
                                    bs = constraints.binding_strength[bit_id, :n_bits]
                                    # 使用 binding_strength 方差作为区分度
                                    bind_var = float(bs.var().item()) if bs.numel() > 0 else 0.0
                                    sensitivity = 0.4 * bind_var + 0.4 * dir_sens + 0.2 * state_sens
                                else:
                                    sensitivity = 0.5 * dir_sens + 0.5 * state_sens

                            sensitivity_map[part_name] = sensitivity

                        # Z-score 归一化：放大比特间差异，为 Gini 系数提供有意义分布
                        vals = np.array(list(sensitivity_map.values()))
                        mean_val = np.mean(vals)
                        std_val = np.std(vals) if np.std(vals) > 1e-10 else 1.0
                        for key in sensitivity_map:
                            z = (sensitivity_map[key] - mean_val) / (std_val + 1e-10)
                            # tanh 映射到 [0, 1]，保持相对差异
                            sensitivity_map[key] = float(np.clip((np.tanh(z) + 1.0) / 2.0, 0.01, 0.99))

                        # 诊断日志：敏感度图质量
                        if self._phase3_verbose:
                            sv = np.array(list(sensitivity_map.values()))
                            sorted_sv = np.sort(sv)
                            gini_diag = 1.0 - (2.0 / len(sv)) * np.sum(
                                [(len(sv) - i) * v for i, v in enumerate(sorted_sv)]) / (np.sum(sorted_sv) + 1e-10)
                            print(f"    [MSI-Diag] L{layer_id} step={step}: "
                                  f"sensitivity n={len(sensitivity_map)} mean={np.mean(sv):.4f} "
                                  f"std={np.std(sv):.4f} gini={gini_diag:.4f} "
                                  f"active={len(active_set)} sealed={constraints.sealed}")
                    else:
                        # 回退：使用状态值作为敏感度代理（罕见）
                        state_float = state.float()
                        for i in range(len(state_float)):
                            sensitivity_map[f"bit_{i}"] = float(state_float[i].item())

                    # 基线偏移：从回流通道获取（如有）
                    # P0 fix (2026-05-30): 锚定 baseline_shift 到回流通道状态
                    # 不仅考虑当前锚定数量，还考虑锚定强度总和与历史锚定事件
                    baseline_shift = 0.0
                    if self.return_flow_channel is not None:
                        anchored = self.return_flow_channel.get_anchored_contents()
                        if anchored:
                            # 锚定强度加权平均（比单纯计数更精确）
                            strengths = [v['anchor_strength'] for v in anchored.values()]
                            baseline_shift = float(np.mean(strengths))
                            # 叠加锚定数量因子
                            baseline_shift *= (1.0 + 0.1 * len(anchored))
                        # 补充：从回流事件历史中获取累积锚定信号
                        flow_history = self.return_flow_channel.get_flow_history(limit=20)
                        successful_anchors = sum(1 for e in flow_history if e.success)
                        if successful_anchors > 0:
                            # 历史锚定成功率作为基线偏移的修正因子
                            success_rate = successful_anchors / len(flow_history)
                            baseline_shift += 0.02 * success_rate
                        baseline_shift = min(baseline_shift, 1.0)  # 上限约束

                    # 获取 ODI 结果用于 MSD 内部门控
                    _odi_for_msd = None
                    if self.organizational_density_index is not None and self.organizational_density_index._result_history:
                        _odi_for_msd = self.organizational_density_index._result_history[-1]
                    # 获取响应历史：使用状态空间分布作为差异化信号
                    # 状态值在不同比特间差异显著，比偏置向量更适合区分历史上下文
                    response_history = {}
                    state_float = state.float()
                    # 将状态按空间位置分组，每组取均值作为特征
                    state_N = state_float.size(0)
                    n_groups = 8  # 分成8个空间区域
                    group_size = max(1, state_N // n_groups)
                    for g in range(n_groups):
                        start = g * group_size
                        end = min((g + 1) * group_size, state_N)
                        ctx = f"state_region_{g}"
                        if ctx not in response_history:
                            response_history[ctx] = []
                        # 该区域的状态均值 + 方差 + 活跃比特数
                        region = state_float[start:end]
                        response_history[ctx].extend([
                            float(region.mean().item()),
                            float(region.std().item()),
                            float((region > 0.5).sum().item()),
                            float((region > 0.2).sum().item()),
                        ])
                    # 补充：偏置记忆条目（作为额外上下文）
                    if self.persistent_bias_memory is not None and self.persistent_bias_memory.n_entries > 0:
                        recent_entries = self.persistent_bias_memory._get_active_entries(target_layer=layer_id + 1)
                        if not recent_entries:
                            all_entries = [i for entries in self.persistent_bias_memory._layer_index.values() for i in entries]
                            recent_entries = [self.persistent_bias_memory._entries[i] for i in all_entries[-20:] if self.persistent_bias_memory._entries[i].is_active]
                        for entry in recent_entries[-4:]:
                            ctx = f"bias_t{entry.timestamp}"
                            if ctx not in response_history:
                                response_history[ctx] = []
                            if entry.bias_vector is not None:
                                bv = entry.bias_vector.float()
                                response_history[ctx].extend([
                                    float(bv.norm().item()), float(entry.current_strength),
                                ])
                    # 叙事修正信号
                    if result_entry.get('narrative_recursion', {}).get('bias_correction_applied'):
                        narr_corr = result_entry['narrative_recursion'].get('correction_norm', 0.0)
                        narr_key = f"narr_t{ts}"
                        if hasattr(constraints, 'direction') and constraints.direction is not None:
                            cd = constraints.direction.float()
                            response_history[narr_key] = [
                                narr_corr, float(cd.norm().item()),
                                float((cd > 0).sum().item()), float((cd < 0).sum().item()),
                            ]
                    msi_result = self.minimal_self_detector.feed(
                        sensitivity_map=sensitivity_map if sensitivity_map else None,
                        response_history=response_history if response_history else None,
                        baseline_shift=baseline_shift if baseline_shift != 0.0 else None,
                        odi_result=_odi_for_msd,
                        timestamp=ts,
                    )
                    result_entry['minimal_self'] = {
                        'detected': msi_result.minimal_self_detected,
                        'msi': msi_result.msi,
                        'msi_label': msi_result.msi_label,
                        'n_active_conditions': msi_result.n_active_conditions,
                        'asymmetry_index': msi_result.asymmetry_index,
                        'history_dependency_index': msi_result.history_dependency_index,
                        'self_reference_index': msi_result.self_reference_index,
                        'odi_at_detection': msi_result.odi_at_detection,
                    }
                    if self._phase3_verbose and msi_result.minimal_self_detected:
                        print(f"    [MSI] L{layer_id} step={step}: "
                              f"*** MINIMAL SELF DETECTED *** "
                              f"MSI={msi_result.msi:.3f}, "
                              f"conditions={msi_result.n_active_conditions}/3")

                # 13. AnticipatoryBiasEngine — 预期偏置
                anticipation_result = None
                if self.anticipatory_bias_engine is not None and p3_active:
                    target_layer = layer_id + 1
                    horizon = self.anticipatory_bias_engine.config.get('default_horizon', 1)
                    anticipation_result = self.anticipatory_bias_engine.predict(
                        target_layer=target_layer,
                        horizon=horizon,
                        timestamp=ts,
                        odi_result=None,  # ODI 门控已通过 p3_active 处理
                    )
                    result_entry['anticipation'] = {
                        'confidence': anticipation_result.confidence,
                        'is_reliable': anticipation_result.is_reliable,
                        'error_trend': anticipation_result.error_trend,
                        'n_predictions': anticipation_result.n_predictions,
                        'odi_gated': anticipation_result.odi_gated,
                    }
                    if self._phase3_verbose and anticipation_result.is_reliable:
                        print(f"    [Anticipation] L{layer_id} step={step}: "
                              f"conf={anticipation_result.confidence:.3f}, "
                              f"trend={anticipation_result.error_trend:+.4f}, "
                              f"reliable={anticipation_result.is_reliable}")

                    # 用当前状态更新预测误差
                    self.anticipatory_bias_engine.update(
                        actual=state.float(),
                        timestamp=ts,
                        horizon=horizon,
                    )

                # 14. CounterfactualEngine — 反事实探索
                cf_result = None
                if self.counterfactual_engine is not None and p3_active:
                    # 探索分岔
                    cf_result = self.counterfactual_engine.explore(
                        current_state=state.float(),
                        odi_result=odi_result,  # 传递实际 ODI 结果以支持内部门控
                        timestamp=ts,
                    )
                    result_entry['counterfactual'] = {
                        'active': cf_result.counterfactual_active,
                        'n_active_branches': cf_result.n_active_branches,
                        'n_divergence_points': cf_result.n_divergence_points,
                        'odi_gated': cf_result.odi_gated,
                    }
                    if self._phase3_verbose and cf_result.counterfactual_active:
                        print(f"    [Counterfactual] L{layer_id} step={step}: "
                              f"branches={cf_result.n_active_branches}, "
                              f"divergences={cf_result.n_divergence_points}")

            # ── 重建循环结束：评估保持深度的可重调用性 ──
            if self.persistent_bias_memory is not None:
                reinvocation_results = self.persistent_bias_memory.end_reconstruction_cycle(
                    timestamp=layer_id * 10000 + step)
                result_entry['reinvocation_results'] = reinvocation_results
                result_entry['n_cycles_tracked'] = (
                    self.persistent_bias_memory.n_cycles_tracked)

            # ── Phase 4 P1: Cross-Scale Coupling ──
            if self.cross_scale_coupling is not None:
                level_states = {}
                # self_sustaining may not be defined if P1 block hasn't run yet;
                # recompute inline from available context (same logic as line 885-894)
                _ss = 0.0
                _ac = len(constraints.active_bits)
                if _ac > 0 and hasattr(constraints, 'direction'):
                    _dv = constraints.direction.float()
                    _ai = list(constraints.active_bits)
                    if len(_ai) > 0:
                        _ad = _dv[_ai]
                        _md = _ad.mean().item()
                        if abs(_md) > 1e-8:
                            _ag = (_ad.sign() * np.sign(_md)).mean().item()
                            _ss = max(0.0, (_ag + 1) / 2)
                mini_stability = float(_ss) if _ss > 0 else 0.0
                mini_odi = result_entry.get('odi', {}).get('value', 0.0)
                level_states['MINI'] = {
                    'stability_score': mini_stability,
                    'odi': mini_odi,
                    'structure_vector': constraints.direction.float().clone() if
                        hasattr(constraints, 'direction') and constraints.direction is not None else None,
                }
                for hl in ['INSTITUTIONAL', 'CIVILIZATION']:
                    hl_state = self.hierarchy.get_layer_state_by_name(hl)
                    if hl_state is not None:
                        level_states[hl] = {
                            'stability_score': hl_state.get('stability_score', 0.0),
                            'odi': hl_state.get('odi', 0.0),
                            'structure_vector': hl_state.get('structure_vector', None),
                        }
                narrative_labels = {}
                if self.narrative_recursion_operator is not None:
                    narr_history = self.narrative_recursion_operator.get_narrative_history(n=1)
                    if narr_history:
                        narrative_labels['MINI'] = narr_history[-1].get('narrative_label', 'silent')
                        narrative_labels['INSTITUTIONAL'] = narr_history[-1].get('institutional_label', 'silent')
                        narrative_labels['CIVILIZATION'] = narr_history[-1].get('civilization_label', 'silent')
                    else:
                        narrative_labels = {'MINI': 'silent', 'INSTITUTIONAL': 'silent', 'CIVILIZATION': 'silent'}
                else:
                    narrative_labels = {'MINI': 'silent', 'INSTITUTIONAL': 'silent', 'CIVILIZATION': 'silent'}
                emergence_events = []
                if self.cooperative_emergence_detector is not None:
                    co_result = locals().get('cooperative_emergence_result')
                    if co_result is not None and co_result.emergence_active:
                        emergence_events.append({
                            'emergence_id': f"co_emerg_{layer_id}_{step}",
                            'source_level': 'MINI',
                            'target_level': co_result.emergence_level,
                            'stability_score': co_result.stability_score,
                            'odi': mini_odi,
                            'structure_vector': constraints.direction.float().clone() if
                                hasattr(constraints, 'direction') and constraints.direction is not None else None,
                        })
                csc_result = self.cross_scale_coupling.step(
                    level_states=level_states,
                    narrative_labels=narrative_labels,
                    emergence_events=emergence_events if emergence_events else None,
                    bias_field=constraints.direction.float() if
                        hasattr(constraints, 'direction') and constraints.direction is not None else None,
                )
                result_entry['cross_scale_coupling'] = {
                    'csci': round(csc_result['csci'].csci, 4),
                    'csci_coherent': csc_result['csci'].is_coherent,
                    'pairwise_coherence': csc_result['csci'].pairwise_coherence,
                    'narrative_coherence': round(csc_result['csci'].narrative_coherence, 4),
                    'structural_coherence': round(csc_result['csci'].structural_coherence, 4),
                    'level_stabilities': {k: round(v, 4) for k, v in csc_result['csci'].level_stabilities.items()},
                    'top_down_constraints': [
                        {'id': c['id'], 'source': c['source'], 'target': c['target'],
                         'strength': c['strength'], 'is_active': c['is_active']}
                        for c in csc_result.get('top_down_constraints', [])
                        if isinstance(c, dict)
                    ],
                    'emergence_count': len(csc_result.get('emergence_results', [])),
                    'narrative_bridge_coherence': round(csc_result['narrative_bridge'].coherence, 4),
                }
                if self._phase4_verbose:
                    csci_val = csc_result['csci'].csci
                    print(f"    [CSC] L{layer_id} step={step}: CSCI={csci_val:.4f} "
                          f"coherent={csc_result['csci'].is_coherent} "
                          f"narrative_coh={csc_result['narrative_bridge'].coherence:.4f}")

            # 7. NarrativeSelfEmergence (Phase 4 P1)
            if self.narrative_self_emergence is not None:
                # Collect narrative themes from narrative recursion operator
                narrative_themes = []
                narrative_level_dist = {}
                institutional_narrative = "silent"
                institutional_coherence = 0.0
                if self.narrative_recursion_operator is not None:
                    narr_summary = self.narrative_recursion_operator.get_summary()
                    narrative_level_dist = narr_summary.get('narrative_level_distribution', {})
                    # Extract themes from recent narrative history
                    recent_narratives = self.narrative_recursion_operator.get_narrative_history(n=5)
                    for nr in recent_narratives:
                        narrative_themes.append(nr.get('narrative_level', 'MINI_NARRATIVE'))
                    # Institutional narrative from level distribution
                    if narrative_level_dist.get('INSTITUTIONAL', 0) > 0:
                        institutional_narrative = "institutional_narrative_active"
                        institutional_coherence = min(1.0, narrative_level_dist.get('INSTITUTIONAL', 0) / 10.0)

                # Get MSI from result_entry
                msi_mean = 0.0
                if 'minimal_self' in result_entry and result_entry['minimal_self'] is not None:
                    msi_mean = result_entry['minimal_self'].get('msi_mean', 0.0)

                # Get ODI
                odi_val = self._last_odi_value

                # Get CIV (civilization count) from narrative level distribution
                civ_count = 0.0
                if narrative_level_dist:
                    civ_count = float(narrative_level_dist.get('CIVILIZATION', 0))

                # Get GBC coherence
                gbc_coherence_val = None
                if 'global_bias_constraint' in result_entry and result_entry['global_bias_constraint'] is not None:
                    gbc_coherence_val = result_entry['global_bias_constraint'].get('coherence', None)

                # Layer distribution
                layer_dist = {}
                if 'level_counts' in result_entry:
                    layer_dist = result_entry['level_counts']

                nse_result = self.narrative_self_emergence.step(
                    msi=msi_mean,
                    odi=odi_val,
                    narrative_themes=narrative_themes if narrative_themes else ["silent"],
                    narrative_level_distribution=narrative_level_dist if narrative_level_dist else {"MINI": 0},
                    institutional_narrative=institutional_narrative,
                    institutional_coherence=institutional_coherence,
                    layer_distribution=layer_dist if layer_dist else None,
                    step=step,
                    civ=civ_count if civ_count > 0 else None,
                    gbc_coherence=gbc_coherence_val,
                )
                result_entry['narrative_self_emergence'] = {
                    'nsi': round(nse_result['nsi'].nsi, 4),
                    'nsi_active': nse_result['nsi'].is_nsi_active,
                    'temporal_continuity': round(nse_result['nsi'].temporal_continuity, 4),
                    'narrative_stability': round(nse_result['nsi'].narrative_stability, 4),
                    'self_history_depth': round(nse_result['nsi'].self_history_depth, 4),
                    'continuity_score': round(nse_result['continuity'].continuity_score, 4),
                    'is_continuous': nse_result['continuity'].is_continuous,
                    'dominant_theme': nse_result['continuity'].dominant_theme,
                    'stability_score': round(nse_result['stability'].stability_score, 4),
                    'is_stable': nse_result['stability'].is_stable,
                    'n_turning_points': nse_result['history'].n_turning_points,
                }
                if self._phase4_verbose:
                    nsi_val = nse_result['nsi'].nsi
                    print(f"    [NSE] L{layer_id} step={step}: NSI={nsi_val:.4f} "
                          f"active={nse_result['nsi'].is_nsi_active} "
                          f"continuity={nse_result['continuity'].continuity_score:.3f} "
                          f"stability={nse_result['stability'].stability_score:.3f}")

            # ── Phase 4 P0: Adaptive Momentum Controller ──
            if self.adaptive_momentum_controller is not None:
                # Collect category heats from narrative recursion operator
                category_heats = {}
                if self.narrative_recursion_operator is not None:
                    narr_summary = self.narrative_recursion_operator.get_summary()
                    narrative_level_dist = narr_summary.get('narrative_level_distribution', {})
                    for level_name, count in narrative_level_dist.items():
                        category_heats[level_name] = float(count)
                if not category_heats:
                    category_heats = {'MINI': 0.0}

                # Get INSTITUTIONAL count from hierarchy
                inst_count = 0
                hl_state = self.hierarchy.get_layer_state_by_name('INSTITUTIONAL')
                if hl_state is not None:
                    inst_count = hl_state.get('institutional_count', 0)

                # Get CIV count
                civ_count = 0
                civ_state = self.hierarchy.get_layer_state_by_name('CIVILIZATION')
                if civ_state is not None:
                    civ_count = civ_state.get('civilization_count', 0)

                amc_result = self.adaptive_momentum_controller.step(
                    category_heats=category_heats,
                    institutional_count=inst_count,
                    civilization_count=civ_count,
                )
                result_entry['adaptive_momentum'] = {
                    'momentum_bonus': round(amc_result.momentum_bonus, 4),
                    'entropy': round(amc_result.entropy, 4),
                    'institutional_count': amc_result.institutional_count,
                    'institutional_rate': round(amc_result.institutional_rate, 4),
                    'adjustment': round(amc_result.adjustment, 6),
                    'mode': amc_result.mode,
                    'should_diffuse': amc_result.should_diffuse,
                    'should_focus': amc_result.should_focus,
                }
                if self._phase4_verbose:
                    print(f"    [AMC] L{layer_id} step={step}: "
                          f"bonus={amc_result.momentum_bonus:.4f} "
                          f"mode={amc_result.mode} "
                          f"adj={amc_result.adjustment:.6f}")

            # ── Phase 4 P0: Institutional Layer Protector ──
            if self.institutional_layer_protector is not None:
                # Get INSTITUTIONAL count
                inst_count_ilp = 0
                hl_state_ilp = self.hierarchy.get_layer_state_by_name('INSTITUTIONAL')
                if hl_state_ilp is not None:
                    inst_count_ilp = hl_state_ilp.get('institutional_count', 0)

                # Get ODI
                odi_ilp = self._last_odi_value

                # Get INSTITUTIONAL diversity (number of categories)
                n_categories = 0
                if hasattr(layer.constraints, 'institutional_categories'):
                    n_categories = len(layer.constraints.institutional_categories)
                elif 'level_counts' in result_entry and result_entry['level_counts']:
                    n_categories = len(result_entry['level_counts'])

                # Build institutional categories dict from level counts
                inst_categories = {}
                if 'level_counts' in result_entry and result_entry['level_counts']:
                    inst_categories = {str(k): int(v) for k, v in result_entry['level_counts'].items()}

                ilp_result = self.institutional_layer_protector.step(
                    institutional_count=inst_count_ilp,
                    institutional_categories=inst_categories if inst_categories else None,
                    current_odi=odi_ilp,
                )
                result_entry['institutional_protector'] = {
                    'institutional_count': ilp_result.institutional_count,
                    'institutional_floor': round(ilp_result.institutional_floor, 4),
                    'consumption_rate_limit': round(ilp_result.consumption_rate_limit, 4),
                    'transition_allowed': ilp_result.transition_allowed,
                    'transition_openness': round(ilp_result.transition_openness, 4),
                    'n_categories': ilp_result.n_categories,
                    'diversity_sufficient': ilp_result.diversity_sufficient,
                    'protection_level': ilp_result.protection_level,
                    'should_consume': ilp_result.should_consume,
                }
                if self._phase4_verbose:
                    print(f"    [ILP] L{layer_id} step={step}: "
                          f"count={ilp_result.institutional_count} "
                          f"floor={ilp_result.institutional_floor:.4f} "
                          f"level={ilp_result.protection_level} "
                          f"transition={'OPEN' if ilp_result.transition_allowed else 'CLOSED'}")

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

        # ILP gating: check if InstitutionalLayerProtector allows consumption
        ilp_allows_consume = True
        if self.institutional_layer_protector is not None:
            ilp_allows_consume = self.institutional_layer_protector.should_consume

        if self.auto_encapsulate and just_sealed and ilp_allows_consume:
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
                    self.seventh_threshold_detector.has_transition_occurred
                    if self.seventh_threshold_detector else False),
                'seventh_threshold_confidence': (
                    self.seventh_threshold_detector.latest_result.transition_confidence
                    if self.seventh_threshold_detector and self.seventh_threshold_detector.latest_result else 0.0),
                'cooperative_emergence_detector_active': self.cooperative_emergence_detector is not None,
                'cooperative_emergence_detected': (
                    self.cooperative_emergence_detector.has_emergence_occurred
                    if self.cooperative_emergence_detector else False),
                'cooperative_emergence_confidence': (
                    self.cooperative_emergence_detector.latest_result.confidence
                    if self.cooperative_emergence_detector and self.cooperative_emergence_detector.latest_result else 0.0),
                'lateral_coupler_active': self.lateral_coupler is not None,
                'lateral_coupler_n_structures': (
                    self.lateral_coupler.n_structures
                    if self.lateral_coupler else 0),
                'global_bias_constraint_active': self.global_bias_constraint is not None,
                'global_bias_constraint_pass_rate': (
                    self.global_bias_constraint.get_pass_rate()
                    if self.global_bias_constraint else 0.0),
                'global_bias_constraint_coherence_trend': (
                    self.global_bias_constraint.get_coherence_trend()
                    if self.global_bias_constraint else []),
                'global_bias_constraint_balance_trend': (
                    self.global_bias_constraint.get_balance_trend()
                    if self.global_bias_constraint else []),
                'layers_with_results': list(self._phase2_layer_results.keys()),
            },
            'phase4_summary': {
                'adaptive_momentum_controller_active': self.adaptive_momentum_controller is not None,
                'institutional_layer_protector_active': self.institutional_layer_protector is not None,
                'cross_scale_coupling_active': self.cross_scale_coupling is not None,
                'narrative_self_emergence_active': self.narrative_self_emergence is not None,
                'amc_history': (
                    self.adaptive_momentum_controller.get_history()
                    if self.adaptive_momentum_controller else None),
                'ilp_history': (
                    self.institutional_layer_protector.get_history()
                    if self.institutional_layer_protector else None),
                'nse_summary': (
                    self.narrative_self_emergence.get_summary()
                    if self.narrative_self_emergence else None),
                'nse_nsi_trend': (
                    self.narrative_self_emergence.get_nsi_trend()
                    if self.narrative_self_emergence else None),
            },
            'gbc_checks': [
                {
                    'passed': r.passed,
                    'coherence': round(r.coherence, 4),
                    'balance': round(r.balance, 4),
                    'violating_mechanisms': r.violating_mechanisms,
                    'n_mechanisms': len(r.local_biases),
                }
                for r in (self.global_bias_constraint.get_history() if self.global_bias_constraint else [])
            ],
            'phase3_summary': {
                'minimal_self_detector_active': self.minimal_self_detector is not None,
                'anticipatory_bias_engine_active': self.anticipatory_bias_engine is not None,
                'counterfactual_engine_active': self.counterfactual_engine is not None,
                'minimal_self_detected': (
                    self.minimal_self_detector.latest_result.minimal_self_detected
                    if self.minimal_self_detector and self.minimal_self_detector.latest_result else False),
                'msi': (
                    self.minimal_self_detector.latest_result.msi
                    if self.minimal_self_detector and self.minimal_self_detector.latest_result else 0.0),
                'anticipation_reliable': (
                    self.anticipatory_bias_engine.get_prediction_accuracy() > 0.5
                    if self.anticipatory_bias_engine else False),
                'anticipation_accuracy': (
                    self.anticipatory_bias_engine.get_prediction_accuracy()
                    if self.anticipatory_bias_engine else 0.0),
                'counterfactual_active': (
                    self.counterfactual_engine.is_active
                    if self.counterfactual_engine else False),
                'counterfactual_n_branches': (
                    self.counterfactual_engine.n_active_branches
                    if self.counterfactual_engine else 0),
                'narrative_recursion_active': (
                    self.narrative_recursion_operator is not None),
                'narrative_summary': (
                    self.narrative_recursion_operator.get_summary()
                    if self.narrative_recursion_operator else None),
                'global_bias_constraint_active': self.global_bias_constraint is not None,
                'global_bias_constraint_pass_rate': (
                    self.global_bias_constraint.get_pass_rate()
                    if self.global_bias_constraint else 0.0),
                'global_bias_constraint_latest': (
                    (lambda h: {
                        'passed': h[0].passed,
                        'coherence': round(h[0].coherence, 4),
                        'balance': round(h[0].balance, 4),
                        'violating_mechanisms': h[0].violating_mechanisms,
                    })(self.global_bias_constraint.get_history(limit=1))
                    if self.global_bias_constraint and self.global_bias_constraint.get_history(limit=1)
                    else None),
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
