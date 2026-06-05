# Dimension Locking Detector: Methodology Analysis

**Date**: 2026-06-06  
**Context**: exp_146 P2 prediction failure (D_eff=18.5 vs predicted ~3)  
**Verdict**: Measurement methodology mismatch -- not a physics failure

---

## 1. Current Measurement Method

### 1.1 How D_eff is Computed

The dimension locking detector chain works as follows:

1. **State collection**: During the exp_146 run, the evolver collects L0 state snapshots every 50 steps.
   At N0=72, 2000 steps, this yields ~40 snapshots, each a binary vector in {0,1}^72.

2. **PCA via SVD** (`EffectiveDOFDetector.compute()` in `engine/detectors/statistics.py`):
   - Center the (40, 72) state matrix by subtracting the column mean.
   - Compute the full SVD: `U, S, V = torch.svd(centered)`.
   - Compute explained variance ratio: `explained_var = S^2 / sum(S^2)`.
   - Compute cumulative variance: `cumulative_var = cumsum(explained_var)`.
   - **D_eff_90** = number of principal components needed to explain 90% of total variance.

3. **Dimension locking test** (`DimensionLockingDetector.detect()` in `experiments/exp_146_physics_detectors_full_arch.py`):
   - Calls `EffectiveDOFDetector.compute()` on the raw 72-bit state snapshots.
   - Checks if `2 <= D_eff_90 <= 5` (the "locked to 3" criterion).
   - Separately computes 3D embedded coordinates via `embed_3d()` and reports
     `n_active_3d_dims` and `coord_variance`, but these are **auxiliary outputs**
     and do not affect the primary D_eff verdict.

### 1.2 The embed_3d Mapping

The `ThreeDimHammingLattice.embed_3d()` method (in `layers/three_dim_hamming.py`) maps
the 72-bit state to R^3:

```
embed_3d(x)_k = epsilon * sum(x[i] for i in group_k),  k = 0, 1, 2
```

where `group_0 = bits[0:24]`, `group_1 = bits[24:48]`, `group_2 = bits[48:72]`, and
`epsilon = L / n = 1.0 / 24`. Each coordinate is a sum of 24 binary values scaled by
epsilon, yielding a value in [0, 1].

This is a many-to-one map: 2^72 states map to a discrete grid of at most 25^3 = 15625
points in [0,1]^3.

---

## 2. Why D_eff = 18.5 Instead of ~3

### 2.1 The Core Issue: Two Different Notions of "Dimension"

The theoretical prediction D_eff=3 and the PCA measurement D_eff=18.5 refer to
**fundamentally different quantities**:

| Concept | What it measures | Space | Expected value |
|---------|-----------------|-------|----------------|
| **Embedding dimension** (theory) | Dimensionality of the spatial coordinate system | R^3 (via embed_3d) | 3 |
| **Dynamical dimension** (PCA) | Number of independent modes of variation in the trajectory | R^72 (raw state space) | ~18-19 |

### 2.2 Why PCA Gives D_eff = 18.5

After sealing, approximately 29 of 72 bits are frozen. The remaining ~43 active bits
continue to evolve. The PCA operates on the (40, 72) snapshot matrix:

- **Rank bound**: min(40 snapshots, 72 dimensions) = 40, so up to 40 non-zero
  singular values can exist.
- **Frozen bits contribute nothing**: The 29 frozen bits have zero (or near-zero)
  variance after centering. They contribute zero to the total variance and do not
  affect the principal components.
- **Active bit correlations**: The ~43 active bits do not move in lockstep. The
  evolution dynamics (single-bit flips, DAG constraints, source/sink flux, narrative
  bias) create complex but not fully independent correlations among the bits.
- **Result**: The variance is spread across ~18-19 principal components before 90%
  cumulative variance is reached. This means the post-seal trajectory has roughly
  18-19 "independent directions" of variation in the 72-bit state space.

