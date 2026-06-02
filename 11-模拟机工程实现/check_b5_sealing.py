import json

with open("experiments/exp_118_b5_results.json") as f:
    data = json.load(f)

for seed, result in data.items():
    l0 = result.get("layer_0", {})
    sealed = l0.get("sealed")
    active = l0.get("n_active_bits")
    sealed_bits = l0.get("n_sealed_bits")
    steps = l0.get("final_step")
    print(f"Seed {seed}: sealed={sealed}, active_bits={active}, sealed_bits={sealed_bits}, steps={steps}")
