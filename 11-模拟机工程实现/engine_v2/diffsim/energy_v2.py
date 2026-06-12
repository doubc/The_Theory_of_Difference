"""energy_v2.py -- 能量预算和管理模块 (修正版)。

Phase 21: 为差异论模拟机添加"能量流"维度。
修正: 能量现在直接影响机制执行和密封阈值。

核心概念:
- energy_budget: 当前能量预算
- energy_decay: 每步自然衰减 (热力学第二定律)
- energy_injection: 环境能量注入
- mechanism_cost: 各机制的运行成本
- seal_threshold_modifier: 能量不足时提高密封阈值(更难密封)
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
    seal_thresholds: List[float] = dfield(default_factory=list)

    def record(self, step: int, budget: float, decay: float,
               injection: float, costs: Dict[str, float], seal_threshold: float):
        self.steps.append(step)
        self.budgets.append(budget)
        self.decay_amounts.append(decay)
        self.injection_amounts.append(injection)
        self.mechanism_costs.append(costs)
        self.seal_thresholds.append(seal_threshold)


class EnergyManager:
    """能量管理器。"""

    def __init__(self, config: Optional[EnergyConfig] = None):
        self.config = config or EnergyConfig()
        self.current_budget = self.config.initial_budget
        self.history = EnergyHistory()
        self.is_depleted = False

    def step(self, n_mechanisms: int = 1) -> Dict[str, float]:
        """执行一步能量衰减和注入。
        
        Args:
            n_mechanisms: 激活的机制数量(用于计算总能耗)
            
        Returns:
            包含各项能量变化的字典
        """
        # 1. 能量衰减(热力学第二定律)
        decay_amount = self.current_budget * self.config.decay_rate
        self.current_budget -= decay_amount
        
        # 2. 环境能量注入
        injection_amount = self.config.injection_rate
        self.current_budget += injection_amount
        
        # 3. 机制能耗
        mechanism_costs = {
            'm9': self.config.m9_cost if n_mechanisms > 0 else 0,
            'm3': self.config.m3_cost if n_mechanisms > 1 else 0,
            'm6': self.config.m6_cost if n_mechanisms > 2 else 0,
            'm1': self.config.m1_cost if n_mechanisms > 3 else 0,
        }
        total_mechanism_cost = sum(mechanism_costs.values())
        self.current_budget -= total_mechanism_cost
        
        # 4. 检查能量是否耗尽
        if self.current_budget < self.config.dead_order_threshold:
            self.is_depleted = True
        
        # 5. 计算当前密封阈值调整
        seal_threshold = self.get_adjusted_seal_threshold()
        
        # 6. 记录历史
        self.history.record(
            step=len(self.history.steps),
            budget=self.current_budget,
            decay=decay_amount,
            injection=injection_amount,
            costs=mechanism_costs,
            seal_threshold=seal_threshold
        )
        
        return {
            'decay': decay_amount,
            'injection': injection_amount,
            'mechanism_costs': mechanism_costs,
            'total_cost': total_mechanism_cost,
            'budget_after': self.current_budget,
            'seal_threshold': seal_threshold,
            'is_depleted': self.is_depleted,
        }
    
    def get_adjusted_seal_threshold(self, base_threshold: float = 0.8) -> float:
        """根据能量预算调整密封阈值。
        
        当能量充足时，阈值降低(更容易密封)；
        当能量不足时，阈值升高(更难密封)。
        
        Args:
            base_threshold: 基础密封阈值(默认0.8)
            
        Returns:
            调整后的阈值(范围[0.5, 1.0])
        """
        budget = self.current_budget
        
        # 能量充足(>50): 阈值降低20%
        if budget > 50:
            adjusted = base_threshold * 0.8
        # 能量中等(20-50): 阈值不变
        elif budget > 20:
            adjusted = base_threshold
        # 能量不足(<20): 阈值升高,最高到1.0
        else:
            # 能量越低,阈值越高(最难密封)
            energy_factor = budget / 20.0  # 0-1 范围
            adjusted = base_threshold + (1.0 - base_threshold) * (1.0 - energy_factor)
        
        # 限制在合理范围
        return max(0.5, min(1.0, adjusted))
    
    def can_execute_mechanism(self, mechanism_name: str) -> bool:
        """检查是否有足够能量执行特定机制。
        
        Args:
            mechanism_name: 机制名称 ('m9', 'm3', 'm6', 'm1')
            
        Returns:
            是否有足够能量
        """
        cost_map = {
            'm9': self.config.m9_cost,
            'm3': self.config.m3_cost,
            'm6': self.config.m6_cost,
            'm1': self.config.m1_cost,
        }
        cost = cost_map.get(mechanism_name, 0)
        return self.current_budget >= cost
    
    def get_summary(self) -> Dict:
        """获取能量系统摘要。"""
        if not self.history.steps:
            return {
                'current_budget': self.current_budget,
                'is_depleted': self.is_depleted,
                'n_steps': 0,
            }
        
        return {
            'current_budget': self.current_budget,
            'is_depleted': self.is_depleted,
            'n_steps': len(self.history.steps),
            'initial_budget': self.config.initial_budget,
            'min_budget': min(self.history.budgets),
            'max_budget': max(self.history.budgets),
            'avg_budget': np.mean(self.history.budgets),
            'final_seal_threshold': self.history.seal_thresholds[-1],
        }
