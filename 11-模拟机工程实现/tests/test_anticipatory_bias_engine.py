"""
tests/test_anticipatory_bias_engine.py — AnticipatoryBiasEngine 单元测试 + 集成测试

覆盖：
- PatternExtrapolator 三种外推方法
- 方法选择策略
- 置信度计算
- ODI 门控
- PredictionErrorTracker
- AnticipationConfidence
- AnticipatoryBiasEngine 主体
- 与 PersistentBiasMemory 集成
"""

import math
import pytest
import torch
import numpy as np

from engine.anticipatory_bias_engine import (
    AnticipatoryBiasEngine,
    PatternExtrapolator,
    PredictionErrorTracker,
    AnticipationConfidence,
    ExpectationField,
    PredictionError,
    AnticipationResult,
    DEFAULT_ANTICIPATION_CONFIG,
)
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.hierarchy_manager import BiasField
from engine.organizational_density_index import DensityIndexResult


# ─── Fixtures ───

@pytest.fixture
def extrapolator():
    return PatternExtrapolator()


@pytest.fixture
def error_tracker():
    return PredictionErrorTracker()


@pytest.fixture
def confidence_evaluator():
    return AnticipationConfidence()


@pytest.fixture
def memory():
    return PersistentBiasMemory()


@pytest.fixture
def engine(memory):
    return AnticipatoryBiasEngine(memory=memory)


@pytest.fixture
def stable_history():
    """方向稳定的历史偏置（适合线性外推）"""
    return [
        (1, torch.tensor([1.0, 0.0, 0.0])),
        (2, torch.tensor([1.1, 0.0, 0.0])),
        (3, torch.tensor([1.2, 0.0, 0.0])),
        (4, torch.tensor([1.3, 0.0, 0.0])),
        (5, torch.tensor([1.4, 0.0, 0.0])),
    ]


@pytest.fixture
def accelerating_history():
    """方向加速变化的历史偏置（方向有明显变化）"""
    return [
        (1, torch.tensor([1.0, 0.1])),
        (2, torch.tensor([0.8, 0.5])),
        (3, torch.tensor([0.3, 1.0])),
        (4, torch.tensor([-0.2, 1.2])),
        (5, torch.tensor([-0.5, 0.9])),
    ]


@pytest.fixture
def unstable_history():
    """方向不稳定的历史偏置"""
    torch.manual_seed(42)
    history = []
    for i in range(10):
        v = torch.randn(3)
        history.append((i + 1, v))
    return history


@pytest.fixture
def odi_result_factory():
    """ODI 结果工厂"""
    def _make(odi_value):
        result = DensityIndexResult(
            odi=odi_value,
            zone="test",
            densification_rate=0.0,
            timestamp=0,
        )
        return result
    return _make


# ─── PatternExtrapolator: 线性外推 ───

class TestPatternExtrapolatorLinear:
    def test_linear_extrapolation_direction(self, extrapolator, stable_history):
        """线性外推应延续趋势方向"""
        vec, conf, method = extrapolator.extrapolate(stable_history, horizon=1)
        assert method == 'linear'
        # 趋势是 +0.1 每步，所以预测应约为 1.5
        assert vec[0].item() == pytest.approx(1.5, abs=0.01)

    def test_linear_extrapolation_horizon(self, extrapolator, stable_history):
        """horizon=2 应预测两步后的值"""
        vec, conf, method = extrapolator.extrapolate(stable_history, horizon=2)
        assert method == 'linear'
        assert vec[0].item() == pytest.approx(1.6, abs=0.01)

    def test_linear_confidence_high_for_stable(self, extrapolator, stable_history):
        """稳定方向的置信度应较高"""
        vec, conf, method = extrapolator.extrapolate(stable_history, horizon=1)
        assert conf > 0.5


# ─── PatternExtrapolator: 加速度外推 ───

class TestPatternExtrapolatorAcceleration:
    def test_acceleration_method_selected(self, extrapolator, accelerating_history):
        """加速变化的历史应选择加速度外推"""
        vec, conf, method = extrapolator.extrapolate(accelerating_history, horizon=1)
        assert method == 'acceleration'

    def test_acceleration_predicts_differently(self, extrapolator, accelerating_history):
        """加速度外推应产生与线性外推不同的结果"""
        vec_acc, _, method = extrapolator.extrapolate(accelerating_history, horizon=1)
        assert method == 'acceleration'
        # 加速度外推结果应是一个有效的非零向量
        assert vec_acc.norm().item() > 0.0


# ─── PatternExtrapolator: 加权外推 ───

