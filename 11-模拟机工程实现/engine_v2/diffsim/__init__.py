"""差异论模拟机 v2 — 自指闭环版 (Self-Referential Closure Edition).
Phase 23: 新增 RecursiveWorld + Layer 导出 (接线 m9_self_reference).
Phase 23 P4: 新增 RecursiveNarrativeLoop 导出 (叙事递归工程化).
"""

from .core import DifferenceField
from .world import World
from .world_v2 import Layer, RecursiveWorld, Params
from .narrative_recursion import RecursiveNarrativeLoop, NarrativeState
from . import mechanisms
from . import metrics

__all__ = ["DifferenceField", "World", "Layer", "RecursiveWorld", "Params",
           "RecursiveNarrativeLoop", "NarrativeState",
           "mechanisms", "metrics"]
__version__ = "2.2.0"
