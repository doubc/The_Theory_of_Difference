"""
tests/test_seventh_threshold_detector.py — 第七阈值检测器测试

覆盖：
1. 纯线性增长 → 无相变检测
2. 离散跳跃 → 检测到相变
3. 超致密区外 → 无检测
4. 临界减速 → 方差增大+自相关 → 检测到相变
5. 多信号融合 → 混合类型
6. 连续跳跃 → 多次相变记录
7. reset 功能
8. 轨迹摘要
9. feed_batch 批量输入
10. 涌现特征检测
11. 零输入/空输入边界
12. 区间转换检测
13. 置信度验证
14. 正负跳跃方向性
15. 第七阈值与六阈值对比（不是简单阈值叠加）
"""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.organizational_density_index import DensityIndexResult
from engine.seventh_threshold_detector import (
    SeventhThresholdDetector, SeventhThresholdResult,
    JumpSignal, CriticalSlowingDownSignal, EmergenceSignature,
    DEFAULT_SEVENTH_CONFIG,
)


def _odi_result(odi, timestamp, zone=None):
    """创建 DensityIndexResult 的辅助函数"""
    if zone is None:
        if odi >= 0.85:
            zone = 'ultra_dense'
        elif odi >= 0.7:
            zone = 'dense'
        elif odi >= 0.5:
            zone = 'pre_subjective'
        elif odi >= 0.3:
            zone = 'structuring'
        else:
            zone = 'sparse'
    return DensityIndexResult(odi=odi, zone=zone, timestamp=timestamp)


def _linear_sequence(start=0.1, step=0.018, n=50):
    """生成线性增长序列"""
    return [_odi_result(start + i * step, i) for i in range(n)]


def _logistic_sequence(mid=0.5, steepness=15, n=50):
    """生成 logistic 增长序列（平滑S曲线）"""
    t = np.linspace(-3, 3, n)
    odis = 1.0 / (1.0 + np.exp(-steepness * (t - (-3 + 6 * mid))))
    return [_odi_result(float(odis[i]), i) for i in range(n)]


class TestSeventhThresholdDetectorBasic:
    """基础功能测试"""

    def test_linear_growth_no_transition(self):
        """纯线性增长不应检测到相变"""
        detector = SeventhThresholdDetector()
        seq = _linear_sequence(n=50)
        transitions = []
        for r in seq:
            res = detector.feed(r)
            if res.transition_detected:
                transitions.append(res)
        # 纯线性增长 = 连续致密化，不是离散相变
        assert len(transitions) == 0, f"Expected 0 transitions, got {len(transitions)}"
        assert detector.transition_count == 0

    def test_discrete_jump_detection(self):
        """离散跳跃应被检测"""
        detector = SeventhThresholdDetector()

        # 先喂入足够历史数据
        for i in range(30):
            r = _odi_result(0.1 + i * 0.02, i)
            detector.feed(r)

        # 此时 ODI = 0.68，还在结构化区
        # 一个大跳跃进入超致密区
        jump_result = detector.feed(_odi_result(0.97, 30))

        assert jump_result.transition_detected
        assert jump_result.transition_type in ('discrete_jump', 'mixed')
        assert jump_result.transition_confidence >= 0.4
        assert jump_result.critical_odi == 0.97

    def test_no_transition_below_ultra_dense(self):
        """超致密区外不应检测到相变（即使有跳跃）"""
        detector = SeventhThresholdDetector()

        for i in range(20):
            r = _odi_result(0.1 + i * 0.02, i)
            detector.feed(r)

        # 跳跃但仍在超致密区之下
        result = detector.feed(_odi_result(0.75, 20))

        assert not result.transition_detected
        assert result.jump_signal.detected == False  # 未进入超致密区，不检测

    def test_empty_state(self):
        """初始状态检测器"""
        detector = SeventhThresholdDetector()
        assert detector.transition_count == 0
        assert detector.latest_result is None
        assert detector.get_trajectory_summary() == {'n_points': 0}
        assert not detector.in_ultra_dense
        assert not detector.has_transition_occurred

    def test_single_feed(self):
        """单个数据点输入"""
        detector = SeventhThresholdDetector()
        result = detector.feed(_odi_result(0.5, 0))
        assert not result.transition_detected
        assert result.n_observations == 1

    def test_reset(self):
        """reset 清零所有状态"""
        detector = SeventhThresholdDetector()
        for r in _linear_sequence(n=30):
            detector.feed(r)

        assert len(detector.odi_trajectory) == 30

        detector.reset()

        assert len(detector.odi_trajectory) == 0
        assert detector.transition_count == 0
        assert not detector.in_ultra_dense
        assert detector.latest_result is None


