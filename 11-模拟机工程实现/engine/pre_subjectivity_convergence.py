"""
engine/pre_subjectivity_convergence.py — 前主体态收束判定 (PreSubjectivityConvergence)

Phase 2 P1 组件 #2

职责：判定六机制是否已耦合收束为可承受高语义加载的组织整体。

理论依据：
- 《象界》第八章：前主体态
- 《Appearing Before Appearing》§4：前主体态是主体性的结构地板
- "前主体态不是主体，却是差异结构在低语义层中所能达到的最充分完成形态。"

收束条件（必须同时满足）：
1. 六阈值全部达标（SixThresholdDetector 通过）
2. 各机制之间的耦合强度超过阈值（相互依赖度）
3. 组织整体的稳定性（在扰动下保持结构的能力）
4. 语义防火墙：注入高语义扰动后，结构不发生崩塌

语义防火墙（严格克制）：
  - 不引入"身份"概念（只有边界，没有身份）
  - 不引入"意志"概念（只有自维持，没有意志）
  - 不引入"回忆"概念（只有保持，没有回忆）
  - 不引入"自我表征"概念（只有复制，没有自我表征）
  - 不引入"评价"概念（只有选择，没有评价）
  - 不引入"意义赋予"概念（只有功能，没有意义）
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from engine.six_threshold_detector import SixThresholdDetector, SixThresholdResult


# ─── 语义防火墙常量 ───
# 这些关键词不应出现在前主体态的任何结构描述中
SEMANTIC_FIREWALL_FORBIDDEN = {
    'identity', 'identity_boundary', 'self_identity',  # 身份
    'will', 'volition', 'intention', 'desire',          # 意志
    'recollection', 'reminiscence', 'episodic_memory',  # 回忆
    'self_representation', 'self_model', 'self_aware',  # 自我表征
    'evaluation', 'judgment', 'value_judgment',         # 评价
    'meaning', 'significance', 'purpose', 'teleology',  # 意义赋予
}

# 允许的结构对应
SEMANTIC_FIREWALL_ALLOWED = {
    'boundary',           # 边界（不是身份边界）
    'self_sustaining',    # 自维持（不是意志）
    'retention',          # 保持（不是回忆）
    'replication',        # 复制（不是自我表征）
    'selection',          # 筛选（不是评价）
    'function',           # 功能（不是意义）
}


@dataclass
class CouplingStatus:
    """耦合强度状态"""
    mechanism_a: str
    mechanism_b: str
    coupling_strength: float = 0.0
    is_coupled: bool = False

    def __repr__(self):
        status = "coupled" if self.is_coupled else "uncoupled"
        return f"{self.mechanism_a} ↔ {self.mechanism_b}: {self.coupling_strength:.4f} ({status})"


@dataclass
class SemanticFirewallResult:
    """语义防火墙检测结果"""
    passed: bool = True
    violations: List[str] = field(default_factory=list)
    n_checked: int = 0

    def __repr__(self):
        if self.passed:
            return f"SemanticFirewall[PASSED] (checked {self.n_checked} fields)"
        return f"SemanticFirewall[FAILED] violations: {self.violations}"


@dataclass
class ConvergenceResult:
    """前主体态收束判定结果"""
    converged: bool = False                 # 是否收束
    six_thresholds_met: bool = False        # 六阈值是否达标
    coupling_strength_met: bool = False     # 耦合强度是否达标
    stability_met: bool = False             # 稳定性是否达标
    semantic_firewall_passed: bool = True   # 语义防火墙是否通过
    n_coupled_pairs: int = 0               # 耦合的机制对数
    min_coupling: float = 0.0              # 最小耦合强度
    stability_score: float = 0.0           # 稳定性评分
    timestamp: int = 0

    @property
    def all_conditions_met(self) -> bool:
        """所有条件是否同时满足"""
        return (self.six_thresholds_met and
                self.coupling_strength_met and
                self.stability_met and
                self.semantic_firewall_passed)

    def __repr__(self):
        if self.converged:
            return (f"Convergence[CONVERGED] "
                    f"coupled_pairs={self.n_coupled_pairs}, "
                    f"stability={self.stability_score:.3f}")
        conditions = []
        if not self.six_thresholds_met:
            conditions.append("thresholds")
        if not self.coupling_strength_met:
            conditions.append("coupling")
        if not self.stability_met:
            conditions.append("stability")
        if not self.semantic_firewall_passed:
            conditions.append("firewall")
        return f"Convergence[NOT_CONVERGED] missing: {', '.join(conditions)}"


class PreSubjectivityConvergence:
    """前主体态收束判定

    判定六机制是否已耦合收束为可承受高语义加载的组织整体。

    收束条件：
    1. 六阈值全部达标（SixThresholdDetector 通过）
    2. 各机制之间的耦合强度超过阈值（相互依赖度）
    3. 组织整体的稳定性（在扰动下保持结构的能力）
    4. 语义防火墙：注入高语义扰动后，结构不发生崩塌

    理论边界：
    - 前主体态不是主体
    - 前主体态是差异结构在低语义层中所能达到的最充分完成形态
    - 从结构到现象的过渡是"组织密度连续增长"，不是尖锐边界
    """

    # 六个机制名称（与 SixThresholdDetector 的阈值一一对应）
    MECHANISMS = [
        'interface_regulation',      # 3.1 界面调节
        'self_sustaining',           # 3.2 自维持
        'retention',                 # 3.3 保持
        'replication',               # 3.4 复制
        'selection',                 # 3.5 筛选
        'functional_differentiation', # 3.6 功能分化
    ]

    # ── 默认耦合权重（核心机制对权重更高） ──
    # 基于象界功能分化理论：核心三对（界面↔自维持、自维持↔保持、保持↔复制）
    # 对结构稳定贡献最大，权重更高。
    DEFAULT_COUPLING_WEIGHTS: Dict[str, float] = {
        # 核心三对（权重 2.0）
        'interface_regulation:self_sustaining': 2.0,
        'self_sustaining:retention': 2.0,
        'retention:replication': 2.0,
        # 扩展三对（权重 1.5）
        'interface_regulation:replication': 1.5,
        'self_sustaining:selection': 1.5,
        'retention:functional_differentiation': 1.5,
        # 其余九对（权重 1.0）
        'interface_regulation:selection': 1.0,
        'interface_regulation:functional_differentiation': 1.0,
        'self_sustaining:functional_differentiation': 1.0,
        'self_sustaining:replication': 1.0,
        'replication:selection': 1.0,
        'replication:functional_differentiation': 1.0,
        'selection:functional_differentiation': 1.0,
        'interface_regulation:retention': 1.0,
        'retention:selection': 1.0,
        'self_sustaining:interface_regulation': 2.0,
        'retention:self_sustaining': 2.0,
        'replication:retention': 2.0,
        'replication:interface_regulation': 1.5,
        'selection:self_sustaining': 1.5,
        'functional_differentiation:retention': 1.5,
        'selection:interface_regulation': 1.0,
        'functional_differentiation:interface_regulation': 1.0,
        'functional_differentiation:self_sustaining': 1.0,
        'replication:self_sustaining': 1.0,
        'selection:replication': 1.0,
        'functional_differentiation:replication': 1.0,
        'functional_differentiation:selection': 1.0,
        'retention:interface_regulation': 1.0,
        'selection:retention': 1.0,
    }

    # ── 动态耦合阈值参数（P1 方案） ──
    # 根据活跃比特数自适应调整阈值：
    #   N_active ≤ 12  → threshold = base × 0.50  (更宽松，信号弱)
    #   N_active ≤ 24  → threshold = base × 0.75  (适度宽松)
    #   N_active > 24  → threshold = base × 1.00  (基准)
    DYNAMIC_THRESHOLD_SCALE_LOW = 0.50    # N_active ≤ 12
    DYNAMIC_THRESHOLD_SCALE_MID = 0.75    # N_active ≤ 24
    DYNAMIC_THRESHOLD_SCALE_HIGH = 1.00   # N_active > 24
    DYNAMIC_THRESHOLD_N_LOW = 12
    DYNAMIC_THRESHOLD_N_MID = 24

    def __init__(self,
                 coupling_threshold: float = 0.3,
                 stability_threshold: float = 0.5,
                 n_perturbation_tests: int = 5,
                 perturbation_scale: float = 0.1,
                 coupling_mode: str = "all",
                 coupling_weights: Optional[Dict[str, float]] = None,
                 dynamic_threshold: bool = False):
        """
        Args:
            coupling_threshold: 耦合强度阈值（超过此值认为两机制耦合）
            stability_threshold: 稳定性阈值（扰动后保持结构的比例）
            n_perturbation_tests: 扰动测试次数
            perturbation_scale: 扰动强度
            coupling_mode: 耦合判定模式
                "all"     — 所有机制对都必须超过阈值（默认，15/15）
                "majority" — 多数机制对超过阈值（≥12/15）
                "weighted" — 加权评分模式（核心机制对权重更高）
            coupling_weights: 耦合权重字典，键为 "mech_a:mech_b" 格式。
                如果为 None，使用 DEFAULT_COUPLING_WEIGHTS。
                仅在 coupling_mode="weighted" 时使用。
            dynamic_threshold: 是否启用动态耦合阈值（根据 N_active 自适应调整）。
                启用后，实际阈值 = coupling_threshold × scale(N_active)。
                这解决了"活跃比特少时信号弱导致耦合被系统性低估"的问题。
        """
        self.coupling_threshold = coupling_threshold
        self.stability_threshold = stability_threshold
        self.n_perturbation_tests = n_perturbation_tests
        self.perturbation_scale = perturbation_scale
        self.coupling_mode = coupling_mode
        self.coupling_weights = coupling_weights or self.DEFAULT_COUPLING_WEIGHTS.copy()
        self.dynamic_threshold = dynamic_threshold

        # 六阈值检测器
        self._threshold_detector = SixThresholdDetector()

        # 耦合矩阵历史
        self._coupling_history: List[Dict[str, float]] = []

        # 检测结果历史
        self._convergence_history: List[ConvergenceResult] = []

        self._step_count: int = 0

    def _get_dynamic_threshold(self, n_active: Optional[int] = None) -> float:
        """计算动态耦合阈值

        根据活跃比特数自适应调整阈值：
          N_active ≤ 12  → base × 0.50
          N_active ≤ 24  → base × 0.75
          N_active > 24  → base × 1.00

        Args:
            n_active: 活跃比特数。如果为 None 或 dynamic_threshold=False，
                      返回基准阈值。

        Returns:
            实际耦合阈值
        """
        if not self.dynamic_threshold or n_active is None:
            return self.coupling_threshold

        if n_active <= self.DYNAMIC_THRESHOLD_N_LOW:
            scale = self.DYNAMIC_THRESHOLD_SCALE_LOW
        elif n_active <= self.DYNAMIC_THRESHOLD_N_MID:
            scale = self.DYNAMIC_THRESHOLD_SCALE_MID
        else:
            scale = self.DYNAMIC_THRESHOLD_SCALE_HIGH

        return self.coupling_threshold * scale

    def evaluate(self,
                 # 六阈值检测参数（透传给 SixThresholdDetector）
                 threshold_params: Optional[Dict] = None,
                 # 耦合强度矩阵（机制间的相互依赖度）
                 coupling_matrix: Optional[Dict[str, Dict[str, float]]] = None,
                 # 结构状态（用于稳定性测试）
                 structure_state: Optional[torch.Tensor] = None,
                 # 结构保持函数（用于扰动测试）
                 structure_fn: Optional[callable] = None,
                 # 待检查的字段名（语义防火墙）
                 field_names: Optional[List[str]] = None,
                 # 时间戳
                 timestamp: Optional[int] = None,
                 # 活跃比特数（用于动态耦合阈值）
                 n_active: Optional[int] = None,
                 ) -> ConvergenceResult:
        """执行前主体态收束判定

        Args:
            threshold_params: 六阈值检测参数（透传给 SixThresholdDetector.detect()）
            coupling_matrix: 耦合矩阵 {mechanism: {mechanism: strength}}
            structure_state: 当前结构状态向量
            structure_fn: 结构保持函数 state → bool，判断结构是否保持
            field_names: 需要检查语义防火墙的字段名列表
            timestamp: 时间戳

        Returns:
            ConvergenceResult 收束判定结果
        """
        if timestamp is not None:
            self._step_count = timestamp
        else:
            self._step_count += 1

        # ── 条件1: 六阈值检测 ──
        if threshold_params is not None:
            threshold_result = self._threshold_detector.detect(**threshold_params,
                                                                timestamp=self._step_count)
        else:
            threshold_result = self._threshold_detector.detect(timestamp=self._step_count)

        six_met = threshold_result.all_met

        # ── 条件2: 耦合强度检测 ──
        effective_threshold = self._get_dynamic_threshold(n_active)
        coupling_met, n_coupled, min_coupling = self._evaluate_coupling(
            coupling_matrix, effective_threshold=effective_threshold)

        # ── 条件3: 稳定性检测 ──
        stability_met, stability_score = self._evaluate_stability(
            structure_state, structure_fn)

        # ── 条件4: 语义防火墙 ──
        fw_result = self._check_semantic_firewall(field_names or [])

        # ── 综合判定 ──
        converged = six_met and coupling_met and stability_met and fw_result.passed

        result = ConvergenceResult(
            converged=converged,
            six_thresholds_met=six_met,
            coupling_strength_met=coupling_met,
            stability_met=stability_met,
            semantic_firewall_passed=fw_result.passed,
            n_coupled_pairs=n_coupled,
            min_coupling=min_coupling,
            stability_score=stability_score,
            timestamp=self._step_count,
        )

        self._convergence_history.append(result)
        return result

    def _evaluate_coupling(self,
                           coupling_matrix: Optional[Dict[str, Dict[str, float]]],
                           effective_threshold: Optional[float] = None
                           ) -> Tuple[bool, int, float]:
        """评估耦合强度

        检查所有机制对之间的耦合强度。
        模式：
          "all"     — 所有机制对都必须超过阈值（15/15）
          "majority" — 多数机制对超过阈值（≥12/15）
          "weighted" — 加权评分模式（核心机制对权重更高，
                     加权得分 ≥ 50% 总权重即通过）

        Args:
            coupling_matrix: 耦合矩阵
            effective_threshold: 有效耦合阈值（由 _get_dynamic_threshold 计算）。
                如果为 None，使用 self.coupling_threshold。

        Returns:
            (coupling_met, n_coupled_pairs, min_coupling)
        """
        if coupling_matrix is None:
            return False, 0, 0.0

        threshold = effective_threshold if effective_threshold is not None else self.coupling_threshold

        n_coupled = 0
        total_pairs = 0
        min_coupling = float('inf')

        mechanisms = self.MECHANISMS
        for i, ma in enumerate(mechanisms):
            for j, mb in enumerate(mechanisms):
                if i >= j:
                    continue
                total_pairs += 1
                strength = coupling_matrix.get(ma, {}).get(mb, 0.0)
                strength = max(strength, coupling_matrix.get(mb, {}).get(ma, 0.0))
                min_coupling = min(min_coupling, strength)
                if strength > threshold:
                    n_coupled += 1

        if total_pairs == 0:
            return False, 0, 0.0

        if min_coupling == float('inf'):
            min_coupling = 0.0

        if self.coupling_mode == "weighted":
            # 加权评分模式：核心机制对权重更高
            # 加权得分 = Σ(weight_i * coupled_i) / Σ(weight_i)
            # 通过条件：加权得分 ≥ 50%
            total_weight = 0.0
            weighted_score = 0.0
            for i, ma in enumerate(mechanisms):
                for j, mb in enumerate(mechanisms):
                    if i >= j:
                        continue
                    key = f"{ma}:{mb}"
                    weight = self.coupling_weights.get(key, 1.0)
                    total_weight += weight
                    strength = coupling_matrix.get(ma, {}).get(mb, 0.0)
                    strength = max(strength, coupling_matrix.get(mb, {}).get(ma, 0.0))
                    if strength > threshold:
                        weighted_score += weight
            coupling_met = (weighted_score / total_weight) >= 0.50 if total_weight > 0 else False
        elif self.coupling_mode == "majority":
            # 多数制：≥12/15 对超过阈值
            majority_threshold = max(1, int(total_pairs * 0.8))
            coupling_met = n_coupled >= majority_threshold
        else:
            # 全对制：所有对都必须超过阈值
            coupling_met = n_coupled == total_pairs
        return coupling_met, n_coupled, min_coupling

    def _evaluate_stability(self,
                            structure_state: Optional[torch.Tensor],
                            structure_fn: Optional[callable]
                            ) -> Tuple[bool, float]:
        """评估稳定性

        对结构施加微小扰动，检测结构是否保持。
        要求：扰动后结构保持比例超过稳定性阈值。

        Args:
            structure_state: 当前结构状态
            structure_fn: 结构保持判断函数

        Returns:
            (stability_met, stability_score)
        """
        if structure_state is None or structure_fn is None:
            return False, 0.0

        success_count = 0
        for _ in range(self.n_perturbation_tests):
            # 施加高斯扰动
            noise = torch.randn_like(structure_state) * self.perturbation_scale
            perturbed = structure_state + noise
            try:
                if structure_fn(perturbed):
                    success_count += 1
            except Exception:
                pass  # 扰动导致异常 → 结构不稳定

        stability_score = success_count / max(1, self.n_perturbation_tests)
        return stability_score > self.stability_threshold, stability_score

    def _check_semantic_firewall(self, field_names: List[str]) -> SemanticFirewallResult:
        """检查语义防火墙

        确保所有字段名不包含被禁止的高语义词汇。

        Args:
            field_names: 待检查的字段名列表

        Returns:
            SemanticFirewallResult
        """
        violations = []
        for name in field_names:
            name_lower = name.lower()
            for forbidden in SEMANTIC_FIREWALL_FORBIDDEN:
                if forbidden in name_lower:
                    violations.append(f"Field '{name}' contains forbidden term '{forbidden}'")

        return SemanticFirewallResult(
            passed=len(violations) == 0,
            violations=violations,
            n_checked=len(field_names),
        )

    @property
    def has_converged(self) -> bool:
        """最近一次判定是否收束"""
        if not self._convergence_history:
            return False
        return self._convergence_history[-1].converged

    @property
    def convergence_step(self) -> Optional[int]:
        """前主体态首次收束的时间戳"""
        for result in self._convergence_history:
            if result.converged:
                return result.timestamp
        return None

    def get_history_summary(self, last_n: int = 10) -> Dict:
        """获取最近 N 次判定的摘要"""
        recent = self._convergence_history[-last_n:] if self._convergence_history else []
        if not recent:
            return {'n_evaluations': 0}

        return {
            'n_evaluations': len(self._convergence_history),
            'n_recent': len(recent),
            'n_converged': sum(1 for r in recent if r.converged),
            'first_convergence_step': self.convergence_step,
            'avg_stability': float(np.mean([r.stability_score for r in recent])),
            'avg_coupled_pairs': float(np.mean([r.n_coupled_pairs for r in recent])),
            'latest_thresholds_met': recent[-1].six_thresholds_met,
            'latest_coupling_met': recent[-1].coupling_strength_met,
            'latest_stability_met': recent[-1].stability_met,
            'latest_firewall_passed': recent[-1].semantic_firewall_passed,
        }

    def reset(self):
        """重置所有状态"""
        self._threshold_detector.reset()
        self._coupling_history.clear()
        self._convergence_history.clear()
        self._step_count = 0
