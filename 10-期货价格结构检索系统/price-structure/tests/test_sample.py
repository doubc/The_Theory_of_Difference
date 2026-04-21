"""
样本库测试
"""

import pytest
import json
import tempfile
from datetime import datetime
from pathlib import Path

from src.models import Point, Segment, Zone, Cycle, Structure, ZoneSource
from src.sample.store import Sample, SampleStore, ForwardOutcome
from src.sample.outcome import compute_forward_outcome
from src.data.loader import load_cu0


class TestSample:
    def test_serialization(self):
        s = Sample(
            id="test_001",
            symbol="CU000",
            t_start=datetime(2024, 1, 1),
            t_end=datetime(2024, 2, 1),
            structure={"zone": {"price_center": 70000}},
            label_type="SlowUpFastDown_TopReversal",
            typicality=0.9,
            annotation="经典案例",
        )
        line = s.to_json()
        s2 = Sample.from_json(line)
        assert s2.id == s.id
        assert s2.label_type == s.label_type
        assert s2.annotation == s.annotation


class TestSampleStore:
    def test_append_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SampleStore(Path(tmpdir) / "test.jsonl")
            s1 = Sample(id="1", symbol="CU000", t_start=datetime(2024, 1, 1),
                        t_end=datetime(2024, 2, 1), structure={}, label_type="type_a", typicality=0.8)
            s2 = Sample(id="2", symbol="CU000", t_start=datetime(2024, 2, 1),
                        t_end=datetime(2024, 3, 1), structure={}, label_type="type_b", typicality=0.6)
            store.append(s1)
            store.append(s2)
            assert store.count() == 2

            all_samples = store.load_all()
            assert len(all_samples) == 2

    def test_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SampleStore(Path(tmpdir) / "test.jsonl")
            store.append(Sample(id="1", symbol="CU000", t_start=datetime(2024, 1, 1),
                                t_end=datetime(2024, 2, 1), structure={}, label_type="type_a", typicality=0.9))
            store.append(Sample(id="2", symbol="AU000", t_start=datetime(2024, 2, 1),
                                t_end=datetime(2024, 3, 1), structure={}, label_type="type_b", typicality=0.5))

            assert len(store.filter(label_type="type_a")) == 1
            assert len(store.filter(symbol="AU000")) == 1
            assert len(store.filter(min_typicality=0.7)) == 1

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SampleStore(Path(tmpdir) / "test.jsonl")
            store.append(Sample(id="1", symbol="CU000", t_start=datetime(2024, 1, 1),
                                t_end=datetime(2024, 2, 1), structure={}, label_type="type_a"))
            assert store.count() == 1
            store.clear()
            assert store.count() == 0


class TestForwardOutcome:
    def test_compute(self):
        loader = load_cu0(str(Path(__file__).parent.parent / "data"), dedup=True)
        bars = loader.get()

        # 取一个中间日期
        t_end = bars[1000].timestamp
        outcome = compute_forward_outcome(bars, t_end)

        assert outcome.ret_5d != 0.0 or outcome.ret_10d != 0.0
        # max_rise 应 > 0，max_dd 应 < 0（或均为0如果窗口超出范围）
        assert isinstance(outcome.max_rise_20d, float)
        assert isinstance(outcome.max_dd_20d, float)
