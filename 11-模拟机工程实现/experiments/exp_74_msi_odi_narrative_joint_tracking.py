"""experiments/exp_74_msi_odi_narrative_joint_tracking.py

Phase 3 实验四：MSI-ODI-叙事联合追踪实验

Purpose:
  在 exp_70（MSI 增长曲线）和 exp_67/68（ODI 验证）的基础上，
  首次将 MSI、ODI 与叙事递归偏置修正（ΔB_narrative）三者联合追踪，
  验证"自指环节断点"——即叙事层对差异场的反馈是否在特定 ODI/MSI 阈值后
  出现非线性跃迁。

  核心问题：
  1. 叙事偏置修正幅度（||ΔB_narrative||）与 ODI 是否存在非线性关系？
     理论预测：ODI > 0.5 后，叙事修正幅度出现跃迁式增长
  2. MSI 的增长是否由叙事修正驱动？
     理论预测：MSI 增速在叙事修正激活后显著提升
  3. 叙事层级分布（MINI→INSTITUTIONAL→CIVILIZATION）如何随 ODI 演变？
     理论预测：随着 ODI 提升，叙事从 MINI 层向 CIVILIZATION 层迁移
  4. 自指断点位置：叙事反馈回路在哪个 ODI 值开始自我强化？

  实验设计：
  - 4 种配置 × 3 次运行
  - 高采样率：每 5 步记录一次 MSI、ODI、叙事统计
  - 记录每次叙事 step 的 ΔB_narrative 幅度和层级分布
  - 计算 ODI-叙事修正的相关系数和断点检测

Configurations:
  A: baseline (weighted, 0.30, N72, steps=400) — 标准配置
  B: low_threshold (weighted, 0.15, N72, steps=400) — 更早触发耦合
  C: high_N (weighted, 0.30, N128, steps=400) — 更大系统
  D: long_run (weighted, 0.30, N72, steps=800) — 长演化观察断点

Acceptance criteria:
  1. ODI-叙事修正幅度相关系数 |r| > 0.4（至少 2 配置）
  2. 检测到至少 1 个自指断点（叙事修正幅度的突变点）
  3. MSI 增速在叙事激活后显著提升（斜率变化 > 50%）
  4. 叙事层级分布出现从 MINI 向更高层的迁移趋势
"""

import sys
import os
import time
import json
import math
from datetime import datetime
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.narrative_self import NarrativeRecursionOperator, DifferenceSignal
from engine.lateral_coupling import LateralCoupler
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from engine.minimal_self_detector import MinimalSelfDetector


# ─── Experiment Configurations ───

CONFIGS = {
    'A_baseline': {
        'N0': 72, 'steps': 400, 'sample_interval': 5, 'p1_eval_interval': 5,
        'coupling_mode': 'weighted', 'coupling_threshold': 0.30,
        'description': 'Baseline: weighted, threshold=0.30, N72, 400 steps',
    },
    'B_low_threshold': {
        'N0': 72, 'steps': 400, 'sample_interval': 5, 'p1_eval_interval': 5,
        'coupling_mode': 'weighted', 'coupling_threshold': 0.15,
        'description': 'Low threshold: weighted, threshold=0.15, N72 — earlier coupling',
    },
    'C_high_N': {
        'N0': 128, 'steps': 400, 'sample_interval': 5, 'p1_eval_interval': 5,
        'coupling_mode': 'weighted', 'coupling_threshold': 0.30,
        'description': 'Large system: weighted, threshold=0.30, N128',
    },
    'D_long_run': {
        'N0': 72, 'steps': 800, 'sample_interval': 5, 'p1_eval_interval': 5,
        'coupling_mode': 'weighted', 'coupling_threshold': 0.30,
        'description': 'Long run: weighted, threshold=0.30, N72, 800 steps — break point detection',
    },
}


# ─── Break Point Detection ───

def detect_break_points(series: np.ndarray, window: int = 20, threshold: float = 2.0) -> List[int]:
    """使用滑动窗口检测时间序列的突变点（自指断点）。
    
    方法：计算窗口内斜率的变化率，超过阈值则判定为断点。
    """
    if len(series) < window * 2:
        return []
    
    # 计算局部斜率
    slopes = []
    for i in range(len(series) - window + 1):
        window_data = series[i:i + window]
        x = np.arange(window)
        if np.std(window_data) < 1e-10:
            slopes.append(0)
            continue
        # 线性拟合
        slope, _ = np.polyfit(x, window_data, 1)
        slopes.append(slope)
    
    slopes = np.array(slopes)
    
    # 检测斜率突变
    slope_changes = np.abs(np.diff(slopes))
    mean_change = np.mean(slope_changes)
    std_change = np.std(slope_changes)
    
    break_points = []
    for i, change in enumerate(slope_changes):
        if change > mean_change + threshold * std_change and change > 0.01:
            break_points.append(i + window)  # 转换为原始序列索引
    
    return break_points


