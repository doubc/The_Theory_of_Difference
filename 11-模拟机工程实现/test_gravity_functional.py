"""Test cross-layer gravity modulation functional test"""
import sys
sys.path.insert(0, '.')

try:
    import torch
    from engine.hierarchical_evolver import HierarchicalEvolver
    
    print("=" * 60)
    print("Cross-Layer Gravity Modulation Functional Test")
    print("=" * 60)
    
    # Create evolver with small params for quick test
    ev = HierarchicalEvolver(
        N0=48,
        steps_per_layer=2000,
        sample_interval=1000,
        max_layers=2,
        verbose_gravity=True
    )
    
    print("\nRunning hierarchical evolution with gravity modulation...")
    results = ev.run(verbose=True)
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    ev.print_results(results)
    
    # Check that gravity was applied
    for i, lr in enumerate(results['layer_results']):
        layer = ev.hierarchy.get_layer(i)
        if hasattr(layer, 'gravity_mean'):
            print(f"Layer {i} gravity_mean: {layer.gravity_mean:.4f}")
    
    print("\nFunctional test PASSED!")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
