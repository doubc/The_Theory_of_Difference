import matplotlib.pyplot as plt
import numpy as np


class MoebiusElement:
    def __init__(self, b, f, epsilon):
        self.b = b  # 基空間位置 (Base)
        self.f = f  # 纖維振幅 (Fiber)
        self.eps = epsilon  # 扭轉狀態 (+1 或 -1)

    def __repr__(self):
        return f"M(b={self.b:.4f}, f={self.f:.4f}, eps={self.eps})"


def moeb_compose(p1, p2):
    """ 實現公理 (P1, P2, P3): 莫比烏斯合成運算 """
    new_b = p1.b + p2.b
    new_f = p1.f + (p1.eps * p2.f)  # 纖維受扭轉狀態影響
    new_eps = p1.eps * p2.eps
    return MoebiusElement(new_b, new_f, new_eps)


def calculate_zeta_minus_one(limit=10000, t=0.001):
    omega = np.pi
    u_b = 2 * omega

    sigma_t = 0
    for n in range(1, limit):
        val = n * np.exp(-t * (n * u_b))
        sigma_t += val

    # 理论发散项
    divergent_part = 1 / ((u_b * t) ** 2)

    # 提取残差
    residual = sigma_t - divergent_part
    return residual


# --- 執行驗證 ---

# 1. 驗證加法的非交換性 (T15)
p = MoebiusElement(0, 1.0, -1)  # 翻面元素
q = MoebiusElement(0, 1.0, 1)  # 正面元素

pq = moeb_compose(p, q)
qp = moeb_compose(q, p)

print("--- 1. 非交換性驗證 ---")
print(f"p o q = {pq}")
print(f"q o p = {qp}")
print(f"兩者相等嗎? {np.isclose(pq.f, qp.f)}\n")

# 2. 提取拓撲殘餘 -1/12 (收敛性测试与绘图)
print("--- 2. 莫比烏斯正則化提取 (收敛性测试) ---")
target = -1 / 12
t_values = np.linspace(0.01, 0.2, 20)
residuals = []

for t_val in t_values:
    # N 需要足够大以保证级数收敛，通常 N > 10/t 即可
    n_limit = int(15 / t_val)
    res = calculate_zeta_minus_one(n_limit, t_val)
    residuals.append(res)
    if t_val in [0.1, 0.05, 0.02, 0.01]:
        print(f"t={t_val:.3f}, N={n_limit}: 残差 = {res:.8f}, 误差 = {abs(res - target):.2e}")

print(f"\n理论目标值 (-1/12):   {target:.8f}")

# --- 绘图部分 ---
plt.figure(figsize=(10, 6))
plt.plot(t_values, residuals, 'b-o', markersize=4, label='Numerical Residual')
plt.axhline(y=target, color='r', linestyle='--', label=f'Theoretical Limit (-1/12 ≈ {target:.4f})')
plt.xlabel('Damping Parameter $t$')
plt.ylabel('Regularized Residual')
plt.title('Convergence of Möbius Regularization to -1/12')
plt.legend()
plt.grid(True, linestyle=':', alpha=0.6)
plt.savefig('moebius_zeta_convergence.png', dpi=300, bbox_inches='tight')
plt.show()

print("\n結論: 隨著阻尼 t 趨近於 0，扣除發散項後的殘餘穩定收斂至 -1/12。图表已保存为 moebius_zeta_convergence.png")
