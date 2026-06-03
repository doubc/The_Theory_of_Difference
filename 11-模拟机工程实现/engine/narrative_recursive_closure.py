"""
Phase 6: Narrative Recursive Closure (NRC)

P_{t+1} = R(S(M(E(P_t))))

Closes the spiral that V1.7 describes but that no simulation has yet implemented.
Narrative feedback rewrites the possibility space, completing the cycle from
generative output back to generative input.

Five sub-modules:
1. EventCompressor (E): narrative tension -> discrete events
2. MinimumVariationSelector (M): minimal-variation response path
3. NearestStableSettler (S): fall to temporary equilibrium
4. NarrativeRecursor (R): 3-layer recursive feedback
5. SpaceRewriter: bridge R output back to CSC input

References
----------
- V1.7 Upgrade Outline S1-S2, S7
- docs/phase6_narrative_recursive_closure_design.md
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import copy
import numpy as np
from collections import deque


@dataclass
class Event:
    """A single compressed event from narrative accumulation."""
    type: str  # 'structural', 'base_map', 'narrative_shift'
    step: int
    magnitude: float  # 0.0 - 1.0
    source_level: str
    target_level: Optional[str] = None
    description: str = ""

    def __repr__(self):
        target = self.target_level or 'self'
        return (f"Event(type={self.type}, step={self.step}, "
                f"mag={self.magnitude:.3f}, "
                f"{self.source_level}->{target})")


@dataclass
class RecursionOutput:
    """Output from the 3-layer narrative recursion."""
    r0_adjustments: Dict[str, float]
    r1_basin_shift: float
    r1_floor_shift: float
    r2_triggered: bool
    r2_new_bits: int
    cycles_completed: int


@dataclass
class RewrittenSpace:
    """The rewritten possibility space, ready for CSC consumption."""
    level_transition_weights: Dict[str, float]
    stability_basin_width: float
    stability_basin_floor: float
    n_bits: int
    new_dimensions: List[str]


@dataclass
class CycleResult:
    """Record of one complete E->M->S->R cycle."""
    cycle_id: int
    events: List[Event]
    selected_path: str
    settled_state: Dict[str, float]
    recursion_output: RecursionOutput
    step: int

    def is_complete(self):
        return len(self.events) > 0 and self.selected_path != "none"


# ============================================================================
# Module 1: EventCompressor (E-function)
# ============================================================================

class EventCompressor:
    """
    E-function: Compress accumulated narrative tension into discrete events.

    Three event types:
    - structural: level re-organization within existing bit structure
    - base_map: bit space rewriting (partial reset, new dimensions)
    - narrative_shift: dominant narrative level changes
    """

    def __init__(self, window=20, collapse_threshold=0.15,
                 emergence_threshold=0.15):
        self.window = window
        self.collapse_threshold = collapse_threshold
        self.emergence_threshold = emergence_threshold
        self._level_history = deque(maxlen=window)

    def reset(self):
        self._level_history.clear()

    def compute_events(self, step, narrative_level_distribution, nsi_result=None):
        events = []
        self._level_history.append({
            'step': step,
            'distribution': narrative_level_distribution.copy(),
        })
        if len(self._level_history) < 2:
            return events

        prev = self._level_history[-2]
        curr = self._level_history[-1]
        prev_dist = prev['distribution']
        curr_dist = curr['distribution']

        prev_total = max(sum(prev_dist.values()), 1)
        curr_total = max(sum(curr_dist.values()), 1)
        all_levels = set(list(prev_dist.keys()) + list(curr_dist.keys()))

        for level in all_levels:
            prev_frac = prev_dist.get(level, 0) / prev_total
            curr_frac = curr_dist.get(level, 0) / curr_total
            delta = curr_frac - prev_frac

            if delta < -self.collapse_threshold:
                events.append(Event(
                    type='structural', step=step, magnitude=abs(delta),
                    source_level=level,
                    description=f"Collapse: {level} dropped {abs(delta):.2%}"
                ))
            if delta > self.emergence_threshold:
                events.append(Event(
                    type='structural', step=step, magnitude=delta,
                    source_level=level,
                    description=f"Emergence: {level} rose {delta:.2%}"
                ))

        prev_dominant = max(prev_dist, key=prev_dist.get) if prev_dist else "NONE"
        curr_dominant = max(curr_dist, key=curr_dist.get) if curr_dist else "NONE"
        if prev_dominant != curr_dominant and prev_dominant != "NONE" and curr_dominant != "NONE":
            events.append(Event(
                type='narrative_shift', step=step, magnitude=0.5,
                source_level=prev_dominant, target_level=curr_dominant,
                description=f"Shift: {prev_dominant} -> {curr_dominant}"
            ))

        if nsi_result is not None:
            nsi_val = nsi_result.get('nsi', 0.0)
            tc = nsi_result.get('temporal_continuity', 0.0)
            if nsi_val > 0.7 and tc < 0.3 and len(self._level_history) >= 5:
                events.append(Event(
                    type='base_map', step=step, magnitude=nsi_val,
                    source_level=curr_dominant,
                    description=(f"Base-map: NSI={nsi_val:.2f} "
                                 f"continuity_crisis={tc:.2f}")
                ))

        return events


# ============================================================================
# Module 2: MinimumVariationSelector (M-function)
# ============================================================================

class MinimumVariationSelector:
    """
    M-function: Select minimal-variation response path after events.
    Implements Occam's razor in action-space.
    """

    def __init__(self, base_cost=0.1, path_memory=50):
        self.base_cost = base_cost
        self.path_memory = path_memory
        self._path_history = deque(maxlen=path_memory)

    def reset(self):
        self._path_history.clear()

    def select_path(self, events, current_level_weights):
        adjustments = {}
        selected_path = 'maintain'

        if not events:
            for level in current_level_weights:
                adjustments[level] = 0.0
            self._path_history.append('maintain')
            return ('maintain', adjustments)

        magnitudes = [e.magnitude for e in events]
        mean_mag = float(np.mean(magnitudes)) if magnitudes else 0.0
        max_mag = float(max(magnitudes)) if magnitudes else 0.0
        has_base_map = any(e.type == 'base_map' for e in events)

        costs = {}
        costs['maintain'] = mean_mag * 1.5
        costs['reinforce'] = mean_mag * 0.8 + self.base_cost
        costs['suppress'] = mean_mag * 1.2 + self.base_cost

        if max_mag > 0.3 or has_base_map:
            costs['restructure'] = max_mag * 0.8
        else:
            costs['restructure'] = 10.0

        selected_path = min(costs, key=costs.get)

        if selected_path == 'maintain':
            for level in current_level_weights:
                adjustments[level] = 0.0
        elif selected_path == 'reinforce':
            for level in current_level_weights:
                adjustments[level] = mean_mag * 0.05
        elif selected_path == 'suppress':
            for level in current_level_weights:
                adjustments[level] = -mean_mag * 0.05
        elif selected_path == 'restructure':
            for level in current_level_weights:
                if level == 'CIVILIZATION':
                    adjustments[level] = max_mag * 0.15
                elif level == 'INSTITUTIONAL':
                    adjustments[level] = max_mag * 0.10
                else:
                    adjustments[level] = -max_mag * 0.05

        self._path_history.append(selected_path)
        return (selected_path, adjustments)


# ============================================================================
# Module 3: NearestStableSettler (S-function)
# ============================================================================

class NearestStableSettler:
    """
    S-function: System falls to nearest temporary stable state.
    """

    def __init__(self, settling_rate=0.3, stability_memory=30):
        self.settling_rate = settling_rate
        self.stability_memory = stability_memory
        self._settled_history = deque(maxlen=stability_memory)
        self._last_nsi = 0.0

    def reset(self):
        self._settled_history.clear()
        self._last_nsi = 0.0

    def settle(self, selected_path, path_adjustments,
               current_distribution, nsi=0.0):
        total = max(sum(current_distribution.values()), 1)
        current_weights = {
            level: count / total
            for level, count in current_distribution.items()
        }
        settled = {}
        for level in current_weights:
            adj = path_adjustments.get(level, 0.0)
            settling_mod = self.settling_rate * (0.5 + nsi * 0.5)
            settled[level] = current_weights[level] + adj * settling_mod

        for level in settled:
            settled[level] = max(0.0, min(1.0, settled[level]))

        total_w = sum(settled.values())
        if total_w > 0:
            settled = {k: v / total_w for k, v in settled.items()}
        else:
            n_lev = len(settled)
            settled = {k: 1.0 / n_lev for k in settled}

        self._settled_history.append({
            'path': selected_path,
            'settled': settled.copy(),
            'nsi': nsi,
        })
        self._last_nsi = nsi
        return settled

    def get_stability_basin_width(self):
        if len(self._settled_history) < 3:
            return 0.5
        recent = list(self._settled_history)[-10:]
        if not recent:
            return 0.5
        level_sets = [s['settled'] for s in recent]
        all_levels = set()
        for ls in level_sets:
            all_levels.update(ls.keys())
        variances = []
        for level in all_levels:
            values = [ls.get(level, 0.0) for ls in level_sets]
            variances.append(float(np.var(values)))
        mean_v = float(np.mean(variances)) if variances else 0.0
        return max(0.0, 1.0 - mean_v * 5.0)


# ============================================================================
# Module 4: NarrativeRecursor (R-function) -- THE KEY COMPONENT
# ============================================================================

class NarrativeRecursor:
    """
    R-function: Three-layer narrative recursion.

    R0 (Micro): per-level affinity adjustments (fast, continuous)
    R1 (Institutional): stability basin shifts (medium, episodic)
    R2 (Civilizational): bit space rewriting (rare, epochal)
    """

    def __init__(self, r0_weight=0.4, r1_weight=0.35, r2_weight=0.25,
                 r2_threshold_nsi=0.85, r2_cooldown=200, max_r2_bits_pct=0.10):
        self.r0_weight = r0_weight
        self.r1_weight = r1_weight
        self.r2_weight = r2_weight
        self.r2_threshold_nsi = r2_threshold_nsi
        self.r2_cooldown = r2_cooldown
        self.max_r2_bits_pct = max_r2_bits_pct
        self._r2_last_step = -1000
        self._cycle_count = 0
        self._total_r2_events = 0

    def reset(self):
        self._r2_last_step = -1000
        self._cycle_count = 0
        self._total_r2_events = 0

    def get_r2_event_count(self):
        return self._total_r2_events

    def recurse(self, settled_state, current_level_weights,
                nsi_history, current_step, current_n_bits):
        self._cycle_count += 1

        # R0: Micro-recursion
        r0_adj = {}
        for level in current_level_weights:
            frac = settled_state.get(level, 0.0)
            if frac > 0:
                r0_adj[level] = self.r0_weight * frac * 0.02
            else:
                r0_adj[level] = -self.r0_weight * 0.005

        # R1: Institutional recursion
        inst_frac = settled_state.get('INSTITUTIONAL', 0.0)
        total_other = max(sum(v for k, v in settled_state.items()
                             if k != 'INSTITUTIONAL'), 0.1)
        inst_dom = inst_frac / (inst_frac + total_other)
        basin_shift = self.r1_weight * (inst_dom - 0.5) * 0.04
        floor_shift = self.r1_weight * (inst_dom - 0.5) * 0.02

        # R2: Civilizational recursion (conditional, rare)
        r2_triggered = False
        r2_new_bits = 0
        current_nsi = nsi_history[-1] if nsi_history else 0.0
        cooldown_ok = (current_step - self._r2_last_step) >= self.r2_cooldown

        if current_nsi >= self.r2_threshold_nsi and cooldown_ok and self._cycle_count > 5:
            r2_triggered = True
            self._total_r2_events += 1
            self._r2_last_step = current_step
            r2_new_bits = max(1, int(current_n_bits * self.max_r2_bits_pct))

        return RecursionOutput(
            r0_adjustments=r0_adj,
            r1_basin_shift=float(basin_shift),
            r1_floor_shift=float(floor_shift),
            r2_triggered=r2_triggered,
            r2_new_bits=r2_new_bits,
            cycles_completed=self._cycle_count,
        )


# ============================================================================
# Module 5: SpaceRewriter
# ============================================================================

class SpaceRewriter:
    """Bridge R-function output back to CSC-consumable possibility space."""

    def __init__(self):
        self._rewrite_count = 0
        self._last_rewrite_step = 0

    def reset(self):
        self._rewrite_count = 0
        self._last_rewrite_step = 0

    def get_rewrite_count(self):
        return self._rewrite_count

    def rewrite(self, recursion_output, current_weights,
                current_basin_width, current_basin_floor,
                current_n_bits, step):
        self._rewrite_count += 1
        self._last_rewrite_step = step

        new_weights = copy.deepcopy(current_weights)
        for level, adj in recursion_output.r0_adjustments.items():
            if level in new_weights:
                new_weights[level] *= (1.0 + adj)
            else:
                new_weights[level] = adj
        for level in new_weights:
            new_weights[level] = max(0.01, min(0.99, new_weights[level]))
        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: v / total for k, v in new_weights.items()}

        new_basin_w = current_basin_width * (1.0 + recursion_output.r1_basin_shift)
        new_basin_w = max(0.1, min(2.0, new_basin_w))
        new_basin_f = current_basin_floor * (1.0 + recursion_output.r1_floor_shift)
        new_basin_f = max(0.01, min(0.5, new_basin_f))

        new_dimensions = []
        new_n_bits = current_n_bits
        if recursion_output.r2_triggered and recursion_output.r2_new_bits > 0:
            new_n_bits = current_n_bits + recursion_output.r2_new_bits
            for i in range(recursion_output.r2_new_bits):
                new_dimensions.append(f"nrc_dim_{self._rewrite_count}_{i}")

        return RewrittenSpace(
            level_transition_weights=new_weights,
            stability_basin_width=new_basin_w,
            stability_basin_floor=new_basin_f,
            n_bits=new_n_bits,
            new_dimensions=new_dimensions,
        )


# ============================================================================
# Main NRC Controller
# ============================================================================

class NarrativeRecursiveClosure:
    """
    Main Phase 6 module: orchestrates the full E->M->S->R->Rewrite pipeline.

    Usage:
        nrc = NarrativeRecursiveClosure()
        result = nrc.process(step, dist, weights, nsi_result, ...)
        if result['rewritten_space'] is not None:
            apply_space(result['rewritten_space'])
    """

    def __init__(self, event_window=20, collapse_threshold=0.15,
                 settling_rate=0.3, r0_weight=0.4, r1_weight=0.35,
                 r2_weight=0.25, r2_threshold_nsi=0.85,
                 r2_cooldown=200, verbose=False):
        self.verbose = verbose
        self.compressor = EventCompressor(window=event_window,
                                          collapse_threshold=collapse_threshold)
        self.selector = MinimumVariationSelector()
        self.settler = NearestStableSettler(settling_rate=settling_rate)
        self.recursor = NarrativeRecursor(
            r0_weight=r0_weight, r1_weight=r1_weight, r2_weight=r2_weight,
            r2_threshold_nsi=r2_threshold_nsi, r2_cooldown=r2_cooldown,
        )
        self.rewriter = SpaceRewriter()
        self._cycles = []
        self._nsi_history = []
        self._step_results = []
        self._current_level_weights = {}

    def reset(self):
        self.compressor.reset()
        self.selector.reset()
        self.settler.reset()
        self.recursor.reset()
        self.rewriter.reset()
        self._cycles.clear()
        self._nsi_history.clear()
        self._step_results.clear()
        self._current_level_weights = {}

    def process(self, step, narrative_level_distribution,
                current_level_weights, nsi_result=None,
                nsi_history_snapshot=None, current_n_bits=48,
                stability_basin_width=0.5, stability_basin_floor=0.1):
        """
        Execute one complete E->M->S->R->Rewrite cycle.
        Returns dict with keys: events, cycle, recursion_output,
        rewritten_space, nrc_cycles_completed, cycle_complete.
        """
        if nsi_result is not None:
            nsi_val = nsi_result.get('nsi', nsi_result.get('nsi_value', 0.0))
            if isinstance(nsi_val, (int, float)):
                self._nsi_history.append(nsi_val)

        self._current_level_weights = current_level_weights.copy()

        # E: Event Compression
        events = self.compressor.compute_events(
            step=step, narrative_level_distribution=narrative_level_distribution,
            nsi_result=nsi_result,
        )

        cycle_complete = False
        recursion_output = None
        rewritten_space = None
        cycle_result = None

        if events:
            # M: Minimum Variation Selection
            selected_path, path_adjustments = self.selector.select_path(
                events=events, current_level_weights=current_level_weights,
            )

            # S: Nearest Stable Settling
            nsi_val = self._nsi_history[-1] if self._nsi_history else 0.0
            settled_state = self.settler.settle(
                selected_path=selected_path, path_adjustments=path_adjustments,
                current_distribution=narrative_level_distribution, nsi=nsi_val,
            )

            # R: Narrative Recursion
            recursion_output = self.recursor.recurse(
                settled_state=settled_state,
                current_level_weights=current_level_weights,
                nsi_history=self._nsi_history,
                current_step=step, current_n_bits=current_n_bits,
            )

            # Rewrite: bridge R output back to P_{t+1}
            basin_width = self.settler.get_stability_basin_width()
            rewritten_space = self.rewriter.rewrite(
                recursion_output=recursion_output,
                current_weights=current_level_weights,
                current_basin_width=stability_basin_width,
                current_basin_floor=stability_basin_floor,
                current_n_bits=current_n_bits, step=step,
            )

            cycle_result = CycleResult(
                cycle_id=len(self._cycles), events=events,
                selected_path=selected_path, settled_state=settled_state,
                recursion_output=recursion_output, step=step,
            )
            self._cycles.append(cycle_result)
            cycle_complete = True

            if self.verbose:
                r2_flag = 'YES' if recursion_output.r2_triggered else 'no'
                print(f"    [NRC] step={step}: events={len(events)} "
                      f"path={selected_path} R2={r2_flag} "
                      f"cycles={recursion_output.cycles_completed}")

        self._step_results.append({
            'step': step, 'n_events': len(events),
            'cycle_complete': cycle_complete,
        })

        return {
            'events': events,
            'cycle': cycle_result,
            'recursion_output': recursion_output,
            'rewritten_space': rewritten_space,
            'nrc_cycles_completed': len(self._cycles),
            'cycle_complete': cycle_complete,
        }

    def get_summary(self):
        n_cycles = len(self._cycles)
        n_r2 = self.recursor.get_r2_event_count()
        n_rewrites = self.rewriter.get_rewrite_count()
        cycle_stats = {}
        if n_cycles > 0:
            events_per = [len(c.events) for c in self._cycles if c.is_complete()]
            if events_per:
                cycle_stats['mean_events_per_cycle'] = round(float(np.mean(events_per)), 2)
                cycle_stats['max_events_per_cycle'] = max(events_per)
                cycle_stats['min_events_per_cycle'] = min(events_per)
        return {
            'nrc_module_active': True,
            'n_cycles': n_cycles,
            'n_r2_events': n_r2,
            'n_rewrites': n_rewrites,
            'cycle_stats': cycle_stats,
            'current_level_weights': self._current_level_weights.copy(),
            'last_r2_step': self.recursor._r2_last_step,
        }

    def get_cycle_history(self):
        return [c for c in self._cycles if c.is_complete()]


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("Phase 6: NRC Self-Test")
    print("=" * 70)

    nrc = NarrativeRecursiveClosure(verbose=True)
    print("\n--- Running 200 simulated steps ---")

    for step in range(1, 201):
        base = 10 + int(5 * np.sin(step / 20))
        dist = {
            'MINI': max(0, base),
            'INSTITUTIONAL': max(0, int(base * 0.5 * (1 + np.sin(step / 15 + 1)))),
            'CIVILIZATION': max(0, int(base * 0.2 * (1 + np.sin(step / 30 + 2)))),
        }
        weights = {'MINI': 0.6, 'MINI_NARRATIVE': 0.2,
                   'INSTITUTIONAL': 0.15, 'CIVILIZATION': 0.05}

        nsi_val = 0.3 + 0.6 * (1 - np.exp(-step / 80)) + 0.05 * np.random.randn()
        nsi_result = {'nsi': float(np.clip(nsi_val, 0.0, 1.0))}
        nsi_hist = [0.5 + 0.3 * np.sin(i / 50) for i in range(step)]

        nrc.process(step=step, narrative_level_distribution=dist,
                    current_level_weights=weights, nsi_result=nsi_result,
                    nsi_history_snapshot=nsi_hist, current_n_bits=48)

    summary = nrc.get_summary()
    print("\n--- NRC Summary ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    cycles = nrc.get_cycle_history()
    print(f"\n--- Total Cycles: {len(cycles)} ---")
    for c in cycles[-5:]:
        print(f"  Cycle {c.cycle_id}: step={c.step}, "
              f"events={len(c.events)}, path={c.selected_path}, "
              f"R2={c.recursion_output.r2_triggered}")

    print("\nNRC module self-test complete\n")
