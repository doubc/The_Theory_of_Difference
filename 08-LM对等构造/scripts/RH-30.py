"""验证素数展开规律"""

def sieve_primes(n):
    """埃拉托色尼筛法，返回 <= n 的所有素数"""
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, n + 1, i):
                is_prime[j] = False
    return [i for i in range(2, n + 1) if is_prime[i]]

N = 1000_000_000  # 筛到一千万
primes = sieve_primes(N)
print(f"素数个数: {len(primes)}")
print(f"最大素数: {primes[-1]}")
print()

# === 检验一：Bertrand 公设 p_{k+1} < 2*p_k ===
violations_bertrand = 0
for i in range(len(primes) - 1):
    if primes[i+1] >= 2 * primes[i]:
        violations_bertrand += 1
        print(f"  Bertrand 违反: p_{i}={primes[i]}, p_{i+1}={primes[i+1]}")
print(f"Bertrand (p_{{k+1}} < 2*p_k): {violations_bertrand} 次违反")

# === 检验二：加法递推 p_{k+1} <= p_k + p_{k-1} ===
violations_add = 0
max_ratio = 0
for i in range(1, len(primes) - 1):
    gap = primes[i+1] - primes[i]
    bound = primes[i-1]
    ratio = gap / bound
    if ratio > max_ratio:
        max_ratio = ratio
    if primes[i+1] > primes[i] + primes[i-1]:
        violations_add += 1
        if violations_add <= 5:
            print(f"  加法违反: p_{{k-1}}={primes[i-1]}, p_k={primes[i]}, p_{{k+1}}={primes[i+1]}")
print(f"加法 (p_{{k+1}} <= p_k + p_{{k-1}}): {violations_add} 次违反")
print(f"最大 gap/p_{{k-1}} 比值: {max_ratio:.6f}")

# === 检验三：更紧的界 p_{k+1} <= p_k + c*sqrt(p_k)*ln(p_k) ===
import math
for c in [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]:
    violations = 0
    for i in range(2, len(primes) - 1):
        gap = primes[i+1] - primes[i]
        bound = c * math.sqrt(primes[i]) * math.log(primes[i])
        if gap > bound:
            violations += 1
    print(f"c={c:5.1f}: gap > c*sqrt(p)*ln(p) 违反 {violations} 次")

# === 检验四：间隙的统计 ===
gaps = [primes[i+1] - primes[i] for i in range(len(primes)-1)]
print(f"\n间隙统计:")
print(f"  平均间隙: {sum(gaps)/len(gaps):.4f}")
print(f"  最大间隙: {max(gaps)} (在 p={primes[gaps.index(max(gaps))]} 之后)")
print(f"  最大间隙/p_k: {max(gaps)/primes[gaps.index(max(gaps))]:.6f}")

# === 检验五：展开螺旋比值 ===
print(f"\n展开比值 p_{{k+1}}/p_k:")
for i in [1, 2, 5, 10, 20, 50, 100, 1000]:
    if i < len(primes):
        print(f"  p_{i+1}/p_{i} = {primes[i]}/{primes[i-1]} = {primes[i]/primes[i-1]:.4f}")

# === 检验六：间隙之和与 Fibonacci 的关系 ===
print(f"\n间隙之和 g_k + g_{{k-1}} vs p_k:")
for i in range(1, min(20, len(gaps))):
    print(f"  g_{i}+g_{i-1}={gaps[i]}+{gaps[i-1]}={gaps[i]+gaps[i-1]}, p_{i}={primes[i]}, "
          f"比值={(gaps[i]+gaps[i-1])/primes[i]:.4f}")
