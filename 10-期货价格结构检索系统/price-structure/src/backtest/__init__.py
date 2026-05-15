"""
回测框架 — 防泄漏检查 + 指标计算 + 滚动验证

P1 整改：新建回测基础设施，为后续策略验证提供安全框架。
对应内审报告 P1 和待办事项 P1-3（FAISS 检索验证需要回测支撑）。

设计原则：
1. 防泄漏优先 — 任何回测前必须通过 assert_no_future_samples
2. 指标可组合 — 每个指标是独立函数
3. 滚动验证 — WalkForwardValidator 提供标准化的滚动窗口
"""

from src.backtest.leakage import assert_no_future_samples
from src.backtest.metrics import hit_rate, mean_return, max_drawdown, calibration
from src.backtest.walk_forward import WalkForwardValidator

__all__ = [
    "assert_no_future_samples",
    "hit_rate",
    "mean_return",
    "max_drawdown",
    "calibration",
    "WalkForwardValidator",
]