def compute_rolling_correlation(x: np.ndarray, y: np.ndarray, window: int = 30) -> np.ndarray:
    """计算滚动相关系数。"""
    if len(x) < window or len(y) < window:
        return np.array([])
    
    correlations = []
    for i in range(len(x) - window + 1):
        wx, wy = x[i:i + window], y[i:i + window]
        if np.std(wx) < 1e-10 or np.std(wy) < 1e-10:
            correlations.append(0)
        else:
            correlations.append(np.corrcoef(wx, wy)[0, 1])
    
    return np.array(correlations)


# ─── Run Single Configuration ───

def run_config(name: str, cfg: dict, n_runs: int = 3) -> Dict:
    """运行单个配置多次，收集 MSI-ODI-叙事联合数据。"""
    all_runs = []
    
    for run_id in range(n_runs):
        print(f"  [{name}] Run {run_id + 1}/{n_runs}...")
        torch.manual_seed(42 + run_id)
        np.random.seed(42 + run_id)
        
        # 初始化组件
        narrative_op = NarrativeRecursionOperator(
            max_chain_length=8,
            min_signal_amplitude=0.05,
            max_signals_per_step=32,
        )
        
        evolver = HierarchicalEvolver(
            N0=cfg["N0"],
            steps_per_layer=cfg["steps"],
            sample_interval=cfg["sample_interval"],
            max_layers=1,
            p1_eval_interval=cfg["p1_eval_interval"],
            persistent_bias_memory=PersistentBiasMemory(),
            cumulative_selector=CumulativeSelector(window_size=20),
            coupling_mode=cfg["coupling_mode"],
            coupling_threshold=cfg["coupling_threshold"],
            narrative_recursion_operator=narrative_op,
        )
        
        # 采样容器
        samples = {
            'step': [],
            'msi': [],
            'odi': [],
            'narrative_magnitude': [],  # ||ΔB_narrative||
            'narrative_level_dist': [],  # {MINI: n, INSTITUTIONAL: n, CIVILIZATION: n}
            'narrative_chain_length': [],
            'anticipation_confidence': [],
            'counterfactual_count': [],
            'bias_correction_applied': [],
        }
        
        def step_callback(state, step_idx, step_result):
            if step_idx % cfg["sample_interval"] != 0:
                return
            
            # 从 state 提取 MSI
            msi = state.get('msi', 0.0)
            
            # 计算 ODI
            diff_matrix = state.get('diff_matrix', None)
            if diff_matrix is not None:
                odi_calc = OrganizationalDensityIndex()
                odi = odi_calc.compute(diff_matrix)
            else:
                odi = 0.0
            
            # 叙事统计
            n_stats = narrative_op.get_stats()
            narrative_mag = n_stats.get('total_correction_magnitude', 0.0)
            level_dist = n_stats.get('level_distribution', {})
            chain_len = n_stats.get('avg_chain_length', 0)
            
            # 预期和反事实
            anticipation = state.get('anticipation_confidence', 0.0)
            counterfactual_count = state.get('counterfactual_activations', 0)
            bias_corrected = step_result.get('narrative_recursion', {}).get('correction_applied', False)
            
            samples['step'].append(step_idx)
            samples['msi'].append(float(msi))
            samples['odi'].append(float(odi))
            samples['narrative_magnitude'].append(float(narrative_mag))
            samples['narrative_level_dist'].append(level_dist)
            samples['narrative_chain_length'].append(float(chain_len))
            samples['anticipation_confidence'].append(float(anticipation))
            samples['counterfactual_count'].append(int(counterfactual_count))
            samples['bias_correction_applied'].append(1 if bias_corrected else 0)
        
        evolver.set_step_callback(step_callback)
        
        # 运行
        start = time.time()
        final_state = evolver.run()
        elapsed = time.time() - start
        
        # 转换为 numpy 数组用于分析
        msi_arr = np.array(samples['msi'])
        odi_arr = np.array(samples['odi'])
        narrative_mag_arr = np.array(samples['narrative_magnitude'])
        
        # 断点检测
        msi_breaks = detect_break_points(msi_arr)
        narrative_breaks = detect_break_points(narrative_mag_arr)
        
        # 相关性分析
        # 过滤掉叙事修正为 0 的点
        non_zero_mask = narrative_mag_arr > 0.01
        if np.sum(non_zero_mask) >= 10:
            odo_narrative_corr = np.corrcoef(odi_arr[non_zero_mask], narrative_mag_arr[non_zero_mask])[0, 1]
        else:
            odo_narrative_corr = 0.0
        
        # MSI 增速分析：叙事激活前后的斜率对比
        first_narrative_step = None
        for i, mag in enumerate(narrative_mag_arr):
            if mag > 0.01:
                first_narrative_step = i
                break
        
        msi_slope_before = 0.0
        msi_slope_after = 0.0
        if first_narrative_step is not None and first_narrative_step > 5:
            before = msi_arr[:first_narrative_step]
            after = msi_arr[first_narrative_step:]
            if len(before) >= 5:
                x_before = np.arange(len(before))
                msi_slope_before = float(np.polyfit(x_before, before, 1)[0])
            if len(after) >= 5:
                x_after = np.arange(len(after))
                msi_slope_after = float(np.polyfit(x_after, after, 1)[0])
        
        # 叙事层级迁移分析
        level_migration = {}
        if len(samples['narrative_level_dist']) >= 10:
            half = len(samples['narrative_level_dist']) // 2
            early = samples['narrative_level_dist'][:half]
            late = samples['narrative_level_dist'][half:]
            
            for level in ['MINI', 'INSTITUTIONAL', 'CIVILIZATION']:
                early_count = sum(1 for d in early if d.get(level, 0) > 0)
                late_count = sum(1 for d in late if d.get(level, 0) > 0)
                level_migration[level] = {
                    'early_ratio': early_count / max(len(early), 1),
                    'late_ratio': late_count / max(len(late), 1),
                    'shift': (late_count - early_count) / max(len(early), 1),
                }
        
        run_data = {
            'run_id': run_id,
            'elapsed_seconds': round(elapsed, 2),
            'samples': samples,
            'analysis': {
                'msi_final': float(msi_arr[-1]) if len(msi_arr) > 0 else 0,
                'msi_max': float(np.max(msi_arr)) if len(msi_arr) > 0 else 0,
                'msi_mean': float(np.mean(msi_arr)) if len(msi_arr) > 0 else 0,
                'odi_final': float(odi_arr[-1]) if len(odi_arr) > 0 else 0,
                'odi_max': float(np.max(odi_arr)) if len(odi_arr) > 0 else 0,
                'narrative_max_magnitude': float(np.max(narrative_mag_arr)) if len(narrative_mag_arr) > 0 else 0,
                'narrative_activations': int(np.sum(narrative_mag_arr > 0.01)),
                'odi_narrative_correlation': round(float(odo_narrative_corr), 4),
                'msi_break_points': msi_breaks,
                'narrative_break_points': narrative_breaks,
                'msi_slope_before_narrative': round(msi_slope_before, 6),
                'msi_slope_after_narrative': round(msi_slope_after, 6),
                'msi_slope_acceleration': round((msi_slope_after - msi_slope_before) / max(abs(msi_slope_before), 1e-10), 2) if msi_slope_before != 0 else 0,
                'level_migration': level_migration,
                'anticipation_final': float(samples['anticipation_confidence'][-1]) if samples['anticipation_confidence'] else 0,
                'counterfactual_total': int(samples['counterfactual_count'][-1]) if samples['counterfactual_count'] else 0,
            }
        }
        all_runs.append(run_data)
        print(f"    MSI={run_data['analysis']['msi_final']:.4f} ODI={run_data['analysis']['odi_final']:.4f} "
              f"Narrative activations={run_data['analysis']['narrative_activations']} "
              f"ODI-Narrative r={run_data['analysis']['odi_narrative_correlation']:.4f}")
    
    return {'config': name, 'runs': all_runs}