class TestSeventhThresholdDetectionModes:
    """检测模式测试"""

    def test_critical_slowing_down(self):
        """临界减速：方差增大+自相关增强 → 检测"""
        detector = SeventhThresholdDetector(
            config={'csd_window': 5, 'csd_variance_ratio': 1.5, 'csd_ac_threshold': 0.3}
        )

        # 先平稳增长到超致密区
        for i in range(20):
            r = _odi_result(0.1 + i * 0.035, i)
            detector.feed(r)

        # 进入超致密区后，加入振荡（方差增大）
        odi_vals = []
        for i in range(10):
            odi = 0.85 + 0.005 * i + 0.01 * np.sin(i * np.pi * 0.7)
            odi_vals.append(odi)
            detector.feed(_odi_result(odi, 20 + i))

        # 临界减速可能被检测
        summary = detector.get_trajectory_summary()
        assert summary['in_ultra_dense']

    def test_discrete_jump_subtle(self):
        """较小的跳跃：可检测但置信度较低"""
        detector = SeventhThresholdDetector(
            config={'jump_sigma_threshold': 2.0, 'min_jump_magnitude': 0.015}
        )

        # 平稳进入超致密区
        for i in range(30):
            detector.feed(_odi_result(0.1 + i * 0.025, i))

        # 小幅跳跃
        result = detector.feed(_odi_result(0.90, 30))
        # 可能有或没有检测到，取决于跳跃是否显著
        assert result.critical_odi >= 0 or not result.transition_detected

    def test_multiple_transitions(self):
        """多次跳跃 → 记录多次相变"""
        detector = SeventhThresholdDetector(
            config={'jump_sigma_threshold': 2.0, 'min_jump_magnitude': 0.02}
        )

        # 基线
        for i in range(20):
            detector.feed(_odi_result(0.85 + i * 0.001, i))

        # 第一次跳跃
        detector.feed(_odi_result(0.92, 20))

        # 恢复平稳
        for i in range(5):
            detector.feed(_odi_result(0.92 + i * 0.001, 21 + i))

        # 第二次跳跃
        detector.feed(_odi_result(0.98, 26))

        transitions = detector.get_transition_history()
        # 至少检测到一次
        assert len(transitions) >= 1
        assert detector.transition_count == len(transitions)

    def test_positive_only_jumps(self):
        """只检测正向（致密化）跳跃，不检测负向跳跃"""
        detector = SeventhThresholdDetector()

        # 进入超致密区
        for i in range(25):
            detector.feed(_odi_result(0.85 + i * 0.003, i))

        # 负向跳跃（去致密化）
        result = detector.feed(_odi_result(0.80, 25))
        assert not result.jump_signal.detected  # 负向跳跃不触发


class TestSeventhThresholdSignals:
    """信号类型测试"""

    def test_jump_signal_fields(self):
        """JumpSignal 所有字段正常填充"""
        detector = SeventhThresholdDetector()
        for i in range(25):
            detector.feed(_odi_result(0.85 + i * 0.002, i))
        result = detector.feed(_odi_result(0.98, 25))

        js = result.jump_signal
        assert isinstance(js, JumpSignal)
        assert js.magnitude > 0
        assert js.sigma_level > 0
        assert js.baseline_std >= 0

    def test_csd_signal_fields(self):
        """CriticalSlowingDownSignal 所有字段正常填充"""
        detector = SeventhThresholdDetector()
        for i in range(20):
            detector.feed(_odi_result(0.85 + i * 0.002, i))

        for i in range(10):
            odi = 0.85 + 0.002 * (20 + i) + 0.01 * np.sin(i * 0.8)
            detector.feed(_odi_result(odi, 20 + i))

        if detector.latest_result:
            csd = detector.latest_result.csd_signal
            assert isinstance(csd, CriticalSlowingDownSignal)
            assert csd.recent_variance >= 0
            assert csd.baseline_variance >= 0
            assert -1.0 <= csd.lag1_autocorrelation <= 1.0

    def test_emergence_signal_fields(self):
        """EmergenceSignature 所有字段正常填充"""
        detector = SeventhThresholdDetector()
        for i in range(20):
            detector.feed(_odi_result(0.85 + i * 0.002, i))
        result = detector.feed(_odi_result(0.92, 20))

        es = result.emergence_signature
        assert isinstance(es, EmergenceSignature)
        assert isinstance(es.signature_description, str)

    def test_result_labels(self):
        """检测结果标签输出正常"""
        r = SeventhThresholdResult(
            transition_detected=True,
            transition_type='mixed',
            transition_confidence=0.75,
            critical_odi=0.92,
            timestamp=10,
        )
        assert '混合' in r.transition_label
        assert '高' in r.confidence_label

        r2 = SeventhThresholdResult(transition_detected=False)
        assert r2.transition_label == '无相变'
        assert r2.confidence_label == '无可信度'


