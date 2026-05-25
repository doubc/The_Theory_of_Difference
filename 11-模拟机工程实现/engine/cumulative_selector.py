"""
engine/cumulative_selector.py — 累积筛选器 (CumulativeSelector)

Phase 2 P0 组件 #3

职责：追踪多次展开中的延续概率差异，区分"偶然保留"与"趋势形成"。

理论依据：
- 《象界》第六章：并存 → 筛选
- 核心洞见："一次保留未必构成趋势，多次保留才会形成偏向。"
- 累积窗口 + 多次保留趋势 = 区分"偶然"与"趋势"

与 M4 单次跃迁判断的区别：
- M4：单次跃迁判断（是否跨过门槛）
- CumulativeSelector：累积窗口内的趋势分析（是否形成方向）
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class VariantRecord:
    """单个变体的延续记录"""
    variant_id: str
    continuation_history: List[bool] = field(default_factory=list)
    creation_step: int = 0
    last_seen_step: int = 0
    metadata: Dict = field(default_factory=dict)

    @property
    def n_observations(self) -> int:
        return len(self.continuation_history)

    @property
    def n_retained(self) -> int:
        return sum(1 for r in self.continuation_history if r)

    def retention_rate(self, window: Optional[int] = None) -> float:
        """计算保留率（可选窗口）"""
        if window is not None and window < len(self.continuation_history):
            recent = self.continuation_history[-window:]
        else:
            recent = self.continuation_history
        if not recent:
            return 0.0
        return sum(1 for r in recent if r) / len(recent)

    def __repr__(self):
        rate = self.retention_rate()
        return (f"VariantRecord({self.variant_id}, "
                f"obs={self.n_observations}, retained={self.n_retained}, "
                f"rate={rate:.2f})")


@dataclass
class SelectionResult:
    """筛选结果"""
    variant_id: str
    trend_score: float = 0.0       # 趋势评分 [0, 1]
    is_trend_forming: bool = False  # 是否形成趋势
    fate_probability: float = 0.0   # 累积延续概率
    n_observations: int = 0         # 观察次数
    is_retained: bool = False       # 本次是否被保留


class CumulativeSelector:
    """累积筛选器

    追踪多次展开中的延续概率差异，区分"偶然保留"与"趋势形成"。

    核心算法：
    1. 记录每次展开中各变体是否被保留
    2. 计算最近 window_size 次的保留频率 → 趋势评分
    3. 保留频率超过 trend_threshold → 判定为趋势形成
    4. 追踪所有变体的累积延续概率（命运分岔）
    """

    def __init__(self, window_size: int = 10,
                 trend_threshold: float = 0.6,
                 min_observations: int = 3,
                 fate_decay: float = 0.99):
        """
        Args:
            window_size: 累积窗口大小
            trend_threshold: 趋势判定阈值（保留频率超过此值判定为趋势）
            min_observations: 最少观察次数（少于此数不做趋势判定）
            fate_decay: 命运概率衰减因子（旧观察的影响力衰减）
        """
        self.window_size = window_size
        self.trend_threshold = trend_threshold
        self.min_observations = min_observations
        self.fate_decay = fate_decay

        # 变体记录 {variant_id: VariantRecord}
        self._variants: Dict[str, VariantRecord] = {}

        # 命运分岔 {variant_id: 累积延续概率}
        self._fate_branches: Dict[str, float] = {}

        # 筛选历史
        self._selection_history: List[SelectionResult] = []

        # 步数计数
        self._step_count: int = 0
        self._next_variant_num: int = 0

    def record_continuation(self, variant_id: str, retained: bool,
                            step: Optional[int] = None) -> SelectionResult:
        """记录一次延续结果

        Args:
            variant_id: 变体标识
            retained: 是否被保留
            step: 当前步数（不传则自动递增）

        Returns:
            SelectionResult 筛选结果
        """
        if step is not None:
            self._step_count = step
        else:
            self._step_count += 1

        # 获取或创建变体记录
        if variant_id not in self._variants:
            self._variants[variant_id] = VariantRecord(
                variant_id=variant_id,
                creation_step=self._step_count,
            )

        record = self._variants[variant_id]
        record.continuation_history.append(retained)
        record.last_seen_step = self._step_count

        # 计算趋势评分
        trend_score = self._compute_trend_score(record)

        # 判定是否形成趋势
        is_trend_forming = (record.n_observations >= self.min_observations and
                            trend_score > self.trend_threshold)

        # 更新命运分岔
        fate_probability = self._update_fate_branch(variant_id, retained)

        result = SelectionResult(
            variant_id=variant_id,
            trend_score=trend_score,
            is_trend_forming=is_trend_forming,
            fate_probability=fate_probability,
            n_observations=record.n_observations,
            is_retained=retained,
        )

        self._selection_history.append(result)
        return result

    def get_trend(self, variant_id: str) -> Optional[float]:
        """获取某变体的趋势评分（最近 window_size 次的保留频率）

        Args:
            variant_id: 变体标识

        Returns:
            trend_score: 趋势评分，变体不存在则返回 None
        """
        if variant_id not in self._variants:
            return None
        return self._compute_trend_score(self._variants[variant_id])

    def is_trend_forming(self, variant_id: str) -> bool:
        """某变体是否已形成趋势

        Args:
            variant_id: 变体标识

        Returns:
            is_trend: 是否形成趋势
        """
        if variant_id not in self._variants:
            return False
        record = self._variants[variant_id]
        if record.n_observations < self.min_observations:
            return False
        trend_score = self._compute_trend_score(record)
        return trend_score > self.trend_threshold

    def get_fate_divergence(self) -> Dict[str, float]:
        """获取所有变体的命运分岔（累积延续概率差异）

        Returns:
            fate_branches: {variant_id: 累积延续概率}
        """
        return dict(self._fate_branches)

    def get_dominant_variants(self, top_k: int = 5) -> List[Tuple[str, float]]:
        """获取主导变体（趋势评分最高的 K 个）

        Returns:
            [(variant_id, trend_score), ...] 按趋势评分降序
        """
        scores = []
        for vid, record in self._variants.items():
            if record.n_observations >= self.min_observations:
                score = self._compute_trend_score(record)
                scores.append((vid, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def create_variant(self, prefix: str = "v") -> str:
        """创建新变体

        Args:
            prefix: 变体 ID 前缀

        Returns:
            variant_id: 新变体的唯一标识
        """
        variant_id = f"{prefix}_{self._next_variant_num:06d}"
        self._next_variant_num += 1
        self._variants[variant_id] = VariantRecord(
            variant_id=variant_id,
            creation_step=self._step_count,
        )
        return variant_id

    @property
    def n_variants(self) -> int:
        """总变体数"""
        return len(self._variants)

    @property
    def n_trending(self) -> int:
        """已形成趋势的变体数"""
        return sum(1 for vid in self._variants if self.is_trend_forming(vid))

    def get_summary(self) -> Dict:
        """获取摘要"""
        return {
            'n_variants': self.n_variants,
            'n_trending': self.n_trending,
            'n_selections': len(self._selection_history),
            'step_count': self._step_count,
            'top_variants': self.get_dominant_variants(5),
            'fate_divergence': self.get_fate_divergence(),
        }

    def _compute_trend_score(self, record: VariantRecord) -> float:
        """计算趋势评分"""
        if record.n_observations == 0:
            return 0.0
        return record.retention_rate(self.window_size)

    def _update_fate_branch(self, variant_id: str, retained: bool) -> float:
        """更新命运分岔

        使用指数加权移动平均计算累积延续概率。
        """
        if variant_id not in self._fate_branches:
            self._fate_branches[variant_id] = 0.5  # 初始均匀概率

        current = self._fate_branches[variant_id]
        # 指数更新：P_new = decay * P_old + (1 - decay) * observation
        observation = 1.0 if retained else 0.0
        new_prob = self.fate_decay * current + (1.0 - self.fate_decay) * observation
        self._fate_branches[variant_id] = new_prob

        return new_prob

    def reset(self):
        """重置所有状态"""
        self._variants.clear()
        self._fate_branches.clear()
        self._selection_history.clear()
        self._step_count = 0
        self._next_variant_num = 0
