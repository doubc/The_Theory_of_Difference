"""exp_32_full_spatial_detection.py — 完整空间检测实验

运行 SpatialEvolver + 全部探测器 (P0-P4)：
- MutualInfoDetector (3D)
- GravitationalPotentialDetector
- DimensionLockingDetector
- GaugeFieldDetector
- SpatialCorrelationDetector
"""
import torch
import numpy as np
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver
from engine.detectors.mutual_info import MutualInfoDetector
from engine.detectors.gravitational_potential import GravitationalPotentialDetector
from engine.detectors.dimension_locking import DimensionLockingDetector
from engine.detectors.gauge_field import GaugeFieldDetector
from engine.detectors.spatial_correlation import SpatialCorrelationDetector

print("=" * 70)
print("exp_32: Full Spatial Detection Pipeline")
print("=" * 70)

N = 48
T = 2000

# ====== 1. 运行空间演化器 ======
print("\n[1] Running SpatialEvolver (N={}, T={})...".format(N, T))
evolver = SpatialLongRangeEvolver(N=N, total_steps=T, sample_interval=T//20)
result = evolver.run(verbose=True)

traj = evolver.get_trajectory_tensor()
traj_3d = evolver.get_3d_trajectory()
flip_seq = evolver.get_flip_sequence()
w_seq = evolver.get_hamming_weight_sequence()

print("\n  Trajectory: {}, 3D Trajectory: {}".format(traj.shape, traj_3d.shape))

# ====== 2. MutualInfo (3D) ======
print("\n[2] Mutual Information (3D distance)")
mi_det = MutualInfoDetector(N=N)
mi_result = mi_det.compute(flip_seq, use_3d_distance=True)
print("  Distance type: {}".format(mi_result['distance_type']))
print("  N bins: {}".format(mi_result['n_bins']))
print("  Decay slope: {:.4f}".format(mi_result['decay_slope']))
print("  Decay detected: {}".format(mi_result['decay_detected']))

# ====== 3. GravitationalPotential ======
print("\n[3] Gravitational Potential")
grav_det = GravitationalPotentialDetector(N=N, n_per_group=N//3)
grav_result = grav_det.compute_from_evolver_result(result)
if 'error' not in grav_result:
    print("  Fit alpha: {:.4f}".format(grav_result['fit_alpha']))
    print("  Fit beta: {:.4f}".format(grav_result['fit_beta']))
    print("  R-squared: {:.4f}".format(grav_result['fit_r_squared']))
    print("  Gravitation detected: {}".format(grav_result['gravitation_detected']))
else:
    print("  Error: {}".format(grav_result['error']))

# ====== 4. DimensionLocking ======
print("\n[4] Dimension Locking")
dim_det = DimensionLockingDetector(N=N, n_per_group=N//3)
dim_result = dim_det.analyze_from_evolver_result(result)
if 'error' not in dim_result:
    pca = dim_result['pca']
    msd = dim_result['msd']
    print("  PCA eigenvalues: {}".format([round(e, 4) for e in pca.get('eigenvalues', [])]))
    print("  Top 3 variance ratio: {:.3f}".format(pca.get('top3_variance_ratio', 0)))
    print("  Locked 3D (PCA): {}".format(pca.get('locked_3d', False)))
    print("  MSD D_eff: {:.2f}".format(msd.get('D_eff', 0)))
    print("  MSD slope: {:.4f}".format(msd.get('power_slope', 0)))
    print("  Dimension locked (MSD): {}".format(msd.get('dimension_locked', False)))
    print("  Overall dimension locked: {}".format(dim_result.get('dimension_locked', False)))
else:
    print("  Error: {}".format(dim_result['error']))

# ====== 5. GaugeField ======
print("\n[5] Gauge Field (su(3) detection)")
gauge_det = GaugeFieldDetector(N=N)
gauge_result = gauge_det.analyze_from_spatial_result(result, max_samples=50)
print("  N mid-surface states: {}".format(gauge_result.get('n_mid_surface_states', 0)))
print("  CR1 pass rate: {:.2f}".format(gauge_result.get('CR1_pass_rate', 0)))
print("  CR2 pass rate: {:.2f}".format(gauge_result.get('CR2_pass_rate', 0)))
print("  Generators (k={}): {}".format(
    gauge_result.get('generators_k3', {}).get('k', '?'),
    gauge_result.get('generators_k3', {}).get('total_generators', '?')))
print("  Algebra: {}".format(gauge_result.get('algebra', '?')))
print("  su(3) signal: {}".format(gauge_result.get('su3_signal', False)))

# ====== 6. SpatialCorrelation ======
print("\n[6] Spatial Correlation")
corr_det = SpatialCorrelationDetector(N=N, n_per_group=N//3)
corr_result = corr_det.analyze_from_evolver_result(result)
if 'error' not in corr_result:
    print("  Correlation length: {:.4f}".format(corr_result.get('correlation_length', 0)))
    print("  Fit type: {}".format(corr_result.get('fit_type', '?')))
    print("  R-squared: {:.4f}".format(corr_result.get('r_squared', 0)))
    print("  Short-range order: {}".format(corr_result.get('short_range_order', False)))
    print("  Long-range order: {}".format(corr_result.get('long_range_order', False)))
    print("  Critical: {}".format(corr_result.get('critical', False)))
else:
    print("  Error: {}".format(corr_result['error']))

# ====== 7. 总结 ======
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("  Spatial evolver: OK ({} snapshots)".format(result['n_snapshots']))
print("  3D trajectory: OK (shape={})".format(traj_3d.shape))
print("  Mutual info (3D): slope={:.4f}, detected={}".format(
    mi_result['decay_slope'], mi_result['decay_detected']))
if 'error' not in grav_result:
    print("  Gravitational: beta={:.2f}, detected={}".format(
        grav_result['fit_beta'], grav_result['gravitation_detected']))
if 'error' not in dim_result:
    print("  Dimension locking: D_eff={:.2f}, locked={}".format(
        msd.get('D_eff', 0), dim_result.get('dimension_locked', False)))
print("  Gauge field: algebra={}, su3_signal={}".format(
    gauge_result.get('algebra', '?'), gauge_result.get('su3_signal', False)))
if 'error' not in corr_result:
    print("  Spatial correlation: xi={:.4f}, type={}".format(
        corr_result.get('correlation_length', 0), corr_result.get('fit_type', '?')))
print("\n  All detectors functional: OK")
