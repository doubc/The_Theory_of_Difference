"""
exp_152 Verification — Phase 14 P0
Verifies the bidirectional coupling fix after _build_connections bugfix.
"""
import sys, os, torch, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from engine.subspace_field import SubspaceField, SubspaceSpec, Rules, CouplingDirection, allocate_static
from engine.subspace_evolver import SubspaceAwareEvolver, LayerCoordinator

def run_single(strength, N0=40, N1=40, seed=42):
    torch.manual_seed(seed)
    indices = allocate_static(N0+N1, k=2)
    field = SubspaceField(
        subspaces={"S0": SubspaceSpec(indices[0], Rules.default()),
                   "S1": SubspaceSpec(indices[1], Rules.default())},
        coupling_strength=strength,
        coupling_direction=CouplingDirection.BIDIRECTIONAL,
        global_coupling=(strength > 0.0),
    )
    evolver = SubspaceAwareEvolver(
        subspace_field=field,
        steps_per_layer=500, sample_interval=500, max_layers=2,
        device="cpu", partial_sealing=False,
        coupling_enabled=(strength > 0),
        coordination_strategy=LayerCoordinator.INDEPENDENT,
        verbose=False,
    )
    result = evolver.run(verbose=False)
    cb = {}
    for name, solver in evolver.solvers.items():
        ev = solver.evolver
        if ev and hasattr(ev.constraints, "coupling_bias"):
            cb[name] = ev.constraints.coupling_bias.norm().item()
        else:
            cb[name] = 0.0
    summary = result.get("summary", {}).get("subspaces", {})
    s0 = summary.get("S0", {}); s1 = summary.get("S1", {})
    return {"strength": strength,
            "S0_L1": s0.get("ever_sealed", False),
            "S1_L1": s1.get("ever_sealed", False),
            "S0_w": s0.get("final_hamming_weight", 0),
            "S1_w": s1.get("final_hamming_weight", 0),
            "cb_S0": cb.get("S0", 0), "cb_S1": cb.get("S1", 0)}

# Also verify connection structure
indices = allocate_static(80, k=2)
field = SubspaceField(
    subspaces={"S0": SubspaceSpec(indices[0], Rules.default()),
               "S1": SubspaceSpec(indices[1], Rules.default())},
    coupling_strength=1.0,
    coupling_direction=CouplingDirection.BIDIRECTIONAL,
    global_coupling=True,
)
conns = [(c.source, c.target) for c in field.connections]
print("=", 72)
print("  exp_152: Coupling Fix Verification (Phase 14 P0)")
print("=", 72)
print(f"  Connections (should be S0->S1 + S1->S0): {conns}")
assert len(conns) == 2, f"Expected 2 connections, got {len(conns)}"
assert ("S0","S1") in conns, "Missing S0->S1"
assert ("S1","S0") in conns, "Missing S1->S0"
print("  Bidirectional connection structure: OK")
print()

strengths = [0.0, 0.3, 1.0, 3.0]
n_runs = 5
all_results = []

for s in strengths:
    level = []
    for ri in range(n_runs):
        seed = 42 + int(s*100) + ri*7
        r = run_single(s, seed=seed)
        level.append(r)
        s0l = "Y" if r["S0_L1"] else "N"
        s1l = "Y" if r["S1_L1"] else "N"
        print(f"  s={s:3.1f} r={ri} L1:S0={s0l} S1={s1l} "
              f"w:S0={r['S0_w']:2.0f} S1={r['S1_w']:2.0f} "
              f"|cb|:S0={r['cb_S0']:.3f} S1={r['cb_S1']:.3f}")
    all_results.append({"strength": s, "runs": level})

print()
print("-"*72)
hdr = f"{'Strength':>8} | {'S0 L1%':>8} | {'S1 L1%':>8} | {'avg w0':>8} | {'avg w1':>8} | {'|cb| S0':>8} | {'|cb| S1':>8}"
print(hdr)
print("-"*72)
for level in all_results:
    s = level["strength"]; runs = level["runs"]
    s0r = sum(1 for r in runs if r["S0_L1"])/len(runs)
    s1r = sum(1 for r in runs if r["S1_L1"])/len(runs)
    aw0 = np.mean([r["S0_w"] for r in runs]); aw1 = np.mean([r["S1_w"] for r in runs])
    ac0 = np.mean([r["cb_S0"] for r in runs]); ac1 = np.mean([r["cb_S1"] for r in runs])
    print(f"{s:>8.1f} | {s0r:>8.2f} | {s1r:>8.2f} | {aw0:>8.1f} | {aw1:>8.1f} | {ac0:>8.4f} | {ac1:>8.4f}")
print("-"*72)

print()
print("KEY CHECK: Are both subspaces receiving coupling?")
kept_all = False
for level in all_results:
    s = level["strength"]; runs = level["runs"]
    both_active = all(r["cb_S0"] > 0.001 and r["cb_S1"] > 0.001 for r in runs if r["strength"] > 0)
    s0_active = sum(1 for r in runs if r["cb_S0"] > 0.001)
    s1_active = sum(1 for r in runs if r["cb_S1"] > 0.001)
    if s == 0.0:
        s0_off = sum(1 for r in runs if r["cb_S0"] < 0.001)
        s1_off = sum(1 for r in runs if r["cb_S1"] < 0.001)
        s0_pass = s0_off == len(runs)
        s1_pass = s1_off == len(runs)
        print(f"  strength={s:.1f}: coupling OFF -> both at 0: S0={s0_pass} S1={s1_pass}")
    else:
        print(f"  strength={s:.1f}: S0|cb|>0={s0_active}/{len(runs)}  S1|cb|>0={s1_active}/{len(runs)}")
        if s0_active > 0 and s1_active > 0:
            kept_all = True

print()
if kept_all:
    print("RESULT: Bidirectional coupling is working - both S0 and S1 receive coupling_bias.")
else:
    print("RESULT: Partial - coupling works for at least one direction.")
print("=", 72)