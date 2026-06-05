#!/usr/bin/env python3
"""
exp_143_auto_analyze.py — Auto-analysis for Phase 9 P1 (Time Scaling)

Usage:
  python docs/exp_143_auto_analyze.py
  (Scans experiments/ for the latest exp_143_*.json result file)

  Or:
  python docs/exp_143_auto_analyze.py experiments/exp_143_phase9_p1_time_scale_20260605_XXXX.json
"""
import sys, os, json, glob
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPERIMENTS_DIR = os.path.join(PROJECT_ROOT, 'experiments')
DOCS_DIR = os.path.join(PROJECT_ROOT, 'docs')

STEP_ORDER = [500, 1000, 2000, 5000, 10000]


def find_latest_result():
    pattern = os.path.join(EXPERIMENTS_DIR, 'exp_143_phase9_p1_time_scale_*.json')
    files = sorted(glob.glob(pattern))
    if not files:
        print("ERROR: No exp_143 result files found.")
        sys.exit(1)
    latest = files[-1]
    return latest, os.path.basename(latest)


def load_result(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_by_steps(data):
    by_steps = data.get('by_steps', {})
    rows = {}
    for steps_str in sorted(by_steps.keys(), key=lambda x: int(x)):
        steps = int(steps_str)
        ev = by_steps[steps_str]
        n_completed = ev.get('n_completed', 0)
        n_formed = ev.get('l1_formed', 0)
        formation_pct = n_formed / max(n_completed, 1) * 100
        mean_nsi = ev.get('mean_nsi_max', 0.0)
        mean_csci = ev.get('mean_csci_std', 0.0)
        mean_civ = ev.get('mean_civ_max', 0.0)
        mean_cont = ev.get('mean_continuity', 0.0)
        mean_nsi_active = ev.get('mean_nsi_active_rate', 0.0)
        first_seal = ev.get('mean_first_seal_step', -1)
        h89 = ev.get('h89_n', 0)
        rows[steps] = {
            'n_completed': n_completed,
            'n_formed': n_formed,
            'formation_pct': formation_pct,
            'mean_nsi': mean_nsi,
            'mean_csci': mean_csci,
            'mean_civ': mean_civ,
            'mean_cont': mean_cont,
            'mean_nsi_active': mean_nsi_active,
            'first_seal_mean': first_seal,
            'h89': h89,
        }
    return rows


def evaluate_hypotheses(rows):
    valid = [s for s in STEP_ORDER if s in rows and rows[s]['n_completed'] > 0]

    # H95: >=4/8 formed by step 500
    ev_500 = rows.get(500, {})
    h95_pass = ev_500.get('n_formed', 0) >= 4 if ev_500 else False

    # H96: H1-H8 stable at 2000+
    h89_2000 = rows.get(2000, {}).get('h89', 0) if 2000 in rows else 0
    h89_5000 = rows.get(5000, {}).get('h89', 0) if 5000 in rows else 0
    h89_10000 = rows.get(10000, {}).get('h89', 0) if 10000 in rows else 0
    degrad_2000_5000 = h89_2000 - h89_5000
    degrad_5000_10000 = h89_5000 - h89_10000
    degrad_count = sum([1 for d in [degrad_2000_5000, degrad_5000_10000] if d > 1])
    h96_pass = degrad_count == 0

    # H97: NSI saturation before 5000
    nsi_5000 = rows.get(5000, {}).get('mean_nsi', 0) if 5000 in rows else 0
    nsi_10000 = rows.get(10000, {}).get('mean_nsi', 0) if 10000 in rows else 0
    if nsi_5000 > 0 and nsi_10000 > 0:
        h97_pass = abs(nsi_10000 - nsi_5000) / max(nsi_5000, 0.001) < 0.05
    else:
        h97_pass = False

    n_pass = sum([h95_pass, h96_pass, h97_pass])
    return {
        'n_pass': n_pass,
        'hypotheses': {
            'H95': {'pass': h95_pass, 'detail': {'formed': ev_500.get('n_formed', 0)}},
            'H96': {'pass': h96_pass, 'detail': {'h89_2000': h89_2000, 'h89_5000': h89_5000, 'h89_10000': h89_10000, 'degradations': degrad_count}},
            'H97': {'pass': h97_pass, 'detail': {'nsi_5000': nsi_5000, 'nsi_10000': nsi_10000}},
        }
    }


def write_report(data, hypotheses, rows, result_file):
    timestamp = os.path.basename(result_file).replace('exp_143_phase9_p1_time_scale_', '').replace('.json', '')
    report_path = os.path.join(DOCS_DIR, f'exp_143_phase9_p1_analysis_{timestamp}.md')

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# Phase 9 P1: Time Scaling Analysis\n")
        f.write(f"**Date**: {data.get('datetime', timestamp)}\n")
        f.write(f"**Result file**: `{result_file}`\n\n")

        f.write("## Overview\n\n")
        f.write(f"Tests layer formation across steps ∈ {STEP_ORDER}, N0=72, 8 seeds each.\n\n")

        f.write("## Hypothesis Results\n\n")
        for h_name, h_info in hypotheses['hypotheses'].items():
            status = 'PASS' if h_info['pass'] else 'FAIL'
            f.write(f"### {h_name}: {status}\n\n")

        f.write(f"\n**Verdict: {hypotheses['n_pass']}/3 PASS**\n\n")

        f.write("## Per-Step Summary\n\n")
        f.write("| Steps | Seeds | Formed | Formation% | NSI | CSCIσ | Civ | SealStep | H1-H8 |\n")
        f.write("|-------|-------|--------|------------|-----|-------|-----|----------|-------|\n")
        for s in STEP_ORDER:
            if s in rows:
                r = rows[s]
                seal = f"{r['first_seal_mean']:.0f}" if r['first_seal_mean'] > 0 else '-'
                f.write(f"| {s} | {r['n_completed']} | {r['n_formed']} | {r['formation_pct']:.0f}% | "
                        f"{r['mean_nsi']:.3f} | {r['mean_csci']:.4f} | {r['mean_civ']:.1f} | "
                        f"{seal} | {r['h89']}/8 |\n")

        f.write("\n## H95: Layer Formation by Step 500\n\n")
        h95 = hypotheses['hypotheses']['H95']
        f.write(f"**{'PASS' if h95['pass'] else 'FAIL'}**\n\n")
        f.write("| Steps | Formed | Threshold |\n")
        f.write("|-------|--------|-----------|\n")
        for s in STEP_ORDER:
            if s in rows:
                ok = rows[s]['n_formed'] >= 4
                f.write(f"| {s} | {rows[s]['n_formed']}/8 | {'OK' if ok else '--'} |\n")

        f.write("\n## H96: H1-H8 Stability at Long Steps\n\n")
        h96 = hypotheses['hypotheses']['H96']
        f.write(f"**{'PASS' if h96['pass'] else 'FAIL'}**\n\n")
        f.write(f"2000: {h96['detail']['h89_2000']}/8 → 5000: {h96['detail']['h89_5000']}/8 → 10000: {h96['detail']['h89_10000']}/8\n")
        f.write(f"Degradations >1: {h96['detail']['degradations']}\n")

        f.write("\n## H97: NSI Saturation Before 5000\n\n")
        h97 = hypotheses['hypotheses']['H97']
        f.write(f"**{'PASS' if h97['pass'] else 'FAIL'}**\n\n")
        f.write(f"NSI at 5000: {h97['detail']['nsi_5000']:.4f}\n")
        f.write(f"NSI at 10000: {h97['detail']['nsi_10000']:.4f}\n")
        if h97['detail']['nsi_5000'] > 0:
            change = abs(h97['detail']['nsi_10000'] - h97['detail']['nsi_5000']) / max(h97['detail']['nsi_5000'], 0.001) * 100
            f.write(f"Change: {change:.1f}% (threshold: <5%)\n")

        f.write("\n## Recommended Next Steps\n\n")
        if hypotheses['n_pass'] >= 2:
            f.write("- **Proceed to Phase 9 P2 (Parameter Sensitivity)**.\n")
            f.write("- Architecture is time-robust.\n")
        else:
            f.write("- **Investigate step-dependent failures** before proceeding.\n")

        f.write("\n---\n")
        f.write(f"*Auto-generated by exp_143_auto_analyze.py at {timestamp}*\n")

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
    print(f"Step values: {data.get('step_values', 'unknown')}")

    rows = analyze_by_steps(data)
    hypotheses = evaluate_hypotheses(rows)

    print(f"\n=== Hypothesis Results ===")
    for h_name, h_info in hypotheses['hypotheses'].items():
        status = 'PASS' if h_info['pass'] else 'FAIL'
        print(f"  {h_name}: {status}")

    print(f"\n  Phase 9 P1: {hypotheses['n_pass']}/3 PASS\n")

    report_path = write_report(data, hypotheses, rows, result_path)
    print(f"\nAnalysis complete. Report: {report_path}")


if __name__ == '__main__':
    main()