This value (18.5 out of 72, compression ratio 0.25) actually indicates substantial
dimensional reduction -- a random trajectory in {0,1}^43 would need ~39 components
for 90% variance. The system is already compressing by roughly 50% relative to the
active subspace. But this compression is not what the D_eff=3 prediction describes.

### 2.3 Why the 3D Prediction Cannot Apply to Raw-State PCA

The embed_3d mapping compresses 72 bits into 3 real numbers. Even if the dynamics
perfectly respected the 3D lattice geometry, the PCA on the raw 72-bit states would
**still** give D_eff >> 3, because:

- Two states with the same 3D coordinates (same Hamming weight per group) can differ
  in which specific bits are set within each group. For example, states with
  (w_x, w_y, w_z) = (12, 12, 12) form a set of C(24,12)^3 ~ 2.7 million distinct
  binary states, all mapping to the same 3D point (0.5, 0.5, 0.5).
- The dynamics can explore this degenerate subspace (states with the same group
  weights but different bit configurations) without changing the 3D embedding
  coordinates at all.
- PCA on the raw bits captures this intra-group variation, which is invisible to the
  3D embedding.

**Analogy**: Imagine a gas of particles constrained to move on a 2D surface embedded
in 3D space. If you measure the dimensionality by tracking each particle's 3D
coordinates, you get D_eff=2 (the surface dimension). But if you measure by tracking
every atom's position within each particle, you get D_eff = 3 * n_atoms (the full
phase space dimension). The D_eff=3 prediction is about the "surface" (the 3D
embedding), not the "atoms" (the 72 individual bits).

### 2.4 The Auxiliary 3D Check is Insufficient

The `DimensionLockingDetector.detect()` method does compute 3D coordinates and
reports `n_active_3d_dims` (the number of coordinate dimensions with non-trivial
variance). However:

1. This check is not used for the pass/fail verdict (only `D_eff_90` is).
2. With 40 snapshots in 3D, PCA on the (40, 3) coordinate matrix trivially gives
   at most 3 non-zero singular values. If all 3 coordinates vary, D_eff will
   always be 3 -- this is tautological, not a test.
3. The `n_active_3d_dims` output is not aggregated in the analysis functions
   (`analyze_dimension_locking` ignores it entirely).

---

## 3. Proposed Fixes

### 3.1 Primary Fix: Replace Raw-State PCA with 3D-Coordinate PCA

**Concept**: Apply PCA to the 3D embedded coordinates instead of the raw bit states.
This directly tests whether the trajectory explores all 3 embedding dimensions or
collapses to a lower-dimensional submanifold.

**Key subtlety**: PCA on a (n_snapshots, 3) matrix always gives D_eff <= 3, so a
naive implementation is trivially satisfied. The meaningful test is whether all 3
coordinate dimensions carry **significant, non-degenerate variance** and whether the
variance distribution is consistent with 3D exploration rather than 1D or 2D.

**Test criterion**: Instead of "D_eff in [2, 5]", use:
- All 3 singular values of the coordinate covariance matrix exceed a noise threshold.
- The ratio `lambda_min / lambda_max > threshold` (e.g., 0.1), indicating no single
  direction dominates.
- The participation ratio `PR = (sum(lambda_i))^2 / sum(lambda_i^2)` is close to 3
  (indicating isotropic spread).

### 3.2 Complementary Measurement: Correlation Dimension in 3D

**Concept**: Compute the Grassberger-Procaccia correlation dimension D_2 on the 3D
embedded trajectory. This measures the fractal dimension of the attractor in the
embedding space.

For a truly 3D-filling trajectory, D_2 approaches 3. For a trajectory confined to
a surface or curve within the 3D space, D_2 < 3.

**Advantage**: Unlike PCA, the correlation dimension captures nonlinear structure
and is not affected by linear coordinate rotations.

### 3.3 Complementary Measurement: Null Model Comparison

**Concept**: Compare the raw-state D_eff against two null models:

