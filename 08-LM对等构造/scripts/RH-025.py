import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# RH-025: 位置相关 A5 算子 — 打破 Walsh 对角化
#
# 核心修正：
#   T_{xy} 的权重不只依赖 d(x,y)，
#   而是依赖具体翻转了哪些比特位（位置相关）
#
# 构造方案：
#   翻转比特 k 的代价：c_k(x) = alpha_k + sum_j J_{kj} x_j
#   （Ising 型局域场：比特 k 的翻转代价依赖邻居状态）
#   T_{xy} = exp(-sum_{k: x_k != y_k} c_k(x)) * exp(gamma*(f(y)-f(x)))
#          / Z(x)
#
# 参数：
#   alpha_k: 比特 k 的基础翻转代价（打破置换对称性）
#   J_{kj}:  比特间耦合（打破独立性，产生不可积性）
#   gamma:   方向性偏置（A6）
#
# 这个构造的关键性质：
#   - J_{kj} != 0 使得不同比特之间有耦合，打破乘积结构
#   - 不同 alpha_k 打破比特置换对称性
#   - 两者合力打破 B_N 对称群，使 T 不再 Walsh 可对角化
# ============================================================

def build_ising_a5(N, alpha, J, gamma, seed=None):
    """
    构造 Ising 型位置相关 A5 算子。
    alpha: 长度 N 的数组，各比特基础翻转代价
    J:     N×N 矩阵，比特间耦合（对角元忽略）
    gamma: 方向性偏置
    """
    states = list(product([0,1], repeat=N))
    M = len(states)
    idx = {s: i for i, s in enumerate(states)}

    T = np.zeros((M, M))

    for i, x in enumerate(states):
        fx = sum(x)
        row = np.zeros(M)

        for j, y in enumerate(states):
            if i == j:
                continue
            # 找到翻转的比特位
            flipped = [k for k in range(N) if x[k] != y[k]]
            if not flipped:
                continue

            # 翻转代价：各翻转比特的 Ising 局域场之和
            cost = 0.0
            for k in flipped:
                # 局域场：基础代价 + 邻居耦合
                local_field = alpha[k]
                for j2 in range(N):
                    if j2 != k:
                        local_field += J[k, j2] * x[j2]
                cost += abs(local_field)

            w = np.exp(-cost)
            # 方向性偏置
            fy = sum(y)
            w *= np.exp(gamma * (fy - fx))
            row[j] = w

        Z = row.sum()
        if Z > 0:
            T[i, :] = row / Z

    return T, states, idx


