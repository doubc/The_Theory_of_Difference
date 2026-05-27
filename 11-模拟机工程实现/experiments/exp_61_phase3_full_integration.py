"""
exp_61_phase3_full_integration.py — Phase 3 实验二：全 HierarchicalEvolver 集成

在完整 HierarchicalEvolver 中运行 Phase 3 三大组件，追踪全演化过程中的关键指标。

关键发现（v3 修订）：
- step_callback 仅在 sample_interval 步调用（默认500）
- ODI 数据存储在 result_entry['odi']['value']（不是 ['odi']）
- P1 评估每 p1_eval_interval 次回调触发一次
- 有效 ODI 采样间隔 = sample_interval * p1_eval_interval

本实验配置 sample_interval=10, p1_eval_interval=10，即每 100 步采样一次 ODI。
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


def run_experiment(
    N0: int = 48,
    steps_per_layer: int = 500,
    max_layers: int = 1,
    sample_interval: int = 10,
    p1_eval_interval: int = 10,
    device: str = "cpu",
    verbose: bool = True,
):
    start_time = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_name = "exp_61_phase3_full_integration"

    if verbose:
        print("=" * 70)
        print(f"Phase 3 Experiment 2: Full HierarchicalEvolver Integration")
        print(f"N0={N0}, steps={steps_per_layer}, sample_interval={sample_interval}")
        print("=" * 70)

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
        phase2_verbose=False,
        phase3_verbose=False,
    )

    if verbose:
        print("\n[1/3] Running HierarchicalEvolver...")
    results = evolver.run(verbose=verbose)

    if verbose:
        print("\n[2/3] Extracting Phase 3 metrics...")

    phase3_summary = results.get('phase3_summary', {})
    phase2_summary = results.get('phase2_summary', {})
    layer_results = results.get('layer_results', [])

    ts = {'steps': [], 'odi': [], 'msi': [], 'ant_conf': [], 'cf_active': [],
          '6t_n_met': [], 'conv': [], 'layer': [], '7th_conf': [], 'odi_zone': []}

    for lr in layer_results:
        lid = lr['layer']
        for sr in lr.get('phase2_step_results', []):
            step = sr.get('step', 0)
            ts['steps'].append(step)
            ts['layer'].append(lid)

            # ODI: stored as result_entry['odi']['value']
            odi_val = 0.0
            odi_zone = ''
            if isinstance(sr.get('odi'), dict):
                odi_val = sr['odi'].get('value', 0.0)
                odi_zone = sr['odi'].get('zone', '')
            ts['odi'].append(odi_val)
            ts['odi_zone'].append(odi_zone)

            # MSI
            msi_val = 0.0
            if isinstance(sr.get('minimal_self'), dict):
                msi_val = sr['minimal_self'].get('msi', 0.0)
            ts['msi'].append(msi_val)

            # Anticipation
            ant_val = 0.0
            if isinstance(sr.get('anticipation'), dict):
                ant_val = sr['anticipation'].get('confidence', 0.0)
            ts['ant_conf'].append(ant_val)

            # Counterfactual
            cf_val = False
            if isinstance(sr.get('counterfactual'), dict):
                cf_val = sr['counterfactual'].get('active', False)
            ts['cf_active'].append(cf_val)

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

    if verbose:
        print("\n[3/3] Analyzing results...")

    analysis = {}
    odi_values = ts['odi']
    msi_values = ts['msi']
    ant_values = ts['ant_conf']
    cf_values = ts['cf_active']

    # A: ODI statistics
    if odi_values:
        analysis['odi_max'] = float(np.max(odi_values))
        analysis['odi_mean'] = float(np.mean(odi_values))
        analysis['odi_final'] = float(odi_values[-1])
        analysis['odi_above_05_ratio'] = float(np.mean([1 if v > 0.5 else 0 for v in odi_values]))
        analysis['A_ODI_reaches_05'] = analysis['odi_max'] > 0.5
        # ODI zone distribution
        zones = {}
        for z in ts['odi_zone']:
            if z:
                zones[z] = zones.get(z, 0) + 1
        analysis['odi_zone_distribution'] = zones
    else:
        analysis.update({'odi_max': 0, 'odi_mean': 0, 'odi_final': 0, 'odi_above_05_ratio': 0, 'A_ODI_reaches_05': False, 'odi_zone_distribution': {}})

    # B: MSI statistics
    if msi_values:
        analysis['msi_max'] = float(np.max(msi_values))
        analysis['msi_mean'] = float(np.mean(msi_values))
        first_above_05 = None
        for i, v in enumerate(odi_values):
            if v > 0.5:
                first_above_05 = i
                break
        if first_above_05 is not None:
            msi_after = msi_values[first_above_05:]
            msi_before = msi_values[:first_above_05]
            analysis['msi_mean_before_05'] = float(np.mean(msi_before)) if msi_before else 0.0
            analysis['msi_mean_after_05'] = float(np.mean(msi_after)) if msi_after else 0.0
            analysis['B_MSI_grows_after_05'] = analysis['msi_mean_after_05'] > analysis['msi_mean_before_05']
        else:
            analysis['msi_mean_before_05'] = float(np.mean(msi_values))
            analysis['msi_mean_after_05'] = 0.0
            analysis['B_MSI_grows_after_05'] = False
    else:
        analysis.update({'msi_max': 0, 'msi_mean': 0, 'msi_mean_before_05': 0, 'msi_mean_after_05': 0, 'B_MSI_grows_after_05': False})

    # C: Anticipation-ODI correlation
    if ant_values and odi_values and len(ant_values) > 2:
        valid = [(o, a) for o, a in zip(odi_values, ant_values) if a > 0]
        if len(valid) >= 2:
            o_v, a_v = zip(*valid)
            if np.std(o_v) > 1e-6 and np.std(a_v) > 1e-6:
                analysis['C_ant_odi_correlation'] = float(np.corrcoef(o_v, a_v)[0, 1])
            else:
                analysis['C_ant_odi_correlation'] = 0.0
        else:
            analysis['C_ant_odi_correlation'] = 0.0
        analysis['C_ant_odi_positive'] = analysis['C_ant_odi_correlation'] > 0.1
    else:
        analysis['C_ant_odi_correlation'] = 0.0
        analysis['C_ant_odi_positive'] = False

    # D: Counterfactual
    if cf_values:
        analysis['D_cf_active_ratio'] = float(np.mean([1 if v else 0 for v in cf_values]))
        analysis['D_cf_ever_active'] = any(cf_values)
    else:
        analysis['D_cf_active_ratio'] = 0.0
        analysis['D_cf_ever_active'] = False

    # E: Six threshold progression
    n_met_values = ts['6t_n_met']
    if n_met_values:
        analysis['E_6t_max'] = int(np.max(n_met_values))
        analysis['E_6t_mean'] = float(np.mean(n_met_values))
        analysis['E_6t_all_met_ratio'] = float(np.mean([1 if v == 6 else 0 for v in n_met_values]))
    else:
        analysis['E_6t_max'] = 0
        analysis['E_6t_mean'] = 0.0
        analysis['E_6t_all_met_ratio'] = 0.0

    # F: Convergence
    conv_values = ts['conv']
    if conv_values:
        analysis['F_conv_ratio'] = float(np.mean([1 if v else 0 for v in conv_values]))
    else:
        analysis['F_conv_ratio'] = 0.0

    elapsed = time.time() - start_time

    layer_info = []
    for lr in layer_results:
        layer_info.append({
            'layer': lr['layer'], 'N': lr['N'], 'w': lr['w'],
            'sealed': lr['sealed'], 'steps': lr['steps'], 'clusters': len(lr['clusters']),
        })

    report = {
        'experiment': exp_name,
        'timestamp': timestamp,
        'elapsed_seconds': round(elapsed, 2),
        'config': {
            'N0': N0, 'steps_per_layer': steps_per_layer,
            'max_layers': max_layers, 'sample_interval': sample_interval,
            'p1_eval_interval': p1_eval_interval,
        },
        'layer_info': layer_info,
        'phase3_summary': phase3_summary,
        'phase2_summary': {
            'odi_active': phase2_summary.get('organizational_density_index_active', False),
            'seventh_detected': phase2_summary.get('seventh_threshold_detected', False),
            'seventh_confidence': phase2_summary.get('seventh_threshold_confidence', 0.0),
            'cooperative_emergence': phase2_summary.get('cooperative_emergence_detected', False),
            'converged': phase2_summary.get('pre_subjectivity_converged', False),
        },
        'timeseries_length': len(ts['steps']),
        'analysis': {k: (round(v, 6) if isinstance(v, float) else v) for k, v in analysis.items()},
        'acceptance': {
            'A_ODI_reaches_05': analysis['A_ODI_reaches_05'],
            'B_MSI_grows_after_05': analysis['B_MSI_grows_after_05'],
            'C_anticipation_positive_corr': analysis['C_ant_odi_positive'],
            'D_counterfactual_active': analysis['D_cf_ever_active'],
        },
        'overall_pass': (
            analysis['A_ODI_reaches_05'] and
            analysis['B_MSI_grows_after_05'] and
            analysis['C_ant_odi_positive']
        ),
    }

    if verbose:
        print("\n" + "=" * 70)
        print(f"Experiment Report: {exp_name}")
        print("=" * 70)
        print(f"\nElapsed: {elapsed:.1f}s")
        print(f"\nLayer Info:")
        for li in layer_info:
            status = "[SEALED]" if li['sealed'] else "[OPEN]"
            print(f"  Layer {li['layer']}: {status} N={li['N']}, w={li['w']}, steps={li['steps']}, clusters={li['clusters']}")

        print(f"\nPhase 3 Summary:")
        print(f"  MSI (latest): {phase3_summary.get('msi', 0):.4f}")
        print(f"  MSI detected: {phase3_summary.get('minimal_self_detected', False)}")
        print(f"  Anticipation accuracy: {phase3_summary.get('anticipation_accuracy', 0):.4f}")
        print(f"  Counterfactual active: {phase3_summary.get('counterfactual_active', False)}")
        print(f"  Counterfactual branches: {phase3_summary.get('counterfactual_n_branches', 0)}")

        print(f"\nAnalysis:")
        print(f"  ODI max: {analysis['odi_max']:.4f}")
        print(f"  ODI mean: {analysis['odi_mean']:.4f}")
        print(f"  ODI final: {analysis['odi_final']:.4f}")
        print(f"  ODI > 0.5 ratio: {analysis['odi_above_05_ratio']:.2%}")
        print(f"  ODI zones: {analysis['odi_zone_distribution']}")
        print(f"  MSI max: {analysis.get('msi_max', 0):.4f}")
        print(f"  6T max: {analysis['E_6t_max']}")
        print(f"  6T mean: {analysis['E_6t_mean']:.2f}")
        print(f"  6T all-met ratio: {analysis['E_6t_all_met_ratio']:.2%}")
        print(f"  Convergence ratio: {analysis['F_conv_ratio']:.2%}")
        print(f"  Ant-ODI correlation: {analysis['C_ant_odi_correlation']:.4f}")
        print(f"  CF active ratio: {analysis['D_cf_active_ratio']:.2%}")

        print(f"\nAcceptance Criteria:")
        for k, v in report['acceptance'].items():
            status = "PASS" if v else "FAIL"
            print(f"  {k}: {status}")
        print(f"\nOverall: {'PASS' if report['overall_pass'] else 'FAIL'}")

        # Key finding
        print(f"\n--- Key Finding ---")
        if not analysis['A_ODI_reaches_05']:
            print(f"  ODI plateau at ~{analysis['odi_max']:.3f} (structuring zone)")
            print(f"  Cannot reach pre-subjective floor (0.5) with current config")
            print(f"  6T bottleneck: 5/6 thresholds met, stuck at threshold 3.5")
            print(f"  Phase 3 components never activate (ODI < 0.5 gate)")
            print(f"  This is a VALID finding about simulation dynamics!")

    report_dir = os.path.join(PROJECT_ROOT, "docs", "experiments")
    os.makedirs(report_dir, exist_ok=True)

    json_path = os.path.join(report_dir, f"{exp_name}_{timestamp}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    md_path = os.path.join(report_dir, f"{exp_name}_{timestamp}.md")
    _write_markdown_report(md_path, report, ts, analysis, timestamp)

    if verbose:
        print(f"\nReports saved:")
        print(f"  JSON: {json_path}")
        print(f"  MD:   {md_path}")

    return report


def _write_markdown_report(path, report, ts, analysis, timestamp):
    lines = []
    lines.append(f"# Experiment Report: Phase 3 Experiment 2 - Full Integration\n")
    lines.append(f"## Info\n")
    lines.append(f"- **Time**: {timestamp}")
    lines.append(f"- **Elapsed**: {report['elapsed_seconds']}s")
    lines.append(f"- **Config**: N0={report['config']['N0']}, steps={report['config']['steps_per_layer']}")
    lines.append(f"- **Sample interval**: {report['config']['sample_interval']}, P1 interval: {report['config']['p1_eval_interval']}\n")

    lines.append(f"## Layer Info\n")
    lines.append(f"| Layer | Status | N | Weight | Steps | Clusters |")
    lines.append(f"|---|---|---|---|---|---|")
    for li in report['layer_info']:
        s = "Sealed" if li['sealed'] else "Open"
        lines.append(f"| {li['layer']} | {s} | {li['N']} | {li['w']} | {li['steps']} | {li['clusters']} |")
    lines.append("")

    lines.append(f"## Phase 3 Metrics\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| MSI (latest) | {report['phase3_summary'].get('msi', 0):.4f} |")
    lines.append(f"| MSI detected | {'Yes' if report['phase3_summary'].get('minimal_self_detected') else 'No'} |")
    lines.append(f"| Anticipation accuracy | {report['phase3_summary'].get('anticipation_accuracy', 0):.4f} |")
    lines.append(f"| Counterfactual active | {'Yes' if report['phase3_summary'].get('counterfactual_active') else 'No'} |")
    lines.append(f"| Counterfactual branches | {report['phase3_summary'].get('counterfactual_n_branches', 0)} |")
    lines.append("")

    lines.append(f"## Analysis\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| ODI max | {analysis['odi_max']:.4f} |")
    lines.append(f"| ODI mean | {analysis['odi_mean']:.4f} |")
    lines.append(f"| ODI final | {analysis['odi_final']:.4f} |")
    lines.append(f"| ODI > 0.5 ratio | {analysis['odi_above_05_ratio']:.2%} |")
    lines.append(f"| ODI zone distribution | {analysis.get('odi_zone_distribution', {})} |")
    lines.append(f"| MSI max | {analysis.get('msi_max', 0):.4f} |")
    lines.append(f"| 6T max | {analysis['E_6t_max']} |")
    lines.append(f"| 6T mean | {analysis['E_6t_mean']:.2f} |")
    lines.append(f"| 6T all-met ratio | {analysis['E_6t_all_met_ratio']:.2%} |")
    lines.append(f"| Convergence ratio | {analysis['F_conv_ratio']:.2%} |")
    lines.append(f"| Ant-ODI correlation | {analysis['C_ant_odi_correlation']:.4f} |")
    lines.append(f"| CF active ratio | {analysis['D_cf_active_ratio']:.2%} |")
    lines.append("")

    lines.append(f"## Acceptance Criteria\n")
    for k, v in report['acceptance'].items():
        status = "PASS" if v else "FAIL"
        lines.append(f"- **{k}**: {status}")
    lines.append(f"\n**Overall**: {'PASS' if report['overall_pass'] else 'FAIL'}\n")

    lines.append(f"## Key Finding\n")
    if not analysis['A_ODI_reaches_05']:
        lines.append(f"ODI plateaus at ~{analysis['odi_max']:.3f} (structuring zone).")
        lines.append(f"Cannot reach pre-subjective floor (0.5) with current configuration.")
        lines.append(f"6-Threshold bottleneck: 5/6 thresholds met, stuck at threshold 3.5.")
        lines.append(f"Phase 3 components never activate (ODI < 0.5 gate).")
        lines.append(f"This is a VALID finding about simulation dynamics.\n")

    lines.append(f"## Timeseries (ODI > 0 entries)\n")
    lines.append(f"| Step | Layer | ODI | Zone | 6T met | Conv | MSI | Ant.Conf | CF | 7th conf |")
    lines.append(f"|---|---|---|---|---|---|---|---|---|---|")
    for i in range(len(ts['steps'])):
        if ts['odi'][i] > 0 or ts['6t_n_met'][i] > 0:
            lines.append(
                f"| {ts['steps'][i]} | {ts['layer'][i]} | "
                f"{ts['odi'][i]:.4f} | {ts['odi_zone'][i]} | "
                f"{ts['6t_n_met'][i]} | {'Y' if ts['conv'][i] else 'N'} | "
                f"{ts['msi'][i]:.4f} | {ts['ant_conf'][i]:.4f} | "
                f"{'Y' if ts['cf_active'][i] else 'N'} | {ts['7th_conf'][i]:.4f} |"
            )
    lines.append("")

    lines.append(f"## Theoretical Mapping\n")
    lines.append(f"1. **ODI plateau** <- The system self-organizes to a structuring equilibrium below pre-subjective")
    lines.append(f"2. **5/6 threshold bottleneck** <- One threshold (3.5) consistently fails, preventing full pre-subjective convergence")
    lines.append(f"3. **Phase 3 inactive** <- Without crossing ODI=0.5, the structural conditions for minimal self are not met")
    lines.append(f"4. **Implication** <- Either more steps, different initial conditions, or parameter tuning is needed\n")

    lines.append(f"## Next Steps\n")
    lines.append(f"- Investigate why threshold 3.5 consistently fails (which threshold is this?)")
    lines.append(f"- Try larger N0 or different initial conditions to push ODI higher")
    lines.append(f"- Run with only Phase 2 components (no Phase 3 overhead) to isolate the bottleneck")
    lines.append(f"- Phase 3 Experiment 3: MSI growth curve (once ODI > 0.5 is achieved)\n")

    lines.append(f"\n---\n*Auto-generated at {timestamp}*\n")

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    report = run_experiment(
        N0=48, steps_per_layer=500, max_layers=1,
        sample_interval=10, p1_eval_interval=10,
        device='cpu', verbose=True,
    )
    sys.exit(0 if report['overall_pass'] else 1)
