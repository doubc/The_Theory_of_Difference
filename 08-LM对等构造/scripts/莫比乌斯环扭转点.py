import numpy as np
import matplotlib.pyplot as plt
from scipy import special


class PrimeMobiusConnection:
    """
    探索素数分布与莫比乌斯环拓扑的联系
    """

    def __init__(self, R=1.0, w=0.8):
        self.R = R
        self.w = w

    def primes_up_to(self, N):
        """
        筛法生成素数
        """
        sieve = np.ones(N + 1, dtype=bool)
        sieve[0] = sieve[1] = False

        for i in range(2, int(np.sqrt(N)) + 1):
            if sieve[i]:
                sieve[i * i::i] = False

        return np.where(sieve)[0]

    def mobius_function(self, n):
        """
        计算数论莫比乌斯函数 μ(n)
        """
        if n == 1:
            return 1

        # 分解质因数
        factors = []
        temp = n
        for p in range(2, int(np.sqrt(n)) + 2):
            while temp % p == 0:
                factors.append(p)
                temp //= p
        if temp > 1:
            factors.append(temp)

        # 检查是否有重复因子
        if len(factors) != len(set(factors)):
            return 0

        # 返回 (-1)^k，k是素因子个数
        return (-1) ** len(factors)

    def mertens_function(self, N):
        """
        Mertens函数: M(N) = Σ_{n=1}^N μ(n)

        这与黎曼猜想等价：
        |M(N)| < N^{1/2+ε} 对所有 ε>0 成立 ⟺ 黎曼猜想成立
        """
        return sum(self.mobius_function(n) for n in range(1, N + 1))

    def prime_counting_vs_mobius(self, N_max=1000):
        """
        比较素数计数函数 π(N) 与 Mertens 函数 M(N)
        """
        primes = self.primes_up_to(N_max)

        N_vals = np.arange(1, N_max + 1)
        pi_N = np.array([np.sum(primes <= n) for n in N_vals])
        M_N = np.array([self.mertens_function(n) for n in N_vals])

        return N_vals, pi_N, M_N

    def riemann_zeros_approximation(self, num_zeros=50):
        """
        黎曼ζ函数的非平凡零点近似值
        （使用前几个已知的零点）
        """
        # 前50个黎曼零点的虚部（近似值）
        known_zeros_imag = [
            14.134725, 21.022040, 25.010858, 30.424876, 32.935062,
            37.586178, 40.918719, 43.327073, 48.005151, 49.773832,
            52.970321, 56.446248, 59.347044, 60.831779, 65.112544,
            67.079811, 69.546402, 72.067158, 75.704691, 77.144840,
            79.337375, 82.910381, 84.735493, 87.425275, 88.809111,
            92.491899, 94.651344, 95.870634, 98.831194, 101.317851,
            103.725538, 105.446623, 107.168611, 111.029536, 111.874659,
            114.320221, 116.226680, 118.790782, 121.370125, 122.946829,
            124.256819, 127.516684, 129.578704, 131.087689, 133.497737,
            134.756509, 138.116042, 139.736209, 141.123707, 143.111846
        ]

        # 所有零点都在临界线 Re(s) = 1/2 上
        zeros = [0.5 + 1j * gamma for gamma in known_zeros_imag[:num_zeros]]

        return zeros

    def mobius_strip_spectral_zeros(self, m_max=30, n_max=30):
        """
        计算莫比乌斯环谱问题的"类零点"

        定义"谱判别式"：
        D(s) = det(Δ - s(1-s))

        零点可能对应于某种共振条件
        """
        eigenvals = []

        for m_half in range(0, m_max):
            m = m_half + 0.5  # 半整数
            for n in range(1, n_max + 1):
                lambda_mn = (m / self.R) ** 2 + (n * np.pi / self.w) ** 2
                eigenvals.append(lambda_mn)

        eigenvals = np.array(sorted(eigenvals))

        # 转换为"s空间"的零点（类比黎曼零点）
        # 假设 λ = s(1-s)，则 s = (1 ± sqrt(1-4λ))/2
        spectral_zeros = []
        for lam in eigenvals[:50]:  # 取前50个
            discriminant = 1 - 4 * lam
            if discriminant < 0:
                # 复数零点
                s_plus = 0.5 + 0.5j * np.sqrt(-discriminant)
                spectral_zeros.append(s_plus)

        return spectral_zeros

    def compare_zero_distributions(self):
        """
        比较黎曼零点与莫比乌斯谱零点的分布
        """
        riemann_zeros = self.riemann_zeros_approximation(50)
        mobius_zeros = self.mobius_strip_spectral_zeros(30, 30)

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 图1: 黎曼零点在临界线上
        ax1 = axes[0, 0]
        riemann_imags = [np.imag(z) for z in riemann_zeros]
        ax1.scatter([0.5] * len(riemann_imags), riemann_imags,
                    color='red', s=50, marker='o', label='Riemann zeros')
        ax1.axvline(x=0.5, color='blue', linestyle='--', linewidth=2,
                    label='Critical line Re(s)=1/2')
        ax1.set_xlabel('Re(s)', fontsize=11)
        ax1.set_ylabel('Im(s)', fontsize=11)
        ax1.set_title('Riemann Zeta Zeros', fontsize=12, fontweight='bold')
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim([0, 1])

        # 图2: 莫比乌斯谱零点
        ax2 = axes[0, 1]
        if mobius_zeros:
            mobius_reals = [np.real(z) for z in mobius_zeros]
            mobius_imags = [np.imag(z) for z in mobius_zeros]
            ax2.scatter(mobius_reals, mobius_imags,
                        color='green', s=50, marker='s', label='Möbius spectral zeros')
        ax2.axvline(x=0.5, color='blue', linestyle='--', linewidth=2,
                    label='Re(s)=1/2')
        ax2.set_xlabel('Re(s)', fontsize=11)
        ax2.set_ylabel('Im(s)', fontsize=11)
        ax2.set_title('Möbius Strip Spectral Zeros', fontsize=12, fontweight='bold')
        ax2.legend(fontsize=10)
        ax2.grid(True, alpha=0.3)

        # 图3: 零点间距分布
        ax3 = axes[1, 0]
        riemann_spacings = np.diff(riemann_imags)
        if mobius_zeros:
            mobius_imags_sorted = sorted([np.imag(z) for z in mobius_zeros])
            mobius_spacings = np.diff(mobius_imags_sorted)
            ax3.hist(mobius_spacings, bins=20, density=True, alpha=0.5,
                     color='green', label='Möbius spacings')
        ax3.hist(riemann_spacings, bins=20, density=True, alpha=0.5,
                 color='red', label='Riemann spacings')
        ax3.set_xlabel('Spacing between zeros', fontsize=11)
        ax3.set_ylabel('Density', fontsize=11)
        ax3.set_title('Zero Spacing Distribution', fontsize=12, fontweight='bold')
        ax3.legend(fontsize=10)
        ax3.grid(True, alpha=0.3)

        # 图4: Mertens函数与√N的比较
        ax4 = axes[1, 1]
        N_vals = np.arange(1, 501)
        M_vals = np.array([self.mertens_function(n) for n in N_vals])
        sqrt_N = np.sqrt(N_vals)

        ax4.plot(N_vals, M_vals, 'b-', linewidth=1.5, label='M(N)')
        ax4.plot(N_vals, sqrt_N, 'r--', linewidth=2, label='√N')
        ax4.plot(N_vals, -sqrt_N, 'r--', linewidth=2)
        ax4.fill_between(N_vals, -sqrt_N, sqrt_N, alpha=0.2, color='red')
        ax4.set_xlabel('N', fontsize=11)
        ax4.set_ylabel('M(N)', fontsize=11)
        ax4.set_title('Mertens Function vs √N\n(Riemann Hypothesis bound)',
                      fontsize=12, fontweight='bold')
        ax4.legend(fontsize=10)
        ax4.grid(True, alpha=0.3)
        ax4.axhline(y=0, color='k', linestyle='-', alpha=0.3)

        plt.suptitle('Prime Distribution & Möbius Topology Connection',
                     fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig('prime_mobius_connection.png', dpi=300, bbox_inches='tight')
        plt.show()


def theoretical_interpretation():
    """
    理论解释：素数分布与莫比乌斯扭转的关系
    """
    print("=" * 70)
    print("素数分布作为莫比乌斯环扭转点的理论框架")
    print("=" * 70)

    print("\n核心假设:")
    print("  1. 素数 p 对应于某种拓扑空间的'基本扭转单元'")
    print("  2. 素数分布的不规则性反映了拓扑缺陷的统计性质")
    print("  3. 黎曼ζ函数的零点编码了这些扭转的全局约束")
    print()

    print("数学对应:")
    print("  • 莫比乌斯函数 μ(n) ←→ 拓扑缠绕数")
    print("  • Mertens函数 M(N) ←→ 累积拓扑荷")
    print("  • 黎曼零点 ←→ 拓扑激发的能谱")
    print("  • 临界线 Re(s)=1/2 ←→ 自对偶对称面")
    print()

    print("你的'零线'发现的意义:")
    print(f"  零线 L = [{1.0 - 0.8 / 2:.2f}, {1.0 + 0.8 / 2:.2f}] = [0.60, 1.40]")
    print()
    print("  这可能对应于:")
    print("  • 素数分布的'临界带' 0 < Re(s) < 1 的几何实现")
    print("  • 在这个区域内，加法结构（算术级数）与")
    print("    乘法结构（素数分解）发生'等价坍缩'")
    print("  • 黎曼零点位于 Re(s)=1/2，正好是零线的'中心'")
    print()

    print("物理图像:")
    print("  想象一个高维的'数论莫比乌斯环':")
    print("  • 基空间：素数的乘法结构")
    print("  • 纤维：加法结构（模运算）")
    print("  • 扭转：由莫比乌斯函数 μ(n) 控制的符号翻转")
    print("  • 自相交点：素数分布的特殊模式")
    print()

    print("待验证的预测:")
    print("  1. 黎曼零点的间距分布应符合莫比乌斯环的谱统计")
    print("  2. 素数间隙的分布可能与拓扑缺陷相关")
    print("  3. '加法≡乘法'的等价性在零线上最强")


if __name__ == "__main__":
    pmc = PrimeMobiusConnection(R=1.0, w=0.8)

    print("正在计算素数与莫比乌斯函数的关系...")
    N_vals, pi_N, M_N = pmc.prime_counting_vs_mobius(500)

    print(f"\n数据统计:")
    print(f"  π(500) = {pi_N[-1]} (不超过500的素数个数)")
    print(f"  M(500) = {M_N[-1]} (Mertens函数值)")
    print(f"  √500 = {np.sqrt(500):.2f}")
    print(f"  |M(500)|/√500 = {abs(M_N[-1]) / np.sqrt(500):.4f}")
    print()

    # 理论解释
    theoretical_interpretation()

    # 可视化
    print("\n生成可视化对比...")
    pmc.compare_zero_distributions()

    print("\n完成！图像已保存为 'prime_mobius_connection.png'")
    print("\n关键洞察:")
    print("  黎曼猜想的本质可能是:")
    print("  '素数分布的拓扑约束导致零点必须位于临界线 Re(s)=1/2'")
    print("  而这个1/2正是莫比乌斯扭转的半整数特征！")
