"""
滚动验证 — Walk-Forward Validation

标准的时序滚动窗口验证，确保：
1. 训练窗口始终在测试窗口之前
2. 窗口逐步前移
3. 每个折叠通过泄漏检查

用法:
    from src.backtest.walk_forward import WalkForwardValidator

    validator = WalkForwardValidator(
        data=structures,
        train_window=60,   # 60天训练
        test_window=20,    # 20天测试
        step=20,           # 每次前进20天
    )
    for fold in validator:
        train, test = fold
        # train = 训练集, test = 测试集
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from src.backtest.leakage import assert_no_future_samples


@dataclass
class Fold:
    """一个验证折叠"""
    fold_id: int
    train_data: list[Any]
    test_data: list[Any]
    train_start: datetime | None = None
    train_end: datetime | None = None
    test_start: datetime | None = None
    test_end: datetime | None = None


class WalkForwardValidator:
    """
    滚动验证器 — 时序数据专用的交叉验证

    与普通 K-Fold 不同，Walk-Forward 严格按时间顺序切分：
    - 训练窗口总是在测试窗口之前
    - 窗口每次前进 step 天
    - 每个折叠自动通过泄漏检查
    """

    def __init__(
        self,
        data: list[Any],
        train_window: int = 60,
        test_window: int = 20,
        step: int = 20,
        date_field: str = "t_end",
    ):
        """
        Args:
            data: 带时间戳的数据列表（Structure / dict / 任何有 t_end 属性的对象）
            train_window: 训练窗口天数
            test_window: 测试窗口天数
            step: 步进天数
            date_field: 时间戳字段名（属性或 dict key）
        """
        self.data = sorted(data, key=lambda x: self._get_date(x, date_field))
        self.train_window = train_window
        self.test_window = test_window
        self.step = step
        self.date_field = date_field

    def _get_date(self, item: Any, field: str | None = None) -> datetime:
        """从数据项中提取日期"""
        f = field or self.date_field
        if isinstance(item, dict):
            val = item.get(f)
            if isinstance(val, str):
                return datetime.fromisoformat(val)
            return val
        val = getattr(item, f, None)
        if isinstance(val, str):
            return datetime.fromisoformat(val)
        return val or datetime.min

    def __iter__(self):
        if not self.data:
            return

        start_date = self._get_date(self.data[0])
        end_date = self._get_date(self.data[-1])

        fold_id = 0
        current = start_date

        while current + timedelta(days=self.train_window + self.test_window) <= end_date:
            train_start = current
            train_end = current + timedelta(days=self.train_window)
            test_start = train_end
            test_end = test_start + timedelta(days=self.test_window)

            # 泄漏检查
            try:
                assert_no_future_samples(train_end, test_start)
            except ValueError:
                break

            # 切分数据
            train_data = [
                d for d in self.data
                if train_start <= self._get_date(d) < train_end
            ]
            test_data = [
                d for d in self.data
                if test_start <= self._get_date(d) < test_end
            ]

            if train_data and test_data:
                yield Fold(
                    fold_id=fold_id,
                    train_data=train_data,
                    test_data=test_data,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
                fold_id += 1

            current += timedelta(days=self.step)

    def __len__(self) -> int:
        """预估折叠数"""
        if not self.data:
            return 0
        start = self._get_date(self.data[0])
        end = self._get_date(self.data[-1])
        total_days = (end - start).days
        available = total_days - self.train_window - self.test_window
        if available <= 0:
            return 0
        return max(0, available // self.step + 1)
