# exp_151 Analysis Preparation — Phase 11 P3: Asymmetric (Unidirectional) Coupling

**Date**: 2026-06-06 23:25 CST (heartbeat)  
**Status**: experiment running (session nova-kelp, pid 4900)  
**Preparing analysis framework** while experiment executes.

---

## 1. Experimental Design (Recap)

| Parameter | Value |
|-----------|-------|
| N0 | 60 (master=40, slave=20) |
| N0* | ≈30.5 (phase transition) |
| Master (S0) | 40 bits > N0* → L1 forms reliably |
| Slave (S1) | 20 bits < N0* → L1 does NOT form at zero coupling |
| Coupling | Unidirectional S0→S1: [0.0, 0.5, 1.0, 2.0, 5.0, 10.0] |
| S1→S0 | Always 0.0 |
| Seeds/level | 8 |
| Total runs | 48 |

**Key innovation vs exp_150**: asymmetric subspace sizes + unidirectional coupling  
exp_150 used symmetric sizes (36 bits each, all > N0*) — all in ordered phase, so coupling had no "room" to modulate.  
exp_151 uses master (40 > N0*) and slave (20 < N0*) — creates an *asymmetric baseline* where only the master forms L1 at zero coupling.

---

## 2. Hypotheses to Evaluate

### H151-1 (Asymmetric baseline)
> At coupling=0.0: master L1 rate ≈ 1.0, slave L1 rate ≈ 0.0

**Pass criterion**: `master_l1_rate(0.0) > 0.5` AND `slave_l1_rate(0.0) < 0.5`  
**Physics**: Master has 40 bits (>N0*), slave has 20 bits (<N0*). At zero coupling they evolve independently.

### H151-2 (Rescue effect)
> As S0→S1 coupling increases, S1's L1 formation rate INCREASES (master "rescues" slave)

**Pass criterion**: `slave_l1_rate(cs)` is monotonically non-decreasing with coupling strength  
**Physics**: Coupling injects master's direction field bias into slave's binding strength. If strong enough, slave may cross the phase transition threshold.

### H151-3 (No reverse effect)
> S0's L1 rate is unaffected by coupling (since S1→S0 = 0.0)

**Pass criterion**: `std(master_l1_rate across all cs) < 0.3`  
**Physics**: No information flows from slave to master. Master's evolution should be coupling-invariant.

### H151-4 (Causal arrow)
> L1 formation timing: S0 predicts S1, but not vice versa (at non-zero coupling)

**Pass criterion**: `l1_timing_diff` is non-None for coupled runs (at least some timing data)  
**Physics**: Unidirectional coupling creates a causal arrow. Master's L1 formation should precede slave's (when slave forms L1).

---

## 3. Expected Results (Pre-Experiment Prediction)

### Prediction for H151-1: ✅ PASS (high confidence)
Master=40 > N0* → L1 forms. Slave=20 < N0* → L1 does not form.  
This is the core design insight. Should be robust across all 8 seeds.

### Prediction for H151-2: ❓ UNCERTAIN
exp_150 found that off-diagonal injection (`strength * direction_field * 0.1`) is too weak to modulate L1 when N_sub > N0*.  
Here, slave is **below** N0* (20 < 30.5), so coupling must *create* L1 formation ability. This is a harder task than exp_150's suppression.  
**Likely outcome**: coupling up to 10.0 is still too weak. H151-2 may **FAIL**.  
**If fails**: need stronger coupling mechanism (direct binding matrix scaling, not directional bias injection).

### Prediction for H151-3: ✅ PASS (high confidence)
S1→S0 coupling = 0.0. Master evolves independently. Rate should be constant (=1.0).

### Prediction for H151-4: ❓ UNCERTAIN
Depends on H151-2. If slave never forms L1 (H151-2 FAIL), there is no `l1_timing_diff` to measure.  
**If H151-2 fails**: H151-4 fails by construction (no timing data).

---

## 4. If H151-2 Fails: Next Steps

If coupling is too weak to produce rescue effect:

1. **Option A**: Increase coupling mechanism strength (change `0.1` factor to `1.0` or higher in `subspace_evolver.py`)
2. **Option B**: Change coupling mechanism from directional bias injection to direct `binding_strength` matrix scaling
3. **Option C**: Use a smaller master (e.g., 35 bits, just above N0*) so the coupling signal is stronger relative to threshold
4. **Option D**: Move to exp_152 (parameter specialization) and return to coupling with a redesigned mechanism in a later sub-phase

**Recommendation**: Try Option A first (increase coupling strength factor in engine). If that works, re-run exp_151 with stronger coupling. If not, Option B (architectural change to coupling mechanism).

---

## 5. Analysis To-Do (after experiment completes)

- [ ] Load `experiments/exp_151_phase11_p3_asymmetric_YYYYMMDD_HHMM.json`
- [ ] Evaluate H151-1 through H151-4
- [ ] If H151-2 fails: quantify how much stronger the coupling needs to be (extrapolate from results)
- [ ] Compare exp_150 and exp_151: does asymmetric baseline help?
- [ ] Write `docs/exp_151_analysis.md`
- [ ] Commit results + analysis
- [ ] Update HEARTBEAT.md (exp_151 DONE, move to exp_152 or coupling mechanism redesign)

---

*Written during heartbeat 2026-06-06 23:25 CST while exp_151 executes in background (session nova-kelp).*
