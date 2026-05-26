"""
engine/return_flow_channel.py — 回流通道 (Return Flow Channel)

Phase 2 P0 组件 #2

职责：管理高语义内容向低语义结构的回流与锚定。

理论依据：
- 《差异论》：高语义世界必须能够回流到低语义层，否则就是空中楼阁
- 《象界》第八章：前主体态是"象→意义"的过渡区

回流通道的设计原则：
1. 不破坏低语义自主性：回流不是高语义对低语义的"控制"，而是"锚定"
2. 保持语义防火墙：回流过程中，低语义层不被高语义词汇污染
3. 可逆性：当高语义内容失去低语义锚定时，应能自动剥离
"""

import torch
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ─── 语义防火墙常量 ───
# 回流通道中的高语义内容类型
HIGH_SEMANTIC_TYPES = {'meaning', 'institution', 'narrative', 'identity'}

# 低语义锚定机制名称（与六机制对应）
LOW_SEMANTIC_MECHANISMS = {
    'boundary',
    'self_sustaining',
    'retention',
    'replication',
    'selection',
    'function',
}


@dataclass
class HighSemanticPayload:
    """高语义载荷 — 需要回流到低语义层的内容"""
    payload_id: str
    content_type: str  # 'meaning' | 'institution' | 'narrative' | 'identity'
    content_vector: torch.Tensor  # 高语义内容的向量表示
    anchor_strength: float = 0.0  # 当前锚定强度 [0, 1]
    created_at: int = 0  # 时间戳

    def __post_init__(self):
        if self.content_type not in HIGH_SEMANTIC_TYPES:
            raise ValueError(
                f"Invalid content_type '{self.content_type}'. "
                f"Must be one of {HIGH_SEMANTIC_TYPES}"
            )


@dataclass
class AnchorPoint:
    """锚点 — 高语义内容在低语义结构上的附着位置"""
    structure_id: int
    mechanism: str  # 锚定在哪个机制上
    location: Optional[torch.Tensor] = None  # 空间位置（如有）
    coupling_strength: float = 0.0  # 与对应机制的耦合强度

    def __post_init__(self):
        # Allow empty string for error/placeholder anchors
        if self.mechanism and self.mechanism not in LOW_SEMANTIC_MECHANISMS:
            raise ValueError(
                f"Invalid mechanism '{self.mechanism}'. "
                f"Must be one of {LOW_SEMANTIC_MECHANISMS} or empty for error cases"
            )


@dataclass
class ReturnFlowEvent:
    """回流事件"""
    payload: HighSemanticPayload
    anchor: AnchorPoint
    timestamp: int
    success: bool
    reason: str
    residual_strength: float = 0.0  # 回流后的剩余锚定强度

    def __repr__(self):
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"ReturnFlowEvent[{status}] payload={self.payload.payload_id} "
            f"type={self.payload.content_type} "
            f"anchor=struct#{self.anchor.structure_id}/{self.anchor.mechanism} "
            f"strength={self.residual_strength:.3f} — {self.reason}"
        )


