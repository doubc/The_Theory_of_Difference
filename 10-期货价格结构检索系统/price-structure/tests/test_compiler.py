"""
编译器测试 — 用铜连续合约数据做端到端验证
"""

import pytest
from pathlib import Path
from src.data.loader import CSVLoader, load_cu0
from src.compiler.pipeline import compile_full, CompilerConfig
from src.compiler.pivots import extract_pivots
from src.compiler.segments import build_segments
from src.compiler.zones import detect_zones
from src.compiler.cycles import build_cycles, assemble_structures
from src.compiler.bundles import detect_bundles


DATA_DIR = str(Path(__file__).parent.parent / "data")


@pytest.fixture
def loader():
    return load_cu0(DATA_DIR, dedup=True)


@pytest.fixture
def all_bars(loader):
    return loader.get()


@pytest.fixture
def recent_bars(loader):
    return loader.get(start="2024-01-01", end="2026-04-20")


@pytest.fixture
def config():
    return CompilerConfig(
        min_amplitude=0.03,
        min_duration=3,
        noise_filter=0.008,
        zone_bandwidth=0.015,
        cluster_eps=0.02,
        cluster_min_points=2,
        min_cycles=2,
        tolerance=0.03,
    )


# ─── 数据层 ────────────────────────────────────────────────

class TestDataLoader:
    def test_load_cu0(self, loader):
        bars = loader.bars
        assert len(bars) == 5178

    def test_date_range(self, loader):
        assert loader.bars[0].timestamp.year == 2005
        assert loader.bars[-1].timestamp.year == 2026

    def test_price_range(self, loader):
        summary = loader.summary()
        assert summary["price_range"][0] > 20000
        assert summary["price_range"][1] > 100000

    def test_get_window(self, loader):
        bars = loader.get(start="2024-01-01", end="2024-12-31")
        assert len(bars) > 200
        assert bars[0].timestamp.year == 2024


# ─── 极值提取 ──────────────────────────────────────────────

class TestPivots:
    def test_extract_basic(self, recent_bars, config):
        pivots = extract_pivots(
            recent_bars,
            min_amplitude=config.min_amplitude,
            min_duration=config.min_duration,
            noise_filter=config.noise_filter,
        )
        assert len(pivots) > 10
        # 极值点应交替高低
        for i in range(1, len(pivots)):
            assert pivots[i].x != pivots[i - 1].x

    def test_empty_input(self, config):
        pivots = extract_pivots([], min_amplitude=0.03, min_duration=3, noise_filter=0.008)
        assert pivots == []


# ─── 段生成 ────────────────────────────────────────────────

class TestSegments:
    def test_build(self, recent_bars, config):
        pivots = extract_pivots(
            recent_bars,
            min_amplitude=config.min_amplitude,
            min_duration=config.min_duration,
            noise_filter=config.noise_filter,
        )
        segments = build_segments(pivots)
        assert len(segments) == len(pivots) - 1
        for seg in segments:
            assert seg.duration >= 0
            assert seg.direction.value != 0  # 非 FLAT


# ─── 关键区识别 ────────────────────────────────────────────

class TestZones:
    def test_detect(self, recent_bars, config):
        pivots = extract_pivots(
            recent_bars,
            min_amplitude=config.min_amplitude,
            min_duration=config.min_duration,
            noise_filter=config.noise_filter,
        )
        zones = detect_zones(
            pivots,
            zone_bandwidth=config.zone_bandwidth,
            cluster_eps=config.cluster_eps,
            cluster_min_points=config.cluster_min_points,
        )
        assert len(zones) > 0
        for z in zones:
            assert z.bandwidth > 0
            assert z.strength > 0
            assert len(z.touches) >= 2


# ─── 编译器全链路 ──────────────────────────────────────────

class TestCompiler:
    def test_full_pipeline_recent(self, recent_bars, config):
        result = compile_full(recent_bars, config)
        s = result.summary()
        assert s["pivots"] > 0
        assert s["segments"] > 0
        assert s["zones"] > 0
        assert s["structures"] > 0

    def test_full_pipeline_all(self, all_bars, config):
        result = compile_full(all_bars, config)
        s = result.summary()
        # 全量数据应产出合理数量的结构
        assert s["pivots"] > 100
        assert s["structures"] > 5
        assert s["bundles"] > 0

    def test_structure_invariants(self, all_bars, config):
        result = compile_full(all_bars, config)
        for st in result.structures:
            inv = st.invariants
            assert "avg_speed_ratio" in inv
            assert "avg_time_ratio" in inv
            assert "cycle_count" in inv
            assert inv["cycle_count"] >= 2

    def test_deterministic(self, recent_bars, config):
        r1 = compile_full(recent_bars, config)
        r2 = compile_full(recent_bars, config)
        assert r1.summary()["pivots"] == r2.summary()["pivots"]
        assert r1.summary()["structures"] == r2.summary()["structures"]
