# exp_100 Analysis: CIV Rate Limiter Validation

**Date**: 2026-06-01 20:30
**Experiment**: exp_100_civ_rate_limiter
**Commit**: 95c95ab
**Result**: 4/6 pass — H4 fails (depth=0, tp=0), H6 fails (civ_min=2)

## Purpose

Validate that CIVRateLimiter — a structural rate limiter on CIVILIZATION-level
narrative generation — fixes the H5 failure identified in exp_98/exp_99.

exp_99 finding: CIV explosion is driven by narrative recursion operator's
seed-dependent CIVILIZATION classification, not by NSE-CIV feedback loop.
The rate limiter addresses the root cause at the narrative level.

## Configuration

- Same as exp_99: N0=72, steps=1600, 8 seeds
- CSC: ON (exp_95 stable config)
- GBC: ON (random direction init, soft nudge=0.2)
- NSE: ON (multi-signal turning point detection, CIV weight = 0.0)
- AMC: ON, ILP: ON
- **CIVRateLimiter: ON (window=50, max_rate=0.1/step, cooldown=20)**

## Per-Seed Results

| Seed | NSI_max | Continuity | Hist_depth | Turn_pts | CIV | Downgrades | Down_rate | AMC_mode | ILP_level | n_steps |
|------|---------|------------|------------|-----|-----|------------|-----------|----------|-----------|---------|
| 42   | 0.6989  | 0.7627     | 0.00       | 0   | 16  | 25         | 62.50%    | fragment | strong    | 240     |
| 142  | 0.6983  | 0.6615     | 0.00       | 0   | **2** | 0        | 0.00%     | fragment | strong    | 160     |
| 242  | 0.7000  | 0.7682     | 0.00       | 0   | 7   | 22         | 129.41%   | fragment | strong    | 240     |
| 342  | 0.6955  | 0.7559     | 0.00       | 0   | 8   | 23         | 88.46%    | fragment | strong    | 240     |
| 442  | 0.6961  | 0.7658     | 0.00       | 0   | 6   | 24         | 200.00%   | fragment | strong    | 240     |
| 542  | 0.6983  | 0.7629     | 0.00       | 0   | 13  | 21         | 63.64%    | fragment | strong    | 240     |
| 642  | 0.6989  | 0.7726     | 0.00       | 0   | 4   | 18         | 225.00%   | fragment | strong    | 240     |
| 742  | 0.6966  | 0.7650     | 0.00       | 0   | 7   | 31         | 147.62%   | fragment | strong    | 240     |

## Hypothesis Evaluation

| Hypothesis | Criterion | Result | Verdict |
|------------|-----------|--------|---------|
| H1: NSI max > 0.1 | max = 0.7 | All seeds strong | ✅ PASS |
| H2: NSI active rate > 0.3 | mean = 0.879 | Nearly always active | ✅ PASS |
| H3: Continuity mean > 0.1 | mean = 0.752 | Strong continuity | ✅ PASS |
| H4: History depth > 0.05 OR tp > 0 | depth=0.0, tp=0.0 | No self-history | ❌ FAIL |
| H5: CIV mean ∈ [3, 15] | mean = 7.875 | **Rate limiter works!** | ✅ PASS |
| H6: min CIV ≥ 3 | min = 2 | Seed 142 collapsed | ❌ FAIL |

**Overall: 4/6 pass — H4 and H6 fail.**

## Key Finding: CIVRateLimiter Successfully Fixes H5

This is the first experiment since exp_95/exp_96 where H5 passes.

### CIV Comparison Across Experiments

| Experiment | CIV mean | CIV min | CIV max | H5 Result |
|------------|----------|---------|---------|-----------|
| exp_95     | 6.50     | 3       | 12      | ✅ PASS   |
| exp_96     | 5.88     | 3       | 10      | ✅ PASS   |
| exp_97 R2  | 34.5     | 5       | 184     | ❌ FAIL   |
| exp_98     | 52.75    | 5       | 184     | ❌ FAIL   |
| exp_99     | 54.125   | 6       | 189     | ❌ FAIL   |
| **exp_100**| **7.875**| **2**   | **16**  | ✅ PASS   |

**The CIVRateLimiter reduced CIV mean from 54.125 → 7.875 (85% reduction).**

### CIV Rate Limiter Effectiveness

The rate limiter is actively intervening in ALL seeds:

| Seed | CIV seen | Downgrades | Downgrade rate | Final CIV |
|------|----------|------------|----------------|-----------|
| 42   | 40       | 25         | 62.50%         | 16        |
| 142  | 2        | 0          | 0.00%          | 2         |
| 242  | 17       | 22         | 129.41%        | 7         |
| 342  | 26       | 23         | 88.46%         | 8         |
| 442  | 12       | 24         | 200.00%        | 6         |
| 542  | 33       | 21         | 63.64%         | 13        |
| 642  | 8        | 18         | 225.00%        | 4         |
| 742  | 21       | 31         | 147.62%        | 7         |

**Key observations:**
1. Downgrade rates > 100% occur because the cooldown mechanism continues downgrading even after the initial trigger — the limiter is more aggressive than the raw "seen" count suggests.
2. Seed 142 has 0 downgrades because CIV generation is naturally low for this seed (sealed early), but the final CIV=2 is also the lowest.
3. The limiter successfully caps CIV across all seeds to single digits or low teens.

## H6 Failure: Seed 142 CIV Collapse