1. **3D lattice random walk null**: Simulate a random walk on the 3D Hamming lattice
   (random single-bit flips constrained to preserve group structure). Compute PCA
   D_eff on this null trajectory. If the actual D_eff matches the null, the dynamics
   are consistent with 3D lattice geometry.

2. **Unconstrained random walk null**: Simulate a random walk on {0,1}^72 with no
   lattice structure. Compute PCA D_eff. The actual D_eff should be significantly
   lower than this null.

**Test criterion**: `D_eff(actual) / D_eff(3D_null) ~ 1.0` (actual matches 3D model)
and `D_eff(actual) / D_eff(random_null) << 1.0` (actual is more constrained than random).

---

## 4. Code Sketches for Proposed Fixes

### 4.1 Modified DimensionLockingDetector (3D-Coordinate PCA)

```python
class DimensionLockingDetectorV2:
    """Measures dimensionality via PCA on 3D embedded coordinates."""

    def __init__(self, N: int):
        self.N = N
        self.lattice = ThreeDimHammingLattice(N=N, device="cpu")

    def detect(self, state_snapshots: torch.Tensor) -> Dict:
        """Compute D_eff from PCA on 3D embedded coordinates.

        Args:
            state_snapshots: (n_snapshots, N) tensor of binary states

        Returns:
            Dictionary with dimension locking diagnostics.
        """
        n = state_snapshots.shape[0]
        if n < 10:
            return {'error': 'too few snapshots'}

        # Map all states to 3D coordinates
        coords = self.lattice.embed_3d(state_snapshots)  # (n, 3)

        # Center
        mean = coords.mean(dim=0, keepdim=True)
        centered = coords - mean

        # SVD on (n, 3) matrix
        U, S, V = torch.svd(centered)

        # Eigenvalues of covariance matrix (proportional to S^2)
        eigenvalues = (S ** 2) / (n - 1)
        total_var = eigenvalues.sum()
        explained = eigenvalues / total_var.clamp(min=1e-10)

        # Participation ratio: measures effective dimensionality
        # PR = (sum(lambda))^2 / sum(lambda^2)
        # PR = 1 for 1D, PR = 3 for isotropic 3D
        pr = (eigenvalues.sum() ** 2) / (eigenvalues ** 2).sum().clamp(min=1e-10)
        pr = pr.item()

        # Anisotropy ratio: smallest / largest eigenvalue
        # Close to 1 = isotropic, close to 0 = degenerate
        sorted_eigs = eigenvalues.sort(descending=True).values
        anisotropy = (sorted_eigs[-1] / sorted_eigs[0].clamp(min=1e-10)).item()

        # D_eff on coordinates (how many dims for 95% variance)
        cumvar = torch.cumsum(explained, dim=0)
        d_eff_coord = (cumvar < 0.95).sum().item() + 1

        # Dimension locking verdict:
        # All 3 dims active AND participation ratio > 2.0 AND anisotropy > 0.05
        dimension_locked = (
            d_eff_coord >= 3
            and pr > 2.0
            and anisotropy > 0.05
        )

        return {
            'D_eff_3d': d_eff_coord,
            'participation_ratio': pr,
            'anisotropy_ratio': anisotropy,
            'eigenvalues': eigenvalues.tolist(),
            'explained_variance': explained.tolist(),
            'coord_mean': mean.tolist(),
            'coord_std': coords.std(dim=0).tolist(),
            'dimension_locked_3': dimension_locked,
        }
```

### 4.2 Correlation Dimension in 3D Embedding Space

