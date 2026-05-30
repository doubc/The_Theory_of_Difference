"""experiments/exp_75_return_flow_integration_800steps.py

Phase 3 实验五：回流通道集成 + 800步长演化

Purpose:
  1. 将 ReturnFlowChannel 正式集成到 HierarchicalEvolver 中
  2. 运行 800 步长演化，观察 ODI 是否稳定突破 0.5
  3. 验证 self_reference 条件是否因回流通道激活而变为 True
  4. 六阈值详细诊断：定位 ODI 瓶颈子指数

关键修复：
  - 在 exp_74 中 ReturnFlowChannel 从未被实例化 → self_reference 永远为 0
  - 本实验显式创建 ReturnFlowChannel 并传入 HierarchicalEvolver
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Dict, List

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


# ─── Six-Threshold Diagnostic ───

def six_threshold_diagnostic(step_results: List[Dict]) -> Dict:
    """对六阈值检测结果进行详细诊断，定位瓶颈。"""
    if not step_results:
        return {"error": "No step results available"}

    last = step_results[-1]
    threshold_data = last.get('thresholds', {})

    diagnostic = {
        'thresholds': {},
        'bottleneck': None,
        'bottleneck_gap': 1.0,
    }

    threshold_names = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']

    for i, name in enumerate(threshold_names):
        key = f'threshold_{i}'
        if key in threshold_data:
            td = threshold_data[key]
            value = td.get('value', 0.0)
            threshold_val = td.get('threshold', 0.0)
            passed = value >= threshold_val
            gap = threshold_val - value if not passed else 0.0
            diagnostic['thresholds'][name] = {
                'value': round(float(value), 4),
                'threshold': round(float(threshold_val), 4),
                'passed': passed,
                'gap': round(float(gap), 4),
            }
            if not passed and gap > diagnostic['bottleneck_gap'] - 0.001:
                # Track the largest gap (biggest shortfall)
                if gap > 0:
                    diagnostic['bottleneck'] = name
                    diagnostic['bottleneck_gap'] = gap

    # ODI sub-indices (stored as flat keys in evolver, not nested under 'sub_indices')
    odi_data = last.get('odi', {})
    sub_indices = odi_data.get('sub_indices', {})
    if not sub_indices:
        # Fallback: extract from flat keys
        sub_indices = {
            'threshold_proximity': odi_data.get('threshold_proximity', 0.0),
            'coupling_density': odi_data.get('coupling_density', 0.0),
            'stability_margin': odi_data.get('stability_margin', 0.0),
            'firewall_purity': odi_data.get('firewall_purity', 0.0),
            'temporal_consistency': odi_data.get('temporal_consistency', 0.0),
            'cross_mechanism_resonance': odi_data.get('cross_mechanism_resonance', 0.0),
        }
    diagnostic['odi_sub_indices'] = {}
    for key, val in sub_indices.items():
        diagnostic['odi_sub_indices'][key] = round(float(val), 4)

    return diagnostic


# ─── Single Run with ReturnFlowChannel ───

def run_with_return_flow(
    N0: int,
    steps: int,
    seed: int,
    sample_interval: int = 5,
    p1_eval_interval: int = 5,
    verbose: bool = True,
) -> Dict:
    """运行单次演化，集成 ReturnFlowChannel。"""

    torch.manual_seed(seed)
    np.random.seed(seed)

    # 创建 ReturnFlowChannel
    # 降低 anchor_threshold 至 0.05，因为 per-mechanism coupling 值较小
    # (binding 均匀分配到 6 个机制，典型 binding=0.3 → per_mech=0.05)
    return_flow_channel = ReturnFlowChannel(
        anchor_threshold=0.05,
        decay_rate=0.01,
        min_retention_steps=10,
    )

    # 创建 UnsealingMechanism（降低 L1 阈值以更早触发解封）
    unsealing_mechanism = UnsealingMechanism(
        l1_coupling_threshold=0.20,
        l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40,
        l2_stability_threshold=0.55,
    )

    # 创建 PreSubjectivityConvergence
    pre_subjectivity = PreSubjectivityConvergence(
        coupling_threshold=0.25,
        stability_threshold=0.40,
        dynamic_threshold=True,
    )

    # 创建 ODI
    odi = OrganizationalDensityIndex(
        temporal_window=10,
        densification_threshold=0.005,
        use_refined_zones=True,
    )

    # 创建 MSI 检测器（降低阈值）
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

    # 创建 GlobalBiasConstraint
    gbc = GlobalBiasConstraint(
        coherence_threshold=0.5,
        balance_threshold=0.3,
        min_mechanisms_required=4,
        geometric_weighting=True,
    )

    # 创建 NarrativeRecursionOperator（降低过滤阈值）
    narrative = NarrativeRecursionOperator(
        bias_dimension=128,
        filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1,
        verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9,
    )

    # 创建 AnticipatoryBiasEngine 和 CounterfactualEngine (Phase 3)
    anticipatory = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01},
    )
    counterfactual = CounterfactualEngine(config={
        'divergence_threshold': 0.1,
        'max_branches': 4,
    })

    # 创建 HierarchicalEvolver
    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=steps,
        sample_interval=sample_interval,
        max_layers=1,
        p1_eval_interval=p1_eval_interval,
        phase2_verbose=verbose,
        phase3_verbose=verbose,
        # Phase 2 P0 组件
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        # Phase 2 P1 组件
        organizational_density_index=odi,
        # 解封与回流
        unsealing_mechanism=unsealing_mechanism,
        return_flow_channel=return_flow_channel,  # ← 关键：传入回流通道
        pre_subjectivity_convergence=pre_subjectivity,
        # Phase 3 组件
        minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory,
        counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative,
        global_bias_constraint=gbc,
    )

    print(f"\n{'='*60}")
    print(f"Run: N={N0}, steps={steps}, seed={seed}")
    print(f"  seal: L1_coupling=0.20, L1_stability=0.35")
    print(f"  MSI: odi_thresh=0.35, self_ref_thresh=0.05, min_cond=1")
    print(f"  Narrative: filter_thresh=0.02")
    print(f"  ReturnFlowChannel: anchor_thresh=0.2, decay=0.01 — ACTIVE")
    print(f"{'='*60}")

    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start

    print(f"\nEvolution completed in {elapsed:.1f}s")

    # 提取六阈值诊断
    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])
    diagnostic = six_threshold_diagnostic(step_results)

    # 提取 MSI/ODI/叙事数据
    msi_values = []
    odi_values = []
    narrative_values = []

    for entry in step_results:
        msi_values.append(entry.get('minimal_self', {}).get('msi', 0.0))
        odi_values.append(entry.get('odi', {}).get('value', 0.0))
        narrative_values.append(
            entry.get('narrative_recursion', {}).get('correction_norm', 0.0)
        )

    return_flow_events = evolver.get_return_flow_events()

    # MSI 分析
    msi_arr = np.array(msi_values)
    msi_nonzero = np.sum(msi_arr > 0)
    msi_max = float(np.max(msi_arr))
    msi_final = float(msi_arr[-1]) if len(msi_arr) > 0 else 0.0
    msi_emergence_events = int(np.sum(msi_arr >= 0.04))

    # ODI 分析
    odi_arr = np.array(odi_values)
    odi_max = float(np.max(odi_arr))
    odi_final = float(odi_arr[-1]) if len(odi_arr) > 0 else 0.0
    odi_mean = float(np.mean(odi_arr))
    odi_above_05 = int(np.sum(odi_arr >= 0.5))

    # 叙事分析
    narrative_arr = np.array(narrative_values)
    narrative_activations = int(np.sum(narrative_arr > 0))
    narrative_max = float(np.max(narrative_arr))

    # MSI 三条件详情（最后一步）
    last_msi = step_results[-1].get('minimal_self', {}) if step_results else {}
    msi_conditions = {
        'asymmetry_detected': last_msi.get('asymmetry', {}).get('detected', False),
        'asymmetry_index': last_msi.get('asymmetry', {}).get('asymmetry_index', 0.0),
        'history_detected': last_msi.get('history_dependency', {}).get('detected', False),
        'history_index': last_msi.get('history_dependency', {}).get('dependency_index', 0.0),
        'self_ref_detected': last_msi.get('self_reference', {}).get('detected', False),
        'self_ref_strength': last_msi.get('self_reference', {}).get('reference_strength', 0.0),
        'active_conditions': last_msi.get('n_active_conditions', 0),
    }

    analysis = {
        'msi': {
            'final': round(msi_final, 4),
            'max': round(msi_max, 4),
            'mean': round(float(np.mean(msi_arr)), 4),
            'nonzero_steps': int(msi_nonzero),
            'total_steps': len(msi_arr),
            'emergence_events': msi_emergence_events,
            'conditions': msi_conditions,
        },
        'odi': {
            'final': round(odi_final, 4),
            'max': round(odi_max, 4),
            'mean': round(odi_mean, 4),
            'above_05_steps': odi_above_05,
        },
        'narrative': {
            'activations': narrative_activations,
            'max': round(narrative_max, 4),
        },
        'return_flow': {
            'events_total': len(return_flow_events),
            'anchored': sum(1 for e in return_flow_events if getattr(e, 'success', False)),
            'detached': sum(1 for e in return_flow_events if not getattr(e, 'success', True)),
        },
        'six_threshold_diagnostic': diagnostic,
        'elapsed_seconds': round(elapsed, 1),
    }

    return {
        'result': result,
        'analysis': analysis,
        'config': {
            'N0': N0,
            'steps': steps,
            'seed': seed,
            'l1_coupling_threshold': 0.20,
            'l1_stability_threshold': 0.35,
            'msi_odi_threshold': 0.35,
            'msi_self_ref_threshold': 0.05,
            'narrative_filter_threshold': 0.02,
            'return_flow_active': True,
        },
    }


# ─── Main ───

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(
        os.path.dirname(__file__),
        f'exp_75_results_{timestamp}.json'
    )

    print(f"exp_75: ReturnFlowChannel 集成 + 800步长演化")
    print(f"Output: {output_file}")

    # 配置：800步长演化 + 降低密封率
    cfg = {
        'N0': 72,
        'steps': 800,
        'sample_interval': 5,
        'p1_eval_interval': 5,
    }

    # 运行 3 次
    runs = []
    for i in range(3):
        seed = 42 + i * 100
        run_result = run_with_return_flow(
            N0=cfg['N0'],
            steps=cfg['steps'],
            seed=seed,
            sample_interval=cfg['sample_interval'],
            p1_eval_interval=cfg['p1_eval_interval'],
            verbose=(i == 0),
        )
        runs.append(run_result)

    # 汇总
    summary = {
        'experiment': 'exp_75_return_flow_integration_800steps',
        'timestamp': timestamp,
        'description': '回流通道集成 + 800步演化 + 六阈值诊断',
        'config': cfg,
        'runs': [],
        'aggregate': {},
    }

    for i, run in enumerate(runs):
        a = run['analysis']
        summary['runs'].append({
            'seed': 42 + i * 100,
            'msi_final': a['msi']['final'],
            'msi_max': a['msi']['max'],
            'msi_nonzero_ratio': round(a['msi']['nonzero_steps'] / a['msi']['total_steps'], 3),
            'msi_emergence_events': a['msi']['emergence_events'],
            'msi_conditions': a['msi']['conditions'],
            'odi_final': a['odi']['final'],
            'odi_max': a['odi']['max'],
            'odi_mean': a['odi']['mean'],
            'odi_above_05_steps': a['odi']['above_05_steps'],
            'narrative_activations': a['narrative']['activations'],
            'narrative_max': a['narrative']['max'],
            'return_flow_events': a['return_flow']['events_total'],
            'return_flow_anchored': a['return_flow']['anchored'],
            'bottleneck': a['six_threshold_diagnostic'].get('bottleneck'),
            'odi_sub_indices': a['six_threshold_diagnostic'].get('odi_sub_indices', {}),
        })

    # 聚合统计
    msi_max_vals = [r['analysis']['msi']['max'] for r in runs]
    odi_max_vals = [r['analysis']['odi']['max'] for r in runs]
    narrative_activations = [r['analysis']['narrative']['activations'] for r in runs]
    return_flow_events = [r['analysis']['return_flow']['events_total'] for r in runs]
    self_ref_activated = [
        r['analysis']['msi']['conditions']['self_ref_detected'] for r in runs
    ]

    summary['aggregate'] = {
        'msi_max_mean': round(float(np.mean(msi_max_vals)), 4),
        'msi_max_std': round(float(np.std(msi_max_vals)), 4),
        'odi_max_mean': round(float(np.mean(odi_max_vals)), 4),
        'odi_above_05_total': sum(r['analysis']['odi']['above_05_steps'] for r in runs),
        'narrative_activations_total': sum(narrative_activations),
        'return_flow_events_total': sum(return_flow_events),
        'self_reference_activated_count': sum(1 for s in self_ref_activated if s),
        'acceptance': {
            'msi_activated': any(m > 0 for m in msi_max_vals),
            'odi_breaks_05': any(o > 0.5 for o in odi_max_vals),
            'narrative_active': any(n > 0 for n in narrative_activations),
            'return_flow_working': any(e > 0 for e in return_flow_events),
            'self_reference_detected': any(self_ref_activated),
        },
    }

    # 保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    # 打印摘要
    print(f"\n{'='*60}")
    print(f"exp_75 结果摘要")
    print(f"{'='*60}")
    for i, r in enumerate(summary['runs']):
        print(f"\n  Run {i+1} (seed={r.get('seed', 'N/A')}):")
        print(f"    MSI: final={r['msi_final']} max={r['msi_max']} "
              f"nonzero={r['msi_nonzero_ratio']} emergence={r['msi_emergence_events']}")
        cond = r['msi_conditions']
        print(f"    MSI conditions: asym={cond['asymmetry_detected']} "
              f"hist={cond['history_detected']} self_ref={cond['self_ref_detected']} "
              f"({cond['active_conditions']}/3)")
        print(f"    ODI: final={r['odi_final']} max={r['odi_max']} "
              f"mean={r['odi_mean']} above_05={r['odi_above_05_steps']}")
        print(f"    Narrative: activations={r['narrative_activations']} max={r['narrative_max']}")
        print(f"    ReturnFlow: events={r['return_flow_events']} anchored={r['return_flow_anchored']}")
        print(f"    Bottleneck: {r['bottleneck']}")

    acc = summary['aggregate']['acceptance']
    print(f"\n{'='*60}")
    print(f"接受标准:")
    print(f"  MSI 激活: {acc['msi_activated']}")
    print(f"  ODI 突破 0.5: {acc['odi_breaks_05']}")
    print(f"  叙事激活: {acc['narrative_active']}")
    print(f"  回流通道工作: {acc['return_flow_working']}")
    print(f"  自参照检测: {acc['self_reference_detected']}")
    print(f"\n结果文件: {output_file}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
