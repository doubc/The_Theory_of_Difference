import time

import matplotlib.pyplot as plt
import numpy as np

# ============================================================
# 莫比乌斯核心
# ============================================================
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


def torsion_weighted_sum(values, epsilons):
    """
    扭转加权求和
    values: 幅度序列（正数）
    epsilons: 方向序列 (+1/-1)
    返回: (累积值, 拓扑电荷序列)
    """
    n = len(values)
    cumulative = np.cumprod(epsilons)  # 累积扭转
    weighted = cumulative * values  # 扭转加权
    result = np.cumsum(weighted)  # 累积求和
    return result, cumulative


def topological_predictability(returns):
    """
    莫比乌斯预测性指标
    输入: 收益率序列
    输出: 预测性得分（越大越有趋势，越小越震荡）
    """
    magnitudes = np.abs(returns)
    directions = np.sign(returns)
    directions[directions == 0] = 1

    cumsum, charge = torsion_weighted_sum(magnitudes, directions)

    # 预测性 = 最终累积值 / 总幅度
    # 趋势: 接近 1（方向一致，累积 ≈ 总幅度）
    # 震荡: 接近 0（方向交替，累积 ≈ 0）
    total_magnitude = np.sum(magnitudes)
    predictability = cumsum[-1] / total_magnitude if total_magnitude > 0 else 0

    return predictability, cumsum, charge


# ============================================================
# 传统方法：滑动窗口自相关
# ============================================================

def traditional_predictability(returns, window=20):
    """
    传统方法：滑动窗口一阶自相关
    需要多次遍历，计算方差和协方差
    """
    n = len(returns)
    autocorr = np.zeros(n)

    for i in range(window, n):
        segment = returns[i - window:i]
        if np.std(segment) < 1e-10:
            autocorr[i] = 0
        else:
            mean = np.mean(segment)
            shifted = segment[1:] - mean
            original = segment[:-1] - mean
            autocorr[i] = np.sum(shifted * original) / (np.std(segment) ** 2 * (window - 1))

    return autocorr


def traditional_predictability_vectorized(returns, window=20):
    """
    传统方法向量化版本
    仍然需要滑动窗口计算
    """
    n = len(returns)
    autocorr = np.full(n, np.nan)

    for i in range(window, n):
        seg = returns[i - window:i]
        s = np.std(seg)
        if s < 1e-10:
            autocorr[i] = 0
            continue
        c = np.corrcoef(seg[:-1], seg[1:])[0, 1]
        autocorr[i] = c if not np.isnan(c) else 0

    return autocorr


# ============================================================
# 生成测试数据
# ============================================================

def generate_price_series(n, regime='mixed', seed=42):
    """
    生成不同机制的价格序列
    """
    np.random.seed(seed)

    if regime == 'trend':
        # 强趋势
        returns = np.random.normal(0.001, 0.01, n)
    elif regime == 'oscillate':
        # 强震荡
        returns = np.random.normal(0, 0.01, n) * np.sin(np.arange(n) * 0.5)
    elif regime == 'mixed':
        # 前半段趋势，后半段震荡
        half = n // 2
        trend = np.random.normal(0.002, 0.008, half)
        oscillate = np.random.normal(0, 0.01, n - half) * np.sin(np.arange(n - half) * 0.8)
        returns = np.concatenate([trend, oscillate])
    else:
        returns = np.random.normal(0, 0.01, n)

    prices = 100 * np.exp(np.cumsum(returns))
    return prices, returns


# ============================================================
# 主实验
# ============================================================

print("=" * 60)
print("莫比乌斯算数：价格序列预测性")
print("=" * 60)

# --- 生成混合机制数据 ---
n_points = 100000
prices, returns = generate_price_series(n_points, regime='mixed')

print(f"\n数据点数: {n_points}")
print(f"价格范围: [{prices.min():.2f}, {prices.max():.2f}]")

# --- 莫比乌斯方法计时 ---
t0 = time.perf_counter()
for _ in range(10):
    pred_mob, cumsum_mob, charge_mob = topological_predictability(returns)
t_mob = (time.perf_counter() - t0) / 10

# --- 传统方法计时 ---
t0 = time.perf_counter()
for _ in range(3):
    autocorr = traditional_predictability_vectorized(returns, window=20)
t_trad = (time.perf_counter() - t0) / 3