class TestPatternExtrapolatorWeighted:
    def test_weighted_method_selected(self, extrapolator, unstable_history):
        """方向不稳定的历史应选择加权外推"""
        vec, conf, method = extrapolator.extrapolate(unstable_history, horizon=1)
        assert method == 'weighted'

    def test_weighted_confidence_lower(self, extrapolator, unstable_history):
        """加权外推的置信度应较低"""
        vec, conf, method = extrapolator.extrapolate(unstable_history, horizon=1)
        assert conf < 0.7


# ─── PatternExtrapolator: 边界情况 ───

class TestPatternExtrapolatorEdgeCases:
    def test_empty_history(self, extrapolator):
        """空历史应返回零向量 + 最低置信度"""
        vec, conf, method = extrapolator.extrapolate([], horizon=1)
        assert method == 'insufficient_history'
        assert conf == DEFAULT_ANTICIPATION_CONFIG['min_confidence']

    def test_short_history(self, extrapolator):
        """历史不足 min_history_length 应返回 insufficient_history"""
        history = [(1, torch.tensor([1.0, 0.0]))]
        vec, conf, method = extrapolator.extrapolate(history, horizon=1)
        assert method == 'insufficient_history'

    def test_exact_min_history(self, extrapolator):
        """刚好等于 min_history_length 的历史应能外推"""
        min_len = DEFAULT_ANTICIPATION_CONFIG['min_history_length']
        history = [(i, torch.tensor([float(i), 0.0])) for i in range(min_len)]
        vec, conf, method = extrapolator.extrapolate(history, horizon=1)
        assert method != 'insufficient_history'

    def test_history_window_truncation(self):
        """超过 history_window 的历史应被截取"""
        config = {**DEFAULT_ANTICIPATION_CONFIG, 'history_window': 5}
        extr = PatternExtrapolator(config)
        history = [(i, torch.tensor([float(i), 0.0])) for i in range(20)]
        vec, conf, method = extr.extrapolate(history, horizon=1)
        # 应只使用最近 5 个
        assert method != 'insufficient_history'


# ─── PredictionErrorTracker ───

class TestPredictionErrorTracker:
    def test_record_error(self, error_tracker):
        """记录预测误差"""
        predicted = torch.tensor([1.0, 0.0])
        actual = torch.tensor([1.5, 0.5])
        error = error_tracker.record_error(predicted, actual, timestamp=1, horizon=1)
        assert error.error_magnitude == pytest.approx(0.7071, abs=0.01)
        assert error_tracker.n_predictions == 1

    def test_error_trend_improving(self, error_tracker):
        """误差递减时趋势应为负"""
        for i in range(10):
            predicted = torch.tensor([1.0])
            actual = torch.tensor([1.0 + 0.1 * (10 - i)])  # 误差递减
            error_tracker.record_error(predicted, actual, timestamp=i, horizon=1)
        assert error_tracker.is_learning()
        assert not error_tracker.is_degrading()

    def test_error_trend_degrading(self, error_tracker):
        """误差递增时趋势应为正"""
        for i in range(10):
            predicted = torch.tensor([1.0])
            actual = torch.tensor([1.0 + 0.1 * (i + 1)])  # 误差递增
            error_tracker.record_error(predicted, actual, timestamp=i, horizon=1)
        assert error_tracker.is_degrading()
        assert not error_tracker.is_learning()

    def test_mean_error(self, error_tracker):
        """平均误差计算"""
        error_tracker.record_error(
            torch.tensor([0.0]), torch.tensor([1.0]), timestamp=0, horizon=1
        )
        error_tracker.record_error(
            torch.tensor([0.0]), torch.tensor([3.0]), timestamp=1, horizon=1
        )
        assert error_tracker.get_mean_error() == pytest.approx(2.0, abs=0.01)

    def test_error_window_limit(self):
        """误差历史不应超过窗口大小"""
        config = {**DEFAULT_ANTICIPATION_CONFIG, 'error_window': 5}
        tracker = PredictionErrorTracker(config)
        for i in range(10):
            tracker.record_error(
                torch.tensor([0.0]), torch.tensor([1.0]), timestamp=i, horizon=1
            )
        assert tracker.n_predictions == 5

    def test_empty_tracker_trend(self, error_tracker):
        """空追踪器的趋势应为 0"""
        assert error_tracker.get_error_trend() == 0.0


# ─── AnticipationConfidence ───

