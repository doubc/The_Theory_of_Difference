"""experiments/exp_82_long_evolution.py

Phase 3 实验十：长程演化 — CIVILIZATION 累积观察（1600步）

Purpose:
  在 exp_81 成功激活 CIVILIZATION（4/240步）的基础上，
  延长演化到 1600 步，观察 CIVILIZATION 级叙事是否随时间累积。

  核心问题：
  1. CIVILIZATION 激活是偶然的还是可持续的？
  2. 更长演化中，CIVILIZATION 步数比例是否增长？
  3. ODI/MSI 的四分位趋势是否持续上升？
  4. 叙事层级分布如何随时间演变？

Design:
  - seed=142（已验证可复现）, N0=72, steps=1600, sample_interval=10
  - 全 Phase 3 组件启用（同 exp_81）
  - 重点追踪：CIVILIZATION 累积曲线、层级分布时间序列

与 exp_81 的区别：
  - exp_81: 800步, sample_interval=5 → 160 记录点
  - exp_82: 1600步, sample_interval=10 → 160 记录点（相同记录密度，更长演化）
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.return_flow_channel import ReturnFlowChannel
from engine.unsealing_mechanism import UnsealingMechanism
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.minimal_self_detector import MinimalSelfDetector
from engine.global_bias_constraint import GlobalBiasConstraint
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from models.narrative_self import NarrativeRecursionOperator, NarrativeLevel
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from engine.six_threshold_detector import SixThresholdDetector


def extract_narrative_level_counts(narrative_summary: Dict) -> Dict:
    """Extract narrative level distribution from operator summary."""
    level_dist = narrative_summary.get('narrative_level_distribution', {})
    return {
        'MINI': level_dist.get('MINI_NARRATIVE', 0) or level_dist.get('MINI', 0),
        'INSTITUTIONAL': level_dist.get('INSTITUTIONAL', 0),
        'CIVILIZATION': level_dist.get('CIVILIZATION', 0),
    }


def analyze_narrative_activation(step_results: List[Dict]) -> Dict:
    """Comprehensive narrative activation analysis with level breakdown."""
    active_count = 0
    correction_count = 0
    msi_at_active = []
    odi_at_active = []
    norms_at_active = []
    civ_activated = False
    civ_steps = []
    civ_msi = []
    civ_odi = []

    prev_civ_count = 0
    for entry in step_results:
        narrative_data = entry.get('narrative_recursion', {})
        msi_data = entry.get('minimal_self', {})
        msi_val = msi_data.get('msi', 0.0) if isinstance(msi_data, dict) else 0.0
        odi_data = entry.get('odi', {})
        odi_val = odi_data.get('value', 0.0) if isinstance(odi_data, dict) else 0.0

        if narrative_data.get('bias_correction_applied', False):
            active_count += 1
            msi_at_active.append(msi_val)
            odi_at_active.append(odi_val)
            norms_at_active.append(float(narrative_data.get('correction_norm', 0.0)))

            level = narrative_data.get('narrative_level', '')
            is_civ_step = (level == 'CIVILIZATION' or narrative_data.get('is_civilization', False))

            level_snap = narrative_data.get('level_distribution_snapshot', {})
            curr_civ_count = level_snap.get('CIVILIZATION', 0)
            if curr_civ_count > prev_civ_count:
                is_civ_step = True
                prev_civ_count = curr_civ_count

            if is_civ_step:
                civ_activated = True
                civ_steps.append(entry.get('step', 0))
                civ_msi.append(msi_val)
                civ_odi.append(odi_val)

        correction = narrative_data.get('correction_norm', 0.0)
        if isinstance(correction, (int, float)) and correction > 0:
            correction_count += 1

    total = max(1, len(step_results))
    return {
        'narrative_active_steps': active_count,
        'narrative_active_ratio': round(active_count / total, 4),
        'narrative_correction_steps': correction_count,
        'msi_at_active_mean': round(float(np.mean(msi_at_active)), 4) if msi_at_active else 0.0,
        'msi_at_active_max': round(float(np.max(msi_at_active)), 4) if msi_at_active else 0.0,
        'odi_at_active_mean': round(float(np.mean(odi_at_active)), 4) if odi_at_active else 0.0,
        'odi_at_active_max': round(float(np.max(odi_at_active)), 4) if odi_at_active else 0.0,
        'mean_correction_norm': round(float(np.mean(norms_at_active)), 6) if norms_at_active else 0.0,
        'max_correction_norm': round(float(np.max(norms_at_active)), 6) if norms_at_active else 0.0,
        'civilization_activated': civ_activated,
        'civilization_steps': civ_steps,
        'civilization_n_steps': len(civ_steps),
        'civilization_msi_mean': round(float(np.mean(civ_msi)), 4) if civ_msi else 0.0,
        'civilization_odi_mean': round(float(np.mean(civ_odi)), 4) if civ_odi else 0.0,
    }


def analyze_growth(values: List[float], label: str) -> Dict:
    """Generic growth analysis for ODI/MSI with quartiles."""
    arr = np.array(values)
    n = len(arr)
    result = {
        f'{label}_min': round(float(np.min(arr)), 6),
        f'{label}_max': round(float(np.max(arr)), 6),
        f'{label}_final': round(float(arr[-1]), 6),
        f'{label}_mean': round(float(np.mean(arr)), 6),
    }
    if n >= 4:
        q1 = n // 4
        q2 = n // 2
        q3 = 3 * n // 4
        result[f'{label}_q1_mean'] = round(float(np.mean(arr[:q1])), 6)
        result[f'{label}_q2_mean'] = round(float(np.mean(arr[q1:q2])), 6)
        result[f'{label}_q3_mean'] = round(float(np.mean(arr[q2:q3])), 6)
        result[f'{label}_q4_mean'] = round(float(np.mean(arr[q3:])), 6)
    return result


def analyze_civilization_accumulation(step_results: List[Dict]) -> Dict:
    """Track CIVILIZATION accumulation over time."""
    cumulative_civ = []
    cumulative_total = []
    civ_count = 0
    total_count = 0

    for entry in step_results:
        narrative_data = entry.get('narrative_recursion', {})
        level = narrative_data.get('narrative_level', '')
        is_civ = (level == 'CIVILIZATION' or narrative_data.get('is_civilization', False))
        level_snap = narrative_data.get('level_distribution_snapshot', {})
        curr_civ = level_snap.get('CIVILIZATION', 0)

        total_count += 1
        if is_civ or curr_civ > civ_count:
            civ_count = curr_civ
        cumulative_civ.append(civ_count)
        cumulative_total.append(total_count)

    # Find CIVILIZATION activation phases
    civ_rate_by_quarter = []
    n = len(cumulative_civ)
    if n >= 4:
        q_size = n // 4
        for i in range(4):
            start = i * q_size
            end = (i + 1) * q_size if i < 3 else n
            civ_start = cumulative_civ[start] if start < n else 0
            civ_end = cumulative_civ[end - 1] if end <= n else cumulative_civ[-1]
            civ_rate_by_quarter.append(civ_end - civ_start)

    return {
        'cumulative_civ_final': cumulative_civ[-1] if cumulative_civ else 0,
        'civ_rate_by_quarter': civ_rate_by_quarter,
        'civ_acceleration': 'increasing' if len(civ_rate_by_quarter) == 4 and civ_rate_by_quarter[3] > civ_rate_by_quarter[0] else 'stable_or_decreasing',
    }


def run_experiment(N0=72, steps=1600, seed=142, sample_interval=10):
    """Run single experiment with all Phase 3 components enabled."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    return_flow_channel = ReturnFlowChannel(
        anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10,
    )
    unsealing_mechanism = UnsealingMechanism(
        l1_coupling_threshold=0.20, l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40, l2_stability_threshold=0.55,
    )
    pre_subjectivity = PreSubjectivityConvergence(
        coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True,
    )
    odi = OrganizationalDensityIndex(
        temporal_window=10, densification_threshold=0.005, use_refined_zones=True,
    )
    msi_detector = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35, 'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10, 'asymmetry_threshold': 0.15,
        'min_parts': 3, 'history_window': 8, 'history_dependency_threshold': 0.15,
        'min_history_depth': 5, 'self_reference_window': 8,
        'self_reference_threshold': 0.05, 'baseline_correlation_threshold': 0.2,
        'msi_activation_threshold': 0.20, 'msi_emergence_threshold': 0.35,
        'min_active_conditions': 1,
    })
    gbc = GlobalBiasConstraint(
        coherence_threshold=0.5, balance_threshold=0.3,
        min_mechanisms_required=4, geometric_weighting=True,
    )
    narrative = NarrativeRecursionOperator(
        bias_dimension=128, filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1, verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9,
    )
    anticipatory = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01},
    )
    counterfactual = CounterfactualEngine(config={
        'divergence_threshold': 0.1, 'max_branches': 4,
    })
    six_threshold = SixThresholdDetector()

    evolver = HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        max_layers=1, p1_eval_interval=sample_interval,
        phase2_verbose=False, phase3_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi, six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing_mechanism, return_flow_channel=return_flow_channel,
        pre_subjectivity_convergence=pre_subjectivity, minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory, counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative, global_bias_constraint=gbc,
    )

    print(f"[exp_82] N0={N0}, steps={steps}, seed={seed}, sample_interval={sample_interval}")
    print(f"[exp_82] Purpose: Long evolution — CIVILIZATION accumulation over 1600 steps")
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"[exp_82] Completed in {elapsed:.1f}s")

    # Extract step results
    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    # ODI / MSI time series
    odi_values = []
    msi_values = []
    for entry in step_results:
        odi_data = entry.get('odi', {})
        odi_val = odi_data.get('value', 0.0) if isinstance(odi_data, dict) else 0.0
        msi_val = entry.get('minimal_self', {}).get('msi', 0.0) if isinstance(entry.get('minimal_self'), dict) else 0.0
        odi_values.append(float(odi_val))
        msi_values.append(float(msi_val))

    # Narrative analysis
    narrative_analysis = analyze_narrative_activation(step_results)

    # CIVILIZATION accumulation analysis
    civ_accumulation = analyze_civilization_accumulation(step_results)

    # GBC trend
    gbc_coherences = []
    for entry in step_results:
        gbc_data = entry.get('global_bias_constraint', {})
        if isinstance(gbc_data, dict) and gbc_data.get('coherence', 0) > 0:
            gbc_coherences.append(gbc_data['coherence'])

    # Narrative summary from operator
    narrative_summary = narrative.get_summary() if narrative else {}

    diagnostic = {
        'seed': seed, 'N0': N0, 'steps': steps, 'sample_interval': sample_interval,
        'elapsed_seconds': round(elapsed, 1),
        'n_steps_recorded': len(step_results),
        'odi': analyze_growth(odi_values, 'odi'),
        'msi': analyze_growth(msi_values, 'msi'),
        'narrative': narrative_analysis,
        'civilization_accumulation': civ_accumulation,
        'narrative_operator_summary': narrative_summary,
        'narrative_level_distribution': extract_narrative_level_counts(narrative_summary),
        'gbc_coherence_mean': round(float(np.mean(gbc_coherences)), 4) if gbc_coherences else 0.0,
        'gbc_coherence_max': round(float(np.max(gbc_coherences)), 4) if gbc_coherences else 0.0,
    }

    return {
        'result': result,
        'diagnostic': diagnostic,
    }