# ─── Main ───

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'experiments/exp_74_results_{timestamp}.json'
    
    print(f"=" * 70)
    print(f"exp_74: MSI-ODI-叙事联合追踪实验")
    print(f"Time: {timestamp}")
    print(f"=" * 70)
    
    all_results = {}
    
    for name, cfg in CONFIGS.items():
        print(f"\n--- {name}: {cfg['description']} ---")
        result = run_config(name, cfg, n_runs=3)
        all_results[name] = result
    
    # 汇总分析
    summary = {
        'experiment': 'exp_74_msi_odi_narrative_joint_tracking',
        'timestamp': timestamp,
        'configurations': {},
        'cross_config_analysis': {},
    }
    
    for name, result in all_results.items():
        runs = result['runs']
        avg_msi = np.mean([r['analysis']['msi_final'] for r in runs])
        avg_odi = np.mean([r['analysis']['odi_final'] for r in runs])
        avg_corr = np.mean([r['analysis']['odi_narrative_correlation'] for r in runs])
        avg_narrative_activations = np.mean([r['analysis']['narrative_activations'] for r in runs])
        avg_slope_acc = np.mean([r['analysis']['msi_slope_acceleration'] for r in runs])
        
        summary['configurations'][name] = {
            'description': CONFIGS[name]['description'],
            'avg_msi_final': round(float(avg_msi), 4),
            'avg_odi_final': round(float(avg_odi), 4),
            'avg_odi_narrative_correlation': round(float(avg_corr), 4),
            'avg_narrative_activations': round(float(avg_narrative_activations), 1),
            'avg_msi_slope_acceleration': round(float(avg_slope_acc), 2),
            'n_runs': len(runs),
        }
    
    # 跨配置分析
    # 1. ODI-叙事相关性是否在所有配置中都显著？
    correlations = {k: v['avg_odi_narrative_correlation'] for k, v in summary['configurations'].items()}
    significant_configs = [k for k, v in correlations.items() if abs(v) > 0.4]
    
    # 2. MSI 增速加速是否普遍？
    slope_accs = {k: v['avg_msi_slope_acceleration'] for k, v in summary['configurations'].items()}
    accelerated_configs = [k for k, v in slope_accs.items() if v > 0.5]
    
    summary['cross_config_analysis'] = {
        'odi_narrative_correlation': {
            'values': correlations,
            'significant_configs': significant_configs,
            'acceptance': len(significant_configs) >= 2,
        },
        'msi_slope_acceleration': {
            'values': slope_accs,
            'accelerated_configs': accelerated_configs,
            'acceptance': len(accelerated_configs) >= 2,
        },
        'acceptance_summary': {
            'c1_odi_narrative_corr': len(significant_configs) >= 2,
            'c2_break_point_detected': any(
                len(r['analysis'].get('narrative_break_points', [])) > 0
                for cfg in all_results.values() for r in cfg['runs']
            ),
            'c3_msi_acceleration': len(accelerated_configs) >= 2,
            'c4_level_migration': _check_level_migration(all_results),
        }
    }
    
    # 保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    
    # 打印摘要
    print(f"\n{'=' * 70}")
    print(f"实验摘要")
    print(f"{'=' * 70}")
    for name, s in summary['configurations'].items():
        print(f"\n  {name}:")
        print(f"    MSI_final={s['avg_msi_final']} ODI_final={s['avg_odi_final']}")
        print(f"    ODI-Narrative r={s['avg_odi_narrative_correlation']} "
              f"Narrative activations={s['avg_narrative_activations']}")
        print(f"    MSI slope acceleration={s['avg_msi_slope_acceleration']}")
    
    acc = summary['cross_config_analysis']['acceptance_summary']
    print(f"\n{'=' * 70}")
    print(f"接受标准:")
    print(f"  C1 ODI-叙事相关 |r|>0.4 (≥2 配置): {acc['c1_odi_narrative_corr']} "
          f"({len(significant_configs)} 配置)")
    print(f"  C2 检测到自指断点: {acc['c2_break_point_detected']}")
    print(f"  C3 MSI 增速加速 >50% (≥2 配置): {acc['c3_msi_acceleration']} "
          f"({len(accelerated_configs)} 配置)")
    print(f"  C4 叙事层级迁移: {acc['c4_level_migration']}")
    print(f"\n结果文件: {output_file}")
    print(f"{'=' * 70}")


def _check_level_migration(all_results: Dict) -> bool:
    """检查叙事层级是否出现从 MINI 向更高层的迁移。"""
    for cfg_name, cfg_data in all_results.items():
        for run in cfg_data['runs']:
            migration = run['analysis'].get('level_migration', {})
            for level, stats in migration.items():
                if level in ('INSTITUTIONAL', 'CIVILIZATION') and stats.get('shift', 0) > 0.1:
                    return True
    return False


if __name__ == '__main__':
    main()
