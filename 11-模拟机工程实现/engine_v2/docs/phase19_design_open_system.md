# Phase 19 Design: Open System (Environment Interaction)

## Core Question

Closed recursion asymptotically approaches iso_score ~ 0.72 (Phase 18 conclusion).
**Key question**: Can environment interaction re-animate the system at saturation?

Old engine (Phase 13-16): L1 flux=0, environment directly wrote state -> destroy or absorb.
engine_v2: L1 flux~0.22, environment modulates params -> true interaction possible.

## Hypotheses

### H19-P0: iso_score > 0.65 -> env cannot restart self-reference
System too stable, absorbs perturbation. Strength 0.05-0.30: iso change < 0.05, flux change < 0.02.

### H19-P1: iso_score < 0.50 -> env can restart self-reference
System unstable, perturbation changes structure. org count k change > 20%, flux change > 0.05.

### H19-P2: High-complexity env -> system absorbs env structure
System org structure vs env feature bits: Spearman rho > 0.5.

### H19-P3: Low-complexity env -> system ignores env
System k, flux, iso_score change < 5%.

## Architecture

### EnvironmentField
1. No sealing, continuous churn (churn_source = all active bits)
2. structural_entropy: 0=white noise, 1=weak cluster, 2=strong cluster
3. env_cycle_length: short(1-3) = fast env; long(10-30) = slow env

### EnvironmentCoupling
- Bidirectional: env -> main (constraint) and main -> env (waste)
- coupling_strength in [0, 1]
- Threshold: above threshold affects m3 flux_budget; below affects m4 candidate set

## Experiments

### exp_185: P0 strength sweep (5 strengths x 16 seeds = 80 runs)
- strengths: 0.0(baseline), 0.05, 0.10, 0.20, 0.50
- N0=48, env.N=16, cycle=5, introduced after L0 seal
- Measure: iso_score delta, L1+L2 flux, emergence depth, k change

### exp_186: P1 complexity sweep (3 levels x 16 seeds = 64 runs)
- structural_entropy: 0(noise), 1(weak), 2(strong), control(no env)
- strength=0.20, N0=48, env.N=24
- Measure: system-env Spearman rho, colonization rate

### exp_187: P2 timing sweep (3 thresholds x 16 seeds = 64 runs)
- threshold: 0.0(always), 0.40, 0.60, 0.80
- strength=0.20, N0=48, env.N=12, entropy=1
- Measure: pre/post iso_score change, reversibility

## Implementation Plan

1. `diffsim/environment.py` - EnvironmentField + EnvironmentCoupling
2. `diffsim/world.py` - integrate coupling into RecursiveWorld
3. `experiments/exp_185/186/187` - experiment scripts
4. `docs/phase19_*_analysis.md` - analysis documents
