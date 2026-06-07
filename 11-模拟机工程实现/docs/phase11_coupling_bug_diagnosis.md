# Phase 11 Coupling Bug Diagnosis

**Written**: 2026-06-08 00:16 CST  
**Author**: Heartbeat diagnostic pass  
**Status**: ✅ Confirmed — bug exists, fix designed but not integrated  

---

## Bug: Cross-Subspace Coupling is Functionally Dead

### What the Code Actually Does

In `subspace_evolver.py`, the `CouplingEngine.make_callback()` creates a step callback that:

1. Reads **source subspace's final direction mean** (`src_mean ∈ [0, 1]`)
2. Computes: `injection = conn.strength × (src_mean - 0.5) × 2.0 × coupling_scale`
3. Applies to **target's `constraints.binding_strength`**:
   ```python
   bs.add_(injection)    # uniform addition to ALL N×N elements
   bs.fill_diagonal_(0)  # zeros diagonal
   ```

### Why It Produces No Meaningful Effect

#### Root Cause 1: Uniform Addition = No Differential Signal

Adding the same scalar to **every element** of the binding_strength matrix has **zero effect** on relative ordering. In `get_A1_prime_candidates()`, the selection logic is:

```python
bindings = torch.tensor([p[2] for p in pairs])  # raw binding_strength[i][j]
bindings = bindings / bindings.sum()            # → probability distribution
indices = torch.multinomial(bindings, n_pairs)  # weighted sample
```

Adding a constant `c` to all elements:
- `prob[i] = (v[i] + c) / (sum(v) + c × N_pairs)`  
- If `c > 0`, probabilities **flatten** toward uniform → **less differentiation**

The coupling thus **reduces signal**, not creates it.

#### Root Cause 2: Wrong Target Mechanism

`binding_strength` is **only read** by `get_A1_prime_candidates()` (lateral pair selection).  
It is **never read** by:

| Dynamic | Where decided | Reads binding_strength? |
|---------|--------------|------------------------|
| Source injection | `get_A8_source_strength` | ❌ No |
| Flip selection | `get_allowed_flips`, `get_A8_weights` | ❌ No |
| Sink absorption | `get_A8_sink_strength`, `get_allowed_absorbs` | ❌ No |
| Sealing | `check_A7` → scoring by `active_bits` | ❌ No (binding_strength used for clustering only) |

**No causal pathway from coupling → sealing behavior.** All Phase 11 coupling experiments that measured sealing rates were measuring noise.

#### Root Cause 3: Chicken-Egg Bootstrapping Deadlock

```python
injection = strength × (src_mean - 0.5) × 2.0 × coupling_scale
```

Before L1 forms, the source subspace is in a random state → `src_mean ≈ 0.5` → `injection ≈ 0`.  
Coupling only becomes non-zero **after** the source has already sealed — but coupling is supposed to **help** the target seal. The mechanism requires what it's supposed to produce.

#### Root Cause 4: Wrong Subspace Size in Exp_151

Exp_151 used N1=20 for subspace S1, but `min_active_bits = max(N//3, 12) = 12`.  
S1's random HW (7–12) was often **below** the sealing threshold, so S1 could never seal regardless of coupling. The entire experiment design was invalid.

---

## Why the Fix Was Never Integrated (Root Cause Analysis)

Exp_152 (Phase 11 P4) contains a **correct fix** implemented as a **monkey-patch**:

| Engine File | Has the fix? | Status |
|------------|-------------|--------|
| `acl/axioms_v2.py` | ❌ No `coupling_bias` field | Missing |
| `engine/subspace_evolver.py` | ❌ Still uses `bs.add_()` | Broken |
| `experiments/exp_152_*.py` | ✅ Monkey-patched | Fragile |

The fix approach (from exp_152):
1. Add `coupling_bias: torch.Tensor(N)` to `AxiomConstraints`
2. Modify `get_allowed_flips()` → filter bits with `coupling_bias < -0.5`
3. Modify `get_A8_weights()` → boost weight by `(1.0 + bias)`, reduce by `(1.0 - 0.5×|bias|)`
4. CouplingEngine writes into `coupling_bias` instead of `binding_strength`

