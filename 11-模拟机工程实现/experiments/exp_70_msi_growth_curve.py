"""
experiments/exp_70_msi_growth_curve.py
  Phase 3 实验三：MSI 增长曲线追踪

Purpose:
  在 ODI 已证实可达 0.75-0.89（exp_67/exp_68）的基础上，
  系统追踪 Phase 3 三大指标（MSI、预期置信度、反事实激活）
  随演化进程的增长曲线。

  核心问题：
  1. MSI 在 ODI > 0.5 后是否持续增长？
  2. 预期置信度与 ODI 的相关性是否 > 0.5？
  3. 反事实引擎是否在 ODI > 0.6 后激活？
  4. 不同耦合模式（all/majority/weighted）下 MSI 增长模式有何差异？

  实验设计：
  - 4 种配置 × 3 次运行（减少随机性）
  - 高采样率：sample_interval=5, p1_eval_interval=5（每25步采样一次）
  - 使用 N0=72（exp_68 最佳配置）

Configurations:
  A: baseline (all, 0.30, N72, steps=300)
  B: majority (0.15, N72, steps=300)
  C: weighted (0.30, N72, steps=300)  — exp_68 最佳
  D: weighted (0.30, N72, steps=500)  — 更长演化

Acceptance criteria:
  1. MSI_max > 0.3 in at least 2 configurations
  2. MSI growth rate after ODI > 0.5 is positive
  3. Anticipation-ODI correlation > 0.3
  4. Counterfactual activates at least once across all runs
"""

import sys
import os
import time
import json
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


# ─── Experiment Configurations ───

CONFIGS = {
    'A_baseline': {
        'N0': 72, 'steps': 300, 'sample_interval': 5, 'p1_eval_interval': 5,
        'coupling_mode': 'all', 'coupling_threshold': 0.30,
        'description': 'Baseline: all mode, threshold=0.30, N72',
    },
    'B_majority': {
        'N0': 72, 'steps': 300, 'sample_interval': 5, 'p1_eval_interval': 5,
        'coupling_mode': 'majority', 'coupling_threshold': 0.15,
        'description': 'Majority mode, threshold=0.15, N72',
    },
    'C_weighted': {
        'N0': 72, 'steps': 300, 'sample_interval': 5, 'p1_eval_interval': 5,
        'coupling_mode': 'weighted', 'coupling_threshold': 0.30,
        'description': 'Weighted mode, threshold=0.30, N72 — exp_68 best',
    },
    'D_weighted_long': {
        'N0': 72, 'steps': 500, 'sample_interval': 5, 'p1_eval_interval': 5,
        'coupling_mode': 'weighted', 'coupling_threshold': 0.30,
        'description': 'Weighted mode, threshold=0.30, N72, 500 steps',
    },
}

N_RUNS = 3
VERBOSE = True


