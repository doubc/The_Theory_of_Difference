"""exp_186_phase19_p1_complexity_sweep.py — Phase 19 P1: 环境复杂度扫描。

假设 H19-P2: 高复杂度环境 (structural_entropy=2) → 系统吸收环境结构
             (Spearman rho > 0.5 between env structure and system org structure)
假设 H19-P3: 低复杂度环境 (structural_entropy=0) → 系统忽略环境
             (k, flux, depth change < 5% vs no-env control)

4 configs × 16 seeds = 64 runs.
"""
import sys, os, json, time, numpy as np
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffsim.world import RecursiveWorld, Params

ENTROPIES = [None, 0, 1, 2]  # None = no env (control)
SEEDS = 16
MAX_LAYERS = 6
COUPLING_STRENGTH = 0.20
ENV_N = 24

BASELINE_PARAMS = Params(
    bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
    cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
    lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
    target_active=0, max_flip=6, churn=2,
    n_meta_colors=4, max_residual=6, max_steps=400,
)


def compute_structure_absorption(world):
    """计算系统吸收环境结构的程度。

    对每个环境颜色簇，测量其比特在系统组织中集中的程度。
    完全吸收 = 同一颜色簇的所有比特在同一个系统组织中。

    Returns:
        dict: {layer_idx: absorption_score}
    """
    if not hasattr(world, 'env') or world.env is None:
        return {}

    env = world.env
    env_color_bits = defaultdict(set)
    for b in range(env.N):
        env_color_bits[int(env.color[b])].add(b)

    results = {}
    for li, layer_obj in enumerate(world.layers):
        field = getattr(layer_obj, 'field', None)
        if field is None or not hasattr(field, 'organizations'):
            continue
        orgs = field.organizations
        if not orgs:
            continue

        # Map bit -> org_id for shared bits (0..env.N-1)
        bit_to_org = {}
        for oid, members in orgs.items():
            for b in members:
                if b < env.N:
                    bit_to_org[b] = oid

        # For each env color cluster, compute concentration
        color_scores = []
        for c, bits in env_color_bits.items():
            if not bits:
                continue
            org_counts = defaultdict(int)
            for b in bits:
                oid = bit_to_org.get(b)
                if oid is not None:
                    org_counts[oid] += 1
            if org_counts:
                max_frac = max(org_counts.values()) / len(bits)
                color_scores.append(max_frac)

        if color_scores:
            results[li] = float(np.mean(color_scores))
        else:
            results[li] = 0.0

    return results


def compute_env_system_rho(world):
    """计算环境聚类结构与系统组织结构的 Spearman rho。

    对共享比特 (0..env.N-1)，测量 env 颜色分配 vs 系统组织归属的一致性。
    方法: pairwise comparison — 如果两比特在相同 env_color，它们是否在相同 system_org？
    """
    if not hasattr(world, 'env') or world.env is None:
        return {}

    env = world.env
    results = {}

    for li, layer_obj in enumerate(world.layers):
        field = getattr(layer_obj, 'field', None)
        if field is None or not hasattr(field, 'organizations'):
            continue
        orgs = field.organizations
        if not orgs:
            continue

        bit_org = {}
        for oid, members in orgs.items():
            for b in members:
                if b < env.N:
                    bit_org[b] = oid

        present_bits = sorted(bit_org.keys())
        if len(present_bits) < 3:
            results[li] = 0.0
            continue

        n = len(present_bits)
        env_same = []
        org_same = []
        for i in range(n):
            bi = present_bits[i]
            ci = int(env.color[bi])
            oi = bit_org[bi]
            for j in range(i+1, n):
                bj = present_bits[j]
                cj = int(env.color[bj])
                oj = bit_org[bj]
                env_same.append(1 if ci == cj else 0)
                org_same.append(1 if oi == oj else 0)

        if len(env_same) < 5:
            results[li] = 0.0
            continue

        rho, _ = spearmanr(env_same, org_same)
        results[li] = float(rho if not np.isnan(rho) else 0.0)

    return results


def compute_colonization(world):
    """计算环境在场率: 多少系统组织使用了环境比特。"""
    if not hasattr(world, 'env') or world.env is None:
        return {}

    env = world.env
    results = {}
    for li, layer_obj in enumerate(world.layers):
        field = getattr(layer_obj, 'field', None)
        if field is None or not hasattr(field, 'organizations'):
            continue
        orgs = field.organizations
        if not orgs:
            results[li] = 0.0
            continue

        env_bit_orgs = set()
        for oid, members in orgs.items():
            for b in members:
                if b < env.N:
                    env_bit_orgs.add(oid)
                    break
        colonization = len(env_bit_orgs) / max(1, len(orgs))
        results[li] = colonization

    return results


