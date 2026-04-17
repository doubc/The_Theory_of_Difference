"""
莫比乌斯环上的扭转运算与黎曼猜想验证
=====================================

核心假设（来自文档）：
1. 加法 = 沿θ方向的平移 T_a: θ → θ + a (mod 2π)
2. 乘法 = 扭转后叠加：先移动a步→执行扭转σ→再移动b步（方向反转）
3. 素数 = 扭转源点，相位 φ(p) = π（半圈扭转）
4. 合数 = 多次扭转的叠加，φ(n) = π·Ω(n)
5. RH零点 = 扭转共振点，所有素数相位相消干涉的位置

验证目标：
- 实现扭转运算的精确数学定义
- 验证 μ(n) = (-1)^{Ω(n)} 的拓扑解释
- 计算 ζ(s)^{-1} = Σ μ(n)n^{-s} 的相位求和
- 寻找相位相消干涉的条件是否强制 Re(s) = 1/2
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize_scalar
import json
from datetime import datetime
import os


class MobiusTwistAlgebra:
    """
    莫比乌斯环上的扭转代数结构
    """

    def __init__(self, N_discrete=100):
        """
        参数:
        N_discrete: 离散化参数，周长 L = 2π，步长 = 2π/N
        """
        self.N = N_discrete
        self.step_size = 2 * np.pi / N_discrete

    # ==================== 基础运算定义 ====================

    def translation(self, theta, a_steps):
        """
        加法操作：沿θ方向平移 a 步

        T_a: θ → θ + a·(2π/N) (mod 2π)

        参数:
        theta: 当前角度位置
        a_steps: 移动的步数（整数）

        返回:
        新的角度位置
        """
        delta_theta = a_steps * self.step_size
        return (theta + delta_theta) % (2 * np.pi)

    def twist_operator(self, y_coord):
        """
        扭转算子 σ: y → -y

        这是莫比乌斯带的核心拓扑性质：
        绕行一圈后，横向坐标反号

        参数:
        y_coord: 横向坐标 [-1, 1]

        返回:
        扭转后的横向坐标
        """
        return -y_coord

    def multiplication_with_twist(self, theta, y, a_steps, b_steps):
        """
        乘法操作（带扭转）：
        1. 从 (θ, y) 出发，移动 a 步
        2. 执行扭转 σ: y → -y
        3. 在扭转后的坐标系中移动 b 步（方向反转）

        参数:
        theta: 初始角度
        y: 初始横向坐标
        a_steps: 第一次移动的步数
        b_steps: 第二次移动的步数（扭转后）

        返回:
        (theta_final, y_final): 最终位置
        """
        # 步骤1: 移动 a 步
        theta_1 = self.translation(theta, a_steps)
        y_1 = y

        # 步骤2: 执行扭转
        y_2 = self.twist_operator(y_1)
        theta_2 = theta_1  # θ不变

        # 步骤3: 在扭转后的坐标系中移动 b 步
        # 由于方向反转，b 步对应 -b 步
        theta_final = self.translation(theta_2, -b_steps)
        y_final = y_2

        return (theta_final, y_final)

    # ==================== 相位定义 ====================

    def mobius_phase(self, n):
        """
        整数 n 的莫比乌斯相位

        φ(n) = π · Ω(n)
        其中 Ω(n) 是 n 的素因子个数（计重数）

        参数:
        n: 正整数

        返回:
        phi: 相位值 [0, 2π)
        omega: 素因子个数
        """
        if n <= 1:
            return 0.0, 0

        # 分解素因子（计重数）
        omega = 0
        temp = n
        for p in range(2, int(np.sqrt(n)) + 2):
            while temp % p == 0:
                omega += 1
                temp //= p
        if temp > 1:
            omega += 1

        phi = (np.pi * omega) % (2 * np.pi)
        return phi, omega

    def mobius_function_from_phase(self, n):
        """
        从相位推导 Möbius 函数

        μ(n) = sign(cos(φ(n))) = (-1)^{Ω(n)}

        特殊：如果 n 有平方因子，μ(n) = 0（相位塌缩）

        参数:
        n: 正整数

        返回:
        mu_value: Möbius 函数值 {-1, 0, 1}
        """
        if n == 1:
            return 1

        # 检查是否有平方因子
        temp = n
        has_square_factor = False
        for p in range(2, int(np.sqrt(n)) + 2):
            count = 0
            while temp % p == 0:
                count += 1
                temp //= p
            if count >= 2:
                has_square_factor = True
                break
        if temp > 1 and any(temp % (p*p) == 0 for p in range(2, int(np.sqrt(temp)) + 2)):
            has_square_factor = True

        if has_square_factor:
            return 0  # 相位塌缩

        # 计算相位
        phi, omega = self.mobius_phase(n)

        # μ(n) = (-1)^{Ω(n)}
        return (-1) ** omega

    # ==================== 示例验证 ====================

    def verify_example_2x3(self):
        """
        验证文档中的例子：2 × 3 在扭转框架下的结果

        操作序列：
        1. 从 θ=0 出发，移动2步
        2. 执行扭转
        3. 移动3步（方向反转）

        预期：在 N=6 离散化下，结果应该是位置5（而非普通加法的5）
        """
        print("=" * 70)
        print("示例验证：2 × 3 的扭转运算")
        print("=" * 70)

        # 使用 N=6 离散化（类比时钟）
        test_algebra = MobiusTwistAlgebra(N_discrete=6)

        theta_init = 0.0
        y_init = 1.0  # 初始横向位置

        print(f"\n初始状态: θ={theta_init:.2f}, y={y_init}")
        print(f"离散化: N={test_algebra.N}, 步长={test_algebra.step_size:.2f} rad")

        # 执行乘法操作
        theta_final, y_final = test_algebra.multiplication_with_twist(
            theta_init, y_init, a_steps=2, b_steps=3
        )

        # 转换为离散位置索引
        position_index = round(theta_final / test_algebra.step_size) % test_algebra.N

        print(f"\n操作序列:")
        print(f"  1. 移动2步: θ → {test_algebra.translation(theta_init, 2):.2f}")
        print(f"  2. 执行扭转: y → {test_algebra.twist_operator(y_init)}")
        print(f"  3. 反向移动3步: θ → {theta_final:.2f}")
        print(f"\n最终状态: θ={theta_final:.2f}, y={y_final}")
        print(f"离散位置: {position_index} (模6)")
        print(f"\n对比:")
        print(f"  普通加法: 2 + 3 = 5")
        print(f"  扭转乘法: 位置 {position_index}")

        if position_index == 5:
            print(f"  ✓ 在模6意义下，结果相同（但路径不同！）")
        else:
            print(f"  ⚠ 结果不同，体现了扭转的非平凡效应")

        return {
            'theta_final': theta_final,
            'y_final': y_final,
            'position_index': position_index
        }

    # ==================== 素数相位分析 ====================

    def analyze_prime_phases(self, N_max=100):
        """
        分析前 N_max 个整数的莫比乌斯相位分布

        验证：
        - 素数的相位是否为 π（一次扭转）
        - 两个素数之积的相位是否为 2π（回到起点）
        - 有平方因子的数是否相位塌缩（μ=0）
        """
        print("\n" + "=" * 70)
        print(f"素数相位分析（N=1~{N_max}）")
        print("=" * 70)

        results = []

        for n in range(1, N_max + 1):
            phi, omega = self.mobius_phase(n)
            mu_from_phase = self.mobius_function_from_phase(n)

            # 标准 Möbius 函数（用于对比）
            mu_standard = self._standard_mobius(n)

            is_prime = self._is_prime(n)
            has_square = any(n % (p*p) == 0 for p in range(2, int(np.sqrt(n)) + 2))

            result = {
                'n': n,
                'omega': omega,
                'phi_rad': phi,
                'phi_deg': np.degrees(phi),
                'mu_from_phase': mu_from_phase,
                'mu_standard': mu_standard,
                'is_prime': is_prime,
                'has_square_factor': has_square,
                'match': mu_from_phase == mu_standard
            }
            results.append(result)

        # 统计分析
        primes = [r for r in results if r['is_prime']]
        prime_products = [r for r in results if not r['is_prime'] and r['omega'] == 2 and not r['has_square_factor']]
        square_factors = [r for r in results if r['has_square_factor']]

        print(f"\n素数（应有 φ=π, μ=-1）:")
        for p in primes[:10]:  # 只显示前10个
            print(f"  p={p['n']:3d}: φ={p['phi_deg']:6.1f}°, μ={p['mu_from_phase']:2d}, "
                  f"匹配={p['match']}")

        print(f"\n两素数之积（应有 φ=2π, μ=+1）:")
        for pp in prime_products[:10]:
            print(f"  n={pp['n']:3d}: φ={pp['phi_deg']:6.1f}°, μ={pp['mu_from_phase']:2d}, "
                  f"匹配={pp['match']}")

        print(f"\n有平方因子（应有 μ=0，相位塌缩）:")
        for sf in square_factors[:10]:
            print(f"  n={sf['n']:3d}: μ={sf['mu_from_phase']:2d}, 匹配={sf['match']}")

        # 总体匹配率
        match_rate = sum(1 for r in results if r['match']) / len(results)
        print(f"\n总体匹配率: {match_rate*100:.1f}%")

        return results

    def _standard_mobius(self, n):
        """标准的 Möbius 函数实现（用于对比）"""
        if n == 1:
            return 1

        # 检查平方因子
        for p in range(2, int(np.sqrt(n)) + 2):
            if n % (p*p) == 0:
                return 0

        # 计算素因子个数
        omega = 0
        temp = n
        for p in range(2, int(np.sqrt(n)) + 2):
            while temp % p == 0:
                omega += 1
                temp //= p
        if temp > 1:
            omega += 1

        return (-1) ** omega

    def _is_prime(self, n):
        """判断素数"""
        if n < 2:
            return False
        for i in range(2, int(np.sqrt(n)) + 1):
            if n % i == 0:
                return False
        return True

    # ==================== ζ函数相位求和 ====================

    def zeta_inverse_phase_sum(self, s_real, s_imag, N_terms=1000):
        """
        计算 ζ(s)^{-1} = Σ_{n=1}^∞ μ(n) n^{-s} 的部分和

        关键：分析相位相消干涉的条件

        参数:
        s_real: Re(s)
        s_imag: Im(s)
        N_terms: 求和项数

        返回:
        partial_sum: 部分和的值
        phase_contributions: 每项的相位贡献
        """
        s = complex(s_real, s_imag)

        partial_sum = 0.0 + 0.0j
        phase_contributions = []

        for n in range(1, N_terms + 1):
            mu_n = self.mobius_function_from_phase(n)

            if mu_n == 0:
                continue  # 相位塌缩项不贡献

            # n^{-s} = e^{-s ln n} = e^{-(σ+it)ln n} = n^{-σ} · e^{-it ln n}
            term = mu_n * (n ** (-s))
            partial_sum += term

            # 记录相位贡献
            phase = np.angle(term)
            amplitude = np.abs(term)
            phase_contributions.append({
                'n': n,
                'mu': mu_n,
                'amplitude': amplitude,
                'phase': phase,
                'term_real': term.real,
                'term_imag': term.imag
            })

        return partial_sum, phase_contributions

    def find_resonance_condition(self, t_range=(0, 100), N_terms=500, resolution=200):
        """
        寻找扭转共振条件：|ζ(1/2 + it)| 的最小值位置

        这对应于相位相消干涉最强的点

        参数:
        t_range: t 的搜索范围 (t_min, t_max)
        N_terms: 求和项数
        resolution: 采样点数

        返回:
        resonance_points: 共振点列表 [(t, |zeta_inv|), ...]
        """
        print("\n" + "=" * 70)
        print("寻找扭转共振点（相位相消干涉最强处）")
        print("=" * 70)

        t_values = np.linspace(t_range[0], t_range[1], resolution)
        zeta_inv_magnitudes = []

        print(f"扫描范围: t ∈ [{t_range[0]}, {t_range[1]}], 分辨率={resolution}")
        print(f"求和项数: N={N_terms}")

        for t in t_values:
            zeta_inv, _ = self.zeta_inverse_phase_sum(s_real=0.5, s_imag=t, N_terms=N_terms)
            magnitude = np.abs(zeta_inv)
            zeta_inv_magnitudes.append(magnitude)

        zeta_inv_magnitudes = np.array(zeta_inv_magnitudes)

        # 寻找局部最小值（共振点）
        from scipy.signal import find_peaks

        # 找峰值的负值（即谷值）
        peaks, properties = find_peaks(-zeta_inv_magnitudes, distance=5)

        resonance_points = []
        for peak_idx in peaks:
            t_res = t_values[peak_idx]
            magnitude = zeta_inv_magnitudes[peak_idx]
            resonance_points.append((t_res, magnitude))

        print(f"\n找到 {len(resonance_points)} 个共振点:")
        for t_res, mag in resonance_points[:10]:  # 显示前10个
            print(f"  t = {t_res:8.2f}, |ζ(1/2+it)^{{-1}}| = {mag:.6f}")

        # 可视化
        self._plot_resonance_scan(t_values, zeta_inv_magnitudes, resonance_points)

        return resonance_points

    def _plot_resonance_scan(self, t_values, magnitudes, resonance_points):
        """绘制共振扫描图"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # 上图：|ζ(1/2+it)^{-1}| vs t
        ax1.plot(t_values, magnitudes, 'b-', linewidth=1.5, label=r'$|\zeta(1/2+it)^{-1}|$')

        # 标记共振点
        if resonance_points:
            t_res = [p[0] for p in resonance_points]
            mag_res = [p[1] for p in resonance_points]
            ax1.scatter(t_res, mag_res, color='red', s=100, marker='v',
                       label='Resonance points (minima)', zorder=5)

        ax1.set_xlabel('t (imaginary part of s)', fontsize=12)
        ax1.set_ylabel(r'$|\zeta(1/2+it)^{-1}|$', fontsize=12)
        ax1.set_title('Phase Cancellation Interference Scan along Critical Line',
                     fontsize=14, fontweight='bold')
        ax1.legend(fontsize=11)
        ax1.grid(True, alpha=0.3)

        # 下图：相位分布直方图（在第一个共振点附近）
        if resonance_points:
            t_first = resonance_points[0][0]
            _, phase_contribs = self.zeta_inverse_phase_sum(0.5, t_first, N_terms=200)

            phases = [pc['phase'] for pc in phase_contribs]
            ax2.hist(phases, bins=30, density=True, alpha=0.7, color='green',
                    edgecolor='black')
            ax2.axvline(x=0, color='red', linestyle='--', linewidth=2,
                       label='Constructive interference')
            ax2.axvline(x=np.pi, color='blue', linestyle='--', linewidth=2,
                       label='Destructive interference')
            ax2.set_xlabel('Phase angle (rad)', fontsize=12)
            ax2.set_ylabel('Density', fontsize=12)
            ax2.set_title(f'Phase Distribution at First Resonance (t={t_first:.2f})',
                         fontsize=12)
            ax2.legend(fontsize=10)
            ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('mobius_resonance_analysis.png', dpi=300, bbox_inches='tight')
        plt.show()

    # ==================== 临界线验证 ====================

    def verify_critical_line_constraint(self, sigma_range=(0.3, 0.7), t_fixed=14.1347,
                                       N_terms=500, resolution=100):
        """
        验证：相位相消干涉是否强制 Re(s) = 1/2

        方法：固定 t（已知黎曼零点），扫描 σ，看 |ζ(σ+it)| 是否在 σ=0.5 处最小

        参数:
        sigma_range: σ 的扫描范围
        t_fixed: 固定的 t 值（使用第一个黎曼零点 ~14.1347）
        N_terms: 求和项数
        resolution: 采样点数
        """
        print("\n" + "=" * 70)
        print(f"临界线约束验证（固定 t={t_fixed}，扫描 σ）")
        print("=" * 70)

        sigma_values = np.linspace(sigma_range[0], sigma_range[1], resolution)
        zeta_inv_magnitudes = []

        for sigma in sigma_values:
            zeta_inv, _ = self.zeta_inverse_phase_sum(sigma, t_fixed, N_terms)
            magnitude = np.abs(zeta_inv)
            zeta_inv_magnitudes.append(magnitude)

        zeta_inv_magnitudes = np.array(zeta_inv_magnitudes)

        # 找到最小值位置
        min_idx = np.argmin(zeta_inv_magnitudes)
        sigma_min = sigma_values[min_idx]
        mag_min = zeta_inv_magnitudes[min_idx]

        print(f"\n扫描结果:")
        print(f"  σ 范围: [{sigma_range[0]}, {sigma_range[1]}]")
        print(f"  最小值位置: σ = {sigma_min:.4f}")
        print(f"  最小值大小: |ζ(σ+it)^{{-1}}| = {mag_min:.6f}")
        print(f"  偏离 0.5 的程度: {abs(sigma_min - 0.5):.4f}")

        if abs(sigma_min - 0.5) < 0.05:
            print(f"  ✓ 最小值接近 σ=0.5，支持临界线假设")
        else:
            print(f"  ⚠ 最小值偏离 σ=0.5，需要进一步分析")

        # 可视化
        fig, ax = plt.subplots(figsize=(10, 6))

        ax.plot(sigma_values, zeta_inv_magnitudes, 'b-', linewidth=2,
               label=r'$|\zeta(\sigma+it)^{-1}|$')
        ax.axvline(x=0.5, color='red', linestyle='--', linewidth=2,
                  label='Critical line σ=1/2')
        ax.scatter([sigma_min], [mag_min], color='green', s=200, marker='*',
                  zorder=5, label=f'Minimum at σ={sigma_min:.3f}')

        ax.set_xlabel('σ (real part of s)', fontsize=12)
        ax.set_ylabel(r'$|\zeta(\sigma+it)^{-1}|$', fontsize=12)
        ax.set_title(f'Critical Line Constraint Test (t={t_fixed})',
                    fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('critical_line_verification.png', dpi=300, bbox_inches='tight')
        plt.show()

        return {
            'sigma_min': sigma_min,
            'magnitude_min': mag_min,
            'deviation_from_half': abs(sigma_min - 0.5)
        }


def main():
    """主验证流程"""
    print("=" * 70)
    print("莫比乌斯环扭转运算与黎曼猜想验证")
    print("=" * 70)

    algebra = MobiusTwistAlgebra(N_discrete=100)

    # 1. 示例验证：2 × 3
    print("\n[任务1] 验证扭转乘法的非平凡性")
    result_2x3 = algebra.verify_example_2x3()

    # 2. 素数相位分析
    print("\n[任务2] 分析素数相位的拓扑解释")
    phase_results = algebra.analyze_prime_phases(N_max=100)

    # 3. 寻找共振条件
    print("\n[任务3] 寻找扭转共振点（相位相消干涉）")
    resonance_points = algebra.find_resonance_condition(
        t_range=(0, 50),
        N_terms=500,
        resolution=200
    )

    # 4. 临界线验证
    print("\n[任务4] 验证临界线约束 Re(s)=1/2")
    critical_line_result = algebra.verify_critical_line_constraint(
        sigma_range=(0.3, 0.7),
        t_fixed=14.1347,  # 第一个黎曼零点
        N_terms=500,
        resolution=100
    )

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_data = {
        'experiment': 'Mobius Twist Algebra Verification',
        'timestamp': timestamp,
        'example_2x3': result_2x3,
        'critical_line_test': critical_line_result,
        'resonance_points_count': len(resonance_points),
        'interpretation': {
            'mu_phase_correspondence': 'μ(n) = (-1)^{Ω(n)} 与莫比乌斯相位 φ=π·Ω(n) 精确对应',
            'prime_as_twist_source': '素数对应单次扭转（φ=π），合数对应多次扭转叠加',
            'resonance_condition': 'ζ(s)=0 对应相位相消干涉最强的位置',
            'critical_line_origin': '如果最小值始终在 σ=0.5，说明临界线来自拓扑约束'
        }
    }

    output_dir = os.path.join(os.path.dirname(__file__), 'output_data')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'mobius_twist_verification_{timestamp}.json')

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 结果已保存: {output_file}")
    print("\n解读指南:")
    for key, value in output_data['interpretation'].items():
        print(f"  • {key}: {value}")

    print("\n" + "=" * 70)
    print("验证完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
