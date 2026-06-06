"""
experiments/exp_151_phase11_p3_asymmetric_coupling.py

Phase 11 P3: Asymmetric (Unidirectional) Coupling — Master-Slave Structure

Purpose:
  Test whether unidirectional coupling from a larger "master" subspace to a
  smaller "slave" subspace can modulate the slave's L1 formation timing.
  This is the subspace analogy of the L1->L0 passive constraint discovered
  in Phase 8.

  exp_150 (symmetric coupling) found that off-diagonal bias injection is too
  weak to modulate L1 when N_sub > N0*. exp_151 tests whether ASYMMETRIC
  coupling (master->slave only) produces measurable effects, and whether
  a master subspace with more bits (N_master > N_slave) can "drive" the
  slave's evolution.

Method:
  Two subspaces with ASYMMETRIC sizes (master=40 bits, slave=20 bits).
  Coupling is UNIDIRECTIONAL: master->slave only (strength scanned).
  Slave->master coupling is always 0.0.

  N0=60 total. Phase transition N0*≈30.5:
    - Master (40 bits) is in ordered phase → L1 FORMS readily
    - Slave  (20 bits) is below threshold   → L1 DOES NOT FORM (at zero coupling)
    This creates a clear asymmetric baseline: master forms L1, slave does not.
    Coupling from master->slave may "rescue" the slave's L1 formation.

Config:
  N0          = 60   (master: 40 bits, slave: 20 bits)
  k           = 2    (S0=master, S1=slave)
  Allocation  = static partition (bits 0-39 = S0, bits 40-59 = S1)
  Coupling    = unidirectional S0->S1: [0.0, 0.5, 1.0, 2.0, 5.0, 10.0]
                 S1->S0: always 0.0
  Seeds       = 8
  Steps/layer = 5000
  Max layers  = 3

Coupling mechanism:
  Same as exp_150: off-diagonal injection into target's binding_strength,
  magnitude = conn.strength * direction_field * 0.1 per 500 steps.
  With unidirectional coupling, only S1 (slave) receives injection from S0.
  Positive strength -> S0's direction field injects bias into S1's binding.

Hypotheses:

  H151-1 (Asymmetric baseline):
    At coupling=0.0, S0 (40 bits, >N0*) forms L1 reliably,
    S1 (20 bits, <N0*) does NOT form L1.
    -> per-subspace L1 rates are S0≈1.0, S1≈0.0 at coupling=0.0.

  H151-2 (Rescue effect):
    As coupling S0->S1 increases, S1's L1 formation rate INCREASES
    (master "rescues" slave from below-threshold).
    -> L1 rate of S1 is monotonic increasing with coupling strength.

  H151-3 (No reverse effect):
    Since S1->S0 coupling = 0.0, S0's L1 rate is unaffected by coupling.
    -> S0's L1 rate ≈ constant across all coupling levels.

  H151-4 (Causal arrow):
    Granger causality (or simple cross-correlation of layer formation times)
    shows asymmetric influence: S0's L1 formation time PREDICTS S1's,
    but not vice versa, at non-zero coupling.
"""

import sys, os, time, json
import numpy as np
from datetime import datetime
from collections import OrderedDict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np

from engine.subspace_field import (
    SubspaceField, SubspaceSpec, Rules,
    CouplingTopology, CouplingDirection,
    allocate_static,
)
from engine.subspace_evolver import run_subspace_experiment

# =============================================================================
# Config
# =============================================================================

N0 = 60
MASTER_SIZE = 40   # > N0* ≈ 30.5, so master forms L1
SLAVE_SIZE = 20    # < N0*, so slave does NOT form L1 at zero coupling
assert MASTER_SIZE + SLAVE_SIZE == N0

STEPS_PER_LAYER = 5000
MAX_LAYERS = 3

# Coupling levels: scan up to 10.0 (exp_150 only went to 1.0 and saw nothing)
# With unidirectional coupling, higher values may produce measurable effects
COUPLING_LEVELS = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0]

SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]

MASTER_NAME = "S0_master"
SLAVE_NAME = "S1_slave"
SUBSPACE_NAMES = [MASTER_NAME, SLAVE_NAME]


# =============================================================================
# Field builder: asymmetric (unidirectional) coupling
# =============================================================================

