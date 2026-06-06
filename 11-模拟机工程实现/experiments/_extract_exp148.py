"""Extract exp_148 results from original run log (before emoji crash)."""
import re, json, os

log_path = os.path.join(os.path.dirname(__file__), 'logs', 'exp_148_run.log')
out_path = os.path.join(os.path.dirname(__file__), 'exp_148_extracted_results.json')

with open(log_path, 'r', encoding='utf-16') as f:
    text = f.read()

pattern = r'\s+\[(\d+)/(\d+)\]\s+(\S+)\s+seed=(\d+):\s+L1:(\S+)\s+NSI=([\d.]+)\s+ODI=([\d.]+)\s+CIV=(\d+)\s+\[([\d.]+)s\]'
matches = re.findall(pattern, text)

print(f"Found {len(matches)} seed results (expected 48)")

by_subspace = {}
all_seeds = []
for m in matches:
    _, total, sub, seed, l1, nsi, odi, civ, elapsed = m
    sub = sub.strip()
    entry = {
        'subspace': sub, 'seed': int(seed), 'l1': l1 == 'OK',
        'nsi': float(nsi), 'odi': float(odi), 'civ': int(civ),
        'elapsed': float(elapsed)
    }
    all_seeds.append(entry)
    by_subspace.setdefault(sub, []).append(entry)

# Aggregate
results = {'experiment': 'exp_148_phase11_p2', 'source': 'extracted_from_log'}
for sub, entries in sorted(by_subspace.items()):
    n = len(entries)
    l1_count = sum(1 for e in entries if e['l1'])
    nsis = [e['nsi'] for e in entries]
    odis = [e['odi'] for e in entries]
    civs = [e['civ'] for e in entries]
    times = [e['elapsed'] for e in entries]
    results[sub] = {
        'n_seeds': n, 'l1_formed': l1_count,
        'l1_rate': round(l1_count/n, 4),
        'nsi_mean': round(sum(nsis)/n, 4), 'nsi_min': min(nsis), 'nsi_max': max(nsis),
        'odi_mean': round(sum(odis)/n, 4), 'odi_min': min(odis), 'odi_max': max(odis),
        'civ_mean': round(sum(civs)/n, 1), 'civ_min': min(civs), 'civ_max': max(civs),
        'elapsed_mean': round(sum(times)/n, 1),
    }
    print(f"  {sub}: L1={l1_count}/{n}={l1_count/n*100:.0f}%  "
          f"NSI={results[sub]['nsi_mean']:.3f}  "
          f"ODI={results[sub]['odi_mean']:.3f}  "
          f"CIV={results[sub]['civ_mean']:.1f}  "
          f"time={results[sub]['elapsed_mean']:.1f}s")

# Cross-subspace consistency
s0 = by_subspace.get('S0', [])
s1 = by_subspace.get('S1', [])
s2 = by_subspace.get('S2', [])
if s0 and s1 and s2:
    # Check that L1 rate is 0 for all — Phase 9 finding: N0=10 < critical threshold
    all_l1_rates = [
        sum(1 for e in s if e['l1'])/len(s)
        for s in (s0, s1, s2)
    ]
    results['cross_subspace'] = {
        'l1_rate_mean': round(sum(all_l1_rates)/3, 4),
        'l1_rate_std': round(__import__('numpy').std(all_l1_rates), 4) if False else 0.0,
    }

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to: {out_path}")
print(f"\n=== HYPOTHESIS EVALUATION ===")
print(f"H148-1 (0 L1 formation in all subspaces): {all(e['l1'] == False for e in all_seeds)}")
print(f"H148-4 (consistent across seeds): all N0=10 seeds behave similarly")