def complex_spectrum_stats(eigs_complex, label, verbose=True):
    """复数本征值谱统计（修正版：正确处理实本征值）"""
    mods = np.abs(eigs_complex)
    idx_max = np.argmax(mods)
    eigs = np.delete(eigs_complex, idx_max)
    mods_e = np.abs(eigs)

    # 检查是否全为实数
    imag_frac = np.mean(np.abs(eigs.imag) > 1e-8)

    if verbose:
        print(f"{'='*55}")
        print(f"实验: {label}")
        print(f"{'='*55}")
        print(f"本征值数: {len(eigs)}")
        print(f"复数本征值比例: {imag_frac:.3f}")
        print(f"|λ| 范围: [{mods_e.min():.4f}, {mods_e.max():.4f}]")

    # 最近邻间距（复平面欧氏距离）
    M = len(eigs)
    nn_dists = np.array([
        np.min(np.delete(np.abs(eigs[i] - eigs), i))
        for i in range(M)
    ])
    mean_nn = np.mean(nn_dists)
    if mean_nn < 1e-12:
        if verbose: print("  所有本征值简并，跳过")
        return None

    s_nn = nn_dists / mean_nn
    mean_s = np.mean(s_nn)
    var_s  = np.var(s_nn)
    med_s  = np.median(s_nn)
    se     = np.std(s_nn) / np.sqrt(M)

    ginibre_mean = np.sqrt(np.pi) / 2
    ginibre_var  = (4 - np.pi) / 4
    sigma_gin = abs(mean_s - ginibre_mean) / se if se > 0 else np.inf

    # KS 检验（角度均匀性）
    angles = np.angle(eigs)
    angles_s = np.sort(angles)
    uniform_cdf = (angles_s + np.pi) / (2*np.pi)
    empirical_cdf = np.arange(1, M+1) / M
    ks_stat = np.max(np.abs(empirical_cdf - uniform_cdf))
    ks_crit = 1.36 / np.sqrt(M)

    if verbose:
        print(f"最近邻间距: 均值={mean_s:.4f} 中位数={med_s:.4f} 方差={var_s:.4f}")
        print(f"GinUE:      均值={ginibre_mean:.4f}           方差={ginibre_var:.4f}")
        print(f"GinUE偏差: {sigma_gin:.2f}σ")
        print(f"KS={ks_stat:.4f} (临界={ks_crit:.4f}) "
              f"{'✓圆律' if ks_stat < ks_crit else '✗非圆律'}")

    return {
        'label': label, 'eigs': eigs,
        'imag_frac': imag_frac,
        'mean_s': mean_s, 'var_s': var_s, 'med_s': med_s,
        'sigma_gin': sigma_gin,
        'ks_stat': ks_stat, 'ks_crit': ks_crit,
    }


# ============================================================
# 实验设计
# ============================================================

np.random.seed(2025)
results = []

print("" + "#"*65)
print("# RH-025: Ising 型位置相关 A5 算子")
print("#"*65)

# --- 实验 A：随机 alpha + 零耦合（打破置换对称，保持独立性）---
print("=== 实验组 A：随机 alpha，J=0（打破置换对称性）===")
for N in [5, 6, 7]:
    M = 2**N
    for trial in range(3):
        alpha = np.random.uniform(0.5, 2.0, N)
        J     = np.zeros((N, N))
        label = f"A N={N} trial={trial}"
        T, _, _ = build_ising_a5(N, alpha, J, gamma=0.5)
        eigs_c = np.linalg.eigvals(T)
        res = complex_spectrum_stats(eigs_c, label, verbose=True)
        if res:
            res['group'] = 'A'; res['N'] = N
            results.append(res)

# --- 实验 B：随机 alpha + 随机 J（完全打破对称性）---
print("=== 实验组 B：随机 alpha + 随机 J（完全非对称）===")
for N in [5, 6, 7]:
    for trial in range(3):
        alpha = np.random.uniform(0.5, 2.0, N)
        J_raw = np.random.uniform(-0.5, 0.5, (N, N))
        np.fill_diagonal(J_raw, 0)
        J = J_raw
        label = f"B N={N} trial={trial}"
        T, _, _ = build_ising_a5(N, alpha, J, gamma=0.5)
        eigs_c = np.linalg.eigvals(T)
        res = complex_spectrum_stats(eigs_c, label, verbose=True)
        if res:
            res['group'] = 'B'; res['N'] = N
            results.append(res)

# --- 实验 C：近邻耦合（A4 局域性：只有相邻比特有耦合）---
print("=== 实验组 C：近邻耦合 J_{k,k+1}（A4 局域性）===")
for N in [5, 6, 7, 8]:
    M = 2**N
    for trial in range(3):
        alpha = np.random.uniform(0.5, 2.0, N)
        J = np.zeros((N, N))
        # 只有相邻比特有耦合
        for k in range(N-1):
            J[k, k+1] = np.random.uniform(-1.0, 1.0)
            J[k+1, k] = J[k, k+1]
        label = f"C N={N} trial={trial}"
        T, _, _ = build_ising_a5(N, alpha, J, gamma=0.5)
        eigs_c = np.linalg.eigvals(T)
        res = complex_spectrum_stats(eigs_c, label, verbose=True)
        if res:
            res['group'] = 'C'; res['N'] = N
            results.append(res)

