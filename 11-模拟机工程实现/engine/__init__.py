"""
engine — 差异论模拟机工程核心引擎

Phase 1 核心组件：
- long_range_evolver_v2.py: 长程演化器（当前主版本）
- spatial_evolver_v2.py: 空间长程演化器

Phase 2 核心组件（象界→前主体态）：
- encapsulation_engine.py: 分层封装引擎（批次11a）
- hierarchy_manager.py: 层级管理器（批次11b）
- hierarchical_evolver.py: 跨层级演化器（批次11c）
- cross_layer_gravity.py: 跨层级引力调制
- xiang_detector.py: 底象检测器 (Phase 2 P0)
- persistent_bias_memory.py: 历史累积偏置记忆 (Phase 2 P0)
- cumulative_selector.py: 累积筛选器 (Phase 2 P0)
- return_flow_channel.py: 回流通道 (Phase 2 P0)
- organizational_density_index.py: 组织密度指数 (Phase 2 P1)
- six_threshold_detector.py: 六阈值同步检测器 (Phase 2 P1)
- seventh_threshold_detector.py: 第七阈值检测器 (Phase 2 P1)
- unsealing_mechanism.py: 解封机制 (Phase 2 P1)
- pre_subjectivity_convergence.py: 前主体态收束判定 (Phase 2 P1)
- self_sustaining_circulation.py: 自维持循环 (Phase 2 P2)
- functional_differentiation.py: 功能分化 (Phase 2 P2)
- replicate_pattern.py: 复制模式 (Phase 2 P2)
- cooperative_emergence_detector.py: 协同涌现检测器 (Phase 2 P1)
- lateral_coupling.py: 横向耦合机制 (Phase 2 P2)
- functional_signal_coupling.py: 功能信号耦合

Phase 3 组件（前主体态→最小自我）：
- minimal_self_detector.py: 最小自我检测器 (Phase 3 P0)
- anticipatory_bias_engine.py: 预期偏置引擎 (Phase 3 P1)
- counterfactual_engine.py: 反事实引擎 (Phase 3 P2)

探测器：
- detectors/statistics.py: 统计量探测器
"""

# Phase 1: 核心演化（注：long_range_evolver_v2 和 spatial_evolver_v2 为 Phase 1 遗留，
# 当前主路径通过 HierarchicalEvolver 直接调用各 Phase 2/3 组件）

# Phase 2: 层级封装
from engine.encapsulation_engine import EncapsulationEngine, EncapsulatedBit, IndexMapping
from engine.hierarchy_manager import HierarchyManager, LayerState, BiasField
from engine.cross_layer_gravity import CrossLayerGravityModulator

# Phase 2: 底象检测
from engine.xiang_detector import XiàngDetector, XiangDetectionResult
from engine.persistent_bias_memory import PersistentBiasMemory, BiasEntry, BiasFieldSnapshot
from engine.cumulative_selector import CumulativeSelector, VariantRecord, SelectionResult

# Phase 2: 回流通道
from engine.return_flow_channel import (
    ReturnFlowChannel, ReturnFlowEvent, HighSemanticPayload, AnchorPoint,
    SemanticFirewallGuard, SemanticFlowFirewallResult,
)

# Phase 2: 前主体态检测
from engine.organizational_density_index import (
    OrganizationalDensityIndex, DensityIndexResult, SubIndexValues,
    ZoneBoundary, DENSE_ZONES, REFINED_DENSE_ZONES, REFINED_TO_BASE_ZONE,
    DEFAULT_SUBINDEX_WEIGHTS,
)
from engine.six_threshold_detector import SixThresholdDetector, ThresholdStatus, SixThresholdResult
from engine.seventh_threshold_detector import (
    SeventhThresholdDetector, SeventhThresholdResult,
    JumpSignal, CriticalSlowingDownSignal, EmergenceSignature, ZoneTransitionSignal,
)
from engine.unsealing_mechanism import (
    UnsealingMechanism, UnsealingEvent,
    InterfaceExchangeRecord, InterfacePatternStability,
)
from engine.pre_subjectivity_convergence import (
    PreSubjectivityConvergence, ConvergenceResult, CouplingStatus, SemanticFirewallResult,
)

# Phase 2: 象界机制
from engine.self_sustaining_circulation import SelfSustainingCirculation, CirculationState, RebuildAttempt
from engine.functional_differentiation import FunctionalDifferentiation, FunctionalState, ComponentContribution
from engine.replicate_pattern import ReplicatePattern, ReplicationResult, KeyRelation
from engine.cooperative_emergence_detector import (
    CooperativeEmergenceDetector, CooperativeEmergenceResult,
    SynchronizedCrossing, CouplingTopologyTransition, CooperativeOscillation, MutualInformationSurge,
)
from engine.lateral_coupling import (
    LateralCoupler, LateralCouplingPair, LateralCouplingReport,
    CouplingType, StructureHandle, DEFAULT_LATERAL_CONFIG,
)
from engine.functional_signal_coupling import (
    FunctionalSignalSet, FunctionalCouplingMatrix,
    extract_functional_signals, compute_functional_coupling_matrix,
)

