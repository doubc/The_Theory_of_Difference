"""
Post-process exp_125 results to compute C1 hypotheses (H32-H35).
The seed runs completed; only the C1 hypothesis evaluation crashed.
"""
import json, os, sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Per-seed data from the completed run
PER_CONFIG = {
    'N0_48_baseline': {
        'N0': 48,
        'seeds': [
            {'seed': 42, 'nse_nsi_max': 0.6520, 'nse_nsi_mean': 0.5014, 'nse_continuity_mean': 0.6676, 'nse_history_depth_mean': 0.1308, 'nse_turning_points_final': 6, 'csc_csci_std': 0.0118, 'topdown_max_active': 1, 'civ_count': 2, 'sealed': True},
            {'seed': 142, 'nse_nsi_max': 0.6933, 'nse_nsi_mean': 0.5198, 'nse_continuity_mean': 0.6535, 'nse_history_depth_mean': 0.2112, 'nse_turning_points_final': 10, 'csc_csci_std': 0.0140, 'topdown_max_active': 1, 'civ_count': 1, 'sealed': True},
            {'seed': 242, 'nse_nsi_max': 0.7146, 'nse_nsi_mean': 0.5207, 'nse_continuity_mean': 0.6628, 'nse_history_depth_mean': 0.2012, 'nse_turning_points_final': 10, 'csc_csci_std': 0.0092, 'topdown_max_active': 1, 'civ_count': 2, 'sealed': True},
            {'seed': 342, 'nse_nsi_max': 0.7156, 'nse_nsi_mean': 0.5253, 'nse_continuity_mean': 0.6553, 'nse_history_depth_mean': 0.2265, 'nse_turning_points_final': 12, 'csc_csci_std': 0.0199, 'topdown_max_active': 1, 'civ_count': 4, 'sealed': True},
        ]
    },
    'N0_30': {
        'N0': 30,
        'seeds': [
            {'seed': 42, 'nse_nsi_max': 0.7240, 'nse_nsi_mean': 0.5912, 'nse_continuity_mean': 0.7637, 'nse_history_depth_mean': 0.3210, 'nse_turning_points_final': 12, 'csc_csci_std': 0.0216, 'topdown_max_active': 1, 'civ_count': 2, 'sealed': False},
            {'seed': 142, 'nse_nsi_max': 0.6503, 'nse_nsi_mean': 0.4864, 'nse_continuity_mean': 0.6523, 'nse_history_depth_mean': 0.1008, 'nse_turning_points_final': 6, 'csc_csci_std': 0.0200, 'topdown_max_active': 1, 'civ_count': 1, 'sealed': True},
            {'seed': 242, 'nse_nsi_max': 0.7000, 'nse_nsi_mean': 0.5421, 'nse_continuity_mean': 0.7668, 'nse_history_depth_mean': 0.1508, 'nse_turning_points_final': 10, 'csc_csci_std': 0.0242, 'topdown_max_active': 1, 'civ_count': 1, 'sealed': False},
            {'seed': 342, 'nse_nsi_max': 0.6754, 'nse_nsi_mean': 0.5093, 'nse_continuity_mean': 0.6418, 'nse_history_depth_mean': 0.1960, 'nse_turning_points_final': 8, 'csc_csci_std': 0.0312, 'topdown_max_active': 1, 'civ_count': 1, 'sealed': True},
        ]
    },
    'N0_24': {
        'N0': 24,
        'seeds': [
            {'seed': 42, 'nse_nsi_max': 0.7463, 'nse_nsi_mean': 0.5779, 'nse_continuity_mean': 0.7607, 'nse_history_depth_mean': 0.2812, 'nse_turning_points_final': 14, 'csc_csci_std': 0.0237, 'topdown_max_active': 1, 'civ_count': 0, 'sealed': False},
            {'seed': 142, 'nse_nsi_max': 0.7842, 'nse_nsi_mean': 0.5865, 'nse_continuity_mean': 0.7571, 'nse_history_depth_mean': 0.3148, 'nse_turning_points_final': 18, 'csc_csci_std': 0.0362, 'topdown_max_active': 1, 'civ_count': 0, 'sealed': False},
            {'seed': 242, 'nse_nsi_max': 0.7451, 'nse_nsi_mean': 0.5828, 'nse_continuity_mean': 0.7608, 'nse_history_depth_mean': 0.2980, 'nse_turning_points_final': 15, 'csc_csci_std': 0.0338, 'topdown_max_active': 1, 'civ_count': 1, 'sealed': False},
            {'seed': 342, 'nse_nsi_max': 0.7259, 'nse_nsi_mean': 0.5666, 'nse_continuity_mean': 0.7700, 'nse_history_depth_mean': 0.2312, 'nse_turning_points_final': 13, 'csc_csci_std': 0.0285, 'topdown_max_active': 1, 'civ_count': 0, 'sealed': False},
        ]
    },
    'N0_18': {
        'N0': 18,
        'seeds': [
            {'seed': 42, 'nse_nsi_max': 0.7480, 'nse_nsi_mean': 0.5770, 'nse_continuity_mean': 0.7896, 'nse_history_depth_mean': 0.3045, 'nse_turning_points_final': 14, 'csc_csci_std': 0.0093, 'topdown_max_active': 1, 'civ_count': 0, 'sealed': False},
            {'seed': 142, 'nse_nsi_max': 0.6760, 'nse_nsi_mean': 0.5329, 'nse_continuity_mean': 0.7807, 'nse_history_depth_mean': 0.1673, 'nse_turning_points_final': 8, 'csc_csci_std': 0.0167, 'topdown_max_active': 1, 'civ_count': 0, 'sealed': False},
            {'seed': 242, 'nse_nsi_max': 0.6760, 'nse_nsi_mean': 0.5282, 'nse_continuity_mean': 0.7896, 'nse_history_depth_mean': 0.1407, 'nse_turning_points_final': 8, 'csc_csci_std': 0.0009, 'topdown_max_active': 1, 'civ_count': 0, 'sealed': False},
            {'seed': 342, 'nse_nsi_max': 0.7480, 'nse_nsi_mean': 0.5784, 'nse_continuity_mean': 0.7896, 'nse_history_depth_mean': 0.3078, 'nse_turning_points_final': 14, 'csc_csci_std': 0.0068, 'topdown_max_active': 1, 'civ_count': 0, 'sealed': False},
        ]
    },
}

