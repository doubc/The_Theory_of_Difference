"""
对象模型测试
"""

import pytest
from datetime import datetime
from src.models import (
    Point, Segment, Zone, Cycle, Structure, Bundle,
    Direction, ZoneSource, Phase,
    first_diff, log_diff, second_diff, time_gap,
    distance_to_zone, relative_distance_to_zone,
    extrema_dispersion,
)


# ─── Point ─────────────────────────────────────────────────

class TestPoint:
    def test_basic(self):
        p = Point(t=datetime(2024, 1, 1), x=70000.0, idx=10)
        assert p.x == 70000.0
        assert p.idx == 10

    def test_log_x(self):
        import math
        p = Point(t=datetime(2024, 1, 1), x=70000.0)
        assert abs(p.log_x - math.log(70000)) < 1e-10

    def test_log_x_zero(self):
        p = Point(t=datetime(2024, 1, 1), x=0.0)
        assert p.log_x == float("-inf")

    def test_serialization(self):
        p = Point(t=datetime(2024, 1, 15), x=72500.5, idx=42)
        d = p.to_dict()
        p2 = Point.from_dict(d)
        assert p2.t == p.t
        assert p2.x == p.x
        assert p2.idx == p.idx


# ─── Direction ─────────────────────────────────────────────

class TestDirection:
    def test_from_delta(self):
        assert Direction.from_delta(100) == Direction.UP
        assert Direction.from_delta(-50) == Direction.DOWN
        assert Direction.from_delta(0) == Direction.FLAT

    def test_from_delta_eps(self):
        assert Direction.from_delta(1e-10) == Direction.FLAT
        assert Direction.from_delta(1e-8) == Direction.UP


# ─── Segment ───────────────────────────────────────────────

class TestSegment:
    def test_basic(self):
        s = Segment(
            start=Point(t=datetime(2024, 1, 1), x=60000),
            end=Point(t=datetime(2024, 1, 10), x=70000),
        )
        assert s.direction == Direction.UP
        assert s.delta == 10000
        assert s.duration == 9
        assert s.abs_delta == 10000

    def test_log_delta(self):
        import math
        s = Segment(
            start=Point(t=datetime(2024, 1, 1), x=60000),
            end=Point(t=datetime(2024, 1, 10), x=70000),
        )
        expected = math.log(70000) - math.log(60000)
        assert abs(s.log_delta - expected) < 1e-10

    def test_serialization(self):
        s = Segment(
            start=Point(t=datetime(2024, 1, 1), x=60000),
            end=Point(t=datetime(2024, 1, 10), x=70000),
        )
        d = s.to_dict()
        s2 = Segment.from_dict(d)
        assert s2.delta == s.delta
        assert s2.direction == s.direction
        assert s2.duration == s.duration


# ─── Zone ──────────────────────────────────────────────────

class TestZone:
    def test_contains(self):
        z = Zone(price_center=70000, bandwidth=1000)
        assert z.contains(70000)
        assert z.contains(70500)
        assert z.contains(69500)
        assert not z.contains(71500)

    def test_distance(self):
        z = Zone(price_center=70000, bandwidth=1000)
        assert z.distance_to(70000) == 0.0
        assert z.distance_to(72000) == 1000  # 72000 - 71000
        assert z.distance_to(68000) == 1000  # 69000 - 68000

    def test_relative_bandwidth(self):
        z = Zone(price_center=70000, bandwidth=1400)
        assert abs(z.relative_bandwidth - 0.02) < 1e-10

    def test_serialization(self):
        z = Zone(price_center=70000, bandwidth=1000, source=ZoneSource.HIGH_CLUSTER, strength=5.0)
        d = z.to_dict()
        z2 = Zone.from_dict(d)
        assert z2.price_center == z.price_center
        assert z2.source == z.source


# ─── Cycle ─────────────────────────────────────────────────

class TestCycle:
    def _make_cycle(self):
        entry = Segment(
            start=Point(t=datetime(2024, 1, 1), x=60000),
            end=Point(t=datetime(2024, 1, 10), x=70000),
        )
        exit_ = Segment(
            start=Point(t=datetime(2024, 1, 10), x=70000),
            end=Point(t=datetime(2024, 1, 12), x=65000),
        )
        zone = Zone(price_center=70000, bandwidth=1000)
        return Cycle(entry=entry, exit=exit_, zone=zone)

    def test_speed_ratio(self):
        c = self._make_cycle()
        assert c.speed_ratio > 0

    def test_time_ratio(self):
        c = self._make_cycle()
        # entry=9d, exit=2d → time_ratio = 9/2 = 4.5
        assert abs(c.time_ratio - 4.5) < 0.1

    def test_amplitude_ratio(self):
        c = self._make_cycle()
        # entry=10000, exit=5000 → amplitude_ratio = 0.5
        assert abs(c.amplitude_ratio - 0.5) < 0.01


# ─── Structure ─────────────────────────────────────────────

class TestStructure:
    def test_signature(self):
        zone = Zone(price_center=70000, bandwidth=1000)
        entry = Segment(
            start=Point(t=datetime(2024, 1, 1), x=60000),
            end=Point(t=datetime(2024, 1, 10), x=70000),
        )
        exit_ = Segment(
            start=Point(t=datetime(2024, 1, 10), x=70000),
            end=Point(t=datetime(2024, 1, 12), x=65000),
        )
        c = Cycle(entry=entry, exit=exit_, zone=zone)
        st = Structure(zone=zone, cycles=[c])
        sig = st.signature()
        assert "n=1" in sig
        assert "sr=" in sig

    def test_serialization(self):
        zone = Zone(price_center=70000, bandwidth=1000)
        st = Structure(zone=zone, cycles=[], typicality=0.8, label="test")
        d = st.to_dict()
        assert d["label"] == "test"
        assert d["typicality"] == 0.8
        assert "signature" in d


# ─── 关系算子 ──────────────────────────────────────────────

class TestRelations:
    def test_first_diff(self):
        p1 = Point(t=datetime(2024, 1, 1), x=60000)
        p2 = Point(t=datetime(2024, 1, 5), x=70000)
        assert first_diff(p1, p2) == 10000

    def test_log_diff(self):
        import math
        p1 = Point(t=datetime(2024, 1, 1), x=60000)
        p2 = Point(t=datetime(2024, 1, 5), x=70000)
        expected = math.log(70000) - math.log(60000)
        assert abs(log_diff(p1, p2) - expected) < 1e-10

    def test_time_gap(self):
        p1 = Point(t=datetime(2024, 1, 1), x=60000)
        p2 = Point(t=datetime(2024, 1, 10), x=70000)
        assert time_gap(p1, p2) == 9

    def test_extrema_dispersion(self):
        pts = [
            Point(t=datetime(2024, 1, 1), x=70000),
            Point(t=datetime(2024, 1, 5), x=70100),
            Point(t=datetime(2024, 1, 10), x=69900),
        ]
        cv = extrema_dispersion(pts)
        assert 0 < cv < 0.01  # 很聚集
