"""
莫比乌斯环素数预测 - 系统性优化实验

目标：通过以下三个维度寻找精度提升空间
1. 谱零点数量扩展（m_max, n_max, num_zeros）
2. 几何参数缩放（R, w 同步放大）
3. 振荡项振幅优化（不同的衰减律）
"""

import numpy as np
import sys
import os

# 导入主类
sys.path.append(os.path.dirname(__file__))
from 莫比乌斯环预测素数2 import OptimizedPrimePredictor


class OptimizationExperiment:
    """优化实验管理器"""
    
    def __init__(self):
        self.results = []
        
    def experiment_spectral_resolution(self):
        """
        实验1：谱分辨率扫描
        
        测试不同数量的谱零点对精度的影响
        """
        print("\n" + "="*80)
        print("实验1：谱分辨率对预测精度的影响")
        print("="*80)
        
        configs = [
            {'m_max': 100, 'n_max': 100, 'num_zeros': 50, 'label': '低分辨率'},
            {'m_max': 200, 'n_max': 200, 'num_zeros': 100, 'label': '中分辨率（当前）'},
            {'m_max': 300, 'n_max': 300, 'num_zeros': 200, 'label': '高分辨率'},
            {'m_max': 500, 'n_max': 500, 'num_zeros': 300, 'label': '超高分辨率'},
        ]
        
        for config in configs:
            print(f"\n测试配置: {config['label']}")
            print(f"  m_max={config['m_max']}, n_max={config['n_max']}, num_zeros={config['num_zeros']}")
            
            predictor = OptimizedPrimePredictor(R=1.0, w=0.8, precision='standard')
            predictor.m_max = config['m_max']
            predictor.n_max = config['n_max']
            predictor.num_zeros_for_oscillation = config['num_zeros']
            
            # 加载素数
            predictor.load_known_primes(N_max=1000000)
            
            # 计算谱零点
            predictor.compute_mobius_spectral_zeros()
            
            # 快速验证（采样100个点）
            test_indices = range(10000, 20000, 100)
            errors = []
            
            for n in test_indices:
                actual = predictor.known_primes[n - 1]
                predicted = predictor.prime_formula_optimized(n)
                rel_error = abs(predicted - actual) / actual * 100
                errors.append(rel_error)
            
            mean_error = np.mean(errors)
            median_error = np.median(errors)
            max_error = np.max(errors)
            
            print(f"  平均相对误差: {mean_error:.4f}%")
            print(f"  中位数误差:   {median_error:.4f}%")
            print(f"  最大误差:     {max_error:.4f}%")
            
            self.results.append({
                'experiment': 'spectral_resolution',
                'config': config,
                'mean_error': mean_error,
                'median_error': median_error,
                'max_error': max_error
            })
    
    def experiment_geometry_scaling(self):
        """
        实验2：几何参数缩放
        
        测试增大R和w是否提升精度（保持R/w比值）
        """
        print("\n" + "="*80)
        print("实验2：几何参数缩放对预测精度的影响")
        print("="*80)
        
        # 保持 R/w = 1.25 的比例
        scale_factors = [1.0, 1.5, 2.0, 3.0, 5.0]
        
        for scale in scale_factors:
            R = 1.0 * scale
            w = 0.8 * scale
            
            print(f"\n测试配置: 缩放因子 {scale}x (R={R:.1f}, w={w:.1f})")
            
            predictor = OptimizedPrimePredictor(R=R, w=w, precision='standard')
            predictor.load_known_primes(N_max=1000000)
            predictor.compute_mobius_spectral_zeros()
            
            # 快速验证
            test_indices = range(10000, 20000, 100)
            errors = []
            
            for n in test_indices:
                actual = predictor.known_primes[n - 1]
                predicted = predictor.prime_formula_optimized(n)
                rel_error = abs(predicted - actual) / actual * 100
                errors.append(rel_error)
            
            mean_error = np.mean(errors)
            median_error = np.median(errors)
            
            print(f"  平均相对误差: {mean_error:.4f}%")
            print(f"  中位数误差:   {median_error:.4f}%")
            
            self.results.append({
                'experiment': 'geometry_scaling',
                'scale_factor': scale,
                'R': R,
                'w': w,
                'mean_error': mean_error,
                'median_error': median_error
            })
    
    def experiment_amplitude_decay(self):
        """
        实验3：振荡项振幅衰减律优化
        
        测试不同的振幅衰减公式
        """
        print("\n" + "="*80)
        print("实验3：振荡项振幅衰减律优化")
        print("="*80)
        
        # 需要临时修改源码中的振幅计算
        # 这里通过继承实现
        
        class ModifiedPredictor(OptimizedPrimePredictor):
            def __init__(self, *args, decay_type='linear', **kwargs):
                super().__init__(*args, **kwargs)
                self.decay_type = decay_type
            
            def prime_formula_optimized(self, n, include_topology=True):
                """重写振荡项计算"""
                if n < 2:
                    return 2.0
                
                if self.mobius_zeros_cache is None:
                    self.compute_mobius_spectral_zeros()
                
                log_n = np.log(n, dtype=self.dtype)
                log_log_n = np.log(log_n)
                
                # 主项（保持不变）
                main_term = n * (
                    log_n + log_log_n - 1
                    + (log_log_n - 2) / log_n
                    - ((log_log_n)**2 - 6*log_log_n + 11) / (2 * log_n**2)
                    + ((log_log_n)**3 - 9*(log_log_n)**2 + 36*log_log_n - 62) / (6 * log_n**3)
                )
                
                # 振荡项（不同的衰减律）
                oscillation = 0.0
                num_zeros = min(self.num_zeros_for_oscillation, len(self.mobius_zeros_cache))
                
                for k in range(num_zeros):
                    gamma_k = self.mobius_zeros_cache[k].imag
                    
                    # === 不同的振幅衰减策略 ===
                    if self.decay_type == 'linear':
                        # 原始：1/(k+1)
                        amplitude = 2.0 / (k + 1)
                    
                    elif self.decay_type == 'inverse_gamma':
                        # 基于零点位置：1/gamma_k
                        amplitude = 2.0 / gamma_k
                    
                    elif self.decay_type == 'mixed':
                        # 混合：1/((k+1)^alpha * gamma_k^beta)
                        alpha, beta = 0.5, 0.5
                        amplitude = 2.0 / ((k + 1)**alpha * gamma_k**beta)
                    
                    elif self.decay_type == 'exponential':
                        # 指数衰减
                        amplitude = 2.0 * np.exp(-k / 50)
                    
                    else:
                        amplitude = 2.0 / (k + 1)
                    
                    phase = gamma_k * log_n
                    damping = np.exp(-k / num_zeros)
                    
                    oscillation += amplitude * damping * np.cos(phase) / np.sqrt(n)
                
                # 拓扑修正
                topological_correction = 0.0
                if include_topology:
                    topological_correction = 0.3 * (self.w / self.R) * np.sin(2 * np.pi * n / self.R)
                
                # 有限尺寸修正
                finite_size_correction = 0.5 * np.log(n) / n
                
                predicted_prime = main_term + oscillation + topological_correction + finite_size_correction
                
                return float(max(predicted_prime, 2.0))
        
        # 测试不同的衰减类型
        decay_types = [
            'linear',           # 原始方法
            'inverse_gamma',    # 基于零点位置
            'mixed',            # 混合衰减
            'exponential',      # 指数衰减
        ]
        
        for decay_type in decay_types:
            print(f"\n测试衰减类型: {decay_type}")
            
            predictor = ModifiedPredictor(R=1.0, w=0.8, precision='standard', decay_type=decay_type)
            predictor.load_known_primes(N_max=1000000)
            predictor.compute_mobius_spectral_zeros()
            
            # 验证
            test_indices = range(10000, 20000, 100)
            errors = []
            
            for n in test_indices:
                actual = predictor.known_primes[n - 1]
                predicted = predictor.prime_formula_optimized(n)
                rel_error = abs(predicted - actual) / actual * 100
                errors.append(rel_error)
            
            mean_error = np.mean(errors)
            median_error = np.median(errors)
            
            print(f"  平均相对误差: {mean_error:.4f}%")
            print(f"  中位数误差:   {median_error:.4f}%")
            
            self.results.append({
                'experiment': 'amplitude_decay',
                'decay_type': decay_type,
                'mean_error': mean_error,
                'median_error': median_error
            })
    
    def save_results(self):
        """保存实验结果"""
        import json
        from datetime import datetime
        
        output_dir = os.path.join(os.path.dirname(__file__), '../output_data')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f'optimization_experiments_{timestamp}.json')
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'experiments': self.results,
                'summary': {
                    'total_experiments': len(self.results),
                    'best_config': min(self.results, key=lambda x: x.get('mean_error', float('inf')))
                },
                'timestamp': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*80}")
        print(f"实验结果已保存到: {filename}")
        print(f"{'='*80}")
        
        # 打印最佳配置
        best = min(self.results, key=lambda x: x.get('mean_error', float('inf')))
        print(f"\n🏆 最佳配置:")
        print(f"  实验类型: {best['experiment']}")
        if 'config' in best:
            print(f"  配置: {best['config']}")
        elif 'decay_type' in best:
            print(f"  衰减类型: {best['decay_type']}")
        elif 'scale_factor' in best:
            print(f"  缩放因子: {best['scale_factor']}x")
        print(f"  平均相对误差: {best['mean_error']:.4f}%")


def main():
    """运行所有优化实验"""
    print("="*80)
    print("莫比乌斯环素数预测 - 系统性优化实验")
    print("="*80)
    print("\n注意：完整实验可能需要较长时间（预计30-60分钟）")
    print("可以注释掉部分实验进行快速测试\n")
    
    experiment = OptimizationExperiment()
    
    # 运行三个实验
    experiment.experiment_spectral_resolution()
    experiment.experiment_geometry_scaling()
    experiment.experiment_amplitude_decay()
    
    # 保存结果
    experiment.save_results()
    
    print("\n✅ 所有实验完成！")


if __name__ == '__main__':
    main()