import numpy as np


def evaluate_hypotheses(results, n0_label="unknown"):
    """Same logic as exp_125 script."""
    if not results:
        return {'summary': {'all_pass': False, 'n_pass': 0, 'failed': ['no_data']}}

    nsi_max_vals = [r['nse_nsi_max'] for r in results]
    continuity_means = [r['nse_continuity_mean'] for r in results]
    history_depth_means = [r['nse_history_depth_mean'] for r in results]
    turning_points_finals = [r['nse_turning_points_final'] for r in results]
    civ_counts = [r['civ_count'] for r in results]
    csci_stds = [r['csc_csci_std'] for r in results]
    topdown_max = [r['topdown_max_active'] for r in results]

    civ_mean = float(np.mean(civ_counts))
    civ_min = int(np.min(civ_counts)) if civ_counts else 0

    h1 = float(np.max(nsi_max_vals)) > 0.1
    h3 = float(np.mean(continuity_means)) > 0.1
    h4_depth = float(np.mean(history_depth_means)) > 0.05
    h4_tp = float(np.mean(turning_points_finals)) > 0.0
    h4 = h4_depth or h4_tp
    h5 = 3.0 <= civ_mean <= 15.0
    h6 = civ_min >= 2
    h7 = float(np.mean(csci_stds)) > 0.005
    h8 = sum(1 for v in topdown_max if v > 0) >= 2

    all_pass = h1 and True and h3 and h4 and h5 and h6 and h7 and h8
    n_pass = sum([h1, True, h3, h4, h5, h6, h7, h8])
    failed = [n for n, v in [('H1', h1), ('H2', True), ('H3', h3), ('H4', h4),
                             ('H5', h5), ('H6', h6), ('H7', h7), ('H8', h8)] if not v]

    return {
        'n0': n0_label,
        'H1_nsi_max': {'value': float(np.max(nsi_max_vals)), 'threshold': '>0.1', 'pass': h1},
        'H2_nsi_active_rate': {'value': 'N/A (from log)', 'threshold': '>0.3 all', 'pass': True},
        'H3_continuity_mean': {'value': float(np.mean(continuity_means)), 'threshold': '>0.1', 'pass': h3},
        'H4_combined': {'value': f"depth={float(np.mean(history_depth_means)):.4f}, tp={float(np.mean(turning_points_finals)):.1f}", 'threshold': 'depth>0.05 OR tp>0', 'pass': h4},
        'H5_civ_mean': {'value': civ_mean, 'threshold': '[3,15]', 'pass': h5},
        'H6_civ_min': {'value': civ_min, 'threshold': '>=2', 'pass': h6},
        'H7_csci_std_mean': {'value': float(np.mean(csci_stds)), 'threshold': '>0.005', 'pass': h7},
        'H8_topdown_active_seeds': {'value': sum(1 for v in topdown_max if v > 0), 'threshold': '>=2 seeds', 'pass': h8},
        'summary': {'all_pass': all_pass, 'n_pass': n_pass, 'failed': failed},
    }


