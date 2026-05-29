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
from typing import Dict, List, Optional, Tuple
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
    mechanism: str  # 锚定在哪个机制上
    location: Optional[torch.Tensor] = None  # 空间位置（如有）
    coupling_strength: float = 0.0  # 与对应机制的耦合强度

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
        anchor_threshold: float = 0.3,      # 最小锚定强度
        decay_rate: float = 0.01,            # 每步锚定强度衰减率
        min_retention_steps: int = 10,       # 最小保留步数（防止过快剥离）
    ):
        """
        Args:
            anchor_threshold: 最小锚定强度，低于此值认为锚定无效
            decay_rate: 每步锚定强度衰减率（模拟时间对锚定关系的侵蚀）
            min_retention_steps: 锚定后至少保留的步数，防止瞬时波动导致剥离
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

    def attempt_anchor(
        self,
        payload: HighSemanticPayload,
        available_structures: List[Dict],
        timestamp: int,
    ) -> ReturnFlowEvent:
        """尝试为高语义载荷找到锚点。

        Args:
            payload: 高语义载荷
            available_structures: 可用的低语义结构及其机制强度
                格式: [{
                    'structure_id': int,
                    'mechanisms': {'boundary': float, 'self_sustaining': float, ...}
                }, ...]
            timestamp: 当前时间戳

        Returns:
            ReturnFlowEvent 回流事件
        """
        self._total_anchor_attempts += 1

        # 1. 选择最佳锚点
        best_anchor = self._select_best_anchor(payload, available_structures)

        if best_anchor is None:
            event = ReturnFlowEvent(
                payload=payload,
                anchor=AnchorPoint(structure_id=-1, mechanism="none"),
                timestamp=timestamp,
                success=False,
                reason="无可用锚点",
            )
            self._flow_events.append(event)
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

        for payload_id, (anchor, strength, steps) in list(self._anchored.items()):
            # 衰减
            new_strength = max(0.0, strength - self.decay_rate)
            steps += 1

            # 检查是否需要剥离
            if (new_strength < self.anchor_threshold
                    and steps >= self.min_retention_steps):
                event = ReturnFlowEvent(
                    payload=payload,
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
                self._anchored[payload_id] = (anchor, new_strength, steps)

        for pid in to_remove:
            del self._anchored[pid]

        self._flow_events.extend(events)
        return events

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
        """强制剥离指定载荷（用于调试或外部干预）"""
        if payload_id not in self._anchored:
            return None

        anchor, strength, steps = self._anchored[payload_id]
        event = ReturnFlowEvent(
            payload=HighSemanticPayload(
                payload_id=payload_id,
                content_type="",
                content_vector=torch.tensor([]),
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

    def __repr__(self) -> str:
        if self.passed:
            return f"SemanticFlowFirewall[PASSED] payload={self.payload_id} (checked {self.n_checked} fields)"
        return f"SemanticFlowFirewall[FAILED] payload={self.payload_id} violations: {self.violations}"


class SemanticFirewallGuard:
    """语义防火墙守卫 — 保护低语义层不被高语义词汇污染。

    在回流通道中，高语义内容以向量形式传递，但锚定过程中可能
    产生元数据（payload_id、reason 等），这些元数据需要检查
    是否包含被禁止的高语义词汇。

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

    def check_payload_metadata(
        self,
        payload: HighSemanticPayload,
    ) -> SemanticFlowFirewallResult:
        """检查高语义载荷的元数据是否包含被禁止的词汇。

        检查范围：
          - payload_id
          - content_type
          - 所有字符串字段

        Args:
            payload: 待检查的高语义载荷

        Returns:
            SemanticFlowFirewallResult 检测结果
        """
        violations = []
        n_checked = 0

        # 检查 payload_id
        n_checked += 1
        for term in self.FORBIDDEN_TERMS:
            if term in payload.payload_id.lower():
                violations.append(
                    f"payload_id '{payload.payload_id}' contains forbidden term '{term}'"
                )

        # 检查 content_type（content_type 本身是枚举值，理论上不应有违规，但检查以防万一）
        n_checked += 1
        for term in self.FORBIDDEN_TERMS:
            if term in payload.content_type.lower():
                # content_type 是预定义的枚举值，这里只做记录不报错
                # 因为 'meaning' 等本身就是合法的 content_type
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
        """检查回流事件的 reason 字段是否包含被禁止的词汇。

        Args:
            event: 待检查的回流事件

        Returns:
            SemanticFlowFirewallResult 检测结果
        """
        violations = []
        n_checked = 0

        reason = event.reason
        n_checked += 1
        for term in self.FORBIDDEN_TERMS:
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
        """检查锚定机制名称是否为合法的低语义术语。

        Args:
            mechanism: 机制名称

        Returns:
            True 如果机制名称是合法的，False 否则
        """
        mech_lower = mechanism.lower()
        for term in self.FORBIDDEN_TERMS:
            if term in mech_lower:
                return False
        return True
