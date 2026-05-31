"""experiments/exp_76_threshold_diagnostic.py

Phase 3 实验六：六阈值逐值诊断

Purpose:
  1. 在演化过程中逐 step 记录六个阈值的 value/threshold/passed 状态
  2. 定位 threshold_proximity=0.0 的根本原因（哪个阈值最远）
  3. 输出详细诊断报告

Key fix vs exp_75:
  - exp_75 只存了聚合后的 threshold_proximity（=0.0）
  - exp_76 读取 hierarchical_evolver.py 暴露的 six_threshold.statuses，
    记录每个阈值的具体数值
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


# ─── Six-Threshold Diagnostic ───

def extract_threshold_details(step_results: List[Dict]) -> List[Dict]:
    """从 step_results 中提取每个 step 的六阈值详细数值。

    hierarchical_evolver.py 的 result_entry['six_threshold'] 现在包含 'statuses' 字段：
      statuses: [ {id, name, value, threshold, is_met, gap, ratio}, ... ]
    """
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


def summarize_thresholds(trajectory: List[Dict]) -> Dict:
    """汇总整个轨迹的阈值表现，找出最薄弱环节。"""
    if not trajectory:
        return {}

    # 收集每个阈值在所有 step 的最大值
    best = {}
    last = {}
    for d in trajectory:
        for tid, tdata in d['thresholds'].items():
            if tid not in best or tdata['value'] > best[tid]['value']:
                best[tid] = tdata
            last[tid] = tdata

    # 找出差距最大的阈值（瓶颈）
    worst_gap = -1.0
    bottleneck = None
    for tid, tdata in last.items():
        if not tdata['is_met'] and tdata['gap'] > worst_gap:
            worst_gap = tdata['gap']
            bottleneck = tid

    # 统计每个阈值的达标步数
    met_counts = {tid: 0 for tid in last}
    total_steps = len(trajectory)
    for d in trajectory:
        for tid, tdata in d['thresholds'].items():
            if tdata['is_met']:
                met_counts[tid] += 1

    return {
        'total_steps': total_steps,
        'best_values': {tid: tdata for tid, tdata in best.items()},
        'last_values': {tid: tdata for tid, tdata in last.items()},
        'met_counts': met_counts,
        'met_fractions': {tid: round(c / total_steps, 3) for tid, c in met_counts.items()},
        'bottleneck': bottleneck,
        'worst_gap': round(worst_gap, 6) if worst_gap >= 0 else None,
    }


# ─── Single Run ───

def run_diagnostic(
    N0: int = 72,
    steps: int = 400,
    seed: int = 42,
    sample_interval: int = 5,
    verbose: bool = True,
) -> Dict[str, Any]:
    """运行单次演化，返回阈值诊断结果。"""

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

    # ★ 关键修复：创建 SixThresholdDetector 并注入 HierarchicalEvolver
    # 之前的 exp_76 缺少此组件，导致 six_threshold 结果为空，
    # 无法获取各阈值的 value/threshold/is_met 详情
    six_threshold = SixThresholdDetector()

    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=steps,
        sample_interval=sample_interval,
        max_layers=1,
        p1_eval_interval=sample_interval,
        phase2_verbose=False,
        phase3_verbose=False,
        # Phase 2 P0
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        # Phase 2 P1
        organizational_density_index=odi,
        six_threshold_detector=six_threshold,
        # 解封与回流
        unsealing_mechanism=unsealing_mechanism,
        return_flow_channel=return_flow_channel,
        pre_subjectivity_convergence=pre_subjectivity,
        # Phase 3
        minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory,
        counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative,
        global_bias_constraint=gbc,
    )

    print(f"[exp_76] N0={N0}, steps={steps}, seed={seed}")

    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"[exp_76] Completed in {elapsed:.1f}s")

    # ── 提取阈值轨迹 ──
    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    threshold_trajectory = extract_threshold_details(step_results)

    # ODI 轨迹
    odi_trajectory = []
    msi_values = []
    for entry in step_results:
        ts = entry.get('step', entry.get('timestamp', 0))
        odi_data = entry.get('odi', {})
        odi_val = odi_data.get('value', 0.0) if isinstance(odi_data, dict) else 0.0
        sub = odi_data.get('sub_indices', {}) if isinstance(odi_data, dict) else {}
        odi_trajectory.append({
            'step': ts,
            'odi': round(float(odi_val), 6),
            'threshold_proximity': sub.get('threshold_proximity', 0.0),
            'coupling_density': sub.get('coupling_density', 0.0),
        })
        msi_values.append(entry.get('minimal_self', {}).get('msi', 0.0))

    # 汇总诊断
    summary = summarize_thresholds(threshold_trajectory)

    msi_arr = np.array(msi_values)
    odi_arr = np.array([t['odi'] for t in odi_trajectory])

    diagnostic = {
        'seed': seed,
        'N0': N0,
        'steps': steps,
        'elapsed_seconds': round(elapsed, 1),
        'n_steps_recorded': len(step_results),
        'threshold_summary': summary,
        'odi_final': round(float(odi_arr[-1]), 6) if len(odi_arr) > 0 else 0.0,
        'odi_max': round(float(np.max(odi_arr)), 6) if len(odi_arr) > 0 else 0.0,
        'odi_above_05_count': int(np.sum(odi_arr >= 0.5)),
        'msi_max': round(float(np.max(msi_arr)), 6) if len(msi_arr) > 0 else 0.0,
        'msi_nonzero_ratio': round(float(np.sum(msi_arr > 0) / max(1, len(msi_arr))), 4),
        # 最近 10 步的阈值快照
        'threshold_trajectory_tail': threshold_trajectory[-10:],
        'odi_trajectory_tail': odi_trajectory[-10:],
    }

    return {
        'result': result,
        'diagnostic': diagnostic,
        'threshold_trajectory': threshold_trajectory,
        'odi_trajectory': odi_trajectory,
    }


# ─── Main ───

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(
        os.path.dirname(__file__),
        f'exp_76_results_{timestamp}.json'
    )

    print(f"{'='*60}")
    print(f"exp_76: 六阈值逐值诊断")
    print(f"Output: {output_file}")
    print(f"{'='*60}")

    cfg = {'N0': 72, 'steps': 400, 'sample_interval': 5}

    # 运行 2 个 seed（快速诊断）
    runs = []
    for i in range(2):
        seed = 42 + i * 100
        run_data = run_diagnostic(
            N0=cfg['N0'],
            steps=cfg['steps'],
            seed=seed,
            sample_interval=cfg['sample_interval'],
            verbose=(i == 0),
        )
        runs.append(run_data)

    # 汇总
    summary = {
        'experiment': 'exp_76_threshold_diagnostic',
        'timestamp': timestamp,
        'description': '六阈值逐值诊断 — 定位 threshold_proximity=0 的根本原因',
        'config': cfg,
        'runs': [],
        'aggregate': {},
    }

    for i, run in enumerate(runs):
        d = run['diagnostic']
        ts = d['threshold_summary']
        run_summary = {
            'seed': d['seed'],
            'odi_final': d['odi_final'],
            'odi_max': d['odi_max'],
            'odi_above_05': d['odi_above_05_count'],
            'msi_max': d['msi_max'],
            'msi_nonzero_ratio': d['msi_nonzero_ratio'],
            'n_steps': d['n_steps_recorded'],
            'bottleneck': ts.get('bottleneck') if ts else None,
            'worst_gap': ts.get('worst_gap') if ts else None,
            'threshold_best': {},
            'threshold_met_frac': {},
        }
        if ts:
            for tid, tdata in ts.get('best_values', {}).items():
                run_summary['threshold_best'][tid] = {
                    'name': tdata['name'],
                    'value': tdata['value'],
                    'threshold': tdata['threshold'],
                    'is_met': tdata['is_met'],
                    'gap': tdata['gap'],
                }
            run_summary['threshold_met_frac'] = ts.get('met_fractions', {})
        summary['runs'].append(run_summary)

    # 聚合
    msi_max_vals = [r['msi_max'] for r in summary['runs']]
    odi_max_vals = [r['odi_max'] for r in summary['runs']]

    summary['aggregate'] = {
        'msi_max_mean': round(float(np.mean(msi_max_vals)), 4),
        'odi_max_mean': round(float(np.mean(odi_max_vals)), 4),
        'odi_above_05_total': sum(r['odi_above_05'] for r in summary['runs']),
    }

    # 保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    # 打印摘要
    print(f"\n{'='*60}")
    print(f"exp_76 六阈值诊断摘要")
    print(f"{'='*60}")
    for r in summary['runs']:
        print(f"\n  Seed {r['seed']}:")
        print(f"    ODI: final={r['odi_final']} max={r['odi_max']}")
        print(f"    ODI>0.5 steps: {r['odi_above_05']}")
        print(f"    MSI max: {r['msi_max']} nonzero={r['msi_nonzero_ratio']}")
        print(f"    瓶颈: {r['bottleneck']} (gap={r['worst_gap']})")
        print(f"    各阈值最佳值:")
        for tid, tdata in r['threshold_best'].items():
            status = 'PASS' if tdata['is_met'] else 'FAIL'
            print(f"      {status} {tid} {tdata['name']}: value={tdata['value']:.4f} / thresh={tdata['threshold']:.4f} gap={tdata['gap']:.4f}")
        print(f"    达标步数占比: {r['threshold_met_frac']}")

    print(f"\n结果文件: {output_file}")
    print(f"{'='*60}")

    return summary


if __name__ == '__main__':
    main()