# Phase 3: 最小自我
from engine.minimal_self_detector import (
    MinimalSelfDetector, MinimalSelfResult,
    AsymmetrySignal, HistoryDependencySignal, SelfReferenceSignal, DEFAULT_MSI_CONFIG,
)
from engine.anticipatory_bias_engine import (
    AnticipatoryBiasEngine, PatternExtrapolator, PredictionErrorTracker,
    AnticipationConfidence, ExpectationField, PredictionError,
    AnticipationResult, DEFAULT_ANTICIPATION_CONFIG,
)
from engine.counterfactual_engine import (
    CounterfactualEngine, ParallelTrajectoryMaintainer, DivergencePointTracker,
    ConsequenceProjector, CounterfactualSelector,
    TrajectoryNode, TrajectoryBranch, TrajectoryState, DivergenceType, ProjectionMethod,
    DivergencePoint, ConsequenceEstimate, ContrastResult, CounterfactualResult,
    DEFAULT_COUNTERFACTUAL_CONFIG,
)

__all__ = [
    # Phase 2: 层级封装
    'EncapsulationEngine', 'EncapsulatedBit', 'IndexMapping',
    'HierarchyManager', 'LayerState', 'BiasField',
    'CrossLayerGravityModulator',
    # Phase 2: 底象检测
    'XiàngDetector', 'XiangDetectionResult',
    'PersistentBiasMemory', 'BiasEntry', 'BiasFieldSnapshot',
    'CumulativeSelector', 'VariantRecord', 'SelectionResult',
    # Phase 2: 回流通道
    'ReturnFlowChannel', 'ReturnFlowEvent', 'HighSemanticPayload', 'AnchorPoint',
    'SemanticFirewallGuard', 'SemanticFlowFirewallResult',
    # Phase 2: 前主体态检测
    'OrganizationalDensityIndex', 'DensityIndexResult', 'SubIndexValues',
    'ZoneBoundary', 'DENSE_ZONES', 'REFINED_DENSE_ZONES', 'REFINED_TO_BASE_ZONE',
    'DEFAULT_SUBINDEX_WEIGHTS',
    'SixThresholdDetector', 'ThresholdStatus', 'SixThresholdResult',
    'SeventhThresholdDetector', 'SeventhThresholdResult',
    'JumpSignal', 'CriticalSlowingDownSignal', 'EmergenceSignature', 'ZoneTransitionSignal',
    'UnsealingMechanism', 'UnsealingEvent', 'InterfaceExchangeRecord', 'InterfacePatternStability',
    'PreSubjectivityConvergence', 'ConvergenceResult', 'CouplingStatus', 'SemanticFirewallResult',
    # Phase 2: 象界机制
    'SelfSustainingCirculation', 'CirculationState', 'RebuildAttempt',
    'FunctionalDifferentiation', 'FunctionalState', 'ComponentContribution',
    'ReplicatePattern', 'ReplicationResult', 'KeyRelation',
    'CooperativeEmergenceDetector', 'CooperativeEmergenceResult',
    'SynchronizedCrossing', 'CouplingTopologyTransition', 'CooperativeOscillation', 'MutualInformationSurge',
    'LateralCoupler', 'LateralCouplingPair', 'LateralCouplingReport',
    'CouplingType', 'StructureHandle', 'DEFAULT_LATERAL_CONFIG',
    'FunctionalSignalSet', 'FunctionalCouplingMatrix',
    'extract_functional_signals', 'compute_functional_coupling_matrix',
    # Phase 3
    'MinimalSelfDetector', 'MinimalSelfResult',
    'AsymmetrySignal', 'HistoryDependencySignal', 'SelfReferenceSignal', 'DEFAULT_MSI_CONFIG',
    'AnticipatoryBiasEngine', 'PatternExtrapolator', 'PredictionErrorTracker',
    'AnticipationConfidence', 'ExpectationField', 'PredictionError',
    'AnticipationResult', 'DEFAULT_ANTICIPATION_CONFIG',
    'CounterfactualEngine', 'ParallelTrajectoryMaintainer', 'DivergencePointTracker',
    'ConsequenceProjector', 'CounterfactualSelector',
    'TrajectoryNode', 'TrajectoryBranch', 'TrajectoryState', 'DivergenceType', 'ProjectionMethod',
    'DivergencePoint', 'ConsequenceEstimate', 'ContrastResult', 'CounterfactualResult',
    'DEFAULT_COUNTERFACTUAL_CONFIG',
]