class ReturnFlowChannel:
    """
    回流通道 — 管理高语义内容向低语义结构的回流与锚定。

    核心机制：
      1. 锚定选择：为每个高语义载荷选择最佳的低语义锚点
      2. 耦合验证：验证锚点与载荷的耦合是否足够强
      3. 持续监测：监测已锚定内容的锚定强度衰减
      4. 自动剥离：当锚定强度低于阈值时，自动剥离高语义内容

    理论立场：
      - 回流不是控制，而是锚定。高语义内容必须找到低语义结构
        作为其存在的物质基础。
      - 剥离是自动的，不需要外部干预。当锚定失效时，高语义内容
        自然脱落，这保证了低语义层的自主性。
    """

    # 锚定机制的权重（不同高语义类型偏好不同的锚点）
    # 这些权重反映了《差异论》中不同类型高语义内容对低语义机制的依赖关系
    ANCHOR_WEIGHTS: Dict[str, Dict[str, float]] = {
        'meaning': {
            'function': 0.4,      # 意义主要锚定在功能机制上
            'selection': 0.3,     # 其次是筛选（选择）
            'retention': 0.2,     # 再次是保持（记忆）
            'replication': 0.1,   # 最后是复制
        },
        'institution': {
            'boundary': 0.4,          # 制度主要锚定在边界上
            'self_sustaining': 0.3,   # 其次是自维持
            'function': 0.2,          # 再次是功能
            'selection': 0.1,         # 最后是筛选
        },
        'narrative': {
            'retention': 0.4,     # 叙事主要锚定在保持（记忆）上
            'replication': 0.3,   # 其次是复制
            'selection': 0.2,     # 再次是筛选
            'function': 0.1,      # 最后是功能
        },
        'identity': {
            'boundary': 0.5,          # 身份（边界）主要锚定在边界上
            'self_sustaining': 0.3,   # 其次是自维持
            'function': 0.2,          # 再次是功能
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
            anchor_threshold: 最小锚定强度，低于此值无法成功锚定
            decay_rate: 每步锚定强度衰减率（模拟高语义内容在低语义层中的自然耗散）
            min_retention_steps: 最小保留步数，防止瞬时波动导致过早剥离
        """
        self.anchor_threshold = anchor_threshold
        self.decay_rate = decay_rate
        self.min_retention_steps = min_retention_steps

        # 已锚定的内容: payload_id → (anchor, strength, steps_since_anchor)
        # 同时存储 content_type 以便剥离时重建 payload
        self._anchored: Dict[str, tuple] = {}

        # 回流事件历史
        self._flow_events: List[ReturnFlowEvent] = []

    def attempt_anchor(
        self,
        payload: HighSemanticPayload,
        available_structures: List[Dict],
        timestamp: int,
    ) -> ReturnFlowEvent:
        """
        尝试为高语义载荷找到锚点。

        Args:
            payload: 高语义载荷
            available_structures: 可用的低语义结构及其机制强度
                格式: [{
                    'structure_id': int,
                    'mechanisms': {'boundary': 0.8, 'self_sustaining': 0.6, ...}
                }]
            timestamp: 当前时间戳

        Returns:
            ReturnFlowEvent 回流事件
        """
        # 1. 选择最佳锚点
        best_anchor = self._select_best_anchor(payload, available_structures)

        if best_anchor is None:
            event = ReturnFlowEvent(
                payload=payload,
                anchor=AnchorPoint(structure_id=-1, mechanism=""),
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
                reason=f"耦合强度 {coupling:.3f} < 阈值 {self.anchor_threshold}",
            )
            self._flow_events.append(event)
            return event

        # 3. 语义防火墙检查：确保锚点机制属于低语义层
        if best_anchor.mechanism not in LOW_SEMANTIC_MECHANISMS:
            event = ReturnFlowEvent(
                payload=payload,
                anchor=best_anchor,
                timestamp=timestamp,
                success=False,
                reason=f"语义防火墙拦截：机制 '{best_anchor.mechanism}' 不属于低语义层",
            )
            self._flow_events.append(event)
            return event

        # 4. 成功锚定
        self._anchored[payload.payload_id] = (
            best_anchor,
            coupling,
            0,  # steps_since_anchor
            payload.content_type,  # 保存类型以便剥离时重建
            payload.content_vector,  # 保存向量
        )

        event = ReturnFlowEvent(
            payload=payload,
            anchor=best_anchor,
            timestamp=timestamp,
            success=True,
            reason=f"锚定在 structure={best_anchor.structure_id}, "
                   f"mechanism={best_anchor.mechanism}",
            residual_strength=coupling,
        )
        self._flow_events.append(event)
        return event

    def _select_best_anchor(
        self,
        payload: HighSemanticPayload,
        available_structures: List[Dict],
    ) -> Optional[AnchorPoint]:
        """为载荷选择最佳锚点"""
        weights = self.ANCHOR_WEIGHTS.get(payload.content_type, {})
        if not weights:
            return None

        best_anchor = None
        best_score = 0.0

        for struct in available_structures:
            struct_id = struct.get('structure_id')
            mechanisms = struct.get('mechanisms', {})

            for mech_name, mech_weight in weights.items():
                mech_strength = mechanisms.get(mech_name, 0.0)
                score = mech_weight * mech_strength

                if score > best_score:
                    best_score = score
                    best_anchor = AnchorPoint(
                        structure_id=struct_id,
                        mechanism=mech_name,
                        coupling_strength=mech_strength,
                    )

        return best_anchor

    def step(self, timestamp: int) -> List[ReturnFlowEvent]:
        """
        执行一步回流通道演化。

        功能：
          1. 对所有已锚定内容衰减锚定强度
          2. 检测需要剥离的内容（强度 < 阈值且超过最小保留步数）
          3. 返回剥离事件列表

        理论含义：
          锚定强度的衰减模拟了高语义内容在低语义层中的自然耗散。
          当锚定强度低于阈值时，说明该高语义内容已经失去了其
          在低语义层的物质基础，应当自动剥离。
        """
        events = []
        to_remove = []

        for payload_id, (anchor, strength, steps, content_type, content_vector) in list(self._anchored.items()):
            # 衰减
            new_strength = max(0.0, strength - self.decay_rate)
            steps += 1

            # 检查是否需要剥离
            if (new_strength < self.anchor_threshold
                    and steps >= self.min_retention_steps):
                payload = HighSemanticPayload(
                    payload_id=payload_id,
                    content_type=content_type,
                    content_vector=content_vector,
                    anchor_strength=new_strength,
                )
                event = ReturnFlowEvent(
                    payload=payload,
                    anchor=anchor,
                    timestamp=timestamp,
                    success=False,
                    reason=f"锚定强度衰减至 {new_strength:.3f} < {self.anchor_threshold}",
                    residual_strength=new_strength,
                )
                events.append(event)
                to_remove.append(payload_id)
            else:
                self._anchored[payload_id] = (
                    anchor, new_strength, steps, content_type, content_vector
                )

        for pid in to_remove:
            del self._anchored[pid]

        self._flow_events.extend(events)
        return events

    def get_anchored_contents(self) -> Dict[str, Dict]:
        """获取所有已锚定内容的状态"""
        result = {}
        for pid, (anchor, strength, steps, content_type, content_vector) in self._anchored.items():
            result[pid] = {
                'structure_id': anchor.structure_id,
                'mechanism': anchor.mechanism,
                'anchor_strength': strength,
                'steps_anchored': steps,
                'content_type': content_type,
            }
        return result

    def get_flow_history(self, limit: int = 100) -> List[ReturnFlowEvent]:
        """获取回流事件历史（最近 N 条）"""
        return self._flow_events[-limit:]

    def get_anchored_count(self) -> int:
        """获取当前已锚定内容的数量"""
        return len(self._anchored)

    def get_total_events(self) -> int:
        """获取总事件数"""
        return len(self._flow_events)

    def get_success_rate(self) -> float:
        """获取锚定成功率"""
        if not self._flow_events:
            return 0.0
        successes = sum(1 for e in self._flow_events if e.success)
        return successes / len(self._flow_events)

    def clear(self):
        """清除所有状态（用于重置或测试）"""
        self._anchored.clear()
        self._flow_events.clear()
