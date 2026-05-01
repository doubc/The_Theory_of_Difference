import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.special import factorial

# ============================================================
# RH-024: {0,1}^N 上的 A5 演化算子 + GinUE 检验
#
# 核心转变：
#   - 放弃宏观格点 GR 度规（正定性无法保证）
#   - 回到 {0,1}^N，构造 A5 演化算子（非厄米转移矩阵）
#   - 检验复数本征值谱与 GinUE 的对应
#
# A5 演化算子定义：
#   T_{xy} = P(x -> y in one step)
#          = exp(-beta * H(x,y)) / Z(x)
#   其中 H(x,y) = Hamming distance(x,y)（A4 局域性）
#   beta 是逆温度参数（A5 耗散强度）
#   Z(x) = sum_y exp(-beta * H(x,y))（归一化）
#
# 非对称性来源：
#   加入 A6 偏置（方向性）：
#   T_{xy} *= exp(gamma * (f(y) - f(x)))
#   其中 f(x) = sum_k x_k（汉明重量，对应"层级"）
#   gamma > 0 使演化偏向高层（不可逆性）
#
# GinUE 检验：
#   复数本征值的径向分布应满足 Ginibre 圆律
#   最近邻间距分布应满足 GinUE 预测
# ============================================================

def hamming(x, y):
    return sum(xi != yi for xi, yi in zip(x, y))

def f_weight(x):
    """层级函数：汉明重量"""
    return sum(x)

def build_a5_operator(N, beta, gamma, noise_eps=0.0):
    """
    构造 {0,1}^N 上的 A5 演化算子。
    beta:      逆温度（A5 耗散强度）
    gamma:     方向性偏置（A6 不可逆性）
    noise_eps: 随机微扰强度（打破残余对称性）
    """
    states = list(product([0,1], repeat=N))
    M = len(states)
    idx = {s: i for i, s in enumerate(states)}

    T = np.zeros((M, M))

    for i, x in enumerate(states):
        fx = f_weight(x)
        row = np.zeros(M)
        for j, y in enumerate(states):
            d = hamming(x, y)
            if d == 0:
                continue
            # A4 局域性：Hamming 距离越大，转移概率越小
            w = np.exp(-beta * d)
            # A6 方向性偏置
            fy = f_weight(y)
            w *= np.exp(gamma * (fy - fx))
            row[j] = w
        Z = row.sum()
        if Z > 0:
            T[i, :] = row / Z

    # 加入随机微扰（打破残余离散对称性）
    if noise_eps > 0:
        noise = noise_eps * np.random.randn(M, M)
        T += noise

    return T, states

def complex_spectrum_stats(eigs_complex, label, verbose=True):
    """
    复数本征值谱统计：
    1. 圆律检验：|lambda| 的分布
    2. 最近邻间距分布
    3. 角度分布均匀性
    """
    # 去掉最大模本征值（平稳分布）
    mods = np.abs(eigs_complex)
    idx_max = np.argmax(mods)
    eigs = np.delete(eigs_complex, idx_max)
    mods = np.abs(eigs)

    if verbose:
        print(f"{'='*60}")
        print(f"实验: {label}")
        print(f"{'='*60}")
        print(f"本征值数: {len(eigs)}")
        print(f"|lambda| 范围: [{mods.min():.4f}, {mods.max():.4f}]")
        print(f"|lambda| 均值: {mods.mean():.4f}, 中位数: {np.median(mods):.4f}")

    # 最近邻间距（复平面中的欧氏距离）
    M = len(eigs)
    nn_dists = []
    for i in range(M):
        dists = np.abs(eigs[i] - eigs)
        dists[i] = np.inf
        nn_dists.append(np.min(dists))
    nn_dists = np.array(nn_dists)

    # 归一化（用平均间距归一化）
    mean_nn = np.mean(nn_dists)
    s_nn = nn_dists / mean_nn

    # GinUE 预测：P(s) = (pi/2) s exp(-pi s^2 / 4)（Ginibre 最近邻）
    # 均值 = sqrt(pi)/2 ≈ 0.886，方差 = (4-pi)/4 ≈ 0.215

    mean_s  = np.mean(s_nn)
    var_s   = np.var(s_nn)
    med_s   = np.median(s_nn)
    # GinUE 理论值
    ginibre_mean = np.sqrt(np.pi) / 2  # ≈ 0.886
    ginibre_var  = (4 - np.pi) / 4     # ≈ 0.215

    if verbose:
        print(f"最近邻间距统计 (归一化):")
        print(f"  均值:   {mean_s:.4f}  (GinUE≈{ginibre_mean:.4f})")
        print(f"  中位数: {med_s:.4f}")
        print(f"  方差:   {var_s:.4f}  (GinUE≈{ginibre_var:.4f})")
        se = np.std(s_nn) / np.sqrt(M)
        sigma_gin = abs(mean_s - ginibre_mean) / se if se > 0 else np.inf
        print(f"  与 GinUE 偏差: {sigma_gin:.2f}σ")

    # 角度分布均匀性（Kolmogorov-Smirnov 检验）
    angles = np.angle(eigs)
    angles_sorted = np.sort(angles)
    # 均匀分布 CDF
    uniform_cdf = (angles_sorted + np.pi) / (2 * np.pi)
    empirical_cdf = np.arange(1, M+1) / M
    ks_stat = np.max(np.abs(empirical_cdf - uniform_cdf))
    ks_critical = 1.36 / np.sqrt(M)  # 5% 显著性水平

    if verbose:
        print(f"角度均匀性 (KS检验):")
        print(f"  KS统计量: {ks_stat:.4f}  (5%临界值: {ks_critical:.4f})")
        print(f"  {'均匀分布 (符合圆律)' if ks_stat < ks_critical else '非均匀 (偏离圆律)'}")

    se = np.std(s_nn) / np.sqrt(M)
    sigma_gin = abs(mean_s - ginibre_mean) / se if se > 0 else np.inf

    return {
        'label': label, 'eigs': eigs, 'mods': mods,
        's_nn': s_nn, 'mean_s': mean_s, 'var_s': var_s,
        'med_s': med_s, 'sigma_gin': sigma_gin,
        'ks_stat': ks_stat, 'ks_critical': ks_critical,
        'ginibre_mean': ginibre_mean, 'ginibre_var': ginibre_var,
    }