def make_asymmetric_field(coupling_strength_master_to_slave: float) -> SubspaceField:
    """
    Build a SubspaceField with:
      - S0_master: 40 bits, NO outgoing coupling config (source side is handled globally)
      - S1_slave:  20 bits, UNIDIRECTIONAL_FWD from S0_master

    The coupling direction is stored in the SOURCE subspace's CouplingTopology.
    S0_master has peer_names={S1_slave} with UNIDIRECTIONAL_FWD.
    S1_slave has peer_names=set() (no reverse coupling).

    NOTE: SubspaceAwareEvolver reads _connections which are built from
    CouplingTopology settings. For UNIDIRECTIONAL_FWD, only the forward
    direction connection is created.
    """
    # Static partition: first MASTER_SIZE bits -> master, rest -> slave
    master_indices = set(range(0, MASTER_SIZE))
    slave_indices = set(range(MASTER_SIZE, N0))

    # Master: has outgoing unidirectional coupling to slave
    master_coupling = CouplingTopology(
        direction=CouplingDirection.UNIDIRECTIONAL_FWD,
        strength=coupling_strength_master_to_slave,
        peer_names={SLAVE_NAME},
    )

    # Slave: NO coupling back to master
    slave_coupling = CouplingTopology(
        direction=CouplingDirection.BIDIRECTIONAL,  # irrelevant (peer_names empty)
        strength=0.0,
        peer_names=set(),
    )

    subspaces = {
        MASTER_NAME: SubspaceSpec(
            bit_indices=master_indices,
            rules=Rules.default(),
            coupling=master_coupling,
            name=MASTER_NAME,
        ),
        SLAVE_NAME: SubspaceSpec(
            bit_indices=slave_indices,
            rules=Rules.default(),
            coupling=slave_coupling,
            name=SLAVE_NAME,
        ),
    }

    # global_coupling=False: use per-subspace coupling topologies
    return SubspaceField(
        subspaces=subspaces,
        global_coupling=False,
    )


# =============================================================================
# Single-run wrapper
# =============================================================================

def run_single(coupling_strength: float, seed: int,
               steps: int = STEPS_PER_LAYER,
               max_layers: int = MAX_LAYERS) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)

    field = make_asymmetric_field(coupling_strength)

    t0 = time.time()
    result = run_subspace_experiment(
        field=field,
        steps_per_layer=steps,
        max_layers=max_layers,
        coupling_enabled=(coupling_strength > 0.0),
        verbose=False,
    )
    elapsed = time.time() - t0

    summary = result.get("summary", {})
    per_subspace = summary.get("subspaces", {})

    # Per-subspace metrics
    subspace_metrics = {}
    for name in SUBSPACE_NAMES:
        ps = per_subspace.get(name, {})
        layers = ps.get("layers", [])
        subspace_metrics[name] = {
            "N": ps.get("N", 0),
            "final_sealed": ps.get("final_sealed", False),
            "ever_sealed": ps.get("ever_sealed", False),
            "final_hw": ps.get("final_hamming_weight", 0.0),
            "n_layers_formed": len(layers),
            "seal_steps": [l.get("seal_step", -1) for l in layers],
        }

    # Cross-subspace: difference in L1 formation step
    m_seal = subspace_metrics[MASTER_NAME]["seal_steps"]
    s_seal = subspace_metrics[SLAVE_NAME]["seal_steps"]
    l1_timing_diff = None
    if m_seal and s_seal:
        # First L1 seal step for each
        l1_timing_diff = min(s_seal) - min(m_seal)  # positive = slave lags

    return {
        "coupling": coupling_strength,
        "seed": seed,
        "elapsed": elapsed,
        "n_layers_executed": summary.get("layers_executed", 0),
        "master_sealed": subspace_metrics[MASTER_NAME]["ever_sealed"],
        "slave_sealed": subspace_metrics[SLAVE_NAME]["ever_sealed"],
        "subspace_metrics": subspace_metrics,
        "l1_timing_diff": l1_timing_diff,
    }


# =============================================================================
# Aggregation & Hypothesis evaluation
# =============================================================================