def run_single_config(config_name, config, run_id):
    """Run a single configuration once, return timeseries + analysis."""
    if VERBOSE:
        print(f"\n  [{config_name}] Run {run_id + 1}/{N_RUNS}: {config['description']}")

    pbm = PersistentBiasMemory()
    cs = CumulativeSelector()
    six_td = SixThresholdDetector()
    psc = PreSubjectivityConvergence(
        coupling_mode=config['coupling_mode'],
        coupling_threshold=config['coupling_threshold'],
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
        N0=config['N0'],
        steps_per_layer=config['steps'],
        sample_interval=config['sample_interval'],
        max_layers=1,
        p1_eval_interval=config['p1_eval_interval'],
        device='cpu',
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

    results = evolver.run(verbose=False)

    # ── Extract timeseries ──
    layer_results = results.get('layer_results', [])
    ts = {
        'steps': [], 'odi': [], 'msi': [], 'ant_conf': [], 'ant_reliable': [],
        'cf_active': [], 'cf_branches': [], '6t_n_met': [], 'conv': [],
        '7th_conf': [], 'odi_zone': [], 'msi_asymmetry': [],
        'msi_history_dep': [], 'msi_self_ref': [],
    }

    for lr in layer_results:
        lid = lr['layer']
        for sr in lr.get('phase2_step_results', []):
            step = sr.get('step', 0)
            ts['steps'].append(step)

            # ODI
            odi_val = 0.0
            odi_zone = ''
            if isinstance(sr.get('odi'), dict):
                odi_val = sr['odi'].get('value', 0.0)
                odi_zone = sr['odi'].get('zone', '')
            ts['odi'].append(odi_val)
            ts['odi_zone'].append(odi_zone)

            # MSI (with sub-indices)
            msi_val = 0.0
            msi_asym = 0.0
            msi_hist = 0.0
            msi_self = 0.0
            if isinstance(sr.get('minimal_self'), dict):
                msi_val = sr['minimal_self'].get('msi', 0.0)
                msi_asym = sr['minimal_self'].get('asymmetry_index', 0.0)
                msi_hist = sr['minimal_self'].get('history_dependency_index', 0.0)
                msi_self = sr['minimal_self'].get('self_reference_index', 0.0)
            ts['msi'].append(msi_val)
            ts['msi_asymmetry'].append(msi_asym)
            ts['msi_history_dep'].append(msi_hist)
            ts['msi_self_ref'].append(msi_self)

            # Anticipation
            ant_val = 0.0
            ant_rel = False
            if isinstance(sr.get('anticipation'), dict):
                ant_val = sr['anticipation'].get('confidence', 0.0)
                ant_rel = sr['anticipation'].get('is_reliable', False)
            ts['ant_conf'].append(ant_val)
            ts['ant_reliable'].append(ant_rel)

            # Counterfactual
            cf_val = False
            cf_br = 0
            if isinstance(sr.get('counterfactual'), dict):
                cf_val = sr['counterfactual'].get('active', False)
                cf_br = sr['counterfactual'].get('n_active_branches', 0)
            ts['cf_active'].append(cf_val)
            ts['cf_branches'].append(cf_br)

            # Six threshold
            n_met = 0
            if isinstance(sr.get('six_threshold'), dict):
                n_met = sr['six_threshold'].get('n_met', 0)
            ts['6t_n_met'].append(n_met)

            # Convergence
            conv = False
            if isinstance(sr.get('convergence'), dict):
                conv = sr['convergence'].get('converged', False)
            ts['conv'].append(conv)

            # Seventh threshold
            s7_conf = 0.0
            if isinstance(sr.get('seventh_threshold'), dict):
                s7_conf = sr['seventh_threshold'].get('confidence', 0.0)
            ts['7th_conf'].append(s7_conf)

    # ── Analysis ──
    analysis = {}
    odi_arr = np.array(ts['odi'])
    msi_arr = np.array(ts['msi'])
    ant_arr = np.array(ts['ant_conf'])
    cf_arr = np.array(ts['cf_active'], dtype=bool)
    n_met_arr = np.array(ts['6t_n_met'])
    conv_arr = np.array(ts['conv'], dtype=bool)

    # ODI stats
    analysis['odi_max'] = float(np.max(odi_arr)) if len(odi_arr) > 0 else 0.0
    analysis['odi_mean'] = float(np.mean(odi_arr)) if len(odi_arr) > 0 else 0.0
    analysis['odi_final'] = float(odi_arr[-1]) if len(odi_arr) > 0 else 0.0
    analysis['odi_above_05_ratio'] = float(np.mean(odi_arr > 0.5)) if len(odi_arr) > 0 else 0.0
    analysis['odi_above_06_ratio'] = float(np.mean(odi_arr > 0.6)) if len(odi_arr) > 0 else 0.0

    # MSI stats
    analysis['msi_max'] = float(np.max(msi_arr)) if len(msi_arr) > 0 else 0.0
    analysis['msi_mean'] = float(np.mean(msi_arr)) if len(msi_arr) > 0 else 0.0
    analysis['msi_final'] = float(msi_arr[-1]) if len(msi_arr) > 0 else 0.0
    analysis['msi_above_03_ratio'] = float(np.mean(msi_arr > 0.3)) if len(msi_arr) > 0 else 0.0

    # MSI growth: before vs after ODI > 0.5
    above_05_mask = odi_arr > 0.5
    if np.any(above_05_mask):
        first_above = np.argmax(above_05_mask)
        msi_before = msi_arr[:first_above]
        msi_after = msi_arr[first_above:]
        analysis['msi_mean_before_05'] = float(np.mean(msi_before)) if len(msi_before) > 0 else 0.0
        analysis['msi_mean_after_05'] = float(np.mean(msi_after)) if len(msi_after) > 0 else 0.0
        analysis['msi_growth_after_05'] = analysis['msi_mean_after_05'] - analysis['msi_mean_before_05']
    else:
        analysis['msi_mean_before_05'] = float(np.mean(msi_arr)) if len(msi_arr) > 0 else 0.0
        analysis['msi_mean_after_05'] = 0.0
        analysis['msi_growth_after_05'] = 0.0

    # MSI sub-indices
    asym_arr = np.array(ts['msi_asymmetry'])
    hist_arr = np.array(ts['msi_history_dep'])
    self_arr = np.array(ts['msi_self_ref'])
    analysis['msi_asymmetry_max'] = float(np.max(asym_arr)) if len(asym_arr) > 0 else 0.0
    analysis['msi_history_dep_max'] = float(np.max(hist_arr)) if len(hist_arr) > 0 else 0.0
    analysis['msi_self_ref_max'] = float(np.max(self_arr)) if len(self_arr) > 0 else 0.0

    # Anticipation-ODI correlation
    valid_ant = ant_arr > 0
    if np.sum(valid_ant) >= 3:
        o_valid = odi_arr[valid_ant]
        a_valid = ant_arr[valid_ant]
        if np.std(o_valid) > 1e-6 and np.std(a_valid) > 1e-6:
            analysis['ant_odi_correlation'] = float(np.corrcoef(o_valid, a_valid)[0, 1])
        else:
            analysis['ant_odi_correlation'] = 0.0
    else:
        analysis['ant_odi_correlation'] = 0.0
    analysis['ant_reliable_ratio'] = float(np.mean(ts['ant_reliable'])) if ts['ant_reliable'] else 0.0

    # Counterfactual
    analysis['cf_active_ratio'] = float(np.mean(cf_arr)) if len(cf_arr) > 0 else 0.0
    analysis['cf_ever_active'] = bool(np.any(cf_arr)) if len(cf_arr) > 0 else False
    analysis['cf_max_branches'] = int(np.max(ts['cf_branches'])) if ts['cf_branches'] else 0

    # Six threshold
    analysis['6t_max'] = int(np.max(n_met_arr)) if len(n_met_arr) > 0 else 0
    analysis['6t_mean'] = float(np.mean(n_met_arr)) if len(n_met_arr) > 0 else 0.0
    analysis['6t_all_met_ratio'] = float(np.mean(n_met_arr == 6)) if len(n_met_arr) > 0 else 0.0

    # Convergence
    analysis['conv_ratio'] = float(np.mean(conv_arr)) if len(conv_arr) > 0 else 0.0

    # ODI zone distribution
    zones = {}
    for z in ts['odi_zone']:
        if z:
            zones[z] = zones.get(z, 0) + 1
    analysis['odi_zone_distribution'] = zones

    return {
        'config_name': config_name,
        'run_id': run_id,
        'ts': ts,
        'analysis': analysis,
        'n_samples': len(ts['steps']),
    }


def run_experiment():
    """Run all configurations."""
    start_time = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_name = "exp_70_msi_growth_curve"

    if VERBOSE:
        print("=" * 70)
        print(f"Phase 3 Experiment 3: MSI Growth Curve Tracking")
        print(f"Time: {timestamp}")
        print(f"Configs: {list(CONFIGS.keys())}")
        print(f"Runs per config: {N_RUNS}")
        print("=" * 70)

    all_results = {}
    for config_name, config in CONFIGS.items():
        if VERBOSE:
            print(f"\n{'─' * 50}")
            print(f"Config: {config_name}")
            print(f"  {config['description']}")
            print(f"  N0={config['N0']}, steps={config['steps']}")
            print(f"  coupling_mode={config['coupling_mode']}, threshold={config['coupling_threshold']}")

        config_runs = []
        for run_id in range(N_RUNS):
            run_result = run_single_config(config_name, config, run_id)
            config_runs.append(run_result)
            if VERBOSE:
                a = run_result['analysis']
                print(f"    Run {run_id + 1}: ODI_max={a['odi_max']:.4f}, "
                      f"MSI_max={a['msi_max']:.4f}, "
                      f"MSI_growth={a['msi_growth_after_05']:+.4f}, "
                      f"Conv={a['conv_ratio']:.1%}")

        all_results[config_name] = config_runs

    # ── Cross-config analysis ──
    if VERBOSE:
        print(f"\n{'=' * 70}")
        print("Cross-Configuration Analysis")
        print("=" * 70)

    cross_analysis = {}
    for config_name, runs in all_results.items():
        odi_maxs = [r['analysis']['odi_max'] for r in runs]
        msi_maxs = [r['analysis']['msi_max'] for r in runs]
        msi_growths = [r['analysis']['msi_growth_after_05'] for r in runs]
        conv_ratios = [r['analysis']['conv_ratio'] for r in runs]
        ant_corrs = [r['analysis']['ant_odi_correlation'] for r in runs]
        cf_actives = [r['analysis']['cf_ever_active'] for r in runs]

        cross_analysis[config_name] = {
            'odi_max_mean': float(np.mean(odi_maxs)),
            'odi_max_std': float(np.std(odi_maxs)),
            'msi_max_mean': float(np.mean(msi_maxs)),
            'msi_max_std': float(np.std(msi_maxs)),
            'msi_growth_mean': float(np.mean(msi_growths)),
            'msi_growth_std': float(np.std(msi_growths)),
            'conv_ratio_mean': float(np.mean(conv_ratios)),
            'ant_corr_mean': float(np.mean(ant_corrs)),
            'cf_active_ratio': float(np.mean(cf_actives)),
            'n_runs': len(runs),
        }

        if VERBOSE:
            ca = cross_analysis[config_name]
            print(f"\n  {config_name}:")
            print(f"    ODI max:     {ca['odi_max_mean']:.4f} ± {ca['odi_max_std']:.4f}")
            print(f"    MSI max:     {ca['msi_max_mean']:.4f} ± {ca['msi_max_std']:.4f}")
            print(f"    MSI growth:  {ca['msi_growth_mean']:+.4f} ± {ca['msi_growth_std']:.4f}")
            print(f"    Conv ratio:  {ca['conv_ratio_mean']:.1%}")
            print(f"    Ant-ODI r:   {ca['ant_corr_mean']:.4f}")
            print(f"    CF active:   {ca['cf_active_ratio']:.1%}")

    # ── Acceptance criteria ──
    acceptance = {}

    # C1: MSI_max > 0.3 in at least 2 configs
    configs_above_03 = sum(
        1 for ca in cross_analysis.values() if ca['msi_max_mean'] > 0.3
    )
    acceptance['C1_MSI_above_03_in_2plus_configs'] = configs_above_03 >= 2

    # C2: MSI growth rate positive in at least 2 configs
    configs_positive_growth = sum(
        1 for ca in cross_analysis.values() if ca['msi_growth_mean'] > 0
    )
    acceptance['C2_MSI_positive_growth_in_2plus_configs'] = configs_positive_growth >= 2

    # C3: Anticipation-ODI correlation > 0.3 in at least 1 config
    configs_ant_corr = sum(
        1 for ca in cross_analysis.values() if ca['ant_corr_mean'] > 0.3
    )
    acceptance['C3_ant_odi_corr_above_03_in_1plus_config'] = configs_ant_corr >= 1

    # C4: Counterfactual activates at least once across all runs
    total_cf_active = sum(
        1 for runs in all_results.values() for r in runs if r['analysis']['cf_ever_active']
    )
    acceptance['C4_counterfactual_activates_at_least_once'] = total_cf_active >= 1

    overall_pass = sum(1 for v in acceptance.values() if v) >= 3  # 3/4 pass = overall pass

    if VERBOSE:
        print(f"\n{'─' * 50}")
        print("Acceptance Criteria:")
        for k, v in acceptance.items():
            status = "PASS" if v else "FAIL"
            print(f"  {k}: {status}")
        print(f"\nOverall: {'PASS' if overall_pass else 'FAIL'} ({sum(1 for v in acceptance.values() if v)}/4)")

    elapsed = time.time() - start_time

    # ── Build report ──
    report = {
        'experiment': exp_name,
        'timestamp': timestamp,
        'elapsed_seconds': round(elapsed, 2),
        'n_configs': len(CONFIGS),
        'n_runs_per_config': N_RUNS,
        'total_runs': len(CONFIGS) * N_RUNS,
        'config_descriptions': {k: v['description'] for k, v in CONFIGS.items()},
        'cross_analysis': cross_analysis,
        'acceptance': acceptance,
        'overall_pass': overall_pass,
        'per_run_summary': {
            config_name: [
                {
                    'run_id': r['run_id'],
                    'odi_max': r['analysis']['odi_max'],
                    'msi_max': r['analysis']['msi_max'],
                    'msi_growth': r['analysis']['msi_growth_after_05'],
                    'conv_ratio': r['analysis']['conv_ratio'],
                    'ant_corr': r['analysis']['ant_odi_correlation'],
                    'cf_active': r['analysis']['cf_ever_active'],
                    'n_samples': r['n_samples'],
                }
                for r in runs
            ]
            for config_name, runs in all_results.items()
        },
    }

    # ── Save reports ──
    report_dir = os.path.join(PROJECT_ROOT, "docs", "experiments")
    os.makedirs(report_dir, exist_ok=True)

    json_path = os.path.join(report_dir, f"{exp_name}_{timestamp}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    md_path = os.path.join(report_dir, f"{exp_name}_{timestamp}.md")
    _write_markdown_report(md_path, report, all_results, cross_analysis, acceptance, overall_pass, timestamp)

    if VERBOSE:
        print(f"\nReports saved:")
        print(f"  JSON: {json_path}")
        print(f"  MD:   {md_path}")
        print(f"\nTotal elapsed: {elapsed:.1f}s")

    return report


def _write_markdown_report(path, report, all_results, cross_analysis, acceptance, overall_pass, timestamp):
    lines = []
    lines.append(f"# Experiment Report: Phase 3 Experiment 3 — MSI Growth Curve\n")
    lines.append(f"## Info\n")
    lines.append(f"- **Time**: {timestamp}")
    lines.append(f"- **Elapsed**: {report['elapsed_seconds']}s")
    lines.append(f"- **Total runs**: {report['total_runs']} ({report['n_configs']} configs × {report['n_runs_per_config']} runs)")
    lines.append(f"- **Overall**: {'✅ PASS' if overall_pass else '❌ FAIL'}\n")

    lines.append(f"## Configurations\n")
    for k, v in report['config_descriptions'].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append(f"## Cross-Configuration Results\n")
    lines.append(f"| Config | ODI max | MSI max | MSI growth | Conv% | Ant-ODI r | CF active |")
    lines.append(f"|---|---|---|---|---|---|---|")
    for config_name, ca in cross_analysis.items():
        lines.append(
            f"| {config_name} "
            f"| {ca['odi_max_mean']:.4f}±{ca['odi_max_std']:.4f} "
            f"| {ca['msi_max_mean']:.4f}±{ca['msi_max_std']:.4f} "
            f"| {ca['msi_growth_mean']:+.4f}±{ca['msi_growth_std']:.4f} "
            f"| {ca['conv_ratio_mean']:.1%} "
            f"| {ca['ant_corr_mean']:.4f} "
            f"| {ca['cf_active_ratio']:.1%} |"
        )
    lines.append("")

    lines.append(f"## Acceptance Criteria\n")
    for k, v in acceptance.items():
        status = "✅ PASS" if v else "❌ FAIL"
        lines.append(f"- **{k}**: {status}")
    lines.append(f"\n**Overall**: {'✅ PASS' if overall_pass else '❌ FAIL'} ({sum(1 for v in acceptance.values() if v)}/4)\n")

    lines.append(f"## Per-Run Details\n")
    for config_name, runs in all_results.items():
        lines.append(f"### {config_name}\n")
        lines.append(f"| Run | ODI max | MSI max | MSI growth | Conv% | Ant-ODI r | CF | Samples |")
        lines.append(f"|---|---|---|---|---|---|---|---|")
        for r in runs:
            a = r['analysis']
            lines.append(
                f"| {r['run_id'] + 1} "
                f"| {a['odi_max']:.4f} "
                f"| {a['msi_max']:.4f} "
                f"| {a['msi_growth_after_05']:+.4f} "
                f"| {a['conv_ratio']:.1%} "
                f"| {a['ant_odi_correlation']:.4f} "
                f"| {'Y' if a['cf_ever_active'] else 'N'} "
                f"| {r['n_samples']} |"
            )
        lines.append("")

    lines.append(f"## Theoretical Mapping\n")
    lines.append(f"1. **MSI growth after ODI > 0.5** ↔ 象界前主体态 → 最小自我涌现")
    lines.append(f"2. **Anticipation-ODI correlation** ↔ 结构密度 → 预期能力正反馈")
    lines.append(f"3. **Counterfactual activation** ↔ 复制+筛选联合扩展 → 反事实推理")
    lines.append(f"4. **MSI sub-indices** (asymmetry/history/self-ref) ↔ 三条件检测器\n")

    lines.append(f"## Next Steps\n")
    lines.append(f"- If MSI growth is positive: investigate the growth rate and saturation level")
    lines.append(f"- If CF never activates: investigate ODI threshold for CF activation")
    lines.append(f"- If Ant-ODI correlation is low: investigate anticipation gating mechanism")
    lines.append(f"- exp_71: 功能信号耦合原型（P2 from architecture redesign）")
    lines.append(f"- exp_72: 分层耦合（P3 from architecture redesign）\n")

    lines.append(f"\n---\n*Auto-generated at {timestamp}*\n")

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    report = run_experiment()
    sys.exit(0 if report['overall_pass'] else 1)