# ============================================================
# 实验设计
# ============================================================

np.random.seed(42)

print("" + "#"*65)
print("# RH-024: A5 演化算子复数谱 + GinUE 检验")
print("#"*65)

# 参数扫描
experiments = []

# N=4 (16态), N=5 (32态), N=6 (64态)
for N in [4, 5, 6]:
    M = 2**N
    print(f"{'='*65}")
    print(f"N={N} ({M}态)")
    print(f"{'='*65}")

    for beta in [0.5, 1.0, 2.0]:
        for gamma in [0.0, 0.5, 1.0]:
            label = f"N={N} β={beta} γ={gamma}"
            T, states = build_a5_operator(N, beta, gamma, noise_eps=0.0)

            # 复数本征值
            eigs_c = np.linalg.eigvals(T)
            eigs_c = np.sort_complex(eigs_c)

            res = complex_spectrum_stats(eigs_c, label, verbose=(N==5))
            if res:
                res['N'] = N
                res['beta'] = beta
                res['gamma'] = gamma
                experiments.append(res)

    # 加噪声版本（打破残余对称性）
    for eps in [0.01, 0.05]:
        label = f"N={N} β=1.0 γ=0.5 ε={eps}"
        T, states = build_a5_operator(N, beta=1.0, gamma=0.5, noise_eps=eps)
        eigs_c = np.linalg.eigvals(T)
        res = complex_spectrum_stats(eigs_c, label, verbose=(N==5))
        if res:
            res['N'] = N
            res['beta'] = 1.0
            res['gamma'] = 0.5
            res['eps'] = eps
            experiments.append(res)


# ============================================================
# 汇总
# ============================================================

print("" + "="*80)
print("RH-024 汇总：A5 演化算子 GinUE 检验")
print("="*80)
print(f"{'实验':<30} {'N':<4} {'NN均值':<9} {'NN方差':<9} {'GinUE偏差':<11} {'KS统计'}")
print("-"*80)
for res in experiments:
    print(f"{res['label']:<30} {res['N']:<4} "
          f"{res['mean_s']:.4f}    {res['var_s']:.4f}    "
          f"{res['sigma_gin']:.2f}σ       {res['ks_stat']:.4f}"
          f"{'*' if res['ks_stat'] > res['ks_critical'] else ''}")
print(f"{'GinUE 理论':<30} {'—':<4} 0.8862    0.2146")


# ============================================================
# 可视化：最佳参数的复数谱图
# ============================================================

# 找最接近 GinUE 的参数（按 sigma_gin 排序）
best = sorted(experiments, key=lambda r: r['sigma_gin'])[:4]

fig, axes = plt.subplots(2, 4, figsize=(16, 8))
s_th = np.linspace(0, 3, 300)
# GinUE 最近邻分布：P(s) = (pi/2) s exp(-pi s^2 / 4)
p_ginibre = (np.pi/2) * s_th * np.exp(-np.pi/4 * s_th**2)
# Poisson（实数）参考
p_poisson = np.exp(-s_th)

colors = ['steelblue', 'darkorange', 'forestgreen', 'crimson']

for col, res in enumerate(best):
    color = colors[col]

    # 行1：复平面本征值分布
    ax = axes[0, col]
    ax.scatter(res['eigs'].real, res['eigs'].imag,
               s=15, alpha=0.7, color=color)
    # 圆律参考圆
    theta = np.linspace(0, 2*np.pi, 200)
    r_circle = np.median(res['mods'])
    ax.plot(r_circle*np.cos(theta), r_circle*np.sin(theta),
            'k--', lw=1, alpha=0.5, label=f'r={r_circle:.2f}')
    ax.set_aspect('equal')
    ax.set_title(f"{res['label']}"
                 f"σ={res['sigma_gin']:.2f}", fontsize=8)
    ax.set_xlabel('Re(λ)'); ax.set_ylabel('Im(λ)')
    ax.legend(fontsize=7); ax.grid(True, alpha=0.3)

    # 行2：最近邻间距分布
    ax2 = axes[1, col]
    ax2.hist(res['s_nn'], bins=12, density=True, alpha=0.65,
             color=color, edgecolor='white')
    ax2.plot(s_th, p_ginibre, 'r-',  lw=2,   label='GinUE')
    ax2.plot(s_th, p_poisson, 'k--', lw=1.5, label='Poisson')
    ax2.axvline(res['mean_s'], color=color, lw=1.5, linestyle=':',
                label=f"mean={res['mean_s']:.3f}")
    ax2.set_xlabel('s (归一化最近邻间距)')
    ax2.set_ylabel('P(s)')
    ax2.set_title(f'NN dist  var={res["var_s"]:.3f}', fontsize=9)
    ax2.legend(fontsize=7); ax2.set_xlim(0, 3); ax2.grid(True, alpha=0.3)

plt.suptitle('RH-024: A5 演化算子复数谱 — GinUE 检验（最佳4个参数）',
             fontsize=11, fontweight='bold')
plt.tight_layout()
plt.savefig('RH024_ginibre.png', dpi=150, bbox_inches='tight')
print("图像已保存为 RH024_ginibre.png")
print("=== RH-024 计算完成 ===")
