"""
RH-037 v2：真正使用相位场定义的素数位置实验

核心区别：
  旧版：candidates -= multiples（集合删除，Eratosthenes）
  新版：计算 Φ_k(n) = Σ e^{iπ·1[p_j|n]}，
        找 Re(Φ_k(n)) = k 的位置（相位完全对齐）

同时计算"累积贡献"：
  每新增素数 p_k，相位场在哪些位置发生了变化？
  变化量是多少？这个变化量与 p_{k+1} 的位置有何关系？
"""

import numpy as np
import json
import os
import matplotlib.pyplot as plt
from datetime import datetime

OUTPUT_DIR = "./rh037_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────
# 核心：相位场计算
# ─────────────────────────────────────────
def compute_phase_field(n, primes_so_far):
    """
    计算整数 n 在前 k 个素数下的相位场值
    Φ_k(n) = Σ_{j=1}^{k} e^{iπ · 1[p_j|n]}
           = Σ_{j=1}^{k} (-1)^{1[p_j|n]}
           = (不整除的素数数量) - (整除的素数数量)

    注意：e^{iπ·0} = 1（不整除），e^{iπ·1} = -1（整除）
    所以 Φ_k(n) = #{j: p_j∤n} - #{j: p_j|n}
    当 Φ_k(n) = k 时，n 不被任何 p_j 整除 → 候选素数
    当 Φ_k(n) = k-2m 时，n 被恰好 m 个 p_j 整除
    """
    k = len(primes_so_far)
    divides_count = sum(1 for p in primes_so_far if n % p == 0)
    not_divides_count = k - divides_count
    # Φ_k(n) = not_divides * 1 + divides * (-1)
    phi = not_divides_count - divides_count
    return phi  # 实数（因为相位只有 0 和 π）

def is_prime_by_phase(n, primes_so_far):
    """
    用相位场判断 n 是否是下一个素数候选
    条件：Φ_k(n) = k（不被任何已知素数整除）
    """
    k = len(primes_so_far)
    return compute_phase_field(n, primes_so_far) == k

