"""按层级分段检验修正的 φ 压缩"""

import bisect
import math

phi = (1 + 5 ** 0.5) / 2


def sieve_primes(n):
    is_prime = bytearray(b'\x01') * (n + 1)
    is_prime[0] = is_prime[1] = 0
    for i in range(2, int(n ** 0.5) + 1):
        if is_prime[i]:
            is_prime[i * i::i] = bytearray(len(is_prime[i * i::i]))
    return [i for i in range(2, n + 1) if is_prime[i]]


N = 100_000_000
primes = sieve_primes(N)

counts = []
for i in range(2, len(primes) - 1):
    p_k = primes[i]
    p_km1 = primes[i - 1]
    right = p_k + p_km1
    if right > N:
        break
    c = bisect.bisect_right(primes, right) - bisect.bisect_left(primes, p_k + 1)
    counts.append(c)

alpha_target = 2 - phi

# 按 log10(p_k) 的整数部分分层
# 层级 m: log10(p_k) ∈ [m, m+1)
levels = {}
for idx in range(1000, len(counts)):
    if idx + 2 < len(primes):
        k = idx + 2
        p_k = primes[k]
        p_km1 = primes[k - 1]
        c = counts[idx]
        val = c * math.log(p_k) / p_km1
        alpha_meas = (1 - val) * math.log(p_k)
        if 0.3 < alpha_meas < 0.45:
            level = int(math.log10(p_k))
            if level not in levels:
                levels[level] = []
            levels[level].append(alpha_meas)

print("按 log10(p_k) 分层的实测 α:")
print(f"{'层级':>8} {'log10(p)范围':>15} {'均值':>10} {'中位数':>10} {'与2-φ差':>10}")
print("-" * 58)

level_means = {}
for level in sorted(levels.keys()):
    vals = levels[level]
    avg = sum(vals) / len(vals)
    med = sorted(vals)[len(vals) // 2]
    diff = avg - alpha_target
    level_means[level] = avg
    lo = 10 ** level
    hi = 10 ** (level + 1)
    print(f"{level:>8} [{lo:>6.0e}, {hi:>6.0e}) {avg:>10.6f} {med:>10.6f} {diff:>10.6f}")

# 检验相邻层级的差值是否按 φ 压缩
print(f"\n相邻层级均值差:")
print(f"{'层级对':>12} {'差值':>10} {'差值·φ':>10} {'比值':>10}")
print("-" * 48)

sorted_levels = sorted(level_means.keys())
for i in range(1, len(sorted_levels)):
    l_prev = sorted_levels[i - 1]
    l_curr = sorted_levels[i]
    diff = level_means[l_curr] - level_means[l_prev]
    if i > 1:
        prev_diff = level_means[sorted_levels[i - 1]] - level_means[sorted_levels[i - 2]]
        ratio = diff / prev_diff if prev_diff != 0 else 0
        print(f"[{l_prev},{l_curr}] {diff:>10.6f} {diff * phi:>10.6f} {ratio:>10.4f}")
    else:
        print(f"[{l_prev},{l_curr}] {diff:>10.6f} {diff * phi:>10.6f} {'--':>10}")

# 检验：如果修正 = delta / phi^m，反推 delta
print(f"\n反推层级修正系数 δ:")
print(f"{'层级m':>8} {'实测α':>10} {'δ = (α-α₁)·φ^m':>18}")
print("-" * 40)

for level in sorted(level_means.keys()):
    avg = level_means[level]
    delta = (avg - alpha_target) * (phi ** level)
    print(f"{level:>8} {avg:>10.6f} {delta:>18.6f}")

# 关键检验：delta 是否趋向常数
print(f"\n如果 δ 收敛到常数，说明修正确实是 δ/φ^m 形式")
