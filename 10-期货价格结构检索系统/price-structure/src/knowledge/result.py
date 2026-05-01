"""
知识匹配结果 — KnowledgeResult + MatchedRule
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class MatchedRule:
    """单条匹配到的知识规则"""
    id: str = ""
    name: str = ""
    level: str = ""          # "L1" / "L2" / "L3"
    verdict: str = ""        # L1: 判定文本
    invalidate: str = ""     # L2: 失效文本
    wisdom: str = ""         # L3: 市场智慧文本
    confidence: float = 0.0  # 置信度 [0, 1]
    weight_adjust: float = 0.0  # 检索权重调整
    severity: str = ""       # L2: high/medium/low
    action: str = ""         # L2: 建议动作
    source: str = ""         # 知识来源

    @property
    def text(self) -> str:
        """返回主文本"""
        return self.verdict or self.invalidate or self.wisdom or ""

    @property
    def icon(self) -> str:
        if self.level == "L1":
            return "✅"
        elif self.level == "L2":
            return "⚠️" if self.severity == "medium" else "🔴"
        else:
            return "💡"


@dataclass
class KnowledgeResult:
    """知识引擎匹配结果"""
    conditions: list[MatchedRule] = field(default_factory=list)      # L1 判定知识
    invalidations: list[MatchedRule] = field(default_factory=list)   # L2 失效知识
    wisdoms: list[MatchedRule] = field(default_factory=list)         # L3 市场知识

    @property
    def confidence_boost(self) -> float:
        """综合置信度调整（来自 L1 判定知识）"""
        return sum(r.weight_adjust for r in self.conditions)

    @property
    def has_invalidations(self) -> bool:
        """是否有失效警告"""
        return len(self.invalidations) > 0

    @property
    def high_severity_count(self) -> int:
        """高严重度失效规则数"""
        return sum(1 for r in self.invalidations if r.severity == "high")

    @property
    def all_rules(self) -> list[MatchedRule]:
        """所有匹配的规则"""
        return self.conditions + self.invalidations + self.wisdoms

    @property
    def total_matched(self) -> int:
        """匹配规则总数"""
        return len(self.all_rules)

    def summary(self) -> str:
        """生成人可读的知识摘要"""
        parts = []

        if self.conditions:
            parts.append("📋 判定知识：")
            for r in self.conditions:
                parts.append(f"  {r.icon} [{r.id}] {r.verdict}")

        if self.invalidations:
            parts.append("⚠️ 失效警告：")
            for r in self.invalidations:
                parts.append(f"  {r.icon} [{r.id}] {r.invalidate}")

        if self.wisdoms:
            parts.append("💡 市场智慧：")
            for r in self.wisdoms:
                parts.append(f"  {r.icon} [{r.id}] {r.wisdom}")

        if not parts:
            return "无匹配知识"

        return "\n".join(parts)

    def to_dict(self) -> dict:
        """转为字典（用于 UI 展示）"""
        return {
            "conditions": [
                {
                    "id": r.id, "name": r.name, "text": r.text,
                    "confidence": r.confidence, "weight_adjust": r.weight_adjust,
                    "source": r.source,
                }
                for r in self.conditions
            ],
            "invalidations": [
                {
                    "id": r.id, "name": r.name, "text": r.text,
                    "severity": r.severity, "action": r.action,
                    "source": r.source,
                }
                for r in self.invalidations
            ],
            "wisdoms": [
                {
                    "id": r.id, "name": r.name, "text": r.text,
                    "source": r.source,
                }
                for r in self.wisdoms
            ],
            "confidence_boost": self.confidence_boost,
            "total_matched": self.total_matched,
        }
