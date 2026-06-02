"""
experiments/exp_121_phase5_b7_partial_sealing.py — Track B7: 部分封口 + 分层封装

修复 exp_120 的两个核心问题：
1. N0=48 的双峰封口（全有/全无）
2. Layer 1 自动创建失败

解决方案：
- 部分封口：横向和层级比特独立封口
- 分层封装：横向封口时只封装横向比特到 L1
- 层级延续：L0 在横向封口后继续运行层级比特

假设：
H41: 部分封口触发率 ≥6/8
H42: L1 形成率 ≥6/8
H43: L0 层级比特最终封口 ≥4/8
H44: L1 比特数在 [10, 30] 范围内
H45: 系统稳定性（无崩溃）
"""

import sys
import os
import torch
import numpy as np
import json
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.layer_narrative_tracker import LayerNarrativeTracker, DEFAULT_LAYER_NARRATIVE_CONFIG
from engine.cross_scale_coupling import CrossScaleCoupling, DEFAULT_CROSS_SCALE_COUPLING_CONFIG
from engine.narrative_self_emergence import NarrativeSelfEmergence, DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG


def run_experiment(seed: int, N0: int = 48, steps_per_layer: int = 5000,
                   partial_sealing: bool = True, binding_threshold: float = 0.05,
                   verbose: bool = True) -> dict:
    """运行单个种子的实验"""

    torch.manual_seed(seed)
    np.random.seed(seed)

    if verbose:
        print(f"\n{'='*70}")
        print(f"Seed {seed} | N0={N0} | partial_sealing={partial_sealing} | "
              f"binding_threshold={binding_threshold}")
        print(f"{'='*70}")

    # 配置 CSC + NSE（Phase 4 简化架构）
    csc_config = {**DEFAULT_CROSS_SCALE_COUPLING_CONFIG}
    csc_config['coupling_strength'] = 0.20
    csc = CrossScaleCoupling(config=csc_config)

    nse_config = {**DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG}
    nse = NarrativeSelfEmergence(config=nse_config)

    lnt_config = {**DEFAULT_LAYER_NARRATIVE_CONFIG}
    lnt = LayerNarrativeTracker(config=lnt_config)

    # 创建分层演化器
    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=steps_per_layer,
        sample_interval=500,
        max_layers=3,
        device="cpu",
        binding_threshold=binding_threshold,
        min_group_size=2,
        auto_encapsulate=True,
        partial_sealing=partial_sealing,  # Track B7 核心开关
        verbose_gravity=False,
        cross_scale_coupling=csc,
        narrative_self_emergence=nse,
        layer_narrative_tracker=lnt,
        phase4_verbose=False,
    )

    # 运行
    result = evolver.run(verbose=verbose)

    # 收集结果
    hierarchy_summary = evolver.hierarchy.get_hierarchy_summary()

    # 分析每层封口状态
    sealing_analysis = []
    for layer in hierarchy_summary['layers']:
        lid = layer['id']
        l_state = evolver.hierarchy.get_layer(lid)
        status = l_state.constraints.get_sealing_status()
        sealing_analysis.append({
            'layer': lid,
            'N': layer['N'],
            'sealed': layer['sealed'],
            'sealed_lateral': status['sealed_lateral'],
            'sealed_hierarchy': status['sealed_hierarchy'],
            'n_sealed_lateral': status['n_sealed_lateral'],
            'n_sealed_hierarchy': status['n_sealed_hierarchy'],
            'n_lateral_total': status['n_lateral_total'],
            'n_hierarchy_total': status['n_hierarchy_total'],
            'sealed_ratio': layer['sealed'] and layer['N'] > 0,
        })

    # 计算假设结果
    lateral_sealed_count = sum(1 for s in sealing_analysis if s['sealed_lateral'])
    l1_created = hierarchy_summary['n_layers'] >= 2
    hierarchy_sealed_count = sum(1 for s in sealing_analysis if s['sealed_hierarchy'])
    l1_n_bits = 0
    if hierarchy_summary['n_layers'] >= 2:
        l1_n_bits = hierarchy_summary['layers'][1]['N']

    hypotheses = {
        'H41_partial_seal': lateral_sealed_count >= 1,  # L0 横向封口
        'H42_l1_formed': l1_created,
        'H43_hierarchy_sealed': hierarchy_sealed_count >= 1,  # L0 层级也封口
        'H44_l1_bits_reasonable': 10 <= l1_n_bits <= 30 if l1_created else False,
        'H45_no_crash': True,  # 如果运行完成就是 True
    }

    # 叙事指标
    lnt_summary = lnt.get_summary()

    return {
        'seed': seed,
        'hierarchy': hierarchy_summary,
        'sealing_analysis': sealing_analysis,
        'hypotheses': hypotheses,
        'encapsulation_events': [
            {k: v for k, v in e.items() if k != 'encapsulated_bits'}
            for e in evolver.encapsulation_events
        ],
        'narrative': {
            'layer_nsi': {k: v.nsi for k, v in lnt_summary.per_layer.items()},
            'layer_activity': lnt_summary.layer_activity,
        },
        'l1_n_bits': l1_n_bits,
        'total_layers': hierarchy_summary['n_layers'],
    }