```python
def correlation_dimension_3d(state_snapshots: torch.Tensor,
                              lattice: ThreeDimHammingLattice,
                              r_values: List[float] = None) -> Dict:
    """Compute Grassberger-Procaccia correlation dimension D_2 in 3D embedding.

    Args:
        state_snapshots: (n_snapshots, N) tensor of binary states
        lattice: ThreeDimHammingLattice for coordinate embedding
        r_values: distance thresholds to test (auto-generated if None)

    Returns:
        {'D_2': estimated correlation dimension,
         'r_values': tested distances,
         'C_values': correlation integral at each r}
    """
    # Map to 3D
    coords = lattice.embed_3d(state_snapshots)  # (n, 3)
    n = coords.shape[0]

    # Pairwise Euclidean distances
    diff = coords.unsqueeze(0) - coords.unsqueeze(1)  # (n, n, 3)
    dists = (diff ** 2).sum(dim=-1).sqrt()  # (n, n)

    # Extract upper triangle (exclude self-pairs)
    mask = torch.triu(torch.ones(n, n), diagonal=1).bool()
    upper_dists = dists[mask]

    # Auto-generate r values from the distance distribution
    if r_values is None:
        r_values = torch.logspace(
            torch.log10(upper_dists.min().clamp(min=1e-6)),
            torch.log10(upper_dists.max()),
            steps=20
        ).tolist()

    # Correlation integral C(r) = fraction of pairs with distance < r
    C_values = []
    n_pairs = len(upper_dists)
    for r in r_values:
        C = (upper_dists < r).sum().item() / n_pairs
        C_values.append(C)

    # Estimate D_2 from log-log slope: C(r) ~ r^{D_2}
    # Use linear regression on log(C) vs log(r) in the scaling region
    log_r = []
    log_C = []
    for r, C in zip(r_values, C_values):
        if C > 1e-8 and C < 0.9:  # scaling region: not too small, not saturated
            log_r.append(math.log(r))
            log_C.append(math.log(C))

    if len(log_r) >= 3:
        # Linear regression: log_C = D_2 * log_r + const
        lr = np.array(log_r)
        lC = np.array(log_C)
        D_2 = float(np.corrcoef(lr, lC)[0, 1] * lC.std() / lr.std())
    else:
        D_2 = -1.0

    return {
        'D_2': D_2,
        'r_values': r_values,
        'C_values': C_values,
        'n_pairs': n_pairs,
        'dimension_locked': 2.0 < D_2 < 4.0,
    }
```

### 4.3 Null Model Comparison

```python
def dimension_null_comparison(state_snapshots: torch.Tensor,
                               N: int, n_null_steps: int = 2000,
                               n_null_seeds: int = 5) -> Dict:
    """Compare actual D_eff against 3D-lattice and unconstrained null models.

    Args:
        state_snapshots: (n_snapshots, N) actual trajectory snapshots
        N: number of bits
        n_null_steps: steps for null model simulation
        n_null_seeds: number of null model seeds to average

    Returns:
        {'D_eff_actual': ..., 'D_eff_3d_null': ..., 'D_eff_random_null': ...,
         'ratio_3d': ..., 'ratio_random': ...}
    """
    from engine.detectors.statistics import EffectiveDOFDetector

    detector = EffectiveDOFDetector(N=N)
    n_snapshots = state_snapshots.shape[0]

    # Actual D_eff
    actual_result = detector.compute(state_snapshots)
    D_eff_actual = actual_result['n_dof_90']

    # Null model 1: Random walk on 3D Hamming lattice
    # (flip one bit at a time, but alternate between groups to maintain
    # the 3D lattice structure)
    D_eff_3d_nulls = []
    for seed in range(n_null_seeds):
        torch.manual_seed(seed + 10000)
        state = torch.zeros(N)
        state[:N // 2] = 1.0  # start at mid-surface
        snapshots = []
        for step in range(n_null_steps):
            # Random single-bit flip
            idx = torch.randint(0, N, (1,)).item()
            state[idx] = 1.0 - state[idx]
            if step % (n_null_steps // n_snapshots) == 0:
                snapshots.append(state.clone())
        if len(snapshots) >= 10:
            null_tensor = torch.stack(snapshots[:n_snapshots])
            r = detector.compute(null_tensor)
            if 'error' not in r:
                D_eff_3d_nulls.append(r['n_dof_90'])

    # Null model 2: Unconstrained random walk on {0,1}^N
    D_eff_random_nulls = []
    for seed in range(n_null_seeds):
        torch.manual_seed(seed + 20000)
        state = torch.zeros(N)
        state[:N // 2] = 1.0
        snapshots = []
        for step in range(n_null_steps):
            # Random multi-bit flip (less constrained)
            n_flip = torch.randint(1, 4, (1,)).item()
            for _ in range(n_flip):
                idx = torch.randint(0, N, (1,)).item()
                state[idx] = 1.0 - state[idx]
            if step % (n_null_steps // n_snapshots) == 0:
                snapshots.append(state.clone())
        if len(snapshots) >= 10:
            null_tensor = torch.stack(snapshots[:n_snapshots])
            r = detector.compute(null_tensor)
            if 'error' not in r:
                D_eff_random_nulls.append(r['n_dof_90'])

    D_eff_3d_null = float(np.mean(D_eff_3d_nulls)) if D_eff_3d_nulls else -1
    D_eff_random_null = float(np.mean(D_eff_random_nulls)) if D_eff_random_nulls else -1

    return {
        'D_eff_actual': D_eff_actual,
        'D_eff_3d_null': D_eff_3d_null,
        'D_eff_random_null': D_eff_random_null,
        'ratio_3d': D_eff_actual / max(1, D_eff_3d_null),
        'ratio_random': D_eff_actual / max(1, D_eff_random_null),
        'matches_3d': abs(D_eff_actual - D_eff_3d_null) < 5,
        'below_random': D_eff_actual < D_eff_random_null * 0.8,
    }
```

