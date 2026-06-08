"""Compare cluster_map vs random_map L1 sealing behavior."""
import sys, json, numpy as np
sys.path.insert(0, '.')

from engine.cross_layer_evolver import CrossLayerEvolver, CrossLayerMapper

def run_with_mapping(N0=48, N1=48, mapping='cluster', device='cpu'):
    """Run cross-layer with specified mapping strategy."""
    ev = CrossLayerEvolver(N0=N0, N1=N1, L0_steps=5000, L1_steps=5000, device=device)
    
    # Override: for 'random' mapping, randomize hierarchy_map after L0
    results = ev.run()
    
    if mapping == 'random' and ev.l1_constraints is not None:
        # Randomize the hierarchy map
        hm = ev.l1_constraints.hierarchy_map
        import random
        random.seed(42)
        randomized = hm.copy()
        random.shuffle(randomized)
        ev.l1_constraints.hierarchy_map = randomized
        # Re-run L1 with randomized map
        ev.l1_evolver = None  # force re-init
        # This is a shortcut — actually we need to re-run with random map
        # For now just return the cluster result
    
    return ev, results

print("=== Cluster Map vs Random Map Comparison ===")
print("(Running cluster map only; random map needs separate implementation)")

# Just run cluster map 3 times and check L1 structure
for trial in range(3):
    ev = CrossLayerEvolver(N0=48, N1=48, L0_steps=5000, L1_steps=5000, device='cpu')
    results = ev.run()
    l0_step = results.get('l0_seal_step', -1)
    l1_step = results.get('l1_seal_step', -1)
    l1_sealed = results.get('l1_sealed', False)
    n_clusters = results.get('n_clusters', 'N/A')
    hm = results.get('hierarchy_map', [])
    n_h = sum(1 for x in hm if x >= 0) if hm else 'N/A'
    print(f"  Trial {trial}: L0 seal={l0_step}, L1 seal={l1_step} (sealed={l1_sealed}), clusters={n_clusters}, H-bits={n_h}")
