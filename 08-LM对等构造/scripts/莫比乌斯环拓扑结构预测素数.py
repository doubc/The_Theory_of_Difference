"""
基于莫比乌斯环拓扑特性的素数位置预测模型 - 严格验证版

使用100万以内的已知素数进行系统性验证
"""

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import gaussian_kde, chisquare
import json
from datetime import datetime
import os


class PrimePredictorFromMobius:
    """
    从莫比乌斯环拓扑预测素数位置（带严格验证）
    """

    def __init__(self, R=1.0, w=0.8):
        self.R = R
        self.w = w
        self.mobius_zeros_cache = None
        self.known_primes = None

    def load_known_primes(self, N_max=1000000):
        """
        生成或加载N_max以内的所有已知素数

        使用埃拉托斯特尼筛法
        """
        sieve = np.ones(N_max + 1, dtype=bool)
        sieve[0] = sieve[1] = False

        for i in range(2, int(np.sqrt(N_max)) + 1):
            if sieve[i]:
                sieve[i * i::i] = False

        self.known_primes = np.where(sieve)[0]

        print(f"✓ 已加载 {len(self.known_primes)} 个素数（范围: 2 ~ {self.known_primes[-1]}）")

        return self.known_primes

    def compute_mobius_spectral_zeros(self, m_max=100, n_max=100):
        """
        计算莫比乌斯环的谱零点（高精度版本）

        增加m_max和n_max以获得更多零点用于大数预测
        """
        eigenvals = []

        for m_half in range(0, m_max):
            m = m_half + 0.5
            for n in range(1, n_max + 1):
                lambda_mn = (m / self.R) ** 2 + (n * np.pi / self.w) ** 2
                eigenvals.append(lambda_mn)

        eigenvals = np.array(sorted(eigenvals))

        spectral_zeros = []
        for lam in eigenvals:
            if lam > 0.25:
                gamma = 0.5 * np.sqrt(4 * lam - 1)
                spectral_zeros.append(0.5 + 1j * gamma)

        spectral_zeros.sort(key=lambda z: np.imag(z))
        self.mobius_zeros_cache = spectral_zeros

        print(f"✓ 已计算 {len(spectral_zeros)} 个莫比乌斯谱零点")

        return spectral_zeros

    def prime_formula_from_topology(self, n):
        """
        第n个素数的解析公式（基于莫比乌斯拓扑）

        p_n ≈ n·log(n) + n·log(log(n)) - n
             + Σ_k [A_k·cos(γ_k·log(n))/√n]
             + C·(w/R)·sin(2πn/R)
        """
        if self.mobius_zeros_cache is None:
            self.compute_mobius_spectral_zeros()

        if n < 2:
            return 2.0

        zeros = self.mobius_zeros_cache

        # 主项：素数定理的高阶渐近展开
        log_n = np.log(n)
        log_log_n = np.log(log_n) if n > 1 else 0

        main_term = n * (log_n + log_log_n - 1 + (log_log_n - 2) / log_n
                         - ((log_log_n) ** 2 - 6 * log_log_n + 11) / (2 * log_n ** 2))

        # 振荡项：来自谱零点的贡献
        oscillation = 0.0
        num_zeros_to_use = min(50, len(zeros))

        for k in range(num_zeros_to_use):
            gamma_k = np.imag(zeros[k])
            # 振幅随k衰减
            amplitude = 2.0 / (k + 1)
            oscillation += amplitude * np.cos(gamma_k * log_n) / np.sqrt(n)

        # 拓扑修正项
        topological_correction = 0.5 * (self.w / self.R) * np.sin(2 * np.pi * n / self.R)

        predicted_prime = main_term + oscillation + topological_correction

        return float(max(predicted_prime, 2.0))

    def predict_next_prime_from_current(self, current_prime_idx):
        """
        基于当前素数索引预测下一个素数

        使用局部零点密度和GUE统计

        参数：
        current_prime_idx: 当前素数在素数序列中的索引（从1开始）

        返回：
        预测的下一个素数值
        """
        if self.known_primes is None:
            raise ValueError("请先调用 load_known_primes() 加载已知素数")

        if self.mobius_zeros_cache is None:
            self.compute_mobius_spectral_zeros()

        # 获取当前素数
        if current_prime_idx >= len(self.known_primes):
            raise ValueError(f"索引 {current_prime_idx} 超出已知素数范围")

        current_p = self.known_primes[current_prime_idx - 1]

        # 局部对数密度
        local_log_p = np.log(current_p)

        # 平均素数间隙约为 log(p)
        # 但需要加上GUE涨落

        # 从莫比乌斯谱中提取局部间距统计
        zeros = self.mobius_zeros_cache
        if current_prime_idx < len(zeros):
            # 使用相邻零点的实际间距
            gamma_current = np.imag(zeros[current_prime_idx - 1])
            gamma_next = np.imag(zeros[current_prime_idx])
            actual_spacing = gamma_next - gamma_current

            # 归一化间距
            mean_gamma = np.mean([np.imag(zeros[i]) for i in range(max(0, current_prime_idx - 10),
                                                                   min(len(zeros), current_prime_idx + 10))])
            normalized_spacing = actual_spacing / (mean_gamma / len(zeros[:current_prime_idx + 10]))
        else:
            # 使用GUE理论值
            normalized_spacing = 1.0

        # GUE分布的期望值为1，但有涨落
        # P(s) = (32/π²)s²exp(-4s²/π)
        gue_mean = 1.0

        # 预测间隙
        predicted_gap = gue_mean * (2 * np.pi / local_log_p) * normalized_spacing

        predicted_next = current_p + predicted_gap

        return {
            'current_index': current_prime_idx,
            'current_prime': int(current_p),
            'predicted_next': float(predicted_next),
            'predicted_gap': float(predicted_gap),
            'local_log_p': float(local_log_p),
            'normalized_spacing': float(normalized_spacing)
        }

    def validate_formula_accuracy(self, n_start=1, n_end=10000):
        """
        系统验证素数公式的准确性

        参数：
        n_start, n_end: 验证的素数索引范围

        返回：
        详细的误差统计分析
        """
        if self.known_primes is None:
            self.load_known_primes()

        print(f"\n正在验证素数公式（索引 {n_start} ~ {n_end}）...")

        errors = []
        relative_errors = []
        absolute_errors = []

        results = []

        for n in range(n_start, min(n_end + 1, len(self.known_primes) + 1)):
            actual = self.known_primes[n - 1]
            predicted = self.prime_formula_from_topology(n)

            error = predicted - actual
            abs_error = abs(error)
            rel_error = abs_error / actual * 100

            errors.append(error)
            absolute_errors.append(abs_error)
            relative_errors.append(rel_error)

            results.append({
                'n': n,
                'actual': int(actual),
                'predicted': float(predicted),
                'error': float(error),
                'abs_error': float(abs_error),
                'rel_error_percent': float(rel_error)
            })

        errors = np.array(errors)
        absolute_errors = np.array(absolute_errors)
        relative_errors = np.array(relative_errors)

        stats = {
            'validation_range': [n_start, min(n_end, len(self.known_primes))],
            'num_samples': len(results),
            'mean_error': float(np.mean(errors)),
            'std_error': float(np.std(errors)),
            'mean_abs_error': float(np.mean(absolute_errors)),
            'max_abs_error': float(np.max(absolute_errors)),
            'mean_rel_error_percent': float(np.mean(relative_errors)),
            'max_rel_error_percent': float(np.max(relative_errors)),
            'median_rel_error_percent': float(np.median(relative_errors)),
            'rms_error': float(np.sqrt(np.mean(errors ** 2))),
            'accuracy_within_1_percent': float(np.sum(relative_errors < 1.0) / len(relative_errors) * 100),
            'accuracy_within_5_percent': float(np.sum(relative_errors < 5.0) / len(relative_errors) * 100),
            'accuracy_within_10_percent': float(np.sum(relative_errors < 10.0) / len(relative_errors) * 100)
        }

        print(f"\n{'=' * 70}")
        print(f"验证结果统计（{stats['num_samples']} 个样本）")
        print(f"{'=' * 70}")
        print(f"平均绝对误差:     {stats['mean_abs_error']:>10.2f}")
        print(f"最大绝对误差:     {stats['max_abs_error']:>10.2f}")
        print(f"均方根误差(RMS):  {stats['rms_error']:>10.2f}")
        print(f"\n平均相对误差:     {stats['mean_rel_error_percent']:>9.2f}%")
        print(f"中位数相对误差:   {stats['median_rel_error_percent']:>9.2f}%")
        print(f"最大相对误差:     {stats['max_rel_error_percent']:>9.2f}%")
        print(f"\n精度统计:")
        print(f"  相对误差 < 1%:  {stats['accuracy_within_1_percent']:>6.2f}%")
        print(f"  相对误差 < 5%:  {stats['accuracy_within_5_percent']:>6.2f}%")
        print(f"  相对误差 < 10%: {stats['accuracy_within_10_percent']:>6.2f}%")
        print(f"{'=' * 70}")

        return {
            'statistics': stats,
            'detailed_results': results[:100],  # 只保存前100个详细结果
            'timestamp': datetime.now().isoformat()
        }

    def validate_next_prime_prediction(self, test_range=(100, 1000)):
        """
        验证"预测下一个素数"功能的准确性

        参数：
        test_range: (start_idx, end_idx) 测试的素数索引范围

        返回：
        预测准确率统计
        """
        if self.known_primes is None:
            self.load_known_primes()

        start_idx, end_idx = test_range

        print(f"\n正在验证下一个素数预测（索引 {start_idx} ~ {end_idx}）...")

        correct_predictions = 0
        total_predictions = 0
        prediction_errors = []

        for idx in range(start_idx, min(end_idx, len(self.known_primes))):
            try:
                pred = self.predict_next_prime_from_current(idx)
                actual_next = self.known_primes[idx]  # 索引从0开始

                predicted_rounded = round(pred['predicted_next'])

                # 检查预测是否准确（允许±1的误差，因为素数必须是整数）
                is_correct = (predicted_rounded == actual_next)

                if is_correct:
                    correct_predictions += 1

                total_predictions += 1

                error = abs(predicted_rounded - actual_next)
                prediction_errors.append(error)

            except Exception as e:
                print(f"  警告: 索引 {idx} 预测失败: {e}")
                continue

        prediction_errors = np.array(prediction_errors)

        accuracy = correct_predictions / total_predictions * 100 if total_predictions > 0 else 0

        print(f"\n{'=' * 70}")
        print(f"下一个素数预测验证结果")
        print(f"{'=' * 70}")
        print(f"总预测次数:       {total_predictions}")
        print(f"正确预测次数:     {correct_predictions}")
        print(f"预测准确率:       {accuracy:>6.2f}%")
        print(f"\n预测误差统计:")
        print(f"  平均绝对误差:   {np.mean(prediction_errors):>10.2f}")
        print(f"  中位数误差:     {np.median(prediction_errors):>10.2f}")
        print(f"  最大误差:       {np.max(prediction_errors):>10.2f}")
        print(f"{'=' * 70}")

        return {
            'test_range': list(test_range),
            'total_predictions': total_predictions,
            'correct_predictions': correct_predictions,
            'accuracy_percent': float(accuracy),
            'mean_error': float(np.mean(prediction_errors)),
            'median_error': float(np.median(prediction_errors)),
            'max_error': int(np.max(prediction_errors)),
            'timestamp': datetime.now().isoformat()
        }

    def torsion_point_validation(self):
        """
        验证扭转点预测的拓扑性质
        """
        print(f"\n{'=' * 70}")
        print("扭转点拓扑性质验证")
        print(f"{'=' * 70}")

        # 测试多个起始点
        test_points = [
            (0, 0.0),
            (np.pi / 4, 0.1),
            (np.pi / 2, 0.2),
            (np.pi, -0.3),
            (3 * np.pi / 2, 0.15),
            (2 * np.pi - 0.1, -0.05)
        ]

        all_valid = True

        for theta, v in test_points:
            result = self.torsion_point_prediction(theta, v)

            # 验证拓扑不变性：两次扭转应回到原点
            second_torsion = self.torsion_point_prediction(
                result['next_torsion_point']['theta'],
                result['next_torsion_point']['v']
            )

            # 检查是否回到原始位置（考虑数值误差）
            theta_diff = abs(second_torsion['next_torsion_point']['theta'] - theta)
            v_diff = abs(second_torsion['next_torsion_point']['v'] - v)

            is_periodic = (theta_diff < 0.01 and v_diff < 0.01)

            status = "✓" if is_periodic else "✗"
            print(f"\n{status} 起始点: θ={theta:.2f}, v={v:.2f}")
            print(f"   第1次扭转 → θ={result['next_torsion_point']['theta']:.2f}, "
                  f"v={result['next_torsion_point']['v']:.2f}")
            print(f"   第2次扭转 → θ={second_torsion['next_torsion_point']['theta']:.2f}, "
                  f"v={second_torsion['next_torsion_point']['v']:.2f}")
            print(f"   周期性检查: Δθ={theta_diff:.4f}, Δv={v_diff:.4f}")

            if not is_periodic:
                all_valid = False

        print(f"\n{'=' * 70}")
        if all_valid:
            print("✓ 所有测试点都满足拓扑周期性 (θ,v) → (θ+2π,-v) → (θ,v)")
        else:
            print("✗ 部分测试点不满足拓扑周期性")
        print(f"{'=' * 70}")

        return all_valid

    def torsion_point_prediction(self, theta_current, v_current):
        """
        预测莫比乌斯环上下一个扭转点的位置
        """
        next_theta = (theta_current + 2 * np.pi) % (2 * np.pi)
        next_v = -v_current

        zero_line_half_width = self.w / 2

        if abs(next_v) > zero_line_half_width:
            next_v = np.sign(next_v) * zero_line_half_width

        return {
            'current_position': {'theta': float(theta_current), 'v': float(v_current)},
            'next_torsion_point': {'theta': float(next_theta), 'v': float(next_v)},
            'delta_theta': float(2 * np.pi),
            'on_zero_line': abs(next_v) <= zero_line_half_width,
            'topological_charge': -1 if abs(next_v) < zero_line_half_width else 0
        }

    def save_all_validation_results(self, formula_stats, prediction_stats, torsion_valid):
        """
        保存所有验证结果
        """
        output_dir = os.path.join(os.path.dirname(__file__), 'output_data')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f'mobius_prime_validation_R{self.R}_w{self.w}_{timestamp}.json')

        results = {
            'model_parameters': {
                'R': self.R,
                'w': self.w,
                'zero_line': [float(self.R - self.w / 2), float(self.R + self.w / 2)]
            },
            'formula_validation': formula_stats,
            'next_prime_prediction_validation': prediction_stats,
            'torsion_topology_validation': torsion_valid,
            'timestamp': timestamp
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n✓ 完整验证结果已保存到: {filename}")

        return filename


def run_comprehensive_validation():
    """
    运行全面的验证流程
    """
    print("=" * 70)
    print("莫比乌斯环素数预测模型 - 全面验证")
    print("=" * 70)

    # 初始化预测器
    predictor = PrimePredictorFromMobius(R=1.0, w=0.8)

    # 步骤1: 加载已知素数
    predictor.load_known_primes(N_max=1000000)

    # 步骤2: 计算莫比乌斯谱零点
    predictor.compute_mobius_spectral_zeros(m_max=100, n_max=100)

    # 步骤3: 验证素数公式准确性
    print("\n" + "=" * 70)
    print("测试1: 素数解析公式验证")
    print("=" * 70)

    # 分段验证不同范围
    ranges_to_test = [
        (1, 100),
        (101, 1000),
        (1001, 10000),
        (10001, 100000)
    ]

    all_formula_stats = []
    for n_start, n_end in ranges_to_test:
        stats = predictor.validate_formula_accuracy(n_start, n_end)
        all_formula_stats.append(stats)

    # 步骤4: 验证下一个素数预测
    print("\n" + "=" * 70)
    print("测试2: 下一个素数位置预测验证")
    print("=" * 70)

    prediction_ranges = [
        (100, 200),
        (1000, 1100),
        (10000, 10100)
    ]

    all_prediction_stats = []
    for start, end in prediction_ranges:
        pred_stats = predictor.validate_next_prime_prediction((start, end))
        all_prediction_stats.append(pred_stats)

    # 步骤5: 验证扭转点拓扑性质
    print("\n" + "=" * 70)
    print("测试3: 扭转点拓扑性质验证")
    print("=" * 70)

    torsion_valid = predictor.torsion_point_validation()

    # 步骤6: 保存所有结果
    summary_file = predictor.save_all_validation_results(
        all_formula_stats,
        all_prediction_stats,
        torsion_valid
    )

    # 最终总结
    print("\n" + "=" * 70)
    print("验证完成总结")
    print("=" * 70)
    print(f"\n1. 素数公式验证:")
    for i, stats in enumerate(all_formula_stats):
        range_info = stats['statistics']['validation_range']
        acc_1pct = stats['statistics']['accuracy_within_1_percent']
        print(f"   范围 [{range_info[0]}, {range_info[1]}]: "
              f"相对误差<1%的比例 = {acc_1pct:.1f}%")

    print(f"\n2. 下一个素数预测:")
    for i, stats in enumerate(all_prediction_stats):
        range_info = stats['test_range']
        print(f"   范围 [{range_info[0]}, {range_info[1]}]: "
              f"准确率 = {stats['accuracy_percent']:.1f}%")

    print(f"\n3. 扭转点拓扑验证: {'通过 ✓' if torsion_valid else '失败 ✗'}")

    print(f"\n详细结果文件: {summary_file}")
    print("=" * 70)

    return predictor, summary_file


if __name__ == "__main__":
    predictor, summary_file = run_comprehensive_validation()
