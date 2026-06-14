#!/usr/bin/env python3
"""
Phase 18 diagnostic: self-referential chain analysis.
Q1: Why does k->1 at every layer above L0?
Q2: What determines chain termination?
Q3: Can we engineer k>1 at higher layers?
"""
import numpy as np
from diffsim import RecursiveWorld
from diffsim.world import Params


def main():
    print("=" * 70)
    print("Phase 18: Emergence Depth Limit - Self-Referential Chain Analysis")
    print("=" * 70)

    # --- Q1: Colors and Organization Merging ---
    print("\n--- Q1: Why does k->1 at every layer above L0? ---")

    w = RecursiveWorld(N0=48, seed=0)
    w.run(6)
    print("Trace (seed=0, default params):")
    for i, layer in enumerate(w.layers):
        f = layer.field
        org_sizes = [len(o) for o in f.organizations.values()]
        org_colors = [set(f.color[list(o)]) for o in f.organizations.values()]
        n_orgs = len(f.organizations)
        print(f"  L{f.layer} N={f.N} orgs={n_orgs} sizes={org_sizes} "
              f"colors={org_colors} a1={len(f.a1_source)} "
              f"sealed={f.sealed} mode={f.naming_meta.get('mode','?')}")

    # --- Q2: Color spill analysis in L1 ---
    print("\n--- Q2: L1 color composition ---")
    if len(w.layers) >= 2:
        f1 = w.layers[1].field
        color_counts = {}
        for b in range(f1.N):
            c = f1.color[b]
            color_counts[c] = color_counts.get(c, 0) + 1
        print(f"  L1 color distribution: {dict(sorted(color_counts.items()))}")
        print(f"  L1 state: {list(f1.state)}")
        if f1.organizations:
            org = list(f1.organizations.values())[0]
            print(f"  L1 only org bits: {sorted(org)}")
            print(f"  L1 only org colors: {sorted(set(f1.color[list(org)]))}")

    # --- Q3: Does n_meta_colors affect k? ---
    print("\n--- Q3: Does larger n_meta_colors produce k>1 at L1? ---")
    for n_colors in [4, 8, 16, 32, 64]:
        l1_org_list = []
        depth_list = []
        for s in range(16):
            p = Params(n_meta_colors=n_colors)
            w = RecursiveWorld(N0=48, seed=s, params=p)
            w.run(6)
            l1_orgs = len(w.layers[1].field.organizations) if len(w.layers) >= 2 else 0
            depth = w.emergence_depth()
            l1_org_list.append(l1_orgs)
            depth_list.append(depth)
        l1_mean = np.mean(l1_org_list)
        l1_max = max(l1_org_list)
        depth_mean = np.mean(depth_list)
        depth_max = max(depth_list)
        print(f"  n_meta_colors={n_colors:>3}: L1 orgs mean={l1_mean:.2f} max={l1_max} "
              f"depth mean={depth_mean:.2f} max={depth_max}")

    # --- Q4: Termination threshold analysis ---
    print("\n--- Q4: When does the chain terminate? ---")
    for s in range(8):
        w = RecursiveWorld(N0=48, seed=s, params=Params(min_org_size=3))
        rep = w.run(6)
        depth = w.emergence_depth()
        last = rep[-1] if rep else None
        print(f"  seed={s}: depth={depth} last_N={last['N']} last_orgs={last['n_orgs']}")

    # --- Q5: min_org_size=2 -> deeper? ---
    print("\n--- Q5: min_org_size=2 (relaxed) -> deeper chain? ---")
    for s in range(8):
        p = Params(min_org_size=2, bind_threshold=1.2, cascade_density=0.8)
        w = RecursiveWorld(N0=48, seed=s, params=p)
        rep = w.run(8)
        depth = w.emergence_depth()
        last = rep[-1] if rep else None
        print(f"  seed={s}: depth={depth} last_N={last['N']} last_orgs={last['n_orgs']}")

    # --- Q6: Does N0 scale affect depth? ---
    print("\n--- Q6: Does N0 scale affect emergence depth? ---")
    for N0 in [24, 36, 48, 72, 96, 128]:
        depths = []
        for s in range(8):
            w = RecursiveWorld(N0=N0, seed=s)
            rep = w.run(8)
            depths.append(w.emergence_depth())
        print(f"  N0={N0:>4}: mean_depth={np.mean(depths):.2f} max_depth={max(depths)}")

    # --- Q7: Critical question — naming bit exhaustion ---
    print("\n--- Q7: Naming bit exhaustion — how many naming bits per layer? ---")
    w = RecursiveWorld(N0=48, seed=0)
    rep = w.run(8)
    for r in rep:
        mode = r["mode"]
        if mode == "self_reference":
            naming_bits = 2 * r["n_orgs"]  # body + naming per org
            print(f"  L{r['layer']}: N={r['N']} orgs={r['n_orgs']} "
                  f"naming_pairs={naming_bits} residual={r['N'] - naming_bits} "
                  f"mode={mode}")
        else:
            print(f"  L{r['layer']}: N={r['N']} orgs={r['n_orgs']} mode={mode}")

    print("\n" + "=" * 70)
    print("Phase 18 Analysis Complete")
    print("=" * 70)


if __name__ == "__main__":
    main()