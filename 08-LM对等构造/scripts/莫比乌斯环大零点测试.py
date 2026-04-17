"""
莫比乌斯环素数预测 - 超大零点数量测试

目标：验证零点数量是否是0.31%精度天花板的瓶颈
测试范围：从100到2000个零点
"""

import numpy as np
import sys
import os
import pickle
from datetime import datetime

sys.path.append(os.path.dirname(__file__))
from 莫比乌斯环预测素数2 import OptimizedPrimePredictor


class PrimeCache:
    """素数缓存管理器"""

    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), '../output_data')

        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        self.cache_file = os.path.join(cache_dir, 'prime_cache.pkl')
        self.prime_cache = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    self.prime_cache = pickle.load(f)
                print(f"✓ 已加载素数缓存")
            except Exception as e:
                print(f"⚠ 缓存加载失败: {e}")
                self.prime_cache = {}

    def get_primes(self, N_max=1000000):
        if N_max in self.prime_cache:
            return self.prime_cache[N_max]

        print(f"  生成素数表 (N_max={N_max})...", end=' ', flush=True)
        sieve = np.ones(N_max + 1, dtype=bool)
        sieve[0] = sieve[1] = False

        for i in range(2, int(np.sqrt(N_max)) + 1):
            if sieve[i]:
                sieve[i * i::i] = False

        primes = np.where(sieve)[0]
        self.prime_cache[N_max] = primes

        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.prime_cache, f)

        print(f"完成 ({len(primes)} 个素数)")
        return primes


def test_large_zero_count():
    """测试超大零点数量对精度的影响"""

    print("=" * 80)
    print("莫比乌斯环素数预测 - 超大零点数量测试")
    print("=" * 80)

    # 初始化素数缓存
    prime_cache = PrimeCache()
    primes = prime_cache.get_primes(N_max=1000000)

    # 测试配置：从零点数100到2000
    zero_configs = [
        {'num_zeros': 100, 'm_max': 500, 'n_max': 500, 'label': '100个零点'},
        {'num_zeros': 200, 'm_max': 500, 'n_max': 500, 'label': '200个零点'},
        {'num_zeros': 300, 'm_max': 500, 'n_max': 500, 'label': '300个零点'},
        {'num_zeros': 500, 'm_max': 1000, 'n_max': 1000, 'label': '500个零点'},
        {'num_zeros': 800, 'm_max': 1500, 'n_max': 1500, 'label': '800个零点'},
        {'num_zeros': 1000, 'm_max': 2000, 'n_max': 2000, 'label': '1000个零点'},
        {'num_zeros': 1500, 'm_max': 2500, 'n_max': 2500, 'label': '1500个零点'},
        {'num_zeros': 2000, 'm_max': 3000, 'n_max': 3000, 'label': '2000个零点'},
    ]

    results = []

    for config in zero_configs:
        print(f"\n{'=' * 80}")
        print(f"测试配置: {config['label']}")
        print(f"  m_max={config['m_max']}, n_max={config['n_max']}, num_zeros={config['num_zeros']}")
        print(f"{'=' * 80}")

        # 创建预测器（使用高精度模式）
        predictor = OptimizedPrimePredictor(R=1.0, w=0.8, precision='high')
        predictor.m_max = config['m_max']
        predictor.n_max = config['n_max']
        predictor.num_zeros_for_oscillation = config['num_zeros']

        # 使用缓存的素数
        predictor.known_primes = primes.astype(predictor.dtype)
        predictor.prime_gaps_cache = np.diff(primes).astype(predictor.dtype)
        print(f"  ✓ 已加载 {len(primes)} 个素数（从缓存）")

        # 计算谱零点（这可能需要一些时间）
        print(f"  正在计算谱零点...", end=' ', flush=True)
        predictor.compute_mobius_spectral_zeros()

        # 验证范围：n=10000 到 50000（更大的范围）
        print(f"  正在进行验证（n=10000~50000，每100个采样）...")
        test_indices = range(10000, 50000, 100)
        errors = []

        for i, n in enumerate(test_indices):
            actual = predictor.known_primes[n - 1]
            predicted = predictor.prime_formula_optimized(n)
            rel_error = abs(predicted - actual) / actual * 100
            errors.append(rel_error)

            # 显示进度
            if (i + 1) % 100 == 0:
                print(f"    进度: {i + 1}/{len(test_indices)}, 当前平均误差: {np.mean(errors):.4f}%")

        mean_error = np.mean(errors)
        median_error = np.median(errors)
        max_error = np.max(errors)
        min_error = np.min(errors)
        std_error = np.std(errors)

        print(f"\n  📊 结果统计:")
        print(f"    平均相对误差: {mean_error:.6f}%")
        print(f"    中位数误差:   {median_error:.6f}%")
        print(f"    标准差:       {std_error:.6f}%")
        print(f"    最大误差:     {max_error:.6f}%")
        print(f"    最小误差:     {min_error:.6f}%")

        results.append({
            'config': config,
            'mean_error': mean_error,
            'median_error': median_error,
            'max_error': max_error,
            'min_error': min_error,
            'std_error': std_error,
            'num_zeros_used': config['num_zeros'],
            'total_eigenmodes': config['m_max'] * config['n_max']
        })

    # 保存结果
    output_dir = os.path.join(os.path.dirname(__file__), '../output_data')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f'large_zero_test_{timestamp}.json')

    import json
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({
            'test_type': 'large_zero_count',
            'results': results,
            'summary': {
                'best_config': min(results, key=lambda x: x['mean_error']),
                'error_reduction': f"{results[0]['mean_error']:.6f}% → {results[-1]['mean_error']:.6f}%",
                'improvement_percent': (
                            (results[0]['mean_error'] - results[-1]['mean_error']) / results[0]['mean_error'] * 100)
            },
            'timestamp': datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 80}")
    print(f"✅ 测试完成！结果已保存到: {filename}")
    print(f"{'=' * 80}")

    # 打印总结
    print(f"\n📈 精度变化趋势:")
    for r in results:
        improvement = ((results[0]['mean_error'] - r['mean_error']) / results[0]['mean_error'] * 100)
        print(f"  {r['config']['label']:15s}: {r['mean_error']:.6f}% (改善 {improvement:+.2f}%)")

    best = min(results, key=lambda x: x['mean_error'])
    print(f"\n🏆 最佳配置:")
    print(f"  零点数量: {best['num_zeros_used']}")
    print(f"  本征模式总数: {best['total_eigenmodes']}")
    print(f"  平均相对误差: {best['mean_error']:.6f}%")
    print(
        f"  相比 baseline 改善: {((results[0]['mean_error'] - best['mean_error']) / results[0]['mean_error'] * 100):.2f}%")


if __name__ == '__main__':
    test_large_zero_count()
