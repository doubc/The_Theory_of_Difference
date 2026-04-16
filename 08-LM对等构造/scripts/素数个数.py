"""局部窗口素数密度 — 优化版（bisect 替换双重循环）"""

import math
import bisect

phi = (1 + 5**0.5) / 2

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
print(f"素数个数: {len(primes)}")

# 用 bisect 统计每个窗口内的素数个数
records = []
for i in range(2, len(primes) - 1):
    p_k = primes[i]
    p_km1 = primes[i-1]
    left = p_k + 1
    right = p_k + p_km1
    count = bisect.bisect_right(primes, right) - bisect.bisect_left(primes, left)
    records.append((i, p_k, p_km1, count))

# === 检验一：占比 ===
print(f"\n{'=' * 60}")
print("检验一：窗口内素数占比 count / p_{k-1}")
print("=" * 60)
print(f"{'k':>6} {'p_k':>10} {'窗口':>10} {'个数':>6} {'占比':>10}")
print("-" * 50)
for idx in [2, 5, 10, 20, 50, 100, 500, 2000, 5000]:
    if idx < len(records):
        i, p_k, p_km1, c = records[idx]
        print(f"{i:>6} {p_k:>10} {p_km1:>10} {c:>6} {c/p_km1:>10.6f}")

# === 检验二：个数 vs 各种候选 ===
print(f"\n{'=' * 60}")
print("检验二：实际个数 vs p/φ vs p/ln(p)")
print("=" * 60)
print(f"{'k':>6} {'实际':>6} {'p/φ':>10} {'p·(φ-1)':>10} {'p/ln(p)':>10}")
print("-" * 50)
for idx in [5, 20, 100, 500, 2000]:
    if idx < len(records):
        i, p_k, p_km1, c = records[idx]
        print(f"{i:>6} {c:>6} {p_km1/phi:>10.1f} {p_km1*(phi-1):>10.1f} {p_km1/math.log(p_k):>10.1f}")

# === 检验三：相邻窗口个数比 ===
print(f"\n{'=' * 60}")
print("检验三：相邻窗口个数比 c_{k}/c_{k-1}")
print("=" * 60)

ratios = []
for idx in range(1, len(records)):
    c_prev = records[idx-1][3]
    c_curr = records[idx][3]
    if c_prev > 0:
        ratios.append(c_curr / c_prev)

print(f"比值个数: {len(ratios)}")
print(f"平均值: {sum(ratios)/len(ratios):.4f}")
print(f"中位数: {sorted(ratios)[len(ratios)//2]:.4f}")
print(f"φ = {phi:.4f}")
print(f"分布:")
for t in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0]:
    below = sum(1 for r in ratios if r < t)
    print(f"  < {t:.1f}: {below:>6} ({100*below/len(ratios):.1f}%)")

# === 检验四：count_k ≤ count_{k-1} + count_{k-2} ? ===
print(f"\n{'=' * 60}")
print("检验四：count_k ≤ count_{k-1} + count_{k-2} ?")
print("=" * 60)

violations = 0
max_ratio = 0
for idx in range(2, len(records)):
    c_k = records[idx][3]
    c_km1 = records[idx-1][3]
    c_km2 = records[idx-2][3]
    denom = c_km1 + c_km2
    if denom > 0:
        r = c_k / denom
        if r > max_ratio:
            max_ratio = r
        if c_k > denom:
            violations += 1

print(f"违反次数: {violations}")
print(f"最大比值: {max_ratio:.4f}")
print(f"φ = {phi:.4f} 参考")

# === 检验五：count · ln(p_k) / p_{k-1} 的渐近值 ===
print(f"\n{'=' * 60}")
print("检验五：count·ln(p_k)/p_{k-1} 渐近值")
print("=" * 60)

multipliers = []
for i, p_k, p_km1, c in records[100:]:
    m = c * math.log(p_k) / p_km1
    multipliers.append(m)

avg = sum(multipliers) / len(multipliers)
med = sorted(multipliers)[len(multipliers) // 2]
std = (sum((m - avg)**2 for m in multipliers) / len(multipliers))**0.5
print(f"样本数: {len(multipliers)}")
print(f"平均值: {avg:.6f}")
print(f"中位数: {med:.6f}")
print(f"标准差: {std:.6f}")
print(f"1/φ = {1/phi:.6f}")
print(f"φ-1 = {phi-1:.6f}")
print(f"1/ln(2) = {1/math.log(2):.6f}")

# === 检验六：这个渐近值是否随 k 变化 ===
print(f"\n{'=' * 60}")
print("检验六：渐近值随 k 的变化")
print("=" * 60)

slices = [
    (100, 500),
    (500, 2000),
    (2000, 5000),
    (5000, 10000),
    (10000, 20000),
    (20000, len(records)),
]

print(f"{'k 范围':>20} {'平均值':>10} {'中位数':>10}")
print("-" * 45)
for start, end in slices:
    if end <= len(records):
        vals = []
        for i, p_k, p_km1, c in records[start:end]:
            vals.append(c * math.log(p_k) / p_km1)
        a = sum(vals) / len(vals)
        m = sorted(vals)[len(vals) // 2]
        print(f"{f'[{start}, {end})':>20} {a:>10.6f} {m:>10.6f}")

# === 检验七：最小密度窗口 ===
print(f"\n{'=' * 60}")
print("检验七：密度最小的 15 个窗口")
print("=" * 60)
print(f"{'k':>6} {'p_k':>12} {'窗口':>10} {'个数':>6} {'密度':>10}")
print("-" * 50)
sorted_recs = sorted(records, key=lambda r: r[3] / r[2] if r[2] > 0 else 1)
for i, p_k, p_km1, c in sorted_recs[:15]:
    print(f"{i:>6} {p_k:>12} {p_km1:>10} {c:>6} {c/p_km1:>10.6f}")
