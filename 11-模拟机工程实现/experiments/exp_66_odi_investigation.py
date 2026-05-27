"""
exp_66_odi_investigation.py — ODI=0 根因调查

目标：精确诊断 ODI 始终为 0 的原因，定位是理论正确结果还是实现缺陷。

假设：
  H1: coupling_matrix 为 None（active_count < 2 或 constraints 无 direction）
  H2: stability_score 为 None（self_sustaining <= 0）
  H3: threshold_result 为 None（locals().get 失败）
  H4: 六阈值全部不达标 → threshold_proximity ≈ 0
  H5: 以上综合导致加权 ODI < 0.05（数值零）

实验设计：
  在 HierarchicalEvolver 的 P1 回调中注入 ODI 子指数探针，
  记录每一步的六个子指数值，确定哪个子指数是主要瓶颈。

运行方式：
  python experiments/exp_66_odi_investigation.py
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


def make_evolver_with_odi_probe(N0=48, steps_per_layer=200, sample_interval=5,
                                  p1_eval_interval=1, device="cpu"):
    """创建带 ODI 探针的 HierarchicalEvolver"""

    pbm = PersistentBiasMemory()
    cs = CumulativeSelector()
    six_td = SixThresholdDetector()
    psc = PreSubjectivityConvergence(
        coupling_threshold=0.15,
        coupling_mode="majority",
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

    return evolver, odi, psc


def run_with_probe(N0=48, steps=200, sample_interval=5, p1_eval_interval=1,
                   device="cpu", seed=42):
    """运行一次实验，收集 ODI 子指数数据"""
    torch.manual_seed(seed)
    np.random.seed(seed)

    evolver, odi, psc = make_evolver_with_odi_probe(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        p1_eval_interval=p1_eval_interval, device=device,
    )

    # 运行
    t0 = time.time()
    results = evolver.run(verbose=False)
    elapsed = time.time() - t0

    # 收集 ODI 历史
    odi_history = odi._odi_history
    result_history = odi._result_history

    # 收集收敛历史
    conv_history = psc._convergence_history

    # 分析 ODI 子指数
    subindex_data = []
    for r in result_history:
        entry = {
            'step': r.timestamp,
            'odi': r.odi,
            'zone': r.zone,
            'subindices': {
                'threshold_proximity': r.subindices.threshold_proximity,
                'coupling_density': r.subindices.coupling_density,
                'stability_margin': r.subindices.stability_margin,
                'firewall_purity': r.subindices.firewall_purity,
                'temporal_consistency': r.subindices.temporal_consistency,
                'cross_mechanism_resonance': r.subindices.cross_mechanism_resonance,
            },
            'densification_rate': r.densification_rate,
            'is_densifying': r.is_densifying,
        }
        subindex_data.append(entry)

    # 分析收敛数据
    convergence_data = []
    for r in conv_history:
        convergence_data.append({
            'step': r.timestamp,
            'converged': r.converged,
            'six_thresholds_met': r.six_thresholds_met,
            'coupling_strength_met': r.coupling_strength_met,
            'stability_met': r.stability_met,
            'n_coupled_pairs': r.n_coupled_pairs,
            'stability_score': r.stability_score,
        })

    # 从 layer_results 中提取 ODI 值（验证一致性）
    layer_results = results.get('layer_results', [])
    odi_from_results = []
    if layer_results:
        for entry in layer_results[0].get('entries', []):
            odi_data = entry.get('odi', {})
            if isinstance(odi_data, dict):
                v = odi_data.get('value', None)
                if v is not None:
                    odi_from_results.append(v)

    return {
        'elapsed': elapsed,
        'odi_history': odi_history,
        'subindex_data': subindex_data,
        'convergence_data': convergence_data,
        'odi_from_results': odi_from_results,
        'odi_max': float(max(odi_history)) if odi_history else 0.0,
        'odi_mean': float(np.mean(odi_history)) if odi_history else 0.0,
        'odi_final': float(odi_history[-1]) if odi_history else 0.0,
        'n_converged': sum(1 for r in conv_history if r.converged),
        'n_total_eval': len(conv_history),
    }


def analyze_subindices(data):
    """分析六个子指数的统计特征"""
    subindex_names = [
        'threshold_proximity', 'coupling_density', 'stability_margin',
        'firewall_purity', 'temporal_consistency', 'cross_mechanism_resonance'
    ]
    weights = {
        'threshold_proximity': 0.30,
        'coupling_density': 0.20,
        'stability_margin': 0.20,
        'firewall_purity': 0.10,
        'temporal_consistency': 0.10,
        'cross_mechanism_resonance': 0.10,
    }

    analysis = {}
    for name in subindex_names:
        values = [d['subindices'][name] for d in data]
        analysis[name] = {
            'mean': float(np.mean(values)),
            'std': float(np.std(values)),
            'min': float(np.min(values)),
            'max': float(np.max(values)),
            'median': float(np.median(values)),
            'n_zero': sum(1 for v in values if v < 1e-8),
            'n_nonzero': sum(1 for v in values if v >= 1e-8),
            'weight': weights[name],
            'weighted_mean': float(np.mean(values)) * weights[name],
        }

    return analysis


def main():
    print("=" * 70)
    print("exp_66: ODI=0 Root Cause Investigation")
    print("=" * 70)

    N0 = 48
    steps = 200
    sample_interval = 5
    p1_eval_interval = 1
    device = "cpu"
    n_seeds = 3

    print(f"\nConfig: N0={N0}, steps={steps}, sample_interval={sample_interval}")
    print(f"p1_eval_interval={p1_eval_interval}, n_seeds={n_seeds}, device={device}")

    all_runs = []
    for seed in range(n_seeds):
        print(f"\n{'─'*50}")
        print(f"Seed {seed} (seed_value={seed*17+42})...")
        data = run_with_probe(
            N0=N0, steps=steps, sample_interval=sample_interval,
            p1_eval_interval=p1_eval_interval, device=device,
            seed=seed * 17 + 42,
        )
        all_runs.append(data)

        print(f"  elapsed={data['elapsed']:.1f}s")
        print(f"  ODI: max={data['odi_max']:.6f}, mean={data['odi_mean']:.6f}, final={data['odi_final']:.6f}")
        print(f"  Convergence: {data['n_converged']}/{data['n_total_eval']}")

        if data['subindex_data']:
            analysis = analyze_subindices(data['subindex_data'])
            print(f"\n  Subindex Analysis (seed={seed}):")
            print(f"  {'Subindex':<30} {'Mean':>8} {'Std':>8} {'Min':>8} {'Max':>8} {'Wt':>6} {'W*Mean':>8} {'n_zero':>7}")
            print(f"  {'─'*90}")
            total_weighted = 0.0
            for name, stats in analysis.items():
                short_name = name[:28]
                print(f"  {short_name:<30} {stats['mean']:>8.4f} {stats['std']:>8.4f} "
                      f"{stats['min']:>8.4f} {stats['max']:>8.4f} "
                      f"{stats['weight']:>6.2f} {stats['weighted_mean']:>8.4f} "
                      f"{stats['n_zero']:>5}/{len(data['subindex_data'])}")
                total_weighted += stats['weighted_mean']
            print(f"  {'─'*90}")
            print(f"  {'TOTAL WEIGHTED ODI (expected)':<30} {total_weighted:>8.4f}")

    # ── 跨种子汇总 ──
    print(f"\n{'='*70}")
    print("CROSS-SEED SUMMARY")
    print(f"{'='*70}")

    print(f"\n{'Seed':>6} {'ODI_max':>10} {'ODI_mean':>10} {'ODI_final':>10} {'Conv':>6} {'Eval':>6}")
    print(f"{'─'*50}")
    for i, data in enumerate(all_runs):
        print(f"{i:>6} {data['odi_max']:>10.6f} {data['odi_mean']:>10.6f} "
              f"{data['odi_final']:>10.6f} {data['n_converged']:>6} {data['n_total_eval']:>6}")

    # ── 诊断结论 ──
    print(f"\n{'='*70}")
    print("DIAGNOSIS")
    print(f"{'='*70}")

    # 使用第一个有子指数数据的运行
    for data in all_runs:
        if data['subindex_data']:
            analysis = analyze_subindices(data['subindex_data'])
            break
    else:
        analysis = {}

    if analysis:
        # 找出主要瓶颈（加权贡献最小的子指数）
        bottleneck = min(analysis.items(), key=lambda x: x[1]['weighted_mean'])
        print(f"\n  Primary bottleneck: {bottleneck[0]}")
        print(f"    Mean value: {bottleneck[1]['mean']:.6f}")
        print(f"    Weight: {bottleneck[1]['weight']}")
        print(f"    Weighted contribution: {bottleneck[1]['weighted_mean']:.6f}")
        print(f"    n_zero: {bottleneck[1]['n_zero']}/{len(data['subindex_data'])}")

        # 检查每个假设
        print(f"\n  Hypothesis Testing:")

        # H1: coupling_matrix is None
        cp = analysis['coupling_density']
        h1 = cp['mean'] < 0.01
        print(f"    H1 (coupling_matrix=None): {'CONFIRMED' if h1 else 'REJECTED'}")
        print(f"      coupling_density mean={cp['mean']:.6f}, n_zero={cp['n_zero']}")

        # H2: stability_score is None
        sm = analysis['stability_margin']
        h2 = sm['mean'] < 0.01
        print(f"    H2 (stability_score=None): {'CONFIRMED' if h2 else 'REJECTED'}")
        print(f"      stability_margin mean={sm['mean']:.6f}, n_zero={sm['n_zero']}")

        # H3: threshold_result is None
        tp = analysis['threshold_proximity']
        h3 = tp['mean'] < 0.01
        print(f"    H3 (threshold_result=None): {'CONFIRMED' if h3 else 'REJECTED'}")
        print(f"      threshold_proximity mean={tp['mean']:.6f}, n_zero={tp['n_zero']}")

        # H4: six thresholds not all met
        h4 = tp['mean'] < 0.5
        print(f"    H4 (six thresholds not met): {'CONFIRMED' if h4 else 'REJECTED'}")
        print(f"      threshold_proximity mean={tp['mean']:.6f} (low = thresholds not met)")

        # 综合诊断
        print(f"\n  Overall Diagnosis:")
        confirmed = []
        if h1: confirmed.append("coupling_matrix=None (H1)")
        if h2: confirmed.append("stability_score=None (H2)")
        if h3: confirmed.append("threshold_result=None (H3)")
        if h4: confirmed.append("six thresholds not met (H4)")

        if confirmed:
            print(f"    Root causes: {', '.join(confirmed)}")
        else:
            print(f"    All basic hypotheses rejected — ODI=0 may be theoretically correct")

        # 理论评估
        print(f"\n  Theoretical Assessment:")
        if h4:
            print(f"    ODI=0 is THEORETICALLY CORRECT when six thresholds are not all met.")
            print(f"    Per 象界: '存在 ≠ 呈象' — structure must cross all six thresholds")
            print(f"    before ODI can be non-zero.")
            print(f"    The coupling bottleneck (exp_63-65) is the real issue to solve.")
        elif h1 or h2 or h3:
            print(f"    ODI=0 is partly an IMPLEMENTATION BUG.")
            print(f"    Missing inputs to ODI.compute() artificially suppress the index.")
            print(f"    Fix: ensure coupling_matrix and stability_score are always provided.")

    # 保存报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        'experiment': 'exp_66_odi_investigation',
        'timestamp': timestamp,
        'config': {
            'N0': N0, 'steps_per_layer': steps,
            'sample_interval': sample_interval, 'p1_eval_interval': p1_eval_interval,
            'n_seeds': n_seeds, 'device': device,
        },
        'runs': [
            {
                'seed': i,
                'odi_max': data['odi_max'],
                'odi_mean': data['odi_mean'],
                'odi_final': data['odi_final'],
                'n_converged': data['n_converged'],
                'n_total_eval': data['n_total_eval'],
                'elapsed': data['elapsed'],
                'n_subindex_entries': len(data['subindex_data']),
                'subindex_data': data['subindex_data'],
                'convergence_data': data['convergence_data'],
            }
            for i, data in enumerate(all_runs)
        ],
    }

    report_dir = os.path.join(PROJECT_ROOT, "docs", "experiments")
    os.makedirs(report_dir, exist_ok=True)
    json_path = os.path.join(report_dir, f"exp_66_odi_investigation_{timestamp}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReport saved: {json_path}")

    return report


if __name__ == '__main__':
    report = main()