class TestAnticipationConfidence:
    def test_high_accuracy_high_confidence(self, confidence_evaluator, error_tracker):
        """高预测准确率应产生高置信度"""
        for i in range(10):
            error_tracker.record_error(
                torch.tensor([1.0]), torch.tensor([1.01]), timestamp=i, horizon=1
            )
        conf = confidence_evaluator.compute(error_tracker, history_stability=0.9)
        assert conf > 0.5

    def test_low_accuracy_low_confidence(self, confidence_evaluator, error_tracker):
        """低预测准确率应产生低置信度"""
        for i in range(10):
            error_tracker.record_error(
                torch.tensor([0.0]), torch.tensor([10.0]), timestamp=i, horizon=1
            )
        conf = confidence_evaluator.compute(error_tracker, history_stability=0.9)
        assert conf < 0.5

    def test_odi_suppression(self, confidence_evaluator, error_tracker, odi_result_factory):
        """低 ODI 应抑制置信度"""
        odi_low = odi_result_factory(0.1)
        odi_high = odi_result_factory(0.8)

        conf_low = confidence_evaluator.compute(error_tracker, 0.9, odi_low)
        conf_high = confidence_evaluator.compute(error_tracker, 0.9, odi_high)

        assert conf_low < conf_high

    def test_odi_full_suppression(self, confidence_evaluator, error_tracker, odi_result_factory):
        """ODI < 0.3 应完全抑制（置信度降至最低）"""
        odi = odi_result_factory(0.1)
        conf = confidence_evaluator.compute(error_tracker, 1.0, odi)
        assert conf <= DEFAULT_ANTICIPATION_CONFIG['min_confidence']

    def test_odi_no_gating(self, confidence_evaluator, error_tracker, odi_result_factory):
        """ODI >= 0.5 应不抑制"""
        odi = odi_result_factory(0.8)
        conf = confidence_evaluator.compute(error_tracker, 0.9, odi)
        assert conf > 0.4

    def test_no_odi_no_gating(self, confidence_evaluator, error_tracker):
        """无 ODI 信息时不应门控"""
        conf = confidence_evaluator.compute(error_tracker, 0.9, None)
        assert conf > 0.0


# ─── AnticipatoryBiasEngine: 基本功能 ───

class TestAnticipatoryBiasEngine:
    def test_predict_returns_result(self, engine):
        """predict 应返回 AnticipationResult"""
        result = engine.predict(target_layer=1, horizon=1, timestamp=0)
        assert isinstance(result, AnticipationResult)

    def test_predict_returns_expectation(self, engine):
        """predict 应包含 ExpectationField"""
        result = engine.predict(target_layer=1, horizon=1, timestamp=0)
        assert isinstance(result.expectation, ExpectationField)

    def test_predict_caches_field(self, engine):
        """predict 应缓存预期场"""
        engine.predict(target_layer=1, horizon=1, timestamp=0)
        cached = engine.get_expectation_field(1)
        assert cached is not None

    def test_predict_no_history_gives_low_confidence(self, engine):
        """无历史时置信度应很低"""
        result = engine.predict(target_layer=1, horizon=1, timestamp=0)
        assert result.confidence < 0.4

    def test_update_returns_error(self, engine):
        """update 应返回 PredictionError"""
        engine.predict(target_layer=1, horizon=1, timestamp=0)
        error = engine.update(torch.tensor([1.0, 0.0, 0.0]), timestamp=1)
        assert isinstance(error, PredictionError)

    def test_update_no_prediction_returns_none(self, engine):
        """无预测时 update 应返回 None"""
        error = engine.update(torch.tensor([1.0]), timestamp=0)
        assert error is None

    def test_prediction_accuracy_zero_when_no_predictions(self, engine):
        """无预测时准确率应为 0"""
        assert engine.get_prediction_accuracy() == 0.0

    def test_error_stats(self, engine):
        """误差统计应返回字典"""
        stats = engine.get_error_stats()
        assert isinstance(stats, dict)
        assert 'n_predictions' in stats
        assert 'mean_error' in stats
        assert 'error_trend' in stats


# ─── AnticipatoryBiasEngine: 与 PersistentBiasMemory 集成 ───

