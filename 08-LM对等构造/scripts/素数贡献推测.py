"""
素数贡献分析与预测系统
=====================

第一步：分析10万以内素数的贡献模式
- 提取所有素数
- 计算每个合数的相位构成
- 量化前驱素数的贡献比例
- 寻找统计规律

第二步：基于规律预测下一个素数
- 建立相位累积模型
- 预测素数间隙
- 验证预测精度
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
import json
from datetime import datetime
import os


class PrimeContributionAnalyzer:
    """
    素数贡献分析器
    """

    def __init__(self):
        self.primes = None
        self.prime_set = None
        self.contribution_data = None

    def generate_primes_up_to(self, N_max=100000):
        """
        生成 N_max 以内的所有素数（埃拉托斯特尼筛法）

        参数:
        N_max: 上限

        返回:
        primes: 素数数组
        """
        print(f"正在生成 {N_max} 以内的素数...")

        sieve = np.ones(N_max + 1, dtype=bool)
        sieve[0] = sieve[1] = False

        for i in range(2, int(np.sqrt(N_max)) + 1):
            if sieve[i]:
                sieve[i * i::i] = False

        self.primes = np.where(sieve)[0]
        self.prime_set = set(self.primes)

        print(f"✓ 找到 {len(self.primes)} 个素数")
        print(f"  范围: [{self.primes[0]}, {self.primes[-1]}]")
        print(f"  第1000个素数: {self.primes[999]}")

        # 安全地显示第10000个素数（如果存在）
        if len(self.primes) >= 10000:
            print(f"  第10000个素数: {self.primes[9999]}")
        else:
            print(f"  最后一个素数 (第{len(self.primes)}个): {self.primes[-1]}")

        return self.primes

    def mobius_phase(self, n):
        """
        计算整数 n 的莫比乌斯相位

        φ(n) = π · Ω(n)
        Ω(n) = n 的素因子个数（计重数）
        """
        if n <= 1:
            return 0.0, 0

        omega = 0
        temp = n
        factors = []

        for p in range(2, int(np.sqrt(n)) + 2):
            while temp % p == 0:
                omega += 1
                factors.append(p)
                temp //= p
        if temp > 1:
            omega += 1
            factors.append(temp)

        phi = (np.pi * omega) % (2 * np.pi)
        return phi, omega, factors

    def analyze_composite_contributions(self, N_max=100000):
        """
        第一步：分析合数的素数贡献模式

        对于每个合数 n，分析：
        - 它的素因子分解
        - 每个素因子的相位贡献
        - 贡献比例的分布
        """
        print("\n" + "=" * 70)
        print("第一步：分析10万以内素数的贡献模式")
        print("=" * 70)

        if self.primes is None:
            self.generate_primes_up_to(N_max)

        contribution_records = []

        # 只分析合数
        composites = [n for n in range(4, N_max + 1) if n not in self.prime_set]

        print(f"正在分析 {len(composites)} 个合数的贡献模式...")

        for n in composites:
            phi_n, omega_n, factors = self.mobius_phase(n)

            if phi_n == 0 or omega_n == 0:
                continue  # 跳过相位塌缩或单位元

            # 计算每个素因子的贡献
            factor_contributions = []
            for p in set(factors):  # 去重
                count = factors.count(p)
                phi_p, _, _ = self.mobius_phase(p)

                # 单个素因子的总贡献 = φ(p) × 出现次数
                total_contribution = phi_p * count
                contribution_ratio = total_contribution / (np.pi * omega_n)

                factor_contributions.append({
                    'prime': p,
                    'count': count,
                    'phi_p': phi_p,
                    'total_contribution': total_contribution,
                    'contribution_ratio': contribution_ratio
                })

            record = {
                'n': n,
                'phi_n': phi_n,
                'omega_n': omega_n,
                'factors': factors,
                'unique_factors': list(set(factors)),
                'factor_contributions': factor_contributions,
                'is_prime_power': len(set(factors)) == 1,  # 是否是素数幂
                'num_unique_factors': len(set(factors))
            }

            contribution_records.append(record)

        self.contribution_data = contribution_records

        print(f"✓ 分析了 {len(contribution_records)} 个有效合数")

        return contribution_records

    def find_contribution_patterns(self):
        """
        寻找贡献模式的统计规律
        """
        print("\n" + "=" * 70)
        print("寻找贡献模式的统计规律")
        print("=" * 70)

        if not self.contribution_data:
            print("⚠ 请先运行 analyze_composite_contributions()")
            return

        data = self.contribution_data

        # 1. 素因子个数分布
        omega_values = [r['omega_n'] for r in data]
        unique_factor_counts = [r['num_unique_factors'] for r in data]

        print(f"\n1. 素因子个数 Ω(n) 分布:")
        for omega in range(1, 8):
            count = omega_values.count(omega)
            percentage = count / len(omega_values) * 100
            print(f"   Ω={omega}: {count:6d} 个 ({percentage:5.2f}%)")

        # 2. 不同素因子个数分布
        print(f"\n2. 不同素因子个数分布:")
        for k in range(1, 6):
            count = unique_factor_counts.count(k)
            percentage = count / len(unique_factor_counts) * 100
            print(f"   {k} 个不同素因子: {count:6d} 个 ({percentage:5.2f}%)")

        # 3. 贡献比例分析
        all_ratios = []
        for r in data:
            for fc in r['factor_contributions']:
                all_ratios.append(fc['contribution_ratio'])

        print(f"\n3. 单个素因子贡献比例统计:")
        print(f"   平均值: {np.mean(all_ratios):.4f}")
        print(f"   中位数: {np.median(all_ratios):.4f}")
        print(f"   标准差: {np.std(all_ratios):.4f}")
        print(f"   最小值: {np.min(all_ratios):.4f}")
        print(f"   最大值: {np.max(all_ratios):.4f}")

        # 4. 典型案例分析
        print(f"\n4. 典型案例:")

        # 两个素数之积
        examples_2primes = [r for r in data if r['omega_n'] == 2 and r['num_unique_factors'] == 2][:5]
        print(f"   两素数之积 (pq):")
        for ex in examples_2primes:
            print(f"     n={ex['n']:4d}: {ex['factors'][0]}×{ex['factors'][1]}, "
                  f"φ={ex['phi_n']:.2f}, 各贡献50%")

        # 三个素数之积
        examples_3primes = [r for r in data if r['omega_n'] == 3 and r['num_unique_factors'] == 3][:5]
        print(f"   三素数之积 (pqr):")
        for ex in examples_3primes:
            print(f"     n={ex['n']:4d}: {'×'.join(map(str, ex['factors']))}, "
                  f"φ={ex['phi_n']:.2f}, 各贡献33.3%")

        # 素数幂
        examples_prime_power = [r for r in data if r['is_prime_power']][:5]
        print(f"   素数幂 (p^k):")
        for ex in examples_prime_power:
            p = ex['factors'][0]
            k = len(ex['factors'])
            print(f"     n={ex['n']:4d}: {p}^{k}, φ={ex['phi_n']:.2f}, "
                  f"单一素数贡献100%")

        # 5. 可视化
        self._plot_contribution_patterns(omega_values, all_ratios)

        return {
            'omega_distribution': omega_values,
            'contribution_ratios': all_ratios
        }

    def _plot_contribution_patterns(self, omega_values, all_ratios):
        """绘制贡献模式图"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))

        # 图1: Ω(n) 分布
        omega_counts = [omega_values.count(k) for k in range(1, 8)]
        ax1.bar(range(1, 8), omega_counts, color='steelblue', edgecolor='black')
        ax1.set_xlabel('Ω(n) - Number of prime factors', fontsize=11)
        ax1.set_ylabel('Count', fontsize=11)
        ax1.set_title('Distribution of Prime Factor Count', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='y')

        # 图2: 贡献比例分布
        ax2.hist(all_ratios, bins=50, density=True, color='coral',
                edgecolor='black', alpha=0.7)
        ax2.axvline(x=np.mean(all_ratios), color='red', linestyle='--',
                   linewidth=2, label=f'Mean={np.mean(all_ratios):.3f}')
        ax2.set_xlabel('Contribution Ratio', fontsize=11)
        ax2.set_ylabel('Density', fontsize=11)
        ax2.set_title('Distribution of Prime Contribution Ratios',
                     fontsize=12, fontweight='bold')
        ax2.legend(fontsize=10)
        ax2.grid(True, alpha=0.3, axis='y')

        # 图3: 累积相位 vs n
        sample_n = list(range(100, 10000, 100))
        sample_phi = []
        for n in sample_n:
            phi, _, _ = self.mobius_phase(n)
            sample_phi.append(phi)

        ax3.plot(sample_n, sample_phi, 'b-', linewidth=1.5, alpha=0.7)
        ax3.axhline(y=np.pi, color='red', linestyle='--', linewidth=2,
                   label='φ=π (prime)')
        ax3.axhline(y=2*np.pi, color='green', linestyle='--', linewidth=2,
                   label='φ=2π (product of 2 primes)')
        ax3.set_xlabel('n', fontsize=11)
        ax3.set_ylabel('φ(n)', fontsize=11)
        ax3.set_title('Phase Accumulation Pattern', fontsize=12, fontweight='bold')
        ax3.legend(fontsize=10)
        ax3.grid(True, alpha=0.3)

        # 图4: 相邻素数间隙
        gaps = np.diff(self.primes[:10000])  # 前10000个素数的间隙
        ax4.hist(gaps, bins=50, density=True, color='purple',
                edgecolor='black', alpha=0.7)
        ax4.set_xlabel('Prime Gap', fontsize=11)
        ax4.set_ylabel('Density', fontsize=11)
        ax4.set_title('Distribution of Prime Gaps (first 10000 primes)',
                     fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        plt.savefig('prime_contribution_patterns.png', dpi=300, bbox_inches='tight')
        plt.show()

    def predict_next_prime_from_pattern(self, current_prime_idx, method='phase_accumulation'):
        """
        第二步：基于贡献模式预测下一个素数

        参数:
        current_prime_idx: 当前素数的索引（从0开始）
        method: 预测方法
            - 'phase_accumulation': 相位累积模型
            - 'gap_statistics': 间隙统计模型

        返回:
        prediction: 预测结果字典
        """
        print("\n" + "=" * 70)
        print("第二步：基于贡献模式预测下一个素数")
        print("=" * 70)

        if self.primes is None:
            print("⚠ 请先生成素数表")
            return None

        if current_prime_idx >= len(self.primes) - 1:
            print(f"⚠ 索引 {current_prime_idx} 超出范围")
            return None

        current_p = self.primes[current_prime_idx]
        actual_next = self.primes[current_prime_idx + 1]
        actual_gap = actual_next - current_p

        print(f"\n当前素数: p_{current_prime_idx + 1} = {current_p}")
        print(f"实际下一个: p_{current_prime_idx + 2} = {actual_next}")
        print(f"实际间隙: {actual_gap}")

        if method == 'phase_accumulation':
            prediction = self._predict_by_phase(current_prime_idx)
        elif method == 'gap_statistics':
            prediction = self._predict_by_gap_statistics(current_prime_idx)
        else:
            print(f"⚠ 未知方法: {method}")
            return None

        # 计算预测误差
        predicted_next = prediction['predicted_next']
        error = abs(predicted_next - actual_next)
        relative_error = error / actual_next * 100

        prediction['actual_next'] = actual_next
        prediction['error'] = error
        prediction['relative_error_%'] = relative_error

        print(f"\n预测结果:")
        print(f"  预测值: {predicted_next:.2f}")
        print(f"  实际值: {actual_next}")
        print(f"  绝对误差: {error:.2f}")
        print(f"  相对误差: {relative_error:.2f}%")

        if error <= 1:
            print(f"  ✓ 精确匹配！")
        elif error <= 5:
            print(f"  ✓ 误差很小，在搜索范围内")
        else:
            print(f"  ⚠ 误差较大")

        return prediction

    def _predict_by_phase(self, current_prime_idx):
        """
        基于相位累积模型的预测（使用新定义的扭转运算）

        核心思想：
        - 当前素数 p_k 的相位是 π（一次扭转）
        - 下一个素数 p_{k+1} 应该是最小的 n > p_k，使得：
          * n 的相位也是 π（奇数次扭转）
          * n 没有平方因子（μ(n) ≠ 0）
          * n 是素数（Ω(n) = 1）

        预测策略：
        1. 从 p_k + 2 开始搜索（跳过偶数）
        2. 对每个候选 n，计算其相位 φ(n)
        3. 如果 φ(n) = π 且 μ(n) = -1，则 n 可能是素数
        4. 结合局部间隙统计缩小搜索范围
        """
        current_p = self.primes[current_prime_idx]

        # 步骤1：计算当前素数的相位状态
        phi_current, omega_current, factors_current = self.mobius_phase(current_p)
        # 对于素数，应该有 phi=π, omega=1

        # 步骤2：预测下一个素数的相位应该是 π（回到单次扭转状态）
        target_phi = np.pi

        # 步骤3：估计搜索范围（基于素数定理）
        log_p = np.log(current_p)
        expected_gap = log_p

        # 考虑前几个间隙的趋势（相位记忆效应）
        if current_prime_idx >= 5:
            prev_gaps = []
            for i in range(1, 6):
                gap = self.primes[current_prime_idx - i + 1] - self.primes[current_prime_idx - i]
                prev_gaps.append(gap)

            # 计算间隙变化的"相位导数"
            gap_changes = np.diff(prev_gaps)
            trend = np.mean(gap_changes)

            # 修正预期间隙（考虑趋势）
            expected_gap += 0.2 * trend

        # 步骤4：在搜索范围内寻找相位匹配的候选
        search_start = int(current_p + 2)
        search_end = int(current_p + expected_gap * 3)  # 搜索3倍预期间隙

        candidates = []
        for n in range(search_start, search_end, 2):  # 只检查奇数
            phi_n, omega_n, factors_n = self.mobius_phase(n)
            mu_n = self.mobius_function_from_phase(n)

            # 筛选条件：
            # 1. 相位接近 π（允许小误差，因为可能有数值波动）
            # 2. μ(n) = -1（奇数个不同素因子，无平方因子）
            # 3. omega_n 较小（倾向于素数或少数素因子之积）

            if mu_n == -1 and omega_n <= 3:
                # 计算与目标相位的距离
                phase_distance = abs(phi_n - target_phi)
                if phase_distance < 0.1:  # 相位非常接近 π
                    candidates.append({
                        'n': n,
                        'phi': phi_n,
                        'omega': omega_n,
                        'factors': factors_n,
                        'phase_distance': phase_distance,
                        'gap_from_current': n - current_p
                    })

        # 步骤5：从候选中选择最可能的下一个素数
        if candidates:
            # 排序标准：
            # 1. 相位距离最小（优先）
            # 2. omega 最小（素数 omega=1，半素数 omega=2）
            # 3. 间隙接近预期间隙

            candidates.sort(key=lambda c: (
                c['omega'],  # 优先 omega 小的
                c['phase_distance'],  # 其次相位接近的
                abs(c['gap_from_current'] - expected_gap)  # 最后间隙合理的
            ))

            # 取最佳候选
            best_candidate = candidates[0]
            predicted_next = best_candidate['n']

            return {
                'method': 'phase_twist_algebra',
                'predicted_next': float(predicted_next),
                'expected_gap': expected_gap,
                'log_p': log_p,
                'current_phi': phi_current,
                'target_phi': target_phi,
                'num_candidates': len(candidates),
                'best_candidate_info': {
                    'n': best_candidate['n'],
                    'omega': best_candidate['omega'],
                    'phase_distance': best_candidate['phase_distance'],
                    'factors': best_candidate['factors'][:5]  # 只显示前5个因子
                }
            }
        else:
            # 如果没有找到相位匹配的候选，回退到统计方法
            print(f"  ⚠ 未找到相位匹配候选，回退到统计方法")
            return self._predict_by_gap_statistics(current_prime_idx)

    def mobius_function_from_phase(self, n):
        """
        从相位推导 Möbius 函数（辅助方法）

        μ(n) = (-1)^{Ω(n)}，如果有平方因子则为 0
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
        if temp > 1:
            # 检查剩余部分是否有平方因子
            for p in range(2, int(np.sqrt(temp)) + 2):
                if temp % (p * p) == 0:
                    has_square_factor = True
                    break

        if has_square_factor:
            return 0  # 相位塌缩

        # 计算相位
        phi, omega, _ = self.mobius_phase(n)

        # μ(n) = (-1)^{Ω(n)}
        return (-1) ** omega

    def _predict_by_gap_statistics(self, current_prime_idx):
        """
        基于间隙统计模型的预测

        使用局部窗口内的间隙分布
        """
        current_p = self.primes[current_prime_idx]

        # 使用局部窗口（前100个素数的间隙）
        window_size = min(100, current_prime_idx)
        if window_size < 10:
            window_size = current_prime_idx

        start_idx = max(0, current_prime_idx - window_size)
        local_primes = self.primes[start_idx:current_prime_idx + 1]
        local_gaps = np.diff(local_primes)

        # 多种统计量
        mean_gap = np.mean(local_gaps)
        median_gap = np.median(local_gaps)

        # 加权平均（最近的间隙权重更大）
        weights = np.exp(np.linspace(-1, 0, len(local_gaps)))
        weighted_mean_gap = np.average(local_gaps, weights=weights)

        # 综合预测
        predicted_gap = 0.4 * mean_gap + 0.3 * median_gap + 0.3 * weighted_mean_gap
        predicted_next = current_p + predicted_gap

        return {
            'method': 'gap_statistics',
            'predicted_next': predicted_next,
            'mean_gap': mean_gap,
            'median_gap': median_gap,
            'weighted_mean_gap': weighted_mean_gap,
            'window_size': window_size
        }

    def batch_prediction_test(self, start_idx=1000, end_idx=2000, method='gap_statistics'):
        """
        批量预测测试

        参数:
        start_idx: 起始索引
        end_idx: 结束索引
        method: 预测方法

        返回:
        results: 预测结果列表
        """
        print(f"\n批量预测测试: p_{start_idx+1} ~ p_{end_idx}")
        print("=" * 70)

        results = []
        errors = []

        for idx in range(start_idx, end_idx):
            prediction = self.predict_next_prime_from_pattern(idx, method)
            if prediction:
                results.append(prediction)
                errors.append(prediction['error'])

        errors = np.array(errors)

        print(f"\n{'='*70}")
        print(f"批量测试结果 ({len(results)} 个预测):")
        print(f"  平均绝对误差: {np.mean(errors):.2f}")
        print(f"  中位数误差: {np.median(errors):.2f}")
        print(f"  标准差: {np.std(errors):.2f}")
        print(f"  最大误差: {np.max(errors):.2f}")
        print(f"  最小误差: {np.min(errors):.2f}")

        # 精度分布
        exact_match = np.sum(errors == 0)
        within_1 = np.sum(errors <= 1)
        within_5 = np.sum(errors <= 5)
        within_10 = np.sum(errors <= 10)

        print(f"\n精度分布:")
        print(f"  精确匹配: {exact_match} ({exact_match/len(results)*100:.1f}%)")
        print(f"  误差≤1: {within_1} ({within_1/len(results)*100:.1f}%)")
        print(f"  误差≤5: {within_5} ({within_5/len(results)*100:.1f}%)")
        print(f"  误差≤10: {within_10} ({within_10/len(results)*100:.1f}%)")

        # 可视化误差分布
        self._plot_prediction_errors(errors)

        return results

    def _plot_prediction_errors(self, errors):
        """绘制预测误差分布"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # 图1: 误差直方图
        ax1.hist(errors, bins=50, color='steelblue', edgecolor='black', alpha=0.7)
        ax1.axvline(x=np.mean(errors), color='red', linestyle='--', linewidth=2,
                   label=f'Mean={np.mean(errors):.2f}')
        ax1.set_xlabel('Absolute Error', fontsize=12)
        ax1.set_ylabel('Count', fontsize=12)
        ax1.set_title('Distribution of Prediction Errors', fontsize=13, fontweight='bold')
        ax1.legend(fontsize=11)
        ax1.grid(True, alpha=0.3, axis='y')

        # 图2: 累积分布
        sorted_errors = np.sort(errors)
        cumulative = np.arange(1, len(sorted_errors) + 1) / len(sorted_errors)

        ax2.plot(sorted_errors, cumulative, 'b-', linewidth=2)
        ax2.axvline(x=1, color='green', linestyle='--', linewidth=2, label='Error ≤ 1')
        ax2.axvline(x=5, color='orange', linestyle='--', linewidth=2, label='Error ≤ 5')
        ax2.set_xlabel('Absolute Error', fontsize=12)
        ax2.set_ylabel('Cumulative Probability', fontsize=12)
        ax2.set_title('Cumulative Distribution of Errors', fontsize=13, fontweight='bold')
        ax2.legend(fontsize=11)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('prediction_error_analysis.png', dpi=300, bbox_inches='tight')
        plt.show()


def main():
    """主流程"""
    print("=" * 70)
    print("素数贡献分析与预测系统")
    print("=" * 70)

    analyzer = PrimeContributionAnalyzer()

    # 第一步：生成素数并分析贡献模式
    analyzer.generate_primes_up_to(100000)
    analyzer.analyze_composite_contributions(100000)
    patterns = analyzer.find_contribution_patterns()

    # 第二步：单个预测示例
    print("\n" + "=" * 70)
    print("单个预测示例")
    print("=" * 70)

    # 测试几个不同的位置
    test_indices = [100, 500, 1000, 5000]

    for idx in test_indices:
        print(f"\n--- 测试 p_{idx+1} ---")
        pred = analyzer.predict_next_prime_from_pattern(idx, method='gap_statistics')

    # 第三步：批量预测测试
    print("\n" + "=" * 70)
    print("批量预测测试")
    print("=" * 70)

    # print("\n=== 测试 gap_statistics 方法 ===")
    # results1 = analyzer.batch_prediction_test(1000, 1100, 'gap_statistics')

    print("\n=== 测试 phase_accumulation 方法 ===")
    results = analyzer.batch_prediction_test(1000, 1100, 'phase_accumulation')

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_data = {
        'experiment': 'Prime Contribution Analysis and Prediction',
        'timestamp': timestamp,
        'num_primes_analyzed': len(analyzer.primes),
        'pattern_summary': {
            'mean_contribution_ratio': float(np.mean(patterns['contribution_ratios'])),
            'median_omega': float(np.median(patterns['omega_distribution']))
        },
        'batch_test_results': {
            'num_predictions': len(results),
            'mean_error': float(np.mean([r['error'] for r in results])),
            'median_error': float(np.median([r['error'] for r in results]))
        }
    }

    output_dir = os.path.join(os.path.dirname(__file__), 'output_data')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'prime_contribution_analysis_{timestamp}.json')

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 结果已保存: {output_file}")
    print("\n" + "=" * 70)
    print("分析完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
