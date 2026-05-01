"""
结构样本库 — JSONL 存储

每行一个样本，方便增量追加和流式读取。
样本 = 编译后的结构 + 标签 + 人工备注 + 前向演化结果
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models import Structure


# ─── 前向演化结果 ──────────────────────────────────────────

@dataclass
class ForwardOutcome:
    """结构结束后的 N 日价格表现"""
    ret_5d: float = 0.0
    ret_10d: float = 0.0
    ret_20d: float = 0.0
    max_rise_20d: float = 0.0
    max_dd_20d: float = 0.0
    regime_tag: str = ""


# ─── 样本 ──────────────────────────────────────────────────

@dataclass
class Sample:
    """一个结构样本"""
    id: str
    symbol: str
    t_start: datetime
    t_end: datetime
    structure: dict              # Structure.to_dict()
    label_type: str              # 结构类型（规则名）
    label_phase: str = "formation"
    typicality: float = 0.0
    annotation: str = ""         # 人工备注
    forward_outcome: Optional[dict] = None

    def to_json(self) -> str:
        d = {
            "id": self.id,
            "symbol": self.symbol,
            "t_start": self.t_start.isoformat(),
            "t_end": self.t_end.isoformat(),
            "structure": self.structure,
            "label_type": self.label_type,
            "label_phase": self.label_phase,
            "typicality": self.typicality,
            "annotation": self.annotation,
            "forward_outcome": self.forward_outcome,
        }
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> Sample:
        d = json.loads(line)
        return cls(
            id=d["id"],
            symbol=d["symbol"],
            t_start=datetime.fromisoformat(d["t_start"]),
            t_end=datetime.fromisoformat(d["t_end"]),
            structure=d["structure"],
            label_type=d["label_type"],
            label_phase=d.get("label_phase", "formation"),
            typicality=d.get("typicality", 0.0),
            annotation=d.get("annotation", ""),
            forward_outcome=d.get("forward_outcome"),
        )


# ─── 样本存储 ──────────────────────────────────────────────

class SampleStore:
    """JSONL 样本库"""

    def __init__(self, path: str | Path = "data/samples/library.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, sample: Sample) -> None:
        """追加一个样本"""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(sample.to_json() + "\n")

    def load_all(self) -> list[Sample]:
        """加载全部样本"""
        if not self.path.exists():
            return []
        samples = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(Sample.from_json(line))
        return samples

    def filter(
        self,
        label_type: str | None = None,
        symbol: str | None = None,
        min_typicality: float | None = None,
    ) -> list[Sample]:
        """条件过滤"""
        result = self.load_all()
        if label_type:
            result = [s for s in result if s.label_type == label_type]
        if symbol:
            result = [s for s in result if s.symbol == symbol]
        if min_typicality is not None:
            result = [s for s in result if s.typicality >= min_typicality]
        return result

    def count(self) -> int:
        """样本数量"""
        if not self.path.exists():
            return 0
        with open(self.path, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def clear(self) -> None:
        """清空样本库"""
        if self.path.exists():
            self.path.unlink()

    @staticmethod
    def from_structure(
        s: Structure,
        label_type: str,
        sample_id: str,
        annotation: str = "",
        forward: ForwardOutcome | None = None,
    ) -> Sample:
        """从 Structure 对象创建 Sample"""
        return Sample(
            id=sample_id,
            symbol=s.symbol or "UNKNOWN",
            t_start=s.t_start or datetime.now(),
            t_end=s.t_end or datetime.now(),
            structure=s.to_dict(),
            label_type=label_type,
            label_phase=s.phases[-1].value if s.phases else "formation",
            typicality=s.typicality,
            annotation=annotation,
            forward_outcome=asdict(forward) if forward else None,
        )
