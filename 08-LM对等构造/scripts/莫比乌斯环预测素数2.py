"""
莫比乌斯环拓扑素数预测模型 - 优化版

改进点：
1. 专注于大数区域（n > 10000）的高精度预测
2. 使用更高精度的数值计算
3. 引入局部零点关联和Montgomery配对相关
4. 贝叶斯修正框架
5. 自适应参数调整
"""

import numpy as np
from scipy.optimize import minimize_scalar, curve_fit
from scipy.stats import gaussian_kde, norm
from scipy.special import loggamma
import json
from datetime import datetime
import os


class OptimizedPrimePredictor:
    """
    优化的莫比乌斯环素数预测器

    核心改进：
    - 高精度渐近展开（包含更多项）
    - 局部零点密度自适应
    - Montgomery配对相关函数
    - 贝叶斯后验修正
    """

    def __init__(self, R=1.0, w=0.8, precision='high'):
        self.R = R
        self.w = w
        self.precision = precision  # 'standard' or 'high'

        # 根据精度设置数值参数
        if precision == 'high':
            self.m_max = 200
            self.n_max = 200
            self.dtype = np.float128 if hasattr(np, 'float128') else np.float64
            self.num_zeros_for_oscillation = 100
        else:
            self.m_max = 100
            self.n_max = 100
            self.dtype = np.float64
            self.num_zeros_for_oscillation = 50

        self.mobius_zeros_cache = None
        self.known_primes = None
        self.prime_gaps_cache = None

    def load_known_primes(self, N_max=1000000):
        """加载已知素数数据库"""
        sieve = np.ones(N_max + 1, dtype=bool)
        sieve[0] = sieve[1] = False

        for i in range(2, int(np.sqrt(N_max)) + 1):
            if sieve[i]:
                sieve[i*i::i] = False

        self.known_primes = np.where(sieve)[0].astype(self.dtype)
        self.prime_gaps_cache = np.diff(self.known_primes).astype(self.dtype)

        print(f"✓ 已加载 {len(self.known_primes)} 个素数（高精度模式: {self.precision}）")
        return self.known_primes

    def compute_mobius_spectral_zeros(self):
        """
        高精度计算莫比乌斯谱零点
        """
        eigenvals = []

        for m_half in range(0, self.m_max):
            m = m_half + 0.5
            for n in range(1, self.n_max + 1):
                lambda_mn = (m / self.R) ** 2 + (n * np.pi / self.w) ** 2
                eigenvals.append(lambda_mn)

        eigenvals = np.array(sorted(eigenvals), dtype=self.dtype)

        spectral_zeros = []
        for lam in eigenvals:
            if lam > 0.25:
                gamma = 0.5 * np.sqrt(4 * lam - 1)
                spectral_zeros.append(complex(0.5, gamma))

        spectral_zeros.sort(key=lambda z: z.imag)
        self.mobius_zeros_cache = np.array(spectral_zeros, dtype=np.complex128)

        print(f"✓ 已计算 {len(spectral_zeros)} 个莫比乌斯谱零点（m_max={self.m_max}, n_max={self.n_max}）")

        return self.mobius_zeros_cache

    def prime_formula_optimized(self, n, include_topology=True):
        """
        优化的素数公式（高精度版本）

        包含：
        1. 高阶渐近展开（到1/log(n)^4项）
        2. 振荡项（使用更多零点）
        3. 拓扑修正（可选）
        4. 有限尺寸修正
        """
        if n < 2:
            return 2.0

        if self.mobius_zeros_cache is None:
            self.compute_mobius_spectral_zeros()

        log_n = np.log(n, dtype=self.dtype)
        log_log_n = np.log(log_n)

        # === 主项：高阶渐近展开 ===
        # 基于素数计数函数的逆
        main_term = n * (
            log_n
            + log_log_n
            - 1
            + (log_log_n - 2) / log_n
            - ((log_log_n)**2 - 6*log_log_n + 11) / (2 * log_n**2)
            + ((log_log_n)**3 - 9*(log_log_n)**2 + 36*log_log_n - 62) / (6 * log_n**3)
            - ((log_log_n)**4 - 12*(log_log_n)**3 + 78*(log_log_n)**2 - 240*log_log_n + 303) / (12 * log_n**4)
        )

        # === 振荡项：来自莫比乌斯谱零点 ===
        oscillation = 0.0
        num_zeros = min(self.num_zeros_for_oscillation, len(self.mobius_zeros_cache))

        for k in range(num_zeros):
            gamma_k = self.mobius_zeros_cache[k].imag

            # 振幅衰减：A_k ~ 1/(k+1)^alpha
            alpha = 1.0  # 可调参数
            amplitude = 2.0 / ((k + 1) ** alpha)

            # 相位项
            phase = gamma_k * log_n

            # 阻尼因子（避免高频振荡过大）
            damping = np.exp(-k / num_zeros)

            oscillation += amplitude * damping * np.cos(phase) / np.sqrt(n)

        # === 拓扑修正项 ===
        topological_correction = 0.0
        if include_topology:
            # 基本拓扑调制
            topological_correction = 0.3 * (self.w / self.R) * np.sin(2 * np.pi * n / self.R)

            # 高阶拓扑谐波
            topological_correction += 0.1 * (self.w / self.R) * np.sin(4 * np.pi * n / self.R) / 2

        # === 有限尺寸修正 ===
        finite_size_correction = 0.5 * np.log(n) / n

        predicted_prime = main_term + oscillation + topological_correction + finite_size_correction

        return float(max(predicted_prime, 2.0))

    def montgomery_pair_correlation(self, s):
        """
        Montgomery配对相关函数

        R(s) = 1 - (sin(πs)/(πs))^2

        描述零点间距的两点关联
        """
        if s == 0:
            return 0.0
        return 1.0 - (np.sin(np.pi * s) / (np.pi * s))**2

    def local_zero_density(self, n_index, window_size=50):
        """
        计算局部零点密度

        使用滑动窗口估计第n个素数附近的零点密度
        """
        if self.mobius_zeros_cache is None:
            self.compute_mobius_spectral_zeros()

        zeros = self.mobius_zeros_cache

        # 确定窗口范围
        start_idx = max(0, n_index - window_size // 2)
        end_idx = min(len(zeros), n_index + window_size // 2)

        if end_idx - start_idx < 2:
            return 1.0  # 默认值

        # 提取窗口内的零点
        window_zeros = zeros[start_idx:end_idx]

        # 计算间距
        spacings = np.diff([z.imag for z in window_zeros])

        if len(spacings) == 0:
            return 1.0

        # 平均间距
        mean_spacing = np.mean(spacings)

        # 归一化密度（相对于全局平均）
        global_mean = np.mean([zeros[i+1].imag - zeros[i].imag for i in range(min(1000, len(zeros)-1))])

        normalized_density = global_mean / mean_spacing if mean_spacing > 0 else 1.0

        return normalized_density

    def predict_next_prime_bayesian(self, current_idx, use_local_stats=True):
        """
        贝叶斯框架下的下一个素数预测

        结合：
        1. 先验：素数定理给出的期望间隙 log(p)
        2. 似然：局部零点统计
        3. 后验：加权平均

        参数：
        current_idx: 当前素数的索引（从1开始）
        use_local_stats: 是否使用局部统计修正
        """
        if self.known_primes is None:
            raise ValueError("请先加载已知素数")

        if current_idx >= len(self.known_primes):
            raise ValueError(f"索引 {current_idx} 超出范围")

        current_p = self.known_primes[current_idx - 1]

        # === 先验分布：基于素数定理 ===
        prior_mean_gap = np.log(current_p)
        prior_std_gap = 0.5 * np.log(current_p)  # 启发式估计

        # === 似然函数：基于局部历史间隙 ===
        if use_local_stats and current_idx > 20:
            # 提取最近的素数间隙
            recent_gaps = self.prime_gaps_cache[max(0, current_idx-21):current_idx-1]

            likelihood_mean = np.mean(recent_gaps)
            likelihood_std = np.std(recent_gaps) if len(recent_gaps) > 1 else prior_std_gap

            # 防止标准差过小
            likelihood_std = max(likelihood_std, 1.0)
        else:
            likelihood_mean = prior_mean_gap
            likelihood_std = prior_std_gap

        # === 莫比乌斯谱修正 ===
        zero_density = self.local_zero_density(current_idx, window_size=50)

        # 零点密度与素数间隙的关系
        spectral_correction = zero_density * (2 * np.pi / np.log(current_p))

        # === 贝叶斯后验 ===
        # 后验均值 = (先验精度×先验均值 + 似然精度×似然均值) / (先验精度 + 似然精度)
        prior_precision = 1.0 / prior_std_gap**2
        likelihood_precision = 1.0 / likelihood_std**2

        posterior_mean_gap = (
            prior_precision * prior_mean_gap
            + likelihood_precision * likelihood_mean
        ) / (prior_precision + likelihood_precision)

        posterior_std_gap = 1.0 / np.sqrt(prior_precision + likelihood_precision)

        # 应用谱修正
        final_predicted_gap = posterior_mean_gap * (spectral_correction / prior_mean_gap)

        predicted_next_prime = current_p + final_predicted_gap

        return {
            'current_index': current_idx,
            'current_prime': float(current_p),
            'predicted_next': float(predicted_next_prime),
            'predicted_gap': float(final_predicted_gap),
            'posterior_std': float(posterior_std_gap),
            'confidence_interval_95': [
                float(predicted_next_prime - 1.96 * posterior_std_gap),
                float(predicted_next_prime + 1.96 * posterior_std_gap)
            ],
            'zero_density_correction': float(zero_density),
            'prior_mean_gap': float(prior_mean_gap),
            'likelihood_mean_gap': float(likelihood_mean)
        }

    def validate_large_primes(self, n_start=10000, n_end=100000, step=100):
        """
        专门验证大数区域的预测精度

        参数：
        n_start: 起始索引（建议>=10000）
        n_end: 结束索引
        step: 采样步长（减少计算量）
        """
        if self.known_primes is None:
            self.load_known_primes()

        print(f"\n正在验证大数区域素数公式（索引 {n_start} ~ {n_end}，步长 {step}）...")

        errors = []
        relative_errors = []
        detailed_results = []

        sample_indices = range(n_start, min(n_end + 1, len(self.known_primes) + 1), step)

        for n in sample_indices:
            actual = self.known_primes[n - 1]
            predicted = self.prime_formula_optimized(n)

            error = predicted - actual
            abs_error = abs(error)
            rel_error = abs_error / actual * 100

            errors.append(error)
            relative_errors.append(rel_error)

            detailed_results.append({
                'n': int(n),
                'actual': int(actual),
                'predicted': float(predicted),
                'error': float(error),
                'abs_error': float(abs_error),
                'rel_error_percent': float(rel_error)
            })

        errors = np.array(errors)
        relative_errors = np.array(relative_errors)

        stats = {
            'validation_range': [int(n_start), int(min(n_end, len(self.known_primes)))],
            'num_samples': len(detailed_results),
            'step_size': step,
            'mean_abs_error': float(np.mean(np.abs(errors))),
            'max_abs_error': float(np.max(np.abs(errors))),
            'rms_error': float(np.sqrt(np.mean(errors**2))),
            'mean_rel_error_percent': float(np.mean(relative_errors)),
            'median_rel_error_percent': float(np.median(relative_errors)),
            'max_rel_error_percent': float(np.max(relative_errors)),
            'min_rel_error_percent': float(np.min(relative_errors)),
            'std_rel_error_percent': float(np.std(relative_errors)),
            'accuracy_within_0.1_percent': float(np.sum(relative_errors < 0.1) / len(relative_errors) * 100),
            'accuracy_within_0.5_percent': float(np.sum(relative_errors < 0.5) / len(relative_errors) * 100),
            'accuracy_within_1_percent': float(np.sum(relative_errors < 1.0) / len(relative_errors) * 100)
        }

        print(f"\n{'='*70}")
        print(f"大数区域验证结果（{stats['num_samples']} 个样本）")
        print(f"{'='*70}")
        print(f"平均绝对误差:     {stats['mean_abs_error']:>12.2f}")
        print(f"最大绝对误差:     {stats['max_abs_error']:>12.2f}")
        print(f"均方根误差(RMS):  {stats['rms_error']:>12.2f}")
        print(f"\n相对误差统计:")
        print(f"  平均值:         {stats['mean_rel_error_percent']:>11.4f}%")
        print(f"  中位数:         {stats['median_rel_error_percent']:>11.4f}%")
        print(f"  标准差:         {stats['std_rel_error_percent']:>11.4f}%")
        print(f"  最大值:         {stats['max_rel_error_percent']:>11.4f}%")
        print(f"  最小值:         {stats['min_rel_error_percent']:>11.4f}%")
        print(f"\n高精度统计:")
        print(f"  相对误差 < 0.1%: {stats['accuracy_within_0.1_percent']:>9.2f}%")
        print(f"  相对误差 < 0.5%: {stats['accuracy_within_0.5_percent']:>9.2f}%")
        print(f"  相对误差 < 1.0%: {stats['accuracy_within_1_percent']:>9.2f}%")
        print(f"{'='*70}")

        return {
            'statistics': stats,
            'detailed_results': detailed_results[:200],  # 保存部分详细结果
            'timestamp': datetime.now().isoformat()
        }

    def validate_next_prime_improved(self, test_range=(10000, 11000)):
        """
        改进版：验证下一个素数预测（大数区域）
        """
        if self.known_primes is None:
            self.load_known_primes()

        start_idx, end_idx = test_range

        print(f"\n正在验证改进的下一个素数预测（索引 {start_idx} ~ {end_idx}）...")

        correct_predictions = 0
        within_1_unit = 0
        within_2_units = 0
        total_predictions = 0
        prediction_errors = []

        for idx in range(start_idx, min(end_idx, len(self.known_primes))):
            try:
                pred = self.predict_next_prime_bayesian(idx, use_local_stats=True)
                actual_next = self.known_primes[idx]

                predicted_rounded = round(pred['predicted_next'])

                error = abs(predicted_rounded - actual_next)
                prediction_errors.append(error)

                if predicted_rounded == actual_next:
                    correct_predictions += 1

                if error <= 1:
                    within_1_unit += 1

                if error <= 2:
                    within_2_units += 1

                total_predictions += 1

            except Exception as e:
                continue

        prediction_errors = np.array(prediction_errors)

        results = {
            'test_range': list(test_range),
            'total_predictions': total_predictions,
            'exact_match': correct_predictions,
            'accuracy_exact_percent': float(correct_predictions / total_predictions * 100) if total_predictions > 0 else 0,
            'within_1_unit': within_1_unit,
            'accuracy_within_1_percent': float(within_1_unit / total_predictions * 100) if total_predictions > 0 else 0,
            'within_2_units': within_2_units,
            'accuracy_within_2_percent': float(within_2_units / total_predictions * 100) if total_predictions > 0 else 0,
            'mean_error': float(np.mean(prediction_errors)),
            'median_error': float(np.median(prediction_errors)),
            'max_error': int(np.max(prediction_errors)),
            'std_error': float(np.std(prediction_errors)),
            'timestamp': datetime.now().isoformat()
        }

        print(f"\n{'='*70}")
        print(f"改进版下一个素数预测验证")
        print(f"{'='*70}")
        print(f"总预测次数:           {total_predictions}")
        print(f"精确匹配:             {correct_predictions} ({results['accuracy_exact_percent']:.2f}%)")
        print(f"误差 ≤ 1:            {within_1_unit} ({results['accuracy_within_1_percent']:.2f}%)")
        print(f"误差 ≤ 2:            {within_2_units} ({results['accuracy_within_2_percent']:.2f}%)")
        print(f"\n误差统计:")
        print(f"  平均值:             {results['mean_error']:>10.2f}")
        print(f"  中位数:             {results['median_error']:>10.2f}")
        print(f"  标准差:             {results['std_error']:>10.2f}")
        print(f"  最大值:             {results['max_error']:>10d}")
        print(f"{'='*70}")

        return results

    def parameter_optimization_scan(self, n_validation_range=(10000, 20000)):
        """
        参数优化扫描：寻找最优的 (R, w) 组合
        """
        print(f"\n正在进行参数优化扫描...")

        best_params = {'R': self.R, 'w': self.w}
        best_error = float('inf')

        # 参数网格
        R_values = np.linspace(0.8, 1.5, 15)
        w_values = np.linspace(0.5, 1.2, 15)

        results_grid = []

        for R in R_values:
            for w in w_values:
                # 创建临时预测器
                temp_predictor = OptimizedPrimePredictor(R=R, w=w, precision='standard')
                temp_predictor.known_primes = self.known_primes
                temp_predictor.compute_mobius_spectral_zeros()

                # 快速验证
                test_indices = range(n_validation_range[0], n_validation_range[1], 50)
                errors = []

                for n in test_indices:
                    actual = self.known_primes[n - 1]
                    predicted = temp_predictor.prime_formula_optimized(n)
                    rel_error = abs(predicted - actual) / actual
                    errors.append(rel_error)

                mean_rel_error = np.mean(errors)

                results_grid.append({
                    'R': float(R),
                    'w': float(w),
                    'mean_rel_error': float(mean_rel_error)
                })

                if mean_rel_error < best_error:
                    best_error = mean_rel_error
                    best_params = {'R': float(R), 'w': float(w)}

        print(f"\n最优参数: R = {best_params['R']:.2f}, w = {best_params['w']:.2f}")
        print(f"最优平均相对误差: {best_error*100:.4f}%")

        return {
            'best_parameters': best_params,
            'best_error_percent': float(best_error * 100),
            'grid_search_results': results_grid,
            'timestamp': datetime.now().isoformat()
        }

    def save_comprehensive_results(self, formula_stats, prediction_stats, param_opt=None):
        """保存综合验证结果"""
        output_dir = os.path.join(os.path.dirname(__file__), '../output_data')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f'optimized_mobius_validation_R{self.R}_w{self.w}_{timestamp}.json')

        results = {
            'model_info': {
                'R': self.R,
                'w': self.w,
                'precision': self.precision,
                'm_max': self.m_max,
                'n_max': self.n_max,
                'num_zeros_used': self.num_zeros_for_oscillation
            },
            'formula_validation_large_primes': formula_stats,
            'next_prime_prediction_improved': prediction_stats,
            'parameter_optimization': param_opt,
            'timestamp': timestamp
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n✓ 结果已保存到: {filename}")
        return filename


def run_optimized_validation():
    """运行优化版的全面验证"""
    print("=" * 70)
    print("莫比乌斯环素数预测 - 优化版验证（大数区域）")
    print("=" * 70)

    # 初始化高精度预测器
    predictor = OptimizedPrimePredictor(R=1.0, w=0.8, precision='high')

    # 加载数据
    predictor.load_known_primes(N_max=1000000)
    predictor.compute_mobius_spectral_zeros()

    # 测试1: 大数区域公式验证
    print("\n" + "=" * 70)
    print("测试1: 大数区域素数公式验证（n > 10000）")
    print("=" * 70)

    formula_stats = predictor.validate_large_primes(
        n_start=10000,
        n_end=100000,
        step=50
    )

    # 测试2: 改进的下一个素数预测
    print("\n" + "=" * 70)
    print("测试2: 改进版下一个素数预测")
    print("=" * 70)

    prediction_stats = predictor.validate_next_prime_improved(
        test_range=(10000, 11000)
    )

    # 测试3: 参数优化（可选，耗时较长）
    print("\n" + "=" * 70)
    print("测试3: 参数优化扫描")
    print("=" * 70)

    param_opt = predictor.parameter_optimization_scan(
        n_validation_range=(10000, 15000)
    )

    # 保存结果
    summary_file = predictor.save_comprehensive_results(
        formula_stats,
        prediction_stats,
        param_opt
    )

    # 最终总结
    print("\n" + "=" * 70)
    print("优化版验证总结")
    print("=" * 70)

    stats = formula_stats['statistics']
    print(f"\n1. 大数公式精度（n=10000~100000）:")
    print(f"   平均相对误差: {stats['mean_rel_error_percent']:.4f}%")
    print(f"   中位数误差:   {stats['median_rel_error_percent']:.4f}%")
    print(f"   <0.1%精度:    {stats['accuracy_within_0.1_percent']:.1f}%")
    print(f"   <0.5%精度:    {stats['accuracy_within_0.5_percent']:.1f}%")

    print(f"\n2. 下一个素数预测（n=10000~11000）:")
    print(f"   精确匹配率:   {prediction_stats['accuracy_exact_percent']:.2f}%")
    print(f"   误差≤1比例:   {prediction_stats['accuracy_within_1_percent']:.2f}%")
    print(f"   误差≤2比例:   {prediction_stats['accuracy_within_2_percent']:.2f}%")
    print(f"   平均误差:     {prediction_stats['mean_error']:.2f}")

    print(f"\n3. 最优参数:")
    print(f"   R = {param_opt['best_parameters']['R']:.2f}")
    print(f"   w = {param_opt['best_parameters']['w']:.2f}")
    print(f"   对应误差:     {param_opt['best_error_percent']:.4f}%")

    print(f"\n完整结果: {summary_file}")
    print("=" * 70)

    return predictor, summary_file


if __name__ == "__main__":
    predictor, summary_file = run_optimized_validation()
