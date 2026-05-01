"""扩大到 10^8，精确验证修正项常数"""

import math
import bisect

phi = (1 + 5**0.5) / 2
alpha_target = 2 - phi

def sieve_primes(n):
    is_prime = bytearray(b'\x01') * (n + 1)
    is_prime[0] = is_prime[1] = 0
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = bytearray(len(is_prime[i*i::i]))
    return [i for i in range(2, n + 1) if is_prime[i]]

print("筛法开始...")
N = 100_000_000  # 10^8
primes = sieve_primes(N)
print(f"素数个数: {len(primes)}")

print("计算窗口素数个数...")
counts = []
for i in range(2, len(primes) - 1):
    p_k = primes[i]
    p_km1 = primes[i-1]
    right = p_k + p_km1
    if right > N:
        break
    c = bisect.bisect_right(primes, right) - bisect.bisect_left(primes, p_k + 1)
    counts.append(c)
print(f"有效窗口数: {len(counts)}")

# 精确检验
print(f"\n2 - φ = {alpha_target:.10f}")
print(f"\n{'k':>10} {'p_k':>14} {'实测α':>12} {'差值':>12} {'误差%':>10}")
print("-" * 62)

checkpoints = [500, 2000, 5000, 10000, 20000, 50000,
               100000, 200000, 500000, 1000000, 2000000, 3000000, 4000000]

for idx in checkpoints:
    if idx < len(counts) and idx + 2 < len(primes):
        k = idx + 2
        p_k = primes[k]
        p_km1 = primes[k-1]
        c = counts[idx]
        val = c * math.log(p_k) / p_km1
        measured = (1 - val) * math.log(p_k)
        diff = measured - alpha_target
        pct = 100 * abs(diff) / alpha_target if alpha_target != 0 else 0
        print(f"{k:>10} {p_k:>14} {measured:>12.6f} {diff:>12.6f} {pct:>10.2f}")

# 趋势分析：误差是否随 k 单调递减
print(f"\n误差趋势（中段）:")
errors = []
for idx in range(2000, min(len(counts), 500000)):
    if idx + 2 < len(primes):
        k = idx + 2
        p_k = primes[k]
        p_km1 = primes[k-1]
        c = counts[idx]
        val = c * math.log(p_k) / p_km1
        measured = (1 - val) * math.log(p_k)
        errors.append(abs(measured - alpha_target))

# 每 10000 个取平均
print(f"{'k 区间':>20} {'平均误差':>12}")
for start in range(0, len(errors), 10000):
    end = min(start + 10000, len(errors))
    chunk = errors[start:end]
    avg = sum(chunk) / len(chunk)
    k_start = start + 2002
    k_end = end + 2001
    print(f"[{k_start:>8}, {k_end:>8}] {avg:>12.6f}")
