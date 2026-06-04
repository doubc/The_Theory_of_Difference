# -*- coding: utf-8 -*-
"""
engine/l1_cycle_detector.py — Lightweight L1 Cycle Detector (LCylDet)

Phase 8 Component A: Monitor L1 NSI/CIV/Theme time series from PerLayerMetricsCollector
and detect cycle events via drop-recovery patterns.

Purpose
-------
The NRC operates only at the system level (L0). L1 has per-layer metrics (NSI, CIV, Theme)
from PerLayerMetricsCollector but no concept of "cycle detection." This module fills that gap,
enabling cross-scale spiral coupling in Phase 8.

Cycle Types
-----------
1. InstitutionalReconfiguration  (NSI-based):  NSI drops >30% then recovers >50%
2. ResourceReshuffle            (CIV-based):    CIV changes by >= 3 bits in <= 20 steps
3. IdentityShift                (Theme-based):  Jaccard(A(t), A(t-50)) < 0.6

Usage
-----
detector = L1CycleDetector()
# At each step after snapshot:
detector.update(step, l1_nsi, l1_civ, l1_active_bits, l1_stability)
# At end:
events = detector.get_detected_cycles()
"""

import math
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import deque
import numpy as np


# ─── Default Configuration ───

DEFAULT_LCYCL_DET_CONFIG = {
    # NSI-based: Institutional Reconfiguration
    'nsi_drop_threshold': 0.30,        # 30% drop from running max
    'nsi_recovery_threshold': 0.50,    # 50% of pre-drop level
    'nsi_recovery_window': 50,         # steps to look for recovery

    # CIV-based: Resource Reshuffle
    'civ_delta_threshold': 3,          # bits (CIV Hamming weight change)
    'civ_delta_window': 20,            # steps

    # Theme-based: Identity Shift
    'theme_jaccard_threshold': 0.6,    # min similarity across gap
    'theme_jaccard_gap': 50,           # step gap for comparison

    # General
    'history_window': 200,             # rolling window size
    'min_cycle_spacing': 30,           # min steps between two cycles of same type
}


@dataclass
class L1CycleEvent:
    """A detected cycle in L1 dynamics."""
    step: int
    cycle_type: str  # 'reconfiguration' | 'reshuffle' | 'identity_shift'
    magnitude: float  # 0.0–1.0
    nsi_before: float
    nsi_after: float
    civ_before: int
    civ_after: int
    theme_jaccard: float
    state_before: Dict
    state_after: Dict
    description: str = ""

    def __repr__(self):
        return (f"L1Cycle(step={self.step}, type={self.cycle_type}, "
                f"mag={self.magnitude:.3f}, NSI {self.nsi_before:.2f}→{self.nsi_after:.2f}, "
                f"CIV {self.civ_before}→{self.civ_after})")


@dataclass
class StateSnapshot:
    """Snapshot of L1 state at a given step."""
    step: int
    nsi: float
    civ: int
    active_bits: Set[int]
    stability: float


