"""关键检验：窗口递推与素数递推的关系"""

import math
import bisect

def sieve_primes(n):
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, n + 1, i):
                is_prime[j] = False
    return [i for i in range(2, n + 1) if is_prime[i]]

N = 10_000_000
primes = sieve_primes(N)

# 窗口素数个数
counts = []
for i in range(2, len(primes) - 1):
    p_k = primes[i]
    p_km1 = primes[i-1]
    left = p_k + 1
    right = min(p_k + p_km1, N)  # 避免越界
    c = bisect.bisect_right(primes, right) - bisect.bisect_left(primes, left)
    counts.append(c)

# === 检验一：c_k / (c_{k-1} + c_{k-2}) 的分布 ===
print("检验一：窗口递推比值分布")
print("=" * 50)

ratios = []
for idx in range(2, len(counts)):
    denom = counts[idx-1] + counts[idx-2]
    if denom > 0:
        ratios.append(counts[idx] / denom)

ratios.sort()
print(f"样本数: {len(ratios)}")
print(f"最大值: {ratios[-1]:.6f}")
print(f"99.9%分位: {ratios[int(len(ratios)*0.999)]:.6f}")
print(f"99%分位: {ratios[int(len(ratios)*0.99)]:.6f}")
print(f"中位数: {ratios[len(ratios)//2]:.4f}")

# === 检验二：等号情形——最大比值的具体实例 ===
print(f"\n检验二：比值最大的 10 个实例")
print("=" * 70)
print(f"{'k':>6} {'p_k':>10} {'c_k':>6} {'c_{{k-1}}+c_{{k-2}}':>15} {'比值':>10}")
print("-" * 55)

ratio_list = []
for idx in range(2, len(counts)):
    denom = counts[idx-1] + counts[idx-2]
    if denom > 0:
        ratio_list.append((idx, counts[idx] / denom, counts[idx], denom))

ratio_list.sort(key=lambda x: -x[1])
for idx, r, c_k, denom in ratio_list[:10]:
    k = idx + 2  # 对应 primes[k]
    print(f"{k:>6} {primes[k]:>10} {c_k:>6} {denom:>15} {r:>10.6f}")

# === 检验三：c_k 递推与 g_k 递推的精确关系 ===
print(f"\n检验三：窗口递推 → 素数递推的推导验证")
print("=" * 70)

# 如果 c_k ≤ c_{k-1} + c_{k-2}，那么：
# p_{k-1}/ln(p_k) ≲ p_{k-2}/ln(p_{k-1}) + p_{k-3}/ln(p_{k-2})
# 这是否蕴含 g_k ≤ p_{k-1}？

# 反过来检验：用实际的 c_k 和素数定理反推 g_k
print(f"{'k':>6} {'g_k':>6} {'p_{{k-1}}':>10} {'g_k/p_{{k-1}}':>12} {'c_k/(c_{{k-1}}+c_{{k-2}})':>20}")
print("-" * 60)

for idx in [2, 5, 10, 20, 50, 100, 500, 2000, 5000]:
    if idx < len(counts) and idx + 2 < len(primes):
        k = idx + 2
        g_k = primes[k+1] - primes[k] if k+1 < len(primes) else 0
        p_km1 = primes[k-1]
        denom = counts[idx-1] + counts[idx-2] if idx >= 2 else 1
        c_ratio = counts[idx] / denom if denom > 0 else 0
        print(f"{k:>6} {g_k:>6} {p_km1:>10} {g_k/p_km1:>12.6f} {c_ratio:>20.6f}")

# === 检验四：修正项的结构 ===
print(f"\n检验四：修正项 1 - count·ln(p)/p_{{k-1}} 的行为")
print("=" * 60)
print(f"{'k':>6} {'修正项':>12} {'修正·ln(p)':>12}")
print("-" * 35)

for idx in [100, 500, 2000, 5000, 10000, 20000, 50000]:
    if idx < len(counts) and idx + 2 < len(primes):
        k = idx + 2
        p_k = primes[k]
        p_km1 = primes[k-1]
        c = counts[idx]
        val = c * math.log(p_k) / p_km1
        correction = 1 - val
        print(f"{k:>6} {correction:>12.6f} {correction * math.log(p_k):>12.4f}")

# === 检验五：窗口递推是否比素数递推更容易证明 ===
print(f"\n检验五：c_k ≤ c_{{k-1}} + c_{{k-2}} 的直接论证")
print("=" * 60)
print("窗口 (p_k, p_k+p_{{k-1}}] 的素数个数 c_k")
print("= π(p_k + p_{{k-1}}) - π(p_k)")
print()
print("如果 c_k ≤ c_{{k-1}} + c_{{k-2}}，即：")
print("π(p_k + p_{{k-1}}) - π(p_k) ≤ π(p_{{k-1}} + p_{{k-2}}) - π(p_{{k-1}})")
print("  + π(p_{{k-2}} + p_{{k-3}}) - π(p_{{k-2}})")
print()
print("用素数定理 π(x) ~ x/ln(x)：")
print("左边 ~ p_{{k-1}}/ln(p_k)")
print("右边 ~ p_{{k-2}}/ln(p_{{k-1}}) + p_{{k-3}}/ln(p_{{k-2}})")
print()
print("因为 p_{{k-1}} ~ p_{{k-2}} ~ p_{{k-3}} ~ k·ln(k)：")
print("左边 ~ k·ln(k)/ln(k·ln(k)) ~ k")
print("右边 ~ k·ln(k)/ln(k·ln(k)) + k·ln(k)/ln(k·ln(k)) ~ 2k")
print()
print("左边 ≤ 右边 自动成立（k ≤ 2k）")
print("这意味着 c_k ≤ c_{{k-1}} + c_{{k-2}} 是素数定理的直接推论！")
