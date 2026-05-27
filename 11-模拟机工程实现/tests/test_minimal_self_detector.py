"""
tests/test_minimal_self_detector.py — 最小自我检测器测试

Phase 3 P0 组件测试

覆盖：
1. 初始状态：无数据，MSI = 0
2. 视角不对称检测（基尼系数）
3. 响应历史依赖检测
4. 自我参照回路检测
5. ODI 门控（ODI < 0.5 时 MSI = 0）
6. MSI 计算（加权几何平均 + ODI 调制）
7. 最小自我涌现判定
8. 三条件全部活跃 → 高 MSI
9. 仅两条件活跃 → 中 MSI
10. 仅一条件活跃 → 不涌现
11. 敏感度分布均匀 → 无不对称
12. 敏感度分布不均匀 → 有不对称
13. 响应不依赖历史 → 无历史依赖
14. 响应依赖历史 → 有历史依赖
15. 响应不影响基线 → 无自我参照
16. 响应影响基线 → 有自我参照
17. ODI 调制效果
18. 涌现历史追踪
19. reset 功能
20. 完整涌现场景（端到端）
"""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.minimal_self_detector import (
    MinimalSelfDetector,
    MinimalSelfResult,
    AsymmetrySignal,
    HistoryDependencySignal,
    SelfReferenceSignal,
    DEFAULT_MSI_CONFIG,
)
from engine.organizational_density_index import DensityIndexResult


