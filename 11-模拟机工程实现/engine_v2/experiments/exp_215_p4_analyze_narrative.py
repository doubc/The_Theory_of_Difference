"""
exp_215 Phase 23 P4 叙事递归轨迹分析

任务:
1. 量化 H23-4e: 叙事递归轨迹呈现螺旋上升模式（相邻层内容差异 > 随机基线）
2. 可视化叙事递归轨迹

假设 H23-4e:
- 叙事递归轨迹呈现螺旋上升模式
- 相邻层内容差异 > 随机基线
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# 配置
import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(SCRIPT_DIR, "..", "results", "exp_215_p4_narrative_v2.json")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "results", "analysis")

def load_results(filepath):
    """加载实验结果"""
    with open(filepath, 'r') as f:
        return json.load(f)

def calculate_inter_layer_difference(results):
    """
    计算层间差异度 (H23-4e 量化)

    方法:
    1. 提取每层的叙事递归历史 (narrative_history)
    2. 计算相邻层之间的轨迹差异
    3. 与随机基线对比
    """
    G5_data = results['results']['G5']['results']

    inter_layer_diffs = []
    entropy_trajectories = []
    delta_trajectories = []

    for seed_data in G5_data:
        if 'narrative_history' not in seed_data:
            continue

        history = seed_data['narrative_history']

        # 提取每层的熵均值和 delta 均值
        layer_metrics = []
        for layer_data in history:
            spiral = layer_data['spiral']
            layer_metrics.append({
                'layer': layer_data['layer'],
                'entropy_mean': spiral['entropy_mean'],
                'delta_mean': spiral['delta_mean'],
                'delta_std': spiral['delta_std'],
                'n_rounds': spiral['n_rounds'],
                'entropy_trend': spiral['entropy_trend']
            })

        # 计算相邻层差异
        for i in range(len(layer_metrics) - 1):
            l1 = layer_metrics[i]
            l2 = layer_metrics[i + 1]

            # 差异度 = |熵均值差| + |delta均值差|
            diff = abs(l2['entropy_mean'] - l1['entropy_mean']) + \
                   abs(l2['delta_mean'] - l1['delta_mean'])
            inter_layer_diffs.append(diff)

        # 保存轨迹数据
        entropy_trajectories.append([m['entropy_mean'] for m in layer_metrics])
        delta_trajectories.append([m['delta_mean'] for m in layer_metrics])

    return {
        'inter_layer_diffs': inter_layer_diffs,
        'entropy_trajectories': entropy_trajectories,
        'delta_trajectories': delta_trajectories,
        'mean_diff': np.mean(inter_layer_diffs) if inter_layer_diffs else 0,
        'std_diff': np.std(inter_layer_diffs) if inter_layer_diffs else 0
    }

def calculate_random_baseline(n_seeds=5, n_layers=5):
    """
    计算随机基线

    随机基线 = 随机生成层间差异的均值
    """
    np.random.seed(42)

    random_diffs = []
    for _ in range(n_seeds):
        # 随机生成每层的两个指标 (entropy, delta)
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

def visualize_narrative_trajectory(results, output_dir):
    """
    可视化叙事递归轨迹
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    G5_data = results['results']['G5']['results']

    # 图1: 熵逐层下降轨迹 (所有 seeds)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1.1 熵均值逐层变化
    ax = axes[0, 0]
    for seed_data in G5_data:
        if 'narrative_history' in seed_data:
            history = seed_data['narrative_history']
            layers = [h['layer'] for h in history]
            entropies = [h['spiral']['entropy_mean'] for h in history]
            ax.plot(layers, entropies, 'o-', alpha=0.6)

    ax.set_xlabel('Layer')
    ax.set_ylabel('Entropy Mean')
    ax.set_title('Entropy Trajectory (All Seeds)')
    ax.grid(True, alpha=0.3)

    # 1.2 Delta 均值逐层变化
    ax = axes[0, 1]
    for seed_data in G5_data:
        if 'narrative_history' in seed_data:
            history = seed_data['narrative_history']
            layers = [h['layer'] for h in history]
            deltas = [h['spiral']['delta_mean'] for h in history]
            ax.plot(layers, deltas, 'o-', alpha=0.6)

    ax.set_xlabel('Layer')
    ax.set_ylabel('Delta Mean')
    ax.set_title('Delta Trajectory (All Seeds)')
    ax.grid(True, alpha=0.3)

    # 1.3 单种子详细递归轮次 (Seed 0, Layer 0)
    ax = axes[1, 0]
    if 'narrative_history' in G5_data[0]:
        layer_0 = G5_data[0]['narrative_history'][0]
        history = layer_0['history']

        rounds = [h['round'] for h in history]
        deltas = [h['delta'] for h in history]
        entropies = [h['high_entropy'] for h in history]

        ax.plot(rounds, deltas, 'o-', label='Delta', linewidth=2)
        ax.set_xlabel('Recursion Round')
        ax.set_ylabel('Delta', color='blue')
        ax.tick_params(axis='y', labelcolor='blue')
        ax.grid(True, alpha=0.3)

        ax2 = ax.twinx()
        ax2.plot(rounds, entropies, 'o--', color='red', alpha=0.6, label='High Entropy')
        ax2.set_ylabel('High Entropy Bits', color='red')
        ax2.tick_params(axis='y', labelcolor='red')

        ax.set_title('Seed 0, Layer 0: Recursion Rounds')

    # 1.4 层间差异度分布
    ax = axes[1, 1]
    analysis = calculate_inter_layer_difference(results)
    random_baseline = calculate_random_baseline()

    ax.hist(analysis['inter_layer_diffs'], bins=10, alpha=0.7, label='G5 (Narrative)', edgecolor='black')
    ax.axvline(analysis['mean_diff'], color='blue', linestyle='--', linewidth=2,
               label=f'G5 Mean = {analysis["mean_diff"]:.3f}')
    ax.axvline(random_baseline['mean'], color='red', linestyle='--', linewidth=2,
               label=f'Random Mean = {random_baseline["mean"]:.3f}')

    ax.set_xlabel('Inter-Layer Difference')
    ax.set_ylabel('Frequency')
    ax.set_title('H23-4e: Inter-Layer Difference Distribution')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/narrative_trajectory_analysis.png", dpi=150)
    print(f"✓ Saved: {output_dir}/narrative_trajectory_analysis.png")

    # 图2: 螺旋递归模式可视化 (Spiral Pattern)
    fig2, ax2 = plt.subplots(figsize=(10, 6))

    # 使用 Seed 0 的所有层
    if 'narrative_history' in G5_data[0]:
        for layer_data in G5_data[0]['narrative_history']:
            layer = layer_data['layer']
            history = layer_data['history']

            rounds = [h['round'] for h in history]
            deltas = [h['delta'] for h in history]

            ax2.plot(rounds, deltas, 'o-', label=f'L{layer}', linewidth=2, markersize=8)

    ax2.set_xlabel('Recursion Round')
    ax2.set_ylabel('Delta (Content Difference)')
    ax2.set_title('Spiral Recursion Pattern (Seed 0, All Layers)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/spiral_recursion_pattern.png", dpi=150)
    print(f"✓ Saved: {output_dir}/spiral_recursion_pattern.png")

    return analysis, random_baseline

def verify_H23_4e(analysis, random_baseline):
    """
    验证 H23-4e 假设

    H23-4e: 叙事递归轨迹呈现螺旋上升模式（相邻层内容差异 > 随机基线）

    判定标准:
    - G5 层间差异均值 > 随机基线均值
    """
    g5_mean = analysis['mean_diff']
    random_mean = random_baseline['mean']

    # 使用 t-test 比较
    from scipy import stats

    t_stat, p_value = stats.ttest_ind(
        analysis['inter_layer_diffs'],
        random_baseline['values'],
        equal_var=False
    )

    passed = g5_mean > random_mean and p_value < 0.05

    print("\n" + "="*60)
    print("H23-4e Verification: Narrative Spiral Pattern")
    print("="*60)
    print(f"G5 Inter-Layer Difference Mean: {g5_mean:.4f} ± {analysis['std_diff']:.4f}")
    print(f"Random Baseline Mean:            {random_mean:.4f} ± {random_baseline['std']:.4f}")
    print(f"t-statistic: {t_stat:.4f}")
    print(f"p-value: {p_value:.4f}")
    print(f"Verdict: {'✓ PASS' if passed else '✗ FAIL'}")
    print("="*60)

    return {
        'hypothesis': 'H23-4e',
        'passed': passed,
        'g5_mean': g5_mean,
        'random_mean': random_mean,
        'p_value': p_value,
        't_statistic': t_stat
    }

def main():
    print("="*60)
    print("Phase 23 P4: Narrative Recursion Trajectory Analysis")
    print("="*60)

    # 1. 加载数据
    print(f"\n[1] Loading results from {RESULTS_FILE}...")
    results = load_results(RESULTS_FILE)
    print(f"✓ Loaded. Experiment: {results['experiment']}")

    # 2. 量化 H23-4e
    print("\n[2] Quantifying H23-4e (inter-layer differences)...")
    analysis = calculate_inter_layer_difference(results)

    # 3. 计算随机基线
    print("[3] Calculating random baseline...")
    random_baseline = calculate_random_baseline()

    # 4. 可视化
    print("\n[4] Generating visualizations...")
    analysis, random_baseline = visualize_narrative_trajectory(results, OUTPUT_DIR)

    # 5. 验证假设
    verification = verify_H23_4e(analysis, random_baseline)

    # 6. 保存分析结果
    output_file = f"{OUTPUT_DIR}/h23_4e_verification.json"
    with open(output_file, 'w') as f:
        json.dump({
            'hypothesis': 'H23-4e',
            'description': 'Narrative recursion trajectory shows spiral pattern',
            'verification': verification,
            'analysis': {
                'inter_layer_diffs': analysis['inter_layer_diffs'],
                'mean_diff': analysis['mean_diff'],
                'std_diff': analysis['std_diff']
            },
            'random_baseline': random_baseline
        }, f, indent=2)
    print(f"\n✓ Saved verification results: {output_file}")

    print("\n" + "="*60)
    print("Analysis Complete!")
    print("="*60)

if __name__ == "__main__":
    main()
