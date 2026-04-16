"""用多项式拟合反推 α1 和 α2"""

import math
import bisect

phi = (1 + 5**0.5) / 2

def sieve_primes(n):
    is_prime = bytearray(b'\x01') * (n + 1)
    is_prime[0] = is_prime[1] = 0
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = bytearray(len(is_prime[i*i::i]))
    return [i for i in range(2, n + 1) if is_prime[i]]

N = 100_000_000
primes = sieve_primes(N)

counts = []
for i in range(2, len(primes) - 1):
    p_k = primes[i]
    p_km1 = primes[i-1]
    right = p_k + p_km1
    if right > N:
        break
    c = bisect.bisect_right(primes, right) - bisect.bisect_left(primes, p_k + 1)
    counts.append(c)

# 收集 (1/ln(p_k), alpha_measured) 的数据点，用于线性回归
# alpha_measured = alpha_1 + alpha_2 * (1/ln(p_k)) + alpha_3 * (1/ln(p_k))^2 + ...
points = []
for idx in range(20000, len(counts)):
    if idx + 2 < len(primes):
        k = idx + 2
        p_k = primes[k]
        p_km1 = primes[k-1]
        c = counts[idx]
        inv_ln = 1.0 / math.log(p_k)
        val = c * math.log(p_k) / p_km1
        alpha_meas = (1 - val) * math.log(p_k)
        if 0.3 < alpha_meas < 0.45:  # 剔除异常值
            points.append((inv_ln, alpha_meas))

print(f"有效数据点: {len(points)}")

# 线性回归: alpha_meas = alpha_1 + alpha_2 * inv_ln
n = len(points)
sx = sum(p[0] for p in points)
sy = sum(p[1] for p in points)
sxx = sum(p[0]**2 for p in points)
sxy = sum(p[0]*p[1] for p in points)

det = n * sxx - sx**2
alpha_1 = (sxx * sy - sx * sxy) / det
alpha_2 = (n * sxy - sx * sy) / det

print(f"\n线性拟合: α_measured = α_1 + α_2 / ln(p)")
print(f"  α_1 = {alpha_1:.10f}")
print(f"  α_2 = {alpha_2:.10f}")
print(f"  2-φ = {2-phi:.10f}")
print(f"  差值 = {alpha_1 - (2-phi):.10f}")

# 二次拟合: alpha_meas = alpha_1 + alpha_2 * inv_ln + alpha_3 * inv_ln^2
sxxx = sum(p[0]**3 for p in points)
sxxy = sum(p[0]**2 * p[1] for p in points)
sxxxx = sum(p[0]**4 for p in points)

# 用 numpy 风格的公式解 3x3 系统
# [n, sx, sxx] [a1]   [sy]
# [sx, sxx, sxxx] [a2] = [sxy]
# [sxx, sxxx, sxxxx] [a3]   [sxxy]

import numpy as np

A = np.array([[n, sx, sxx],
              [sx, sxx, sxxx],
              [sxx, sxxx, sxxxx]])
b = np.array([sy, sxy, sxxy])

result = np.linalg.solve(A, b)
a1, a2, a3 = result

print(f"\n二次拟合: α_measured = α_1 + α_2/ln(p) + α_3/ln²(p)")
print(f"  α_1 = {a1:.10f}")
print(f"  α_2 = {a2:.10f}")
print(f"  α_3 = {a3:.10f}")
print(f"  2-φ = {2-phi:.10f}")
print(f"  差值 = {a1 - (2-phi):.10f}")

# 检验拟合质量：残差
residuals_linear = [p[1] - (alpha_1 + alpha_2 * p[0]) for p in points]
residuals_quad = [p[1] - (a1 + a2 * p[0] + a3 * p[0]**2) for p in points]

rmse_linear = (sum(r**2 for r in residuals_linear) / n)**0.5
rmse_quad = (sum(r**2 for r in residuals_quad) / n)**0.5

print(f"\n拟合质量:")
print(f"  线性 RMSE: {rmse_linear:.6f}")
print(f"  二次 RMSE: {rmse_quad:.6f}")
print(f"  改善比例: {(1 - rmse_quad/rmse_linear)*100:.1f}%")
