"""
学习模块测试
"""

import pytest
import math
from datetime import datetime, timedelta

from src.models import Point, Segment, Zone, Cycle, Structure, ZoneSource
from src.learning.features import extract_features, FEATURE_NAMES
from src.learning.classifier import RuleClassifier, ClassifyResult
from src.learning.embedding import embed, cosine_similarity, euclidean_distance, find_nearest


def _make_struct(
    label: str | None = None,
    speed_ratio: float = 2.0,
    cycle_count: int = 4,
    zone_source: ZoneSource = ZoneSource.HIGH_CLUSTER,
) -> Structure:
    zone = Zone(price_center=70000, bandwidth=1000, source=zone_source, strength=5.0)
    cycles = []
    base = datetime(2024, 1, 1)
    for i in range(cycle_count):
        entry = Segment(
            start=Point(t=base + timedelta(days=i * 10), x=65000),
            end=Point(t=base + timedelta(days=9 + i * 10), x=70000),
        )
        exit_dur = max(1, int(entry.duration / speed_ratio))
        exit_ = Segment(
            start=Point(t=base + timedelta(days=9 + i * 10), x=70000),
            end=Point(t=base + timedelta(days=9 + i * 10 + exit_dur), x=65000),
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


# ─── 特征工程 ──────────────────────────────────────────────

class TestFeatures:
    def test_extract(self):
        s = _make_struct(speed_ratio=2.0, cycle_count=4)
        feats = extract_features(s)
        assert len(feats) == len(FEATURE_NAMES)
        assert feats[0] == 4.0  # cycle_count

    def test_batch(self):
        from src.learning.features import extract_features_batch
        structs = [_make_struct(), _make_struct(speed_ratio=0.5)]
        batch = extract_features_batch(structs)
        assert len(batch) == 2
        assert len(batch[0]) == len(FEATURE_NAMES)


# ─── 分类器 ────────────────────────────────────────────────

class TestClassifier:
    def test_rule_classifier_slow_up(self):
        clf = RuleClassifier()
        s = _make_struct(speed_ratio=2.0)
        result = clf.classify(s)
        assert result.label == "slow_up_fast_down"
        assert result.confidence > 0.5

    def test_rule_classifier_balanced(self):
        clf = RuleClassifier()
        s = _make_struct(speed_ratio=1.0)
        result = clf.classify(s)
        assert result.label == "balanced"

    def test_rule_classifier_fast_up(self):
        clf = RuleClassifier()
        s = _make_struct(speed_ratio=0.4)
        result = clf.classify(s)
        assert result.label == "fast_up_slow_down"


# ─── Embedding ─────────────────────────────────────────────

class TestEmbedding:
    def test_embed_dim(self):
        s = _make_struct()
        v = embed(s)
        assert len(v) == len(FEATURE_NAMES)

    def test_identical_similarity(self):
        s = _make_struct(speed_ratio=2.0)
        v = embed(s)
        assert cosine_similarity(v, v) > 0.999

    def test_cosine_range(self):
        v1 = embed(_make_struct(speed_ratio=2.0))
        v2 = embed(_make_struct(speed_ratio=0.5))
        sim = cosine_similarity(v1, v2)
        assert -1.0 <= sim <= 1.0

    def test_find_nearest(self):
        vecs = [embed(_make_struct(speed_ratio=2.0)),
                embed(_make_struct(speed_ratio=1.0)),
                embed(_make_struct(speed_ratio=0.5))]
        query = embed(_make_struct(speed_ratio=2.1))
        nearest = find_nearest(query, vecs, top_k=2)
        assert len(nearest) == 2
        assert nearest[0][0] == 0  # 最接近 speed_ratio=2.0
