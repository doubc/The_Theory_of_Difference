"""差异论模拟机 v2 — 自指闭环版 (Self-Referential Closure Edition).

以"差异论 / 差异即世界"为理论基底，将九个机制实现为显式、可独立检视的
"齿轮"(gears)，并补回原项目缺失的关键动作：

    A9 封装自身 → 完成自指 → 以 L1 作为新的差异源 → 九个机制咬合成闭环

九个机制(高语义表达):
    聚簇 → 层级 → 守恒 → 先天完备性 → 最小变易 → 破缺 → 循环 → 锁定 → 自指
"""
from .core import DifferenceField
from .world import Layer, RecursiveWorld
from . import mechanisms
from . import metrics

__all__ = ["DifferenceField", "Layer", "RecursiveWorld", "mechanisms", "metrics"]
__version__ = "2.0.0"