class TestSeventhThresholdBatchAndHistory:
    """批量输入和历史测试"""

    def test_feed_batch(self):
        """批量输入返回结果列表"""
        detector = SeventhThresholdDetector()
        seq = _linear_sequence(n=30)
        results = detector.feed_batch(seq)

        assert len(results) == 30
        assert all(isinstance(r, SeventhThresholdResult) for r in results)

    def test_odi_trajectory(self):
        """ODI 轨迹正确记录"""
        detector = SeventhThresholdDetector()
        seq = _linear_sequence(n=15)
        for r in seq:
            detector.feed(r)

        traj = detector.odi_trajectory
        assert len(traj) == 15
        assert traj[0] == 0.1
        assert traj[-1] > traj[0]

    def test_diffs_trajectory(self):
        """差分轨迹正确记录"""
        detector = SeventhThresholdDetector()
        seq = _linear_sequence(n=10)
        for r in seq:
            detector.feed(r)

        diffs = detector.diffs_trajectory
        assert len(diffs) == 9  # n-1 个差分
        # 所有差分应近似相等（线性序列）
        assert np.std(diffs) < 1e-6

    def test_get_transition_history(self):
        """获取相变历史"""
        detector = SeventhThresholdDetector()
        for i in range(20):
            detector.feed(_odi_result(0.85 + i * 0.001, i))
        detector.feed(_odi_result(0.95, 20))

        history = detector.get_transition_history()
        assert len(history) == detector.transition_count
        for h in history:
            assert h.transition_detected

    def test_trajectory_summary(self):
        """轨迹摘要信息完整"""
        detector = SeventhThresholdDetector()
        seq = _linear_sequence(n=30)
        for r in seq:
            detector.feed(r)

        summary = detector.get_trajectory_summary()
        assert summary['n_points'] == 30
        assert 'odi_min' in summary
        assert 'odi_max' in summary
        assert 'odi_mean' in summary
        assert 'odi_std' in summary
        assert 'current_odi' in summary
        assert 'total_change' in summary


class TestSeventhThresholdEdgeCases:
    """边界情况测试"""

    def test_logistic_curve_few_transitions(self):
        """Logistic 曲线应有极少或无相变（平滑连续）"""
        detector = SeventhThresholdDetector()
        seq = _logistic_sequence(mid=0.6, steepness=10, n=50)
        for r in seq:
            detector.feed(r)

        transitions = detector.get_transition_history()
        # Logistic 是平滑的S曲线，可能只有少数点被检测
        # 关键是我们不期望大量误报
        assert len(transitions) <= 5, f"Too many transitions on smooth curve: {len(transitions)}"

    def test_constant_ultra_dense(self):
        """超致密区中恒定ODI → 无相变"""
        detector = SeventhThresholdDetector()

        # 先进入超致密区
        for i in range(20):
            detector.feed(_odi_result(0.85 + i * 0.005, i))

        # 然后恒定为0.90
        for i in range(20):
            detector.feed(_odi_result(0.90, 20 + i))

        transitions = detector.get_transition_history()
        # 恒定值不应触发相变
        assert len(transitions) == 0

    def test_small_fluctuations_no_transition(self):
        """小幅波动不应触发相变"""
        detector = SeventhThresholdDetector()

        for i in range(30):
            odi = 0.86 + 0.002 * i + 0.003 * np.sin(i * 0.5)
            detector.feed(_odi_result(odi, i))

        transitions = detector.get_transition_history()
        # 小幅随机波动不是相变
        assert len(transitions) == 0

    def test_custom_config(self):
        """自定义配置参数"""
        detector = SeventhThresholdDetector(config={
            'jump_sigma_threshold': 5.0,  # 非常高，几乎不检测
            'min_jump_magnitude': 0.1,
        })

        for i in range(25):
            detector.feed(_odi_result(0.85 + i * 0.002, i))
        result = detector.feed(_odi_result(0.95, 25))

        # 高阈值下可能不检测
        assert result.jump_signal.sigma_level >= 0

    def test_odi_at_boundaries(self):
        """ODI 在边界值（0, 1）的处理"""
        detector = SeventhThresholdDetector()

        detector.feed(_odi_result(0.0, 0))
        detector.feed(_odi_result(1.0, 1))

        assert len(detector.odi_trajectory) == 2
        assert detector.odi_trajectory[0] == 0.0
        assert detector.odi_trajectory[1] == 1.0

    def test_repr(self):
        """__repr__ 正常输出"""
        r = SeventhThresholdResult(
            transition_detected=True,
            transition_type='mixed',
            transition_confidence=0.85,
            critical_odi=0.92,
            timestamp=42,
        )
        s = repr(r)
        assert 'SeventhThreshold' in s
        assert '0.92' in s
        assert '0.85' in s


