"""Quick single-seed test for exp_97 multi-signal validation."""
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from experiments.exp_97_multisignal_h4_validation import run_single_seed, evaluate_hypotheses, EXP95_CSC_CONFIG

result = run_single_seed(
    N0=72, steps=1600, seed=42, sample_interval=10,
    gbc_soft_nudge=0.2, use_csc=True,
    csc_config=EXP95_CSC_CONFIG,
    use_nse=True,
)

print("=== Single Seed Test (seed=42) ===")
print("NSI max:       {:.4f}".format(result['nse_nsi_max']))
print("NSI mean:      {:.4f}".format(result['nse_nsi_mean']))
print("NSI active:    {:.4f}".format(result['nse_nsi_active_rate']))
print("Continuity:    {:.4f}".format(result['nse_continuity_mean']))
print("Stability:     {:.4f}".format(result['nse_stability_mean']))
print("Hist depth max:{:.4f}".format(result['nse_history_depth_max']))
print("Hist depth avg:{:.4f}".format(result['nse_history_depth_mean']))
print("Turn pts max:  {}".format(result['nse_turning_points_max']))
print("Turn pts final:{}".format(result['nse_turning_points_final']))
print("CIV count:     {}".format(result['civ_count']))
print("GBC coh mean:  {:.4f}".format(result['gbc_coherence_mean']))
print("CSC CSCI mean: {:.4f}".format(result['csc_csci_mean']))
print("Elapsed:       {:.1f}s".format(result['elapsed']))
