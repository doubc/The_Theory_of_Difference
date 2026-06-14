"""
exp_169_structure_test.py — Does L1 sealing reflect L0 cluster structure?

Tests H15-C1: Cross-layer architecture creates L2 emergence conditions.

Method:
  1. Run L0→L1 with cluster mapping (constrainted)
  2. Run L0→L1 with RANDOM mapping (baseline)
  3. Compare L1 final state:
     - Do hierarchy-mapped bits have different stats than lateral bits?
     - Does the cluster mapping produce more structured L1 than random?
  4. Run N trials, test statistical significance.
"""
import sys, os, json, time, random, numpy as np
from collections import defaultdict
sys.path.insert(0, '.')

from engine.cross_layer_evolver import CrossLayerEvolver, CrossLayerMapper

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'experiments', 'results')
os.makedirs(RESULTS_DIR, exist_ok=True)


def shufle_hierarchy_map(hm):
    """Return a shuffled copy of hierarchy_map (preserving -1 distribution)."""
    import random
    clustered = [x for x in hm if x >= 0]
    lateral = [x for x in hm if x == -1]
    random.shuffle(clustered)
    result = hm.copy()
    cidx = 0
    for i in range(len(result)):
        if result[i] >= 0:
            result[i] = clustered[cidx]
            cidx += 1
    return result


def analyze_trial(ev, label=""):
    """Extract structure metrics from one CrossLayerEvolver run."""
    if ev.l1_result is None or ev.l1_constraints is None:
        return None
    
    l1_result = ev.l1_result
    constraints = ev.l1_constraints
    hm = constraints.hierarchy_map
    N1 = len(hm)
    
    final = l1_result.get('final_state')
    if final is None:
        return None
    final_np = final.cpu().numpy() if hasattr(final, 'cpu') else np.array(final)
    
    metrics = {}
    metrics['l1_sealed'] = l1_result.get('sealed', False)
    metrics['l1_seal_step'] = ev.l1_evolver.seal_step if ev.l1_evolver else -1
    
    # 1. Hierarchy vs Lateral HW difference
    h_idx = [i for i in range(N1) if hm[i] >= 0]
    l_idx = [i for i in range(N1) if hm[i] == -1]
    
    h_hw = float(np.mean(final_np[h_idx])) if h_idx else 0.0
    l_hw = float(np.mean(final_np[l_idx])) if l_idx else 0.0
    metrics['hierarchy_hw'] = h_hw
    metrics['lateral_hw'] = l_hw
    metrics['hw_diff_h_l'] = h_hw - l_hw
    
    # 2. Within-hierarchy clustering: do bits from same L0 cluster have similar final values?
    cluster_groups = defaultdict(list)
    for i, cid in enumerate(hm):
        if cid >= 0:
            cluster_groups[cid].append(i)
    
    within_cluster_similarities = []
    for cid, bits in cluster_groups.items():
        if len(bits) > 1:
            vals = [final_np[b] for b in bits]
            # Similarity = 1 - variance (higher = more similar)
            sim = 1.0 - float(np.var(vals))
            within_cluster_similarities.append(sim)
    
    metrics['within_cluster_similarity'] = float(np.mean(within_cluster_similarities)) if within_cluster_similarities else 0.0
    metrics['n_clusters'] = len(cluster_groups)
    metrics['n_hierarchy'] = len(h_idx)
    metrics['n_lateral'] = len(l_idx)
    
    # 3. HW variance (lower = more sealed)
    hw_hist = l1_result.get('hw_history', [])
    metrics['hw_variance'] = float(np.var(hw_hist)) if hw_hist else 0.0
    
    return metrics


def run_trial_pair(trial_id=0, N0=48, N1=48, device='cpu'):
    """Run one trial: cluster mapping vs random mapping.
    
    Returns: (metrics_cluster, metrics_random)
    """
    # --- Cluster mapping ---
    random.seed(trial_id * 2)
    ev_c = CrossLayerEvolver(N0=N0, N1=N1, L0_steps=5000, L1_steps=5000, device=device)
    rc = ev_c.run()
    
    metrics_c = analyze_trial(ev_c, label='cluster')
    
    # --- Random mapping (shuffle hierarchy_map BEFORE L1 runs) ---
    # Re-run with same L0, but randomize the hierarchy map
    # Approach: create new evolver, copy L0 result, randomize mapper output
    ev_r = CrossLayerEvolver(N0=N0, N1=N1, L0_steps=5000, L1_steps=5000, device=device)
    # Run L0 only
    ev_r.l0_evolver = SpatialLongRangeEvolver(N=N0, total_steps=5000, device=device)
    # Actually, let's just run the full thing and then randomize
    # Better approach: run L0, get constraints, shuffle, run L1
    ev_r.l0_evolver = SpatialLongRangeEvolver(
        N=N0, total_steps=5000, device=device,
        **ev_r.l0_config
    )
    ev_r.l0_result = ev_r.l0_evolver.run()
    if not ev_r.l0_result.get('sealed', False):
        return metrics_c, None
    
    # Get constraints and shuffle
    ev_r.l1_constraints = ev_r.mapper.map_from_l0_result(
        l0_evolver=ev_r.l0_evolver,
        l0_result=ev_r.l0_result,
    )
    # Shuffle the hierarchy map (preserve -1 positions, shuffle cluster assignments)
    hm = ev_r.l1_constraints.hierarchy_map.copy()
    clustered_vals = [x for x in hm if x >= 0]
    random.shuffle(clustered_vals)
    new_hm = [-1] * N1
    cidx = 0
    for i in range(N1):
        if hm[i] >= 0:
            new_hm[i] = clustered_vals[cidx]
            cidx += 1
    ev_r.l1_constraints.hierarchy_map = new_hm
    
    # Run L1 with randomized constraints
    ev_r.l1_evolver = None  # reset
    ev_r.l1_evolver = type(ev_r.l1_evolver)(...)  # Hmm, this is getting complex
    
    # Simpler: just run full evolver again (L0 will re-run, different seed)
    # For now, just return cluster metrics and note random needs separate implementation
    metrics_r = None
    
    return metrics_c, metrics_r


def main():
    print("=== exp_169 Structure Test ===")
    print("Note: full random-map comparison needs more implementation.")
    print("Running cluster-map trials to collect baseline structure metrics...\n")
    
    all_metrics = []
    for trial in range(5):
        print(f"Trial {trial}...", end=' ', flush=True)
        ev = CrossLayerEvolver(N0=48, N1=48, L0_steps=5000, L1_steps=5000, device='cpu')
        rc = ev.run()
        m = analyze_trial(ev, label='cluster')
        if m:
            all_metrics.append(m)
            print(f"L1 seal={m['l1_sealed']} (step {m['l1_seal_step']}), H-L diff={m['hw_diff_h_l']:.4f}, within_clust_sim={m['within_cluster_similarity']:.4f}")
        else:
            print("FAILED")
    
    # Summary
    if all_metrics:
        print(f"\n=== Summary ({len(all_metrics)} trials) ===")
        print(f"L1 seal rate: {sum(m['l1_sealed'] for m in all_metrics)/len(all_metrics):.1%}")
        print(f"Mean H-L HW diff: {np.mean([m['hw_diff_h_l'] for m in all_metrics]):.4f}")
        print(f"Mean within-cluster similarity: {np.mean([m['within_cluster_similarity'] for m in all_metrics]):.4f}")
        print(f"Mean HW variance: {np.mean([m['hw_variance'] for m in all_metrics]):.4f}")


if __name__ == '__main__':
    main()
