"""
engine/institutional_layer_protector.py — INSTITUTIONAL 层级保护器 (InstitutionalLayerProtector)

Phase 4 P0 组件（新增）

职责：保护 INSTITUTIONAL 层级积累不被过早消耗，控制 INSTITUTIONAL → CIVILIZATION
转换的阈值和速率，确保 CIVILIZATION 涌现的原材料充足。

理论依据：
- 差异论 V1.7 "层级涌现不可逆性"：高层级一旦涌现，不应被低层级波动摧毁
- 《象界》八环节咬合："耦合功能化"（第七环节）需要"并存筛选化"（第六环节）的充分发展
- INSTITUTIONAL 层级是"耦合功能化"的原材料

核心问题（exp_90 发现）：
- 模式 A（Seed 242/642）：INSTITUTIONAL 丰富但无法跨越到 CIVILIZATION
  → 需要降低转换阈值，增加 INSTITUTIONAL → CIVILIZATION 的转化效率
- 模式 B（Seed 742）：INSTITUTIONAL 层级被过早消耗
  → 需要增加保护性约束，防止 INSTITUTIONAL 被过快消耗

三个子组件：
1. AccumulationGuard — 保护 INSTITUTIONAL 积累不被过早消耗
2. TransitionGate — 控制 INSTITUTIONAL → CIVILIZATION 的转换
3. DiversityEnforcer — 确保 INSTITUTIONAL 层级的类别多样性

设计原则：
1. 保护不能引入"目标函数优化"——必须是纯结构性的反馈
2. 保护响应延迟 ≥ 10 步（避免高频振荡）
3. 消耗速率限制每步 ≤ 5%（渐进消耗，非突变）
4. 转换阈值必须自适应（不同种子有不同的 INSTITUTIONAL 积累曲线）

语义防火墙：
- "保护" ≠ "保存"（是结构性约束，非外部存储）
- "转换" ≠ "升级"（是层级间的结构重组，非价值判断）
- "多样性" ≠ "丰富性"（是类别数度量，非质性评价）
"""

import math
from typing import Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field

import torch
import numpy as np


# ─── 默认配置 ───
DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG = {
    # INSTITUTIONAL 积累保护
    'min_institutional_floor': 20,      # INSTITUTIONAL 最低地板值（低于此触发强保护）
    'min_institutional_threshold': 35,  # INSTITUTIONAL 最低阈值（低于此触发弱保护）
    'protection_response_delay': 10,    # 保护响应延迟步数

    # 消耗速率限制
    'max_consumption_rate_per_step': 0.10,  # 每步最大消耗比例（10%，exp_92 从 5% 翻倍）
    'consumption_cooldown_steps': 10,        # 消耗冷却步数（exp_92 从 20 减半）

    # 转换门控
    'transition_min_institutional': 25,     # 转换所需最低 INSTITUTIONAL 数量（exp_92 从 40 降低）
    'transition_min_diversity': 2,           # 转换所需最低类别数（exp_92 从 3 降低）
    'transition_min_odi': 0.15,             # 转换所需最低 ODI（exp_92 从 0.5 大幅降低）
    'transition_cooldown_steps': 15,         # 转换冷却步数（exp_92 从 30 减半）

    # 多样性强制
    'min_categories_for_transition': 2,     # 转换所需的最低 INSTITUTIONAL 类别数（exp_92 从 3 降低）
    'diversity_window': 50,                 # 多样性计算窗口

    # 调节增益
    'protection_gain': 0.02,                # 保护强度增益
    'diversity_gain': 0.01,                 # 多样性补偿增益
}


@dataclass
class ProtectionState:
    """保护状态快照"""
    institutional_count: int                # 当前 INSTITUTIONAL 数量
    institutional_floor: float             # 当前地板值（动态）
    consumption_rate_limit: float          # 当前消耗速率限制
    transition_allowed: bool               # 是否允许 INSTITUTIONAL → CIVILIZATION 转换
    transition_openness: float             # 转换门控开放度 [0, 1]
    n_categories: int                      # 当前 INSTITUTIONAL 类别数
    diversity_sufficient: bool             # 多样性是否充足
    protection_level: str                  # 保护级别：'none', 'weak', 'strong'
    step: int                              # 当前步数


@dataclass
class InstitutionalProtectorResult:
    """INSTITUTIONAL 层级保护器的输出"""
    institutional_count: int                # 当前 INSTITUTIONAL 数量
    institutional_floor: float             # 当前地板值
    consumption_rate_limit: float          # 消耗速率限制（每步最大消耗比例）
    transition_allowed: bool               # 是否允许转换
    transition_openness: float             # 转换门控开放度 [0, 1]
    n_categories: int                      # 类别数
    diversity_sufficient: bool             # 多样性是否充足
    protection_level: str                  # 保护级别
    should_consume: bool                   # 当前步是否允许消耗 INSTITUTIONAL
    step: int                              # 当前步数
    state: ProtectionState                 # 完整状态快照