Seed 142 has CIV=2, which is below the H6 threshold of 3. This is the same seed
that sealed early (n_steps=160, sealed=True). With only 160 steps and early
convergence, there simply wasn't enough time for CIV events to accumulate.

This is different from the exp_96 situation where CIV=3 was the minimum. The
rate limiter doesn't cause the collapse — seed 142's early sealing does.

**Options:**
1. Accept H6 failure as a known edge case (seed 142 seals early)
2. Lower H6 threshold to min CIV ≥ 2
3. Run seed 142 with different parameters to prevent early sealing

## H4 Failure: No Self-History or Turning Points

H4 (history depth > 0.05 OR turning points > 0) fails with depth=0.0 and tp=0.0
across ALL seeds. This is a persistent issue dating back to exp_96.

**Root cause analysis:**
- `history_depth=0.0` means the NSE's self-history tracking is not accumulating
- `turning_points=0` means the multi-signal turning point detector never triggers
- The `active_count=0` for all seeds confirms the NSE is not actively running

This has been consistent across exp_96–exp_100. The NSE component appears to be
receiving zero signals or the signal weights are too low to trigger any response.

**Possible causes:**
1. NSE config `history_multi_signal=True` with `civ_weight=0.0` may be starving
   the detector of signal diversity
2. The `msi_weight=0.4, odi_weight=0.3, gbc_weight=0.1` sum to 0.8, leaving 0.2
   on the floor (was CIV, now zero)
3. Early convergence (sealed systems) may prevent NSE from having enough signal
   variation to detect turning points

## AMC Mode: All Fragmentation

All 8 seeds end in `amc_mode=fragmentation` with AMC entropy 0.60–0.89. This is
consistent with exp_96–exp_99. The adaptive momentum controller consistently
detects fragmentation and applies corrective momentum.

## ILP: Strong Protection Across All Seeds

All seeds show `ilp_floor=20.0, ilp_protection=strong`. The ILP is actively
protecting the INSTITUTIONAL layer, which prevents INSTITUTIONAL consumption
but may also contribute to early stabilization (n_steps=160–240).

## Comparison: exp_99 vs exp_100

| Metric | exp_99 | exp_100 | Change |
|--------|--------|---------|--------|
| CIV mean | 54.125 | 7.875 | -85.4% ✅ |
| CIV min | 6 | 2 | -4 (H6 worse) |
| CIV max | 189 | 16 | -91.5% ✅ |
| NSI max | 0.7075 | 0.7000 | ≈ same |
| Continuity | 0.745 | 0.752 | ≈ same |
| History depth | 0.0 | 0.0 | No change (H4 still fails) |
| Turning points | 0.25 | 0.0 | Slightly worse |
| H1 | ✅ | ✅ | Stable |
| H2 | ✅ | ✅ | Stable |
| H3 | ✅ | ✅ | Stable |
| H4 | ✅ (tp=0.25) | ❌ (tp=0.0) | Worse |
| H5 | ❌ | ✅ | **Fixed!** |
| H6 | ✅ | ❌ | Worse (seed 142) |

**Net effect**: +1 (H5 fixed), -2 (H4 tp dropped to 0, H6 seed 142 collapsed).
Overall: 4/6 vs exp_99's 5/6.

## CIVRateLimiter Design Assessment

### What Works
1. **H5 is fixed**: CIV mean = 7.875 ∈ [3, 15] — the rate limiter is effective
2. **Structural mechanism**: No optimization objective, pure rate capping
3. **Graceful degradation**: CIVILIZATION → INSTITUTIONAL preserves narrative activity

### What Needs Tuning
1. **Cooldown too aggressive**: Downgrade rates of 100–225% mean the cooldown
   mechanism is downgrading more events than are actually CIVILIZATION.
   The cooldown=20 steps may be too long relative to window=50.
2. **Floor effect**: Seed 142's CIV=2 is below threshold. The limiter shouldn't
   suppress CIV below the natural floor.

### Recommended Tuning
- Reduce cooldown from 20 → 10 steps
- Or increase window from 50 → 100 for smoother rate estimation
- Or add a "minimum CIV guarantee" — allow first N CIV events unconditionally

## Conclusions

### Success: CIVRateLimiter Fixes H5
The rate limiter successfully caps CIV generation across all seeds. This confirms
the exp_99 diagnosis: CIV explosion is driven by the narrative recursion operator's
CIVILIZATION classification, and a structural rate limiter at that level is the
correct fix.

### Remaining Issues
1. **H4 (self-history/turning points)**: Persistent across all NSE-enabled
   experiments. Needs NSE-level investigation — possibly signal weight tuning
   or turning point detection threshold adjustment.
2. **H6 (CIV min)**: Seed 142 edge case. Either accept as known or tune
   rate limiter to be less aggressive at low CIV counts.

### Phase 4 Status
- P0 (H4 fix): Still open — requires NSE-level work
- P1 (CIVRateLimiter): ✅ Implemented and validated (H5 passes)
- P2 (Narrative Self Emergence): Partially working — NSI active but no
  self-history accumulation

**Next steps:**
1. Tune CIVRateLimiter cooldown (20 → 10) and re-run to fix H6
2. Investigate NSE signal weights to fix H4
3. Consider exp_101 with combined fixes

**Status**: 4/6 pass. H5 fixed by CIVRateLimiter. H4 and H6 remain.
