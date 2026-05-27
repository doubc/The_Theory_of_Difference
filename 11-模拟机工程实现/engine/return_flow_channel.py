"""
engine/return_flow_channel.py — 回流通道 (Return Flow Channel)

Phase 2 P0 组件 #2

职责：管理高语义内容向低语义结构的回流与锚定。

理论依据：
- 《差异论》：高语义世界必须能够回流到低语义层，否则就是空中楼阁
- 《象界》第八章：前主体态是"象→意义"的过渡区
- ABA §4.3：前主体态的回流应受语义防火墙持续约束，防止语义内容过早泄漏

回流通道的设计原则：
1. 不破坏低语义自主性：回流不是高语义对低语义的"控制"，而是"锚定"
2. 保持语义防火墙：回流过程中，低语义层不被高语义词汇污染
3. 可逆性：当高语义内容失去低语义锚定时，应能自动剥离
4. 语义防火墙集成：通过 SemanticFirewallGuard 对载荷内容进行持续审查
"""

import torch
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


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

# ─── 语义防火墙禁止词（与 PreSubjectivityConvergence 一致） ───
_FIREWALL_FORBIDDEN: Set[str] = {
    'identity', 'identity_boundary', 'self_identity',
    'will', 'volition', 'intention', 'desire',
    'recollection', 'reminiscence', 'episodic_memory',
    'self_representation', 'self_model', 'self_aware',
    'evaluation', 'judgment', 'value_judgment',
    'meaning', 'significance', 'purpose', 'teleology',
}

_FIREWALL_ALLOWED: Set[str] = {
    'boundary', 'self_sustaining', 'retention',
    'replication', 'selection', 'function',
}


@dataclass
class SemanticFlowFirewallResult:
    """回流通道语义防火墙检查结果

    扩展 SemanticFirewallResult，增加回流通道特有的检查维度：
    - 载荷内容类型审查（content_type 是否属于高语义类型）
    - 锚点机制审查（mechanism 是否属于低语义层）
    - 复合审查（content_type + mechanism 组合是否安全）
    """
    passed: bool = True
    violations: List[str] = field(default_factory=list)
    n_checked: int = 0
    content_type_checked: str = ''
    mechanism_checked: str = ''

    @property
    def is_clean(self) -> bool:
        return self.passed and len(self.violations) == 0

    def __repr__(self):
        if self.passed:
            return (f"FlowFirewall[PASSED] "
                    f"(content={self.content_type_checked}, "
                    f"mechanism={self.mechanism_checked})")
        return (f"FlowFirewall[FAILED] violations: {self.violations}")


