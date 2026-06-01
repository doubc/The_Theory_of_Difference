"""Quick single-seed smoke test for exp_101"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.exp_101_combined_fix import run_single_seed, EXP95_CSC_CONFIG

result = run_single_seed(
    N0=72, steps=1600, seed=42, sample_interval=10,
    gbc_soft_nudge=0.2, use_csc=True, csc_config=EXP95_CSC_CONFIG,
    use_nse=True, use_amc=True, use_ilp=True,
)
print(f"seed=42: NSI_max={result['nse_nsi_max']:.4f}, "
      f"continuity={result['nse_continuity_mean']:.4f}, "
      f"history_depth={result['nse_history_depth_max']:.4f}, "
      f"tp_max={result['nse_turning_points_max']}, "
      f"civ={result['civ_count']}, "
      f"downgrades={result['civ_limiter_total_downgrades']}")
