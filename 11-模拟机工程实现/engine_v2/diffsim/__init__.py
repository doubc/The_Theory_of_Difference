"""差异论模拟机 v2 — 自指闭环版 (Self-Referential Closure Edition).
"""

from .core import DifferenceField
from .world import RecursiveWorld
from . import mechanisms
from . import metrics

__all__ = ["DifferenceField", "RecursiveWorld", "mechanisms", "metrics"]
__version__ = "2.0.0"
