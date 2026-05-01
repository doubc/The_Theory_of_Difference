from src.multitimeframe.consistency import TFSnapshot, compute_mci
from src.retrieval.transition import build_transition_distribution, wilson_interval
from src.scoring.priority import compute_priority, compute_amplitude_convergence
from src.sector.mapping import get_sector, get_chain_peers


def test_priority_formation_depth_differentiates():
    """形成深度必须让'老 forming'和'新 forming'拉开差距"""
    young = compute_priority("forming", 30, 59, "H",
                             test_count=2, duration_days=10,
                             amplitude_convergence=0.0, time_since_last_test=20)
    mature = compute_priority("forming", 30, 59, "H",
                              test_count=5, duration_days=90,
                              amplitude_convergence=-0.03, time_since_last_test=3)
    assert mature.total - young.total >= 10, "成熟 forming 必须比年轻 forming 至少高 10 分"


def test_sector_no_unknown_for_major_symbols():
    for sym in ["CU0", "RB0", "HC0", "I0", "FG0", "SA0", "M0", "TA0", "V0"]:
        assert get_sector(sym).sector != "其他", f"{sym} 不该是未知板块"


def test_chain_peers_black_metal():
    peers = get_chain_peers("RB0")
    assert "HC0" in peers and "I0" in peers


def test_wilson_small_sample():
    low, high = wilson_interval(3, 5)
    assert 0.0 < low < 0.6 and 0.4 < high < 1.0


def test_transition_fallback_on_low_support():
    """严格匹配样本<5 时应自动放宽条件"""
    history = [
                  {"phase": "confirmation", "quality": "B", "flux_sign": "+",
                   "from_zone": 100.0, "to_zone": 102.0, "holding_days": 10, "max_drawdown": 0.01}
              ] * 8
    dist = build_transition_distribution(
        history_transitions=history,
        current_context={"phase": "confirmation", "quality": "A", "flux_sign": "-"},
    )
    assert dist.total_samples > 0, "应当回退到 phase 匹配"


def test_mci_strong_resonance():
    snap = TFSnapshot("", "up", 1, "confirmation", 100.0, 2.0, 70)
    snaps = {
        "D": TFSnapshot("D", "up", 1, "confirmation", 100.0, 3.0, 70),
        "1h": TFSnapshot("1h", "up", 1, "confirmation", 100.0, 2.0, 70),
        "5m": TFSnapshot("5m", "up", 1, "forming", 100.0, 1.0, 65),
    }
    r = compute_mci(snaps)
    assert r.mci >= 0.70, f"完全同向应当强共振，实际 {r.mci}"