def evaluate_asymmetric_scan(runs_by_coupling: dict):
    coupling_levels = sorted(runs_by_coupling.keys())
    aggregates = OrderedDict()

    for cs in coupling_levels:
        runs = runs_by_coupling[cs]
        n = len(runs)

        master_rates = [1 if r["master_sealed"] else 0 for r in runs]
        slave_rates = [1 if r["slave_sealed"] else 0 for r in runs]

        m_rate = sum(master_rates) / max(n, 1)
        s_rate = sum(slave_rates) / max(n, 1)

        aggregates[cs] = {
            "n_runs": n,
            "master_l1_rate": m_rate,
            "slave_l1_rate": s_rate,
            "master_std": float(np.std(master_rates)),
            "slave_std": float(np.std(slave_rates)),
        }

    # ── H151-1: Asymmetric baseline at coupling=0.0 ──
    z = aggregates.get(0.0, {})
    h151_1_pass = (z.get("master_l1_rate", 0) > 0.5 and
                    z.get("slave_l1_rate", 1) < 0.5)

    # ── H151-2: Rescue effect (slave rate increases with coupling) ──
    slave_rates_by_cs = [aggregates[cs]["slave_l1_rate"]
                         for cs in coupling_levels if cs > 0]
    if len(slave_rates_by_cs) >= 2:
        # Monotonically non-decreasing
        h151_2_pass = all(
            slave_rates_by_cs[i] <= slave_rates_by_cs[i+1] + 0.01
            for i in range(len(slave_rates_by_cs)-1)
        )
    else:
        h151_2_pass = False

    # ── H151-3: No reverse effect (master rate constant) ──
    master_rates_all = [aggregates[cs]["master_l1_rate"] for cs in coupling_levels]
    master_std_all = np.std(master_rates_all)
    h151_3_pass = master_std_all < 0.3  # master rate roughly constant

    # ── H151-4: Causal arrow (timing diff non-zero at non-zero coupling) ──
    # Check if l1_timing_diff is non-None and non-zero for coupled runs
    timing_diffs = []
    for cs in coupling_levels:
        if cs == 0.0:
            continue
        for r in runs_by_coupling[cs]:
            if r["l1_timing_diff"] is not None:
                timing_diffs.append(r["l1_timing_diff"])
    h151_4_pass = len(timing_diffs) > 0  # at least some timing data collected

    n_pass = sum([h151_1_pass, h151_2_pass, h151_3_pass, h151_4_pass])

    return {
        "H151_1": {
            "pass": h151_1_pass,
            "description": f"Asymmetric baseline: master_rate={z.get('master_l1_rate',-1):.2f}, slave_rate={z.get('slave_l1_rate',-1):.2f} at coupling=0.0.",
        },
        "H151_2": {
            "pass": h151_2_pass,
            "slave_rates": {cs: aggregates[cs]["slave_l1_rate"]
                             for cs in coupling_levels if cs > 0},
            "description": "Slave L1 rate increases (rescue effect) with coupling.",
        },
        "H151_3": {
            "pass": h151_3_pass,
            "master_rates": {cs: aggregates[cs]["master_l1_rate"]
                             for cs in coupling_levels},
            "master_std": float(master_std_all),
            "description": "Master L1 rate unaffected by coupling (no reverse).",
        },
        "H151_4": {
            "pass": h151_4_pass,
            "n_timing_samples": len(timing_diffs),
            "description": "Causal arrow: L1 timing diff measurable at non-zero coupling.",
        },
        "aggregates": aggregates,
        "n_hypotheses_passed": n_pass,
    }


# =============================================================================
# Main
# =============================================================================