# ─────────────────────────────────────────
# 相位场动态演化
# ─────────────────────────────────────────
def phase_field_evolution(N_primes=100, search_limit=700):
    """
    逐步构建相位场，记录每一步的演化

    对每个新素数 p_k，记录：
    1. p_k 加入后，相位场在哪些位置发生了变化（从候选→非候选）
    2. 变化的幅度（相位跳变量）
    3. p_{k+1} 处的相位场值的演化历史
    """
    primes = [2]
    search_range = np.arange(2, search_limit)

    # 记录每个位置的相位场值（初始：空集，Φ_0(n)=0 for all n）
    phi_values = np.zeros(search_limit, dtype=int)

    # 加入 p_1=2 后的初始化
    for n in search_range:
        phi_values[n] = compute_phase_field(n, primes)

    evolution_log = []
    contribution_log = []

    while len(primes) < N_primes:
        k = len(primes)
        p_k = primes[-1]

        # 找下一个候选：Φ_k(n) = k，n > p_k
        next_prime = None
        for n in range(p_k + 1, search_limit):
            if phi_values[n] == k:
                next_prime = n
                break

        if next_prime is None:
            print(f"搜索范围不足，在 p_{k}={p_k} 后停止")
            break

        # 记录加入 next_prime 前的状态
        p_next = next_prime
        primes.append(p_next)

        # 计算 p_next 对相位场的贡献：
        # 所有 p_next 的倍数，相位场值减少2（从候选→非候选）
        affected_positions = list(range(p_next, search_limit, p_next))
        phase_changes = []
        candidates_lost = 0

        for pos in affected_positions:
            old_phi = phi_values[pos]
            phi_values[pos] -= 2  # e^{iπ} = -1，贡献从+1变为-1，净变化-2
            new_phi = phi_values[pos]
            if old_phi == k and new_phi != k + 1:
                candidates_lost += 1
            phase_changes.append({
                "position": int(pos),
                "old_phi": int(old_phi),
                "new_phi": int(new_phi),
                "was_candidate": bool(old_phi == k)
            })

        # 贡献量：p_next 使多少候选位置失效
        contribution = {
            "k": k,
            "p_k": int(p_k),
            "p_next": int(p_next),
            "gap": int(p_next - p_k),
            "num_affected": len(affected_positions),
            "candidates_lost": candidates_lost,
            # 相位场在 p_next 处的历史值（被加入前）
            "phi_at_p_next_before": int(phi_values[p_next] + 2),
            # 累积贡献：p_next 的倍数密度
            "multiples_density": len(affected_positions) / search_limit,
            # 关键比值
            "gap_over_p_prev": float(p_next - p_k) / p_k if len(primes) > 2 else None,
        }
        contribution_log.append(contribution)

        # 演化快照（每10步记录一次）
        if k % 10 == 0:
            snapshot = {
                "k": k,
                "p_k": int(p_k),
                "phi_distribution": {
                    str(v): int(np.sum(phi_values[2:search_limit//2] == v))
                    for v in range(-k, k+2, 2)
                }
            }
            evolution_log.append(snapshot)

    return primes, contribution_log, evolution_log, phi_values


# ─────────────────────────────────────────
# 分析：累积贡献与位置的关系
# ─────────────────────────────────────────
def analyze_phase_contributions(primes, contribution_log):
    """
    核心分析：从相位场角度，
    p_k 的贡献量（multiples_density）与 gap_k 的关系
    """
    if len(contribution_log) < 3:
        return {}

    gaps       = np.array([c["gap"]              for c in contribution_log[1:]], dtype=float)
    p_ks       = np.array([c["p_k"]              for c in contribution_log[1:]], dtype=float)
    densities  = np.array([c["multiples_density"] for c in contribution_log[1:]], dtype=float)
    lost       = np.array([c["candidates_lost"]   for c in contribution_log[1:]], dtype=float)
    affected   = np.array([c["num_affected"]       for c in contribution_log[1:]], dtype=float)

    # 候选公式1：gap ≈ 1 / density（密度越高，间隔越小）
    pred1 = 1.0 / (densities + 1e-10)
    # 候选公式2：gap ≈ p_k * density（反比）
    pred2 = p_ks * densities
    # 候选公式3：gap ≈ p_k / affected
    pred3 = p_ks / (affected + 1e-10)

    def corr(x, y):
        mask = np.isfinite(x) & np.isfinite(y)
        if mask.sum() < 3:
            return 0.0
        return float(np.corrcoef(x[mask], y[mask])[0, 1])

    print("[相位场贡献分析]")
    print(f"{'候选公式':<35} {'与 gap 的相关系数':>18}")
    print("-" * 55)
    formulas = {
        "1/density（密度倒数）":      (pred1, corr(pred1, gaps)),
        "p_k × density":             (pred2, corr(pred2, gaps)),
        "p_k / num_affected":        (pred3, corr(pred3, gaps)),
        "ln(p_k)（素数定理）":        (np.log(p_ks), corr(np.log(p_ks), gaps)),
        "√p_k":                      (np.sqrt(p_ks), corr(np.sqrt(p_ks), gaps)),
    }
    for name, (pred, c) in formulas.items():
        mark = " ★★★" if abs(c) > 0.8 else (" ★★" if abs(c) > 0.6 else "")
        print(f"{name:<35} {c:>18.4f}{mark}")

    best_name = max(formulas, key=lambda x: abs(formulas[x][1]))
    best_corr = formulas[best_name][1]
    print(f"最佳候选：{best_name}，相关系数 = {best_corr:.4f}")

    return formulas, best_name


# ─────────────────────────────────────────
# 可视化
# ─────────────────────────────────────────
def visualize_phase(primes, contribution_log, phi_values):
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle("RH-037 v2：相位场框架下的素数累积贡献", fontsize=13)

    gaps      = [c["gap"]              for c in contribution_log[1:]]
    p_ks      = [c["p_k"]             for c in contribution_log[1:]]
    densities = [c["multiples_density"] for c in contribution_log[1:]]
    lost_     = [c["candidates_lost"]  for c in contribution_log[1:]]

    # (a) 相位场快照（前700个整数）
    ax = axes[0, 0]
    x = np.arange(2, min(200, len(phi_values)))
    ax.bar(x, phi_values[2:min(200, len(phi_values))],
           color=['green' if v == len(primes)-1 else
                  ('red' if v < 0 else 'steelblue')
                  for v in phi_values[2:min(200, len(phi_values))]],
           width=1.0, alpha=0.7)
    for p in primes[:20]:
        if p < 200:
            ax.axvline(p, color='red', lw=1, alpha=0.5)
    ax.set_xlabel('n')
    ax.set_ylabel('Φ_k(n)')
    ax.set_title('相位场快照（红线=素数）')
    ax.grid(alpha=0.3)

    # (b) 贡献密度 vs gap
    ax = axes[0, 1]
    ax.scatter(densities, gaps, s=10, alpha=0.5, color='purple')
    ax.set_xlabel('p_k 的倍数密度（贡献量/搜索范围）')
    ax.set_ylabel('gap_k')
    ax.set_title('相位贡献密度 vs 间隔')
    ax.grid(alpha=0.3)

    # (c) gap / ln(p_k)（应趋向1，素数定理）
    ax = axes[0, 2]
    ratio = np.array(gaps) / np.log(np.array(p_ks) + 1)
    ax.plot(p_ks, ratio, 'b-', lw=0.8, alpha=0.8)
    ax.axhline(1.0, color='red', ls='--', lw=1.5, label='素数定理预测=1')
    ax.set_xlabel('p_k')
    ax.set_ylabel('gap_k / ln(p_k)')
    ax.set_title('间隔/ln(p_k)（应趋向1）')
    ax.legend(); ax.grid(alpha=0.3)

    # (d) 加法递推验证
    ax = axes[1, 0]
    p_prevs = [c["p_k"] for c in contribution_log[:-1]]
    gaps2   = [c["gap"] for c in contribution_log[1:]]
    n = min(len(p_prevs), len(gaps2))
    ax.scatter(p_prevs[:n], gaps2[:n], s=8, alpha=0.5, color='orange')
    lim = max(p_prevs[:n])
    ax.plot([0, lim], [0, lim], 'r--', lw=1.5, label='$g_k = p_{k-1}$（上界）')
    ax.set_xlabel('$p_{k-1}$')
    ax.set_ylabel('$g_k$')
    ax.set_title('加法递推 $g_k \\leq p_{k-1}$（相位场验证）')
    ax.legend(); ax.grid(alpha=0.3)

    # (e) 相位场变化量（candidates_lost）vs gap
    ax = axes[1, 1]
    ax.scatter(lost_, gaps, s=8, alpha=0.5, color='green')
    ax.set_xlabel('candidates_lost（相位场失效候选数）')
    ax.set_ylabel('gap_k')
    ax.set_title('相位失效数 vs 间隔')
    ax.grid(alpha=0.3)

    # (f) 1/density vs gap（候选公式）
    ax = axes[1, 2]
    pred = 1.0 / (np.array(densities) + 1e-10)
    ax.scatter(pred, gaps, s=8, alpha=0.5, color='red')
    lim2 = min(max(pred), max(gaps) * 3)
    ax.plot([0, lim2], [0, lim2], 'k--', lw=1.5, label='完美预测线')
    ax.set_xlim(0, lim2)
    ax.set_xlabel('1/density（候选公式）')
    ax.set_ylabel('实际 gap_k')
    ax.set_title('候选公式 $g_k \\approx 1/\\rho_k$')
    ax.legend(); ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "rh037_phase_v2.png")
    plt.savefig(path, dpi=150)
    print(f"✓ 图已保存: {path}")
    plt.close()


# ─────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────
def main():
    print("=" * 60)
    print("RH-037 v2：相位场框架下的素数累积贡献")
    print("=" * 60)

    primes, contribution_log, evolution_log, phi_values = \
        phase_field_evolution(N_primes=150, search_limit=1000)

    print(f"✓ 找到 {len(primes)} 个素数")
    print(f"  最大素数: {primes[-1]}")

    formulas, best = analyze_phase_contributions(primes, contribution_log)
    visualize_phase(primes, contribution_log, phi_values)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = {
        "timestamp": ts,
        "num_primes": len(primes),
        "primes_sample": primes[:30],
        "contribution_sample": contribution_log[:20],
        "best_formula": best,
    }
    path = os.path.join(OUTPUT_DIR, f"rh037_phase_v2_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✓ 结果已保存: {path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