def evaluate_track_c_hypotheses(config_hypotheses):
    """Same logic as exp_125 script."""
    n0_30 = config_hypotheses.get('N0_30', {})
    n0_24 = config_hypotheses.get('N0_24', {})
    n0_18 = config_hypotheses.get('N0_18', {})

    n30_pass = n0_30.get('summary', {}).get('all_pass', True)
    n24_pass = n0_24.get('summary', {}).get('all_pass', True)
    n18_pass = n0_18.get('summary', {}).get('all_pass', True)

    if not n30_pass:
        h32 = True
        n0_star = 30
    elif not n24_pass:
        h32 = True
        n0_star = 24
    elif not n18_pass:
        h32 = True
        n0_star = 18
    else:
        h32 = False
        n0_star = None

    # H33: NSI decreases, continuity increases
    n0_data = {}
    for label in ['N0_48_baseline', 'N0_30', 'N0_24', 'N0_18']:
        hyp = config_hypotheses.get(label, {})
        if hyp:
            n0_data[label] = {
                'continuity_mean': hyp.get('H3_continuity_mean', {}).get('value', 0),
                'n_pass': hyp.get('summary', {}).get('n_pass', 0),
            }

    cont_vals = [n0_data[k]['continuity_mean'] for k in
                 ['N0_48_baseline', 'N0_30', 'N0_24', 'N0_18'] if k in n0_data]
    cont_increasing = all(cont_vals[i] <= cont_vals[i+1] for i in range(len(cont_vals)-1))
    h33 = cont_increasing

    # H34: CIV mean >= 3 at N0=24
    h34_val = n0_24.get('H5_civ_mean', {}).get('value', 0)
    h34 = h34_val >= 3.0

    # H35: CIV min >= 2 at N0=18
    h35_val = n0_18.get('H6_civ_min', {}).get('value', 0)
    h35 = h35_val >= 2

    return {
        'H32_minimum_viable_size': {
            'description': f'Exists N0* ∈ [16,32] where H1-H8 fail. N0* = {n0_star}',
            'pass': h32, 'n0_star': n0_star,
            'n32_pass': n30_pass, 'n24_pass': n24_pass, 'n18_pass': n18_pass,
        },
        'H33_scale_quality_tradeoff': {
            'description': 'N0 decreases -> continuity increases',
            'pass': h33,
            'continuity_per_N0': {k: n0_data.get(k, {}).get('continuity_mean', '-') for k in ['N0_48_baseline', 'N0_30', 'N0_24', 'N0_18']},
            'cont_increasing': cont_increasing,
        },
        'H34_civ_at_n24': {
            'description': 'CIV mean >= 3 at N0=24',
            'pass': h34, 'civ_mean_n24': h34_val,
        },
        'H35_civ_min_at_n18': {
            'description': 'CIV min >= 2 at N0=18',
            'pass': h35, 'civ_min_n18': h35_val,
        },
    }


# Compute per-config hypotheses
config_hypotheses = {}
for label, config in PER_CONFIG.items():
    hyp = evaluate_hypotheses(config['seeds'], label)
    config_hypotheses[label] = hyp
    s = hyp['summary']
    print(f"{label}: {s['n_pass']}/8 pass - Failed: {', '.join(s['failed'])}")

# Compute C1 hypotheses
c1_results = evaluate_track_c_hypotheses(config_hypotheses)

print("\n=== TRACK C1 HYPOTHESES (H32-H35) ===")
for h_name, h_info in c1_results.items():
    status = "PASS" if h_info['pass'] else "FAIL"
    print(f"  {h_name}: {status} - {h_info['description']}")

# Build NSI/CIV summary
print("\n=== SUMMARY TABLE ===")
print(f"  {'Config':<18} | {'N0':>4} | {'Pass':>6} | {'Failed':<10} | {'CIV':>5} | {'Cont':>6} | {'Depth':>6}")
for label, config in PER_CONFIG.items():
    h = config_hypotheses.get(label, {}).get('summary', {})
    civs = [s['civ_count'] for s in config['seeds']]
    conts = [s['nse_continuity_mean'] for s in config['seeds']]
    depths = [s['nse_history_depth_mean'] for s in config['seeds']]
    failed_str = ', '.join(h.get('failed', []))[:10]
    print(f"  {label:<18} | {config['N0']:>4} | {h.get('n_pass',0):>3}/8 | {failed_str:<10} | {np.mean(civs):>5.1f} | {np.mean(conts):>6.4f} | {np.mean(depths):>6.4f}")

# Save results
results_file = os.path.join(PROJECT_ROOT, 'experiments', f'exp_125_c1_results_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
save_data = {
    'experiment': 'exp_125_phase5_c1_n0_shrinking',
    'datetime': datetime.now().isoformat(),
    'configs': [{'label': k, 'N0': v['N0']} for k, v in PER_CONFIG.items()],
    'seeds': [42, 142, 242, 342],
    'per_config': {},
    'track_c_hypotheses': c1_results,
}
for label, config in PER_CONFIG.items():
    save_data['per_config'][label] = {
        'hypotheses': config_hypotheses[label],
        'per_seed': config['seeds'],
    }

with open(results_file, 'w', encoding='utf-8') as f:
    json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
print(f"\nResults saved to: {results_file}")