class TestAnticipatoryBiasEngineIntegration:
    def test_predict_with_memory_entries(self):
        """有历史偏置条目时应能预测"""
        memory = PersistentBiasMemory()
        engine = AnticipatoryBiasEngine(memory=memory)

        # 使用 record() 添加历史偏置（接受 BiasField）
        for i in range(5):
            bf = BiasField(
                source_layer=0,
                target_layer=1,
                bias_vector=torch.tensor([float(i + 1), 0.0, 0.0]),
                strength=1.0,
                origin_step=i + 1,
            )
            memory.record(bf, timestamp=i + 1)

        result = engine.predict(target_layer=1, horizon=1, timestamp=6)
        assert result.confidence > 0.01
        assert isinstance(result.expectation, ExpectationField)

    def test_predict_update_cycle(self):
        """预测 → 更新 → 再预测的闭环"""
        memory = PersistentBiasMemory()
        engine = AnticipatoryBiasEngine(memory=memory)

        for i in range(5):
            bf = BiasField(
                source_layer=0,
                target_layer=1,
                bias_vector=torch.tensor([float(i + 1), 0.0]),
                strength=1.0,
                origin_step=i + 1,
            )
            memory.record(bf, timestamp=i + 1)

        # 第一次预测
        result1 = engine.predict(target_layer=1, horizon=1, timestamp=6)
        assert result1.expectation.method != 'insufficient_history'

        # 更新
        actual = torch.tensor([6.5, 0.0])
        error = engine.update(actual, timestamp=7, horizon=1)
        assert error is not None

        # 第二次预测
        result2 = engine.predict(target_layer=1, horizon=1, timestamp=8)
        assert isinstance(result2, AnticipationResult)

    def test_odi_gating(self, odi_result_factory):
        """ODI 门控应影响置信度"""
        memory = PersistentBiasMemory()
        engine = AnticipatoryBiasEngine(memory=memory)

        for i in range(5):
            bf = BiasField(
                source_layer=0,
                target_layer=1,
                bias_vector=torch.tensor([float(i + 1), 0.0]),
                strength=1.0,
                origin_step=i + 1,
            )
            memory.record(bf, timestamp=i + 1)

        odi_low = odi_result_factory(0.1)
        odi_high = odi_result_factory(0.8)

        result_low = engine.predict(target_layer=1, horizon=1, timestamp=6, odi_result=odi_low)
        result_high = engine.predict(target_layer=1, horizon=1, timestamp=6, odi_result=odi_high)

        assert result_low.confidence < result_high.confidence

    def test_multi_layer_independence(self):
        """不同目标层的预测应独立"""
        memory = PersistentBiasMemory()
        engine = AnticipatoryBiasEngine(memory=memory)

        for layer in [1, 2]:
            for i in range(5):
                bf = BiasField(
                    source_layer=layer - 1,
                    target_layer=layer,
                    bias_vector=torch.tensor([float(i + 1) * layer, 0.0]),
                    strength=1.0,
                    origin_step=i + 1,
                )
                memory.record(bf, timestamp=i + 1)

        result_l1 = engine.predict(target_layer=1, horizon=1, timestamp=6)
        result_l2 = engine.predict(target_layer=2, horizon=1, timestamp=6)

        # 不同层的预期向量应不同
        assert not torch.allclose(
            result_l1.expectation.expected_vector,
            result_l2.expectation.expected_vector,
        )

    def test_reliability_requires_min_predictions(self):
        """可靠性判定需要最少预测次数"""
        memory = PersistentBiasMemory()
        engine = AnticipatoryBiasEngine(memory=memory)

        for i in range(5):
            bf = BiasField(
                source_layer=0,
                target_layer=1,
                bias_vector=torch.tensor([float(i + 1), 0.0]),
                strength=1.0,
                origin_step=i + 1,
            )
            memory.record(bf, timestamp=i + 1)

        result = engine.predict(target_layer=1, horizon=1, timestamp=6)
        # 预测次数不足时不应判定为可靠
        min_pred = DEFAULT_ANTICIPATION_CONFIG['reliability_min_predictions']
        if result.n_predictions < min_pred:
            assert not result.is_reliable


# ─── ExpectationField 数据类 ───

class TestExpectationField:
    def test_is_reliable(self):
        field = ExpectationField(
            source_layer=0, target_layer=1,
            expected_vector=torch.tensor([1.0]),
            confidence=0.5, horizon=1, timestamp=0, method='linear',
        )
        assert field.is_reliable  # 0.5 > 0.3

    def test_is_not_reliable(self):
        field = ExpectationField(
            source_layer=0, target_layer=1,
            expected_vector=torch.tensor([1.0]),
            confidence=0.1, horizon=1, timestamp=0, method='linear',
        )
        assert not field.is_reliable

    def test_expected_magnitude(self):
        field = ExpectationField(
            source_layer=0, target_layer=1,
            expected_vector=torch.tensor([3.0, 4.0]),
            confidence=0.5, horizon=1, timestamp=0, method='linear',
        )
        assert field.expected_magnitude == pytest.approx(5.0, abs=0.01)


# ─── PredictionError 数据类 ───

class TestPredictionError:
    def test_error_magnitude(self):
        predicted = torch.tensor([1.0, 2.0])
        actual = torch.tensor([4.0, 6.0])
        error = PredictionError(
            timestamp=0, predicted=predicted, actual=actual,
            error_magnitude=5.0, relative_error=1.0, horizon=1,
        )
        assert error.error_magnitude == 5.0


# ─── AnticipationResult 数据类 ───

class TestAnticipationResult:
    def test_repr(self):
        field = ExpectationField(
            source_layer=0, target_layer=1,
            expected_vector=torch.tensor([1.0]),
            confidence=0.5, horizon=1, timestamp=0, method='linear',
        )
        result = AnticipationResult(
            expectation=field, confidence=0.5,
            error_trend=-0.01, n_predictions=10,
            mean_error=0.1, is_reliable=True,
            odi_gated=False, timestamp=0,
        )
        repr_str = repr(result)
        assert 'AnticipationResult' in repr_str