def spearmanr(x, y):
    """Compute Spearman rank correlation coefficient."""
    n = len(x)
    if n < 3:
        return 0.0, 1.0
    x_rank = np.argsort(np.argsort(np.asarray(x))).astype(float)
    y_rank = np.argsort(np.argsort(np.asarray(y))).astype(float)
    d = x_rank - y_rank
    rho = 1.0 - (6.0 * np.sum(d * d)) / (n * (n * n - 1.0))
    return rho, 0.0


def run_config(entropy, seed):
    """单次实验：给定熵水平和种子，运行 RecursiveWorld。"""
    if entropy is None:
        env_config = None
    else:
        env_config = {
            "N": ENV_N,
            "structural_entropy": entropy,
            "cycle_length": 5,
            "threshold": 0.0,
        }

    world = RecursiveWorld(
        N0=48, n0_active=40, n_colors=6, seed=seed,
        params=BASELINE_PARAMS, self_encapsulate=True,
        env_config=env_config,
        env_coupling_strength=COUPLING_STRENGTH if env_config else 0.0,
    )
    report = world.run(max_layers=MAX_LAYERS, verbose=False)

    depth = world.emergence_depth()

    absorption = compute_structure_absorption(world)
    rho = compute_env_system_rho(world)
    colonization = compute_colonization(world)

    env_flux = world.env.mean_flux() if world.env else None
    env_events = world.env_coupling.summary() if world.env_coupling else None

    return {
        "entropy": entropy,
        "seed": seed,
        "emergence_depth": depth,
        "n_layers": len(report),
        "layers": report,
        "structure_absorption": absorption,
        "env_system_rho": rho,
        "colonization": colonization,
        "env_flux": env_flux,
        "coupling_events": env_events,
    }


