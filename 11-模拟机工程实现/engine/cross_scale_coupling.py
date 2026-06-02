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
    'serial_l1_to_l2_attenuation': 0.5,       # L1→L2 信号衰减（0.5 = L2 gets half of L1）
    'serial_l1_to_l2_noise': 0.15,            # L1→L2 传导噪声（higher = more independent L2）
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
        self._serial_l1_l2_attenuation = cfg.get('serial_l1_to_l2_attenuation', 0.7)
        self._serial_l1_l2_noise = cfg.get('serial_l1_to_l2_noise', 0.05)

        # L1 state buffer for serial mode: store L1 outputs with timestamps
        # so L2 can read L1's state from (delay) steps ago
        self._l1_state_buffer: Deque[Dict] = deque(maxlen=self._serial_l1_l2_delay + 50)
        # Processed L2 state (computed from L1, not from external input)
        self._last_serial_l2_state: Optional[Dict] = None

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

        # ── Phase 5 Track B2: Serial coupling mode ──
        # In serial mode, CIVILIZATION (L2) state is derived from INSTITUTIONAL (L1)
        # rather than read directly. This breaks the L1-L2 perfect correlation.
        if self.coupling_mode == 'serial':
            level_states = self._apply_serial_coupling(level_states)

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

        Process:
        1. Store L1's current state in a buffer with timestamp
        2. Retrieve L1's state from (delay) steps ago
        3. Derive L2 state from that delayed L1 state, with attenuation and noise
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
            # Derive L2 from delayed L1 with attenuation + noise
            l1_stability = delayed_l1['stability_score']
            l1_odi = delayed_l1['odi']
            l1_vector = delayed_l1['structure_vector']

            # Attenuation: L2 stability < L1 stability (information loss per layer)
            l2_stability = l1_stability * self._serial_l1_l2_attenuation

            # Add noise to structure vector (breaks perfect correlation)
            if l1_vector is not None and l1_vector.numel() > 0:
                noise = torch.randn_like(l1_vector) * self._serial_l1_l2_noise
                l2_vector = l1_vector * self._serial_l1_l2_attenuation + noise
                norm = l2_vector.norm().item()
                if norm > 1e-8:
                    l2_vector = l2_vector / norm
            else:
                l2_vector = None

            # ODI: L2's organizational density is derived from L1's
            l2_odi = l1_odi * self._serial_l1_l2_attenuation * 0.8  # extra reduction for L2

            derived_l2 = {
                'stability_score': float(np.clip(l2_stability, 0.0, 1.0)),
                'odi': float(np.clip(l2_odi, 0.0, 1.0)),
                'structure_vector': l2_vector,
                'serial_derived': True,
                'serial_source': 'L1_delayed',
                'serial_delay': self._serial_l1_l2_delay,
            }

        self._last_serial_l2_state = derived_l2

        # Replace L2 state in level_states with derived state
        modified_states = dict(level_states)  # shallow copy
        modified_states['CIVILIZATION'] = derived_l2
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
        return summary

    def reset(self):
        """重置所有子组件"""
        self.top_down = TopDownConstraint(self.config)
        self.bottom_up = BottomUpEmergenceEvaluator(self.config)
        self.narrator = ScaleBridgingNarrator(self.config)
        self._level_stabilities.clear()
        self._narrative_coherence_history.clear()
        self._csci_history.clear()
        self._step_count = 0
        self._l1_state_buffer.clear()
        self._last_serial_l2_state = None