class SemanticFirewallGuard:
    """回流通道语义防火墙守卫

    职责：在回流通道的锚定和持续监测过程中，
    对高语义载荷进行多层审查，防止语义内容过早泄漏到低语义层。

    审查层级：
    1. 内容类型审查：content_type 是否在允许的高语义类型白名单中
    2. 锚点机制审查：mechanism 是否在低语义机制白名单中
    3. 组合审查：content_type + mechanism 的组合是否安全
       （例如：identity 类型不应锚定在 function 机制上）
    4. 向量范数审查：content_vector 的范数是否超过安全阈值
       （防止过强的语义内容一次性注入低语义层）

    理论依据：
    - ABA §4.3：前主体态的回流应受持续约束
    - 《差异论》：回流不是控制，而是锚定——锚定必须受到约束
    - 语义防火墙的目的不是阻止回流，而是确保回流不破坏低语义层的自主性
    """

    # 危险组合：content_type → 不允许锚定的机制
    # 这些组合会导致语义内容"直接注入"错误的机制层
    DANGEROUS_COMBINATIONS: Dict[str, Set[str]] = {
        'identity': {'function'},         # 身份不应仅锚定在功能上
        'meaning': {'boundary'},          # 意义不应锚定在边界上
        'institution': {'replication'},   # 制度不应仅靠复制维持
        'narrative': {'function'},        # 叙事不应仅锚定在功能上
    }

    # 内容向量最大安全范数（超过此值需要分片回流）
    MAX_SAFE_NORM: float = 10.0

    def __init__(self,
                 forbidden_terms: Optional[Set[str]] = None,
                 allowed_mechanisms: Optional[Set[str]] = None,
                 dangerous_combinations: Optional[Dict[str, Set[str]]] = None,
                 max_safe_norm: float = 10.0):
        self._forbidden = forbidden_terms or _FIREWALL_FORBIDDEN
        self._allowed_mechanisms = allowed_mechanisms or _FIREWALL_ALLOWED
        self._dangerous = dangerous_combinations or self.DANGEROUS_COMBINATIONS
        self._max_safe_norm = max_safe_norm

    def check_anchor(self,
                     content_type: str,
                     mechanism: str,
                     content_vector: Optional[torch.Tensor] = None,
                     payload_id: str = '') -> SemanticFlowFirewallResult:
        """对锚定请求进行完整防火墙检查

        Args:
            content_type: 载荷内容类型
            mechanism: 目标锚定机制
            content_vector: 载荷内容向量（可选，用于范数检查）
            payload_id: 载荷ID（用于错误信息）

        Returns:
            SemanticFlowFirewallResult
        """
        violations = []
        n_checked = 0

        # 层1：内容类型白名单检查
        n_checked += 1
        if content_type not in HIGH_SEMANTIC_TYPES:
            violations.append(
                f"Payload '{payload_id}': content_type '{content_type}' "
                f"not in allowed high-semantic types {HIGH_SEMANTIC_TYPES}"
            )

        # 层2：锚点机制白名单检查
        n_checked += 1
        if mechanism not in self._allowed_mechanisms:
            violations.append(
                f"Payload '{payload_id}': mechanism '{mechanism}' "
                f"not in low-semantic mechanisms {self._allowed_mechanisms}"
            )

        # 层3：危险组合检查
        n_checked += 1
        dangerous_mechanisms = self._dangerous.get(content_type, set())
        if mechanism in dangerous_mechanisms:
            violations.append(
                f"Payload '{payload_id}': dangerous combination "
                f"content_type='{content_type}' + mechanism='{mechanism}'"
            )

        # 层4：向量范数检查（如果提供）
        if content_vector is not None:
            n_checked += 1
            norm = float(torch.norm(content_vector))
            if norm > self._max_safe_norm:
                violations.append(
                    f"Payload '{payload_id}': content vector norm {norm:.3f} "
                    f"exceeds safe threshold {self._max_safe_norm}"
                )

        return SemanticFlowFirewallResult(
            passed=len(violations) == 0,
            violations=violations,
            n_checked=n_checked,
            content_type_checked=content_type,
            mechanism_checked=mechanism,
        )

    def check_content_type(self, content_type: str) -> bool:
        """快速检查：content_type 是否属于允许的高语义类型"""
        return content_type in HIGH_SEMANTIC_TYPES

    def check_mechanism(self, mechanism: str) -> bool:
        """快速检查：mechanism 是否属于低语义层"""
        return mechanism in self._allowed_mechanisms

    def get_safe_mechanisms(self, content_type: str) -> Set[str]:
        """获取对给定 content_type 安全的锚定机制集合"""
        dangerous = self._dangerous.get(content_type, set())
        return self._allowed_mechanisms - dangerous

    @property
    def max_safe_norm(self) -> float:
        return self._max_safe_norm

    @property
    def forbidden_terms(self) -> Set[str]:
        return set(self._forbidden)

    @property
    def allowed_mechanisms(self) -> Set[str]:
        return set(self._allowed_mechanisms)


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
        firewall_guard: Optional[SemanticFirewallGuard] = None,
    ):
        """
        Args:
            anchor_threshold: 最小锚定强度，低于此值无法成功锚定
            decay_rate: 每步锚定强度衰减率（模拟高语义内容在低语义层中的自然耗散）
            min_retention_steps: 最小保留步数，防止瞬时波动导致过早剥离
            firewall_guard: 语义防火墙守卫（可选，用于对载荷内容进行持续审查）
        """
        self.anchor_threshold = anchor_threshold
        self.decay_rate = decay_rate
        self.min_retention_steps = min_retention_steps
        self._firewall_guard = firewall_guard

        # 已锚定的内容: payload_id → (anchor, strength, steps_since_anchor)
        # 同时存储 content_type 以便剥离时重建 payload
        self._anchored: Dict[str, tuple] = {}

        # 回流事件历史
        self._flow_events: List[ReturnFlowEvent] = []

        # 防火墙拦截计数
        self._firewall_blocks: int = 0

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

        # 3b. 语义防火墙守卫多层审查（如果已配置）
        if self._firewall_guard is not None:
            fw_result = self._firewall_guard.check_anchor(
                content_type=payload.content_type,
                mechanism=best_anchor.mechanism,
                content_vector=payload.content_vector,
                payload_id=payload.payload_id,
            )
            if not fw_result.passed:
                self._firewall_blocks += 1
                violation_str = "; ".join(fw_result.violations)
                event = ReturnFlowEvent(
                    payload=payload,
                    anchor=best_anchor,
                    timestamp=timestamp,
                    success=False,
                    reason=f"语义防火墙深度审查拦截: {violation_str}",
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

    @property
    def firewall_block_count(self) -> int:
        """获取防火墙拦截次数"""
        return self._firewall_blocks

    @property
    def has_firewall(self) -> bool:
        """是否配置了语义防火墙守卫"""
        return self._firewall_guard is not None

    def get_firewall_guard(self) -> Optional[SemanticFirewallGuard]:
        """获取当前的语义防火墙守卫实例"""
        return self._firewall_guard

    def set_firewall_guard(self, guard: Optional[SemanticFirewallGuard]):
        """设置或移除语义防火墙守卫"""
        self._firewall_guard = guard

    def clear(self):
        """清除所有状态（用于重置或测试）"""
        self._anchored.clear()
        self._flow_events.clear()
        self._firewall_blocks = 0
