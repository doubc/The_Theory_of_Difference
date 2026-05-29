"""
engine/return_flow_channel.py — 回流通道 (Return Flow Channel)

Phase 2 P0 组件 #2

职责：管理高语义内容向低语义结构的回流与锚定。

理论依据：
- 《差异论》：高语义世界必须能够回流到低语义层，否则就是空中楼阁
- 回流是双向的：低语义→高语义（涌现），高语义→低语义（锚定）
- 回流不是"控制"，而是"锚定" — 高语义内容必须找到低语义结构作为其存在的物质基础

设计文档：docs/phase2_unsealing_return_flow_design.md

核心机制：
  1. 锚定选择：为每个高语义载荷选择最佳的低语义锚点
  2. 耦合验证：验证锚点与载荷的耦合是否足够强
  3. 持续监测：监测已锚定内容的锚定强度衰减
  4. 自动剥离：当锚定强度低于阈值时，自动剥离高语义内容

语义防火墙约束：
  - 回流过程中，低语义层不被高语义词汇污染
  - 高语义内容以向量形式传递，而非文本/概念形式
  - 剥离机制确保高语义内容不会永久污染低语义结构
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import torch
import numpy as np


# =============================================================================
# 数据类定义
# =============================================================================

@dataclass
class HighSemanticPayload:
    """高语义载荷 — 需要回流到低语义层的内容

    内容类型映射（来自解封事件的 reason）：
      - 'meaning':    意义 — 锚定偏好：function > selection > retention > replication
      - 'institution': 制度 — 锚定偏好：boundary > self_sustaining > function > selection
      - 'narrative':  叙事 — 锚定偏好：retention > replication > selection > function
      - 'identity':   身份 — 锚定偏好：boundary > self_sustaining > function
    """
    payload_id: str
    content_type: str  # 'meaning' | 'institution' | 'narrative' | 'identity'
    content_vector: torch.Tensor  # 高语义内容的向量表示
    anchor_strength: float = 0.0  # 初始锚定强度 [0, 1]
    created_at: int = 0  # 时间戳

    def __post_init__(self):
        if self.content_type not in HIGH_SEMANTIC_TYPES:
            raise ValueError(
                f"Invalid content_type '{self.content_type}'. "
                f"Must be one of {HIGH_SEMANTIC_TYPES}"
            )

    def __repr__(self) -> str:
        return (f"HighSemanticPayload[id={self.payload_id}, "
                f"type={self.content_type}, "
                f"vec_shape={list(self.content_vector.shape)}, "
                f"anchor={self.anchor_strength:.3f}]")


@dataclass
class AnchorPoint:
    """锚点 — 高语义内容在低语义结构上的附着位置

    锚定在某个结构的某个机制上，耦合强度表示锚定的牢固程度。
    """
    structure_id: int
    mechanism: Optional[str] = None  # 锚定在哪个机制上（None 表示无可用锚点）
    location: Optional[torch.Tensor] = None  # 空间位置（如有）
    coupling_strength: float = 0.0  # 与对应机制的耦合强度

    def __post_init__(self):
        if self.mechanism is not None and self.mechanism not in LOW_SEMANTIC_MECHANISMS:
            raise ValueError(
                f"Invalid mechanism '{self.mechanism}'. "
                f"Must be one of {LOW_SEMANTIC_MECHANISMS} or None"
            )

    def __repr__(self) -> str:
        return (f"AnchorPoint[struct={self.structure_id}, "
                f"mech={self.mechanism}, "
                f"coupling={self.coupling_strength:.3f}]")


@dataclass
class ReturnFlowEvent:
    """回流事件

    记录一次锚定尝试或剥离事件的结果。
    """
    payload: HighSemanticPayload
    anchor: AnchorPoint
    timestamp: int
    success: bool
    reason: str
    residual_strength: float = 0.0  # 回流/剥离后的剩余锚定强度

    def __repr__(self) -> str:
        status = "ANCHORED" if self.success else "DETACHED"
        return (f"ReturnFlowEvent[{status}] "
                f"payload={self.payload.payload_id} "
                f"→ struct={self.anchor.structure_id}/{self.anchor.mechanism} "
                f"reason={self.reason}")


# =============================================================================
# 语义类型常量 — 供测试和外部模块引用
# =============================================================================

HIGH_SEMANTIC_TYPES = frozenset({'meaning', 'institution', 'narrative', 'identity'})
"""高语义内容类型 — 对应解封事件的 reason 映射"""

LOW_SEMANTIC_MECHANISMS = frozenset({'boundary', 'self_sustaining', 'retention',
                                      'replication', 'selection', 'function'})
"""低语义锚定机制 — 高语义载荷可锚定的低语义结构机制"""

# =============================================================================
# 回流通道
# =============================================================================

class ReturnFlowChannel:
    """回流通道 — 管理高语义内容向低语义结构的回流与锚定。

    核心机制：
      1. 锚定选择：为每个高语义载荷选择最佳的低语义锚点
      2. 耦合验证：验证锚点与载荷的耦合是否足够强
      3. 持续监测：监测已锚定内容的锚定强度衰减
      4. 自动剥离：当锚定强度低于阈值时，自动剥离高语义内容

    理论边界：
      - 回流不是高语义对低语义的"控制"，而是"锚定"
      - 当锚定失效时，高语义内容自动剥离，保证低语义层的自主性
      - 即使在 Level 3 全通道开放后，语义防火墙仍然有效
    """

    # 锚定机制的权重（不同高语义类型偏好不同的锚点）
    # 权重越高，该机制越适合作为该类型内容的锚点
    ANCHOR_WEIGHTS: Dict[str, Dict[str, float]] = {
        'meaning': {
            'function': 0.4, 'selection': 0.3,
            'retention': 0.2, 'replication': 0.1,
        },
        'institution': {
            'boundary': 0.4, 'self_sustaining': 0.3,
            'function': 0.2, 'selection': 0.1,
        },
        'narrative': {
            'retention': 0.4, 'replication': 0.3,
            'selection': 0.2, 'function': 0.1,
        },
        'identity': {
            'boundary': 0.5, 'self_sustaining': 0.3,
            'function': 0.2,
        },
    }

    def __init__(
        self,
        anchor_threshold: float = 0.3,          # 最小锚定强度
        decay_rate: float = 0.01,               # 每步锚定强度衰减率
        min_retention_steps: int = 10,          # 最小保留步数（防止过快剥离）
        firewall_guard: Optional['SemanticFirewallGuard'] = None,  # 语义防火墙守卫
    ):
        """
        Args:
            anchor_threshold: 最小锚定强度，低于此值认为锚定无效
            decay_rate: 每步锚定强度衰减率（模拟时间对锚定关系的侵蚀）
            min_retention_steps: 锚定后至少保留的步数，防止瞬时波动导致剥离
            firewall_guard: 语义防火墙守卫（可选，不提供则不启用防火墙）
        """
        self.anchor_threshold = anchor_threshold
        self.decay_rate = decay_rate
        self.min_retention_steps = min_retention_steps

        # 已锚定的内容: payload_id → (anchor, strength, steps_since_anchor)
        self._anchored: Dict[str, Tuple[AnchorPoint, float, int]] = {}

        # 事件历史
        self._flow_events: List[ReturnFlowEvent] = []

        # 统计
        self._total_anchor_attempts: int = 0
        self._total_successful_anchors: int = 0
        self._total_detachments: int = 0

        # 防火墙
        self._firewall_guard: Optional['SemanticFirewallGuard'] = firewall_guard
        self.firewall_block_count: int = 0

    @property
    def has_firewall(self) -> bool:
        """是否启用了防火墙守卫"""
        return self._firewall_guard is not None

    def set_firewall_guard(self, guard: Optional['SemanticFirewallGuard']) -> None:
        """动态设置或移除防火墙守卫"""
        self._firewall_guard = guard

    def get_firewall_guard(self) -> Optional['SemanticFirewallGuard']:
        """获取当前防火墙守卫"""
        return self._firewall_guard

    def attempt_anchor(
        self,
        payload: HighSemanticPayload,
        available_structures: List[Dict],
        timestamp: int,
        unsealing_levels: Optional[Dict[int, int]] = None,
    ) -> ReturnFlowEvent:
        """尝试为高语义载荷找到锚点。

        Args:
            payload: 高语义载荷
            available_structures: 可用的低语义结构及其机制强度
                格式: [{
                    'structure_id': int,
                    'mechanisms': {'boundary': float, 'self_sustaining': float, ...},
                    'unsealing_level': int,  # 可选，若未提供则从 unsealing_levels 查询
                }, ...]
            timestamp: 当前时间戳
            unsealing_levels: 结构的解封等级映射 {structure_id: level}，可选
                若 structure 未标注 unsealing_level 且此处未提供映射，默认视为 Level 0（封闭）

        Returns:
            ReturnFlowEvent 回流事件
        """
        self._total_anchor_attempts += 1

        # 0. 防火墙预审查（如果启用了守卫）：仅检查内容类型和向量范数
        if self._firewall_guard is not None:
            violations = []
            # 层1：内容类型检查
            if not self._firewall_guard.check_content_type(payload.content_type):
                violations.append(
                    f"content_type '{payload.content_type}' not in allowed high-semantic types {HIGH_SEMANTIC_TYPES}"
                )
            # 层4：向量范数检查
            if payload.content_vector is not None:
                norm_ok, norm_val = self._firewall_guard.check_vector_norm(payload.content_vector)
                if not norm_ok:
                    violations.append(
                        f"vector norm {norm_val:.2f} exceeds max_safe_norm {self._firewall_guard.max_safe_norm}"
                    )
            if violations:
                event = ReturnFlowEvent(
                    payload=payload,
                    anchor=AnchorPoint(structure_id=-1, mechanism=None),
                    timestamp=timestamp,
                    success=False,
                    reason=f"firewall blocked: {'; '.join(violations)}",
                )
                self._flow_events.append(event)
                self.firewall_block_count += 1
                return event

        # 1. 解封等级检查：Level 0（封闭）结构拒绝锚定
        if unsealing_levels is not None:
            for struct in available_structures:
                sid = struct.get("structure_id")
                level = struct.get("unsealing_level", unsealing_levels.get(sid, 0))
                if level == 0:
                    struct["_filtered"] = True

        # 2. 选择最佳锚点（自动跳过已过滤的封闭结构）
        best_anchor = self._select_best_anchor(payload, available_structures)

        if best_anchor is None:
            event = ReturnFlowEvent(
                payload=payload,
                anchor=AnchorPoint(structure_id=-1, mechanism=None),
                timestamp=timestamp,
                success=False,
                reason="无可用锚点",
            )
            self._flow_events.append(event)
            return event

        # 2.1 二次防火墙审查：确定锚点后检查危险组合
        if self._firewall_guard is not None:
            fw_result = self._firewall_guard.check_anchor(
                content_type=payload.content_type,
                mechanism=best_anchor.mechanism,
                content_vector=payload.content_vector,
                payload_id=payload.payload_id,
            )
            if not fw_result.passed:
                event = ReturnFlowEvent(
                    payload=payload,
                    anchor=best_anchor,
                    timestamp=timestamp,
                    success=False,
                    reason=f"firewall blocked: {'; '.join(fw_result.violations)}",
                )
                self._flow_events.append(event)
                self.firewall_block_count += 1
                return event

        # 2. 验证耦合强度
        coupling = best_anchor.coupling_strength
        if coupling < self.anchor_threshold:
            event = ReturnFlowEvent(
                payload=payload,
                anchor=best_anchor,
                timestamp=timestamp,
                success=False,
                reason=f"耦合强度 {coupling:.3f} < 阈值 {self.anchor_threshold:.3f}",
            )
            self._flow_events.append(event)
            return event

        # 3. 成功锚定
        self._anchored[payload.payload_id] = (
            best_anchor,
            payload.anchor_strength if payload.anchor_strength > 0 else coupling,
            0,  # steps_since_anchor
        )
        self._total_successful_anchors += 1

        event = ReturnFlowEvent(
            payload=payload,
            anchor=best_anchor,
            timestamp=timestamp,
            success=True,
            reason=f"锚定在 structure={best_anchor.structure_id}, "
                   f"mechanism={best_anchor.mechanism}, "
                   f"coupling={coupling:.3f}",
            residual_strength=coupling,
        )
        self._flow_events.append(event)
        return event

    def _select_best_anchor(
        self,
        payload: HighSemanticPayload,
        available_structures: List[Dict],
    ) -> Optional[AnchorPoint]:
        """为载荷选择最佳锚点。

        使用内容类型对应的锚定权重，对每个可用结构的每个机制进行评分，
        选择得分最高的锚点。

        评分 = 锚定权重 × 机制强度

        注意：会自动跳过标记为 "_filtered" 的结构（如 Level 0 封闭结构）。
        """
        weights = self.ANCHOR_WEIGHTS.get(payload.content_type, {})
        if not weights:
            return None

        best_anchor = None
        best_score = 0.0

        for struct in available_structures:
            struct_id = struct.get('structure_id')
            mechanisms = struct.get('mechanisms', {})

            for mech_name, weight in weights.items():
                mech_strength = mechanisms.get(mech_name, 0.0)
                score = weight * mech_strength

                if score > best_score:
                    best_score = score
                    best_anchor = AnchorPoint(
                        structure_id=struct_id,
                        mechanism=mech_name,
                        coupling_strength=mech_strength,
                    )

        return best_anchor

    def step(self, timestamp: int) -> List[ReturnFlowEvent]:
        """执行一步回流通道演化。

        功能：
          1. 对所有已锚定内容衰减锚定强度
          2. 检测需要剥离的内容（强度 < 阈值且超过最小保留步数）
          3. 返回剥离事件列表

        Args:
            timestamp: 当前时间戳

        Returns:
            剥离事件列表
        """
        events = []
        to_remove = []

        for payload_id, entry in list(self._anchored.items()):
            # 兼容旧格式 (anchor, strength, steps) 和新格式 (payload, anchor, strength, steps)
            if len(entry) == 3:
                anchor, strength, steps = entry
                # 旧格式没有存储 payload，构造一个占位符
                payload = None
            else:
                payload, anchor, strength, steps = entry
            # 衰减
            new_strength = max(0.0, strength - self.decay_rate)
            steps += 1

            # 检查是否需要剥离
            if (new_strength < self.anchor_threshold
                    and steps >= self.min_retention_steps):
                event = ReturnFlowEvent(
                    payload=payload or HighSemanticPayload(
                        payload_id=payload_id, content_type="meaning",
                        content_vector=torch.zeros(1)),
                    anchor=anchor,
                    timestamp=timestamp,
                    success=False,
                    reason=f"锚定强度衰减至 {new_strength:.3f} < {self.anchor_threshold:.3f} "
                           f"(已锚定 {steps} 步)",
                    residual_strength=new_strength,
                )
                events.append(event)
                to_remove.append(payload_id)
                self._total_detachments += 1
            else:
                self._anchored[payload_id] = (payload, anchor, new_strength, steps)

        for pid in to_remove:
            del self._anchored[pid]

        self._flow_events.extend(events)
        return events

    def clear(self) -> None:
        """清空所有已锚定内容、事件历史和统计计数（含防火墙拦截计数）。"""
        self._anchored.clear()
        self._flow_events.clear()
        self._total_anchor_attempts = 0
        self._total_successful_anchors = 0
        self._total_detachments = 0
        self.firewall_block_count = 0

    # ─── 查询接口 ───

    def get_anchored_contents(self) -> Dict[str, Dict]:
        """获取所有已锚定内容的状态。

        Returns:
            {payload_id: {
                'structure_id': int,
                'mechanism': str,
                'anchor_strength': float,
                'steps_anchored': int,
            }, ...}
        """
        result = {}
        for pid, (anchor, strength, steps) in self._anchored.items():
            result[pid] = {
                'structure_id': anchor.structure_id,
                'mechanism': anchor.mechanism,
                'anchor_strength': strength,
                'steps_anchored': steps,
            }
        return result

    def get_anchored_count(self) -> int:
        """获取当前已锚定内容的数量"""
        return len(self._anchored)

    def get_flow_history(self, limit: int = 100) -> List[ReturnFlowEvent]:
        """获取回流事件历史（最近 N 条）"""
        return self._flow_events[-limit:]

    def get_total_events(self) -> int:
        """获取总事件数"""
        return len(self._flow_events)

    def get_success_rate(self) -> float:
        """获取锚定成功率"""
        if self._total_anchor_attempts == 0:
            return 0.0
        return self._total_successful_anchors / self._total_anchor_attempts

    def get_stats(self) -> Dict:
        """获取统计摘要"""
        anchored = self.get_anchored_contents()
        if anchored:
            strengths = [v['anchor_strength'] for v in anchored.values()]
            avg_strength = float(np.mean(strengths))
            min_strength = float(np.min(strengths))
            max_strength = float(np.max(strengths))
        else:
            avg_strength = min_strength = max_strength = 0.0

        return {
            'anchored_count': len(anchored),
            'total_anchor_attempts': self._total_anchor_attempts,
            'total_successful_anchors': self._total_successful_anchors,
            'total_detachments': self._total_detachments,
            'success_rate': self.get_success_rate(),
            'avg_anchor_strength': avg_strength,
            'min_anchor_strength': min_strength,
            'max_anchor_strength': max_strength,
            'anchor_threshold': self.anchor_threshold,
            'decay_rate': self.decay_rate,
            'min_retention_steps': self.min_retention_steps,
        }

    def get_anchor_by_structure(self, structure_id: int) -> List[Dict]:
        """获取锚定在指定结构上的所有内容"""
        result = []
        for pid, (anchor, strength, steps) in self._anchored.items():
            if anchor.structure_id == structure_id:
                result.append({
                    'payload_id': pid,
                    'mechanism': anchor.mechanism,
                    'anchor_strength': strength,
                    'steps_anchored': steps,
                })
        return result

    def get_anchor_by_mechanism(self, mechanism: str) -> List[Dict]:
        """获取锚定在指定机制上的所有内容"""
        result = []
        for pid, (anchor, strength, steps) in self._anchored.items():
            if anchor.mechanism == mechanism:
                result.append({
                    'payload_id': pid,
                    'structure_id': anchor.structure_id,
                    'anchor_strength': strength,
                    'steps_anchored': steps,
                })
        return result

    def force_detach(self, payload_id: str) -> Optional[ReturnFlowEvent]:
        """强制剥离指定载荷（用于调试或外部干预）

        注意：构造占位 Payload 时使用 'meaning' 作为默认 content_type
        以满足 HighSemanticPayload 的 __post_init__ 校验。
        """
        if payload_id not in self._anchored:
            return None

        anchor, strength, steps = self._anchored[payload_id]
        event = ReturnFlowEvent(
            payload=HighSemanticPayload(
                payload_id=payload_id,
                content_type='meaning',  # 占位类型，满足校验
                content_vector=torch.zeros(1),
            ),
            anchor=anchor,
            timestamp=0,
            success=False,
            reason="强制剥离",
            residual_strength=strength,
        )
        del self._anchored[payload_id]
        self._total_detachments += 1
        self._flow_events.append(event)
        return event

    def reset(self):
        """重置所有状态"""
        self._anchored.clear()
        self._flow_events.clear()
        self._total_anchor_attempts = 0
        self._total_successful_anchors = 0
        self._total_detachments = 0

    def __repr__(self) -> str:
        n_anchored = len(self._anchored)
        rate = self.get_success_rate()
        return (f"ReturnFlowChannel[anchored={n_anchored}, "
                f"success_rate={rate:.1%}, "
                f"events={len(self._flow_events)}]")


# =============================================================================
# 语义防火墙（回流通道专用）
# =============================================================================

@dataclass
class SemanticFlowFirewallResult:
    """语义防火墙检测结果（回流通道专用）

    检查高语义载荷在回流过程中是否污染了低语义层的描述体系。
    """
    passed: bool = True
    violations: List[str] = field(default_factory=list)
    n_checked: int = 0
    payload_id: str = ""
    content_type_checked: str = ""
    mechanism_checked: str = ""

    @property
    def is_clean(self) -> bool:
        """是否通过所有检查（无违规）"""
        return self.passed and len(self.violations) == 0

    def __repr__(self) -> str:
        if self.passed:
            return (f"SemanticFlowFirewall[PASSED] payload={self.payload_id} "
                    f"(checked {self.n_checked} fields"
                    f"{f', content_type={self.content_type_checked}' if self.content_type_checked else ''}"
                    f"{f', mechanism={self.mechanism_checked}' if self.mechanism_checked else ''})")
        return f"SemanticFlowFirewall[FAILED] payload={self.payload_id} violations: {self.violations}"


class SemanticFirewallGuard:
    """语义防火墙守卫 — 保护低语义层不被高语义词汇污染。

    四层审查：
      1. 内容类型白名单检查（content_type 是否在 HIGH_SEMANTIC_TYPES 中）
      2. 锚点机制白名单检查（mechanism 是否在 LOW_SEMANTIC_MECHANISMS 中）
      3. 危险组合检查（如 identity+function, meaning+boundary 等）
      4. 向量范数检查（防止过强的语义内容一次性注入低语义层）

    理论依据：
      - 前主体态阶段，低语义层必须保持语义纯净
      - 高语义内容以向量形式存在，不应以文本/概念形式渗入
      - 即使 Level 3 全通道开放，语义防火墙仍然有效
    """

    # 被禁止的高语义词汇（与 pre_subjectivity_convergence 保持一致）
    FORBIDDEN_TERMS = {
        'identity', 'identity_boundary', 'self_identity',
        'will', 'volition', 'intention', 'desire',
        'recollection', 'reminiscence', 'episodic_memory',
        'self_representation', 'self_model', 'self_aware',
        'evaluation', 'judgment', 'value_judgment',
        'meaning', 'significance', 'purpose', 'teleology',
    }

    # 允许的结构对应词（低语义层合法术语）
    ALLOWED_TERMS = {
        'boundary', 'self_sustaining', 'retention',
        'replication', 'selection', 'function',
        'interface', 'coupling', 'stability', 'density',
        'anchor', 'payload', 'structure', 'mechanism',
    }

    # 危险组合：(content_type, mechanism) 对，禁止锚定
    DEFAULT_DANGEROUS_COMBINATIONS = {
        ('identity', 'function'),
        ('meaning', 'boundary'),
        ('institution', 'replication'),
        ('narrative', 'function'),
    }

    def __init__(
        self,
        max_safe_norm: float = 10.0,
        forbidden_terms: Optional[Set[str]] = None,
        allowed_mechanisms: Optional[Set[str]] = None,
        dangerous_combinations: Optional[Set[Tuple[str, str]]] = None,
    ):
        """
        Args:
            max_safe_norm: 内容向量的最大安全范数，超过则拦截
            forbidden_terms: 被禁止的术语集合（默认使用 FORBIDDEN_TERMS）
            allowed_mechanisms: 允许的低语义机制集合（默认使用 LOW_SEMANTIC_MECHANISMS）
            dangerous_combinations: 危险的内容类型+机制组合（默认使用 DEFAULT_DANGEROUS_COMBINATIONS）
        """
        self.max_safe_norm = max_safe_norm
        self.forbidden_terms = forbidden_terms if forbidden_terms is not None else self.FORBIDDEN_TERMS
        self.allowed_mechanisms = allowed_mechanisms if allowed_mechanisms is not None else set(LOW_SEMANTIC_MECHANISMS)
        self.dangerous_combinations = (
            dangerous_combinations if dangerous_combinations is not None
            else self.DEFAULT_DANGEROUS_COMBINATIONS
        )

    # ─── 四层审查方法 ───

    def check_content_type(self, content_type: str) -> bool:
        """层1：检查内容类型是否在允许的高语义类型集合中。"""
        return content_type in HIGH_SEMANTIC_TYPES

    def check_mechanism(self, mechanism: str) -> bool:
        """层2：检查锚点机制是否在允许的低语义机制集合中。"""
        return mechanism in self.allowed_mechanisms

    def check_dangerous_combination(self, content_type: str, mechanism: str) -> bool:
        """层3：检查内容类型+机制组合是否为危险组合。
        支持两种格式：set of tuples 或 dict of sets。"""
        if isinstance(self.dangerous_combinations, dict):
            return mechanism not in self.dangerous_combinations.get(content_type, set())
        return (content_type, mechanism) not in self.dangerous_combinations

    def check_vector_norm(self, content_vector: Optional[torch.Tensor]) -> Tuple[bool, float]:
        """层4：检查内容向量的范数是否超过安全阈值。

        Returns:
            (passed, norm_value)
        """
        if content_vector is None:
            return True, 0.0
        norm = float(torch.norm(content_vector).item())
        return norm <= self.max_safe_norm, norm

    def check_anchor(
        self,
        content_type: str,
        mechanism: str,
        content_vector: Optional[torch.Tensor] = None,
        payload_id: str = "",
    ) -> SemanticFlowFirewallResult:
        """执行完整的四层防火墙审查。

        Args:
            content_type: 高语义内容类型
            mechanism: 低语义锚点机制
            content_vector: 内容向量（可选，若不提供则跳过层4）
            payload_id: 载荷 ID（用于结果报告）

        Returns:
            SemanticFlowFirewallResult 检查结果
        """
        violations = []
        n_checked = 0

        # 层1：内容类型检查
        n_checked += 1
        if not self.check_content_type(content_type):
            violations.append(
                f"content_type '{content_type}' not in allowed high-semantic types {HIGH_SEMANTIC_TYPES}"
            )

        # 层2：机制检查
        n_checked += 1
        if not self.check_mechanism(mechanism):
            violations.append(
                f"mechanism '{mechanism}' not in low-semantic mechanisms {self.allowed_mechanisms}"
            )

        # 层3：危险组合检查（仅当层1和层2都通过时才检查）
        if self.check_content_type(content_type) and self.check_mechanism(mechanism):
            n_checked += 1
            if not self.check_dangerous_combination(content_type, mechanism):
                violations.append(
                    f"dangerous combination: '{content_type}' + '{mechanism}' is prohibited"
                )

        # 层4：向量范数检查
        if content_vector is not None:
            n_checked += 1
            norm_ok, norm_val = self.check_vector_norm(content_vector)
            if not norm_ok:
                violations.append(
                    f"vector norm {norm_val:.2f} exceeds max_safe_norm {self.max_safe_norm}"
                )

        return SemanticFlowFirewallResult(
            passed=len(violations) == 0,
            violations=violations,
            n_checked=n_checked,
            payload_id=payload_id,
            content_type_checked=content_type,
            mechanism_checked=mechanism,
        )

    def get_safe_mechanisms(self, content_type: str) -> Set[str]:
        """获取对给定内容类型安全的机制集合（排除危险组合）。"""
        safe = set(self.allowed_mechanisms)
        for ct, mech in self.dangerous_combinations:
            if ct == content_type:
                safe.discard(mech)
        return safe

    # ─── 元数据检查（保留向后兼容） ───

    def check_payload_metadata(
        self,
        payload: HighSemanticPayload,
    ) -> SemanticFlowFirewallResult:
        """检查高语义载荷的元数据是否包含被禁止的词汇。"""
        violations = []
        n_checked = 0

        n_checked += 1
        for term in self.forbidden_terms:
            if term in payload.payload_id.lower():
                violations.append(
                    f"payload_id '{payload.payload_id}' contains forbidden term '{term}'"
                )

        n_checked += 1
        for term in self.forbidden_terms:
            if term in payload.content_type.lower():
                pass

        return SemanticFlowFirewallResult(
            passed=len(violations) == 0,
            violations=violations,
            n_checked=n_checked,
            payload_id=payload.payload_id,
        )

    def check_event_reason(
        self,
        event: ReturnFlowEvent,
    ) -> SemanticFlowFirewallResult:
        """检查回流事件的 reason 字段是否包含被禁止的词汇。"""
        violations = []
        n_checked = 0

        reason = event.reason
        n_checked += 1
        for term in self.forbidden_terms:
            if term in reason.lower():
                violations.append(
                    f"event reason '{reason}' contains forbidden term '{term}'"
                )

        return SemanticFlowFirewallResult(
            passed=len(violations) == 0,
            violations=violations,
            n_checked=n_checked,
            payload_id=event.payload.payload_id,
        )

    def check_anchor_mechanism(
        self,
        mechanism: str,
    ) -> bool:
        """检查锚定机制名称是否为合法的低语义术语。"""
        return self.check_mechanism(mechanism)
