"""
相似性检索测试
"""

import pytest
from datetime import datetime

from src.models import Point, Segment, Zone, Cycle, Structure, ZoneSource
from src.retrieval.similarity import (
    geometric_similarity, relational_similarity, family_similarity,
    similarity, INVARIANT_KEYS,
)
from src.retrieval.engine import RetrievalEngine, PosteriorStats
from src.sample.store import SampleStore, Sample


# ─── 测试用 Structure 构造 ─────────────────────────────────

def _make_struct(
    label: str | None = None,
    speed_ratio: float = 2.0,
    time_ratio: float = 2.0,
    cycle_count: int = 4,
    zone_source: ZoneSource = ZoneSource.HIGH_CLUSTER,
) -> Structure:
    zone = Zone(price_center=70000, bandwidth=1000, source=zone_source, strength=5.0)
    cycles = []
    for i in range(cycle_count):
        entry = Segment(
            start=Point(t=datetime(2024, 1, 1), x=65000),
            end=Point(t=datetime(2024, 1, 10), x=70000),
        )
        # 控制 speed_ratio: exit.duration = entry.duration / speed_ratio
        exit_dur = max(1, int(entry.duration / speed_ratio))
        exit_ = Segment(
            start=Point(t=datetime(2024, 1, 10), x=70000),
            end=Point(t=datetime(2024, 1, 10 + exit_dur), x=65000),
        )
        cycles.append(Cycle(entry=entry, exit=exit_, zone=zone))
    st = Structure(zone=zone, cycles=cycles, label=label)
    st.invariants = {
        "avg_speed_ratio": st.avg_speed_ratio,
        "avg_time_ratio": st.avg_time_ratio,
        "high_cluster_stddev": st.high_cluster_stddev,
        "cycle_count": len(cycles),
    }
    return st


# ─── 几何相似 ──────────────────────────────────────────────

class TestGeometricSimilarity:
    def test_identical(self):
        s1 = _make_struct(speed_ratio=2.0, cycle_count=4)
        s2 = _make_struct(speed_ratio=2.0, cycle_count=4)
        g = geometric_similarity(s1, s2)
        assert g > 0.99

    def test_different(self):
        s1 = _make_struct(speed_ratio=2.0, cycle_count=4)
        s2 = _make_struct(speed_ratio=0.5, cycle_count=10)
        g = geometric_similarity(s1, s2)
        assert g < 0.8

    def test_range(self):
        s1 = _make_struct()
        s2 = _make_struct(speed_ratio=1.5)
        g = geometric_similarity(s1, s2)
        assert 0.0 <= g <= 1.0


# ─── 关系相似 ──────────────────────────────────────────────

class TestRelationalSimilarity:
    def test_same_zone_source(self):
        s1 = _make_struct(zone_source=ZoneSource.HIGH_CLUSTER)
        s2 = _make_struct(zone_source=ZoneSource.HIGH_CLUSTER)
        r = relational_similarity(s1, s2)
        assert r > 0.7

    def test_different_zone_source(self):
        s1 = _make_struct(zone_source=ZoneSource.HIGH_CLUSTER)
        s2 = _make_struct(zone_source=ZoneSource.LOW_CLUSTER)
        r = relational_similarity(s1, s2)
        # zone 不一致扣分，但 speed/time 方向一致 → 分数不会太低
        assert r < 0.85


# ─── 族相似 ────────────────────────────────────────────────

class TestFamilySimilarity:
    def test_same_label(self):
        s1 = _make_struct(label="SlowUpFastDown_TopReversal")
        s2 = _make_struct(label="SlowUpFastDown_TopReversal")
        assert family_similarity(s1, s2) == 1.0

    def test_mirror(self):
        s1 = _make_struct(label="SlowUpFastDown_TopReversal")
        s2 = _make_struct(label="SlowDownFastUp_BottomReversal")
        assert family_similarity(s1, s2) == 0.6

    def test_different_label(self):
        s1 = _make_struct(label="SlowUpFastDown_TopReversal")
        s2 = _make_struct(label="BalancedConsolidation")
        assert family_similarity(s1, s2) == 0.0

    def test_no_label(self):
        s1 = _make_struct(zone_source=ZoneSource.HIGH_CLUSTER)
        s2 = _make_struct(zone_source=ZoneSource.HIGH_CLUSTER)
        assert family_similarity(s1, s2) == 0.5