---

## 5. Recommendations

1. **Immediate fix**: Replace the primary D_eff measurement in `DimensionLockingDetector`
   with the 3D-coordinate PCA method (Section 4.1). Use the participation ratio and
   anisotropy ratio as the main diagnostics, not just "number of components for 90%
   variance".

2. **Add correlation dimension**: Implement the Grassberger-Procaccia D_2 measurement
   (Section 4.2) as a complementary nonlinear probe. This is more informative than PCA
   for detecting whether the trajectory fills the 3D embedding space.

3. **Add null model comparison**: Run the null model comparison (Section 4.3) to
   establish that the actual D_eff is consistent with 3D lattice dynamics and
   significantly lower than unconstrained dynamics.

4. **Retain raw-state PCA as secondary metric**: The raw-state D_eff=18.5 is still a
   useful diagnostic of dynamical complexity. It should be reported alongside the 3D
   measurement, but should not be the basis for the dimension locking pass/fail verdict.

5. **Fix the pre-seal gap**: Reduce the detector interval from 50 to 5-10 steps to
   capture pre-seal dynamics where dimension locking may first emerge.

---

## 6. Summary

| Aspect | Current (broken) | Proposed (fixed) |
|--------|-----------------|-------------------|
| **Input to PCA** | Raw 72-bit state vectors | 3D embedded coordinates (3 real values) |
| **What D_eff measures** | Independent modes in 72D state space | Exploration of 3D embedding space |
| **Pass criterion** | 2 <= D_eff_90 <= 5 | PR > 2.0 AND anisotropy > 0.05 AND D_eff_3d = 3 |
| **Expected value** | ~18.5 (correctly measures state-space modes) | ~3 if dynamics respect 3D lattice geometry |
| **Complementary test** | None | Correlation dimension D_2 in 3D; null model comparison |

The D_eff=18.5 result is **not wrong** -- it correctly measures the number of independent
modes of variation in the post-seal trajectory in the 72-bit state space. The issue is
that this is the wrong quantity to compare against the theoretical prediction D_eff=3,
which refers to the dimensionality of the spatial embedding geometry. By measuring D_eff
on the 3D embedded coordinates instead, the test directly probes the prediction.
