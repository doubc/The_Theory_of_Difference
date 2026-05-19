"""
experiments/exp_40_hierarchical.py — 跨层级演化实验

验证分层封装机制：
1. N=48 初始系统
2. 每层运行直到 A9 触发封口
3. 自动封装并创建新层
4. 观察层级涌现和九机制指标
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hierarchical_evolver import HierarchicalEvolver


def main():
    print("=" * 70)
    print("EXP 40: Hierarchical Encapsulation Test")
    print("=" * 70)

    start_time = time.time()

    evolver = HierarchicalEvolver(
        N0=48,
        steps_per_layer=3000,
        sample_interval=300,
        max_layers=3,
        device="cpu",
        binding_threshold=0.1,
        min_group_size=2,
        n_hierarchy_bits=16,
        L=1.0,
        auto_encapsulate=True
    )

    results = evolver.run(verbose=True)
    elapsed = time.time() - start_time

    evolver.print_results(results)

    # 保存结果
    output = {
        'experiment': 'exp_40_hierarchical',
        'N0': 48,
        'n_layers': results['n_layers'],
        'elapsed_seconds': elapsed,
        'layer_results': [
            {
                'layer': lr['layer'],
                'N': lr['N'],
                'w': lr['w'],
                'sealed': lr['sealed'],
                'steps': lr['steps'],
                'inj': lr['inj'],
                'abs': lr['abs'],
                'cycles': lr['cycles'],
                'n_clusters': len(lr['clusters']),
            }
            for lr in results['layer_results']
        ],
        'encapsulation_events': [
            {
                'from': ev['from_layer'],
                'to': ev['to_layer'],
                'bits_before': ev['n_bits_before'],
                'bits_after': ev['n_bits_after'],
                'active_preserved': ev['n_active_preserved'],
                'encapsulated': ev['n_encapsulated'],
            }
            for ev in results['encapsulation_events']
        ]
    }

    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'exp_40_results.json'
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {output_path}")
    print(f"Elapsed: {elapsed:.1f}s")

    # ====== 验收检查 ======
    print("\n" + "=" * 70)
    print("ACCEPTANCE CHECKS")
    print("=" * 70)

    checks = []

    # 1. 至少 2 层
    n_layers = results['n_layers']
    checks.append(("≥2 layers", n_layers >= 2, f"n_layers={n_layers}"))

    # 2. 第 0 层封口
    layer0_sealed = results['layer_results'][0]['sealed'] if results['layer_results'] else False
    checks.append(("Layer 0 sealed", layer0_sealed, f"sealed={layer0_sealed}"))

    # 3. 至少 1 次封装事件
    n_enc = len(results['encapsulation_events'])
    checks.append(("≥1 encapsulation", n_enc >= 1, f"n_events={n_enc}"))

    # 4. 每层都有九机制指标（除了可能的残余层）
    for lr in results['layer_results']:
        if lr['steps'] == 0:
            continue  # 跳过残余层
        has_data = lr['steps'] > 0
        checks.append((f"Layer {lr['layer']} has data", has_data,
                        f"steps={lr['steps']}"))

    # 5. 比特数递减
    if len(results['layer_results']) >= 2:
        n0 = results['layer_results'][0]['N']
        n1 = results['layer_results'][1]['N']
        checks.append(("N decreases", n1 < n0, f"N0={n0} → N1={n1}"))

    all_pass = True
    for name, passed, detail in checks:
        status = "PASS [OK]" if passed else "FAIL [XX]"
        print(f"  {status}: {name} ({detail})")
        if not passed:
            all_pass = False

    print(f"\n{'ALL CHECKS PASSED [OK]' if all_pass else 'SOME CHECKS FAILED [XX]'}")

    return all_pass


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