def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(
        os.path.dirname(__file__),
        f'exp_82_results_{timestamp}.json'
    )

    print(f"{'='*60}")
    print(f"exp_82: Long Evolution — CIVILIZATION Accumulation")
    print(f"Testing: Does CIVILIZATION accumulate over 1600 steps?")
    print(f"Output: {output_file}")
    print(f"{'='*60}")

    run_data = run_experiment(N0=72, steps=1600, seed=142, sample_interval=10)
    diag = run_data['diagnostic']

    # Print summary
    print(f"\n{'='*60}")
    print(f"exp_82 Results (seed={diag['seed']}):")
    print(f"  Steps recorded: {diag['n_steps_recorded']}")
    print(f"  Elapsed: {diag['elapsed_seconds']}s")
    print(f"\n  ODI: min={diag['odi']['odi_min']:.4f} max={diag['odi']['odi_max']:.4f} "
          f"final={diag['odi']['odi_final']:.4f} mean={diag['odi']['odi_mean']:.4f}")
    print(f"  ODI quarters: Q1={diag['odi'].get('odi_q1_mean','?')} "
          f"Q2={diag['odi'].get('odi_q2_mean','?')} "
          f"Q3={diag['odi'].get('odi_q3_mean','?')} "
          f"Q4={diag['odi'].get('odi_q4_mean','?')}")
    print(f"\n  MSI: min={diag['msi']['msi_min']:.4f} max={diag['msi']['msi_max']:.4f} "
          f"final={diag['msi']['msi_final']:.4f} mean={diag['msi']['msi_mean']:.4f}")
    print(f"  MSI quarters: Q1={diag['msi'].get('msi_q1_mean','?')} "
          f"Q2={diag['msi'].get('msi_q2_mean','?')} "
          f"Q3={diag['msi'].get('msi_q3_mean','?')} "
          f"Q4={diag['msi'].get('msi_q4_mean','?')}")
    print(f"\n  Narrative:")
    print(f"    Active steps: {diag['narrative']['narrative_active_steps']}/{diag['n_steps_recorded']} "
          f"({diag['narrative']['narrative_active_ratio']*100:.1f}%)")
    print(f"    Correction steps: {diag['narrative']['narrative_correction_steps']}")
    print(f"    MSI at active: mean={diag['narrative']['msi_at_active_mean']:.4f} "
          f"max={diag['narrative']['msi_at_active_max']:.4f}")
    print(f"    ODI at active: mean={diag['narrative']['odi_at_active_mean']:.4f} "
          f"max={diag['narrative']['odi_at_active_max']:.4f}")
    print(f"    Mean correction norm: {diag['narrative']['mean_correction_norm']:.6f}")
    print(f"    Max correction norm: {diag['narrative']['max_correction_norm']:.6f}")
    print(f"\n  *** CIVILIZATION ***")
    print(f"    Activated: {diag['narrative']['civilization_activated']}")
    print(f"    N steps: {diag['narrative']['civilization_n_steps']}")
    if diag['narrative']['civilization_activated']:
        print(f"    Steps: {diag['narrative']['civilization_steps']}")
        print(f"    MSI at CIVILIZATION: mean={diag['narrative']['civilization_msi_mean']:.4f}")
        print(f"    ODI at CIVILIZATION: mean={diag['narrative']['civilization_odi_mean']:.4f}")
    if diag.get('narrative_level_distribution'):
        print(f"    Level dist: {diag['narrative_level_distribution']}")
    if diag.get('narrative_operator_summary'):
        ns = diag['narrative_operator_summary']
        print(f"    Operator records: {ns.get('total_narrative_records', 0)}")
        print(f"    Validated records: {ns.get('validated_records', 0)}")
    if diag.get('civilization_accumulation'):
        ca = diag['civilization_accumulation']
        print(f"    Cumulative CIV final: {ca['cumulative_civ_final']}")
        print(f"    CIV rate by quarter: {ca['civ_rate_by_quarter']}")
        print(f"    CIV acceleration: {ca['civ_acceleration']}")
    print(f"\n  GBC: coherence_mean={diag['gbc_coherence_mean']:.4f} "
          f"max={diag['gbc_coherence_max']:.4f}")
    print(f"{'='*60}")

    # Comparison with exp_81
    print(f"\n  Comparison with exp_81 (seed=142, N0=72, 800 steps):")
    print(f"    exp_81: CIVILIZATION=4, ODI max=0.7231, MSI max=0.3310")
    print(f"    exp_82: CIVILIZATION={diag['narrative']['civilization_n_steps']}, "
          f"ODI max={diag['odi']['odi_max']:.4f}, MSI max={diag['msi']['msi_max']:.4f}")
    if diag['narrative']['civilization_activated']:
        civ = diag['narrative']['civilization_n_steps']
        if civ > 4:
            print(f"    >>> CIVILIZATION ACCUMULATION CONFIRMED ({civ} > 4) <<<")
        elif civ == 4:
            print(f"    >>> CIVILIZATION STABLE (same as exp_81) <<<")
        else:
            print(f"    >>> CIVILIZATION DECREASED — investigate <<<")
    else:
        print(f"    >>> CIVILIZATION not activated in longer run — regression? <<<")
    print(f"{'='*60}")

    # Save
    summary = {
        'experiment': 'exp_82_long_evolution',
        'timestamp': timestamp,
        'description': 'Long evolution (1600 steps) — CIVILIZATION accumulation observation',
        'hypothesis': 'CIVILIZATION steps will accumulate over longer evolution',
        'comparison_target': 'exp_81 (800 steps, CIVILIZATION=4)',
        'diagnostic': diag,
    }
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults saved to: {output_file}")

    return summary


if __name__ == '__main__':
    main()
