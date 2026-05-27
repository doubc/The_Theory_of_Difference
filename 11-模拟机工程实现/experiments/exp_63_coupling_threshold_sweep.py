"""
exp_63_coupling_threshold_sweep.py — Phase 3 实验三：耦合阈值扫描

目标：验证 exp_62 诊断结论——降低耦合阈值能否使前主体态收束达成。

实验设计：
  运行三组对比：
  A. 基线: coupling_threshold=0.3, mode=all  (原始配置)
  B. 低阈值: coupling_threshold=0.15, mode=all  (所有15对 > 0.15)
  C. 多数制: coupling_threshold=0.3, mode=majority (>=12/15 对 > 0.3)

  每组运行2次，取均值，减少随机波动影响。

理论依据：
  exp_62 证明六阈值本身不是瓶颈（封口后6/6全部达标），
  瓶颈在于耦合强度要求过严（15对全部 > 0.3）。
  本实验测试两种放松方式。

运行方式：
  python experiments/exp_63_coupling_threshold_sweep.py
"""

import sys
import os
import time
import json
from datetime import datetime
from copy import deepcopy

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.unsealing_mechanism import UnsealingMechanism
from engine.return_flow_channel import ReturnFlowChannel
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.seventh_threshold_detector import SeventhThresholdDetector
from engine.cooperative_emergence_detector import CooperativeEmergenceDetector
from engine.lateral_coupling import LateralCoupler
from engine.minimal_self_detector import MinimalSelfDetector
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine


def make_evolver(coupling_threshold=0.3, N0=48, steps_per_layer=200,
                 sample_interval=5, p1_eval_interval=1, device="cpu"):
    """创建配置好的 HierarchicalEvolver"""
    pbm = PersistentBiasMemory()
    cs = CumulativeSelector()
    six_td = SixThresholdDetector()
    psc = PreSubjectivityConvergence(coupling_threshold=coupling_threshold)
    um = UnsealingMechanism()
    rfc = ReturnFlowChannel()
    odi = OrganizationalDensityIndex()
    std = SeventhThresholdDetector()
    ced = CooperativeEmergenceDetector()
    lc = LateralCoupler()
    msd = MinimalSelfDetector()
    abe = AnticipatoryBiasEngine(memory=pbm)
    cfe = CounterfactualEngine()

    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=steps_per_layer,
        sample_interval=sample_interval,
        max_layers=1,
        p1_eval_interval=p1_eval_interval,
        device=device,
        persistent_bias_memory=pbm,
        cumulative_selector=cs,
        six_threshold_detector=six_td,
        pre_subjectivity_convergence=psc,
        unsealing_mechanism=um,
        return_flow_channel=rfc,
        organizational_density_index=odi,
        seventh_threshold_detector=std,
        cooperative_emergence_detector=ced,
        lateral_coupler=lc,
        minimal_self_detector=msd,
        anticipatory_bias_engine=abe,
        counterfactual_engine=cfe,
        phase2_verbose=False,
        phase3_verbose=False,
    )
    return evolver, psc


