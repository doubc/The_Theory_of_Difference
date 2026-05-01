"""
单元测试 — Phase 8 重构后的新模块

覆盖：classify_price_position, compute_priority_score, build_risk_tags,
      pick_today_three, fmt_* 函数, departure_score, build_market_overview
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.workbench.ui_formatters import (
    classify_price_position, build_risk_tags,
    fmt_direction, fmt_phase, fmt_position, fmt_volume,
    fmt_flux_color, fmt_tier_color, fmt_departure_color, fmt_priority_color,
)
from src.workbench.scan_filters import (
    compute_priority_score, apply_scan_filters, pick_today_three, build_market_overview,
)
from src.workbench.scan_pipeline import departure_score
from src.workbench.scan_models import ScanRecord, SignalInfo, ZoneInfo


# ═══════════════════════════════════════════════════════════
# classify_price_position
# ═══════════════════════════════════════════════════════════

class TestClassifyPricePosition:
    def test_above_zone(self):
        desc, code = classify_price_position(110, 100, 90, 95, 5)
        assert code == "H"
        assert "破缺上行" in desc

    def test_below_zone(self):
        desc, code = classify_price_position(80, 100, 90, 95, 5)
        assert code == "L"
        assert "破缺下行" in desc

    def test_inside_zone_center(self):
        desc, code = classify_price_position(95, 100, 90, 95, 5)
        assert code == "M"
        assert "稳态内" in desc

    def test_inside_zone_near_upper(self):
        # dist_to_upper = (100 - 99.3) / 5 = 0.14 < 0.15 → 试探边界
        desc, code = classify_price_position(99.3, 100, 90, 95, 5)
        assert code == "M"
        assert "试探边界" in desc

    def test_inside_zone_near_lower(self):
        # dist_to_lower = (90.7 - 90) / 5 = 0.14 < 0.15 → 试探边界
        desc, code = classify_price_position(90.7, 100, 90, 95, 5)
        assert code == "M"
        assert "试探边界" in desc

    def test_zero_bandwidth(self):
        desc, code = classify_price_position(95, 95, 95, 95, 0)
        assert code == "M"


# ═══════════════════════════════════════════════════════════
# compute_priority_score
# ═══════════════════════════════════════════════════════════

class TestComputePriorityScore:
    def test_max_score(self):
        score = compute_priority_score(
            dep_score=100, qa_score=1.0, phase_code="breakout",
            price_position_code="H", latest_vol=100000, results_so_far=[],
        )
        assert score > 0.8

    def test_min_score(self):
        score = compute_priority_score(
            dep_score=0, qa_score=0.0, phase_code="stable",
            price_position_code="M", latest_vol=1000, results_so_far=[{"volume": 100000}],
        )
        assert score < 0.3

    def test_breakout_higher_than_stable(self):
        s_breakout = compute_priority_score(50, 0.5, "breakout", "M", 50000, [])
        s_stable = compute_priority_score(50, 0.5, "stable", "M", 50000, [])
        assert s_breakout > s_stable

    def test_volume_relative(self):
        s_high = compute_priority_score(50, 0.5, "forming", "M", 100000, [{"volume": 100000}])
        s_low = compute_priority_score(50, 0.5, "forming", "M", 10000, [{"volume": 100000}])
        assert s_high > s_low


# ═══════════════════════════════════════════════════════════
# build_risk_tags
# ═══════════════════════════════════════════════════════════

class TestBuildRiskTags:
    def test_breakout_blind(self):
        tags = build_risk_tags({"is_blind": True, "phase_code": "breakout", "flux": 0.1, "departure_score": 10})
        assert "⚠️高压缩" in tags
        assert "🔴破缺" in tags

    def test_high_flux(self):
        tags = build_risk_tags({"is_blind": False, "phase_code": "stable", "flux": 0.6, "departure_score": 10})
        assert "⚡高通量" in tags

    def test_high_departure(self):
        tags = build_risk_tags({"is_blind": False, "phase_code": "forming", "flux": 0.1, "departure_score": 70})
        assert "🔥高活跃" in tags

    def test_empty(self):
        tags = build_risk_tags({"is_blind": False, "phase_code": "stable", "flux": 0.1, "departure_score": 10})
        assert tags == []


# ═══════════════════════════════════════════════════════════
# fmt_* 函数
# ═══════════════════════════════════════════════════════════

class TestFormatters:
    def test_fmt_direction(self):
        assert fmt_direction("up") == "📈"
        assert fmt_direction("down") == "📉"
        assert fmt_direction("unclear") == "➡️"

    def test_fmt_phase(self):
        assert "破缺" in fmt_phase("breakout")
        assert "确认" in fmt_phase("confirmation")
        assert "稳态" in fmt_phase("stable")

    def test_fmt_position(self):
        assert fmt_position("H") == "高位"
        assert fmt_position("M") == "中位"
        assert fmt_position("L") == "低位"

    def test_fmt_volume(self):
        assert fmt_volume(123456) == "123,456"
        assert fmt_volume(0) == "0"

    def test_fmt_flux_color(self):
        assert fmt_flux_color(0.3) == "#4caf50"
        assert fmt_flux_color(-0.3) == "#ef5350"
        assert fmt_flux_color(0.1) == "#999"

    def test_fmt_tier_color(self):
        assert fmt_tier_color("A") == "#4caf50"
        assert fmt_tier_color("B") == "#2196f3"
        assert fmt_tier_color("C") == "#ff9800"
        assert fmt_tier_color("?") == "#999"

    def test_fmt_departure_color(self):
        assert fmt_departure_color(60) == "#4caf50"
        assert fmt_departure_color(30) == "#ff9800"
        assert fmt_departure_color(10) == "#999"

    def test_fmt_priority_color(self):
        assert fmt_priority_color(70) == "#4caf50"
        assert fmt_priority_color(50) == "#ff9800"
        assert fmt_priority_color(30) == "#999"


# ═══════════════════════════════════════════════════════════
# departure_score
# ═══════════════════════════════════════════════════════════

class TestDepartureScore:
    def test_all_max(self):
        r = {
            "phase_transition": True,
            "flux_magnitude": 0.5,
            "departure_velocity": 0.5,
            "signal_score": 1.0,
        }
        assert departure_score(r) == 100.0

    def test_all_zero(self):
        r = {
            "phase_transition": False,
            "flux_magnitude": 0,
            "departure_velocity": 0,
            "signal_score": 0,
        }
        assert departure_score(r) == 0.0

    def test_partial(self):
        r = {
            "phase_transition": True,
            "flux_magnitude": 0.25,
            "departure_velocity": 0,
            "signal_score": 0.5,
        }
        score = departure_score(r)
        assert 40 < score < 60  # 25 + 12.5 + 0 + 12.5 = 50


# ═══════════════════════════════════════════════════════════
# pick_today_three
# ═══════════════════════════════════════════════════════════

class TestPickTodayThree:
    def _make_data(self):
        return [
            {"symbol": "CU0", "symbol_name": "铜", "phase_code": "confirmation", "priority_score": 80, "price_position": "稳态内", "direction": "up"},
            {"symbol": "RB0", "symbol_name": "螺纹钢", "phase_code": "breakout", "priority_score": 75, "price_position": "破缺上行", "direction": "up"},
            {"symbol": "I0", "symbol_name": "铁矿石", "phase_code": "forming", "priority_score": 60, "price_position": " ! 试探边界", "direction": "down"},
            {"symbol": "AL0", "symbol_name": "铝", "phase_code": "stable", "priority_score": 50, "price_position": "稳态内", "direction": "unclear"},
            {"symbol": "AU0", "symbol_name": "黄金", "phase_code": "confirmation", "priority_score": 70, "price_position": "稳态内", "direction": "up"},
        ]

    def test_picks_three(self):
        result = pick_today_three(self._make_data())
        assert len(result) == 3

    def test_picks_confirmation(self):
        result = pick_today_three(self._make_data())
        confirm_picks = [r for r in result if r["pick_reason"] == "最强确认"]
        assert len(confirm_picks) == 1
        assert confirm_picks[0]["symbol"] == "CU0"  # highest priority among confirmations

    def test_picks_breakout(self):
        result = pick_today_three(self._make_data())
        breakout_picks = [r for r in result if r["pick_reason"] == "最强破缺"]
        assert len(breakout_picks) == 1
        assert breakout_picks[0]["symbol"] == "RB0"

    def test_picks_boundary_test(self):
        result = pick_today_three(self._make_data())
        boundary_picks = [r for r in result if r["pick_reason"] == "最强边界试探"]
        assert len(boundary_picks) == 1
        assert boundary_picks[0]["symbol"] == "I0"

    def test_no_breakout_fills_with_priority(self):
        data = [
            {"symbol": "CU0", "symbol_name": "铜", "phase_code": "confirmation", "priority_score": 80, "price_position": "稳态内", "direction": "up"},
            {"symbol": "AL0", "symbol_name": "铝", "phase_code": "stable", "priority_score": 50, "price_position": "稳态内", "direction": "unclear"},
            {"symbol": "ZN0", "symbol_name": "锌", "phase_code": "forming", "priority_score": 40, "price_position": "稳态内", "direction": "up"},
            {"symbol": "PB0", "symbol_name": "铅", "phase_code": "stable", "priority_score": 30, "price_position": "稳态内", "direction": "down"},
        ]
        result = pick_today_three(data)
        assert len(result) == 3
        reasons = [r["pick_reason"] for r in result]
        assert "综合优先级" in reasons

    def test_empty_data(self):
        result = pick_today_three([])
        assert result == []


# ═══════════════════════════════════════════════════════════
# build_market_overview
# ═══════════════════════════════════════════════════════════

class TestBuildMarketOverview:
    def test_basic(self):
        data = [
            {"departure_score": 60, "motion": "→breakout"},
            {"departure_score": 30, "motion": "→confirmation"},
            {"departure_score": 10, "motion": "stable"},
        ]
        overview = build_market_overview(data)
        assert overview["active_count"] == 3
        assert overview["departure_count"] == 1
        assert overview["breakout_count"] == 1
        assert overview["confirmation_count"] == 1


# ═══════════════════════════════════════════════════════════
# apply_scan_filters
# ═══════════════════════════════════════════════════════════

class TestApplyScanFilters:
    def _make_data(self):
        return [
            {"symbol": "CU0", "direction": "up", "phase_code": "breakout", "price_position_code": "H", "tier": "A", "zone_trend": "上行", "sector": "有色金属", "volume": 50000},
            {"symbol": "RB0", "direction": "down", "phase_code": "confirmation", "price_position_code": "M", "tier": "B", "zone_trend": "下行", "sector": "黑色金属", "volume": 30000},
            {"symbol": "AL0", "direction": "unclear", "phase_code": "stable", "price_position_code": "L", "tier": "C", "zone_trend": "持平", "sector": "有色金属", "volume": 10000},
        ]

    def test_no_filter(self):
        assert len(apply_scan_filters(self._make_data())) == 3

    def test_direction_filter(self):
        assert len(apply_scan_filters(self._make_data(), direction="偏多")) == 1

    def test_motion_filter(self):
        assert len(apply_scan_filters(self._make_data(), motion="破缺")) == 1

    def test_tier_filter(self):
        assert len(apply_scan_filters(self._make_data(), tier="A")) == 1

    def test_sector_filter(self):
        assert len(apply_scan_filters(self._make_data(), sector="有色金属")) == 2

    def test_volume_filter(self):
        assert len(apply_scan_filters(self._make_data(), min_volume=20000)) == 2

    def test_combined_filter(self):
        result = apply_scan_filters(self._make_data(), direction="偏多", tier="A")
        assert len(result) == 1
        assert result[0]["symbol"] == "CU0"


# ═══════════════════════════════════════════════════════════
# ScanRecord dataclass
# ═══════════════════════════════════════════════════════════

class TestScanRecord:
    def test_to_dict_roundtrip(self):
        rec = ScanRecord(
            symbol="CU0", symbol_name="铜", volume=50000,
            last_price=70000.0, phase_code="breakout", direction="up",
            priority_score=80.0,
        )
        d = rec.to_dict()
        assert d["symbol"] == "CU0"
        assert d["volume"] == 50000

        rec2 = ScanRecord.from_dict(d)
        assert rec2.symbol == "CU0"
        assert rec2.volume == 50000
        assert rec2.phase_code == "breakout"

    def test_signal_info_roundtrip(self):
        sig = SignalInfo(kind="breakout_confirm", direction="long", confidence=0.85)
        rec = ScanRecord(symbol="CU0", signal_info=sig)
        d = rec.to_dict()
        assert d["signal_info"]["kind"] == "breakout_confirm"

        rec2 = ScanRecord.from_dict(d)
        assert rec2.signal_info.kind == "breakout_confirm"
        assert rec2.signal_info.confidence == 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