But as a **monkey-patch**, it only works when explicitly called in experiment scripts.  
The actual engine code (`subspace_evolver.py`) was **never updated**.

**Why wasn't it integrated?** Probable causes:
- Phase 11 ended (all 4 sub-phases complete)
- Phase 12 moved to temporal clustering (single-subspace → no coupling needed)
- Phase 13 moved to post-sealing dynamics (also single-subspace)
- The fix was deferred and never prioritized

---

## Potential Side Effect: Does Binding_Strength Uniform Addition Affect Anything?

**Yes**: In `A7 scoring` (line 560 of `axioms_v2.py`):
```python
bind_score = sum(self.binding_strength[i][j].item() for j in active_now if j != i)
```
Higher bind_score → less likely to be frozen during sealing. Uniform addition raises ALL scores equally, so ranking is preserved.

**But**: The absolute threshold in `get_clusters()`:
```python
threshold = 0.5
if self.binding_strength[i][j].item() > threshold:
```
Uniform addition could push pairs above this threshold, creating **spurious clusters**. This artifact may have contaminated Phase 11 clustering analysis.

---

## Fix Plan (for Phase 14)

### Step 1: Add `coupling_bias` to `AxiomConstraints.__init__`

```python
self.coupling_bias: torch.Tensor = torch.zeros(N, device=device)
```

### Step 2: Modify `get_allowed_flips(state)`

After computing allowed flips, filter out bits where `coupling_bias[i] < -0.5`  
(Meaning: "source says avoid energizing this bit because its source is saturated").

### Step 3: Modify `get_A8_weights(state)`

```python
for i in range(N):
    b = self.coupling_bias[i].item()
    if b > 0:
        w[i] *= (1.0 + b)        # boost injection where source is active
    elif b < 0:
        w[i] *= (1.0 - abs(b) * 0.5)  # suppress where source is saturated
```

### Step 4: Rewrite `CouplingEngine.make_callback()`

Replace the uniform `binding_strength` injection with per-bit coupling_bias:

```python
# Source → target coupling_bias
# Map source bits to target bits via modulo
for src_i in range(N_src):
    if source_state[src_i] > 0.5:        # active source bit
        tgt_i = src_i % N_tgt
        target_bias[tgt_i] += src_mean_dir * conn.strength

# Normalize to [-1, +1]
target_bias = target_bias.clamp(-1.0, 1.0)
constraints.coupling_bias.copy_(target_bias)
```

### Step 5: Remove Dead Code

Delete these lines from `CouplingEngine._coupling_callback`:
```python
bs = constraints.binding_strength
bs.add_(injection)
bs.fill_diagonal_(0)
```

### Step 6: Update `expand_to()` in AxiomConstraints

Ensure `coupling_bias` is preserved/reset when N expands.

---

## Impact Assessment

| Component | Affected? | Why |
|-----------|-----------|-----|
| Exp_150 (coupling sweep) | ✅ **Spurious** | Dead coupling → all results are baseline noise |
| Exp_151 (asymmetric N) | ✅ **Spurious** | Dead coupling + wrong N → invalid design |
| Exp_152 (proposed fix) | ✅ **Monkey-patch only** | Fix works but not in engine |
| Phase 12 (temporal clustering) | ❌ Not affected | Single-subspace, no coupling involved |
| Phase 13 (post-sealing dynamics) | ❌ Not affected | Single-subspace, no coupling involved |
| `get_A1_prime_candidates` | ⚠️ Minor | Uniform addition flattens distribution |
| `get_clusters` (threshold) | ⚠️ Minor | Uniform addition may create spurious clusters |

---

## Recommendation

**Phase 14 must start by fixing this bug.**  
Without a working coupling mechanism, any multi-subspace experiment will produce meaningless results.

The fix is well-understood (from exp_152's design), localized to 3 files, and has no regression risk for single-subspace experiments (coupling_bias defaults to all zeros → no effect).