def extract_metrics(results, psc):
    """从演化结果中提取关键指标"""
    # ODI
    odi_values = []
    for entry in results.get('layer_results', [{}])[0].get('entries', []):
        odi_data = entry.get('odi', {})
        if isinstance(odi_data, dict):
            v = odi_data.get('value', odi_data.get('odi', None))
            if v is not None:
                odi_values.append(v)

    # 收敛历史
    conv_history = psc._convergence_history
    n_total = len(conv_history)
    n_converged = sum(1 for r in conv_history if r.converged)
    n_six_met = sum(1 for r in conv_history if r.six_thresholds_met)
    n_coupling_met = sum(1 for r in conv_history if r.coupling_strength_met)
    n_stability_met = sum(1 for r in conv_history if r.stability_met)
    n_fw_met = sum(1 for r in conv_history if r.semantic_firewall_passed)

    # 耦合统计
    avg_n_coupled = np.mean([r.n_coupled_pairs for r in conv_history]) if conv_history else 0
    avg_min_coupling = np.mean([r.min_coupling for r in conv_history]) if conv_history else 0
    max_n_coupled = max([r.n_coupled_pairs for r in conv_history]) if conv_history else 0

    # Phase 3
    p3 = results.get('phase3_summary', {})

    return {
        'n_evaluations': n_total,
        'n_converged': n_converged,
        'converged': n_converged > 0,
        'convergence_rate': n_converged / n_total if n_total > 0 else 0,
        'six_threshold_rate': n_six_met / n_total if n_total > 0 else 0,
        'coupling_rate': n_coupling_met / n_total if n_total > 0 else 0,
        'stability_rate': n_stability_met / n_total if n_total > 0 else 0,
        'firewall_rate': n_fw_met / n_total if n_total > 0 else 0,
        'avg_n_coupled': float(avg_n_coupled),
        'max_n_coupled': max_n_coupled,
        'avg_min_coupling': float(avg_min_coupling),
        'odi_max': float(max(odi_values)) if odi_values else 0.0,
        'odi_mean': float(np.mean(odi_values)) if odi_values else 0.0,
        'odi_final': float(odi_values[-1]) if odi_values else 0.0,
        'msi_max': p3.get('msi_max', 0.0),
        'anticipation_max': p3.get('anticipation_max', 0.0),
    }


def run_trial(config_name, coupling_threshold, N0=48, steps_per_layer=200,
              sample_interval=5, p1_eval_interval=1, n_runs=2, device="cpu"):
    """运行一组配置的多次试验"""
    print(f"\n{'='*60}")
    print(f"Config: {config_name} (coupling_threshold={coupling_threshold})")
    print(f"Running {n_runs} trials...")
    print(f"{'='*60}")

    all_metrics = []
    for run_idx in range(n_runs):
        print(f"\n  Run {run_idx+1}/{n_runs}...")
        evolver, psc = make_evolver(
            coupling_threshold=coupling_threshold,
            N0=N0, steps_per_layer=steps_per_layer,
            sample_interval=sample_interval, p1_eval_interval=p1_eval_interval,
            device=device,
        )
        t0 = time.time()
        results = evolver.run(verbose=False)
        elapsed = time.time() - t0

        metrics = extract_metrics(results, psc)
        metrics['elapsed'] = elapsed
        metrics['run'] = run_idx + 1
        all_metrics.append(metrics)

        print(f"    converged={metrics['converged']}, "
              f"6T={metrics['six_threshold_rate']*100:.1f}%, "
              f"coupling={metrics['coupling_rate']*100:.1f}%, "
              f"stability={metrics['stability_rate']*100:.1f}%, "
              f"ODI_max={metrics['odi_max']:.4f}, "
              f"avg_coupled={metrics['avg_n_coupled']:.1f}/15, "
              f"elapsed={elapsed:.1f}s")

    # 汇总
    summary = {
        'config': config_name,
        'coupling_threshold': coupling_threshold,
        'n_runs': n_runs,
        'n_converged': sum(1 for m in all_metrics if m['converged']),
        'avg_convergence_rate': float(np.mean([m['convergence_rate'] for m in all_metrics])),
        'avg_six_rate': float(np.mean([m['six_threshold_rate'] for m in all_metrics])),
        'avg_coupling_rate': float(np.mean([m['coupling_rate'] for m in all_metrics])),
        'avg_stability_rate': float(np.mean([m['stability_rate'] for m in all_metrics])),
        'avg_odi_max': float(np.mean([m['odi_max'] for m in all_metrics])),
        'avg_odi_final': float(np.mean([m['odi_final'] for m in all_metrics])),
        'avg_n_coupled': float(np.mean([m['avg_n_coupled'] for m in all_metrics])),
        'max_n_coupled_best': max(m['max_n_coupled'] for m in all_metrics),
        'avg_min_coupling': float(np.mean([m['avg_min_coupling'] for m in all_metrics])),
        'avg_elapsed': float(np.mean([m['elapsed'] for m in all_metrics])),
        'per_run': all_metrics,
    }

    return summary


