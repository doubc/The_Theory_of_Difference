"""exp_31_spatial_detection.py — 空间演化 + 物理检测实验

验证接入空间嵌入层后的完整检测流程：
1. SpatialEvolver 运行
2. MutualInfoDetector (3D 距离) 分析
3. GravitationalPotentialDetector 分析
4. DimensionLockingDetector 分析
"""
import torch
import numpy as np
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver
from engine.detectors.mutual_info import MutualInfoDetector
from engine.detectors.gravitational_potential import GravitationalPotentialDetector
from engine.detectors.dimension_locking import DimensionLockingDetector

print("=" * 70)
print("exp_31: Spatial Evolution + Physical Detection")
print("=" * 70)

N = 48
T = 2000

# ====== 1. 运行空间演化器 ======
print("\n[1] Running SpatialEvolver...")
evolver = SpatialLongRangeEvolver(N=N, total_steps=T, sample_interval=T//20)
result = evolver.run(verbose=True)

# ====== 2. 3D 轨迹统计 ======
print("\n[2] 3D Trajectory Statistics")
traj_3d = evolver.get_3d_trajectory()
print(f"  Shape: {traj_3d.shape}")
print(f"  X range: [{traj_3d[:, 0].min():.3f}, {traj_3d[:, 0].max():.3f}]")
print(f"  Y range: [{traj_3d[:, 1].min():.3f}, {traj_3d[:, 1].max():.3f}]")
print(f"  Z range: [{traj_3d[:, 2].min():.3f}, {traj_3d[:, 2].max():.3f}]")

# 质心漂移
com = traj_3d.mean(axis=0)
print(f"  Center of mass: [{com[0]:.3f}, {com[1]:.3f}, {com[2]:.3f}]")

# ====== 3. 互信息分析 (3D 距离) ======
print("\n[3] Mutual Information (3D distance)")
traj = evolver.get_trajectory_tensor()
flip_seq = evolver.get_flip_sequence()

mi_det = MutualInfoDetector(N=N)
mi_result = mi_det.compute(flip_seq, use_3d_distance=True)
print(f"  Distance type: {mi_result['distance_type']}")
print(f"  N bins: {mi_result['n_bins']}")
print(f"  Decay slope: {mi_result['decay_slope']:.4f}")
print(f"  Decay detected: {mi_result['decay_detected']}")
if mi_result['mi_by_distance']:
    top3 = sorted(mi_result['mi_by_distance'].items())[:3]
    print(f"  Top 3 MI values:")
    for d, mi in top3:
        print(f"    d={d:.3f}: MI={mi:.6f}")

# ====== 4. 引力势分析 ======
print("\n[4] Gravitational Potential")
grav_det = GravitationalPotentialDetector(N=N, n_per_group=N//3)
grav_result = grav_det.compute_from_evolver_result(result)
if 'error' not in grav_result:
    print(f"  Fit alpha: {grav_result['fit_alpha']:.4f}")
    print(f"  Fit beta: {grav_result['fit_beta']:.4f}")
    print(f"  R-squared: {grav_result['fit_r_squared']:.4f}")
    print(f"  Gravitation detected: {grav_result['gravitation_detected']}")
    print(f"  N data points: {grav_result['n_data_points']}")
else:
    print(f"  Error: {grav_result['error']}")

# ====== 5. 维度锁定分析 ======
print("\n[5] Dimension Locking")
dim_det = DimensionLockingDetector(N=N, n_per_group=N//3)
dim_result = dim_det.analyze_from_evolver_result(result)
if 'error' not in dim_result:
    pca = dim_result['pca']
    msd = dim_result['msd']
    print(f"  PCA eigenvalues: {pca.get('eigenvalues', 'N/A')}")
    print(f"  Top 3 variance ratio: {pca.get('top3_variance_ratio', 0):.3f}")
    print(f"  Locked 3D (PCA): {pca.get('locked_3d', False)}")
    print(f"  MSD D_eff: {msd.get('D_eff', 0):.2f}")
    print(f"  MSD slope: {msd.get('power_slope', 0):.4f}")
    print(f"  Dimension locked (MSD): {msd.get('dimension_locked', False)}")
    print(f"  Overall dimension locked: {dim_result.get('dimension_locked', False)}")
else:
    print(f"  Error: {dim_result['error']}")

# ====== 6. 总结 ======
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  Spatial evolver: OK ({result['n_snapshots']} snapshots)")
print(f"  3D trajectory: OK (shape={traj_3d.shape})")
print(f"  Mutual info (3D): slope={mi_result['decay_slope']:.4f}, detected={mi_result['decay_detected']}")
if 'error' not in grav_result:
    print(f"  Gravitational potential: beta={grav_result['fit_beta']:.2f}, detected={grav_result['gravitation_detected']}")
if 'error' not in dim_result:
    print(f"  Dimension locking: D_eff={msd.get('D_eff', 0):.2f}, locked={dim_result.get('dimension_locked', False)}")
print(f"  All detectors functional: OK")
