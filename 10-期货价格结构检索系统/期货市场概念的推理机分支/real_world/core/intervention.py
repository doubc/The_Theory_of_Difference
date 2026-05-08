"""干预机制：制度边界调整。

干预不是外部强制，而是改变系统运行的条件结构，
迫使系统在新的约束下重新组织，形成新的最近稳态。

理论依据：《期货市场的差异论解读》
- 第十三章：制度边界变化可以打破稳态
- 第四章：交易所是"有权力的参与者"
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class InterventionType(str, Enum):
    """干预类型。"""
    MARGIN_ADJUST = "margin_adjust"      # 保证金调整
    CHANNEL_RESTRICT = "channel_restrict"  # 通道限制
    COMPOSITE = "composite"              # 综合干预


@dataclass
class Intervention:
    """制度边界干预事件。
    
    干预改变系统的条件结构，迫使主体在新的约束下重新组织行为。
    """
    time: int                           # 干预发生的时间步
    type: str                           # 干预类型
    target: str                         # 干预目标
    params: Dict[str, float] = field(default_factory=dict)  # 干预参数
    description: str = ""
    
    # 干预效果记录
    pre_state: Dict[str, Any] = field(default_factory=dict)
    post_state: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.description:
            self.description = f"{self.type} 干预 @ t={self.time}"


@dataclass
class InterventionResult:
    """干预执行结果。"""
    intervention: Intervention
    success: bool
    pressure_change: float = 0.0        # 压力变化量
    pressure_change_rate: float = 0.0   # 压力变化率
    stability_improved: bool = False    # 稳态是否改善
    message: str = ""
