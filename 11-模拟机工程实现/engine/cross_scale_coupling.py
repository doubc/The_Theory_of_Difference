"""
engine/cross_scale_coupling.py — 跨尺度耦合器 (CrossScaleCoupling)

Phase 4 P1 组件（新增）

职责：建立 MINI ↔ INSTITUTIONAL ↔ CIVILIZATION 三个层级之间的双向因果。
当前封装机制仅支持自底向上（MINI → INSTITUTIONAL → CIVILIZATION），
缺少高层级对低层级的"向下传导"影响。

理论依据：
- 差异论 V1.7 底图事件与底图承接 — 底图事件后旧资源在新空间中寻找承接位置
- 制度相变 Γ — 当 K_t ≤ K* 时，新制度对所有层级施加新约束
- 《象界》八环节咬合 — "耦合功能化"需要双向约束

四个子组件：
1. TopDownConstraint — 高层级对低层级的约束偏置
2. BottomUpEmergence — 低层级向高层级的涌现质量评估
3. ScaleBridgingNarrator — 跨尺度叙事桥梁
4. CrossScaleCoherenceIndex (CSCI) — 跨尺度相干指数

设计原则：
1. 双向耦合不能引入"目标函数优化"——必须是纯结构性的约束传导
2. Top-Down 强度必须渐进（避免低层级失去自主性）
3. 涌现存活标准：高层级在 ≥ 50 步内保持结构稳定性
4. 耦合响应延迟 ≥ 15 步（避免高频振荡）

语义防火墙：
- "约束" ≠ "控制"（是结构性偏置，非外部指令）
- "涌现" ≠ "创造"（是已有结构的重组）
- "叙事" ≠ "意义"（是功能角色的结构性描述）
- "因果" ≠ "因果力"（是跨层级的约束传导）
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

import torch
import numpy as np


# ─── 默认配置 ───
DEFAULT_CROSS_SCALE_COUPLING_CONFIG = {
    # Top-Down 约束
    'topdown_max_constraint_strength': 0.15,   # 最大约束强度（避免过度压制低层级）
    'topdown_min_constraint_strength': 0.02,   # 最小约束强度
    'topdown_response_delay': 15,              # 响应延迟步数
    'topdown_decay_rate': 0.97,                # 约束衰减率（每步）
    'topdown_propagation_depth': 2,            # 向下传导的最大层级距离
    'topdown_stability_threshold': 0.3,        # P1: 高层级稳定性门槛（0.5→0.3，让TopDown激活）

    # Bottom-Up 涌现质量评估
    'emergence_min_stability_steps': 50,       # 涌现存活所需最小稳定步数
    'emergence_stability_threshold': 0.6,      # 结构稳定性阈值
    'emergence_min_odi': 0.25,                 # 涌现所需最低 ODI
    'emergence_cooldown_steps': 30,            # 涌现后冷却步数

    # 跨尺度叙事桥梁
    'narrative_bridge_window': 100,            # 叙事桥梁计算窗口
    'narrative_min_coherence': 0.3,            # 叙事相干最低阈值
    'narrative_integration_rate': 0.05,        # 叙事整合速率

    # CSCI 计算
    'csci_levels': ['MINI', 'INSTITUTIONAL', 'CIVILIZATION'],
    'csci_alpha': 0.4,   # 层级间相干权重
    'csci_beta': 0.3,    # 叙事方向一致性权重
    'csci_gamma': 0.3,   # 结构稳定性权重

    # Phase 5 Track B2: 层级耦合模式
    # 'parallel': L0→L1 和 L0→L2 并行（原始模式，L1-L2 耦合 r≈0.98）
    # 'serial':   L0→L1→L2 串行（理论正确模式，L2 从 L1 制度状态派生）
    'coupling_mode': 'parallel',

    # Serial mode: L1→L2 传导参数
    'serial_l1_to_l2_delay': 15,              # L1→L2 传导延迟步数
    # Track B2 default:
    #   'serial_l1_to_l2_attenuation': 0.7,
    #   'serial_l1_to_l2_noise': 0.05,
    # Track B3 default (2026-06-02):
    'serial_l1_to_l2_attenuation': 0.3,       # L1→L2 信号衰减（B3: 0.7→0.3，大幅降低镜像效应）
    'serial_l1_to_l2_noise_abs': 0.1,         # B3: 绝对噪声基底
    'serial_l1_to_l2_noise_rel': 0.3,         # B3: 相对噪声（相对于 L1 信号强度的比例）
    'serial_l1_to_l2_odi_factor': 0.5,        # B3: L2 ODI 额外衰减因子（B2 为 0.8）
    # Track B3: L2 层内自生动力学
    'serial_l2_intrinsic_perturbation_rate': 0.02,   # 每步对 L2 结构向量施加随机扰动的概率
    'serial_l2_intrinsic_perturbation_magnitude': 0.15,  # 扰动幅度
    'serial_l2_autonomous_decay': 0.98,              # L2 稳定性每步自动衰减率（模拟文明层级自然耗散）
    # Track B3: L0→L1 信号增强
    'serial_l0_to_l1_signal_weight': 0.4,     # L0 信号在 L1 中的权重（抑制 L1 自稳压制）

    # ─── Phase 5 Track B4: Constraint Conduction Mode ───
    # coupling_mode='constraint': L2 有独立聚簇，L1 提供软约束边界
    'l2_N0': 72,                              # L2 独立聚簇规模
    'constraint_stability_weight': 0.2,       # L1 稳定性约束权重
    'constraint_activity_weight': 0.15,       # L1 叙事活动约束权重
    'constraint_structure_weight': 0.1,       # L1 聚簇结构约束权重
    'constraint_tolerance': 0.3,              # 约束容差（软边界）
    'l0_direct_to_l2_weight': 0.4,            # L0 直接输入 L2 权重
    'l0_to_l1_signal_weight': 0.5,            # 增强 L0→L1 信号权重（B4: 0.4→0.5）
    'l1_autonomous_stability_weight': 0.5,    # 降低 L1 制度自稳权重（B4: ~0.8→0.5）
    'l0_to_l1_response_delay': 10,            # L0→L1 响应延迟步数
    'l2_narrative_threshold': 0.01,           # 降低 L2 叙事阈值
    'constraint_response_tracking_window': 200,  # 约束响应延迟追踪窗口

    # ─── Phase 5 Track B5: Independent L2 Clustering + Stability Floor ───
    'l2_independent_N0': 72,                   # L2 独立聚簇规模
    'l2_stability_floor': 0.15,                # L2 最小稳定性（防止被 clamp 到零）
    'l2_constraint_strength': 0.1,             # L1→L2 软约束强度（additive）
    'l2_perturbation_rate': 0.03,              # L2 每步结构扰动概率
    'l2_perturbation_magnitude': 0.2,          # L2 扰动幅度
    'l2_autonomous_decay': 0.97,               # L2 稳定性自衰减率
    'l2_odi_independence_weight': 0.5,         # L2 ODI 独立计算权重
    'l2_clustering_noise': 0.15,               # L2 聚簇生成噪声
    'l2_constraint_bias_type': 'additive',     # 'additive' 或 'multiplicative'
    'l2_min_active_objects': 10,               # L2 最小活动对象数（用于叙事激活）
}


class CouplingDirection(Enum):
    """耦合方向"""
    BOTTOM_UP = "bottom_up"
    TOP_DOWN = "top_down"
    BIDIRECTIONAL = "bidirectional"


class EmergenceQuality(Enum):
    """涌现质量等级"""
    POOR = 0        # 质量差，无法存活
    MARGINAL = 1    # 勉强存活
    GOOD = 2        # 良好，可存活
    STRONG = 3      # 强涌现，稳定存活


@dataclass
class TopDownConstraintState:
    """Top-Down 约束状态"""
    source_level: str                 # 约束来源层级
    target_level: str                 # 约束目标层级
    constraint_strength: float        # 当前约束强度 [0, 1]
    constraint_vector: Optional[torch.Tensor] = None  # 约束方向向量
    steps_elapsed: int = 0            # 约束存在的时间步数
    is_active: bool = False           # 约束是否活跃


@dataclass
class EmergenceQualityResult:
    """涌现质量评估结果"""
    source_level: str                 # 涌现来源层级
    target_level: str                 # 涌现目标层级
    quality: EmergenceQuality         # 涌现质量等级
    stability_score: float            # 结构稳定性得分 [0, 1]
    odi_score: float                  # ODI 得分 [0, 1]
    steps_stable: int                 # 已稳定步数
    is_surviving: bool                # 是否存活（质量 >= GOOD 且稳定步数达标）
    step: int                         # 当前步数


@dataclass
class ScaleBridgingNarrative:
    """跨尺度叙事桥梁"""
    mini_narrative: str               # MINI 层级叙事标签
    institutional_narrative: str      # INSTITUTIONAL 层级叙事标签
    civilization_narrative: str       # CIVILIZATION 层级叙事标签
    coherence: float                  # 三层叙事相干度 [0, 1]
    is_coherent: bool                 # 是否达到相干阈值
    integration_progress: float       # 整合进度 [0, 1]
    step: int                         # 当前步数


@dataclass
class CrossScaleCoherenceResult:
    """跨尺度相干指数结果"""
    csci: float                       # 跨尺度相干指数 [0, 1]
    pairwise_coherence: Dict[str, float]  # 层级对之间的相干度
    narrative_coherence: float        # 叙事方向一致性 [0, 1]
    structural_coherence: float       # 结构稳定性相干 [0, 1]
    level_stabilities: Dict[str, float]   # 各层级稳定性
    step: int                         # 当前步数
    is_coherent: bool                 # CSCI 是否达标（> 0.5）


# ─── Constraint Conduction (Track B4) ───

@dataclass
class ConstraintConductionState:
    """约束传导状态"""
    l1_stability_constraint: float       # L1 稳定性约束值
    l1_activity_constraint: float        # L1 叙事活动约束值
    l1_structure_constraint: float       # L1 聚簇结构约束值
    l2_autonomous_stability: float       # L2 自主演化稳定性
    l2_constrained_stability: float      # L2 受约束后的稳定性
    l2_independent_odi: float            # L2 独立 ODI
    constraint_response_delay: int       # 约束响应延迟（步）
    step: int


class ConstraintConduction:
    """层间约束传导 (Track B4)

    核心转变：从"状态派生"到"约束传导"
    - L2 不直接从 L1 派生状态，而是从 L0 独立聚簇 + L1 约束边界演化
    - L1 提供软边界约束（clamp），而非硬派生
    - L2 有独立的差异场和动力学

    理论依据：
    - 差异论 §2.2: "层级不是信息的逐级传递，而是差异在不同尺度上的重新组织"
    - 差异论 §2.3: "制度是文明的约束，但不是文明的决定者"
    """

    def __init__(self, config=None):
        from collections import deque
        import numpy as np
        cfg = dict(DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
        cfg.update(config or {})
        self.stability_weight = cfg.get('constraint_stability_weight', 0.2)
        self.activity_weight = cfg.get('constraint_activity_weight', 0.15)
        self.structure_weight = cfg.get('constraint_structure_weight', 0.1)
        self.tolerance = cfg.get('constraint_tolerance', 0.3)
        self.l0_direct_weight = cfg.get('l0_direct_to_l2_weight', 0.4)
        self.l0_to_l1_signal_weight = cfg.get('l0_to_l1_signal_weight', 0.5)
        self.l1_autonomous_weight = cfg.get('l1_autonomous_stability_weight', 0.5)
        self.l0_to_l1_response_delay = cfg.get('l0_to_l1_response_delay', 10)
        self.l2_narrative_threshold = cfg.get('l2_narrative_threshold', 0.01)
        self.response_tracking_window = cfg.get('constraint_response_tracking_window', 200)

        self._step_count = 0
        self._l1_state_buffer = deque(maxlen=self.response_tracking_window)
        self._l2_autonomous_history = deque(maxlen=self.response_tracking_window)
        self._l2_constrained_history = deque(maxlen=self.response_tracking_window)
        self._constraint_response_delays = deque(maxlen=100)
        self._last_state = None

    def update(self, l0_state, l1_state, l2_autonomous_state):
        self._step_count += 1
        self._l1_state_buffer.append({
            'step': self._step_count,
            'stability_score': l1_state.get('stability_score', 0.0),
            'odi': l1_state.get('odi', 0.0),
            'narrative_count': l1_state.get('narrative_count', 0),
        })

        l1_stability = l1_state.get('stability_score', 0.0)
        l1_odi = l1_state.get('odi', 0.0)
        l1_narrative_count = l1_state.get('narrative_count', 0)

        l1_stability_constraint = l1_stability
        l1_activity_constraint = l1_narrative_count / 100.0
        l1_structure_constraint = l1_odi

        l2_auto_stability = l2_autonomous_state.get('stability_score', 0.0)
        l2_auto_odi = l2_autonomous_state.get('odi', 0.0)

        l0_stability = l0_state.get('stability_score', 0.0)

        l2_base_stability = (
            l2_auto_stability * (1.0 - self.l0_direct_weight) +
            l0_stability * self.l0_direct_weight
        )

        lower_bound = l1_stability_constraint * (1.0 - self.tolerance)
        upper_bound = l1_stability_constraint * (1.0 + self.tolerance)
        if l1_stability_constraint < 0.1:
            lower_bound = 0.0
            upper_bound = 1.0

        l2_constrained_stability = float(np.clip(l2_base_stability, lower_bound, upper_bound))

        response_delay = self._detect_response_delay(l1_stability, l2_constrained_stability)
        if response_delay is not None:
            self._constraint_response_delays.append(response_delay)

        self._l2_autonomous_history.append(l2_base_stability)
        self._l2_constrained_history.append(l2_constrained_stability)

        state = ConstraintConductionState(
            l1_stability_constraint=l1_stability_constraint,
            l1_activity_constraint=l1_activity_constraint,
            l1_structure_constraint=l1_structure_constraint,
            l2_autonomous_stability=l2_base_stability,
            l2_constrained_stability=l2_constrained_stability,
            l2_independent_odi=l2_auto_odi,
            constraint_response_delay=response_delay if response_delay is not None else -1,
            step=self._step_count,
        )
        self._last_state = state
        return state

    def _detect_response_delay(self, l1_stability, l2_stability):
        if len(self._l1_state_buffer) < 5:
            return None
        recent_l1 = list(self._l1_state_buffer)[-10:]
        l1_changes = []
        for i in range(1, len(recent_l1)):
            delta = abs(recent_l1[i]['stability_score'] - recent_l1[i-1]['stability_score'])
            if delta > 0.15:
                l1_changes.append((recent_l1[i-1]['step'], recent_l1[i]['step'], delta))
        if not l1_changes:
            return None
        if len(self._l2_constrained_history) >= 5:
            l2_values = list(self._l2_constrained_history)
            for i in range(1, len(l2_values)):
                if abs(l2_values[i] - l2_values[i-1]) > 0.1:
                    estimated_delay = max(1, i)
                    if 1 <= estimated_delay <= 100:
                        return estimated_delay
        return None

    def get_l1_l2_correlation(self):
        auto_vals = list(self._l2_autonomous_history)
        constrained_vals = list(self._l2_constrained_history)
        if len(auto_vals) < 30 or len(constrained_vals) < 30:
            return None
        min_len = min(len(auto_vals), len(constrained_vals))
        auto_arr = np.array(auto_vals[-min_len:])
        constrained_arr = np.array(constrained_vals[-min_len:])
        return float(np.corrcoef(auto_arr, constrained_arr)[0, 1])

    def get_avg_response_delay(self):
        delays = [d for d in self._constraint_response_delays if d > 0]
        return float(np.mean(delays)) if delays else 0.0

    def get_summary(self):
        import numpy as np
        return {
            'l2_autonomous_mean': float(np.mean(self._l2_autonomous_history)) if self._l2_autonomous_history else 0.0,
            'l2_constrained_mean': float(np.mean(self._l2_constrained_history)) if self._l2_constrained_history else 0.0,
            'l1_l2_correlation': self.get_l1_l2_correlation(),
            'avg_response_delay': self.get_avg_response_delay(),
            'n_response_events': len(self._constraint_response_delays),
            'latest_state': {
                'l1_stability_constraint': self._last_state.l1_stability_constraint if self._last_state else 0.0,
                'l2_autonomous_stability': self._last_state.l2_autonomous_stability if self._last_state else 0.0,
                'l2_constrained_stability': self._last_state.l2_constrained_stability if self._last_state else 0.0,
                'l2_independent_odi': self._last_state.l2_independent_odi if self._last_state else 0.0,
            }
        }

    def reset(self):
        self._step_count = 0
        self._l1_state_buffer.clear()
        self._l2_autonomous_history.clear()
        self._l2_constrained_history.clear()
        self._constraint_response_delays.clear()
        self._last_state = None


class IndependentL2Coupling:
    """独立 L2 聚簇 + 软约束 (Track B5)

    核心设计：
    1. L2 独立聚簇：从 L0 结构向量生成 L2 自己的聚簇，而非从 L1 派生
    2. 软约束：L1 提供 additive 偏置，而非 hard clamp
    3. 稳定性地板：L2 有最小稳定性，防止被压制到零
    4. 内在动力学：L2 有自己的扰动和衰减机制

    理论依据：
    - 差异论 §2.2: "层级不是信息的逐级传递，而是差异在不同尺度上的重新组织"
    - 差异论 §2.3: "制度是文明的约束，但不是文明的决定者"
    """

    def __init__(self, config=None):
        cfg = dict(DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
        cfg.update(config or {})
        self.N0 = cfg.get('l2_independent_N0', 72)
        self.stability_floor = cfg.get('l2_stability_floor', 0.15)
        self.constraint_strength = cfg.get('l2_constraint_strength', 0.1)
        self.perturbation_rate = cfg.get('l2_perturbation_rate', 0.03)
        self.perturbation_magnitude = cfg.get('l2_perturbation_magnitude', 0.2)
        self.autonomous_decay = cfg.get('l2_autonomous_decay', 0.97)
        self.odi_independence_weight = cfg.get('l2_odi_independence_weight', 0.5)
        self.clustering_noise = cfg.get('l2_clustering_noise', 0.15)
        self.bias_type = cfg.get('l2_constraint_bias_type', 'additive')
        self.min_active_objects = cfg.get('l2_min_active_objects', 10)

        self._step_count = 0
        self._l2_stability_history = deque(maxlen=500)
        self._l1_stability_history = deque(maxlen=500)
        self._l0_stability_history = deque(maxlen=500)
        self._l2_odi_history = deque(maxlen=500)
        self._l0_odi_history = deque(maxlen=500)
        self._l1_l2_correlation_window = deque(maxlen=200)
        self._l0_l2_correlation_window = deque(maxlen=200)
        self._response_delays = deque(maxlen=100)
        self._last_l2_state = None
        self._l2_structure_vector = None
        self._l2_autonomous_stability = 0.0

    def update(self, l0_state, l1_state, l2_seed=None):
        """执行一步独立 L2 耦合

        Parameters
        ----------
        l0_state : dict
            MINI 层级状态 {stability_score, odi, structure_vector}
        l1_state : dict
            INSTITUTIONAL 层级状态 {stability_score, odi, structure_vector}
        l2_seed : int, optional
            L2 聚簇随机种子

        Returns
        -------
        dict
            L2 独立耦合结果
        """
        self._step_count += 1

        l0_stability = l0_state.get('stability_score', 0.0)
        l0_odi = l0_state.get('odi', 0.0)
        l0_vector = l0_state.get('structure_vector')

        l1_stability = l1_state.get('stability_score', 0.0)
        l1_odi = l1_state.get('odi', 0.0)
        l1_vector = l1_state.get('structure_vector')

        # Record histories
        self._l0_stability_history.append(l0_stability)
        self._l1_stability_history.append(l1_stability)
        self._l0_odi_history.append(l0_odi)

        # ── Step 1: Generate L2 autonomous stability (独立于 L1) ──
        # L2 自主稳定性来自 L0 的直接映射 + 内在动力学
        if l0_stability > 0:
            # L2 从 L0 继承基础稳定性，但经过衰减
            l2_auto_base = l0_stability * 0.6
        else:
            # L0 无活动时，L2 依靠内在动力学维持最低活动
            l2_auto_base = 0.05

        # 应用自主衰减
        if self._l2_autonomous_stability > 0:
            l2_auto_base = 0.7 * l2_auto_base + 0.3 * (self._l2_autonomous_stability * self.autonomous_decay)

        # ── Step 2: Generate L2 structure vector (独立聚簇) ──
        if l0_vector is not None and l0_vector.numel() > 0:
            # 从 L0 向量生成 L2 向量：添加聚类噪声以模拟独立差异场
            noise = torch.randn_like(l0_vector) * self.clustering_noise
            l2_vector = l0_vector + noise

            # 内在扰动
            if np.random.random() < self.perturbation_rate:
                perturbation = torch.randn_like(l2_vector) * self.perturbation_magnitude
                l2_vector = l2_vector + perturbation

            norm = l2_vector.norm().item()
            if norm > 1e-8:
                l2_vector = l2_vector / norm
        else:
            l2_vector = None

        self._l2_structure_vector = l2_vector

        # ── Step 3: Compute L2 independent ODI ──
        # L2 ODI = L0 ODI * independence_weight + 独立噪声
        l2_odi = l0_odi * self.odi_independence_weight
        if l2_vector is not None:
            # 基于 L2 向量的幅度添加独立 ODI 分量
            vec_magnitude = l2_vector.norm().item()
            l2_odi = l2_odi + vec_magnitude * (1 - self.odi_independence_weight) * 0.3
        l2_odi = float(np.clip(l2_odi, 0.0, 1.0))

        # ── Step 4: Apply soft constraint from L1 (非 hard clamp) ──
        if self.bias_type == 'additive':
            # Additive: L1 提供偏置，不改变 L2 的基础值范围
            l1_constraint_bias = (l1_stability - l2_auto_base) * self.constraint_strength
            l2_stability = l2_auto_base + l1_constraint_bias
        else:
            # Multiplicative: L1 按比例调节 L2
            if l2_auto_base > 0:
                ratio = l1_stability / l2_auto_base
                l2_stability = l2_auto_base * (0.7 + 0.3 * ratio)
            else:
                l2_stability = l1_stability * self.constraint_strength

        # ── Step 5: Apply stability floor ──
        l2_stability = float(np.clip(l2_stability, self.stability_floor, 1.0))

        self._l2_autonomous_stability = l2_auto_base
        self._l2_stability_history.append(l2_stability)
        self._l2_odi_history.append(l2_odi)

        # ── Step 6: Track correlations ──
        if len(self._l1_stability_history) >= 30:
            l1_vals = np.array(list(self._l1_stability_history)[-100:])
            l2_vals = np.array(list(self._l2_stability_history)[-100:])
            min_len = min(len(l1_vals), len(l2_vals))
            if min_len >= 30:
                corr = np.corrcoef(l1_vals[-min_len:], l2_vals[-min_len:])[0, 1]
                self._l1_l2_correlation_window.append(float(corr) if not np.isnan(corr) else 0.0)

        if len(self._l0_stability_history) >= 30:
            l0_vals = np.array(list(self._l0_stability_history)[-100:])
            l2_vals = np.array(list(self._l2_stability_history)[-100:])
            min_len = min(len(l0_vals), len(l2_vals))
            if min_len >= 30:
                corr = np.corrcoef(l0_vals[-min_len:], l2_vals[-min_len:])[0, 1]
                self._l0_l2_correlation_window.append(float(corr) if not np.isnan(corr) else 0.0)

        # ── Step 7: Detect response delay (L1→L2) ──
        response_delay = self._detect_response_delay(l1_stability, l2_stability)
        if response_delay is not None:
            self._response_delays.append(response_delay)

        state = {
            'stability_score': l2_stability,
            'odi': l2_odi,
            'structure_vector': l2_vector,
            'independent_l2': True,
            'l2_autonomous_stability': l2_auto_base,
            'l1_constraint_bias': l1_constraint_bias if self.bias_type == 'additive' else 0.0,
            'stability_floor': self.stability_floor,
            'l1_l2_correlation': self.get_l1_l2_correlation(),
            'l0_l2_correlation': self.get_l0_l2_correlation(),
            'avg_response_delay': self.get_avg_response_delay(),
            'step': self._step_count,
        }
        self._last_l2_state = state
        return state

    def _detect_response_delay(self, l1_stability, l2_stability):
        """检测 L1→L2 的响应延迟"""
        if len(self._l1_stability_history) < 10:
            return None
        recent_l1 = list(self._l1_stability_history)[-20:]
        l1_changes = []
        for i in range(1, len(recent_l1)):
            delta = abs(recent_l1[i] - recent_l1[i - 1])
            if delta > 0.1:
                l1_changes.append(i)
        if not l1_changes:
            return None
        recent_l2 = list(self._l2_stability_history)[-20:]
        l2_changes = []
        for i in range(1, len(recent_l2)):
            delta = abs(recent_l2[i] - recent_l2[i - 1])
            if delta > 0.05:
                l2_changes.append(i)
        if not l2_changes:
            return None
        # 简单匹配：找到最近的 L1 变化后 L2 变化的延迟
        for l1_idx in l1_changes[-3:]:
            for l2_idx in l2_changes:
                if l2_idx > l1_idx and (l2_idx - l1_idx) <= 20:
                    return l2_idx - l1_idx
        return None

    def get_l1_l2_correlation(self):
        vals = list(self._l1_l2_correlation_window)
        if not vals:
            return None
        return float(np.mean(vals))

    def get_l0_l2_correlation(self):
        vals = list(self._l0_l2_correlation_window)
        if not vals:
            return None
        return float(np.mean(vals))

    def get_avg_response_delay(self):
        delays = [d for d in self._response_delays if d > 0]
        return float(np.mean(delays)) if delays else 0.0

    def get_summary(self):
        return {
            'l2_stability_mean': float(np.mean(self._l2_stability_history)) if self._l2_stability_history else 0.0,
            'l2_stability_min': float(np.min(self._l2_stability_history)) if self._l2_stability_history else 0.0,
            'l2_stability_max': float(np.max(self._l2_stability_history)) if self._l2_stability_history else 0.0,
            'l2_odi_mean': float(np.mean(self._l2_odi_history)) if self._l2_odi_history else 0.0,
            'l1_l2_correlation': self.get_l1_l2_correlation(),
            'l0_l2_correlation': self.get_l0_l2_correlation(),
            'avg_response_delay': self.get_avg_response_delay(),
            'n_response_events': len(self._response_delays),
            'latest_state': self._last_l2_state,
        }

    def reset(self):
        self._step_count = 0
        self._l2_stability_history.clear()
        self._l1_stability_history.clear()
        self._l0_stability_history.clear()
        self._l2_odi_history.clear()
        self._l0_odi_history.clear()
        self._l1_l2_correlation_window.clear()
        self._l0_l2_correlation_window.clear()
        self._response_delays.clear()
        self._last_l2_state = None
        self._l2_structure_vector = None
        self._l2_autonomous_stability = 0.0


class TopDownConstraint:
    """高层级对低层级的约束

    当高层级（INSTITUTIONAL/CIVILIZATION）形成稳态时，
    对低层级（MINI）的演化方向施加结构性偏置。

    理论依据：制度相变 Γ — 当 K_t ≤ K* 时，新制度对所有层级施加新约束。
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_CROSS_SCALE_COUPLING_CONFIG, **(config or {})}
        self.max_strength = cfg['topdown_max_constraint_strength']
        self.min_strength = cfg['topdown_min_constraint_strength']
        self.response_delay = cfg['topdown_response_delay']
        self.decay_rate = cfg['topdown_decay_rate']
        self.propagation_depth = cfg['topdown_propagation_depth']
        self.stability_threshold = cfg.get('topdown_stability_threshold', 0.5)

        self._step_count = 0
        self._active_constraints: Dict[str, TopDownConstraintState] = {}
        self._constraint_history: Deque[Dict] = deque(maxlen=200)

    def update(
        self,
        level_states: Dict[str, Dict],
        bias_field: Optional[torch.Tensor] = None,
    ) -> Dict[str, TopDownConstraintState]:
        """更新 Top-Down 约束

        Parameters
        ----------
        level_states : Dict[str, Dict]
            各层级状态 {level_name: {odI, structure_vector, narrative_label, ...}}
        bias_field : Optional[torch.Tensor]
            当前低层级的偏置场（用于计算约束方向）

        Returns
        -------
        Dict[str, TopDownConstraintState]
            活跃的约束状态 {constraint_id: state}
        """
        self._step_count += 1

        # 1. 衰减现有约束
        for cid, state in list(self._active_constraints.items()):
            state.steps_elapsed += 1
            state.constraint_strength *= self.decay_rate
            if state.constraint_strength < self.min_strength * 0.5:
                del self._active_constraints[cid]

        # 2. 从高层级生成新约束
        high_levels = ['CIVILIZATION', 'INSTITUTIONAL']
        low_levels = ['MINI', 'INSTITUTIONAL']

        for high_level in high_levels:
            if high_level not in level_states:
                continue
            high_state = level_states[high_level]

            # 检查高层级是否达到稳态
            stability = high_state.get('stability_score', 0.0)
            if stability < self.stability_threshold:
                continue

            for low_level in low_levels:
                if low_level == high_level:
                    continue

                # 层级距离检查
                level_order = ['MINI', 'INSTITUTIONAL', 'CIVILIZATION']
                high_idx = level_order.index(high_level) if high_level in level_order else 0
                low_idx = level_order.index(low_level) if low_level in level_order else 0
                distance = abs(high_idx - low_idx)

                if distance > self.propagation_depth:
                    continue

                # 生成约束
                constraint_id = f"{high_level}→{low_level}"

                # 约束强度：基于高层级稳定性和层级距离
                distance_factor = 1.0 / (distance + 1)
                base_strength = stability * distance_factor * self.max_strength

                # 响应延迟：前 N 步不施加约束
                if self._step_count <= self.response_delay:
                    effective_strength = 0.0
                else:
                    effective_strength = base_strength

                # 约束方向：基于高层级的结构向量
                constraint_vector = None
                if bias_field is not None and high_state.get('structure_vector') is not None:
                    high_vec = high_state['structure_vector']
                    if high_vec is not None and high_vec.numel() > 0:
                        # 约束方向 = 高层级结构向量在低层级偏置场方向的投影
                        bias_flat = bias_field.flatten()
                        high_flat = high_vec.flatten()
                        min_len = min(len(bias_flat), len(high_flat))
                        if min_len > 0:
                            high_sub = high_flat[:min_len]
                            norm = high_sub.norm().item()
                            if norm > 1e-8:
                                constraint_vector = high_sub / norm

                state = TopDownConstraintState(
                    source_level=high_level,
                    target_level=low_level,
                    constraint_strength=effective_strength,
                    constraint_vector=constraint_vector,
                    steps_elapsed=0,
                    is_active=effective_strength > self.min_strength,
                )
                self._active_constraints[constraint_id] = state

        # 记录历史
        self._constraint_history.append({
            'step': self._step_count,
            'n_active': len(self._active_constraints),
            'total_strength': sum(s.constraint_strength for s in self._active_constraints.values()),
        })

        return self._active_constraints

    def apply_constraint(
        self,
        target_bias: torch.Tensor,
        constraint_id: str,
    ) -> Tuple[torch.Tensor, float]:
        """将约束应用到目标偏置场

        Returns
        -------
        Tuple[torch.Tensor, float]
            (constrained_bias, applied_strength)
        """
        state = self._active_constraints.get(constraint_id)
        if state is None or not state.is_active or state.constraint_vector is None:
            return target_bias, 0.0

        # 约束应用：在目标偏置场上叠加约束方向的偏置
        constraint_vec = state.constraint_vector
        target_flat = target_bias.flatten()

        min_len = min(len(target_flat), len(constraint_vec))
        if min_len < 1:
            return target_bias, 0.0

        # 投影约束到目标维度
        if len(constraint_vec) > min_len:
            constraint_sub = constraint_vec[:min_len]
        else:
            # 重复约束向量以匹配目标维度
            repeat_times = (min_len + len(constraint_vec) - 1) // len(constraint_vec)
            constraint_sub = constraint_vec.repeat(repeat_times)[:min_len]

        # 计算目标向量对应部分的投影
        target_sub = target_flat[:min_len]
        proj = torch.dot(target_sub, constraint_sub) / (
            torch.norm(target_sub).item() * torch.norm(constraint_sub).item() + 1e-10
        )

        # 约束效果：如果投影为负（方向相反），施加反向偏置
        if proj < 0:
            adjustment = constraint_sub * state.constraint_strength
            # 投影回原维度
            full_adjustment = torch.zeros_like(target_flat)
            full_adjustment[:min_len] = adjustment
            if len(constraint_vec) > min_len:
                full_adjustment[min_len:] = 0.0
            constrained = target_flat + full_adjustment
        else:
            constrained = target_flat

        return constrained.reshape(target_bias.shape), state.constraint_strength

    def get_active_constraints(self) -> List[Dict]:
        """获取活跃约束列表"""
        return [
            {
                'id': cid,
                'source': s.source_level,
                'target': s.target_level,
                'strength': round(s.constraint_strength, 4),
                'steps': s.steps_elapsed,
                'is_active': s.is_active,
            }
            for cid, s in self._active_constraints.items()
            if s.is_active
        ]

    def get_summary(self) -> Dict:
        """获取约束摘要"""
        return {
            'n_active_constraints': len([s for s in self._active_constraints.values() if s.is_active]),
            'total_constraint_strength': sum(
                s.constraint_strength for s in self._active_constraints.values()
            ),
            'constraints': self.get_active_constraints(),
        }