class AccumulationGuard:
    """INSTITUTIONAL 积累守护器

    保护 INSTITUTIONAL 层级不被过早消耗。
    当 INSTITUTIONAL 低于阈值时，降低 CIVILIZATION 消耗 INSTITUTIONAL 的速率。

    理论依据：层级涌现的不可逆性 — 高层级的原材料不应被低层级波动耗尽。
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG, **(config or {})}
        self.min_floor = cfg['min_institutional_floor']
        self.min_threshold = cfg['min_institutional_threshold']
        self.response_delay = cfg['protection_response_delay']
        self.max_consumption_rate = cfg['max_consumption_rate_per_step']
        self.cooldown_steps = cfg['consumption_cooldown_steps']
        self.protection_gain = cfg['protection_gain']

        self._step_count = 0
        self._last_consumption_step = -999
        self._institutional_history: Deque[Tuple[int, int]] = deque(maxlen=self.response_delay * 2)

    def step(self, institutional_count: int) -> Tuple[float, str, bool]:
        """执行一步保护评估

        Parameters
        ----------
        institutional_count : int
            当前 INSTITUTIONAL 层级数量

        Returns
        -------
        Tuple[float, str, bool]
            (consumption_rate_limit, protection_level, should_consume)
            - consumption_rate_limit: 每步最大消耗比例
            - protection_level: 'none', 'weak', 'strong'
            - should_consume: 当前步是否允许消耗
        """
        self._step_count += 1
        self._institutional_history.append((self._step_count, institutional_count))

        # 冷却检查：消耗后需等待冷却期
        steps_since_consumption = self._step_count - self._last_consumption_step
        in_cooldown = steps_since_consumption < self.cooldown_steps

        # 保护级别判定
        if institutional_count < self.min_floor:
            # 强保护：低于地板值
            protection_level = 'strong'
            rate_limit = 0.01  # 几乎不允许消耗
            should_consume = False
        elif institutional_count < self.min_threshold:
            # 弱保护：低于阈值但高于地板
            protection_level = 'weak'
            # 线性插值：从 max_consumption_rate (at threshold) 到 0.01 (at floor)
            ratio = (institutional_count - self.min_floor) / max(1, self.min_threshold - self.min_floor)
            rate_limit = 0.01 + (self.max_consumption_rate - 0.01) * ratio
            should_consume = not in_cooldown and ratio > 0.3
        else:
            # 无保护：充足
            protection_level = 'none'
            rate_limit = self.max_consumption_rate
            should_consume = not in_cooldown

        return rate_limit, protection_level, should_consume

    def record_consumption(self, step: int):
        """记录一次 INSTITUTIONAL 消耗事件"""
        self._last_consumption_step = step

    def get_trend(self) -> float:
        """获取 INSTITUTIONAL 积累趋势（正=增长，负=减少）"""
        if len(self._institutional_history) < 2:
            return 0.0
        values = list(self._institutional_history)
        counts = [c for _, c in values]
        if len(counts) < 2:
            return 0.0
        return (counts[-1] - counts[0]) / len(counts)


class TransitionGate:
    """INSTITUTIONAL → CIVILIZATION 转换门控

    控制 INSTITUTIONAL 层级向 CIVILIZATION 层级的转换。
    要求 INSTITUTIONAL 积累达到最小质量后才能开启转换。

    理论依据：相变需要临界质量 — 没有足够丰富的中间层级，叙事递归无法向上跨越。
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG, **(config or {})}
        self.min_institutional = cfg['transition_min_institutional']
        self.min_diversity = cfg['transition_min_diversity']
        self.min_odi = cfg['transition_min_odi']
        self.cooldown_steps = cfg['transition_cooldown_steps']

        self._last_transition_step = -999
        self._transition_history: Deque[int] = deque(maxlen=10)

    def evaluate(
        self,
        institutional_count: int,
        n_categories: int,
        current_odi: float,
        step: int,
    ) -> Tuple[bool, float]:
        """评估是否允许 INSTITUTIONAL → CIVILIZATION 转换

        Parameters
        ----------
        institutional_count : int
            当前 INSTITUTIONAL 数量
        n_categories : int
            当前 INSTITUTIONAL 类别数
        current_odi : float
            当前 ODI 值
        step : int
            当前步数

        Returns
        -------
        Tuple[bool, float]
            (transition_allowed, openness)
            - transition_allowed: 是否允许转换
            - openness: 转换门控开放度 [0, 1]
        """
        # 冷却检查
        steps_since_transition = step - self._last_transition_step
        in_cooldown = steps_since_transition < self.cooldown_steps

        # 三个条件独立评估
        inst_ok = institutional_count >= self.min_institutional
        div_ok = n_categories >= self.min_diversity
        odi_ok = current_odi >= self.min_odi

        # 开放度 = 满足条件的比例（连续值）
        openness = 0.0
        if institutional_count > 0:
            inst_ratio = min(1.0, institutional_count / self.min_institutional)
            openness += inst_ratio * 0.4  # INSTITUTIONAL 数量权重 40%
        if n_categories > 0:
            div_ratio = min(1.0, n_categories / self.min_diversity)
            openness += div_ratio * 0.3  # 多样性权重 30%
        openness += min(1.0, max(0.0, current_odi / max(0.01, self.min_odi))) * 0.3  # ODI 权重 30%

        # 转换条件：三个条件都满足，且不在冷却期
        transition_allowed = inst_ok and div_ok and odi_ok and not in_cooldown

        if transition_allowed:
            self._last_transition_step = step
            self._transition_history.append(step)

        return transition_allowed, float(np.clip(openness, 0.0, 1.0))

    def get_n_transitions(self) -> int:
        """获取已发生的转换次数"""
        return len(self._transition_history)