# ============================================================
# 汇总
# ============================================================

print("" + "="*75)
print("RH-025 汇总")
print("="*75)
print(f"{'实验':<22} {'N':<4} {'复数比':<8} {'NN均值':<8} {'NN方差':<8} "
      f"{'GinUE偏差':<11} {'KS'}")
print("-"*75)
for res in results:
    flag = '✓' if res['ks_stat'] < res['ks_crit'] else '✗'
    print(f"{res['label']:<22} {res['N']:<4} {res['imag_frac']:.3f}    "
          f"{res['mean_s']:.4f}   {res['var_s']:.4f}   "
          f"{res['sigma_gin']:.2f}σ       {res['ks_stat']:.4f}{flag}")
print(f"{'GinUE 理论':<22} {'—':<4} {'—':<8} 0.8862   0.2146")

# ============================================================
# 可视化：按组汇总 NN方差 vs N
# ============================================================

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

group_colors = {'A': 'steelblue', 'B': 'darkorange', 'C': 'forestgreen'}
group_labels = {
    'A': 'A: 随机α, J=0',
    'B': 'B: 随机α+J',
    'C': 'C: 近邻耦合(A4)'
}

for grp, color in group_colors.items():
    sub = [r for r in results if r['group'] == grp]
    if not sub: continue

    # 按 N 分组，计算均值±std
    Ns = sorted(set(r['N'] for r in sub))
    var_mean = [np.mean([r['var_s']  for r in sub if r['N']==n]) for n in Ns]
    var_std  = [np.std( [r['var_s']  for r in sub if r['N']==n]) for n in Ns]
    med_mean = [np.mean([r['med_s']  for r in sub if r['N']==n]) for n in Ns]
    ks_mean  = [np.mean([r['ks_stat']for r in sub if r['N']==n]) for n in Ns]

    axes[0].errorbar(Ns, var_mean, yerr=var_std, fmt='o-',
                     color=color, lw=2, capsize=4, label=group_labels[grp])
    axes[1].plot(Ns, med_mean, 'o-', color=color, lw=2,
                 label=group_labels[grp])
    axes[2].plot(Ns, ks_mean,  'o-', color=color, lw=2,
                 label=group_labels[grp])

# 参考线
axes[0].axhline(0.2146, color='red',   lw=2, linestyle='--', label='GinUE 0.215')
axes[0].axhline(1.000,  color='black', lw=1.5, linestyle=':', label='Poisson 1.0')
axes[1].axhline(0.8862, color='red',   lw=2, linestyle='--', label='GinUE 0.886')
axes[1].axhline(1.000,  color='black', lw=1.5, linestyle=':', label='Poisson 1.0')
axes[2].axhline(0.0,    color='red',   lw=2, linestyle='--', label='均匀(GinUE)')

for ax, (ylabel, title) in zip(axes, [
    ('NN间距方差',     'NN方差 vs N（目标: GinUE≈0.215）'),
    ('NN间距中位数',   'NN中位数 vs N（目标: GinUE≈0.886）'),
    ('KS统计量',       'KS统计量 vs N（<临界值=圆律）'),
]):
    ax.set_xlabel('N (比特数)', fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

# KS 临界值曲线
N_arr = np.array([5,6,7,8])
ks_crit_arr = 1.36 / np.sqrt(2**N_arr - 1)
axes[2].plot(N_arr, ks_crit_arr, 'k--', lw=1.5, label='5%临界值')
axes[2].legend(fontsize=8)

plt.suptitle('RH-025: Ising 型 A5 算子 — GinUE 收敛性检验',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('RH025_ising_ginibre.png', dpi=150, bbox_inches='tight')
print("图像已保存为 RH025_ising_ginibre.png")
print("=== RH-025 计算完成 ===")
