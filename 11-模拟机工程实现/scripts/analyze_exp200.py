"""Quick analysis of exp_200 results."""
import json
from pathlib import Path

with open("results/exp_200_p0_energy_baseline.json") as f:
    results = json.load(f)

# Group by config
by_cfg = {}
for r in results:
    if 'error' in r:
        print(f"ERROR {r['config']} seed={r['seed']}: {r['error']}")
        continue
    cfg = r['config']
    by_cfg.setdefault(cfg, []).append(r)

for cfg in sorted(by_cfg.keys()):
    rows = by_cfg[cfg]
    print(f"\n=== {cfg} ({len(rows)} seeds) ===")
    for r in rows:
        fluxes = [rec.get('autonomous_flux', 0) for rec in r['report']]
        depths = [rec.get('layer', -1) for rec in r['report']]
        energy_ratios = [rec.get('energy_ratio', None) for rec in r['report']]
        print(f"  seed={r['seed']:2d}  depth={r['emergence_depth']}  "
              f"fluxes={[round(f,4) for f in fluxes]}  "
              f"energy_ratios={[round(e,2) if e else None for e in energy_ratios]}")