class TestMinimalSelfDetector:
    """MinimalSelfDetector 测试套件"""

    def setup_method(self):
        self.detector = MinimalSelfDetector()

    # ─── 初始状态 ───

    def test_initial_state(self):
        """初始状态：无数据，MSI = 0"""
        assert self.detector.current_msi == 0.0
        assert not self.detector.has_minimal_self
        assert self.detector.emergence_count == 0
        assert self.detector.latest_result is None

    def test_empty_feed_returns_zero_msi(self):
        """空输入返回 MSI = 0"""
        result = self.detector.feed()
        assert result.msi == 0.0
        assert not result.minimal_self_detected
        assert result.n_active_conditions == 0

    # ─── 视角不对称检测 ───

    def test_asymmetry_uniform_sensitivity(self):
        """均匀敏感度 → 无不对称"""
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.5, 'B': 0.5, 'C': 0.5}
            )
        result = self.detector.latest_result
        assert not result.asymmetry.detected
        assert result.asymmetry_index < 0.1

    def test_asymmetry_nonuniform_sensitivity(self):
        """非均匀敏感度 → 有不对称"""
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05}
            )
        result = self.detector.latest_result
        assert result.asymmetry.detected
        assert result.asymmetry_index > 0.25

    def test_asymmetry_dominant_and_weakest(self):
        """不对称检测正确识别主导和最弱部分"""
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'X': 0.8, 'Y': 0.2, 'Z': 0.1}
            )
        result = self.detector.latest_result
        assert result.asymmetry.dominant_part == 'X'
        assert result.asymmetry.weakest_part == 'Z'

    def test_asymmetry_min_parts(self):
        """部分数不足时不检测不对称"""
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1}  # 只有2部分，min_parts=3
            )
        result = self.detector.latest_result
        assert not result.asymmetry.detected

    # ─── 历史依赖检测 ───

    def test_history_dependency_no_variance(self):
        """响应不依赖历史 → 无历史依赖"""
        for i in range(10):
            self.detector.feed(
                response_history={
                    'ctx_1': [0.5, 0.5, 0.5],
                    'ctx_2': [0.5, 0.5, 0.5],
                }
            )
        result = self.detector.latest_result
        assert not result.history_dependency.detected

    def test_history_dependency_with_variance(self):
        """响应依赖历史 → 有历史依赖"""
        for i in range(10):
            self.detector.feed(
                response_history={
                    'ctx_1': [0.9, 0.85, 0.95],
                    'ctx_2': [0.1, 0.15, 0.05],
                }
            )
        result = self.detector.latest_result
        assert result.history_dependency.detected
        assert result.history_dependency.dependency_index > 0.3

    def test_history_dependency_single_context(self):
        """单一上下文 → 无法检测历史依赖"""
        for i in range(10):
            self.detector.feed(
                response_history={
                    'ctx_1': [0.5, 0.6, 0.4],
                }
            )
        result = self.detector.latest_result
        assert not result.history_dependency.detected

    # ─── 自我参照检测 ───

    def test_self_reference_no_correlation(self):
        """响应不影响基线 → 无自我参照"""
        np.random.seed(42)
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.5, 'B': 0.5, 'C': 0.5},
                baseline_shift=np.random.randn() * 0.1,  # 随机偏移
            )
        result = self.detector.latest_result
        # 随机偏移不应产生显著相关
        assert not result.self_reference.detected

    def test_self_reference_with_correlation(self):
        """响应影响基线 → 有自我参照"""
        for i in range(10):
            response_val = 0.5 + i * 0.05
            self.detector.feed(
                sensitivity_map={'A': response_val, 'B': response_val * 0.8, 'C': response_val * 0.6},
                baseline_shift=response_val * 0.3,  # 与响应正相关
            )
        result = self.detector.latest_result
        assert result.self_reference.detected
        assert result.self_reference.response_baseline_correlation > 0.3

    def test_self_reference_negative_correlation(self):
        """负相关也是自我参照"""
        for i in range(10):
            response_val = 0.5 + i * 0.05
            self.detector.feed(
                sensitivity_map={'A': response_val, 'B': response_val * 0.8, 'C': response_val * 0.6},
                baseline_shift=-response_val * 0.3,  # 与响应负相关
            )
        result = self.detector.latest_result
        assert result.self_reference.detected

    # ─── ODI 门控 ───

    def test_odi_gate_below_threshold(self):
        """ODI < 0.5 时 MSI = 0（即使三条件都满足）"""
        odi_result = DensityIndexResult(odi=0.3)
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05},
                response_history={
                    'ctx_1': [0.9, 0.85],
                    'ctx_2': [0.1, 0.15],
                },
                baseline_shift=0.3,
                odi_result=odi_result,
            )
        result = self.detector.latest_result
        assert result.msi == 0.0
        assert not result.minimal_self_detected

    def test_odi_gate_above_threshold(self):
        """ODI > 0.5 时允许 MSI 增长"""
        odi_result = DensityIndexResult(odi=0.7)
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05},
                response_history={
                    'ctx_1': [0.9, 0.85],
                    'ctx_2': [0.1, 0.15],
                },
                baseline_shift=0.3,
                odi_result=odi_result,
            )
        result = self.detector.latest_result
        assert result.msi > 0.0

    # ─── MSI 计算 ───

    def test_msi_all_three_conditions(self):
        """三条件全部活跃 → 高 MSI"""
        odi_result = DensityIndexResult(odi=0.8)
        for i in range(10):
            resp_val = 0.3 + i * 0.05
            self.detector.feed(
                sensitivity_map={'A': resp_val * 2, 'B': resp_val * 0.3, 'C': resp_val * 0.1},
                response_history={
                    'ctx_1': [0.9, 0.85],
                    'ctx_2': [0.1, 0.15],
                },
                baseline_shift=resp_val * 0.5,  # 与响应正相关
                odi_result=odi_result,
            )
        result = self.detector.latest_result
        assert result.n_active_conditions == 3
        assert result.msi > 0.35

    def test_msi_two_conditions(self):
        """两条件活跃 → 中 MSI"""
        odi_result = DensityIndexResult(odi=0.7)
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05},
                response_history={
                    'ctx_1': [0.9, 0.85],
                    'ctx_2': [0.1, 0.15],
                },
                odi_result=odi_result,
            )
        result = self.detector.latest_result
        assert result.n_active_conditions == 2

    def test_msi_one_condition_not_emergent(self):
        """仅一条件活跃 → 不涌现"""
        odi_result = DensityIndexResult(odi=0.7)
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05},
                odi_result=odi_result,
            )
        result = self.detector.latest_result
        assert result.n_active_conditions == 1
        assert not result.minimal_self_detected

    # ─── ODI 调制 ───

    def test_odi_modulation_increases_msi(self):
        """更高的 ODI 产生更高的 MSI（其他条件相同）"""
        results = []
        for odi_val in [0.5, 0.6, 0.7, 0.8, 0.9]:
            detector = MinimalSelfDetector()
            odi_result = DensityIndexResult(odi=odi_val)
            for i in range(10):
                detector.feed(
                    sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05},
                    response_history={
                        'ctx_1': [0.9, 0.85],
                        'ctx_2': [0.1, 0.15],
                    },
                    baseline_shift=0.3,
                    odi_result=odi_result,
                )
            results.append(detector.current_msi)

        # MSI 应随 ODI 单调不减
        for i in range(len(results) - 1):
            assert results[i + 1] >= results[i] - 0.01  # 允许微小数值误差

    # ─── 涌现追踪 ───

    def test_emergence_count(self):
        """涌现计数正确"""
        odi_result = DensityIndexResult(odi=0.8)
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05},
                response_history={
                    'ctx_1': [0.9, 0.85],
                    'ctx_2': [0.1, 0.15],
                },
                baseline_shift=0.3,
                odi_result=odi_result,
            )
        # 从第5步开始（min_observations 后）应该持续涌现
        assert self.detector.emergence_count > 0

    def test_emergence_history(self):
        """涌现历史正确记录"""
        odi_result = DensityIndexResult(odi=0.8)
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05},
                response_history={
                    'ctx_1': [0.9, 0.85],
                    'ctx_2': [0.1, 0.15],
                },
                baseline_shift=0.3,
                odi_result=odi_result,
            )
        history = self.detector.get_emergence_history()
        assert len(history) > 0
        assert all(r.minimal_self_detected for r in history)

    def test_msi_trajectory(self):
        """MSI 轨迹正确记录"""
        odi_result = DensityIndexResult(odi=0.8)
        for i in range(5):
            self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05},
                odi_result=odi_result,
            )
        trajectory = self.detector.get_msi_trajectory()
        assert len(trajectory) == 5

    # ─── reset ───

    def test_reset(self):
        """重置后所有状态清零"""
        odi_result = DensityIndexResult(odi=0.8)
        for i in range(10):
            self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05},
                odi_result=odi_result,
            )
        self.detector.reset()
        assert self.detector.current_msi == 0.0
        assert not self.detector.has_minimal_self
        assert self.detector.emergence_count == 0
        assert self.detector.latest_result is None
        assert len(self.detector.get_msi_trajectory()) == 0

    # ─── 完整涌现场景 ───

    def test_full_emergence_scenario(self):
        """端到端：完整的最小自我涌现场景"""
        detector = MinimalSelfDetector()
        odi_result = DensityIndexResult(odi=0.75)

        # 阶段1：初始无结构
        for i in range(5):
            result = detector.feed(odi_result=DensityIndexResult(odi=0.3))
            assert not result.minimal_self_detected

        # 阶段2：逐渐建立不对称
        for i in range(5):
            result = detector.feed(
                sensitivity_map={'A': 0.7 + i * 0.05, 'B': 0.2, 'C': 0.1},
                odi_result=odi_result,
            )

        # 阶段3：加入历史依赖和自我参照
        for i in range(10):
            result = detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.15, 'C': 0.05},
                response_history={
                    'ctx_1': [0.85, 0.9, 0.88],
                    'ctx_2': [0.1, 0.15, 0.08],
                },
                baseline_shift=0.25,
                odi_result=odi_result,
            )

        # 最终应检测到最小自我
        assert result.minimal_self_detected
        assert result.msi > 0.35
        assert result.n_active_conditions >= 2
        assert detector.has_minimal_self

    # ─── 信号摘要 ───

    def test_signal_summary(self):
        """信号摘要正确"""
        odi_result = DensityIndexResult(odi=0.8)
        for i in range(10):
            resp_val = 0.3 + i * 0.05
            self.detector.feed(
                sensitivity_map={'A': resp_val * 2, 'B': resp_val * 0.3, 'C': resp_val * 0.1},
                response_history={
                    'ctx_1': [0.9, 0.85],
                    'ctx_2': [0.1, 0.15],
                },
                baseline_shift=resp_val * 0.5,  # 与响应正相关
                odi_result=odi_result,
            )
        summary = self.detector.get_signal_summary()
        assert summary['n_evaluations'] == 10
        assert summary['asymmetry_triggers'] > 0
        assert summary['history_dependency_triggers'] > 0
        assert summary['self_reference_triggers'] > 0
        assert summary['max_msi'] > 0

    # ─── 描述生成 ───

    def test_description_no_emergence(self):
        """无涌现时描述正确"""
        result = self.detector.feed()
        assert '无最小自我' in result.description

    def test_description_with_emergence(self):
        """涌现时描述正确"""
        odi_result = DensityIndexResult(odi=0.8)
        for i in range(10):
            result = self.detector.feed(
                sensitivity_map={'A': 0.9, 'B': 0.1, 'C': 0.05},
                response_history={
                    'ctx_1': [0.9, 0.85],
                    'ctx_2': [0.1, 0.15],
                },
                baseline_shift=0.3,
                odi_result=odi_result,
            )
        if result.minimal_self_detected:
            assert '最小自我涌现' in result.description
            assert 'MSI=' in result.description

    # ─── 属性测试 ───

    def test_msi_bounds(self):
        """MSI 始终在 [0, 1] 范围内"""
        odi_result = DensityIndexResult(odi=0.9)
        for i in range(20):
            result = self.detector.feed(
                sensitivity_map={'A': np.random.rand(), 'B': np.random.rand(), 'C': np.random.rand()},
                odi_result=odi_result,
            )
            assert 0.0 <= result.msi <= 1.0

    def test_asymmetry_index_bounds(self):
        """不对称指数始终在 [0, 1] 范围内"""
        for i in range(10):
            result = self.detector.feed(
                sensitivity_map={'A': np.random.rand(), 'B': np.random.rand(), 'C': np.random.rand()},
            )
            assert 0.0 <= result.asymmetry_index <= 1.0

    def test_history_dependency_bounds(self):
        """历史依赖度始终在 [0, 1] 范围内"""
        for i in range(10):
            result = self.detector.feed(
                response_history={
                    'ctx_1': list(np.random.rand(5)),
                    'ctx_2': list(np.random.rand(5)),
                }
            )
            assert 0.0 <= result.history_dependency_index <= 1.0

    def test_self_reference_bounds(self):
        """自我参照度始终在 [0, 1] 范围内"""
        for i in range(10):
            result = self.detector.feed(
                sensitivity_map={'A': 0.5, 'B': 0.5, 'C': 0.5},
                baseline_shift=np.random.randn() * 0.1,
            )
            assert 0.0 <= result.self_reference_index <= 1.0

    # ─── 涌现标签 ───

    def test_msi_label(self):
        """MSI 标签正确"""
        result = MinimalSelfResult(msi=0.0)
        assert result.msi_label == '无最小自我'

        result = MinimalSelfResult(msi=0.2)
        assert '萌芽' in result.msi_label

        result = MinimalSelfResult(msi=0.4)
        assert '前最小自我' in result.msi_label

        result = MinimalSelfResult(msi=0.55)
        assert '涌现' in result.msi_label

        result = MinimalSelfResult(msi=0.8)
        assert '稳定' in result.msi_label

    def test_emergence_label(self):
        """涌现标签正确"""
        result = MinimalSelfResult(
            minimal_self_detected=False, n_active_conditions=0
        )
        assert result.emergence_label == '无最小自我信号'

        result = MinimalSelfResult(
            minimal_self_detected=False, n_active_conditions=1
        )
        assert '萌芽' in result.emergence_label

        result = MinimalSelfResult(
            minimal_self_detected=False, n_active_conditions=2
        )
        assert '前兆' in result.emergence_label

        result = MinimalSelfResult(
            minimal_self_detected=True, n_active_conditions=3
        )
        assert '已涌现' in result.emergence_label

    # ─── repr ───

    def test_repr(self):
        """repr 不抛出异常"""
        result = self.detector.feed()
        s = repr(result)
        assert 'MinimalSelf' in s
        assert 'MSI=' in s