def main():
    seeds = [42, 142, 242, 342, 442, 542, 642, 742]
    N0 = 48
    steps = 5000
    binding_threshold = 0.05

    print("=" * 70)
    print("Track B7: Partial Sealing + Layered Encapsulation")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"N0={N0}, steps={steps}, binding_threshold={binding_threshold}")
    print(f"Seeds: {seeds}")
    print("=" * 70)

    results = []
    for seed in seeds:
        result = run_experiment(
            seed=seed, N0=N0, steps_per_layer=steps,
            partial_sealing=True, binding_threshold=binding_threshold,
            verbose=True
        )
        results.append(result)

    # 汇总
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    h41_pass = sum(1 for r in results if r['hypotheses']['H41_partial_seal'])
    h42_pass = sum(1 for r in results if r['hypotheses']['H42_l1_formed'])
    h43_pass = sum(1 for r in results if r['hypotheses']['H43_hierarchy_sealed'])
    h44_pass = sum(1 for r in results if r['hypotheses']['H44_l1_bits_reasonable'])
    h45_pass = sum(1 for r in results if r['hypotheses']['H45_no_crash'])

    print(f"H41 (Partial seal L0 lateral): {h41_pass}/{len(seeds)} seeds")
    print(f"H42 (L1 created):              {h42_pass}/{len(seeds)} seeds")
    print(f"H43 (L0 hierarchy sealed):     {h43_pass}/{len(seeds)} seeds")
    print(f"H44 (L1 bits 10-30):           {h44_pass}/{len(seeds)} seeds")
    print(f"H45 (No crash):                {h45_pass}/{len(seeds)} seeds")

    # 详细封口分析
    print("\n--- Sealing Analysis ---")
    for r in results:
        s = r['sealing_analysis'][0]  # L0
        print(f"  Seed {r['seed']:3d}: L0 sealed={s['sealed']}, "
              f"lateral={s['n_sealed_lateral']}/{s['n_lateral_total']}, "
              f"hierarchy={s['n_sealed_hierarchy']}/{s['n_hierarchy_total']}, "
              f"L1 bits={r['l1_n_bits']}, layers={r['total_layers']}")

    # 保存结果
    output_dir = project_root / "experiments" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "exp_121_b7_partial_sealing.json"

    # 简化结果用于 JSON 保存
    simple_results = []
    for r in results:
        simple_results.append({
            'seed': r['seed'],
            'hypotheses': r['hypotheses'],
            'sealing_analysis': r['sealing_analysis'],
            'l1_n_bits': r['l1_n_bits'],
            'total_layers': r['total_layers'],
            'encapsulation_count': len(r['encapsulation_events']),
            'narrative': r['narrative'],
        })

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'experiment': 'exp_121_track_b7_partial_sealing',
            'date': datetime.now().isoformat(),
            'config': {
                'N0': N0,
                'steps_per_layer': steps,
                'binding_threshold': binding_threshold,
                'partial_sealing': True,
                'seeds': seeds,
            },
            'summary': {
                'H41': f"{h41_pass}/{len(seeds)}",
                'H42': f"{h42_pass}/{len(seeds)}",
                'H43': f"{h43_pass}/{len(seeds)}",
                'H44': f"{h44_pass}/{len(seeds)}",
                'H45': f"{h45_pass}/{len(seeds)}",
            },
            'results': simple_results,
        }, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_file}")

    # 返回总通过率
    total_hypotheses = 5
    total_seeds = len(seeds)
    total_pass = h41_pass + h42_pass + h43_pass + h44_pass + h45_pass
    total_possible = total_hypotheses * total_seeds
    print(f"\nOverall: {total_pass}/{total_possible} hypothesis-seeds pass "
          f"({100*total_pass/total_possible:.1f}%)")

    return results


if __name__ == '__main__':
    main()