def main():
    results = []
    t0 = time.time()
    total = len(ENTROPIES) * SEEDS
    done = 0

    print(f"exp_186 P1: {total} runs ({len(ENTROPIES)} entropies x {SEEDS} seeds, "
          f"strength={COUPLING_STRENGTH}, env.N={ENV_N})")
    print("=" * 100)
    hdr = f"{'entropy':>8} {'seed':>4} {'depth':>5} {'L0_flux':>8} {'L1_flux':>8} "
    hdr += f"{'L2_flux':>8} {'L3_flux':>8} {'L0_orgs':>7} {'absorp':>7} {'rho':>7} {'col':>7} {'env_fl':>7}"
    print(hdr)
    print("-" * 100)

    for entropy in ENTROPIES:
        for seed in range(SEEDS):
            res = run_config(entropy, seed)
            results.append(res)
            done += 1

            depth = res["emergence_depth"]
            layers = res["layers"]
            l0 = layers[0] if len(layers) > 0 else {}
            l1 = layers[1] if len(layers) > 1 else {}
            l2 = layers[2] if len(layers) > 2 else {}
            l3 = layers[3] if len(layers) > 3 else {}
            env_f = res["env_flux"] if res["env_flux"] is not None else 0.0

            absorp = res["structure_absorption"].get(1, 0.0)
            rho_val = res["env_system_rho"].get(1, 0.0)
            col_val = res["colonization"].get(1, 0.0)

            e_str = str(entropy) if entropy is not None else "none"
            print(f"{e_str:>8} {seed:>4d} {depth:>5d} "
                  f"{l0.get('autonomous_flux', 0):>8.4f} "
                  f"{l1.get('autonomous_flux', 0):>8.4f} "
                  f"{l2.get('autonomous_flux', 0):>8.4f} "
                  f"{l3.get('autonomous_flux', 0):>8.4f} "
                  f"{l0.get('n_orgs', 0):>7d} "
                  f"{absorp:>7.3f} {rho_val:>7.3f} {col_val:>7.3f} {env_f:>7.4f}")

    elapsed = time.time() - t0
    print(f"\nTotal: {done}/{total} runs in {elapsed:.1f}s")

    # Summary table
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    shdr = f"{'entropy':>8} {'mean_dep':>8} {'L3+%':>7} {'L1_flux':>8} {'L2_flux':>8} "
    shdr += f"{'L3_flux':>8} {'L1_abs':>7} {'L2_abs':>7} {'L1_rho':>7} {'L2_rho':>7} "
    shdr += f"{'L1_col':>7} {'env_fl':>7}"
    print(shdr)
    print("-" * 100)

    for entropy in ENTROPIES:
        strs = [r for r in results if r["entropy"] == entropy]
        depths_v = [r["emergence_depth"] for r in strs]
        l1f = [r["layers"][1]["autonomous_flux"] for r in strs if len(r["layers"]) > 1]
        l2f = [r["layers"][2]["autonomous_flux"] for r in strs if len(r["layers"]) > 2]
        l3f = [r["layers"][3]["autonomous_flux"] for r in strs if len(r["layers"]) > 3]
        evf = [r["env_flux"] for r in strs if r["env_flux"] is not None]
        l3p = sum(1 for d in depths_v if d >= 3) / max(1, len(depths_v)) * 100
        l1a = np.mean([r["structure_absorption"].get(1, 0.0) for r in strs])
        l2a = np.mean([r["structure_absorption"].get(2, 0.0) for r in strs])
        l1r = np.mean([r["env_system_rho"].get(1, 0.0) for r in strs])
        l2r = np.mean([r["env_system_rho"].get(2, 0.0) for r in strs])
        l1c = np.mean([r["colonization"].get(1, 0.0) for r in strs])

        e_str = str(entropy) if entropy is not None else "none"
        print(f"{e_str:>8} {np.mean(depths_v):>8.2f} {l3p:>6.1f}% "
              f"{np.mean(l1f) if l1f else 0:>8.4f} "
              f"{np.mean(l2f) if l2f else 0:>8.4f} "
              f"{np.mean(l3f) if l3f else 0:>8.4f} "
              f"{l1a:>7.3f} {l2a:>7.3f} "
              f"{l1r:>7.3f} {l2r:>7.3f} {l1c:>7.3f} "
              f"{np.mean(evf) if evf else 0:>7.4f}")

    # Hypothesis tests
    print("\n" + "=" * 100)
    print("HYPOTHESIS TESTS")
    print("=" * 100)

    control = [r for r in results if r["entropy"] is None]
    c_depth = np.mean([r["emergence_depth"] for r in control])
    c_l1_flux = np.mean([r["layers"][1]["autonomous_flux"] for r in control if len(r["layers"]) > 1])

    for entropy in [0, 1, 2]:
        strs2 = [r for r in results if r["entropy"] == entropy]
        if not strs2:
            continue
        dm = np.mean([r["emergence_depth"] for r in strs2])
        l1m = np.mean([r["layers"][1]["autonomous_flux"] for r in strs2 if len(r["layers"]) > 1])
        l3pct = sum(1 for r in strs2 if r["emergence_depth"] >= 3) / len(strs2) * 100
        l1am = np.mean([r["structure_absorption"].get(1, 0.0) for r in strs2])
        l2am = np.mean([r["structure_absorption"].get(2, 0.0) for r in strs2])
        l1rm = np.mean([r["env_system_rho"].get(1, 0.0) for r in strs2])

        # H19-P3: Low complexity (entropy=0) → system ignores
        if entropy == 0:
            dd = abs(dm - c_depth) / max(0.01, c_depth) * 100
            fd = abs(l1m - c_l1_flux) / max(0.01, c_l1_flux) * 100
            print(f"\nH19-P3 (entropy=0, noise -> system ignores):")
            print(f"  depth: {dm:.2f} vs control {c_depth:.2f} ({dd:.1f}% change)")
            print(f"  L1 flux: {l1m:.4f} vs control {c_l1_flux:.4f} ({fd:.1f}% change)")
            if dd <= 5 and fd <= 5:
                print(f"  -> H19-P3 CONFIRMED (noise env ignored)")
            else:
                print(f"  -> H19-P3 REJECTED (noise env affects system)")

        # H19-P2: High complexity (entropy=2) → system absorbs
        if entropy == 2:
            print(f"\nH19-P2 (entropy=2, strong clusters -> system absorbs):")
            print(f"  L1 absorption: {l1am:.3f} (target > 0.5)")
            print(f"  L2 absorption: {l2am:.3f}")
            print(f"  L1 env-system rho: {l1rm:.3f} (target > 0.3)")
            if l1am > 0.5:
                print(f"  -> H19-P2 CONFIRMED (system absorbed env structure)")
            else:
                print(f"  -> H19-P2 NOT CONFIRMED (absorption {l1am:.3f} <= 0.5)")

        if entropy == 1:
            print(f"\nH19-P1 (entropy=1, weak clusters - reference):")
            print(f"  depth: {dm:.2f} (control={c_depth:.2f})")
            print(f"  L1 absorption: {l1am:.3f}")
            print(f"  L1 rho: {l1rm:.3f}")

    # Save
    out_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"exp_186_p1_complexity_sweep_{ts}.json")

    def convert(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "experiment": "exp_186_phase19_p1_complexity_sweep",
            "config": {
                "entropies": [str(e) if e is not None else "none" for e in ENTROPIES],
                "seeds": SEEDS,
                "coupling_strength": COUPLING_STRENGTH,
                "env_N": ENV_N,
                "params": BASELINE_PARAMS.__dict__,
            },
            "results": results,
        }, f, indent=2, ensure_ascii=False, default=convert)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()