class DiversityEnforcer:
    """INSTITUTIONAL 多样性强制器

    确保 INSTITUTIONAL 层级的类别多样性。
    防止单一类别的 INSTITUTIONAL 过度集中（模式 B 的碎片化）。

    理论依据：层级多样性是涌现的必要条件 — 单一类别无法支撑跨尺度的结构耦合。
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG, **(config or {})}
        self.min_categories = cfg['min_categories_for_transition']
        self.diversity_window = cfg['diversity_window']
        self.diversity_gain = cfg['diversity_gain']
        self._category_history: Deque[Dict[str, int]] = deque(maxlen=self.diversity_window)

    def record(self, institutional_categories: Dict[str, int]):
        """记录一步的 INSTITUTIONAL 类别分布

        Parameters
        ----------
        institutional_categories : Dict[str, int]
            类别 → 数量的映射
        """
        self._category_history.append(dict(institutional_categories))

    def get_diversity(self) -> Tuple[int, bool]:
        """获取当前 INSTITUTIONAL 多样性

        Returns
        -------
        Tuple[int, bool]
            (n_categories, is_sufficient)
        """
        if not self._category_history:
            return 0, False

        # 聚合窗口内的类别
        all_categories: Dict[str, int] = {}
        for step_dist in self._category_history:
            for cat, count in step_dist.items():
                all_categories[cat] = all_categories.get(cat, 0) + count

        n_categories = len(all_categories)
        is_sufficient = n_categories >= self.min_categories
        return n_categories, is_sufficient

    def get_diversity_entropy(self) -> float:
        """获取 INSTITUTIONAL 类别分布的归一化熵 [0, 1]"""
        if not self._category_history:
            return 0.0

        all_categories: Dict[str, int] = {}
        for step_dist in self._category_history:
            for cat, count in step_dist.items():
                all_categories[cat] = all_categories.get(cat, 0) + count

        if not all_categories:
            return 0.0

        values = np.array(list(all_categories.values()), dtype=np.float64)
        total = values.sum()
        if total < 1e-10:
            return 0.0

        probs = values / total
        probs = probs[probs > 0]
        entropy = -np.sum(probs * np.log(probs + 1e-10))
        max_entropy = np.log(len(probs)) if len(probs) > 1 else 1.0

        return float(np.clip(entropy / max_entropy if max_entropy > 0 else 0.0, 0.0, 1.0))

    def get_compensation_signal(self) -> float:
        """获取多样性补偿信号

        当多样性不足时，返回正的补偿信号（鼓励增加多样性）。
        当多样性充足时，返回 0。

        Returns
        -------
        float
            补偿信号 [0, 1]
        """
        n_categories, is_sufficient = self.get_diversity()
        if is_sufficient:
            return 0.0

        deficit = (self.min_categories - n_categories) / self.min_categories
        return float(np.clip(deficit * self.diversity_gain, 0.0, self.diversity_gain * 3))


class InstitutionalLayerProtector:
    """INSTITUTIONAL 层级保护器

    保护 INSTITUTIONAL 层级积累，控制 INSTITUTIONAL → CIVILIZATION 转换。

    三个信息来源：
    1. AccumulationGuard — INSTITUTIONAL 积累守护
    2. TransitionGate — 转换门控
    3. DiversityEnforcer — 多样性强制

    设计原则：
    - 纯结构性反馈，无目标函数优化
    - 响应延迟 ≥ 10 步
    - 消耗速率限制每步 ≤ 5%
    - 转换阈值自适应
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG, **(config or {})}
        self.config = cfg

        self._accumulation_guard = AccumulationGuard(cfg)
        self._transition_gate = TransitionGate(cfg)
        self._diversity_enforcer = DiversityEnforcer(cfg)

        self._step_count = 0
        self._current_floor = float(cfg['min_institutional_floor'])

        # 统计追踪（供 get_history 和 exp_91 使用）
        self._final_institutional_count = 0
        self._n_protection_events = 0       # protection_level != 'none' 的次数
        self._n_transitions_allowed = 0
        self._n_transitions_blocked = 0
        self._last_mode = 'init'

    def step(
        self,
        institutional_count: int,
        institutional_categories: Optional[Dict[str, int]] = None,
        current_odi: float = 0.0,
    ) -> InstitutionalProtectorResult:
        """执行一步 INSTITUTIONAL 层级保护

        Parameters
        ----------
        institutional_count : int
            当前 INSTITUTIONAL 层级数量
        institutional_categories : Optional[Dict[str, int]]
            INSTITUTIONAL 类别分布 {category: count}
        current_odi : float
            当前 ODI 值

        Returns
        -------
        InstitutionalProtectorResult
            保护结果
        """
        self._step_count += 1

        # 1. 积累守护
        rate_limit, protection_level, should_consume = self._accumulation_guard.step(
            institutional_count)
        self._last_should_consume = should_consume  # 供外部查询（如 evolver 的 encapsulate 门控）

        # 2. 多样性强制
        if institutional_categories is not None:
            self._diversity_enforcer.record(institutional_categories)
        n_categories, diversity_sufficient = self._diversity_enforcer.get_diversity()
        compensation = self._diversity_enforcer.get_compensation_signal()

        # 3. 转换门控
        transition_allowed, openness = self._transition_gate.evaluate(
            institutional_count=institutional_count,
            n_categories=n_categories,
            current_odi=current_odi,
            step=self._step_count,
        )

        # 4. 动态地板调整
        # 如果多样性不足，提高地板值（更严格保护）
        if not diversity_sufficient:
            self._current_floor = min(
                self.config['min_institutional_threshold'],
                self._current_floor + compensation * 10,
            )
        else:
            # 逐步恢复
            self._current_floor = max(
                float(self.config['min_institutional_floor']),
                self._current_floor - 0.1,
            )

        # 5. 统计追踪（在 transition_allowed 计算之后）
        self._final_institutional_count = institutional_count
        if protection_level != 'none':
            self._n_protection_events += 1
        if transition_allowed:
            self._n_transitions_allowed += 1
        else:
            self._n_transitions_blocked += 1
        self._last_mode = protection_level

        # 6. 构建状态
        state = ProtectionState(
            institutional_count=institutional_count,
            institutional_floor=self._current_floor,
            consumption_rate_limit=rate_limit,
            transition_allowed=transition_allowed,
            transition_openness=openness,
            n_categories=n_categories,
            diversity_sufficient=diversity_sufficient,
            protection_level=protection_level,
            step=self._step_count,
        )

        return InstitutionalProtectorResult(
            institutional_count=institutional_count,
            institutional_floor=self._current_floor,
            consumption_rate_limit=rate_limit,
            transition_allowed=transition_allowed,
            transition_openness=openness,
            n_categories=n_categories,
            diversity_sufficient=diversity_sufficient,
            protection_level=protection_level,
            should_consume=should_consume,
            step=self._step_count,
            state=state,
        )

    @property
    def should_consume(self) -> bool:
        """当前是否允许消耗 INSTITUTIONAL（供外部门控查询）"""
        return getattr(self, '_last_should_consume', True)

    def record_consumption(self):
        """记录一次 INSTITUTIONAL 消耗事件"""
        self._accumulation_guard.record_consumption(self._step_count)

    def get_history(self) -> Dict:
        """获取保护历史"""
        n_categories, diversity_ok = self._diversity_enforcer.get_diversity()
        return {
            'step_count': self._step_count,
            'institutional_count': self._final_institutional_count,
            'institutional_floor': self._current_floor,
            'accumulation_trend': self._accumulation_guard.get_trend(),
            'n_transitions': self._transition_gate.get_n_transitions(),
            'n_protection_events': self._n_protection_events,
            'n_transitions_allowed': self._n_transitions_allowed,
            'n_transitions_blocked': self._n_transitions_blocked,
            'n_categories': n_categories,
            'diversity_sufficient': diversity_ok,
            'diversity_entropy': self._diversity_enforcer.get_diversity_entropy(),
            'mode': self._last_mode,
        }

    def reset(self):
        """重置保护器状态"""
        cfg = self.config
        self._step_count = 0
        self._current_floor = float(cfg['min_institutional_floor'])
        self._accumulation_guard = AccumulationGuard(cfg)
        self._transition_gate = TransitionGate(cfg)
        self._diversity_enforcer = DiversityEnforcer(cfg)
