"""experiments/exp_77_long_run_threshold.py

Phase 3 实验七：长步数六阈值稳定性验证

Purpose:
  1. 延长演化步数至 1600，验证六阈值达标步数占比能否稳定提升
  2. 观察 ODI/MSI 在长演化中的增长曲线和稳态行为
  3. 检测叙事递归是否在 ODI > 0.5 + MSI > 0.35 后开始激活
  4. 为 Phase 3 的 GBC/反事实/预期引擎集成提供基线数据

Based on:
  exp_76_threshold_diagnostic.py (with SixThresholdDetector injection fix)
  exp_74 diagnosis: ODI/MSI 需要更长演化才能稳定突破前主体态地板

Key hypothesis:
  - 论文 §4.4 说前主体态是"范围"而非"固定阈值"
  - 长演化中 ODI 应从 structuring 区(0.3-0.5)逐步增长到 pre_subjective 区(0.5-0.8)
  - 六阈值达标步数占比应随演化推进而增加
  - MSI 应在 ODI > 0.5 后开始显著增长（验证前主体态地板假设）
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


# ─── Helpers (from exp_76) ───

def extract_threshold_details(step_results: List[Dict]) -> List[Dict]:
    trajectory = []
    for entry in step_results:
        six_data = entry.get('six_threshold', {})
        ts = entry.get('step', entry.get('timestamp', 0))
        odi_data = entry.get('odi', {})
        odi_val = odi_data.get('value', 0.0) if isinstance(odi_data, dict) else 0.0

        detail = {
            'step': ts,
            'odi': round(float(odi_val), 6),
            'n_met': six_data.get('n_met', 0),
            'all_met': six_data.get('all_met', False),
            'bottleneck': six_data.get('bottleneck'),
            'thresholds': {},
        }
        for s in six_data.get('statuses', []):
            detail['thresholds'][s['id']] = {
                'name': s['name'],
                'value': s['value'],
                'threshold': s['threshold'],
                'is_met': s['is_met'],
                'gap': s['gap'],
                'ratio': s['ratio'],
            }
        trajectory.append(detail)
    return trajectory


def analyze_growth_curve(odi_values: List[float], msi_values: List[float],
                         steps: List[int]) -> Dict:
    """Analyze ODI/MSI growth curves for phase transitions."""
    odi_arr = np.array(odi_values)
    msi_arr = np.array(msi_values)
    step_arr = np.array(steps)

    result = {
        'odi': {
            'min': round(float(np.min(odi_arr)), 6),
            'max': round(float(np.max(odi_arr)), 6),
            'final': round(float(odi_arr[-1]), 6),
            'mean': round(float(np.mean(odi_arr)), 6),
            'above_05_count': int(np.sum(odi_arr >= 0.5)),
            'above_08_count': int(np.sum(odi_arr >= 0.8)),
            'above_05_ratio': round(float(np.sum(odi_arr >= 0.5) / len(odi_arr)), 4),
        },
        'msi': {
            'min': round(float(np.min(msi_arr)), 6),
            'max': round(float(np.max(msi_arr)), 6),
            'final': round(float(msi_arr[-1]), 6),
            'mean': round(float(np.mean(msi_arr)), 6),
            'nonzero_count': int(np.sum(msi_arr > 0)),
            'nonzero_ratio': round(float(np.sum(msi_arr > 0) / len(msi_arr)), 4),
            'above_035_count': int(np.sum(msi_arr >= 0.35)),
        },
    }

    # Phase transition detection: find step where ODI first crosses 0.5
    above_05 = np.where(odi_arr >= 0.5)[0]
    if len(above_05) > 0:
        first_cross_idx = above_05[0]
        result['odi']['first_cross_05_step'] = int(step_arr[first_cross_idx])
        result['odi']['first_cross_05_value'] = round(float(odi_arr[first_cross_idx]), 6)
    else:
        result['odi']['first_cross_05_step'] = None

    # Phase transition detection: find step where MSI first exceeds 0.35
    above_035 = np.where(msi_arr >= 0.35)[0]
    if len(above_035) > 0:
        first_msi_idx = above_035[0]
        result['msi']['first_cross_035_step'] = int(step_arr[first_msi_idx])
        result['msi']['first_cross_035_value'] = round(float(msi_arr[first_msi_idx]), 6)
    else:
        result['msi']['first_cross_035_step'] = None

    # Growth rate analysis: compare first half vs second half ODI
    mid = len(odi_arr) // 2
    if mid > 0:
        result['odi']['first_half_mean'] = round(float(np.mean(odi_arr[:mid])), 6)
        result['odi']['second_half_mean'] = round(float(np.mean(odi_arr[mid:])), 6)
        result['msi']['first_half_mean'] = round(float(np.mean(msi_arr[:mid])), 6)
        result['msi']['second_half_mean'] = round(float(np.mean(msi_arr[mid:])), 6)

    # Quarters analysis for growth trend
    q1 = len(odi_arr) // 4
    q2 = len(odi_arr) // 2
    q3 = 3 * len(odi_arr) // 4
    if q1 > 0:
        result['odi']['q1_mean'] = round(float(np.mean(odi_arr[:q1])), 6)
        result['odi']['q2_mean'] = round(float(np.mean(odi_arr[q1:q2])), 6)
        result['odi']['q3_mean'] = round(float(np.mean(odi_arr[q2:q3])), 6)
        result['odi']['q4_mean'] = round(float(np.mean(odi_arr[q3:])), 6)
        result['msi']['q1_mean'] = round(float(np.mean(msi_arr[:q1])), 6)
        result['msi']['q2_mean'] = round(float(np.mean(msi_arr[q1:q2])), 6)
        result['msi']['q3_mean'] = round(float(np.mean(msi_arr[q2:q3])), 6)
        result['msi']['q4_mean'] = round(float(np.mean(msi_arr[q3:])), 6)

    return result


def analyze_narrative_activation(step_results: List[Dict]) -> Dict:
    """Analyze narrative recursion activation patterns."""
    narrative_active_count = 0
    narrative_correction_count = 0
    msi_at_narrative = []

    for entry in step_results:
        # Fix: evolver writes to 'narrative_recursion', not 'narrative'
        narrative_data = entry.get('narrative_recursion', {})
        msi_data = entry.get('minimal_self', {})
        msi_val = msi_data.get('msi', 0.0) if isinstance(msi_data, dict) else 0.0

        # Fix: evolver uses 'bias_correction_applied' field, not 'active'
        if narrative_data.get('bias_correction_applied', False):
            narrative_active_count += 1
            msi_at_narrative.append(msi_val)

        correction = narrative_data.get('correction_norm', 0.0)
        if isinstance(correction, (int, float)) and correction > 0:
            narrative_correction_count += 1

    return {
        'narrative_active_steps': narrative_active_count,
        'narrative_active_ratio': round(narrative_active_count / max(1, len(step_results)), 4),
        'narrative_correction_steps': narrative_correction_count,
        'msi_at_narrative_mean': round(float(np.mean(msi_at_narrative)), 4) if msi_at_narrative else 0.0,
        'msi_at_narrative_max': round(float(np.max(msi_at_narrative)), 4) if msi_at_narrative else 0.0,
    }


def analyze_gbc_trend(step_results: List[Dict]) -> Dict:
    """Analyze GlobalBiasConstraint coherence and balance trends."""
    coherences = []
    balances = []
    pass_count = 0

    for entry in step_results:
        gbc_data = entry.get('global_bias_constraint', {})
        if isinstance(gbc_data, dict):
            coh = gbc_data.get('coherence', 0.0)
            bal = gbc_data.get('balance', 0.0)
            coherences.append(coh)
            balances.append(bal)
            if gbc_data.get('passed', False):
                pass_count += 1

    if not coherences:
        return {'available': False}

    return {
        'available': True,
        'coherence_mean': round(float(np.mean(coherences)), 4),
        'coherence_max': round(float(np.max(coherences)), 4),
        'balance_mean': round(float(np.mean(balances)), 4),
        'balance_max': round(float(np.max(balances)), 4),
        'pass_rate': round(pass_count / len(coherences), 4),
        'pass_count': pass_count,
    }


# ─── Single Run ───

def run_long_diagnostic(
    N0: int = 72,
    steps: int = 1600,
    seed: int = 42,
    sample_interval: int = 10,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Run long evolution with full Phase 3 diagnostics."""

    torch.manual_seed(seed)
    np.random.seed(seed)

    return_flow_channel = ReturnFlowChannel(
        anchor_threshold=0.05,
        decay_rate=0.01,
        min_retention_steps=10,
    )

    unsealing_mechanism = UnsealingMechanism(
        l1_coupling_threshold=0.20,
        l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40,
        l2_stability_threshold=0.55,
    )

    pre_subjectivity = PreSubjectivityConvergence(
        coupling_threshold=0.25,
        stability_threshold=0.40,
        dynamic_threshold=True,
    )

    odi = OrganizationalDensityIndex(
        temporal_window=10,
        densification_threshold=0.005,
        use_refined_zones=True,
    )

    msi_detector = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35,
        'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10,
        'asymmetry_threshold': 0.15,
        'min_parts': 3,
        'history_window': 8,
        'history_dependency_threshold': 0.15,
        'min_history_depth': 5,
        'self_reference_window': 8,
        'self_reference_threshold': 0.05,
        'baseline_correlation_threshold': 0.2,
        'msi_activation_threshold': 0.20,
        'msi_emergence_threshold': 0.35,
        'min_active_conditions': 1,
    })

    gbc = GlobalBiasConstraint(
        coherence_threshold=0.5,
        balance_threshold=0.3,
        min_mechanisms_required=4,
        geometric_weighting=True,
    )

    narrative = NarrativeRecursionOperator(
        bias_dimension=128,
        filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1,
        verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9,
    )

    anticipatory = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01},
    )
    counterfactual = CounterfactualEngine(config={
        'divergence_threshold': 0.1,
        'max_branches': 4,
    })

    six_threshold = SixThresholdDetector()

    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=steps,
        sample_interval=sample_interval,
        max_layers=1,
        p1_eval_interval=sample_interval,
        phase2_verbose=False,
        phase3_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi,
        six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing_mechanism,
        return_flow_channel=return_flow_channel,
        pre_subjectivity_convergence=pre_subjectivity,
        minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory,
        counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative,
        global_bias_constraint=gbc,
    )

    print(f"[exp_77] N0={N0}, steps={steps}, seed={seed}")

    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"[exp_77] Completed in {elapsed:.1f}s")

    # ── Extract data ──
    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    # Threshold trajectory
    threshold_trajectory = extract_threshold_details(step_results)

    # ODI / MSI values
    odi_values = []
    msi_values = []
    step_nums = []
    for entry in step_results:
        ts = entry.get('step', entry.get('timestamp', 0))
        odi_data = entry.get('odi', {})
        odi_val = odi_data.get('value', 0.0) if isinstance(odi_data, dict) else 0.0
        msi_val = entry.get('minimal_self', {}).get('msi', 0.0) if isinstance(entry.get('minimal_self'), dict) else 0.0
        odi_values.append(float(odi_val))
        msi_values.append(float(msi_val))
        step_nums.append(ts)

    # ── Analyses ──
    growth_analysis = analyze_growth_curve(odi_values, msi_values, step_nums)
    narrative_analysis = analyze_narrative_activation(step_results)
    gbc_analysis = analyze_gbc_trend(step_results)

    # Threshold met fraction by quarters
    threshold_met_by_quarter = {}
    q_size = len(threshold_trajectory) // 4
    if q_size > 0:
        for qi, qlabel in enumerate(['q1', 'q2', 'q3', 'q4']):
            q_data = threshold_trajectory[qi * q_size : (qi + 1) * q_size]
            met_fracs = {}
            for d in q_data:
                for tid, tdata in d['thresholds'].items():
                    if tid not in met_fracs:
                        met_fracs[tid] = {'met': 0, 'total': 0}
                    met_fracs[tid]['total'] += 1
                    if tdata['is_met']:
                        met_fracs[tid]['met'] += 1
            threshold_met_by_quarter[qlabel] = {
                tid: round(v['met'] / max(1, v['total']), 3)
                for tid, v in met_fracs.items()
            }

    diagnostic = {
        'seed': seed,
        'N0': N0,
        'steps': steps,
        'elapsed_seconds': round(elapsed, 1),
        'n_steps_recorded': len(step_results),
        'growth_analysis': growth_analysis,
        'narrative_analysis': narrative_analysis,
        'gbc_analysis': gbc_analysis,
        'threshold_met_by_quarter': threshold_met_by_quarter,
    }

    return {
        'result': result,
        'diagnostic': diagnostic,
        'threshold_trajectory': threshold_trajectory,
    }


