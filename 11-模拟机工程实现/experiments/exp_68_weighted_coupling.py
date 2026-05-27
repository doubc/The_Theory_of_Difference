"""
exp_68_weighted_coupling.py — 加权耦合实验

目标：测试 newly implemented weighted coupling mode 是否能进一步提升收敛率。

背景：
  - exp_65 表明多数制（≥12/15）不如全对制（PSC bug 修复后）
  - exp_67 确认耦合密度（CD）仍是最低子指数（0.55-0.66）
  - 耦合架构重设计文档（docs/coupling_architecture_redesign.md）提出 P0 方案：
    加权耦合——核心机制对（界面↔自维持、自维持↔保持、保持↔复制）权重 2.0，
    扩展三对权重 1.5，其余权重 1.0
  - PreSubjectivityConvergence 已实现 coupling_mode="weighted"

实验设计：
  A. 基线: all, threshold=0.30, N0=48, steps=200  (与 exp_63/65/67 直接对比)
  B. 多数制: majority, threshold=0.15, N0=48, steps=200  (exp_65 最佳)
  C. 加权: weighted, threshold=0.30, N0=48, steps=200  (P0 方案，默认阈值)
  D. 加权+低阈值: weighted, threshold=0.15, N0=48, steps=200  (P0 + 更低阈值)
  E. 加权+高容量: weighted, threshold=0.30, N0=72, steps=300  (P0 + 更多比特)

  每组运行4次，减少随机波动。

运行方式：
  python experiments/exp_68_weighted_coupling.py
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


def make_evolver(coupling_threshold=0.3, coupling_mode="all", N0=48,
                 steps_per_layer=200, sample_interval=5, p1_eval_interval=1,
                 device="cpu"):
    """创建配置好的 HierarchicalEvolver"""
    pbm = PersistentBiasMemory()
    cs = CumulativeSelector()
    six_td = SixThresholdDetector()
    psc = PreSubjectivityConvergence(
        coupling_threshold=coupling_threshold,
        coupling_mode=coupling_mode,
    )
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
    return evolver, psc, odi


def extract_metrics(results, psc, odi):
    """从演化结果中提取关键指标（含 ODI 子指数）"""
    # ODI 时间序列
    odi_values = []
    odi_subindices = {
        'threshold_proximity': [],
        'coupling_density': [],
        'stability_margin': [],
        'firewall_purity': [],
        'temporal_consistency': [],
        'cross_mechanism_resonance': [],
    }
    zone_distribution = {}

    layer_results = results.get('layer_results', [])
    for layer in layer_results:
        for step_result in layer.get('phase2_step_results', []):
            odi_data = step_result.get('odi', {})
            if isinstance(odi_data, dict):
                v = odi_data.get('value', odi_data.get('odi', None))
                if v is not None:
                    odi_values.append(v)
                    for key in odi_subindices:
                        sv = odi_data.get(key)
                        if sv is not None:
                            odi_subindices[key].append(sv)
                    zone = odi_data.get('zone', '')
                    if zone:
                        zone_distribution[zone] = zone_distribution.get(zone, 0) + 1

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

    # 收敛时间步
    convergence_steps = [r.timestamp for r in conv_history if r.converged]

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
        'convergence_steps': convergence_steps,
        'odi_max': float(max(odi_values)) if odi_values else 0.0,
        'odi_mean': float(np.mean(odi_values)) if odi_values else 0.0,
        'odi_final': float(odi_values[-1]) if odi_values else 0.0,
        'odi_median': float(np.median(odi_values)) if odi_values else 0.0,
        'odi_std': float(np.std(odi_values)) if odi_values else 0.0,
        'odi_subindices_mean': {
            k: float(np.mean(v)) if v else 0.0
            for k, v in odi_subindices.items()
        },
        'odi_subindices_max': {
            k: float(max(v)) if v else 0.0
            for k, v in odi_subindices.items()
        },
        'zone_distribution': zone_distribution,
        'msi_max': p3.get('msi_max', 0.0),
        'anticipation_max': p3.get('anticipation_max', 0.0),
    }


def run_trial(config_name, coupling_threshold, coupling_mode="all",
              N0=48, steps_per_layer=200, sample_interval=5,
              p1_eval_interval=1, n_runs=4, device="cpu"):
    """运行一组配置的多次试验"""
    print(f"\n{'='*60}")
    print(f"Config: {config_name}")
    print(f"  coupling_threshold={coupling_threshold}, mode={coupling_mode}, N0={N0}, steps={steps_per_layer}")
    print(f"Running {n_runs} trials...")
    print(f"{'='*60}")

    all_metrics = []
    for run_idx in range(n_runs):
        print(f"\n  Run {run_idx+1}/{n_runs}...")
        evolver, psc, odi = make_evolver(
            coupling_threshold=coupling_threshold,
            coupling_mode=coupling_mode,
            N0=N0, steps_per_layer=steps_per_layer,
            sample_interval=sample_interval, p1_eval_interval=p1_eval_interval,
            device=device,
        )
        t0 = time.time()
        results = evolver.run(verbose=False)
        elapsed = time.time() - t0

        metrics = extract_metrics(results, psc, odi)
        metrics['elapsed'] = elapsed
        metrics['run'] = run_idx + 1
        all_metrics.append(metrics)

        sub = metrics['odi_subindices_mean']
        print(f"    converged={metrics['converged']}, "
              f"conv_rate={metrics['convergence_rate']*100:.1f}%, "
              f"ODI_max={metrics['odi_max']:.4f}, "
              f"ODI_mean={metrics['odi_mean']:.4f}")
        print(f"    subindices: tp={sub['threshold_proximity']:.3f}, "
              f"cd={sub['coupling_density']:.3f}, "
              f"sm={sub['stability_margin']:.3f}, "
              f"fp={sub['firewall_purity']:.3f}, "
              f"tc={sub['temporal_consistency']:.3f}, "
              f"cr={sub['cross_mechanism_resonance']:.3f}")
        print(f"    avg_coupled={metrics['avg_n_coupled']:.1f}/15, "
              f"elapsed={elapsed:.1f}s")

    summary = {
        'config': config_name,
        'coupling_threshold': coupling_threshold,
        'coupling_mode': coupling_mode,
        'N0': N0,
        'steps_per_layer': steps_per_layer,
        'n_runs': n_runs,
        'n_converged': sum(1 for m in all_metrics if m['converged']),
        'avg_convergence_rate': float(np.mean([m['convergence_rate'] for m in all_metrics])),
        'avg_six_rate': float(np.mean([m['six_threshold_rate'] for m in all_metrics])),
        'avg_coupling_rate': float(np.mean([m['coupling_rate'] for m in all_metrics])),
        'avg_stability_rate': float(np.mean([m['stability_rate'] for m in all_metrics])),
        'avg_odi_max': float(np.mean([m['odi_max'] for m in all_metrics])),
        'avg_odi_mean': float(np.mean([m['odi_mean'] for m in all_metrics])),
        'avg_odi_median': float(np.mean([m['odi_median'] for m in all_metrics])),
        'avg_odi_std': float(np.mean([m['odi_std'] for m in all_metrics])),
        'avg_odi_final': float(np.mean([m['odi_final'] for m in all_metrics])),
        'avg_n_coupled': float(np.mean([m['avg_n_coupled'] for m in all_metrics])),
        'max_n_coupled_best': max(m['max_n_coupled'] for m in all_metrics),
        'avg_min_coupling': float(np.mean([m['avg_min_coupling'] for m in all_metrics])),
        'avg_elapsed': float(np.mean([m['elapsed'] for m in all_metrics])),
        'avg_subindices_mean': {
            k: float(np.mean([m['odi_subindices_mean'][k] for m in all_metrics]))
            for k in ['threshold_proximity', 'coupling_density', 'stability_margin',
                      'firewall_purity', 'temporal_consistency', 'cross_mechanism_resonance']
        },
        'per_run': all_metrics,
    }

    return summary


def main():
    print("=" * 70)
    print("exp_68: Weighted Coupling Experiment")
    print("Testing weighted coupling mode (P0 from architecture redesign)")
    print("=" * 70)

    sample_interval = 5
    p1_eval_interval = 1
    n_runs = 4
    device = "cpu"

    print(f"\nGlobal config: sample_interval={sample_interval}, p1_eval_interval={p1_eval_interval}")
    print(f"n_runs={n_runs}, device={device}")

    # ── 实验 A: 基线 (all, threshold=0.30, N0=48, steps=200) ──
    baseline = run_trial(
        "A_baseline_all_0.30_N48", coupling_threshold=0.30, coupling_mode="all",
        N0=48, steps_per_layer=200,
        sample_interval=sample_interval, p1_eval_interval=p1_eval_interval,
        n_runs=n_runs, device=device,
    )

    # ── 实验 B: 多数制最佳 (majority, threshold=0.15, N0=48, steps=200) ──
    majority = run_trial(
        "B_majority_0.15_N48", coupling_threshold=0.15, coupling_mode="majority",
        N0=48, steps_per_layer=200,
        sample_interval=sample_interval, p1_eval_interval=p1_eval_interval,
        n_runs=n_runs, device=device,
    )

    # ── 实验 C: 加权默认阈值 (weighted, threshold=0.30, N0=48, steps=200) ──
    weighted_default = run_trial(
        "C_weighted_0.30_N48", coupling_threshold=0.30, coupling_mode="weighted",
        N0=48, steps_per_layer=200,
        sample_interval=sample_interval, p1_eval_interval=p1_eval_interval,
        n_runs=n_runs, device=device,
    )

    # ── 实验 D: 加权+低阈值 (weighted, threshold=0.15, N0=48, steps=200) ──
    weighted_low = run_trial(
        "D_weighted_0.15_N48", coupling_threshold=0.15, coupling_mode="weighted",
        N0=48, steps_per_layer=200,
        sample_interval=sample_interval, p1_eval_interval=p1_eval_interval,
        n_runs=n_runs, device=device,
    )

    # ── 实验 E: 加权+高容量 (weighted, threshold=0.30, N0=72, steps=300) ──
    weighted_high = run_trial(
        "E_weighted_0.30_N72", coupling_threshold=0.30, coupling_mode="weighted",
        N0=72, steps_per_layer=300,
        sample_interval=sample_interval, p1_eval_interval=p1_eval_interval,
        n_runs=n_runs, device=device,
    )

    # ── 汇总对比 ──
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)

    configs = [baseline, majority, weighted_default, weighted_low, weighted_high]
    header = (f"{'Config':<35} {'Conv%':>6} {'6T%':>6} {'Cpl%':>6} "
              f"{'Stb%':>6} {'ODI_max':>8} {'ODI_mean':>8} {'CplAvg':>7}")
    print(header)
    print("-" * 85)
    for cfg in configs:
        print(f"{cfg['config']:<35} "
              f"{cfg['avg_convergence_rate']*100:>5.1f}% "
              f"{cfg['avg_six_rate']*100:>5.1f}% "
              f"{cfg['avg_coupling_rate']*100:>5.1f}% "
              f"{cfg['avg_stability_rate']*100:>5.1f}% "
              f"{cfg['avg_odi_max']:>8.4f} "
              f"{cfg['avg_odi_mean']:>8.4f} "
              f"{cfg['avg_n_coupled']:>6.1f}/15")

    # 子指数对比
    print("\n" + "=" * 70)
    print("ODI SUB-INDEX COMPARISON (mean)")
    print("=" * 70)

    sub_keys = ['threshold_proximity', 'coupling_density', 'stability_margin',
                'firewall_purity', 'temporal_consistency', 'cross_mechanism_resonance']
    sub_labels = ['TP', 'CD', 'SM', 'FP', 'TC', 'CR']
    header2 = f"{'Config':<35}" + "".join(f"{l:>8}" for l in sub_labels)
    print(header2)
    print("-" * 85)
    for cfg in configs:
        vals = cfg['avg_subindices_mean']
        line = f"{cfg['config']:<35}"
        for k in sub_keys:
            line += f"{vals[k]:>8.4f}"
        print(line)

    # 判定
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    best = max(configs, key=lambda c: c['avg_convergence_rate'])
    print(f"  Best config: {best['config']} (conv={best['avg_convergence_rate']*100:.1f}%)")

    # 加权 vs 基线
    base_conv = baseline['avg_convergence_rate']
    wdef_conv = weighted_default['avg_convergence_rate']
    wlow_conv = weighted_low['avg_convergence_rate']
    whigh_conv = weighted_high['avg_convergence_rate']
    maj_conv = majority['avg_convergence_rate']

    print(f"\n  [WEIGHTED vs BASELINE]")
    print(f"    baseline (all, 0.30):        {base_conv*100:.1f}%")
    print(f"    majority (0.15):             {maj_conv*100:.1f}%")
    print(f"    weighted (0.30):             {wdef_conv*100:.1f}%")
    print(f"    weighted (0.15):             {wlow_conv*100:.1f}%")
    print(f"    weighted (0.30, N72):        {whigh_conv*100:.1f}%")

    if wdef_conv > base_conv:
        print(f"    [OK] 加权(0.30) 优于基线: {base_conv*100:.1f}% -> {wdef_conv*100:.1f}%")
    else:
        print(f"    [??] 加权(0.30) 未优于基线: {base_conv*100:.1f}% -> {wdef_conv*100:.1f}%")

    if wlow_conv > maj_conv:
        print(f"    [OK] 加权(0.15) 优于多数制(0.15): {maj_conv*100:.1f}% -> {wlow_conv*100:.1f}%")
    else:
        print(f"    [??] 加权(0.15) 未优于多数制(0.15): {maj_conv*100:.1f}% -> {wlow_conv*100:.1f}%")

    # 耦合密度子指数对比
    print(f"\n  [COUPLING DENSITY] 子指数对比:")
    for cfg in configs:
        cd = cfg['avg_subindices_mean']['coupling_density']
        bar = '█' * int(cd * 40)
        print(f"    {cfg['config']:<35} CD={cd:.4f} {bar}")

    # 与历史对比
    print(f"\n  [HISTORY] 与历史实验对比:")
    print(f"    exp_63 基线 (all, 0.30):       ~10.0%")
    print(f"    exp_65 多数制 (0.15):          ~33.1%")
    print(f"    exp_67 基线 (all, 0.30):       {base_conv*100:.1f}% (复现)")
    print(f"    exp_68 加权 (0.30):            {wdef_conv*100:.1f}% (新)")
    print(f"    exp_68 加权 (0.15):            {wlow_conv*100:.1f}% (新)")
    print(f"    exp_68 加权 (0.30, N72):       {whigh_conv*100:.1f}% (新)")

    # 保存报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        'experiment': 'exp_68_weighted_coupling',
        'timestamp': timestamp,
        'description': '加权耦合模式实验 (P0 from architecture redesign)',
        'config': {
            'sample_interval': sample_interval, 'p1_eval_interval': p1_eval_interval,
            'n_runs': n_runs, 'device': device,
        },
        'results': {
            'A_baseline_all_0.30_N48': {k: v for k, v in baseline.items() if k != 'per_run'},
            'B_majority_0.15_N48': {k: v for k, v in majority.items() if k != 'per_run'},
            'C_weighted_0.30_N48': {k: v for k, v in weighted_default.items() if k != 'per_run'},
            'D_weighted_0.15_N48': {k: v for k, v in weighted_low.items() if k != 'per_run'},
            'E_weighted_0.30_N72': {k: v for k, v in weighted_high.items() if k != 'per_run'},
        },
    }

    report_dir = os.path.join(PROJECT_ROOT, "docs", "experiments")
    os.makedirs(report_dir, exist_ok=True)
    json_path = os.path.join(report_dir, f"exp_68_weighted_coupling_{timestamp}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReport saved: {json_path}")

    return report


if __name__ == '__main__':
    report = main()