# ─── 综合相似度 ────────────────────────────────────────────

class TestSimilarity:
    def test_identical(self):
        s1 = _make_struct(label="test", speed_ratio=2.0)
        s2 = _make_struct(label="test", speed_ratio=2.0)
        sc = similarity(s1, s2)
        assert sc.total > 0.95
        assert "cycle_count" in sc.matched_invariants

    def test_weights(self):
        s1 = _make_struct()
        s2 = _make_struct(speed_ratio=0.5)
        sc1 = similarity(s1, s2, weights=(1.0, 0.0, 0.0))
        sc2 = similarity(s1, s2, weights=(0.0, 1.0, 0.0))
        # 不同权重应产出不同总分
        assert sc1.total != sc2.total


# ─── 检索引擎 ──────────────────────────────────────────────

class TestRetrievalEngine:
    def test_retrieve(self):
        store = SampleStore("/tmp/test_retrieval.jsonl")
        store.clear()

        # 塞入一些样本
        for i in range(5):
            s = Sample(
                id=f"sample_{i}",
                symbol="CU000",
                t_start=datetime(2024, 1, 1),
                t_end=datetime(2024, 2, 1),
                structure={
                    "zone": {"price_center": 70000 + i * 1000, "bandwidth": 1000,
                             "source": "high_cluster", "strength": 5.0},
                    "invariants": {"avg_speed_ratio": 2.0 + i * 0.1,
                                   "avg_time_ratio": 2.0,
                                   "high_cluster_stddev": 200,
                                   "cycle_count": 4},
                },
                label_type="SlowUpFastDown_TopReversal",
                typicality=0.9,
                forward_outcome={"ret_5d": 0.01 * i, "ret_10d": 0.02 * i,
                                 "ret_20d": 0.03 * i, "max_dd_20d": -0.01,
                                 "max_rise_20d": 0.05},
            )
            store.append(s)

        engine = RetrievalEngine(store)
        query = _make_struct(label="SlowUpFastDown_TopReversal", speed_ratio=2.0)
        result = engine.retrieve(query, top_k=3)

        assert len(result.neighbors) > 0
        assert result.posterior.sample_size > 0
        assert result.neighbors[0].score.total >= result.neighbors[-1].score.total

        store.clear()


# ─── 后验统计 ──────────────────────────────────────────────

class TestPosteriorStats:
    def test_aggregate(self):
        store = SampleStore("/tmp/test_posterior.jsonl")
        store.clear()

        for i in range(3):
            store.append(Sample(
                id=f"p_{i}", symbol="CU000",
                t_start=datetime(2024, 1, 1), t_end=datetime(2024, 2, 1),
                structure={"zone": {"price_center": 70000, "bandwidth": 1000,
                                    "source": "high_cluster", "strength": 5.0},
                           "invariants": {"avg_speed_ratio": 2.0, "avg_time_ratio": 2.0,
                                          "high_cluster_stddev": 200, "cycle_count": 4}},
                label_type="test",
                forward_outcome={"ret_5d": 0.01, "ret_10d": 0.02, "ret_20d": 0.03,
                                 "max_dd_20d": -0.02, "max_rise_20d": 0.05},
            ))

        engine = RetrievalEngine(store)
        query = _make_struct(label="test", speed_ratio=2.0)
        result = engine.retrieve(query, top_k=10)

        assert result.posterior.sample_size == 3
        assert abs(result.posterior.mean_ret_5d - 0.01) < 1e-6
        assert result.posterior.prob_positive_10d == 1.0

        store.clear()