class BottomUpEmergenceEvaluator:
    """低层级向高层级的涌现质量评估

    评估封装机制产生的高层级结构是否具有"存活"质量。
    存活标准：在 ≥ 50 步内保持结构稳定性。

    理论依据：涌现不是瞬间完成的，需要经历一个"存活检验"期。
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_CROSS_SCALE_COUPLING_CONFIG, **(config or {})}
        self.min_stability_steps = cfg['emergence_min_stability_steps']
        self.stability_threshold = cfg['emergence_stability_threshold']
        self.min_odi = cfg['emergence_min_odi']
        self.cooldown_steps = cfg['emergence_cooldown_steps']

        # 追踪每个涌现候选的稳定性
        self._emergence_candidates: Dict[str, Dict] = {}
        self._surviving_emergences: List[str] = []
        self._step_count = 0

    def evaluate(
        self,
        emergence_id: str,
        source_level: str,
        target_level: str,
        stability_score: float,
        odi: float,
        structure_vector: Optional[torch.Tensor] = None,
    ) -> EmergenceQualityResult:
        """评估涌现质量

        Parameters
        ----------
        emergence_id : str
            涌现事件唯一标识
        source_level : str
            来源层级
        target_level : str
            目标层级
        stability_score : float
            结构稳定性得分 [0, 1]
        odi : float
            当前 ODI
        structure_vector : Optional[torch.Tensor]
            结构向量（用于后续稳定性追踪）

        Returns
        -------
        EmergenceQualityResult
        """
        self._step_count += 1

        # 初始化或更新候选
        if emergence_id not in self._emergence_candidates:
            self._emergence_candidates[emergence_id] = {
                'source_level': source_level,
                'target_level': target_level,
                'first_appearance_step': self._step_count,
                'stable_steps': 0,
                'unstable_steps': 0,
                'max_stability': stability_score,
                'structure_vector': structure_vector,
                'odi_at_appearance': odi,
            }

        candidate = self._emergence_candidates[emergence_id]

        # 更新稳定性计数
        if stability_score >= self.stability_threshold:
            candidate['stable_steps'] += 1
        else:
            candidate['unstable_steps'] += 1

        candidate['max_stability'] = max(candidate['max_stability'], stability_score)

        # 计算质量等级
        stability_ratio = candidate['stable_steps'] / max(1, candidate['stable_steps'] + candidate['unstable_steps'])
        odi_score = min(odi / self.min_odi, 1.0)

        # 质量判定
        if stability_ratio >= 0.8 and stability_score >= self.stability_threshold and odi_score >= 0.8:
            quality = EmergenceQuality.STRONG
        elif stability_ratio >= 0.6 and stability_score >= self.stability_threshold * 0.8:
            quality = EmergenceQuality.GOOD
        elif stability_ratio >= 0.4:
            quality = EmergenceQuality.MARGINAL
        else:
            quality = EmergenceQuality.POOR

        # 存活判定
        is_surviving = (
            quality in (EmergenceQuality.GOOD, EmergenceQuality.STRONG)
            and candidate['stable_steps'] >= self.min_stability_steps
        )

        if is_surviving and emergence_id not in self._surviving_emergences:
            self._surviving_emergences.append(emergence_id)

        return EmergenceQualityResult(
            source_level=source_level,
            target_level=target_level,
            quality=quality,
            stability_score=stability_score,
            odi_score=odi_score,
            steps_stable=candidate['stable_steps'],
            is_surviving=is_surviving,
            step=self._step_count,
        )

    def get_surviving_emergences(self) -> List[str]:
        """获取存活的涌现事件列表"""
        return list(self._surviving_emergences)

    def get_candidate_stats(self) -> Dict:
        """获取候选统计"""
        return {
            'n_candidates': len(self._emergence_candidates),
            'n_surviving': len(self._surviving_emergences),
            'survival_rate': (
                len(self._surviving_emergences) / len(self._emergence_candidates)
                if self._emergence_candidates else 0.0
            ),
            'candidates': {
                eid: {
                    'source': c['source_level'],
                    'target': c['target_level'],
                    'stable_steps': c['stable_steps'],
                    'unstable_steps': c['unstable_steps'],
                    'max_stability': round(c['max_stability'], 4),
                    'is_surviving': eid in self._surviving_emergences,
                }
                for eid, c in self._emergence_candidates.items()
            },
        }


class ScaleBridgingNarrator:
    """跨尺度叙事桥梁

    将不同层级的叙事连接为一个连贯的整体：
    - MINI 层级的"小叙事" → INSTITUTIONAL 层级的"制度叙事"
    - INSTITUTIONAL 层级的"制度叙事" → CIVILIZATION 层级的"文明叙事"

    理论依据：叙事递归的三层需要被整合为一个连贯的"自我叙事"。
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_CROSS_SCALE_COUPLING_CONFIG, **(config or {})}
        self.bridge_window = cfg['narrative_bridge_window']
        self.min_coherence = cfg['narrative_min_coherence']
        self.integration_rate = cfg['narrative_integration_rate']

        self._narrative_history: Deque[Dict[str, str]] = deque(maxlen=self.bridge_window)
        self._integration_progress = 0.0
        self._step_count = 0

    def update(
        self,
        mini_narrative: str,
        institutional_narrative: str,
        civilization_narrative: str,
    ) -> ScaleBridgingNarrative:
        """更新跨尺度叙事桥梁

        Parameters
        ----------
        mini_narrative : str
            MINI 层级叙事标签
        institutional_narrative : str
            INSTITUTIONAL 层级叙事标签
        civilization_narrative : str
            CIVILIZATION 层级叙事标签

        Returns
        -------
        ScaleBridgingNarrative
        """
        self._step_count += 1
        self._narrative_history.append({
            'MINI': mini_narrative,
            'INSTITUTIONAL': institutional_narrative,
            'CIVILIZATION': civilization_narrative,
        })

        # 计算叙事相干度
        coherence = self._compute_coherence(
            mini_narrative, institutional_narrative, civilization_narrative,
        )

        # 更新整合进度
        if coherence >= self.min_coherence:
            self._integration_progress = min(1.0, self._integration_progress + self.integration_rate)
        else:
            self._integration_progress = max(0.0, self._integration_progress - self.integration_rate * 0.5)

        return ScaleBridgingNarrative(
            mini_narrative=mini_narrative,
            institutional_narrative=institutional_narrative,
            civilization_narrative=civilization_narrative,
            coherence=coherence,
            is_coherent=coherence >= self.min_coherence,
            integration_progress=self._integration_progress,
            step=self._step_count,
        )

    def _compute_coherence(
        self,
        mini: str,
        institutional: str,
        civilization: str,
    ) -> float:
        """计算三层叙事相干度 [0, 1]

        相干度 = 层级间叙事标签的语义相似度（基于共同词根/前缀）
        """
        def shared_prefix_ratio(a: str, b: str) -> float:
            if not a or not b:
                return 0.0
            # 简单的共同前缀/子串匹配
            a_words = set(a.replace('_', ' ').split())
            b_words = set(b.replace('_', ' ').split())
            if not a_words or not b_words:
                return 0.0
            intersection = len(a_words & b_words)
            union = len(a_words | b_words)
            return intersection / union if union > 0 else 0.0

        # MINI ↔ INSTITUTIONAL
        mini_inst = shared_prefix_ratio(mini, institutional)
        # INSTITUTIONAL ↔ CIVILIZATION
        inst_civ = shared_prefix_ratio(institutional, civilization)
        # MINI ↔ CIVILIZATION（跨层）
        mini_civ = shared_prefix_ratio(mini, civilization) * 0.5  # 跨层权重减半

        # 综合相干度
        coherence = (mini_inst + inst_civ + mini_civ) / 3.0
        return float(np.clip(coherence, 0.0, 1.0))

    def get_integration_status(self) -> Dict:
        """获取整合状态"""
        return {
            'integration_progress': round(self._integration_progress, 4),
            'bridge_window_size': len(self._narrative_history),
            'step': self._step_count,
        }


