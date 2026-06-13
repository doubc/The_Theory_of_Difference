"""差异论模拟机 v2 — 自指闭环版 (Self-Referential Closure Edition).
"""

from .core import DifferenceField
from .world import World
from . import mechanisms
from . import metrics

__all__ = ["DifferenceField", "World", "mechanisms", "metrics"]
__version__ = "2.0.0"
