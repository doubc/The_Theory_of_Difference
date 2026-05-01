"""
反身性追踪模块 — V1.6 P2 骨架

理论基础（V1.6 Ch14 命题 14.4）：
  方法失效的根本原因，不是市场突然无规律，
  而是方法在被广泛采用后，会逐步压缩支撑它有效的差异。

核心机制：
  1. 规则性能历史追踪：每条规则匹配后，追踪被匹配结构的后续表现
  2. 准确率衰减检测：当准确率衰减超过阈值，标记规则可能已失效
  3. 影响评估：预估系统输出对市场的反身性影响
  4. 叙事递归：规则输出 → 市场参与者采纳 → 市场结构变化 → 规则失效

当前状态：骨架实现，预留接口。
完整实现需要大量样本积累 + 长期运行数据。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json


@dataclass
class RulePerformanceRecord:
    """单条规则的单次匹配记录"""
    rule_name: str                # 规则名称
    match_date: str               # 匹配日期
    symbol: str                   # 品种
    predicted_direction: str      # 预测方向 (up/down/unclear)
    actual_ret_5d: float | None = None   # 实际5日收益
    actual_ret_10d: float | None = None  # 实际10日收益
    actual_ret_20d: float | None = None  # 实际20日收益
    verified: bool = False        # 是否已验证
    verify_date: str = ""         # 验证日期


@dataclass
class RulePerformanceSummary:
    """规则性能汇总"""
    rule_name: str
    total_matches: int = 0
    verified_matches: int = 0
    accuracy_5d: float = 0.0      # 5日方向准确率
    accuracy_10d: float = 0.0
    accuracy_20d: float = 0.0
    recent_accuracy: float = 0.0  # 最近 N 次的准确率
    decay_detected: bool = False  # 是否检测到衰减
    decay_rate: float = 0.0       # 衰减速率
    recommended_weight: float = 1.0  # 建议权重（衰减时降低）
    last_updated: str = ""


@dataclass
class ReflexivityTracker:
    """
    反身性追踪器

    追踪两个层面：
    1. 规则层面：规则的准确率是否在衰减
    2. 系统层面：被系统标记过的品种，后续结构变化是否偏离历史分布
    """
    records: list[RulePerformanceRecord] = field(default_factory=list)
    storage_path: str = "data/reflexivity"

    def add_record(self, record: RulePerformanceRecord) -> None:
        """添加一次规则匹配记录"""
        self.records.append(record)

    def update_outcome(
        self,
        rule_name: str,
        symbol: str,
        match_date: str,
        ret_5d: float | None = None,
        ret_10d: float | None = None,
        ret_20d: float | None = None,
    ) -> None:
        """更新规则匹配后的实际结果"""
        for r in self.records:
            if r.rule_name == rule_name and r.symbol == symbol and r.match_date == match_date:
                r.actual_ret_5d = ret_5d
                r.actual_ret_10d = ret_10d
                r.actual_ret_20d = ret_20d
                r.verified = True
                r.verify_date = datetime.now().strftime("%Y-%m-%d")
                break

    def summarize(self, rule_name: str) -> RulePerformanceSummary:
        """汇总指定规则的性能"""
        records = [r for r in self.records if r.rule_name == rule_name]
        if not records:
            return RulePerformanceSummary(rule_name=rule_name)

        verified = [r for r in records if r.verified]
        total = len(records)

        def _accuracy(horizon: str) -> float:
            valid = [r for r in verified if getattr(r, f"actual_ret_{horizon}") is not None]
            if not valid:
                return 0.0
            correct = 0
            for r in valid:
                actual = getattr(r, f"actual_ret_{horizon}")
                if r.predicted_direction == "up" and actual > 0:
                    correct += 1
                elif r.predicted_direction == "down" and actual < 0:
                    correct += 1
            return correct / len(valid)

        acc_5 = _accuracy("5d")
        acc_10 = _accuracy("10d")
        acc_20 = _accuracy("20d")

        # 最近 N 次的准确率（用于检测衰减）
        recent_n = min(10, len(verified))
        recent_verified = verified[-recent_n:] if recent_n > 0 else []
        recent_acc = 0.0
        if recent_verified:
            correct = sum(
                1 for r in recent_verified
                if (r.predicted_direction == "up" and r.actual_ret_10d and r.actual_ret_10d > 0)
                or (r.predicted_direction == "down" and r.actual_ret_10d and r.actual_ret_10d < 0)
            )
            recent_acc = correct / len(recent_verified)

        # 衰减检测：最近准确率 vs 全局准确率
        decay = False
        decay_rate = 0.0
        if acc_10 > 0 and len(verified) >= 10:
            decay_rate = (acc_10 - recent_acc) / acc_10
            if decay_rate > 0.3:  # 衰减 > 30%
                decay = True

        # 建议权重
        weight = 1.0
        if decay:
            weight = max(0.3, 1.0 - decay_rate)

        return RulePerformanceSummary(
            rule_name=rule_name,
            total_matches=total,
            verified_matches=len(verified),
            accuracy_5d=round(acc_5, 3),
            accuracy_10d=round(acc_10, 3),
            accuracy_20d=round(acc_20, 3),
            recent_accuracy=round(recent_acc, 3),
            decay_detected=decay,
            decay_rate=round(decay_rate, 3),
            recommended_weight=round(weight, 3),
            last_updated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    def save(self) -> None:
        """持久化到磁盘"""
        path = Path(self.storage_path)
        path.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "rule_name": r.rule_name,
                "match_date": r.match_date,
                "symbol": r.symbol,
                "predicted_direction": r.predicted_direction,
                "actual_ret_5d": r.actual_ret_5d,
                "actual_ret_10d": r.actual_ret_10d,
                "actual_ret_20d": r.actual_ret_20d,
                "verified": r.verified,
                "verify_date": r.verify_date,
            }
            for r in self.records
        ]
        with open(path / "records.jsonl", "w") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, storage_path: str = "data/reflexivity") -> ReflexivityTracker:
        """从磁盘加载"""
        path = Path(storage_path) / "records.jsonl"
        tracker = cls(storage_path=storage_path)
        if not path.exists():
            return tracker
        with open(path) as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    tracker.records.append(RulePerformanceRecord(**d))
        return tracker
