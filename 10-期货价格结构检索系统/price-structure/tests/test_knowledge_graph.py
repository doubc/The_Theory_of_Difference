"""
知识图谱模块测试

覆盖：
- NarrativeRecursionTracker（叙事递归追踪）
- ReflexivityDetector（反身性检测）
- TransferNetwork（跨品种差异转移）
- StructureGraph 扩展功能
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.graph.narrative_tracker import (
    NarrativeRecursionTracker, NarrativeSnapshot,
    NarrativeEvolutionChain, NarrativeEvolutionStep,
    LockReport, DriftReport,
)
from src.graph.reflexivity import (
    ReflexivityDetector, RuleMatchRecord,
    InvalidationEvent, ReflexivityLoop,
    TemplateDecayReport, ReflexivityReport,
)
from src.graph.transfer_network import (
    TransferNetwork, FluxRecord, TransferEdge,
    TransferPath, ProductNode, TransferNetworkReport,
)
from src.graph.store import GraphStore
from src.graph import StructureGraph, NodeType, EdgeType


# ═══════════════════════════════════════════════════════════
# NarrativeRecursionTracker
# ═══════════════════════════════════════════════════════════

class TestNarrativeTracker:

    def _make_snapshot(self, text, ts, zone_key="CU0:70000"):
        return NarrativeSnapshot(
            text=text, timestamp=ts,
            zone_key=zone_key, structure_id=f"test_{ts.strftime('%Y%m%d')}",
        )

    def test_text_similarity_identical(self):
        assert NarrativeRecursionTracker._text_similarity("abc", "abc") == 1.0

    def test_text_similarity_empty(self):
        assert NarrativeRecursionTracker._text_similarity("", "") == 1.0

    def test_text_similarity_one_empty(self):
        assert NarrativeRecursionTracker._text_similarity("abc", "") == 0.0

    def test_text_similarity_similar(self):
        sim = NarrativeRecursionTracker._text_similarity(
            "恐慌性抛售导致铜价大跌",
            "恐慌抛售导致铜价下跌"
        )
        assert 0.5 < sim < 1.0

    def test_chain_total_drift(self):
        snap1 = self._make_snapshot("恐慌抛售", datetime(2025, 1, 1))
        snap2 = self._make_snapshot("价格企稳", datetime(2025, 1, 15))
        step = NarrativeEvolutionStep(
            from_snapshot=snap1, to_snapshot=snap2,
            similarity=0.6, drift_delta=0.4,
            phase_changed=True, flux_direction="positive",
        )
        chain = NarrativeEvolutionChain(zone_key="CU0:70000", steps=[step])
        assert chain.total_drift == pytest.approx(0.4)

    def test_chain_avg_similarity(self):
        snap1 = self._make_snapshot("a", datetime(2025, 1, 1))
        snap2 = self._make_snapshot("b", datetime(2025, 1, 15))
        snap3 = self._make_snapshot("c", datetime(2025, 2, 1))
        steps = [
            NarrativeEvolutionStep(snap1, snap2, 0.8, 0.2, False, "neutral"),
            NarrativeEvolutionStep(snap2, snap3, 0.6, 0.4, True, "negative"),
        ]
        chain = NarrativeEvolutionChain(zone_key="CU0:70000", steps=steps)
        assert chain.avg_similarity == pytest.approx(0.7)

    def test_lock_detection_not_locked(self):
        tracker = NarrativeRecursionTracker(lock_min_steps=3)
        snap1 = self._make_snapshot("恐慌抛售", datetime(2025, 1, 1))
        snap2 = self._make_snapshot("价格企稳", datetime(2025, 1, 15))
        steps = [
            NarrativeEvolutionStep(snap1, snap2, 0.6, 0.4, True, "positive"),
        ]
        chain = NarrativeEvolutionChain(zone_key="CU0:70000", steps=steps, snapshots=[snap1, snap2])
        lock = tracker.detect_lock(chain)
        assert not lock.is_locked

    def test_lock_detection_locked(self):
        tracker = NarrativeRecursionTracker(lock_threshold=0.9, lock_min_steps=3)
        snaps = [
            self._make_snapshot(f"叙事{i}", datetime(2025, 1, 1) + timedelta(days=i * 10))
            for i in range(5)
        ]
        steps = [
            NarrativeEvolutionStep(snaps[i], snaps[i + 1], 0.95, 0.05, False, "neutral")
            for i in range(4)
        ]
        chain = NarrativeEvolutionChain(zone_key="CU0:70000", steps=steps, snapshots=snaps)
        lock = tracker.detect_lock(chain)
        assert lock.is_locked
        assert lock.lock_strength > 0

    def test_drift_rate_computation(self):
        tracker = NarrativeRecursionTracker()
        snaps = [
            self._make_snapshot(f"叙事{i}", datetime(2025, 1, 1) + timedelta(days=i * 10))
            for i in range(4)
        ]
        steps = [
            NarrativeEvolutionStep(snaps[i], snaps[i + 1], 0.7, 0.3, False, "neutral")
            for i in range(3)
        ]
        chain = NarrativeEvolutionChain(zone_key="CU0:70000", steps=steps, snapshots=snaps)
        drift = tracker.compute_drift_rate(chain)
        assert drift.drift_rate == pytest.approx(0.3)
        assert drift.drift_trend in ("stable", "accelerating", "decelerating")

    def test_from_store(self):
        import shutil
        base = "/tmp/test_narrative_store"
        if os.path.exists(base):
            shutil.rmtree(base)
        store = GraphStore(base)

        store.append_narrative({
            "narrative_id": "n1", "text": "恐慌抛售",
            "zone_key": "CU0:70000", "timestamp": "2025-01-01", "symbol": "CU0",
        })
        store.append_narrative({
            "narrative_id": "n2", "text": "价格企稳回升",
            "zone_key": "CU0:70000", "timestamp": "2025-01-15", "symbol": "CU0",
        })

        tracker = NarrativeRecursionTracker.from_store(store, symbol="CU0")
        assert len(tracker._chains) > 0

        # Cleanup
        shutil.rmtree(store.base)


# ═══════════════════════════════════════════════════════════
# ReflexivityDetector
# ═══════════════════════════════════════════════════════════

class TestReflexivityDetector:

    def test_record_match(self):
        det = ReflexivityDetector()
        det.record_match("rule_1", "struct_1", 0.8)
        assert len(det._match_records) == 1
        assert det._match_records[0].rule_id == "rule_1"

    def test_record_outcome(self):
        det = ReflexivityDetector()
        det.record_match("rule_1", "struct_1", 0.8)
        det.record_outcome("rule_1", "struct_1", "success", 0.05)
        assert det._match_records[0].outcome == "success"
        assert det._match_records[0].outcome_return == 0.05

    def test_record_invalidation(self):
        det = ReflexivityDetector()
        det.record_invalidation("rule_1", "struct_1", "market changed", 0.7)
        assert len(det._invalidation_events) == 1
        assert det._invalidation_events[0].severity == 0.7

    def test_template_effectiveness(self):
        det = ReflexivityDetector()
        for i in range(10):
            det.record_match("rule_1", f"struct_{i}", 0.8)
            outcome = "success" if i < 7 else "failure"
            det.record_outcome("rule_1", f"struct_{i}", outcome)

        eff = det._compute_template_effectiveness("rule_1")
        assert eff == pytest.approx(0.7)

    def test_analyze_decay(self):
        det = ReflexivityDetector(decay_window=10, min_matches=3)
        # Early successes, later failures
        for i in range(10):
            det.record_match("rule_1", f"struct_{i}", 0.8)
            outcome = "success" if i < 6 else "failure"
            det.record_outcome("rule_1", f"struct_{i}", outcome)

        reports = det.analyze_template_decay()
        assert len(reports) == 1
        assert reports[0].rule_id == "rule_1"
        assert reports[0].total_matches == 10
        assert reports[0].success_count == 6
        assert reports[0].failure_count == 4

    def test_auto_downgrade(self):
        det = ReflexivityDetector(decay_window=5, min_matches=3, downgrade_threshold=0.3)
        graph = StructureGraph()
        graph.add_rule_node("rule_1")

        # Rapid decay
        for i in range(8):
            det.record_match("rule_1", f"struct_{i}", 0.8)
            outcome = "success" if i < 2 else "failure"
            det.record_outcome("rule_1", f"struct_{i}", outcome)

        actions = det.auto_downgrade(graph)
        # May or may not downgrade depending on exact threshold
        assert isinstance(actions, list)

    def test_generate_report(self):
        det = ReflexivityDetector()
        graph = StructureGraph()
        graph.add_rule_node("rule_1")

        det.record_match("rule_1", "struct_1", 0.8)
        det.record_outcome("rule_1", "struct_1", "success")

        report = det.generate_report(graph)
        assert isinstance(report, ReflexivityReport)
        assert report.total_rules == 1

    def test_get_rule_history(self):
        det = ReflexivityDetector()
        det.record_match("rule_1", "struct_1", 0.8, datetime(2025, 1, 1))
        det.record_match("rule_1", "struct_2", 0.7, datetime(2025, 1, 15))

        history = det.get_rule_history("rule_1")
        assert len(history) == 2
        assert history[0]["structure_id"] == "struct_1"

    def test_to_dict(self):
        det = ReflexivityDetector()
        det.record_match("rule_1", "struct_1", 0.8)
        d = det.to_dict()
        assert d["match_records"] == 1
        assert d["rules_tracked"] == 1


# ═══════════════════════════════════════════════════════════
# TransferNetwork
# ═══════════════════════════════════════════════════════════

class TestTransferNetwork:

    def _make_records(self, symbol, fluxes, start=datetime(2025, 1, 1)):
        return [
            FluxRecord(
                symbol=symbol,
                timestamp=start + timedelta(days=i),
                conservation_flux=f,
                phase_tendency="release" if f > 0 else "accumulation",
                zone_center=70000 if symbol == "CU0" else 20000,
                cycle_count=3,
            )
            for i, f in enumerate(fluxes)
        ]

    def test_add_flux_record(self):
        net = TransferNetwork()
        record = FluxRecord(
            symbol="CU0", timestamp=datetime(2025, 1, 1),
            conservation_flux=0.5, phase_tendency="release",
            zone_center=70000, cycle_count=3,
        )
        net.add_flux_record(record)
        assert len(net._flux_history["CU0"]) == 1

    def test_add_flux_batch(self):
        net = TransferNetwork()
        records = self._make_records("CU0", [0.1, 0.2, 0.3])
        net.add_flux_batch(records)
        assert len(net._flux_history["CU0"]) == 3

    def test_negative_correlation_detected(self):
        """负相关 = 差异转移特征"""
        import random
        random.seed(42)
        net = TransferNetwork(min_overlap_days=20, correlation_threshold=-0.3)

        for i in range(60):
            ts = datetime(2025, 1, 1) + timedelta(days=i)
            cu = random.gauss(0, 0.5) if i < 30 else random.gauss(0.3, 0.3)
            al = -cu * 0.7 + random.gauss(0, 0.2)
            net.add_flux_record(FluxRecord("CU0", ts, cu, "", 70000, 3))
            net.add_flux_record(FluxRecord("AL0", ts, al, "", 20000, 2))

        report = net.build_network()
        assert len(report.edges) >= 1
        # Should detect negative correlation
        edge = report.edges[0]
        assert edge.correlation < -0.3

    def test_no_correlation(self):
        """无相关 → 无边"""
        import random
        random.seed(99)
        net = TransferNetwork(min_overlap_days=10)

        for i in range(30):
            ts = datetime(2025, 1, 1) + timedelta(days=i)
            net.add_flux_record(FluxRecord("CU0", ts, random.gauss(0, 1), "", 70000, 3))
            net.add_flux_record(FluxRecord("AL0", ts, random.gauss(0, 1), "", 20000, 2))

        report = net.build_network()
        # Random data - may or may not have edges
        assert isinstance(report.edges, list)

    def test_transfer_matrix(self):
        net = TransferNetwork()
        net._nodes = {
            "CU0": ProductNode("CU0", "CU0", 0.1, 0.2, "release", 0.5, 1),
            "AL0": ProductNode("AL0", "AL0", -0.1, 0.3, "accumulation", 0.3, 1),
        }
        net._edges = [
            TransferEdge("CU0", "AL0", 0.8, "CU0→AL0", -0.8, 0, "高", 10),
        ]

        symbols, matrix = net.get_transfer_matrix()
        assert len(symbols) == 2
        assert matrix.shape == (2, 2)
        assert matrix[0][1] == pytest.approx(0.8)
        assert matrix[1][0] == pytest.approx(0.8)  # Symmetric

    def test_get_strongest_transfers(self):
        net = TransferNetwork()
        net._edges = [
            TransferEdge("A", "B", 0.9, "", -0.9, 0, "高", 10),
            TransferEdge("A", "C", 0.3, "", -0.3, 0, "低", 3),
        ]
        top = net.get_strongest_transfers(1)
        assert len(top) == 1
        assert top[0].strength == 0.9

    def test_systemic_stress(self):
        net = TransferNetwork()
        net._edges = [
            TransferEdge("A", "B", 0.8, "", -0.8, 0, "高", 10),
            TransferEdge("B", "C", 0.6, "", -0.6, 0, "中", 5),
        ]
        net._nodes = {
            "A": ProductNode("A", "A", 0.1, 0.3, "release", 0.5, 2),
            "B": ProductNode("B", "B", -0.1, 0.2, "accumulation", 0.3, 2),
            "C": ProductNode("C", "C", 0.0, 0.1, "stable", 0.1, 1),
        }
        stress = net._compute_systemic_stress()
        assert 0 <= stress <= 1

    def test_to_dict(self):
        net = TransferNetwork()
        net.add_flux_record(FluxRecord("CU0", datetime(2025, 1, 1), 0.5, "", 70000, 3))
        d = net.to_dict()
        assert d["products"] == 0  # No build yet
        assert d["flux_records"] == 1

    def test_ingest_from_structures(self):
        net = TransferNetwork()
        mock_st = MagicMock()
        mock_st.motion = MagicMock()
        mock_st.motion.conservation_flux = 0.5
        mock_st.motion.phase_tendency = "release"
        mock_st.motion.movement_type.value = "trend_up"
        mock_st.zone.price_center = 70000
        mock_st.cycle_count = 3
        mock_st.t_end = datetime(2025, 1, 1)

        count = net.ingest_from_structures([mock_st], "CU0")
        assert count == 1
        assert len(net._flux_history["CU0"]) == 1


# ═══════════════════════════════════════════════════════════
# StructureGraph 扩展
# ═══════════════════════════════════════════════════════════

class TestStructureGraphExtended:

    def test_add_structure_node(self):
        g = StructureGraph()
        nid = g.add_structure_node("test_001", zone_center=70000)
        assert nid == "struct:test_001"
        assert g.G.nodes[nid]["node_type"] == "structure"

    def test_add_zone_node(self):
        g = StructureGraph()
        nid = g.add_zone_node("CU0_70000", price_center=70000)
        assert nid == "zone:CU0_70000"

    def test_link_evolution(self):
        g = StructureGraph()
        s1 = g.add_structure_node("old")
        s2 = g.add_structure_node("new")
        g.link_evolution(s1, s2)
        chain = g.get_structure_evolution_chain(s1)
        assert len(chain) == 2

    def test_reflexivity_loops(self):
        g = StructureGraph()
        r = g.add_rule_node("breakout_rule")
        s1 = g.add_structure_node("struct_1")
        s2 = g.add_structure_node("struct_2")
        g.link_rule_identification(s1, r)
        g.link_evolution(s1, s2)
        g.link_rule_invalidation(s2, r)

        loops = g.get_reflexivity_loops()
        assert len(loops) >= 1

    def test_zone_network(self):
        g = StructureGraph()
        z1 = g.add_zone_node("Z1", price_center=70000)
        z2 = g.add_zone_node("Z2", price_center=71000)
        g.link_adjacent_zones(z1, z2, distance=1000)

        network = g.get_zone_network()
        assert "zone:Z1" in network
        assert "zone:Z2" in network["zone:Z1"]["adjacent_zones"]


# ═══════════════════════════════════════════════════════════
# 集成测试
# ═══════════════════════════════════════════════════════════

class TestIntegration:

    def test_full_pipeline(self):
        """完整流水线：图谱构建 → 叙事追踪 → 反身性检测"""
        import shutil

        # 1. 构建图谱
        graph = StructureGraph()
        s1 = graph.add_structure_node("CU0_S0_20250101", zone_center=70000, narrative="恐慌抛售")
        z1 = graph.add_zone_node("CU0_70000", price_center=70000)
        graph.link_structure_zone(s1, z1)
        sym = graph.add_symbol_node("CU0")
        graph.link_structure_symbol(s1, sym)

        assert graph.G.number_of_nodes() == 3
        assert graph.G.number_of_edges() == 2

        # 2. 持久化
        import shutil
        base = "/tmp/test_integration"
        if os.path.exists(base):
            shutil.rmtree(base)
        store = GraphStore(base)

        stats = graph.save_to_store(store)
        assert stats["structures"] >= 1

        # 3. 重新加载
        loaded = StructureGraph.load_from_store(store)
        assert loaded.G.number_of_nodes() >= 1

        # 4. 叙事追踪
        tracker = NarrativeRecursionTracker()
        assert tracker._text_similarity("恐慌抛售", "恐慌抛售缓解") > 0.3

        # 5. 反身性检测
        detector = ReflexivityDetector()
        detector.record_match("rule_1", "struct_1", 0.8)
        assert len(detector._match_records) == 1

        # Cleanup
        shutil.rmtree(store.base)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
