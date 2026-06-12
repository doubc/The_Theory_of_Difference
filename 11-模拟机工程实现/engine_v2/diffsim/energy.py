"""energy.py -- 能量预算和管理模块。

Phase 21: 为差异论模拟机添加"能量流"维度。
能量是驱动九机制齿轮运转的"货币"，消耗于自指(A9)、守恒(m3)、封装(m6)等机制。

核心概念:
- energy_budget: 每层的总能量预算
- energy_decay: 每步自然衰减 (热力学第二定律)
- energy_injection: 环境能量注入
- mechanism_cost: 各机制的运行成本
"""

from __future__ import annotations
from dataclasses import dataclass, field as dfield
from typing import Dict, List, Optional
import numpy as np


@dataclass
class EnergyConfig:
    """能量系统配置。"""
    initial_budget: float = 100.0       # 初始能量预算
    decay_rate: float = 0.01            # 每步衰减率 (1% per step)
    injection_rate: float = 0.5         # 每步环境注入量
    m9_cost: float = 1.0               # 自指(A9)能耗
    m3_cost: float = 0.5               # 守恒(m3)能耗
    m6_cost: float = 0.5               # 封装(m6)能耗
    m1_cost: float = 0.3               # 差异生成(m1)能耗
    low_energy_threshold: float = 10.0  # 低能量警告阈值
    dead_order_threshold: float = 2.0   # 死秩序阈值（能量耗尽）


@dataclass
class EnergyHistory:
    """能量历史记录。"""
    steps: List[int] = dfield(default_factory=list)
    budgets: List[float] = dfield(default_factory=list)
    decay_amounts: List[float] = dfield(default_factory=list)
    injection_amounts: List[float] = dfield(default_factory=list)
    mechanism_costs: List[Dict[str, float]] = dfield(default_factory=list)
    entropy_production: List[float] = dfield(default_factory=list)

    def record(self, step: int, budget: float, decay: float,
               injection: float, costs: Dict[str, float]):
        self.steps.append(step)
        self.budgets.append(budget)
        self.decay_amounts.append(decay)
        self.injection_amounts.append(injection)
        self.mechanism_costs.append(costs)

    def final_budget(self) -> float:
        return self.budgets[-1] if self.budgets else 0.0

    def total_consumed(self) -> float:
        return sum(sum(costs.values()) for costs in self.mechanism_costs)

    def total_injected(self) -> float:
        return sum(self.injection_amounts)

    def total_decayed(self) -> float:
        return sum(self.decay_amounts)


class EnergyManager:
    """能量预算管理器。

    每层 Layer 拥有独立的 EnergyManager。
    能量流: 初始预算 -> [每步衰减 + 环境注入 - 机制能耗] -> 剩余预算
    """

    def __init__(self, config: Optional[EnergyConfig] = None):
        self.config = config or EnergyConfig()
        self.budget = self.config.initial_budget
        self.history = EnergyHistory()
        self._step = 0
        self.is_low_energy = False
        self.is_dead_order = False

    def step(self, active_bits: int, total_bits: int,
             entropy_production: float = 0.0) -> Dict[str, float]:
        """执行一步能量更新。

        Returns:
            costs: 各机制能耗字典
        """
        cfg = self.config

        # 1. 自然衰减
        decay = self.budget * cfg.decay_rate
        self.budget -= decay

        # 2. 环境注入 (与活跃比特数成正比)
        injection = cfg.injection_rate * (active_bits / max(total_bits, 1))
        self.budget += injection

        # 3. 机制能耗 (每步固定成本 = 各机制成本之和)
        mechanism_cost = cfg.m1_cost + cfg.m3_cost + cfg.m6_cost + cfg.m9_cost
        actual = min(mechanism_cost, max(self.budget, 0.0))
        self.budget -= actual
        costs = {
            'decay': decay,
            'injection': injection,
            'mechanism': actual,
        }

        # 4. 记录
        self.history.record(self._step, self.budget, decay, injection, costs)
        self._step += 1

        # 5. 状态检测
        self.is_low_energy = self.budget < cfg.low_energy_threshold
        self.is_dead_order = self.budget < cfg.dead_order_threshold

        return costs

    def consume(self, mechanism: str, amount: float) -> bool:
        """消耗能量。返回是否成功（预算充足）。"""
        if self.budget < amount:
            return False
        self.budget -= amount
        # 更新最近一条历史记录
        if self.history.mechanism_costs:
            self.history.mechanism_costs[-1][mechanism] = amount
        return True

    def inject_burst(self, amount: float):
        """一次性能量注入（例如环境突变）。"""
        self.budget += amount

    def budget_ratio(self) -> float:
        """剩余预算占初始预算的比例。"""
        return self.budget / self.config.initial_budget

    def throttle_factor(self) -> float:
        """节流因子：基于预算比例返回 0.0-1.0 的调制强度。

        能量充足时返回 1.0 (full power)，能量耗尽时返回 0.0 (no power)。
        使用平滑的线性映射：
        - budget_ratio >= 0.5: throttle = 1.0
        - budget_ratio <= 0.1: throttle = 0.0
        - 中间: 线性插值

        这确保机制在能量充足时全功率运行，在能量不足时逐渐减弱。
        """
        ratio = self.budget_ratio()
        if ratio >= 0.5:
            return 1.0
        elif ratio <= 0.1:
            return 0.0
        else:
            # 线性插值: 0.1 -> 0.0, 0.5 -> 1.0
            return (ratio - 0.1) / (0.5 - 0.1)  # (ratio - 0.1) / 0.4

    def summary(self) -> Dict:
        return {
            'final_budget': self.history.final_budget(),
            'total_consumed': self.history.total_consumed(),
            'total_injected': self.history.total_injected(),
            'total_decayed': self.history.total_decayed(),
            'budget_ratio': self.budget_ratio(),
            'is_low_energy': self.is_low_energy,
            'is_dead_order': self.is_dead_order,
            'n_steps': self._step,
        }
