"""
exp_62_six_threshold_diagnostic.py — 六阈值瓶颈诊断

目标：精确测量每个阈值的实际值，找出哪个阈值是瓶颈，以及为什么。

关键问题：
- 哪个阈值持续不达标？
- 该阈值的实际值与目标值差距多大？
- 输入参数（active_count, bias_depth, variant_probs 等）是否合理？
- 是参数问题还是阈值设置过严？

运行方式：
  直接运行，输出详细的逐阈值分析报告
"""

import sys
import os
import json
import time
from datetime import datetime

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


def run_diagnostic(
    N0: int = 48,
    steps_per_layer: int = 200,
    max_layers: int = 1,
    sample_interval: int = 5,
    p1_eval_interval: int = 1,
    device: str = "cpu",
):
    """运行六阈值诊断实验"""
    start_time = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("Six-Threshold Bottleneck Diagnostic")
    print(f"N0={N0}, steps={steps_per_layer}, sample_interval={sample_interval}")
    print(f"p1_eval_interval={p1_eval_interval}")
    print("=" * 70)

    # 创建独立的六阈值检测器用于详细记录
    diagnostic_td = SixThresholdDetector()

    pbm = PersistentBiasMemory()
    cs = CumulativeSelector()
    six_td = SixThresholdDetector()
    psc = PreSubjectivityConvergence()
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
        max_layers=max_layers,
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
        phase2_verbose=True,
        phase3_verbose=False,
    )

    print("\n[1/2] Running HierarchicalEvolver with verbose Phase 2 output...")
    results = evolver.run(verbose=True)

    print("\n[2/2] Analyzing six-threshold history...")

    # 获取六阈值历史
    history = six_td._history
    if not history:
        print("ERROR: No six-threshold detections recorded!")
        return

    print(f"\nTotal P1 evaluations: {len(history)}")

    # 逐阈值分析
    threshold_ids = ['3.1', '3.2', '3.3', '3.4', '3.5', '3.6']
    threshold_names = {
        '3.1': '界面调节度',
        '3.2': '自维持稳健性',
        '3.3': '保持深度',
        '3.4': '复制保真度',
        '3.5': '选择压力',
        '3.6': '功能分化指数',
    }
    threshold_targets = {
        '3.1': 0.3,
        '3.2': 0.5,
        '3.3': 2.0,
        '3.4': 0.6,
        '3.5': 0.2,
        '3.6': 0.3,
    }

    print("\n" + "=" * 70)
    print("Per-Threshold Analysis")
    print("=" * 70)

    analysis = {}
    for tid in threshold_ids:
        values = []
        met_count = 0
        for result in history:
            for status in result.threshold_statuses:
                if status.threshold_id == tid:
                    values.append(status.value)
                    if status.is_met:
                        met_count += 1

        if values:
            arr = np.array(values)
            target = threshold_targets[tid]
            met_ratio = met_count / len(history) if len(history) > 0 else 0.0
            analysis[tid] = {
                'name': threshold_names[tid],
                'target': target,
                'mean': float(np.mean(arr)),
                'max': float(np.max(arr)),
                'min': float(np.min(arr)),
                'std': float(np.std(arr)),
                'final': float(arr[-1]),
                'met_count': met_count,
                'met_ratio': met_ratio,
                'gap_to_target': float(target - np.mean(arr)),
                'is_bottleneck': met_ratio < 0.1,
            }
            print(f"\n  [{tid}] {threshold_names[tid]} (target={target})")
            print(f"    mean={np.mean(arr):.4f}, max={np.max(arr):.4f}, min={np.min(arr):.4f}, std={np.std(arr):.4f}")
            print(f"    final={arr[-1]:.4f}, met={met_count}/{len(history)} ({met_count/len(history)*100:.1f}%)")
            print(f"    gap_to_target={target - np.mean(arr):.4f}")
        else:
            print(f"\n  [{tid}] {threshold_names[tid]} — NO DATA")

    # 瓶颈排序
    print("\n" + "=" * 70)
    print("Bottleneck Ranking (by met_ratio, lowest = worst bottleneck)")
    print("=" * 70)
    ranked = sorted(analysis.items(), key=lambda x: x[1]['met_ratio'])
    for rank, (tid, info) in enumerate(ranked, 1):
        status = "🔴 BOTTLENECK" if info['met_ratio'] < 0.1 else ("🟡 MARGINAL" if info['met_ratio'] < 0.5 else "🟢 OK")
        print(f"  {rank}. [{tid}] {info['name']}: met={info['met_ratio']*100:.1f}%, "
              f"mean={info['mean']:.4f} vs target={info['target']:.4f} {status}")

    # n_met 分布
    print("\n" + "=" * 70)
    print("n_met Distribution")
    print("=" * 70)
    n_met_counts = {}
    for result in history:
        n = result.n_met
        n_met_counts[n] = n_met_counts.get(n, 0) + 1
    for n_met in sorted(n_met_counts.keys()):
        count = n_met_counts[n_met]
        pct = count / len(history) * 100
        bar = "█" * int(pct / 2)
        print(f"  {n_met}/6: {count:4d} ({pct:5.1f}%) {bar}")

    # 全达标次数
    all_met_count = sum(1 for r in history if r.all_met)
    print(f"\n  All 6/6 met: {all_met_count}/{len(history)} ({all_met_count/len(history)*100:.1f}%)")

    # 最频繁瓶颈
    bottleneck_counts = {}
    for result in history:
        if result.bottleneck:
            bottleneck_counts[result.bottleneck] = bottleneck_counts.get(result.bottleneck, 0) + 1
    if bottleneck_counts:
        print(f"\n  Most frequent bottleneck: {max(bottleneck_counts, key=bottleneck_counts.get)} "
              f"({bottleneck_counts[max(bottleneck_counts, key=bottleneck_counts.get)]} times)")

    elapsed = time.time() - start_time

    # 保存报告
    report = {
        'experiment': 'exp_62_six_threshold_diagnostic',
        'timestamp': timestamp,
        'elapsed_seconds': round(elapsed, 2),
        'config': {
            'N0': N0, 'steps_per_layer': steps_per_layer,
            'sample_interval': sample_interval, 'p1_eval_interval': p1_eval_interval,
        },
        'n_evaluations': len(history),
        'threshold_analysis': {tid: {k: (round(v, 6) if isinstance(v, float) else v)
                                      for k, v in info.items()}
                                for tid, info in analysis.items()},
        'n_met_distribution': {str(k): v for k, v in n_met_counts.items()},
        'all_met_count': all_met_count,
        'bottleneck_frequency': bottleneck_counts,
        'top_bottleneck': ranked[0][0] if ranked else None,
    }

    report_dir = os.path.join(PROJECT_ROOT, "docs", "experiments")
    os.makedirs(report_dir, exist_ok=True)
    json_path = os.path.join(report_dir, f"exp_62_diagnostic_{timestamp}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nReport saved: {json_path}")
    print(f"Elapsed: {elapsed:.1f}s")
    print("=" * 70)

    return report


if __name__ == '__main__':
    report = run_diagnostic(
        N0=48, steps_per_layer=200, max_layers=1,
        sample_interval=5, p1_eval_interval=1,
        device='cpu',
    )
