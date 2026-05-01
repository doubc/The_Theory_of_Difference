"""
RH-035 对照实验
读取本地缓存，用相同振幅框架对比三组频率的预测精度：
  组A：莫比乌斯谱零点 γ_mn
  组B：黎曼零点虚部  γ_k^(RH)
  组C：随机对照频率

实验设计原则：
  - 三组使用完全相同的振幅函数和阻尼，只替换频率
  - 主项固定（高阶渐近展开），振荡项单独计算贡献
  - 对照组C是零假设：如果A≈C，说明振荡项无结构性贡献
"""

import numpy as np
import json
import os
from datetime import datetime

DATA_DIR = "./rh035_data"
OUTPUT_DIR = "./rh035_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────
# 加载缓存数据
# ─────────────────────────────────────────
def load_data():
    print("加载缓存数据...")
    with open(os.path.join(DATA_DIR, "rh035_primes.json")) as f:
        primes = np.array(json.load(f)["data"], dtype=np.float64)
    with open(os.path.join(DATA_DIR, "rh035_mobius_zeros.json")) as f:
        mobius_g = np.array(json.load(f)["data"], dtype=np.float64)
    with open(os.path.join(DATA_DIR, "rh035_riemann_zeros.json")) as f:
        riemann_g = np.array(json.load(f)["data"], dtype=np.float64)
    with open(os.path.join(DATA_DIR, "rh035_random_zeros.json")) as f:
        random_g = np.array(json.load(f)["data"], dtype=np.float64)
    print(f"✓ 素数：{len(primes)} 个 | 莫比乌斯零点：{len(mobius_g)} | "
          f"黎曼零点：{len(riemann_g)} | 随机频率：{len(random_g)}")
    return primes, mobius_g, riemann_g, random_g

# ─────────────────────────────────────────
# 主项：高阶渐近展开（与频率无关）
# ─────────────────────────────────────────
def main_term(n):
    """p_n 的渐近展开，到 (ln n)^{-4} 项"""
    ln = np.log(n)
    lln = np.log(ln)
    return n * (
        ln
        + lln
        - 1
        + (lln - 2) / ln
        - (lln**2 - 6*lln + 11) / (2 * ln**2)
        + (lln**3 - 9*lln**2 + 36*lln - 62) / (6 * ln**3)
        - (lln**4 - 12*lln**3 + 78*lln**2 - 240*lln + 303) / (12 * ln**4)
    )

# ─────────────────────────────────────────
# 振荡项：三组共用相同振幅，只替换频率
# ─────────────────────────────────────────
def oscillation_term(n, gammas, num_zeros=100):
    """
    振荡修正项（三组完全相同的振幅框架）
    osc = Σ_k  A_k · damp_k · cos(γ_k · ln n) / √n
    A_k = 2/(k+1)，damp_k = exp(-k/num_zeros)
    """
    ln_n = np.log(n)
    k = np.arange(min(num_zeros, len(gammas)), dtype=np.float64)
    g = gammas[:len(k)]
    amplitudes = 2.0 / (k + 1)
    damping = np.exp(-k / num_zeros)
    phases = g * ln_n
    return np.sum(amplitudes * damping * np.cos(phases)) / np.sqrt(n)

# ─────────────────────────────────────────
# 预测函数（主项 + 振荡，无拓扑修正）
# ─────────────────────────────────────────
def predict(n, gammas, num_zeros=100):
    return main_term(n) + oscillation_term(n, gammas, num_zeros)

# ─────────────────────────────────────────
# 单组验证
# ─────────────────────────────────────────
def validate_group(label, primes, gammas, n_start=10000, n_end=78498, step=50, num_zeros=100):
    """
    对 n_start ~ n_end 范围内的素数进行预测，计算误差统计
    step：采样步长（减少计算量）
    """
    indices = range(n_start, min(n_end + 1, len(primes) + 1), step)
    rel_errors = []
    main_only_errors = []  # 纯主项误差，用于分离振荡贡献

    for n in indices:
        actual = primes[n - 1]
        pred_full = predict(n, gammas, num_zeros)
        pred_main = main_term(n)

        rel_full = abs(pred_full - actual) / actual * 100
        rel_main = abs(pred_main - actual) / actual * 100

        rel_errors.append(rel_full)
        main_only_errors.append(rel_main)

    rel_errors = np.array(rel_errors)
    main_only_errors = np.array(main_only_errors)

    stats = {
        "label": label,
        "n_range": [n_start, n_end],
        "num_samples": len(rel_errors),
        "num_zeros_used": num_zeros,
        # 完整公式误差
        "mean_rel_error_%": float(np.mean(rel_errors)),
        "median_rel_error_%": float(np.median(rel_errors)),
        "std_rel_error_%": float(np.std(rel_errors)),
        "max_rel_error_%": float(np.max(rel_errors)),
        # 纯主项误差（振荡贡献的基准线）
        "main_term_only_mean_%": float(np.mean(main_only_errors)),
        # 振荡项的净改善（正值=改善，负值=恶化）
        "oscillation_improvement_%": float(np.mean(main_only_errors) - np.mean(rel_errors)),
        # 精度分布
        "within_0.1%": float(np.mean(rel_errors < 0.1) * 100),
        "within_0.5%": float(np.mean(rel_errors < 0.5) * 100),
        "within_1.0%": float(np.mean(rel_errors < 1.0) * 100),
    }
    return stats

