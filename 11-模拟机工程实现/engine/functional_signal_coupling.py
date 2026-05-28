"""engine/functional_signal_coupling.py

Phase 2 P2: Functional Signal Coupling (P2方案)

Extract 6 functional signals from Phase 2 component outputs
instead of bit_id % 6 positional grouping.
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class FunctionalSignalSet:
    interface_regulation: float = 0.0
    self_sustaining: float = 0.0
    retention: float = 0.0
    replication: float = 0.0
    selection: float = 0.0
    functional_differentiation: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "interface_regulation": self.interface_regulation,
            "self_sustaining": self.self_sustaining,
            "retention": self.retention,
            "replication": self.replication,
            "selection": self.selection,
            "functional_differentiation": self.functional_differentiation,
        }

    @staticmethod
    def mechanism_names() -> List[str]:
        return [
            "interface_regulation",
            "self_sustaining",
            "retention",
            "replication",
            "selection",
            "functional_differentiation",
        ]

    def __repr__(self):
        parts = ["%s=%.4f" % (k, v) for k, v in self.to_dict().items()]
        return "FunctionalSignalSet(%s)" % ", ".join(parts)


@dataclass
class FunctionalCouplingMatrix:
    matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    signals: Optional[FunctionalSignalSet] = None

    def coupling_strength(self, ma: str, mb: str) -> float:
        return self.matrix.get(ma, {}).get(mb, 0.0)

    def n_above_threshold(self, threshold: float = 0.3) -> int:
        names = FunctionalSignalSet.mechanism_names()
        count = 0
        for i, ma in enumerate(names):
            for j, mb in enumerate(names):
                if i < j and self.matrix.get(ma, {}).get(mb, 0.0) > threshold:
                    count += 1
        return count

    @property
    def total_pairs(self) -> int:
        n = len(FunctionalSignalSet.mechanism_names())
        return n * (n - 1) // 2


def _gini(values):
    if not values:
        return 0.0
    arr = np.array(values, dtype=np.float64)
    if arr.sum() < 1e-12:
        return 0.0
    arr = np.sort(arr)
    n = len(arr)
    index = np.arange(1, n + 1)
    return float((2 * np.sum(index * arr) - (n + 1) * np.sum(arr)) / (n * np.sum(arr)))


def extract_functional_signals(
    active_count=0,
    total_bits=1,
    direction_agreement=0.0,
    aggregate_retention_depth=0.0,
    variant_retention_rates=None,
    selection_trend_scores=None,
    component_contributions=None,
):
    interface_regulation = active_count / max(1, total_bits)
    self_sustaining = float(np.clip(direction_agreement, 0.0, 1.0))
    retention = float(np.clip(aggregate_retention_depth, 0.0, 1.0))

    if variant_retention_rates and len(variant_retention_rates) > 0:
        replication = float(np.clip(np.mean(variant_retention_rates), 0.0, 1.0))
    else:
        replication = 0.0

    if selection_trend_scores and len(selection_trend_scores) > 0:
        selection = float(np.clip(np.mean(selection_trend_scores), 0.0, 1.0))
    else:
        selection = 0.0

    if component_contributions and len(component_contributions) >= 2:
        vals = [float(v) for v in component_contributions.values()]
        functional_differentiation = float(np.clip(_gini(vals), 0.0, 1.0))
    else:
        functional_differentiation = 0.0

    return FunctionalSignalSet(
        interface_regulation=interface_regulation,
        self_sustaining=self_sustaining,
        retention=retention,
        replication=replication,
        selection=selection,
        functional_differentiation=functional_differentiation,
    )


def compute_functional_coupling_matrix(signals, method="product"):
    sig_dict = signals.to_dict()
    names = FunctionalSignalSet.mechanism_names()
    eps = 1e-8
    matrix = {}

    for ma in names:
        matrix[ma] = {}
        for mb in names:
            if ma == mb:
                matrix[ma][mb] = 1.0
            else:
                s_a = sig_dict[ma]
                s_b = sig_dict[mb]
                if method == "product":
                    numerator = 2.0 * min(s_a, s_b)
                    denominator = s_a + s_b + eps
                    strength = numerator / denominator
                elif method == "correlation-inspired":
                    max_val = max(s_a, s_b)
                    if max_val < eps:
                        strength = 0.0
                    else:
                        strength = 1.0 - abs(s_a - s_b) / (max_val + eps)
                else:
                    raise ValueError("Unknown coupling method: %s" % method)
                matrix[ma][mb] = float(np.clip(strength, 0.0, 1.0))

    return FunctionalCouplingMatrix(matrix=matrix, signals=signals)
