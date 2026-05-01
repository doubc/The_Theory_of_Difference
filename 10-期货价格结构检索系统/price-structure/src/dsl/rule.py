"""
规则引擎 — 基于 YAML 的结构规则定义与匹配

把主观结构翻译成可执行规则：
  文字描述 → YAML → 程序扫出

约束原语支持：
  单值匹配、区间 [lo, hi]、比较 {gt/gte/lt/lte}、{between: [lo, hi]}
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.models import Structure


# ─── 约束原语 ──────────────────────────────────────────────

def _cmp(value: float, spec: Any) -> bool:
    """
    约束比较：
      单值 → value == spec
      [lo, hi] → lo <= value <= hi
      {gt: x} / {gte: x} / {lt: x} / {lte: x}
      {between: [lo, hi]}
    """
    if isinstance(spec, (int, float)):
        return abs(value - spec) < 1e-9
    if isinstance(spec, list) and len(spec) == 2:
        return spec[0] <= value <= spec[1]
    if isinstance(spec, dict):
        if "gt" in spec and not value > spec["gt"]:
            return False
        if "gte" in spec and not value >= spec["gte"]:
            return False
        if "lt" in spec and not value < spec["lt"]:
            return False
        if "lte" in spec and not value <= spec["lte"]:
            return False
        if "between" in spec:
            lo, hi = spec["between"]
            if not (lo <= value <= hi):
                return False
        return True
    return False


# ─── 规则定义 ──────────────────────────────────────────────

@dataclass
class Rule:
    """单条结构规则"""
    name: str
    description: str = ""

    # Zone 约束
    zone_source: str | None = None  # high_cluster / low_cluster

    # 不变量约束
    cycles: Any = None              # e.g. {"gte": 3}
    speed_ratio: Any = None         # e.g. {"gt": 1.5}
    time_ratio: Any = None          # e.g. {"gt": 1.8}
    high_cluster_cv: Any = None     # e.g. {"lt": 0.02}
    high_cluster_stddev: Any = None
    zone_rel_bw: Any = None         # 相对带宽
    zone_strength: Any = None

    def match(self, s: Structure) -> tuple[bool, dict]:
        """
        匹配结构

        返回: (是否全部通过, {约束名: True/False})
        """
        checks: dict[str, bool] = {}

        # Zone 来源
        if self.zone_source is not None:
            checks["zone_source"] = s.zone.source.value == self.zone_source

        # 从 invariants 或属性取值
        inv = s.invariants or {}
        attr_map = {
            "cycles": inv.get("cycle_count", s.cycle_count),
            "speed_ratio": inv.get("avg_speed_ratio", s.avg_speed_ratio),
            "time_ratio": inv.get("avg_time_ratio", s.avg_time_ratio),
            "high_cluster_cv": s.high_cluster_cv,
            "high_cluster_stddev": inv.get("high_cluster_stddev", s.high_cluster_stddev),
            "zone_rel_bw": s.zone.relative_bandwidth,
            "zone_strength": s.zone.strength,
        }

        for key, value in attr_map.items():
            spec = getattr(self, key, None)
            if spec is not None:
                checks[key] = _cmp(value, spec)

        passed = all(checks.values()) if checks else False
        return passed, checks

    def typicality_score(self, checks: dict) -> float:
        """典型度 = 通过的约束比例"""
        if not checks:
            return 0.0
        return sum(1 for v in checks.values() if v) / len(checks)


# ─── 规则加载器 ────────────────────────────────────────────

def load_rules(yaml_path: str | Path) -> list[Rule]:
    """从 YAML 文件加载规则列表"""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    rules = []
    for item in data.get("rules", []):
        rules.append(Rule(**item))
    return rules


# ─── 扫描器 ────────────────────────────────────────────────

@dataclass
class RuleMatch:
    """一条匹配结果"""
    rule: Rule
    structure: Structure
    checks: dict
    typicality: float


def scan(structures: list[Structure], rules: list[Rule]) -> list[RuleMatch]:
    """
    用规则扫描结构列表

    每个结构匹配所有规则，取最高 typicality 的命中。
    """
    matches: list[RuleMatch] = []
    for s in structures:
        best_match: RuleMatch | None = None
        for r in rules:
            passed, checks = r.match(s)
            if passed:
                typ = r.typicality_score(checks)
                candidate = RuleMatch(
                    rule=r, structure=s, checks=checks, typicality=typ,
                )
                if best_match is None or typ > best_match.typicality:
                    best_match = candidate
        if best_match:
            s.label = best_match.rule.name
            s.typicality = best_match.typicality
            matches.append(best_match)
    return matches