# ─────────────────────────────────────────
# 零点数量敏感性分析
# ─────────────────────────────────────────
def sensitivity_to_num_zeros(primes, gammas_dict, n_test=50000, zero_counts=[10, 50, 100, 200, 500]):
    """
    固定 n，改变使用的零点数量，观察误差变化
    用于判断振荡项是否随零点增多而收敛
    """
    print("\n[敏感性分析] 零点数量 vs 预测误差（n=50000）...")
    actual = primes[n_test - 1]
    results = {}

    for label, gammas in gammas_dict.items():
        errors_by_k = []
        for k in zero_counts:
            pred = predict(n_test, gammas, num_zeros=k)
            rel_err = abs(pred - actual) / actual * 100
            errors_by_k.append({"num_zeros": k, "rel_error_%": float(rel_err)})
        results[label] = errors_by_k

    return results

# ─────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────
def main():
    print("=" * 65)
    print("RH-035 对照实验：莫比乌斯谱 vs 黎曼零点 vs 随机频率")
    print("=" * 65)

    primes, mobius_g, riemann_g, random_g = load_data()

    gammas_dict = {
        "A_mobius":  mobius_g,
        "B_riemann": riemann_g,
        "C_random":  random_g,
    }

    # ── 主实验：三组误差对比 ──
    print("\n[主实验] 验证范围 n=10000~78498，步长50，使用100个零点")
    results = {}
    for label, gammas in gammas_dict.items():
        print(f"  运行组 {label}...")
        stats = validate_group(label, primes, gammas,
                               n_start=10000, n_end=78498,
                               step=50, num_zeros=100)
        results[label] = stats

    # ── 打印对比表 ──
    print("\n" + "=" * 65)
    print(f"{'指标':<30} {'A_莫比乌斯':>10} {'B_黎曼':>10} {'C_随机':>10}")
    print("-" * 65)
    keys = [
        ("mean_rel_error_%",          "平均相对误差 (%)"),
        ("median_rel_error_%",        "中位数误差 (%)"),
        ("std_rel_error_%",           "误差标准差 (%)"),
        ("max_rel_error_%",           "最大误差 (%)"),
        ("main_term_only_mean_%",     "纯主项误差 (%)"),
        ("oscillation_improvement_%", "振荡项净改善 (%)"),
        ("within_0.1%",               "误差<0.1% 比例"),
        ("within_0.5%",               "误差<0.5% 比例"),
    ]
    for key, name in keys:
        va = results["A_mobius"][key]
        vb = results["B_riemann"][key]
        vc = results["C_random"][key]
        print(f"{name:<30} {va:>10.4f} {vb:>10.4f} {vc:>10.4f}")
    print("=" * 65)

    # ── 敏感性分析 ──
    sens = sensitivity_to_num_zeros(primes, gammas_dict,
                                    n_test=50000,
                                    zero_counts=[10, 50, 100, 200, 500])

    print("\n[敏感性] 零点数量 vs 误差（n=50000）")
    print(f"{'零点数':>8} {'A_莫比乌斯':>12} {'B_黎曼':>12} {'C_随机':>12}")
    print("-" * 50)
    for i, k in enumerate([10, 50, 100, 200, 500]):
        va = sens["A_mobius"][i]["rel_error_%"]
        vb = sens["B_riemann"][i]["rel_error_%"]
        vc = sens["C_random"][i]["rel_error_%"]
        print(f"{k:>8} {va:>12.4f} {vb:>12.4f} {vc:>12.4f}")

    # ── 保存结果 ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        "experiment": "RH-035 三组对照",
        "timestamp": timestamp,
        "main_results": results,
        "sensitivity_analysis": sens,
        "interpretation_guide": {
            "A≈B>>C": "莫比乌斯谱捕捉到黎曼零点结构，P0 有推进价值",
            "A≈B≈C": "振荡项无结构性贡献，精度来自主项，P0 需重新定向",
            "A>>B,C": "莫比乌斯谱有独立贡献，与黎曼零点不同但有效",
            "B>>A≈C": "黎曼零点有效，莫比乌斯谱未捕捉到正确结构",
        }
    }
    out_path = os.path.join(OUTPUT_DIR, f"rh035_comparison_{timestamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 结果已保存：{out_path}")
    print("\n解读指南：")
    for k, v in output["interpretation_guide"].items():
        print(f"  {k}  →  {v}")
    print("=" * 65)

if __name__ == "__main__":
    main()