def main():
    print("=" * 70)
    print("exp_63: Coupling Threshold Sweep")
    print("Testing whether lowering coupling threshold enables convergence")
    print("=" * 70)

    N0 = 48
    steps = 200
    sample_interval = 5
    p1_eval_interval = 1
    n_runs = 2
    device = "cpu"

    print(f"\nConfig: N0={N0}, steps={steps}, sample_interval={sample_interval}")
    print(f"p1_eval_interval={p1_eval_interval}, n_runs={n_runs}, device={device}")

    # ── 实验 A: 基线 (coupling_threshold=0.3) ──
    baseline = run_trial(
        "A_baseline_0.30", coupling_threshold=0.30,
        N0=N0, steps_per_layer=steps,
        sample_interval=sample_interval, p1_eval_interval=p1_eval_interval,
        n_runs=n_runs, device=device,
    )

    # ── 实验 B: 低阈值 (coupling_threshold=0.15) ──
    low_thresh = run_trial(
        "B_low_threshold_0.15", coupling_threshold=0.15,
        N0=N0, steps_per_layer=steps,
        sample_interval=sample_interval, p1_eval_interval=p1_eval_interval,
        n_runs=n_runs, device=device,
    )

    # ── 汇总对比 ──
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)

    configs = [baseline, low_thresh]
    header = f"{'Config':<25} {'Conv%':>6} {'6T%':>6} {'Cpl%':>6} {'Stb%':>6} {'ODI_max':>8} {'CplAvg':>7} {'MinCpl':>7}"
    print(header)
    print("-" * 70)
    for cfg in configs:
        print(f"{cfg['config']:<25} "
              f"{cfg['avg_convergence_rate']*100:>5.1f}% "
              f"{cfg['avg_six_rate']*100:>5.1f}% "
              f"{cfg['avg_coupling_rate']*100:>5.1f}% "
              f"{cfg['avg_stability_rate']*100:>5.1f}% "
              f"{cfg['avg_odi_max']:>8.4f} "
              f"{cfg['avg_n_coupled']:>6.1f}/15 "
              f"{cfg['avg_min_coupling']:>7.4f}")

    # 判定
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    base_conv = baseline['avg_convergence_rate']
    low_conv = low_thresh['avg_convergence_rate']
    base_coupling = baseline['avg_coupling_rate']
    low_coupling = low_thresh['avg_coupling_rate']

    if low_conv > base_conv:
        print(f"✅ 降低耦合阈值有效: convergence {base_conv*100:.1f}% -> {low_conv*100:.1f}%")
    elif low_coupling > base_coupling:
        print(f"🟡 耦合率改善但未收敛: coupling {base_coupling*100:.1f}% -> {low_coupling*100:.1f}%")
    else:
        print(f"❌ 降低阈值无改善")

    if baseline['avg_stability_rate'] < 0.5:
        print(f"⚠️  稳定性是另一个瓶颈: {baseline['avg_stability_rate']*100:.1f}%")

    # 保存报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        'experiment': 'exp_63_coupling_threshold_sweep',
        'timestamp': timestamp,
        'config': {
            'N0': N0, 'steps_per_layer': steps,
            'sample_interval': sample_interval, 'p1_eval_interval': p1_eval_interval,
            'n_runs': n_runs, 'device': device,
        },
        'results': {
            'A_baseline_0.30': {k: v for k, v in baseline.items() if k != 'per_run'},
            'B_low_threshold_0.15': {k: v for k, v in low_thresh.items() if k != 'per_run'},
        },
    }

    report_dir = os.path.join(PROJECT_ROOT, "docs", "experiments")
    os.makedirs(report_dir, exist_ok=True)
    json_path = os.path.join(report_dir, f"exp_63_coupling_sweep_{timestamp}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReport saved: {json_path}")

    return report


if __name__ == '__main__':
    report = main()