print(f"\n--- 时间对比 ---")
print(f"传统方法 (自相关): {t_trad * 1000:.2f} ms")
print(f"莫比乌斯 (扭转加权): {t_mob * 1000:.2f} ms")
print(f"加速比: {t_trad / t_mob:.1f}x")

# --- 预测性分析 ---
half = n_points // 2
pred_trend, _, _ = topological_predictability(returns[:half])
pred_osc, _, _ = topological_predictability(returns[half:])

print(f"\n--- 预测性分析 ---")
print(f"前半段 (趋势期) 预测性: {pred_trend:.4f}")
print(f"后半段 (震荡期) 预测性: {pred_osc:.4f}")
print(f"趋势期 vs 震荡期 差异: {abs(pred_trend - pred_osc):.4f}")

# --- 滚动窗口预测性 ---
window = 500
step = 50
rolling_pred = []
for i in range(0, n_points - window, step):
    p, _, _ = topological_predictability(returns[i:i + window])
    rolling_pred.append(p)

print(f"\n滚动窗口预测性:")
print(f"  最大值: {max(rolling_pred):.4f} (强趋势)")
print(f"  最小值: {min(rolling_pred):.4f} (强震荡)")
print(f"  均值: {np.mean(rolling_pred):.4f}")

# --- 画图 ---
fig, axes = plt.subplots(3, 2, figsize=(14, 12))

# 价格
axes[0, 0].plot(prices, 'b-', linewidth=0.3)
axes[0, 0].axvline(half, color='red', linestyle='--', alpha=0.5, label='趋势→震荡分界')
axes[0, 0].set_xlabel('时间')
axes[0, 0].set_ylabel('价格')
axes[0, 0].set_title('价格序列（前半趋势，后半震荡）')
axes[0, 0].legend()
axes[0, 0].grid(True, alpha=0.3)

# 扭转加权累积
axes[0, 1].plot(cumsum_mob, 'purple', linewidth=0.5)
axes[0, 1].axvline(half, color='red', linestyle='--', alpha=0.5)
axes[0, 1].set_xlabel('时间')
axes[0, 1].set_ylabel('扭转加权累积值')
axes[0, 1].set_title('扭转加权求和（趋势期上升，震荡期平坦）')
axes[0, 1].grid(True, alpha=0.3)

# 拓扑电荷
axes[1, 0].plot(charge_mob, 'green', linewidth=0.3)
axes[1, 0].axvline(half, color='red', linestyle='--', alpha=0.5)
axes[1, 0].set_xlabel('时间')
axes[1, 0].set_ylabel('拓扑电荷')
axes[1, 0].set_title('拓扑电荷演化')
axes[1, 0].grid(True, alpha=0.3)

# 传统自相关
valid = ~np.isnan(autocorr)
axes[1, 1].plot(np.where(valid)[0], autocorr[valid], 'steelblue', linewidth=0.3)
axes[1, 1].axvline(half, color='red', linestyle='--', alpha=0.5)
axes[1, 1].set_xlabel('时间')
axes[1, 1].set_ylabel('自相关系数')
axes[1, 1].set_title('传统方法：滑动窗口自相关')
axes[1, 1].grid(True, alpha=0.3)

# 滚动预测性
x_rolling = np.arange(0, n_points - window, step) + window // 2
axes[2, 0].plot(x_rolling, rolling_pred, 'crimson', linewidth=1)
axes[2, 0].axvline(half, color='red', linestyle='--', alpha=0.5)
axes[2, 0].set_xlabel('时间')
axes[2, 0].set_ylabel('预测性得分')
axes[2, 0].set_title('莫比乌斯滚动预测性（趋势期高，震荡期低）')
axes[2, 0].grid(True, alpha=0.3)

# 时间对比
axes[2, 1].bar(['传统\n(自相关)', '莫比乌斯\n(扭转加权)'],
               [t_trad * 1000, t_mob * 1000],
               color=['steelblue', 'crimson'], alpha=0.8)
axes[2, 1].set_ylabel('时间 (ms)')
axes[2, 1].set_title(f'计算时间 (加速 {t_trad / t_mob:.1f}x)')
axes[2, 1].grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('benchmark_predictability.png', dpi=150)
plt.show()
print("\n图已保存: benchmark_predictability.png")
