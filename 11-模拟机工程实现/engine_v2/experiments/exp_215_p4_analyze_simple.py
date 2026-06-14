"""
exp_215 Phase 23 P4 叙事递归轨迹分析 (简化版)

任务:
1. 量化 H23-4e: 叙事递归轨迹呈现螺旋上升模式
2. 可视化叙事递归轨迹
"""

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 非交互后端
import matplotlib.pyplot as plt
from pathlib import Path
import sys

# 配置
RESULTS_FILE = "../results/exp_215_p4_narrative_v2.json"
OUTPUT_DIR = "../results/analysis"

def load_results(filepath):
    """加载实验结果"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_narrative_trajectory(results):
    """
    分析叙事递归轨迹

    返回:
    - layers_data: 每层的指标 (entropy, delta, n_rounds)
    - inter_layer_diffs: 层间差异度
    """
    G5_data = results['results']['G5']['results']

    all_layers_data = []
    inter_layer_diffs = []

    for seed_idx, seed_data in enumerate(G5_data):
        if 'narrative_history' not in seed_data:
            continue

        history = seed_data['narrative_history']
        seed_layers = []

        for layer_data in history:
            spiral = layer_data['spiral']
            seed_layers.append({
                'seed': seed_idx,
                'layer': layer_data['layer'],
                'entropy_mean': spiral['entropy_mean'],
                'delta_mean': spiral['delta_mean'],
                'delta_std': spiral['delta_std'],
                'n_rounds': spiral['n_rounds'],
                'entropy_trend': spiral['entropy_trend']
            })

        # 计算相邻层差异
        for i in range(len(seed_layers) - 1):
            l1 = seed_layers[i]
            l2 = seed_layers[i + 1]
            diff = abs(l2['entropy_mean'] - l1['entropy_mean']) + \
                   abs(l2['delta_mean'] - l1['delta_mean'])
            inter_layer_diffs.append(diff)

        all_layers_data.extend(seed_layers)

    return all_layers_data, inter_layer_diffs

def calculate_random_baseline(n_samples=100, n_layers=5):
    """计算随机基线"""
    np.random.seed(42)

    random_diffs = []
    for _ in range(n_samples):
        # 随机生成每层指标
        random_metrics = np.random.rand(n_layers, 2)

        # 计算相邻层差异
        for i in range(n_layers - 1):
            diff = np.sum(np.abs(random_metrics[i+1] - random_metrics[i]))
            random_diffs.append(diff)

    return {
        'mean': np.mean(random_diffs),
        'std': np.std(random_diffs),
        'values': random_diffs
    }

def visualize(results, output_dir):
    """生成可视化"""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    G5_data = results['results']['G5']['results']

    # 图1: 熵逐层下降
    fig, ax = plt.subplots(figsize=(10, 6))

    for seed_idx, seed_data in enumerate(G5_data):
        if 'narrative_history' not in seed_data:
            continue

        history = seed_data['narrative_history']
        layers = [h['layer'] for h in history]
        entropies = [h['spiral']['entropy_mean'] for h in history]
        ax.plot(layers, entropies, 'o-', label=f'Seed {seed_idx}', linewidth=2, markersize=8)

    ax.set_xlabel('Layer', fontsize=12)
    ax.set_ylabel('Entropy Mean', fontsize=12)
    ax.set_title('Narrative Recursion: Entropy Trajectory', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/entropy_trajectory.png", dpi=150)
    print(f"Saved: {output_dir}/entropy_trajectory.png")
    plt.close()

    # 图2: Delta 轨迹
    fig, ax = plt.subplots(figsize=(10, 6))

    for seed_idx, seed_data in enumerate(G5_data):
        if 'narrative_history' not in seed_data:
            continue

        history = seed_data['narrative_history']
        layers = [h['layer'] for h in history]
        deltas = [h['spiral']['delta_mean'] for h in history]
        ax.plot(layers, deltas, 's-', label=f'Seed {seed_idx}', linewidth=2, markersize=8)

    ax.set_xlabel('Layer', fontsize=12)
    ax.set_ylabel('Delta Mean', fontsize=12)
    ax.set_title('Narrative Recursion: Delta Trajectory', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/delta_trajectory.png", dpi=150)
    print(f"Saved: {output_dir}/delta_trajectory.png")
    plt.close()

    # 图3: 层间差异度对比
    all_layers_data, inter_layer_diffs = analyze_narrative_trajectory(results)
    random_baseline = calculate_random_baseline()

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.hist(inter_layer_diffs, bins=15, alpha=0.7, color='blue',
            label=f'G5 (Narrative) - Mean={np.mean(inter_layer_diffs):.3f}', edgecolor='black')
    ax.axvline(np.mean(inter_layer_diffs), color='blue', linestyle='--', linewidth=2)

    ax.axvline(random_baseline['mean'], color='red', linestyle='--', linewidth=2,
               label=f'Random Baseline - Mean={random_baseline["mean"]:.3f}')

    ax.set_xlabel('Inter-Layer Difference', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title('H23-4e: Inter-Layer Difference Distribution', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/inter_layer_diff_comparison.png", dpi=150)
    print(f"Saved: {output_dir}/inter_layer_diff_comparison.png")
    plt.close()

    return inter_layer_diffs, random_baseline

def verify_H23_4e(inter_layer_diffs, random_baseline):
    """
    验证 H23-4e

    假设: 叙事递归轨迹呈现螺旋上升模式（相邻层内容差异 > 随机基线）
    """
    from scipy import stats

    g5_mean = np.mean(inter_layer_diffs)
    random_mean = random_baseline['mean']

    # 单尾 t-test (G5 > Random)
    t_stat, p_value = stats.ttest_ind(
        inter_layer_diffs,
        random_baseline['values'],
        equal_var=False,
        alternative='greater'
    )

    passed = g5_mean > random_mean and p_value < 0.05

    print("\n" + "="*70)
    print("H23-4e Verification: Narrative Spiral Pattern")
    print("="*70)
    print(f"G5 Inter-Layer Diff Mean:    {g5_mean:.4f} +/- {np.std(inter_layer_diffs):.4f}")
    print(f"Random Baseline Mean:        {random_mean:.4f} +/- {random_baseline['std']:.4f}")
    print(f"Difference (G5 - Random):    {g5_mean - random_mean:.4f}")
    print(f"t-statistic:                 {t_stat:.4f}")
    print(f"p-value (one-tailed):        {p_value:.4f}")
    print(f"\nVerdict: {'PASS' if passed else 'FAIL'}")
    print("="*70)

    return {
        'hypothesis': 'H23-4e',
        'description': 'Narrative recursion trajectory shows spiral pattern (inter-layer diff > random)',
        'passed': passed,
        'g5_mean': float(g5_mean),
        'random_mean': float(random_mean),
        'difference': float(g5_mean - random_mean),
        'p_value': float(p_value),
        't_statistic': float(t_stat),
        'inter_layer_diffs': [float(x) for x in inter_layer_diffs],
        'random_baseline': random_baseline
    }

def main():
    print("="*70)
    print("Phase 23 P4: Narrative Recursion Trajectory Analysis (Simple)")
    print("="*70)

    # 1. 加载数据
    print(f"\n[1] Loading results from {RESULTS_FILE}...")
    results = load_results(RESULTS_FILE)
    print(f"Loaded: {results['experiment']}")

    # 2. 可视化
    print("\n[2] Generating visualizations...")
    inter_layer_diffs, random_baseline = visualize(results, OUTPUT_DIR)

    # 3. 验证 H23-4e
    print("\n[3] Verifying H23-4e hypothesis...")
    verification = verify_H23_4e(inter_layer_diffs, random_baseline)

    # 4. 保存结果
    output_file = f"{OUTPUT_DIR}/h23_4e_verification.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(verification, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {output_file}")

    print("\n" + "="*70)
    print("Analysis Complete!")
    print("="*70)

if __name__ == "__main__":
    main()
