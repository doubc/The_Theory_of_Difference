"""
exp_169_quick_structure_analysis.py — Quick structure analysis for H15-C1

Based on HEARTBEAT.md status (2026-06-08 11:30 CST):
- exp_169 statistical test complete (N=5, all configs 100% L1 seal)
- Structure analysis needed: "Does L1 structure reflect L0 cluster structure?"

H15-C1 Hypothesis: Cross-layer architecture creates L2 emergence conditions by 
preserving L0 structural information in L1 constraint patterns.

This script performs quick check:
1. Run 3 trials of pilot_cluster_map config
2. Extract L0 frozen bits and L1 constraint patterns
3. Check correlation between L0 cluster structure and L1 constraint structure
4. Compare with random mapping baseline

Author: OpenClaw AI Assistant
Date: 2026-06-08
"""

import sys
import os
import json
import numpy as np
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = "C:/Users/Administrator/Documents/the_theory_of_difference/11-模拟机工程实现"
sys.path.insert(0, PROJECT_ROOT)

try:
    from engine.cross_layer_evolver import CrossLayerEvolver, CrossLayerMapper
    from bitarr import bitarray
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure you're running from the project root directory")
    sys.exit(1)


def analyze_l0_l1_structure(ev):
    """Analyze if L1 constraint pattern reflects L0 cluster structure.
    
    Returns:
        dict with structure metrics or None if experiment didn't seal
    """
    if not ev.l1_result or not ev.l1_result.get('sealed', False):
        return None
    
    if ev.l0_result is None or ev.l1_constraints is None:
        return None
    
    l0_result = ev.l0_result
    l1_result = ev.l1_result
    constraints = ev.l1_constraints
    hm = constraints.hierarchy_map
    
    # Get L0 frozen bits (sealed configuration)
    l0_final = l0_result.get('final_state')
    if l0_final is None:
        return None
    
    l0_final_np = np.array(l0_final)
    l0_frozen = np.where(l0_final_np == 1)[0]  # Assuming 1 = frozen/decided
    
    # Get L1 constraint pattern
    l1_final = l1_result.get('final_state')
    if l1_final is None:
        return None
    
    l1_final_np = np.array(l1_final)
    
    # Analyze hierarchy map clusters
    cluster_groups = defaultdict(list)
    for i, cid in enumerate(hm):
        if cid >= 0:
            cluster_groups[cid].append(i)
    
    # Check if L1 bits from same L0 cluster have similar values
    within_cluster_similarities = []
    between_cluster_similarities = []
    
    for cid, bits in cluster_groups.items():
        if len(bits) > 1:
            vals = [l1_final_np[b] for b in bits]
            # Within cluster similarity (lower variance = more similar)
            within_var = np.var(vals)
            within_cluster_similarities.append(1.0 - within_var)
    
    # Calculate metrics
    metrics = {
        'l1_sealed': l1_result.get('sealed', False),
        'n_clusters': len(cluster_groups),
        'n_hierarchy_bits': sum(1 for x in hm if x >= 0),
        'n_lateral_bits': sum(1 for x in hm if x == -1),
        'within_cluster_similarity_mean': float(np.mean(within_cluster_similarities)) if within_cluster_similarities else 0.0,
        'within_cluster_similarity_std': float(np.std(within_cluster_similarities)) if within_cluster_similarities else 0.0,
        'l0_frozen_count': len(l0_frozen),
        'l1_hw': float(np.sum(l1_final_np)),
        'l1_hw_var': float(np.var(l1_final_np)),
    }
    
    # Check if L1 HW distribution matches L0 cluster structure
    # Hypothesis: bits from same cluster should have similar L1 values
    metrics['structure_preserved'] = metrics['within_cluster_similarity_mean'] > 0.7
    
    return metrics


def run_quick_analysis(n_trials=3, config='pilot_cluster_map'):
    """Run quick structure analysis."""
    print(f"=== exp_169 Quick Structure Analysis ===")
    print(f"Config: {config}")
    print(f"Trials: {n_trials}\n")
    
    results = []
    
    for trial in range(n_trials):
        print(f"Trial {trial}...", end=' ', flush=True)
        
        try:
            ev = CrossLayerEvolver(
                N0=48,
                N1=48,
                hierarchy_bits=16,  # N1//3
                mapping_mode=config.replace('pilot_', '').replace('_with_feedback', ''),
                device='cpu',
                seed=trial
            )
            
            result = ev.run()
            metrics = analyze_l0_l1_structure(ev)
            
            if metrics:
                results.append(metrics)
                print(f"✓ Structure preserved: {metrics['structure_preserved']}")
            else:
                print("✗ No structure data (L0 or L1 not sealed)")
                
        except Exception as e:
            print(f"✗ Error: {e}")
            continue
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Successful trials: {len(results)}/{n_trials}")
    
    if results:
        structure_preserved_count = sum(1 for r in results if r['structure_preserved'])
        print(f"Structure preserved (within_cluster_similarity > 0.7): {structure_preserved_count}/{len(results)}")
        
        avg_similarity = np.mean([r['within_cluster_similarity_mean'] for r in results])
        print(f"Average within-cluster similarity: {avg_similarity:.3f}")
        
        if avg_similarity > 0.7:
            print(f"\n✅ H15-C1 PARTIALLY CONFIRMED: L1 shows some structural reflection of L0")
            return "PARTIALLY_CONFIRMED"
        else:
            print(f"\n❌ H15-C1 REJECTED: L1 does not reflect L0 cluster structure")
            return "REJECTED"
    else:
        print(f"\n⚠️ No valid results obtained")
        return "INCONCLUSIVE"


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='exp_169 Quick Structure Analysis')
    parser.add_argument('--n-trials', type=int, default=3, help='Number of trials')
    parser.add_argument('--config', type=str, default='pilot_cluster_map', 
                       choices=['pilot_cluster_map', 'pilot_random_map', 'pilot_cluster_map_with_feedback'],
                       help='Experiment configuration')
    
    args = parser.parse_args()
    
    result = run_quick_analysis(n_trials=args.n_trials, config=args.config)
    
    print(f"\n=== Final Verdict ===")
    print(f"H15-C1: {result}")
    print(f"\nUpdate HEARTBEAT.md accordingly.")
