"""
DSL 规则引擎测试
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from src.models import Point, Segment, Zone, Cycle, Structure, ZoneSource
from src.dsl.rule import Rule, load_rules, scan, _cmp


# ─── 约束原语 ──────────────────────────────────────────────

class TestCmp:
    def test_exact(self):
        assert _cmp(1.5, 1.5) is True
        assert _cmp(1.5, 1.6) is False

    def test_range(self):
        assert _cmp(1.0, [0.5, 1.5]) is True
        assert _cmp(2.0, [0.5, 1.5]) is False

    def test_gt(self):
        assert _cmp(2.0, {"gt": 1.5}) is True
        assert _cmp(1.0, {"gt": 1.5}) is False

    def test_between(self):
        assert _cmp(1.0, {"between": [0.5, 1.5]}) is True
        assert _cmp(2.0, {"between": [0.5, 1.5]}) is False

    def test_combined(self):
        assert _cmp(1.2, {"gte": 1.0, "lte": 1.5}) is True
        assert _cmp(0.8, {"gte": 1.0, "lte": 1.5}) is False


# ─── 规则匹配 ──────────────────────────────────────────────

def _make_structure(
    zone_source: ZoneSource = ZoneSource.HIGH_CLUSTER,
    speed_ratio: float = 2.0,
    time_ratio: float = 2.0,
    n_cycles: int = 4,
) -> Structure:
    """构建一个测试用的 Structure"""
    zone = Zone(price_center=70000, bandwidth=1000, source=zone_source, strength=5.0)
    cycles = []
    base = datetime(2024, 1, 1)
    for i in range(n_cycles):
        entry = Segment(
            start=Point(t=base + timedelta(days=i * 10), x=65000),
            end=Point(t=base + timedelta(days=9 + i * 10), x=70000),
        )
        exit_dur = max(1, int(entry.duration / speed_ratio)) if speed_ratio > 0 else 1
        exit_ = Segment(
            start=Point(t=base + timedelta(days=9 + i * 10), x=70000),
            end=Point(t=base + timedelta(days=9 + i * 10 + exit_dur), x=65000),
        )
        cycles.append(Cycle(entry=entry, exit=exit_, zone=zone))

    st = Structure(zone=zone, cycles=cycles)
    st.invariants = {
        "avg_speed_ratio": st.avg_speed_ratio,
        "avg_time_ratio": st.avg_time_ratio,
        "high_cluster_stddev": st.high_cluster_stddev,
        "cycle_count": len(cycles),
    }
    return st


class TestRuleMatch:
    def test_slow_up_fast_down_match(self):
        rule = Rule(
            name="SlowUpFastDown_TopReversal",
            zone_source="high_cluster",
            cycles={"gte": 3},
            speed_ratio={"gt": 1.5},
            time_ratio={"gt": 1.5},
            high_cluster_cv={"lt": 0.02},
        )
        st = _make_structure(speed_ratio=2.0, time_ratio=2.0)
        passed, checks = rule.match(st)
        assert passed is True

    def test_no_match_wrong_zone(self):
        rule = Rule(
            name="Test",
            zone_source="high_cluster",
            cycles={"gte": 3},
        )
        st = _make_structure(zone_source=ZoneSource.LOW_CLUSTER)
        passed, checks = rule.match(st)
        assert passed is False

    def test_no_match_few_cycles(self):
        rule = Rule(
            name="Test",
            zone_source="high_cluster",
            cycles={"gte": 5},
        )
        st = _make_structure(n_cycles=2)
        passed, checks = rule.match(st)
        assert passed is False

    def test_typicality(self):
        rule = Rule(
            name="Test",
            zone_source="high_cluster",
            cycles={"gte": 3},
            speed_ratio={"gt": 1.5},
        )
        st = _make_structure(speed_ratio=2.0)
        passed, checks = rule.match(st)
        typ = rule.typicality_score(checks)
        assert typ == 1.0  # 全部通过


# ─── 规则加载 ──────────────────────────────────────────────

class TestRuleLoader:
    def test_load_default(self):
        rules_path = Path(__file__).parent.parent / "src" / "dsl" / "rules" / "default.yaml"
        rules = load_rules(rules_path)
        assert len(rules) >= 4
        names = [r.name for r in rules]
        assert "SlowUpFastDown_TopReversal" in names
        assert "BalancedConsolidation" in names


# ─── 扫描器 ────────────────────────────────────────────────

class TestScanner:
    def test_scan_matches(self):
        rules_path = Path(__file__).parent.parent / "src" / "dsl" / "rules" / "default.yaml"
        rules = load_rules(rules_path)

        structures = [
            _make_structure(speed_ratio=2.0, time_ratio=2.0, n_cycles=4),  # 应命中 SlowUpFastDown
            _make_structure(speed_ratio=0.5, time_ratio=0.5, n_cycles=4),  # 应命中 FastUpSlowDown
            _make_structure(speed_ratio=1.0, time_ratio=1.0, n_cycles=4),  # 应命中 Balanced
        ]
        matches = scan(structures, rules)
        assert len(matches) == 3
        assert matches[0].structure.label == "SlowUpFastDown_TopReversal"
        assert matches[1].structure.label == "FastUpSlowDown_TopDistribution"
        assert matches[2].structure.label == "BalancedConsolidation"

    def test_scan_no_match(self):
        rules = [Rule(name="Strict", zone_source="high_cluster", cycles={"gte": 100})]
        structures = [_make_structure(n_cycles=2)]
        matches = scan(structures, rules)
        assert len(matches) == 0
