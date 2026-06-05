#!/usr/bin/env python3
"""
exp_142_auto_analyze.py — Auto-analysis for Phase 9 P0 (N0 Scaling)

Usage:
  python docs/exp_142_auto_analyze.py
  (Scans experiments/ for the latest exp_142_*.json result file)

  Or:
  python docs/exp_142_auto_analyze.py experiments/exp_142_phase9_p0_n0_scale_20260605_XXXX.json
"""
import sys, os, json, glob, re
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPERIMENTS_DIR = os.path.join(PROJECT_ROOT, 'experiments')
DOCS_DIR = os.path.join(PROJECT_ROOT, 'docs')

N0_ORDER = [24, 36, 48, 72, 96, 144, 288]
NRC_KEYS = ['nrc_active', 'n_cycles', 'n_r2_events', 'n_rewrites', 'cumulative_tension', 'peak_nsi']
L1_KEYS = ['l1_formed', 'l1_nsi_samples', 'l1_mean_nsi', 'l1_seal_ratio',
           'l0_l1_theme_divergence', 'l1_mean_civ', 'l1_civ_samples']


def find_latest_result():
    pattern = os.path.join(EXPERIMENTS_DIR, 'exp_142_phase9_p0_n0_scale_*.json')
    files = sorted(glob.glob(pattern))
    if not files:
        print("ERROR: No exp_142 result files found.")
        sys.exit(1)
    latest = files[-1]
    return latest, os.path.basename(latest)