class L1CycleDetector:
    """
    Lightweight L1 cycle detector that monitors PerLayerMetricsCollector outputs
    and detects cycle events via three independent signals.

    Usage:
        detector = L1CycleDetector()
        detector.update(step=10, l1_nsi=0.65, l1_civ=12, l1_active_bits={0,1,2,3,...}, l1_stability=0.8)
        ...
        cycles = detector.get_detected_cycles()
        summary = detector.get_summary()
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_LCYCL_DET_CONFIG, **(config or {})}

        self.nsi_drop_threshold = cfg['nsi_drop_threshold']
        self.nsi_recovery_threshold = cfg['nsi_recovery_threshold']
        self.nsi_recovery_window = cfg['nsi_recovery_window']
        self.civ_delta_threshold = cfg['civ_delta_threshold']
        self.civ_delta_window = cfg['civ_delta_window']
        self.theme_jaccard_threshold = cfg['theme_jaccard_threshold']
        self.theme_jaccard_gap = cfg['theme_jaccard_gap']
        self.history_window = cfg['history_window']
        self.min_cycle_spacing = cfg['min_cycle_spacing']

        # Rolling history
        self._history = deque(maxlen=self.history_window + 100)  # extra buffer for gaps
        self._current_snapshot = None
        self._running_max_nsi = 0.0
        self._detected_cycles: List[L1CycleEvent] = []
        self._last_cycle_step = {
            'reconfiguration': -self.min_cycle_spacing,
            'reshuffle': -self.min_cycle_spacing,
            'identity_shift': -self.min_cycle_spacing,
        }
        self._nsi_drop_start = None  # (drop_start_step, nsi_at_drop_start, max_before_drop)

    def reset(self):
        self._history.clear()
        self._current_snapshot = None
        self._running_max_nsi = 0.0
        self._detected_cycles.clear()
        self._last_cycle_step = {k: -self.min_cycle_spacing
                                  for k in self._last_cycle_step}
        self._nsi_drop_start = None

    def update(self, step: int, l1_nsi: float, l1_civ: int,
               l1_active_bits: Set[int], l1_stability: float = 0.5):
        """
        Process one step of L1 data. Must be called at each snapshot step.

        Parameters
        ----------
        step : int
            Current simulation step.
        l1_nsi : float
            L1 NSI value from PerLayerNSITracker (0.0–1.0).
        l1_civ : int
            L1 CIV value (number of active bits, Hamming weight).
        l1_active_bits : Set[int]
            Set of active bit indices in L1.
        l1_stability : float
            L1 institutional stability (0.0–1.0).
        """
        self._current_snapshot = StateSnapshot(
            step=step, nsi=l1_nsi, civ=l1_civ,
            active_bits=set(l1_active_bits) if l1_active_bits else set(),
            stability=l1_stability,
        )
        self._history.append(self._current_snapshot)
        self._running_max_nsi = max(self._running_max_nsi, l1_nsi)

        # Run all three detection algorithms
        self._check_nsi_cycle(step, l1_nsi)
        self._check_civ_cycle(step, l1_civ)
        self._check_theme_cycle(step, l1_active_bits)

    # ─── NSI-based: Institutional Reconfiguration ───

    def _check_nsi_cycle(self, step: int, current_nsi: float):
        """Detect NSI drop-recovery pattern."""
        if self._nsi_drop_start is None:
            # Check if we just started a drop
            if len(self._history) >= 3:
                # Get last few NSI values
                recent = [s.nsi for s in list(self._history)[-3:]]
                current_nsi = recent[-1]
                recent_max = max(recent)
                running_max = self._running_max_nsi

                # Detect drop: current significantly below running max
                if running_max > 0.1 and current_nsi < running_max * (1.0 - self.nsi_drop_threshold):
                    # Find the peak before the drop (scan backward)
                    for s in reversed(list(self._history)[:-2]):
                        if s.nsi >= running_max * 0.95:
                            self._nsi_drop_start = (s.step, s.nsi, running_max)
                            break
                    if self._nsi_drop_start is None:
                        self._nsi_drop_start = (step, current_nsi, running_max)
            return

        # We're tracking a drop. Check for recovery.
        drop_start_step, nsi_at_drop, max_before_drop = self._nsi_drop_start
        recovery_target = nsi_at_drop * self.nsi_recovery_threshold
        steps_since_drop = step - drop_start_step

        if steps_since_drop > self.nsi_recovery_window:
            # Drop unratified — no recovery within window
            self._nsi_drop_start = None
            return

        # Check cooldown
        steps_since_last = step - self._last_cycle_step['reconfiguration']
        if steps_since_last < self.min_cycle_spacing:
            self._nsi_drop_start = None
            return

        # Detect recovery
        if current_nsi >= recovery_target:
            magnitude = min(1.0, (nsi_at_drop - self._get_nsi_nadir(
                drop_start_step, step)) / max(nsi_at_drop, 0.01))
            magnitude = max(0.1, magnitude)

            self._detected_cycles.append(L1CycleEvent(
                step=step,
                cycle_type='reconfiguration',
                magnitude=round(magnitude, 3),
                nsi_before=round(nsi_at_drop, 4),
                nsi_after=round(current_nsi, 4),
                civ_before=self._get_civ_at_step(drop_start_step),
                civ_after=self._current_snapshot.civ if self._current_snapshot else 0,
                theme_jaccard=1.0,  # placeholder; theme comparison below
                state_before={'step': drop_start_step, 'nsi': nsi_at_drop,
                              'max_before_drop': max_before_drop},
                state_after={'step': step, 'nsi': current_nsi},
                description=(f"Institutional reconfiguration: NSI "
                             f"{nsi_at_drop:.2f}→{current_nsi:.2f}, "
                             f"drop={nsi_at_drop - current_nsi:.2f}"),
            ))
            self._last_cycle_step['reconfiguration'] = step
            self._nsi_drop_start = None

    def _get_nsi_nadir(self, start_step: int, end_step: int) -> float:
        """Find the minimum NSI between start_step and end_step."""
        nadir = 1.0
        for s in self._history:
            if start_step <= s.step <= end_step:
                nadir = min(nadir, s.nsi)
        return nadir

    def _get_civ_at_step(self, target_step: int) -> int:
        """Get CIV at a specific step from history."""
        for s in reversed(self._history):
            if s.step <= target_step:
                return s.civ
        return 0

    def _get_active_bits_at_step(self, target_step: int) -> Set[int]:
        """Get active bits at a specific step from history."""
        for s in reversed(self._history):
            if s.step <= target_step:
                return s.active_bits
        return set()

    # ─── CIV-based: Resource Reshuffle ───

    def _check_civ_cycle(self, step: int, current_civ: int):
        """Detect rapid CIV change indicating cluster reshuffle."""
        steps_since_last = step - self._last_cycle_step['reshuffle']
        if steps_since_last < self.min_cycle_spacing:
            return

        # Need enough history
        if len(self._history) < 5:
            return

        # Get CIV values in the civ_delta_window
        civ_values = [s.civ for s in list(self._history)[-self.civ_delta_window:]]
        if len(civ_values) < 3:
            return

        civ_min = min(civ_values)
        civ_max = max(civ_values)
        civ_delta = civ_max - civ_min

        if civ_delta >= self.civ_delta_threshold:
            # Find the step of the min and max
            min_step = None
            max_step = None
            for s in reversed(self._history):
                if s.civ == civ_min and min_step is None:
                    min_step = s.step
                if s.civ == civ_max and max_step is None:
                    max_step = s.step
                if min_step is not None and max_step is not None:
                    break

            # The delta must happen within the window
            if min_step is None or max_step is None:
                return
            if abs(min_step - max_step) > self.civ_delta_window:
                return

            magnitude = min(1.0, civ_delta / 10.0)  # 10+ bits = max magnitude

            self._detected_cycles.append(L1CycleEvent(
                step=step,
                cycle_type='reshuffle',
                magnitude=round(magnitude, 3),
                nsi_before=self._get_nsi_before(max(0, step - self.civ_delta_window)),
                nsi_after=self._history[-1].nsi if self._history else 0.0,
                civ_before=civ_min,
                civ_after=civ_max,
                theme_jaccard=1.0,
                state_before={'step': min_step, 'civ': civ_min},
                state_after={'step': max_step, 'civ': civ_max},
                description=(f"Resource reshuffle: CIV {civ_min}→{civ_max} "
                             f"(delta={civ_delta}) in {abs(step - min_step)} steps"),
            ))
            self._last_cycle_step['reshuffle'] = step

    def _get_nsi_before(self, target_step: int) -> float:
        """Get NSI before a specific step."""
        for s in reversed(self._history):
            if s.step <= target_step:
                return s.nsi
        return 0.0

    # ─── Theme-based: Identity Shift ───

    def _check_theme_cycle(self, step: int, current_active_bits: Set[int]):
        """Detect significant shift in active bit composition (theme identity change)."""
        steps_since_last = step - self._last_cycle_step['identity_shift']
        if steps_since_last < self.min_cycle_spacing:
            return

        if step < self.theme_jaccard_gap:
            return

        if not current_active_bits:
            return

        # Get active bits from `theme_jaccard_gap` steps ago
        past_bits = self._get_active_bits_at_step(step - self.theme_jaccard_gap)
        if not past_bits:
            return

        # Compute Jaccard similarity
        intersection = len(past_bits & current_active_bits)
        union = len(past_bits | current_active_bits)
        jaccard = intersection / max(union, 1)

        if jaccard < self.theme_jaccard_threshold:
            magnitude = min(1.0, (1.0 - jaccard) * 1.5)  # jaccard 0.0 → mag 1.5, capped at 1.0

            self._detected_cycles.append(L1CycleEvent(
                step=step,
                cycle_type='identity_shift',
                magnitude=round(magnitude, 3),
                nsi_before=self._history[-1].nsi if self._history else 0.0,
                nsi_after=self._history[-1].nsi if self._history else 0.0,
                civ_before=self._get_civ_at_step(step - self.theme_jaccard_gap),
                civ_after=self._current_snapshot.civ if self._current_snapshot else 0,
                theme_jaccard=round(jaccard, 4),
                state_before={'step': step - self.theme_jaccard_gap,
                              'n_active': len(past_bits)},
                state_after={'step': step, 'n_active': len(current_active_bits)},
                description=(f"Identity shift: theme Jaccard={jaccard:.3f} "
                             f"({len(past_bits)}→{len(current_active_bits)} active bits)"),
            ))
            self._last_cycle_step['identity_shift'] = step

    # ─── Public API ───

    def get_detected_cycles(self) -> List[L1CycleEvent]:
        """Return all detected L1 cycle events, ordered by step."""
        return sorted(self._detected_cycles, key=lambda e: e.step)

    def get_cycle_times(self) -> Dict[str, List[int]]:
        """Return dict of {type: [step, ...]} for correlation analysis."""
        result = {'reconfiguration': [], 'reshuffle': [], 'identity_shift': [], 'all': []}
        for event in self._detected_cycles:
            result[event.cycle_type].append(event.step)
            result['all'].append(event.step)
        for key in result:
            result[key] = sorted(result[key])
        return result

    def get_summary(self) -> Dict:
        """Get a summary of detected cycles."""
        n_reconfig = sum(1 for e in self._detected_cycles
                         if e.cycle_type == 'reconfiguration')
        n_reshuffle = sum(1 for e in self._detected_cycles
                          if e.cycle_type == 'reshuffle')
        n_identity = sum(1 for e in self._detected_cycles
                         if e.cycle_type == 'identity_shift')

        cycle_steps = [e.step for e in self._detected_cycles]
        cycle_spacings = []
        if len(cycle_steps) >= 2:
            sorted_steps = sorted(cycle_steps)
            cycle_spacings = [sorted_steps[i+1] - sorted_steps[i]
                              for i in range(len(sorted_steps)-1)]

        return {
            'total_cycles': len(self._detected_cycles),
            'by_type': {
                'reconfiguration': n_reconfig,
                'reshuffle': n_reshuffle,
                'identity_shift': n_identity,
            },
            'cycle_steps': cycle_steps,
            'mean_spacing': round(float(np.mean(cycle_spacings)), 1) if cycle_spacings else 0.0,
            'min_spacing': min(cycle_spacings) if cycle_spacings else 0,
            'max_spacing': max(cycle_spacings) if cycle_spacings else 0,
        }


# ─── Utility: Cycle Timing Correlation ───

def compute_cycle_jaccard(l0_cycle_steps: List[int],
                          l1_cycle_steps: List[int],
                          epsilon: int = 50) -> float:
    """
    Compute Jaccard similarity between L0 and L1 cycle timing sets,
    allowing epsilon-approximate matching.

    Two cycles match if |t_L0 - t_L1| <= epsilon.

    Returns: float in [0.0, 1.0]
    """
    if not l0_cycle_steps or not l1_cycle_steps:
        return 0.0

    l0_sorted = sorted(set(l0_cycle_steps))
    l1_sorted = sorted(set(l1_cycle_steps))

    # Count matches (each L0 cycle can match at most one L1 cycle)
    matches = 0
    l1_matched = set()

    for t0 in l0_sorted:
        for i, t1 in enumerate(l1_sorted):
            if i in l1_matched:
                continue
            if abs(t0 - t1) <= epsilon:
                matches += 1
                l1_matched.add(i)
                break

    union = len(l0_sorted) + len(l1_sorted) - matches
    return matches / max(union, 1)


def compute_cycle_delay_distribution(l0_cycle_steps: List[int],
                                     l1_cycle_steps: List[int],
                                     epsilon: int = 50) -> Dict:
    """
    Compute the delay distribution between matched L0 and L1 cycles.
    Positive delay = L1 cycle LAGS behind L0 cycle.

    Returns dict with delays list, mean_delay, direction.
    """
    if not l0_cycle_steps or not l1_cycle_steps:
        return {'delays': [], 'mean_delay': 0.0, 'n_matches': 0,
                'l0_before_l1': 0, 'l1_before_l0': 0}

    l0_sorted = sorted(set(l0_cycle_steps))
    l1_sorted = sorted(set(l1_cycle_steps))

    delays = []
    l1_matched = set()

    for t0 in l0_sorted:
        for i, t1 in enumerate(l1_sorted):
            if i in l1_matched:
                continue
            if abs(t0 - t1) <= epsilon:
                delays.append(t1 - t0)
                l1_matched.add(i)
                break

    n_matches = len(delays)
    l0_before = sum(1 for d in delays if d > 0)
    l1_before = sum(1 for d in delays if d < 0)

    return {
        'delays': delays,
        'mean_delay': round(float(np.mean(delays)), 1) if delays else 0.0,
        'n_matches': n_matches,
        'l0_before_l1': l0_before,
        'l1_before_l0': l1_before,
    }


# ─── Phase 8 P1: Encapsulation-Aware Callback ───

class L1AwareLCylDetCallback:
    """
    Encapsulation-aware tracking callback for L1 cycle detection.

    Phase 8 P1 workaround: With max_layers=1, the evolver never fires the
    tracking callback for layer_id=1 because the run loop iterates only
    up to max_layers. However, the hierarchy DOES contain L1 data after
    encapsulation (via check_and_encapsulate()).

    This callback extracts L1 metrics from the hierarchy when l1_formed
    is detected, feeding them to an L1CycleDetector for cycle detection.

    Usage:
        detector = L1CycleDetector()
        collector = PerLayerMetricsCollector(config)
        hierarchy_getter = lambda: evolver.hierarchy
        cb = L1AwareLCylDetCallback(collector, detector, hierarchy_getter)
        result = evolver.run(tracking_callback=cb.step)
    """

    def __init__(self, collector, l1_detector, hierarchy_getter):
        self.collector = collector
        self.l1_detector = l1_detector
        self.hierarchy_getter = hierarchy_getter  # callable -> HierarchyManager
        self._last_l1_nsi = 0.0
        self._last_l1_civ = 0
        self._last_l1_active_bits = set()
        self._l1_extracted = False

    def step(self, step, layer_id, n_active, n_total, n_frozen,
             hamming_weight, active_bits, frozen_bits,
             global_odi, global_msi,
             l0_sealed=False, l1_formed=False, l1_unique_active=0,
             l1_sealing_threshold=0,
             **kwargs):
        """
        Called by HierarchicalEvolver for each layer snapshot.
        Forwards to collector, then extracts L1 data from hierarchy
        when l1_formed is True (regardless of layer_id).
        """
        # Forward to collector first
        if self.collector:
            self.collector.step(
                step, layer_id, n_active, n_total, n_frozen,
                hamming_weight, active_bits, frozen_bits,
                global_odi, global_msi,
                l0_sealed=l0_sealed, l1_formed=l1_formed,
                l1_unique_active=l1_unique_active,
                l1_sealing_threshold=l1_sealing_threshold,
            )

        # Extract L1 data when available
        if l1_formed and layer_id == 0 and self.l1_detector:
            hierarchy = self.hierarchy_getter()
            if hierarchy and hierarchy.n_layers > 1:
                l1_layer = hierarchy.get_layer(1)

                # Compute L1 metrics from LayerState
                l1_active = len(l1_layer.active_bits)
                l1_total = l1_layer.n_bits
                l1_nsi = l1_active / max(l1_total, 1)
                l1_civ = l1_active
                l1_stability = 1.0 - (len(l1_layer.frozen_bits) / max(l1_total, 1))

                self._last_l1_nsi = l1_nsi
                self._last_l1_civ = l1_civ
                self._last_l1_active_bits = set(l1_layer.active_bits)
                self._l1_extracted = True

                # Feed to L1CycleDetector
                self.l1_detector.update(
                    step=step,
                    l1_nsi=l1_nsi,
                    l1_civ=l1_civ,
                    l1_active_bits=l1_layer.active_bits,
                    l1_stability=l1_stability,
                )
            elif self._l1_extracted:
                # L1 was formed but now hierarchy lost? feed last known
                self.l1_detector.update(
                    step=step,
                    l1_nsi=self._last_l1_nsi,
                    l1_civ=self._last_l1_civ,
                    l1_active_bits=self._last_l1_active_bits,
                    l1_stability=0.5,
                )

    def get_l1_metrics(self) -> Dict:
        """Get L1 cycle metrics from the detector."""
        if not self.l1_detector:
            return {'l1_detector': {'total_cycles': 0}, 'l1_extracted': False}

        summary = self.l1_detector.get_summary()
        cycle_times = self.l1_detector.get_cycle_times()
        types_active = sum(1 for v in cycle_times.values() if len(v) > 0)
        # Exclude 'all' key from type count
        type_count = {'reconfiguration': cycle_times.get('reconfiguration', []),
                      'reshuffle': cycle_times.get('reshuffle', []),
                      'identity_shift': cycle_times.get('identity_shift', [])}
        n_types = sum(1 for v in type_count.values() if len(v) > 0)

        return {
            'l1_detector': summary,
            'l1_cycle_times': cycle_times,
            'n_cycle_types_active': n_types,
            'l1_last_nsi': self._last_l1_nsi,
            'l1_last_civ': self._last_l1_civ,
            'l1_extracted': self._l1_extracted,
        }
