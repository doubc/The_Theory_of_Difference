"""
回测泄漏检查 — 确保没有未来样本泄漏

核心原则：训练集和测试集不能有重叠的时间范围。
任何回测前必须通过此检查。
"""

from __future__ import annotations

from datetime import datetime


def assert_no_future_samples(
    train_end: datetime | str,
    test_start: datetime | str,
    tolerance_days: int = 0,
) -> bool:
    """
    断言训练集截止时间不晚于测试集开始时间

    Args:
        train_end: 训练集截止时间（datetime 或 ISO 字符串）
        test_start: 测试集开始时间（datetime 或 ISO 字符串）
        tolerance_days: 允许的容差天数（默认 0，严格不允许重叠）

    Returns:
        True 如果通过检查

    Raises:
        ValueError: 如果训练集截止时间晚于测试集开始时间（泄漏）
    """
    if isinstance(train_end, str):
        train_end = datetime.fromisoformat(train_end)
    if isinstance(test_start, str):
        test_start = datetime.fromisoformat(test_start)

    delta = (test_start - train_end).days
    if delta < tolerance_days:
        raise ValueError(
            f"未来样本泄漏! 训练截止 {train_end:%Y-%m-%d} "
            f"晚于测试开始 {test_start:%Y-%m-%d} (差距 {delta} 天, 容差 {tolerance_days} 天)"
        )
    return True


def check_sample_leakage(
    train_timestamps: list[datetime],
    test_timestamps: list[datetime],
) -> dict:
    """
    检查两个时间戳列表之间是否有重叠

    Args:
        train_timestamps: 训练集时间戳
        test_timestamps: 测试集时间戳

    Returns:
        {"leak": bool, "overlap_count": int, "overlap_samples": list}
    """
    train_set = set(train_timestamps)
    test_set = set(test_timestamps)
    overlap = train_set & test_set

    return {
        "leak": len(overlap) > 0,
        "overlap_count": len(overlap),
        "overlap_samples": sorted(list(overlap)),
    }