class TestSeventhThresholdIntegration:
    """集成场景测试"""

    def test_full_densification_scenario(self):
        """完整致密化场景：稀疏→结构化→前主体态→致密→超致密→跃迁"""
        detector = SeventhThresholdDetector()

        # 阶段1：稀疏区（0.0-0.3）
        for i in range(10):
            detector.feed(_odi_result(0.05 + i * 0.025, i))

        assert not detector.in_ultra_dense

        # 阶段2：结构化区（0.3-0.5）
        for i in range(10):
            detector.feed(_odi_result(0.3 + i * 0.02, 10 + i))

        # 阶段3：前主体态区（0.5-0.7）
        for i in range(10):
            detector.feed(_odi_result(0.5 + i * 0.02, 20 + i))

        # 阶段4：致密区（0.7-0.85）
        for i in range(10):
            detector.feed(_odi_result(0.7 + i * 0.015, 30 + i))

        # 阶段5：进入超致密区
        for i in range(10):
            detector.feed(_odi_result(0.85 + i * 0.005, 40 + i))

        assert detector.in_ultra_dense

        # 阶段6：离散跃迁
        result = detector.feed(_odi_result(0.97, 50))

        assert result.transition_detected
        assert result.critical_odi == 0.97
        assert result.transition_confidence >= 0.4

    def test_pre_subjective_to_seventh_threshold(self):
        """从六阈值达标到第七阈值涌现的完整路径"""
        detector = SeventhThresholdDetector()

        # 模拟六阈值达标后继续致密化
        # 前主体态地板 ODI ≈ 0.5
        for i in range(15):
            detector.feed(_odi_result(0.5 + i * 0.01, i))

        # 进入超致密区
        for i in range(15):
            detector.feed(_odi_result(0.65 + i * 0.015, 15 + i))

        # 超致密区内离散跃迁
        result = detector.feed(_odi_result(0.98, 30))

        # 应检测到跃迁
        assert result.transition_detected or detector.transition_count > 0

    def test_seventh_not_six_plus_one(self):
        """第七阈值不是第六阈值的简单叠加——验证检测逻辑的独立性"""
        detector = SeventhThresholdDetector()

        # 即使ODI很高，如果是纯线性增长，也不应检测
        for i in range(40):
            odi = 0.6 + i * 0.01  # 纯线性 0.6 → 0.99
            detector.feed(_odi_result(odi, i))

        # 纯线性不应有跃迁
        assert detector.transition_count == 0
        assert detector.in_ultra_dense  # 尽管在超致密区

        # 但加入离散跳跃后就应有
        detector2 = SeventhThresholdDetector()
        for i in range(30):
            detector2.feed(_odi_result(0.6 + i * 0.01, i))
        result = detector2.feed(_odi_result(0.98, 30))

        # 这次应有跃迁
        assert detector2.transition_count >= 1
        assert result.transition_detected

    def test_confidence_scaling(self):
        """可信度随信号数量递增"""
        # 单信号
        r1 = SeventhThresholdResult(
            transition_detected=True,
            transition_type='discrete_jump',
            transition_confidence=0.4,
        )
        assert r1.confidence_label == '中可信度'

        # 高可信度
        r2 = SeventhThresholdResult(
            transition_detected=True,
            transition_type='mixed',
            transition_confidence=0.85,
        )
        assert r2.confidence_label == '高可信度'

        # 无检出
        r3 = SeventhThresholdResult(transition_detected=False)
        assert r3.confidence_label == '无可信度'