class CrossScaleCoupling:
    """跨尺度耦合器 — 双向因果的统一编排

    整合四个子组件：
    1. TopDownConstraint — 高层级对低层级的约束
    2. BottomUpEmergenceEvaluator — 涌现质量评估
    3. ScaleBridgingNarrator — 跨尺度叙事桥梁
    4. CrossScaleCoherenceIndex (CSCI) — 跨尺度相干指数

    工作流程：
    1. 收集各层级状态
    2. 计算 Top-Down 约束
    3. 评估 Bottom-Up 涌现质量
    4. 更新跨尺度叙事桥梁
    5. 计算 CSCI

    Phase 5 Track B2 新增：
    - coupling_mode='serial': L0→L1→L2 串行传导
      L2 不再直接读取 L0 聚簇，而是从 L1 的制度输出派生
      理论依据："层级不是权力意义上的高低先行，而是结构生成中的组织分层"（差异论 §2.2）
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_CROSS_SCALE_COUPLING_CONFIG, **(config or {})}
        self.config = cfg

        self.top_down = TopDownConstraint(cfg)
        self.bottom_up = BottomUpEmergenceEvaluator(cfg)
        self.narrator = ScaleBridgingNarrator(cfg)

        # CSCI 计算所需的历史数据
        self._level_stabilities: Deque[Dict[str, float]] = deque(maxlen=100)
        self._narrative_coherence_history: Deque[float] = deque(maxlen=100)
        self._step_count = 0

        # 统计
        self._csci_history: Deque[float] = deque(maxlen=200)

        # Phase 5 Track B2: Serial coupling state
        self.coupling_mode = cfg.get('coupling_mode', 'parallel')
        self._serial_l1_l2_delay = cfg.get('serial_l1_to_l2_delay', 15)
        # Track B2 params (backward compatible):
        self._serial_l1_l2_attenuation = cfg.get('serial_l1_to_l2_attenuation', 0.7)
        self._serial_l1_l2_noise = cfg.get('serial_l1_to_l2_noise', 0.05)
        # Track B3 params:
        self._serial_l1_l2_noise_abs = cfg.get('serial_l1_to_l2_noise_abs', 0.1)
        self._serial_l1_l2_noise_rel = cfg.get('serial_l1_to_l2_noise_rel', 0.3)
        self._serial_l1_l2_odi_factor = cfg.get('serial_l1_to_l2_odi_factor', 0.5)
        self._serial_l2_intrinsic_perturbation_rate = cfg.get('serial_l2_intrinsic_perturbation_rate', 0.02)
        self._serial_l2_intrinsic_perturbation_magnitude = cfg.get('serial_l2_intrinsic_perturbation_magnitude', 0.15)
        self._serial_l2_autonomous_decay = cfg.get('serial_l2_autonomous_decay', 0.98)
        self._serial_l0_to_l1_signal_weight = cfg.get('serial_l0_to_l1_signal_weight', 0.4)

        # L1 state buffer for serial mode: store L1 outputs with timestamps
        # so L2 can read L1's state from (delay) steps ago
        self._l1_state_buffer: Deque[Dict] = deque(maxlen=self._serial_l1_l2_delay + 50)
        # Processed L2 state (computed from L1, not from external input)
        self._last_serial_l2_state: Optional[Dict] = None
        # Track B3: L2 intrinsic state (for autonomous dynamics)
        self._l2_intrinsic_state: Optional[torch.Tensor] = None
        self._l2_intrinsic_step = 0

        # Track B4: Constraint Conduction
        self.constraint_conduction = ConstraintConduction(cfg)
        # Track B5: Independent L2 Coupling
        self.independent_l2 = IndependentL2Coupling(cfg)

    def step(
        self,
        level_states: Dict[str, Dict],
        narrative_labels: Dict[str, str],
        emergence_events: Optional[List[Dict]] = None,
        bias_field: Optional[torch.Tensor] = None,
    ) -> Dict:
        """执行一步跨尺度耦合

        Parameters
        ----------
        level_states : Dict[str, Dict]
            各层级状态 {level_name: {stability_score, odi, structure_vector, ...}}
        narrative_labels : Dict[str, str]
            各层级叙事标签 {level_name: narrative_label}
        emergence_events : Optional[List[Dict]]
            当前步的涌现事件列表 [{emergence_id, source_level, target_level, stability_score, odi, structure_vector}]
        bias_field : Optional[torch.Tensor]
            当前偏置场（用于 Top-Down 约束计算）

        Returns
        -------
        Dict
            跨尺度耦合结果
        """
        self._step_count += 1

        # ── Phase 5 Track B2/B4: Coupling mode dispatch ──
        if self.coupling_mode == 'serial':
            level_states = self._apply_serial_coupling(level_states)
        elif self.coupling_mode == 'constraint':
            level_states = self._apply_constraint_coupling(level_states)
        elif self.coupling_mode == 'independent':
            level_states = self._apply_independent_coupling(level_states)

        # 1. Top-Down 约束
        constraints = self.top_down.update(level_states, bias_field)

        # 2. Bottom-Up 涌现质量评估
        emergence_results = []
        if emergence_events:
            for event in emergence_events:
                result = self.bottom_up.evaluate(
                    emergence_id=event.get('emergence_id', f"emerg_{self._step_count}"),
                    source_level=event.get('source_level', 'MINI'),
                    target_level=event.get('target_level', 'INSTITUTIONAL'),
                    stability_score=event.get('stability_score', 0.0),
                    odi=event.get('odi', 0.0),
                    structure_vector=event.get('structure_vector'),
                )
                emergence_results.append(result)

        # 3. 跨尺度叙事桥梁
        mini_narr = narrative_labels.get('MINI', 'silent')
        inst_narr = narrative_labels.get('INSTITUTIONAL', 'silent')
        civ_narr = narrative_labels.get('CIVILIZATION', 'silent')
        narrative_bridge = self.narrator.update(mini_narr, inst_narr, civ_narr)

        # 4. 记录层级稳定性
        level_stabilities = {
            level: state.get('stability_score', 0.0)
            for level, state in level_states.items()
        }
        self._level_stabilities.append(level_stabilities)

        # 5. 计算 CSCI
        csci_result = self._compute_csci(level_stabilities, narrative_bridge)
        self._csci_history.append(csci_result.csci)
        self._narrative_coherence_history.append(narrative_bridge.coherence)

        return {
            'top_down_constraints': constraints,
            'emergence_results': emergence_results,
            'narrative_bridge': narrative_bridge,
            'csci': csci_result,
            'step': self._step_count,
        }

    def _apply_serial_coupling(self, level_states: Dict[str, Dict]) -> Dict[str, Dict]:
        """Apply serial coupling: derive L2 state from L1, not from external input.

        Theory: "层级不是权力意义上的高低先行，而是结构生成中的组织分层" (差异论 §2.2)
        L2 should be a re-organization of L1's institutional output,
        not a parallel read of L0's clusters.

        Process (Track B3):
        1. Store L1's current state in a buffer with timestamp
        2. Retrieve L1's state from (delay) steps ago
        3. Derive L2 state from that delayed L1 state, with:
           - Stronger attenuation (B3: 0.3 vs B2: 0.7)
           - Combined noise: absolute + relative to L1 signal (B3)
           - L2 autonomous decay (B3)
           - Intrinsic L2 perturbation (B3)
        4. Replace the externally-provided L2 state with this derived state
        """
        # Store L1 state with current step
        l1_state = level_states.get('INSTITUTIONAL', {})
        self._l1_state_buffer.append({
            'step': self._step_count,
            'stability_score': l1_state.get('stability_score', 0.0),
            'odi': l1_state.get('odi', 0.0),
            'structure_vector': l1_state.get('structure_vector'),
        })

        # Retrieve L1 state from (delay) steps ago
        target_step = self._step_count - self._serial_l1_l2_delay
        delayed_l1 = None
        for entry in self._l1_state_buffer:
            if entry['step'] == target_step:
                delayed_l1 = entry
                break

        if delayed_l1 is None:
            # Not enough history yet — L2 remains dormant
            # Use a minimal stability that won't activate TopDown from L2
            derived_l2 = {
                'stability_score': 0.05,
                'odi': 0.0,
                'structure_vector': None,
                'serial_derived': True,
                'serial_source': 'L1_dormant',
            }
        else:
            # ── Track B3: Derive L2 from delayed L1 with enhanced noise + autonomous dynamics ──
            l1_stability = delayed_l1['stability_score']
            l1_odi = delayed_l1['odi']
            l1_vector = delayed_l1['structure_vector']

            # Attenuation: L2 stability < L1 stability (B3: 0.3 vs B2: 0.7)
            l2_stability = l1_stability * self._serial_l1_l2_attenuation

            # Track B3: L2 autonomous decay (simulates civilizational natural dissipation)
            if self._last_serial_l2_state is not None:
                prev_l2_stability = self._last_serial_l2_state.get('stability_score', 0.0)
                # Blend derived stability with decayed previous state
                l2_stability = 0.6 * l2_stability + 0.4 * (prev_l2_stability * self._serial_l2_autonomous_decay)

            # B3: Add noise to L2 stability score (breaks L1-L2 stability correlation)
            # This is the key change: L2 stability is no longer a deterministic function of L1
            l2_stability_noise = np.random.normal(0, 0.25)  # stronger noise for B3
            l2_stability = l2_stability + l2_stability_noise

            # Track B3: Combined noise (absolute + relative to L1 signal)
            if l1_vector is not None and l1_vector.numel() > 0:
                # Relative noise: scales with L1 signal strength
                l1_signal_magnitude = l1_vector.norm().item()
                relative_noise_scale = self._serial_l1_l2_noise_rel * l1_signal_magnitude
                # Combined noise
                noise = torch.randn_like(l1_vector) * (relative_noise_scale + self._serial_l1_l2_noise_abs)
                l2_vector = l1_vector * self._serial_l1_l2_attenuation + noise
                norm = l2_vector.norm().item()
                if norm > 1e-8:
                    l2_vector = l2_vector / norm
            else:
                l2_vector = None

            # Track B3: ODI with extra attenuation factor
            l2_odi = l1_odi * self._serial_l1_l2_attenuation * self._serial_l1_l2_odi_factor

            # Track B3: Intrinsic L2 perturbation (random structural perturbation independent of L1)
            if l2_vector is not None and self._l2_intrinsic_state is not None:
                if np.random.random() < self._serial_l2_intrinsic_perturbation_rate:
                    intrinsic_noise = torch.randn_like(l2_vector) * self._serial_l2_intrinsic_perturbation_magnitude
                    l2_vector = l2_vector + intrinsic_noise
                    norm = l2_vector.norm().item()
                    if norm > 1e-8:
                        l2_vector = l2_vector / norm

            derived_l2 = {
                'stability_score': float(np.clip(l2_stability, 0.0, 1.0)),
                'odi': float(np.clip(l2_odi, 0.0, 1.0)),
                'structure_vector': l2_vector,
                'serial_derived': True,
                'serial_source': 'L1_delayed',
                'serial_delay': self._serial_l1_l2_delay,
                'b3_noise_abs': self._serial_l1_l2_noise_abs,
                'b3_noise_rel': self._serial_l1_l2_noise_rel,
                'b3_intrinsic_perturbed': l2_vector is not None and self._l2_intrinsic_state is not None,
            }

            # Update intrinsic state for next step
            if l2_vector is not None:
                self._l2_intrinsic_state = l2_vector.clone()
                self._l2_intrinsic_step = self._step_count

        self._last_serial_l2_state = derived_l2

        # Replace L2 state in level_states with derived state
        modified_states = dict(level_states)  # shallow copy
        modified_states['CIVILIZATION'] = derived_l2
        return modified_states

    def _apply_constraint_coupling(self, level_states: Dict[str, Dict]) -> Dict[str, Dict]:
        """Apply constraint conduction coupling (Track B4).

        L2 has independent clustering from L0, with L1 providing soft constraints.
        Unlike serial mode (state derivation), constraint mode uses soft boundaries.

        Process:
        1. Extract L0, L1, and L2 autonomous states
        2. Run constraint conduction: L2 = f(L0_direct, L1_constraint_boundary)
        3. Return modified level_states with constrained L2
        """
        l0_state = level_states.get('MINI', {})
        l1_state = level_states.get('INSTITUTIONAL', {})
        l2_auto_state = level_states.get('CIVILIZATION', {})

        # Run constraint conduction
        cc_result = self.constraint_conduction.update(l0_state, l1_state, l2_auto_state)

        # Build constrained L2 state
        constrained_l2 = {
            'stability_score': cc_result.l2_constrained_stability,
            'odi': cc_result.l2_independent_odi,
            'structure_vector': l2_auto_state.get('structure_vector'),
            'constraint_conduction': True,
            'constraint_source': 'L1_soft_boundary',
            'l2_autonomous_stability': cc_result.l2_autonomous_stability,
            'constraint_response_delay': cc_result.constraint_response_delay,
        }

        modified_states = dict(level_states)
        modified_states['CIVILIZATION'] = constrained_l2
        return modified_states

    def _apply_independent_coupling(self, level_states: Dict[str, Dict]) -> Dict[str, Dict]:
        """Apply independent L2 coupling (Track B5).

        L2 has truly independent clustering from L0, with L1 providing soft constraints.
        Key differences from constraint mode:
        1. L2 autonomy is not clamped by L1 — it has a stability floor
        2. L2 ODI is independently computed, not shared
        3. L2 has intrinsic perturbation and decay dynamics

        Process:
        1. Extract L0 and L1 states
        2. Run independent L2 coupling: L2 = f(L0_direct, L1_soft_bias, intrinsic)
        3. Apply stability floor to prevent suppression
        4. Return modified level_states with independent L2
        """
        l0_state = level_states.get('MINI', {})
        l1_state = level_states.get('INSTITUTIONAL', {})

        # Run independent L2 coupling
        l2_result = self.independent_l2.update(l0_state, l1_state)

        # Build independent L2 state
        independent_l2 = {
            'stability_score': l2_result['stability_score'],
            'odi': l2_result['odi'],
            'structure_vector': l2_result['structure_vector'],
            'independent_l2': True,
            'l2_autonomous_stability': l2_result['l2_autonomous_stability'],
            'l1_constraint_bias': l2_result.get('l1_constraint_bias', 0.0),
            'stability_floor': l2_result.get('stability_floor', 0.15),
            'l1_l2_correlation': l2_result.get('l1_l2_correlation'),
            'l0_l2_correlation': l2_result.get('l0_l2_correlation'),
            'constraint_response_delay': l2_result.get('avg_response_delay', 0),
        }

        modified_states = dict(level_states)
        modified_states['CIVILIZATION'] = independent_l2
        return modified_states

    def _compute_csci(
        self,
        level_stabilities: Dict[str, float],
        narrative_bridge: ScaleBridgingNarrative,
    ) -> CrossScaleCoherenceResult:
        """计算跨尺度相干指数

        CSCI = α·层级间相干 + β·叙事方向一致性 + γ·结构稳定性相干
        """
        cfg = self.config

        # 层级间相干（基于稳定性差异）
        levels = ['MINI', 'INSTITUTIONAL', 'CIVILIZATION']
        pairwise = {}
        for i in range(len(levels)):
            for j in range(i + 1, len(levels)):
                l1, l2 = levels[i], levels[j]
                s1 = level_stabilities.get(l1, 0.0)
                s2 = level_stabilities.get(l2, 0.0)
                # 相干度 = 1 - |稳定性差异|
                coherence = 1.0 - abs(s1 - s2)
                pairwise[f"{l1}↔{l2}"] = coherence

        avg_pairwise = np.mean(list(pairwise.values())) if pairwise else 0.0

        # 叙事方向一致性
        narrative_coherence = narrative_bridge.coherence

        # 结构稳定性相干（各层级稳定性的方差倒数）
        stability_values = list(level_stabilities.values())
        if len(stability_values) >= 2:
            stability_std = np.std(stability_values)
            structural_coherence = 1.0 / (1.0 + stability_std)
        else:
            structural_coherence = stability_values[0] if stability_values else 0.0

        # 综合 CSCI
        csci = (
            cfg['csci_alpha'] * avg_pairwise +
            cfg['csci_beta'] * narrative_coherence +
            cfg['csci_gamma'] * structural_coherence
        )

        return CrossScaleCoherenceResult(
            csci=float(np.clip(csci, 0.0, 1.0)),
            pairwise_coherence={k: round(v, 4) for k, v in pairwise.items()},
            narrative_coherence=float(narrative_bridge.coherence),
            structural_coherence=float(structural_coherence),
            level_stabilities={k: round(v, 4) for k, v in level_stabilities.items()},
            step=self._step_count,
            is_coherent=csci > 0.5,
        )

    def get_csci_trend(self) -> Dict:
        """获取 CSCI 趋势"""
        if not self._csci_history:
            return {'mean': 0.0, 'min': 0.0, 'max': 0.0, 'n': 0}

        values = list(self._csci_history)
        return {
            'mean': round(float(np.mean(values)), 4),
            'min': round(float(np.min(values)), 4),
            'max': round(float(np.max(values)), 4),
            'std': round(float(np.std(values)), 4),
            'n': len(values),
            'latest': round(values[-1], 4),
        }

    def get_summary(self) -> Dict:
        """获取跨尺度耦合摘要"""
        summary = {
            'step': self._step_count,
            'top_down': self.top_down.get_summary(),
            'bottom_up': self.bottom_up.get_candidate_stats(),
            'narrative_bridge': self.narrator.get_integration_status(),
            'csci_trend': self.get_csci_trend(),
            'is_coherent': (
                self._csci_history[-1] > 0.5
                if self._csci_history else False
            ),
            'coupling_mode': self.coupling_mode,
        }
        if self.coupling_mode == 'serial':
            summary['serial_l2_state'] = {
                'stability_score': self._last_serial_l2_state.get('stability_score', 0.0) if self._last_serial_l2_state else 0.0,
                'serial_source': self._last_serial_l2_state.get('serial_source', 'none') if self._last_serial_l2_state else 'none',
                'l1_buffer_size': len(self._l1_state_buffer),
            }
        if self.coupling_mode == 'constraint':
            summary['constraint_conduction'] = self.constraint_conduction.get_summary()
        if self.coupling_mode == 'independent':
            summary['independent_l2'] = self.independent_l2.get_summary()
        return summary

    def reset(self):
        """重置所有子组件"""
        self.top_down = TopDownConstraint(self.config)
        self.bottom_up = BottomUpEmergenceEvaluator(self.config)
        self.narrator = ScaleBridgingNarrator(self.config)
        self.constraint_conduction.reset()
        self.independent_l2.reset()
        self._level_stabilities.clear()
        self._narrative_coherence_history.clear()
        self._csci_history.clear()
        self._step_count = 0
        self._l1_state_buffer.clear()
        self._last_serial_l2_state = None
        self._l2_intrinsic_state = None
        self._l2_intrinsic_step = 0
