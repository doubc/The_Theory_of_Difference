"""
RH-037 v2 修正版（完整）
"""

import numpy as np
import json
import os
import matplotlib.pyplot as plt
from datetime import datetime

OUTPUT_DIR = "./rh037_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────
# 1. 相位场演化
# ─────────────────────────────────────────
def phase_field_evolution(N_primes=150, search_limit=2000):
    # 标准筛真值用于验证
    sieve = np.ones(search_limit, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(np.sqrt(search_limit)) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    true_primes_set = set(np.where(sieve)[0])

    # phi[n] = #{j: p_j∤n} - #{j: p_j|n}
    # 初始 k=0，phi 全为 0
    # 候选条件：phi[n] == k
    phi = np.zeros(search_limit, dtype=np.int32)

    primes = []
    contribution_log = []
    k = 0

    for step in range(N_primes):
        start = primes[-1] + 1 if primes else 2
        next_prime = None
        for n in range(start, search_limit):
            if phi[n] == k:
                next_prime = n
                break

        if next_prime is None:
            print(f"搜索范围不足，已找到 {len(primes)} 个素数，"
                  f"建议增大 search_limit（当前={search_limit}）")
            break

        p_prev = primes[-1] if primes else None
        primes.append(next_prime)
        k += 1

        # 更新相位场：next_prime 的倍数 phi -= 2
        affected = list(range(next_prime, search_limit, next_prime))
        candidates_lost = sum(1 for m in affected if phi[m] == k - 1)
        for m in affected:
            phi[m] -= 2

        gap = (next_prime - p_prev) if p_prev is not None else None

        contribution_log.append({
            "k":                k,
            "p_k":              next_prime,
            "p_prev":           p_prev,
            "gap":              gap,
            "num_affected":     len(affected),
            "candidates_lost":  candidates_lost,
            "multiples_density": len(affected) / search_limit,
            "verified_correct": next_prime in true_primes_set,
        })

    print(f"✓ 找到 {len(primes)} 个素数，最大 p = {primes[-1]}")
    print(f"  全部验证正确: {all(c['verified_correct'] for c in contribution_log)}")
    return primes, contribution_log, phi


# ─────────────────────────────────────────
# 2. 分析
# ─────────────────────────────────────────
def analyze_phase_contributions(contribution_log):
    valid = [c for c in contribution_log
             if c["gap"] is not None and c["p_prev"] is not None]
    if len(valid) < 5:
        print("有效数据不足，跳过分析")
        return {}, "（数据不足）"

    gaps      = np.array([c["gap"]               for c in valid], dtype=float)
    p_ks      = np.array([c["p_k"]               for c in valid], dtype=float)
    p_prevs   = np.array([c["p_prev"]            for c in valid], dtype=float)
    densities = np.array([c["multiples_density"]  for c in valid], dtype=float)
    affected  = np.array([c["num_affected"]        for c in valid], dtype=float)
    lost      = np.array([c["candidates_lost"]     for c in valid], dtype=float)

    def corr(x, y):
        mask = np.isfinite(x) & np.isfinite(y) & (x != 0)
        if mask.sum() < 3:
            return 0.0
        return float(np.corrcoef(x[mask], y[mask])[0, 1])

    formulas = {
        "ln(p_k)（素数定理期望）":       np.log(p_ks),
        "p_{k-1}（加法递推上界）":        p_prevs,
        "1/density（密度倒数）":          1.0 / (densities + 1e-12),
        "p_k / num_affected":            p_ks / (affected + 1e-12),
        "p_k / candidates_lost":         p_ks / (lost + 1e-12),
        "√p_k":                          np.sqrt(p_ks),
        "ln(p_k)²":                      np.log(p_ks)**2,
        "p_{k-1} × density":             p_prevs * densities,
    }

    print("\n[相位场贡献分析] gap_k 与各候选量的相关系数：")
    print(f"{'候选量':<35} {'相关系数':>10}")
    print("-" * 48)
    correlations = {}
    for name, vals in formulas.items():
        c = corr(vals, gaps)
        correlations[name] = c
        mark = " ★★★" if abs(c) > 0.8 else (" ★★" if abs(c) > 0.6 else "")
        print(f"{name:<35} {c:>10.4f}{mark}")

    best = max(correlations, key=lambda x: abs(correlations[x]))
    print(f"\n最佳候选：{best}，相关系数 = {correlations[best]:.4f}")

    # 加法递推验证
    violations = sum(1 for c in valid if c["gap"] > c["p_prev"])
    print(f"\n加法递推验证（gap <= p_prev）：{len(valid)-violations}/{len(valid)} 通过"
          f"（违反 {violations} 次）")

    # gap / ln(p_k) 统计
    ratio = gaps / np.log(p_ks)
    print(f"\ngap/ln(p_k) 统计：均值={ratio.mean():.4f}，"
          f"中位数={np.median(ratio):.4f}，std={ratio.std():.4f}")

    return correlations, best


# ─────────────────────────────────────────
# 3. 可视化
# ─────────────────────────────────────────
def visualize(primes, contribution_log, phi):
    valid = [c for c in contribution_log
             if c["gap"] is not None and c["p_prev"] is not None]

    gaps      = np.array([c["gap"]               for c in valid], dtype=float)
    p_ks      = np.array([c["p_k"]               for c in valid], dtype=float)
    p_prevs   = np.array([c["p_prev"]            for c in valid], dtype=float)
    densities = np.array([c["multiples_density"]  for c in valid], dtype=float)
    lost      = np.array([c["candidates_lost"]     for c in valid], dtype=float)

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle("RH-037 v2：相位场框架下的素数累积贡献", fontsize=13)

    # (a) 相位场快照（前300个整数）
    ax = axes[0, 0]
    limit = min(300, len(phi))
    x = np.arange(2, limit)
    phi_slice = phi[2:limit]
    k_final = len(primes)
    colors = ['green' if v == k_final else ('red' if v < 0 else 'steelblue')
              for v in phi_slice]
    ax.bar(x, phi_slice, color=colors, width=1.0, alpha=0.8)
    for p in primes:
        if p < limit:
            ax.axvline(p, color='red', lw=0.8, alpha=0.4)
    ax.set_xlabel('n')
    ax.set_ylabel('Φ_k(n)')
    ax.set_title('相位场快照（绿=候选，红线=素数）')
    ax.grid(alpha=0.3)

    # (b) gap vs p_{k-1}（加法递推）
    ax = axes[0, 1]
    ax.scatter(p_prevs, gaps, s=8, alpha=0.5, color='steelblue')
    lim = max(p_prevs)
    ax.plot([0, lim], [0, lim], 'r--', lw=1.5, label='$g_k = p_{k-1}$（上界）')
    ax.set_xlabel('$p_{k-1}$')
    ax.set_ylabel('$g_k$')
    ax.set_title('加法递推：$g_k \\leq p_{k-1}$')
    ax.legend(); ax.grid(alpha=0.3)

    # (c) gap / ln(p_k) 趋势
    ax = axes[0, 2]
    ratio = gaps / np.log(p_ks)
    ax.plot(p_ks, ratio, 'b-', lw=0.8, alpha=0.8)
    ax.axhline(1.0, color='red', ls='--', lw=1.5, label='素数定理预测=1')
    ax.axhline(ratio.mean(), color='green', ls=':', lw=1.5,
               label=f'均值={ratio.mean():.3f}')
    ax.set_xlabel('$p_k$')
    ax.set_ylabel('$g_k / \\ln(p_k)$')
    ax.set_title('间隔/ln(p_k)（趋向1=素数定理）')
    ax.legend(); ax.grid(alpha=0.3)

    # (d) 贡献密度 vs gap
    ax = axes[1, 0]
    ax.scatter(densities, gaps, s=8, alpha=0.5, color='purple')
    ax.set_xlabel('倍数密度（num_affected / search_limit）')
    ax.set_ylabel('$g_k$')
    ax.set_title('相位贡献密度 vs 间隔')
    ax.grid(alpha=0.3)

    # (e) candidates_lost vs gap
    ax = axes[1, 1]
    ax.scatter(lost, gaps, s=8, alpha=0.5, color='orange')
    ax.set_xlabel('candidates_lost（相位失效候选数）')
    ax.set_ylabel('$g_k$')
    ax.set_title('相位失效数 vs 间隔')
    ax.grid(alpha=0.3)

    # (f) 候选公式：1/density vs gap
    ax = axes[1, 2]
    pred = 1.0 / (densities + 1e-12)
    # 裁剪极端值
    clip = np.percentile(pred, 95)
    mask = pred < clip
    ax.scatter(pred[mask], gaps[mask], s=8, alpha=0.5, color='green')
    lim2 = min(pred[mask].max(), gaps[mask].max() * 2)
    ax.plot([0, lim2], [0, lim2], 'k--', lw=1.5, label='完美预测线')
    ax.set_xlabel('1/density')
    ax.set_ylabel('实际 $g_k$')
    ax.set_title('候选公式 $g_k \\approx 1/\\rho_k$')
    ax.legend(); ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "rh037_phase_v2.png")
    plt.savefig(path, dpi=150)
    print(f"✓ 图已保存: {path}")
    plt.close()


# ─────────────────────────────────────────
# 4. 主流程
# ─────────────────────────────────────────
def main():
    print("=" * 60)
    print("RH-037 v2 修正版：相位场框架下的素数累积贡献")
    print("=" * 60)

    primes, contribution_log, phi = phase_field_evolution(
        N_primes=150, search_limit=2000
    )

    correlations, best = analyze_phase_contributions(contribution_log)
    visualize(primes, contribution_log, phi)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = {
        "timestamp": ts,
        "num_primes": len(primes),
        "primes_sample": primes[:30],
        "contribution_sample": contribution_log[:20],
        "correlations": correlations,
        "best_formula": best,
        "additive_recurrence_verified": all(
            c["gap"] <= c["p_prev"]
            for c in contribution_log
            if c["gap"] is not None and c["p_prev"] is not None
        ),
    }
    path = os.path.join(OUTPUT_DIR, f"rh037_phase_v2_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✓ 结果已保存: {path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
