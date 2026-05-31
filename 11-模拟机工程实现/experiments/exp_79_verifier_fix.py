"""experiments/exp_79_verifier_fix.py

Phase 3 实验九：verifier post_odi 修复验证 + seed=142 可复现性

Purpose:
  验证 verifier post_odi 自动估算修复后，叙事验证器是否能正确通过验证。
  同时测试 seed=142 可复现性。

与 exp_77 的区别：
  1. 使用修复后的 hierarchical_evolver.py（方向向量 one-hot + ODI 实参）
  2. 每步记录叙事细节（信号数、修正范数、叙事层级）
  3. 800 步（更快），单 seed=42
  4. 增加叙事激活的步级时间序列分析

Key hypothesis:
  - 方向向量修复后，新颖性计算不再恒为 0，叙事筛选器应能通过部分信号
  - ODI 实参传递后，叙事验证器有正确的 post_odi 参考值
  - 叙事应在 MSI > 0.35 且 ODI > 0.5 的步数中激活
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
from models.narrative_self import NarrativeRecursionOperator
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from engine.six_threshold_detector import SixThresholdDetector


def extract_narrative_timeseries(step_results: List[Dict]) -> List[Dict]:
    """Extract per-step narrative activation time series."""
    series = []
    for entry in step_results:
        step = entry.get('step', 0)
        narrative_data = entry.get('narrative_recursion', {})
        msi_data = entry.get('minimal_self', {})
        msi_val = msi_data.get('msi', 0.0) if isinstance(msi_data, dict) else 0.0
        odi_data = entry.get('odi', {})
        odi_val = odi_data.get('value', 0.0) if isinstance(odi_data, dict) else 0.0

        point = {
            'step': step,
            'msi': round(float(msi_val), 6),
            'odi': round(float(odi_val), 6),
            'narrative_active': narrative_data.get('bias_correction_applied', False),
            'signals_processed': narrative_data.get('signals_processed', 0),
            'correction_norm': round(float(narrative_data.get('correction_norm', 0.0)), 8),
        }
        series.append(point)
    return series


def analyze_narrative_activation(step_results: List[Dict]) -> Dict:
    """Comprehensive narrative activation analysis."""
    active_count = 0
    correction_count = 0
    msi_at_active = []
    odi_at_active = []
    signals_at_active = []
    norms_at_active = []

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
            signals_at_active.append(narrative_data.get('signals_processed', 0))
            norms_at_active.append(float(narrative_data.get('correction_norm', 0.0)))

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
        'signals_at_active_mean': round(float(np.mean(signals_at_active)), 1) if signals_at_active else 0.0,
        'mean_correction_norm': round(float(np.mean(norms_at_active)), 6) if norms_at_active else 0.0,
        'max_correction_norm': round(float(np.max(norms_at_active)), 6) if norms_at_active else 0.0,
    }


def analyze_growth(values: List[float], label: str) -> Dict:
    """Generic growth analysis for ODI/MSI."""
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


def run_experiment(N0=72, steps=800, seed=42, sample_interval=5):
    """Run single experiment."""
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

    print(f"[exp_79] N0={N0}, steps={steps}, seed={seed}, sample_interval={sample_interval}")
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"[exp_79] Completed in {elapsed:.1f}s")

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

    # Narrative time series
    narrative_ts = extract_narrative_timeseries(step_results)
    narrative_analysis = analyze_narrative_activation(step_results)

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
        'narrative_operator_summary': narrative_summary,
        'gbc_coherence_mean': round(float(np.mean(gbc_coherences)), 4) if gbc_coherences else 0.0,
        'gbc_coherence_max': round(float(np.max(gbc_coherences)), 4) if gbc_coherences else 0.0,
    }

    return {
        'result': result,
        'diagnostic': diagnostic,
        'narrative_timeseries': narrative_ts,
    }


def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(
        os.path.dirname(__file__),
        f'exp_79_results_{timestamp}.json'
    )

    print(f"{'='*60}")
    print(f"exp_79: Narrative Activation Verification")
    print(f"Testing: direction vector fix + ODI passthrough")
    print(f"Output: {output_file}")
    print(f"{'='*60}")

    all_results = []
    for seed in [142, 242]:
        run_data = run_experiment(N0=72, steps=800, seed=seed, sample_interval=5)
        all_results.append(run_data)
    diag = all_results[0]['diagnostic']

    # Print summary
    print(f"\n{'='*60}")
    print(f"exp_79 Results (seed={diag['seed']}):")
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
    if diag.get('narrative_operator_summary'):
        ns = diag['narrative_operator_summary']
        print(f"    Operator records: {ns.get('total_narrative_records', 0)}")
        print(f"    Validated records: {ns.get('validated_records', 0)}")
        print(f"    Level dist: {ns.get('narrative_level_distribution', {})}")
    print(f"\n  GBC: coherence_mean={diag['gbc_coherence_mean']:.4f} "
          f"max={diag['gbc_coherence_max']:.4f}")
    print(f"{'='*60}")

    # Save
    summary = {
        'experiment': 'exp_79_verifier_fix',
        'timestamp': timestamp,
        'description': 'exp_79: verifier post_odi fix + seed reproducibility (142, 242)',
        'fixes_tested': [
            '4eab9b2: direction vector one-hot encoding (was scalar, novelty always 0)',
            'ODI passthrough: _last_odi_value tracking (was hardcoded 0.0)',
            'post_odi estimation: bias alignment proxy (was hardcoded same as pre_odi)',
        ],
        'diagnostic': diag,
        'narrative_timeseries': run_data['narrative_timeseries'],
    }
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults saved to: {output_file}")

    return summary


if __name__ == '__main__':
    main()
