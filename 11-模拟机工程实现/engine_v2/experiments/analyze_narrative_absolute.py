"""
exp_215 Phase 23 P4 叙事递归轨迹分析 (绝对路径版)
"""

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import stats

# 使用绝对路径
RESULTS_FILE = r"C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现\engine_v2\results\exp_215_p4_narrative_v2.json"
OUTPUT_DIR = r"C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现\engine_v2\results\analysis"

def load_results(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_narrative_metrics(results):
    """提取 G5 的叙事递归指标"""
    G5_data = results['results']['G5']['results']

    all_metrics = []
    for seed_data in G5_data:
        if 'narrative_history' not in seed_data:
            continue

        seed = seed_data['seed']
        for layer_data in seed_data['narrative_history']:
            spiral = layer_data['spiral']
            all_metrics.append({
                'seed': seed,
                'layer': layer_data['layer'],
                'entropy_mean': spiral['entropy_mean'],
                'delta_mean': spiral['delta_mean'],
                'delta_std': spiral['delta_std'],
                'n_rounds': spiral['n_rounds'],
                'entropy_trend': spiral['entropy_trend']
            })

    return all_metrics

def calculate_inter_layer_differences(metrics):
    """计算层间差异度"""
    diffs = []

    # 按 seed 分组
    seeds = {}
    for m in metrics:
        if m['seed'] not in seeds:
            seeds[m['seed']] = []
        seeds[m['seed']].append(m)

    # 计算每对相邻层的差异
    for seed, seed_metrics in seeds.items():
        seed_metrics_sorted = sorted(seed_metrics, key=lambda x: x['layer'])
        for i in range(len(seed_metrics_sorted) - 1):
            l1 = seed_metrics_sorted[i]
            l2 = seed_metrics_sorted[i + 1]
            diff = abs(l2['entropy_mean'] - l1['entropy_mean']) + \
                   abs(l2['delta_mean'] - l1['delta_mean'])
            diffs.append(diff)

    return diffs

def random_baseline(n_samples=1000, n_layers=5):
    """生成随机基线"""
    np.random.seed(42)
    random_diffs = []

    for _ in range(n_samples):
        random_metrics = np.random.rand(n_layers, 2)
        for i in range(n_layers - 1):
            diff = np.sum(np.abs(random_metrics[i+1] - random_metrics[i]))
            random_diffs.append(diff)

    return random_diffs

def visualize(metrics, inter_layer_diffs, random_diffs, output_dir):
    """生成可视化"""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 图1: 熵轨迹
    fig, ax = plt.subplots(figsize=(10, 6))
    seeds = {}
    for m in metrics:
        if m['seed'] not in seeds:
            seeds[m['seed']] = {'layers': [], 'entropies': []}
        seeds[m['seed']]['layers'].append(m['layer'])
        seeds[m['seed']]['entropies'].append(m['entropy_mean'])

    for seed, data in seeds.items():
        ax.plot(data['layers'], data['entropies'], 'o-', label=f'Seed {seed}', linewidth=2, markersize=8)

    ax.set_xlabel('Layer', fontsize=12)
    ax.set_ylabel('Entropy Mean', fontsize=12)
    ax.set_title('Narrative Recursion: Entropy Trajectory', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/entropy_trajectory.png", dpi=150)
    print(f"Saved: entropy_trajectory.png")
    plt.close()

    # 图2: Delta 轨迹
    fig, ax = plt.subplots(figsize=(10, 6))
    for seed, data in seeds.items():
        deltas = [m['delta_mean'] for m in metrics if m['seed'] == seed]
        layers = sorted(set(m['layer'] for m in metrics if m['seed'] == seed))
        ax.plot(layers, deltas, 's-', label=f'Seed {seed}', linewidth=2, markersize=8)

    ax.set_xlabel('Layer', fontsize=12)
    ax.set_ylabel('Delta Mean', fontsize=12)
    ax.set_title('Narrative Recursion: Delta Trajectory', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/delta_trajectory.png", dpi=150)
    print(f"Saved: delta_trajectory.png")
    plt.close()

    # 图3: 层间差异对比
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(inter_layer_diffs, bins=15, alpha=0.7, color='blue',
            label=f'G5 (Narrative) Mean={np.mean(inter_layer_diffs):.3f}', edgecolor='black')
    ax.axvline(np.mean(inter_layer_diffs), color='blue', linestyle='--', linewidth=2)

    ax.axvline(np.mean(random_diffs), color='red', linestyle='--', linewidth=2,
               label=f'Random Baseline Mean={np.mean(random_diffs):.3f}')

    ax.set_xlabel('Inter-Layer Difference', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title('H23-4e: Inter-Layer Difference Comparison', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/inter_layer_diff_comparison.png", dpi=150)
    print(f"Saved: inter_layer_diff_comparison.png")
    plt.close()

def verify_hypothesis(inter_layer_diffs, random_diffs):
    """验证 H23-4e"""
    g5_mean = np.mean(inter_layer_diffs)
    random_mean = np.mean(random_diffs)

    # 单尾 t-test
    t_stat, p_value = stats.ttest_ind(
        inter_layer_diffs,
        random_diffs,
        equal_var=False,
        alternative='greater'
    )

    passed = g5_mean > random_mean and p_value < 0.05

    print("\n" + "="*70)
    print("H23-4e Verification: Narrative Spiral Pattern")
    print("="*70)
    print(f"G5 Inter-Layer Diff Mean: {g5_mean:.4f} +/- {np.std(inter_layer_diffs):.4f}")
    print(f"Random Baseline Mean:     {random_mean:.4f} +/- {np.std(random_diffs):.4f}")
    print(f"Difference (G5 - Random):  {g5_mean - random_mean:.4f}")
    print(f"t-statistic:              {t_stat:.4f}")
    print(f"p-value (one-tailed):     {p_value:.4f}")
    print(f"\nVerdict: {'PASS' if passed else 'FAIL'}")
    print("="*70)

    return {
        'hypothesis': 'H23-4e',
        'description': 'Narrative recursion trajectory shows spiral pattern',
        'passed': bool(passed),
        'g5_mean': float(g5_mean),
        'random_mean': float(random_mean),
        'difference': float(g5_mean - random_mean),
        'p_value': float(p_value),
        't_statistic': float(t_stat)
    }

def main():
    print("="*70)
    print("Phase 23 P4: Narrative Trajectory Analysis")
    print("="*70)

    # 1. 加载数据
    print(f"\n[1] Loading: {RESULTS_FILE}")
    results = load_results(RESULTS_FILE)
    print(f"Loaded: {results['experiment']}")

    # 2. 提取指标
    print("\n[2] Extracting narrative metrics...")
    metrics = extract_narrative_metrics(results)
    print(f"Extracted {len(metrics)} layer records from G5")

    # 3. 计算层间差异
    print("\n[3] Calculating inter-layer differences...")
    inter_layer_diffs = calculate_inter_layer_differences(metrics)
    print(f"Calculated {len(inter_layer_diffs)} inter-layer differences")

    # 4. 随机基线
    print("\n[4] Generating random baseline...")
    random_diffs = random_baseline()
    print(f"Generated {len(random_diffs)} random samples")

    # 5. 可视化
    print("\n[5] Generating visualizations...")
    visualize(metrics, inter_layer_diffs, random_diffs, OUTPUT_DIR)

    # 6. 验证假设
    print("\n[6] Verifying H23-4e...")
    verification = verify_hypothesis(inter_layer_diffs, random_diffs)

    # 7. 保存
    output_file = f"{OUTPUT_DIR}/h23_4e_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(verification, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {output_file}")

    print("\n" + "="*70)
    print("Analysis Complete!")
    print("="*70)

if __name__ == "__main__":
    main()