# ─── Main ───

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(
        os.path.dirname(__file__),
        f'exp_77_results_{timestamp}.json'
    )

    print(f"{'='*60}")
    print(f"exp_77: Long-run threshold stability (1600 steps)")
    print(f"Output: {output_file}")
    print(f"{'='*60}")

    # Run 2 seeds for comparison
    runs = []
    for i in range(2):
        seed = 42 + i * 100
        run_data = run_long_diagnostic(
            N0=72,
            steps=1600,
            seed=seed,
            sample_interval=10,
            verbose=(i == 0),
        )
        runs.append(run_data)

    # Summary
    summary = {
        'experiment': 'exp_77_long_run_threshold',
        'timestamp': timestamp,
        'description': 'Long-run (1600 steps) six-threshold stability verification',
        'hypothesis': 'ODI/MSI should stabilize above pre-subjective floor with longer evolution',
        'runs': [],
    }

    for i, run in enumerate(runs):
        d = run['diagnostic']
        ga = d['growth_analysis']
        run_summary = {
            'seed': d['seed'],
            'elapsed': d['elapsed_seconds'],
            'steps_recorded': d['n_steps_recorded'],
            'odi': ga['odi'],
            'msi': ga['msi'],
            'narrative': d['narrative_analysis'],
            'gbc': d['gbc_analysis'],
            'threshold_met_by_quarter': d.get('threshold_met_by_quarter', {}),
        }
        summary['runs'].append(run_summary)

        # Print
        print(f"\n{'='*60}")
        print(f"Seed {d['seed']} Results:")
        print(f"  ODI: min={ga['odi']['min']} max={ga['odi']['max']} "
              f"final={ga['odi']['final']} mean={ga['odi']['mean']}")
        print(f"  ODI > 0.5: {ga['odi']['above_05_count']}/{d['n_steps_recorded']} "
              f"({ga['odi']['above_05_ratio']*100:.1f}%)")
        print(f"  ODI > 0.8: {ga['odi']['above_08_count']}/{d['n_steps_recorded']}")
        if ga['odi'].get('first_cross_05_step') is not None:
            print(f"  ODI first > 0.5 at step {ga['odi']['first_cross_05_step']}")
        print(f"  ODI quarters: Q1={ga['odi'].get('q1_mean','?')} "
              f"Q2={ga['odi'].get('q2_mean','?')} "
              f"Q3={ga['odi'].get('q3_mean','?')} "
              f"Q4={ga['odi'].get('q4_mean','?')}")
        print(f"  MSI: min={ga['msi']['min']} max={ga['msi']['max']} "
              f"final={ga['msi']['final']} mean={ga['msi']['mean']}")
        print(f"  MSI nonzero: {ga['msi']['nonzero_count']}/{d['n_steps_recorded']} "
              f"({ga['msi']['nonzero_ratio']*100:.1f}%)")
        print(f"  MSI > 0.35: {ga['msi']['above_035_count']}/{d['n_steps_recorded']}")
        if ga['msi'].get('first_cross_035_step') is not None:
            print(f"  MSI first > 0.35 at step {ga['msi']['first_cross_035_step']}")
        print(f"  Narrative: active={d['narrative_analysis']['narrative_active_steps']} "
              f"corrections={d['narrative_analysis']['narrative_correction_steps']}")
        if d['gbc_analysis'].get('available'):
            print(f"  GBC: coherence_max={d['gbc_analysis']['coherence_max']} "
                  f"balance_max={d['gbc_analysis']['balance_max']} "
                  f"pass_rate={d['gbc_analysis']['pass_rate']}")

    # Save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")
    print(f"{'='*60}")

    return summary


if __name__ == '__main__':
    main()
