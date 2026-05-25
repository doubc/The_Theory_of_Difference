"""
engine — 差异论模拟机工程核心引擎

核心组件：
- difference_layers.py: 差异分层量化 (D0-D4)
- encapsulation_engine.py: 分层封装引擎
- hierarchy_manager.py: 层级管理器（含 BiasField, LayerState）
- xiang_detector.py: 底象检测器 (Phase 2 P0 #1)
- persistent_bias_memory.py: 历史累积偏置记忆 (Phase 2 P0 #2)
- cumulative_selector.py: 累积筛选器 (Phase 2 P0 #3)
- detectors/: 涌现统计量探测器集
"""

from engine.hierarchy_manager import HierarchyManager, LayerState, BiasField
from engine.encapsulation_engine import EncapsulationEngine, EncapsulatedBit, IndexMapping
from engine.difference_layers import DifferenceLayerAnalyzer, DifferenceLayerReport
from engine.xiang_detector import XiàngDetector, XiangDetectionResult
from engine.persistent_bias_memory import PersistentBiasMemory, BiasEntry, BiasFieldSnapshot
from engine.cumulative_selector import CumulativeSelector, VariantRecord, SelectionResult

__all__ = [
    'HierarchyManager', 'LayerState', 'BiasField',
    'EncapsulationEngine', 'EncapsulatedBit', 'IndexMapping',
    'DifferenceLayerAnalyzer', 'DifferenceLayerReport',
    'XiàngDetector', 'XiangDetectionResult',
    'PersistentBiasMemory', 'BiasEntry', 'BiasFieldSnapshot',
    'CumulativeSelector', 'VariantRecord', 'SelectionResult',
]