def load_result(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_by_n0(data):
    """Aggregate per-N0 metrics from the by_n0 dict."""
    by_n0 = data.get('by_n0', {})
    rows = {}
    for n0_str in sorted(by_n0.keys(), key=lambda x: int(x)):
        n0 = int(n0_str)
        ev = by_n0[n0_str]
        n_completed = ev.get('n_completed', 0)
        formation_rate = ev.get('formation_rate', ev.get('n_formed', 0) / max(ev.get('n_completed', 1), 1))
        n_formed = ev.get('n_formed', 0)
        mean_nsi = ev.get('mean_nsi', ev.get('mean_nse_nsi', 0.0))
        mean_csci = ev.get('mean_csc_csci_std', ev.get('mean_csci_std', 0.0))
        mean_civ = ev.get('mean_civ_max', 0.0)
        mean_divergence = ev.get('mean_divergence', 0.0)
        mean_seal_ratio = ev.get('mean_seal_ratio', 0.0)
        mean_td = ev.get('mean_topdown_max', 0.0)
        mean_cont = ev.get('mean_continuity', 0.0)
        mean_hd = ev.get('mean_history_depth', 0.0)
        mean_nsi_active = ev.get('mean_nsi_active_rate', 0.0)
        first_seal_mean = ev.get('first_seal_mean', -1.0)

        # H1-H8
        h1 = ev.get('h1_nsi_max', mean_nsi) > 0.1
        h2_rate = ev.get('h2_nsi_active_rate', mean_nsi_active)
        h2 = h2_rate > 0.3 if h2_rate else False
        h3 = ev.get('h3_continuity_mean', mean_cont) > 0.1
        h4 = ev.get('h4_hd_mean', mean_hd) > 0.05
        h5 = mean_civ >= 3
        h6 = mean_civ >= 2
        h7 = mean_csci > 0.005
        h8 = ev.get('h8_td_active_seeds', 0) >= 2
        h_pass = sum([h1, h2, h3, h4, h5, h6, h7, h8])

        rows[n0] = {
            'n_completed': n_completed,
            'n_formed': n_formed,
            'formation_pct': formation_rate * 100,
            'H90_pass': n_formed >= 6,
            'mean_nsi': mean_nsi,
            'mean_csci': mean_csci,
            'mean_civ': mean_civ,
            'mean_divergence': mean_divergence,
            'mean_seal_ratio': mean_seal_ratio,
            'mean_td': mean_td,
            'mean_cont': mean_cont,
            'mean_hd': mean_hd,
            'mean_nsi_active': mean_nsi_active,
            'first_seal_mean': first_seal_mean,
            'H1-H8_pass': h_pass,
            'h1': h1, 'h2': h2, 'h3': h3, 'h4': h4,
            'h5': h5, 'h6': h6, 'h7': h7, 'h8': h8,
        }
    return rows


def evaluate_hypotheses(rows):
    """Evaluate 4 overarching hypotheses."""
    valid_n0 = [n0 for n0 in N0_ORDER if n0 in rows and rows[n0]['n_completed'] > 0]

    # H90: Layer formation ≥ 6/8 seeds at N0 ≥ 36
    n0_ge36 = [n0 for n0 in valid_n0 if n0 >= 36]
    h90_pass = all(rows[n0]['H90_pass'] for n0 in n0_ge36) if n0_ge36 else False
    h90_detail = {n0: rows[n0]['formation_pct'] for n0 in valid_n0}

    # H91: NSI monotonic with N0
    nsi_vals = [rows[n0]['mean_nsi'] for n0 in valid_n0]
    if len(nsi_vals) >= 3:
        from scipy.stats import spearmanr
        sp_nsi, p_nsi = spearmanr(valid_n0, nsi_vals)
        h91_pass = sp_nsi > 0.5
    else:
        sp_nsi, p_nsi = 0.0, 1.0
        h91_pass = False
    h91_detail = {n0: rows[n0]['mean_nsi'] for n0 in valid_n0}

    # H92: Convergence time scales sub-linearly with N0
    seal_n0 = [n0 for n0 in valid_n0 if rows[n0]['first_seal_mean'] > 0]
    if len(seal_n0) >= 3:
        seal_steps = [rows[n0]['first_seal_mean'] for n0 in seal_n0]
        from scipy.stats import spearmanr
        sp_seal, _ = spearmanr(seal_n0, seal_steps)
        seal_ratios = [rows[n0]['first_seal_mean'] / n0 for n0 in seal_n0]
        sp_ratio, _ = spearmanr(seal_n0, seal_ratios)
        h92_pass = sp_ratio <= 0.3  # Not positively correlated
    else:
        sp_seal, sp_ratio = 0.0, 0.0
        h92_pass = False
    h92_detail = {n0: {'first_seal': rows[n0]['first_seal_mean'],
                        'ratio': rows[n0]['first_seal_mean'] / n0 if n0 > 0 else 'n/a'}
                  for n0 in valid_n0 if rows[n0]['first_seal_mean'] > 0}

    # H93: L0-L1 divergence near 0 at all N0
    div_vals = [rows[n0]['mean_divergence'] for n0 in valid_n0 if n0 >= 24]
    h93_pass = all(d < 0.05 for d in div_vals) if div_vals else False
    h93_detail = {n0: rows[n0]['mean_divergence'] for n0 in valid_n0}

    n_pass = sum([h90_pass, h91_pass, h92_pass, h93_pass])
    return {
        'n_pass': n_pass,
        'hypotheses': {
            'H90': {'pass': h90_pass, 'detail': h90_detail},
            'H91': {'pass': h91_pass, 'detail': h91_detail, 'spearman_rho': sp_nsi, 'p_value': p_nsi},
            'H92': {'pass': h92_pass, 'detail': h92_detail, 'seal_rho': sp_seal, 'ratio_rho': sp_ratio},
            'H93': {'pass': h93_pass, 'detail': h93_detail},
        }
    }


def write_report(data, hypotheses, rows, result_file):
    timestamp = os.path.basename(result_file).replace('exp_142_phase9_p0_n0_scale_', '').replace('.json', '')
    report_path = os.path.join(DOCS_DIR, f'exp_142_phase9_p0_analysis_{timestamp}.md')

    max_n0 = max(N0_ORDER)
    min_n0 = min(N0_ORDER)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# Phase 9 P0: N0 Scaling Analysis\n")
        f.write(f"**Date**: {data.get('datetime', timestamp)}\n")
        f.write(f"**Result file**: `{result_file}`\n\n")

        f.write("## Overview\n\n")
        f.write(f"Tests layer formation across N0 ∈ {min_n0}–{max_n0} × 8 seeds × 2000 steps.\n\n")

        f.write("## Hypothesis Results\n\n")
        for h_name, h_info in hypotheses['hypotheses'].items():
            status = '✅ PASS' if h_info['pass'] else '❌ FAIL'
            f.write(f"### {h_name}: {status}\n\n")

        f.write(f"\n**Verdict: {hypotheses['n_pass']}/4 PASS**\n\n")

        f.write("## Per-N0 Summary\n\n")
        f.write(f"| N0 | Seeds | Formed | Formation% | NSI | CSCIσ | Civ | Divergence | SealRatio | H1-H8 |\n")
        f.write(f"|----|-------|--------|------------|-----|-------|-----|------------|-----------|-------|\n")
        for n0 in N0_ORDER:
            if n0 in rows:
                r = rows[n0]
                f.write(f"| {n0} | {r['n_completed']} | {r['n_formed']} | {r['formation_pct']:.0f}% | "
                        f"{r['mean_nsi']:.3f} | {r['mean_csci']:.4f} | {r['mean_civ']:.1f} | "
                        f"{r['mean_divergence']:.4f} | {r['mean_seal_ratio']:.3f} | {r['H1-H8_pass']}/8 |\n")

        f.write("\n## H90: Layer Formation ≥ 6/8 at N0 ≥ 36\n\n")
        f.write(f"**{'PASS' if hypotheses['hypotheses']['H90']['pass'] else 'FAIL'}**\n\n")
        f.write("| N0 | Formation% | ≥6/8? |\n")
        f.write("|----|------------|-------|\n")
        for n0 in N0_ORDER:
            if n0 in rows:
                ok = rows[n0]['H90_pass']
                f.write(f"| {n0} | {rows[n0]['formation_pct']:.0f}% | {'✅' if ok else '❌'} |\n")

        f.write("\n## H91: NSI Monotonic with N0\n\n")
        h91 = hypotheses['hypotheses']['H91']
        f.write(f"**{'PASS' if h91['pass'] else 'FAIL'}**\n")
        f.write(f"Spearman ρ = {h91.get('spearman_rho', 0):.3f} (threshold: >0.5)\n\n")
        f.write("| N0 | Mean NSI |\n")
        f.write("|----|----------|\n")
        for n0 in N0_ORDER:
            if n0 in rows:
                f.write(f"| {n0} | {rows[n0]['mean_nsi']:.4f} |\n")

        f.write("\n## H92: Convergence Sub-linear with N0\n\n")
        h92 = hypotheses['hypotheses']['H92']
        f.write(f"**{'PASS' if h92['pass'] else 'FAIL'}**\n")
        f.write(f"Seal-steps ρ = {h92.get('seal_rho', 0):.3f}, Ratio ρ = {h92.get('ratio_rho', 0):.3f} (want ≤0.3)\n\n")
        f.write("| N0 | First Seal | Seal/N0 |\n")
        f.write("|----|------------|---------|\n")
        for n0 in N0_ORDER:
            if n0 in rows and rows[n0]['first_seal_mean'] > 0:
                ratio = rows[n0]['first_seal_mean'] / n0
                f.write(f"| {n0} | {rows[n0]['first_seal_mean']:.0f} | {ratio:.2f} |\n")
            elif n0 in rows:
                f.write(f"| {n0} | — | — |\n")

        f.write("\n## H93: L0-L1 Divergence ≈0 Across N0\n\n")
        h93 = hypotheses['hypotheses']['H93']
        f.write(f"**{'PASS' if h93['pass'] else 'FAIL'}**\n\n")
        f.write("| N0 | Divergence |\n")
        f.write("|----|------------|\n")
        for n0 in N0_ORDER:
            if n0 in rows:
                ok = rows[n0]['mean_divergence'] < 0.05
                f.write(f"| {n0} | {rows[n0]['mean_divergence']:.4f} {'✅' if ok else '❌'} |\n")

        f.write("\n## NSI Metrics Detail\n\n")
        f.write("| N0 | NSI Mean | NSI Max | NSI Active | Continuity | History Depth | Civ Mean | Civ Max |\n")
        f.write("|----|----------|---------|------------|------------|---------------|----------|--------|\n")
        for n0 in N0_ORDER:
            if n0 in rows:
                r = rows[n0]
                f.write(f"| {n0} | {r['mean_nsi']:.3f} | — | {r['mean_nsi_active']:.2f} | {r['mean_cont']:.3f} | "
                        f"{r['mean_hd']:.3f} | — | {r['mean_civ']:.1f} |\n")

        f.write("\n## Recommended Next Steps\n\n")
        n_pass = hypotheses['n_pass']
        if n_pass >= 3:
            f.write("- **Proceed to Phase 9 P1 (Time Scaling)** — N0 scaling robust.\n")
            f.write("- P1 tests step counts: 500, 1000, 2000, 5000, 10000\n")
            f.write("- Also proceed to P2 (parameter sensitivity) if time permits.\n")
        elif n_pass >= 2:
            f.write("- **Address failed hypotheses before P1**.\n")
            f.write("- May need to investigate why scaling hypothesis failed.\n")
            f.write("- Consider expanding the N0 range upward or re-examining metrics.\n")
        else:
            f.write("- **Stop and reassess** — too many hypotheses failed.\n")
            f.write("- The architecture may not be robust across N0 scales.\n")

        f.write("\n---\n")
        f.write(f"*Auto-generated by exp_142_auto_analyze.py at {timestamp}*\n")

    print(f"Report written: {report_path}")
    return report_path


def main():
    if len(sys.argv) > 1:
        result_path = sys.argv[1]
    else:
        result_path, basename = find_latest_result()

    print(f"Loading: {result_path}")
    data = load_result(result_path)
    print(f"Experiment: {data.get('experiment', 'unknown')}")
    print(f"Timestamp:  {data.get('datetime', 'unknown')}")
    print(f"N0 values:  {data.get('n0_values', 'unknown')}")

    rows = analyze_by_n0(data)
    hypotheses = evaluate_hypotheses(rows)

    print(f"\n=== Hypothesis Results ===")
    for h_name, h_info in hypotheses['hypotheses'].items():
        status = 'PASS' if h_info['pass'] else 'FAIL'
        print(f"  {h_name}: {status}")

    print(f"\n  Phase 9 P0: {hypotheses['n_pass']}/4 PASS\n")

    report_path = write_report(data, hypotheses, rows, result_path)
    print(f"\nAnalysis complete. Report: {report_path}")


if __name__ == '__main__':
    main()