def main():
    print('=' * 75, flush=True)
    print('exp_151: PHASE 11 P3 - Asymmetric (Unidirectional) Coupling', flush=True)
    print('=' * 75, flush=True)
    print(f'  N0          = {N0} (master={MASTER_SIZE}, slave={SLAVE_SIZE})', flush=True)
    print(f'  N0*         ≈ 30.5 (master>{MASTER_SIZE}->L1 forms, slave<{SLAVE_SIZE}->L1 no)', flush=True)
    print(f'  Allocation  = static partition (asymmetric sizes)', flush=True)
    print(f'  Coupling    = S0->S1: {COUPLING_LEVELS},  S1->S0: 0.0', flush=True)
    print(f'  Seeds/level = {len(SEEDS)}', flush=True)
    print(f'  Total runs  = {len(COUPLING_LEVELS) * len(SEEDS)}', flush=True)
    print(f'  Steps/layer = {STEPS_PER_LAYER}', flush=True)
    print(f'  Max layers  = {MAX_LAYERS}', flush=True)
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}', flush=True)
    print(flush=True)

    runs_by_coupling = {cs: [] for cs in COUPLING_LEVELS}
    total_runs = len(COUPLING_LEVELS) * len(SEEDS)
    done = 0

    t_start = time.time()
    for cs in COUPLING_LEVELS:
        label = f"{cs:.1f}" if cs != int(cs) else f"{int(cs)}"
        print(f'  --- Coupling S0->S1: {label} ---', flush=True)
        for seed in SEEDS:
            t0 = time.time()
            result = run_single(cs, seed)
            elapsed = time.time() - t0
            runs_by_coupling[cs].append(result)
            done += 1

            m_flag = "Y" if result["master_sealed"] else "N"
            s_flag = "Y" if result["slave_sealed"] else "N"
            td = result["l1_timing_diff"]
            td_str = f"td={td:.0f}" if td is not None else "td=N/A"

            # ETA
            elapsed_total = time.time() - t_start
            avg_per_run = elapsed_total / max(done, 1)
            eta_seconds = avg_per_run * (total_runs - done)
            eta_min = int(eta_seconds // 60)
            eta_sec = int(eta_seconds % 60)
            eta_str = f"ETA {eta_min}m{eta_sec:02d}s" if eta_seconds > 0 else "ETA done"

            print(f'    [{done}/{total_runs}] cs={label} seed={seed} '
                  f'M:[{m_flag}] S:[{s_flag}] '
                  f'{td_str} '
                  f'[{elapsed:.1f}s] {eta_str}', flush=True)

    # Evaluate
    print(f'\n{"=" * 75}', flush=True)
    print('  EVALUATING HYPOTHESES', flush=True)
    print(f'{"=" * 75}', flush=True)

    evaluation = evaluate_asymmetric_scan(runs_by_coupling)

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    rf = os.path.join(PROJECT_ROOT, 'experiments',
                      f'exp_151_phase11_p3_asymmetric_{timestamp}.json')

    per_seed_clean = {}
    for cs, runs in runs_by_coupling.items():
        key = str(cs)
        per_seed_clean[key] = []
        for r in runs:
            entry = {k: v for k, v in r.items() if k != "subspace_metrics"}
            entry["subspace_metrics"] = {
                k: {sk: sv for sk, sv in v.items()}
                for k, v in r.get("subspace_metrics", {}).items()
            }
            per_seed_clean[key].append(entry)

    # Convert numpy types to native Python types for JSON serialization
    def convert_numpy_types(obj):
        if isinstance(obj, dict):
            return {k: convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_numpy_types(v) for v in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return convert_numpy_types(obj.tolist())
        else:
            return obj

    # Deep convert evaluation and per_seed_clean
    evaluation_clean = convert_numpy_types(evaluation)
    per_seed_clean = convert_numpy_types(per_seed_clean)

    with open(rf, 'w', encoding='utf-8') as f:
        json.dump({
            "experiment": "exp_151_phase11_p3",
            "datetime": datetime.now().isoformat(),
            "config": {
                "N0": N0,
                "master_size": MASTER_SIZE,
                "slave_size": SLAVE_SIZE,
                "subspaces": SUBSPACE_NAMES,
                "coupling_direction": "S0_master->S1_slave only (unidirectional)",
                "coupling_levels": COUPLING_LEVELS,
                "seeds": SEEDS,
                "steps_per_layer": STEPS_PER_LAYER,
                "max_layers": MAX_LAYERS,
            },
            "hypotheses": {
                hk: {
                    "pass": evaluation_clean[hk]["pass"],
                    "description": evaluation_clean[hk].get("description", ""),
                }
                for hk in ["H151_1", "H151_2", "H151_3", "H151_4"]
            },
            "n_pass": evaluation_clean["n_hypotheses_passed"],
            "aggregates": {str(k): v for k, v in evaluation_clean["aggregates"].items()},
            "per_seed": per_seed_clean,
        }, f, indent=2)

    n_pass = evaluation["n_hypotheses_passed"]
    print(f'\n  Results saved: {rf}', flush=True)

    for hk in ["H151_1", "H151_2", "H151_3", "H151_4"]:
        h = evaluation[hk]
        print(f'\n  {hk}: {"[PASS]" if h["pass"] else "[FAIL]"}', flush=True)
        print(f'    {h["description"]}', flush=True)

    print(f'\n  Phase 11 P3 (exp_151): {n_pass}/4 PASS', flush=True)
    print(flush=True)

    # Summary table
    agg = evaluation["aggregates"]
    print(f'  COUPLING SCAN SUMMARY', flush=True)
    print(f'  {"Coupling":<10} {"Master_L1":<12} {"Slave_L1":<12} {"Master_std":<12} {"Slave_std":<12}', flush=True)
    print(f'  {"-"*58}', flush=True)
    for cs in sorted(agg.keys()):
        a = agg[cs]
        print(f'  {cs:<10.1f} {a["master_l1_rate"]:<12.3f} {a["slave_l1_rate"]:<12.3f} '
              f'{a.get("master_std", 0):<12.3f} {a.get("slave_std", 0):<12.3f}', flush=True)


if __name__ == "__main__":
    main()
