"""
engine/adaptive_momentum_controller.py — 自适应动量控制器 (AdaptiveMomentumController)

Phase 4 P0 组件（新增）

职责：动态调节叙事动量强度，解决 H4 失败问题（3/8 种子 CIV=2）。

理论依据：
- 差异论 V1.7 "最小变易"原理：变化沿最小总偏移路径
- INSTITUTIONAL 层级是"耦合功能化"（第七环节）的原材料
- 动量不是外部参数，而是系统自身结构状态的函数

核心问题（exp_90 发现）：
- 模式 A（Seed 242/642）：过度稳定陷阱 — INSTITUTIONAL 丰富但动量不足
- 模式 B（Seed 742）：结构碎片化 — 动量过高但分布不均，INSTITUTIONAL 极度匮乏

设计原则：
1. 自适应不能引入"目标函数优化"——必须是纯结构性的反馈
2. 动量调节的响应延迟 ≥ 20 步（避免高频振荡）
3. 调节幅度每步 ≤ 0.05（渐进调节，非突变）
4. momentum_bonus ∈ [0.1, 0.5]（有界）

语义防火墙：
- "自适应" ≠ "学习"（没有梯度下降）
- "动量" ≠ "速度"（是历史模式的持续性强度）
- "调节" ≠ "控制"（是结构反馈，非外部干预）
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

import torch
import numpy as np


# ─── 默认配置 ───
DEFAULT_ADAPTIVE_MOMENTUM_CONFIG = {
    # 动量范围
    'min_momentum_bonus': 0.1,          # 最小动量加成
    'max_momentum_bonus': 0.5,          # 最大动量加成
    'default_momentum_bonus': 0.3,      # 默认/初始动量加成

    # 调节约束
    'max_adjustment_per_step': 0.05,    # 每步最大调节幅度
    'response_delay_steps': 20,         # 响应延迟步数（避免高频振荡）

    # 熵追踪
    'entropy_window': 50,               # 熵计算窗口大小
    'entropy_low_threshold': 0.3,       # 熵低阈值（低于此需要扩散）
    'entropy_high_threshold': 0.7,      # 熵高阈值（高于此需要聚焦）

    # INSTITUTIONAL 密度监控
    'institutional_min_accumulation': 50,  # INSTITUTIONAL 最低积累量
    'institutional_monitor_window': 100,   # 积累速率监控窗口

    # 模式检测
    'stability_trap_threshold': 0.8,    # 过度稳定判定阈值（INSTITUTIONAL 高但 CIV 低）
    'fragmentation_threshold': 0.2,     # 碎片化判定阈值（动量高但 INSTITUTIONAL 低）

    # 调节增益
    'entropy_gain': 0.02,               # 熵偏差 → 动量调节的增益
    'institutional_gain': 0.03,         # INSTITUTIONAL 偏差 → 动量调节的增益
}


@dataclass
class MomentumEntropyTracker:
    """动量熵追踪器 — 追踪 momentum_cache 的熵

    熵衡量动量在叙事范畴间的分布均匀程度：
    - 熵低 → 动量集中在少数范畴（过度聚焦）→ 需要扩散
    - 熵高 → 动量分散在多数范畴（过度分散）→ 需要聚焦

    使用 Shannon 熵：H = -Σ p_i * log(p_i)
    归一化到 [0, 1]：H_norm = H / log(n_categories)
    """

    window_size: int = 50

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_ADAPTIVE_MOMENTUM_CONFIG, **(config or {})}
        self.window_size = cfg['entropy_window']
        self._heat_history: Deque[Dict[str, float]] = deque(maxlen=self.window_size)

    def record(self, category_heats: Dict[str, float]):
        """记录一步的范畴热度分布"""
        self._heat_history.append(dict(category_heats))

    def compute_entropy(self) -> float:
        """计算当前动量分布的归一化 Shannon 熵 [0, 1]"""
        if not self._heat_history:
            return 0.5  # 无数据时返回中性值

        # 聚合窗口内的热度
        total_heats: Dict[str, float] = {}
        for step_heats in self._heat_history:
            for cat, heat in step_heats.items():
                total_heats[cat] = total_heats.get(cat, 0.0) + heat

        if not total_heats:
            return 0.5

        # 归一化为概率分布
        values = np.array(list(total_heats.values()), dtype=np.float64)
        total = values.sum()
        if total < 1e-10:
            return 0.5

        probs = values / total
        probs = probs[probs > 0]  # 移除零概率

        # Shannon 熵
        entropy = -np.sum(probs * np.log(probs + 1e-10))
        max_entropy = np.log(len(probs)) if len(probs) > 1 else 1.0

        normalized = entropy / max_entropy if max_entropy > 0 else 0.0
        return float(np.clip(normalized, 0.0, 1.0))

    @property
    def n_records(self) -> int:
        return len(self._heat_history)


@dataclass
class InstitutionalDensityMonitor:
    """INSTITUTIONAL 密度监控器 — 监控 INSTITUTIONAL 层级积累速率

    追踪 INSTITUTIONAL 层级的积累情况：
    - 积累过缓 → 降低 CIVILIZATION 涌现阈值（增加动量）
    - 积累过快 → 增加保护性约束（降低动量）
    """

    monitor_window: int = 100
    min_accumulation: int = 50

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_ADAPTIVE_MOMENTUM_CONFIG, **(config or {})}
        self.monitor_window = cfg['institutional_monitor_window']
        self.min_accumulation = cfg['institutional_min_accumulation']
        self._accumulation_history: Deque[Tuple[int, int]] = deque(maxlen=self.monitor_window)

    def record(self, institutional_count: int, step: int):
        """记录 INSTITUTIONAL 层级数量"""
        self._accumulation_history.append((step, institutional_count))

    def get_accumulation_rate(self) -> float:
        """计算 INSTITUTIONAL 积累速率（每步增加量）"""
        if len(self._accumulation_history) < 2:
            return 0.0

        values = list(self._accumulation_history)
        steps = [s for s, _ in values]
        counts = [c for _, c in values]

        if len(steps) < 2:
            return 0.0

        step_range = steps[-1] - steps[0]
        if step_range <= 0:
            return 0.0

        count_range = counts[-1] - counts[0]
        return count_range / step_range

    def get_current_count(self) -> int:
        """获取当前 INSTITUTIONAL 数量"""
        if not self._accumulation_history:
            return 0
        return self._accumulation_history[-1][1]

    def is_under_accumulated(self) -> bool:
        """INSTITUTIONAL 是否积累不足"""
        return self.get_current_count() < self.min_accumulation

    def is_over_accumulated(self) -> bool:
        """INSTITUTIONAL 是否积累过度（超过最小值的 3 倍）"""
        return self.get_current_count() > self.min_accumulation * 3


@dataclass
class MomentumState:
    """动量状态快照"""
    momentum_bonus: float               # 当前动量加成
    entropy: float                      # 当前动量熵
    institutional_count: int            # 当前 INSTITUTIONAL 数量
    institutional_rate: float           # INSTITUTIONAL 积累速率
    adjustment: float                   # 上一步调节量
    step: int                           # 当前步数
    mode: str                           # 当前模式：'normal', 'stability_trap', 'fragmentation'


@dataclass
class AdaptiveMomentumResult:
    """自适应动量控制器的输出"""
    momentum_bonus: float               # 调整后的动量加成
    entropy: float                      # 当前动量熵
    institutional_count: int            # 当前 INSTITUTIONAL 数量
    institutional_rate: float           # INSTITUTIONAL 积累速率
    adjustment: float                   # 本次调节量
    mode: str                           # 检测到的模式
    should_diffuse: bool                # 是否需要扩散（熵过低）
    should_focus: bool                  # 是否需要聚焦（熵过高）
    step: int                           # 当前步数
    state: MomentumState                # 完整状态快照


class AdaptiveMomentumController:
    """自适应动量控制器

    根据系统自身结构状态动态调节叙事动量强度。

    三个信息来源：
    1. MomentumEntropyTracker — 动量在范畴间的分布熵
    2. InstitutionalDensityMonitor — INSTITUTIONAL 层级积累速率
    3. 当前 momentum_bonus 值

    两种失败模式的响应策略：
    - 模式 A（过度稳定陷阱）：INSTITUTIONAL 高但动量低 → 增加动量
    - 模式 B（结构碎片化）：动量高但 INSTITUTIONAL 低 → 降低动量 + 增加扩散

    调节约束：
    - 每步调节幅度 ≤ max_adjustment_per_step
    - 响应延迟 ≥ response_delay_steps（前 N 步不调节）
    - momentum_bonus ∈ [min_momentum_bonus, max_momentum_bonus]
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_ADAPTIVE_MOMENTUM_CONFIG, **(config or {})}
        self.config = cfg

        self._entropy_tracker = MomentumEntropyTracker(cfg)
        self._institutional_monitor = InstitutionalDensityMonitor(cfg)

        self._current_momentum_bonus = cfg['default_momentum_bonus']
        self._step_count = 0
        self._last_adjustment = 0.0
        self._adjustment_history: Deque[float] = deque(maxlen=100)

        # 模式检测状态
        self._mode = 'normal'
        self._civ_history: Deque[int] = deque(maxlen=50)

    @property
    def momentum_bonus(self) -> float:
        return self._current_momentum_bonus

    def step(
        self,
        category_heats: Dict[str, float],
        institutional_count: int,
        civilization_count: int = 0,
    ) -> AdaptiveMomentumResult:
        """执行一步自适应动量调节

        Parameters
        ----------
        category_heats : Dict[str, float]
            当前步的叙事范畴热度分布 {category: heat}
        institutional_count : int
            当前 INSTITUTIONAL 层级数量
        civilization_count : int
            当前 CIVILIZATION 层级数量（用于模式检测）

        Returns
        -------
        AdaptiveMomentumResult
            调节结果
        """
        self._step_count += 1

        # 1. 记录观测
        self._entropy_tracker.record(category_heats)
        self._institutional_monitor.record(institutional_count, self._step_count)
        self._civ_history.append(civilization_count)

        # 2. 计算当前熵
        entropy = self._entropy_tracker.compute_entropy()

        # 3. 计算 INSTITUTIONAL 积累速率
        inst_rate = self._institutional_monitor.get_accumulation_rate()

        # 4. 模式检测
        mode = self._detect_mode(institutional_count, civilization_count)

        # 5. 计算调节量
        adjustment = self._compute_adjustment(entropy, institutional_count, inst_rate, mode)

        # 6. 应用调节（受约束）
        if self._step_count > self.config['response_delay_steps']:
            clamped_adjustment = np.clip(
                adjustment,
                -self.config['max_adjustment_per_step'],
                self.config['max_adjustment_per_step'],
            )
            new_bonus = self._current_momentum_bonus + clamped_adjustment
            new_bonus = float(np.clip(
                new_bonus,
                self.config['min_momentum_bonus'],
                self.config['max_momentum_bonus'],
            ))
            actual_adjustment = new_bonus - self._current_momentum_bonus
            self._current_momentum_bonus = new_bonus
        else:
            actual_adjustment = 0.0

        self._last_adjustment = actual_adjustment
        self._adjustment_history.append(actual_adjustment)

        # 7. 构建结果
        state = MomentumState(
            momentum_bonus=self._current_momentum_bonus,
            entropy=entropy,
            institutional_count=institutional_count,
            institutional_rate=inst_rate,
            adjustment=actual_adjustment,
            step=self._step_count,
            mode=mode,
        )

        return AdaptiveMomentumResult(
            momentum_bonus=self._current_momentum_bonus,
            entropy=entropy,
            institutional_count=institutional_count,
            institutional_rate=inst_rate,
            adjustment=actual_adjustment,
            mode=mode,
            should_diffuse=entropy < self.config['entropy_low_threshold'],
            should_focus=entropy > self.config['entropy_high_threshold'],
            step=self._step_count,
            state=state,
        )

    def _detect_mode(self, institutional_count: int, civilization_count: int) -> str:
        """检测当前系统模式

        Returns
        -------
        str
            'normal', 'stability_trap', 或 'fragmentation'
        """
        cfg = self.config

        # 模式 A：过度稳定陷阱
        # INSTITUTIONAL 丰富（> stability_trap_threshold * min_accumulation）但 CIV 低
        if (institutional_count > cfg['institutional_min_accumulation'] * cfg['stability_trap_threshold']
                and civilization_count < 3):
            self._mode = 'stability_trap'
            return self._mode

        # 模式 B：结构碎片化
        # 动量高（> 0.35）但 INSTITUTIONAL 极低
        if (self._current_momentum_bonus > 0.35
                and institutional_count < cfg['institutional_min_accumulation'] * cfg['fragmentation_threshold']):
            self._mode = 'fragmentation'
            return self._mode

        self._mode = 'normal'
        return self._mode

    def _compute_adjustment(
        self,
        entropy: float,
        institutional_count: int,
        institutional_rate: float,
        mode: str,
    ) -> float:
        """计算动量调节量

        纯结构性反馈，无目标函数优化。

        Parameters
        ----------
        entropy : float
            当前动量熵 [0, 1]
        institutional_count : int
            当前 INSTITUTIONAL 数量
        institutional_rate : float
            INSTITUTIONAL 积累速率
        mode : str
            检测到的模式

        Returns
        -------
        float
            动量调节量（正=增加，负=减少）
        """
        cfg = self.config
        adjustment = 0.0

        # ── 熵反馈 ──
        # 熵过低（< low_threshold）→ 动量过度集中 → 需要降低动量（扩散）
        # 熵过高（> high_threshold）→ 动量过度分散 → 需要增加动量（聚焦）
        entropy_mid = (cfg['entropy_low_threshold'] + cfg['entropy_high_threshold']) / 2.0
        entropy_deviation = entropy - entropy_mid  # 正=熵高，负=熵低
        # 熵高 → 需要聚焦 → 增加动量（正调节）
        # 熵低 → 需要扩散 → 减少动量（负调节）
        entropy_adjustment = entropy_deviation * cfg['entropy_gain']
        adjustment += entropy_adjustment

        # ── INSTITUTIONAL 积累反馈 ──
        # 积累不足 → 需要增加动量帮助跨越
        # 积累过度 → 需要降低动量防止消耗
        inst_min = cfg['institutional_min_accumulation']
        if institutional_count < inst_min:
            # 积累不足：增加动量（正调节）
            inst_deficit = (inst_min - institutional_count) / inst_min
            adjustment += inst_deficit * cfg['institutional_gain']
        elif institutional_count > inst_min * 2:
            # 积累过度：降低动量（负调节）
            inst_excess = (institutional_count - inst_min * 2) / (inst_min * 2)
            adjustment -= inst_excess * cfg['institutional_gain']

        # ── 模式特定调节 ──
        if mode == 'stability_trap':
            # 模式 A：INSTITUTIONAL 丰富但 CIV 低 → 增加动量帮助跨越
            adjustment += 0.03  # 温和增加
        elif mode == 'fragmentation':
            # 模式 B：动量高但 INSTITUTIONAL 低 → 降低动量 + 扩散
            adjustment -= 0.04  # 温和减少

        return float(adjustment)

    def get_history(self) -> Dict:
        """获取调节历史"""
        return {
            'current_momentum_bonus': self._current_momentum_bonus,
            'step_count': self._step_count,
            'last_adjustment': self._last_adjustment,
            'mode': self._mode,
            'n_adjustments': len(self._adjustment_history),
            'mean_adjustment': float(np.mean(list(self._adjustment_history))) if self._adjustment_history else 0.0,
            'entropy': self._entropy_tracker.compute_entropy(),
            'institutional_count': self._institutional_monitor.get_current_count(),
            'institutional_rate': self._institutional_monitor.get_accumulation_rate(),
        }

    def reset(self):
        """重置控制器状态"""
        self._current_momentum_bonus = self.config['default_momentum_bonus']
        self._step_count = 0
        self._last_adjustment = 0.0
        self._adjustment_history.clear()
        self._entropy_tracker = MomentumEntropyTracker(self.config)
        self._institutional_monitor = InstitutionalDensityMonitor(self.config)
        self._mode = 'normal'
        self._civ_history.clear()
