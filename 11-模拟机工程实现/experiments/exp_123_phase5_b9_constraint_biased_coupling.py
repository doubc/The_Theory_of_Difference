"""
Phase 5 Track B9: Constraint-Based Coupling (exp_123)

假设：
H50 (L1→L2 偏置生效): L1 冻结 bits 对 L2 稳定性有可测量的偏置效应（0.1 < bias_effect < 0.5）
H51 (L1-L2 相关性): L1-L2 稳定性相关性 > 0 但 < 0.7（偏置但不完全耦合）
H52 (L2 自主性): L2 有非零 ODI 且 not silent
H53 (L0→L2 主导性): L0-L2 相关性 > L1-L2 相关性（L2 主要从 L0 派生）

实验设计：
- 8 seeds × 2000 steps
- N0=48 (L0), N0=72 (L2 独立聚类)
- 使用 ConstraintBiasedCoupling（L1 冻结结构偏置 L2）
- 对比 B5 (IndependentL2Coupling) 作为基线

评估指标：
- L1-L2 稳定性相关性
- L0-L2 稳定性相关性
- L2 是否 silent
- L1 偏置强度演化
"""

import sys
import os
import json
import numpy as np
from datetime import datetime

# 项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from engine.cross_scale_coupling import ConstraintBiasedCoupling

# 实验配置
N_SEEDS = 8
N_STEPS = 2000
N0_L0 = 48
N0_L2 = 72

# Track B9 假设阈值
H50_BIAS_EFFECT_MIN = 0.1
H50_BIAS_EFFECT_MAX = 0.5
H51_L1_L2_CORR_MAX = 0.7
H51_L1_L2_CORR_MIN = 0.0
H52_SILENT_RATE_MAX = 0.0  # L2 不能是 silent
H53_L0_L2_CORR_MIN = 0.3  # L0-L2 相关性应该显著


def run_seed(seed, n_steps=2000, verbose=False):
    """运行单个 seed 的 Track B9 实验"""
    print(f"\n{'='*60}")
    print(f" Running seed {seed} (Track B9: Constraint-Based Coupling)")
    print(f"{'='*60}")

    # 1. 初始化组件
    config = {
        'l1_bias_strength': 0.4,
        'l1_frozen_gravity': 0.3,
        'l1_bias_decay': 0.98,
        'l1_min_bias': 0.05,
        'l2_independent_N0': N0_L2,
        'l2_stability_floor': 0.15,
        'l2_perturbation_rate': 0.03,
        'l2_perturbation_magnitude': 0.2,
        'l2_autonomous_decay': 0.97,
        'l2_odi_independence_weight': 0.5,
        'l2_clustering_noise': 0.15,
        'l0_direct_to_l2_weight': 0.4,
    }
    cbc = ConstraintBiasedCoupling(config)

    # 2. 模拟 L0 / L1 状态序列（简化模拟）
    results = {
        'seed': int(seed),
        'n_steps': int(n_steps),
        'l1_freeze_events': [],
        'l2_stability_history': [],
        'l1_stability_history': [],
        'l0_stability_history': [],
        'l2_odi_history': [],
        'l1_bias_strength_history': [],
        'l1_bias_effect_history': [],
        'l1_frozen_bits_count_history': [],
    }

    # 简化模拟：L0 稳定性（随机游走 + 漂移）
    np.random.seed(seed)
    l0_stability = 0.3 + np.random.random() * 0.4  # 初始 0.3-0.7
    l1_stability = 0.2 + np.random.random() * 0.3  # 初始 0.2-0.5
    l1_frozen = False
    l1_frozen_bits = set()

    for step in range(n_steps):
        # L0 随机游走
        l0_stability += np.random.randn() * 0.02
        l0_stability = np.clip(l0_stability, 0.0, 1.0)

        # L1 稳定性（受 L0 影响）
        l1_stability += (l0_stability - l1_stability) * 0.05 + np.random.randn() * 0.01
        l1_stability = np.clip(l1_stability, 0.0, 1.0)

        # L1 冻结事件（模拟 sealing）
        if not l1_frozen and l1_stability > 0.6 and np.random.random() < 0.002:
            l1_frozen = True
            l1_frozen_bits = set(np.random.choice(N0_L0, size=int(N0_L0 * 0.4), replace=False))
            results['l1_freeze_events'].append(int(step))
            if verbose:
                print(f"  Step {step}: L1 frozen ({len(l1_frozen_bits)} bits)")

        # 构造状态字典
        l0_state = {
            'stability_score': float(l0_stability),
            'odi': float(np.random.random() * 0.5),
            'structure_vector': None,  # 简化：不传真实向量
            'active_bits': set(range(N0_L0)),
        }
        l1_state = {
            'stability_score': float(l1_stability),
            'odi': float(np.random.random() * 0.3),
            'structure_vector': None,
            'frozen_bits': l1_frozen_bits if l1_frozen else set(),
        }

        # 执行一步 ConstraintBiasedCoupling
        l2_state = cbc.update(l0_state, l1_state)

        # 记录历史
        results['l0_stability_history'].append(float(l0_stability))
        results['l1_stability_history'].append(float(l1_stability))
        results['l2_stability_history'].append(float(l2_state['stability_score']))
        results['l2_odi_history'].append(float(l2_state['odi']))
        results['l1_bias_strength_history'].append(float(l2_state.get('l1_bias_strength', 0.0)))
        results['l1_bias_effect_history'].append(float(l2_state.get('l1_bias_effect', 0.0)))
        results['l1_frozen_bits_count_history'].append(int(l2_state.get('l1_frozen_bits_count', 0)))

        if verbose and step % 500 == 0:
            print(f"  Step {step}: L0={l0_stability:.3f}, L1={l1_stability:.3f}, "
                  f"L2={l2_state['stability_score']:.3f}, bias_eff={l2_state.get('l1_bias_effect', 0):.4f}")

    # 3. 计算最终结果
    summary = cbc.get_summary()
    # 转换为 JSON 可序列化
    summary_serializable = {}
    for k, v in summary.items():
        if isinstance(v, dict):
            summary_serializable[k] = {kk: float(vv) if isinstance(vv, (int, float, np.floating, np.integer)) else vv for kk, vv in v.items()}
        elif isinstance(v, (int, float, np.floating, np.integer)):
            summary_serializable[k] = float(v)
        else:
            summary_serializable[k] = v
    results['summary'] = summary_serializable
    results['n_l1_freeze_events'] = len(results['l1_freeze_events'])

    return results


def evaluate_hypotheses(all_results):
    """评估 Track B9 假设"""
    print(f"\n{'='*60}")
    print(" Evaluating Track B9 Hypotheses")
    print(f"{'='*60}")

    hypotheses = {
        'H50': {'pass': 0, 'total': 0, 'detail': []},
        'H51': {'pass': 0, 'total': 0, 'detail': []},
        'H52': {'pass': 0, 'total': 0, 'detail': []},
        'H53': {'pass': 0, 'total': 0, 'detail': []},
    }

    for result in all_results:
        seed = result['seed']
        summary = result['summary']

        # H50: L1 冻结 bits 对 L2 稳定性有可测量的偏置效应
        bias_effects = result['l1_bias_effect_history']
        active_biases = [b for b in bias_effects if abs(b) > 1e-6]
        if active_biases:
            mean_bias = np.mean([abs(b) for b in active_biases])
            h50_pass = H50_BIAS_EFFECT_MIN < mean_bias < H50_BIAS_EFFECT_MAX
        else:
            mean_bias = 0.0
            h50_pass = False
        hypotheses['H50']['pass'] += int(h50_pass)
        hypotheses['H50']['total'] += 1
        hypotheses['H50']['detail'].append({'seed': int(seed), 'mean_bias': float(mean_bias), 'pass': bool(h50_pass)})

        # H51: L1-L2 稳定性相关性 > 0 但 < 0.7
        l1_l2_corr = summary.get('l1_l2_correlation', None)
        if l1_l2_corr is not None:
            h51_pass = l1_l2_corr > H51_L1_L2_CORR_MIN and l1_l2_corr < H51_L1_L2_CORR_MAX
        else:
            h51_pass = False
        hypotheses['H51']['pass'] += int(h51_pass)
        hypotheses['H51']['total'] += 1
        hypotheses['H51']['detail'].append({'seed': int(seed), 'corr': float(l1_l2_corr) if l1_l2_corr is not None else None, 'pass': bool(h51_pass)})

        # H52: L2 有非零 ODI 且 not silent
        odi_history = result['l2_odi_history']
        mean_odi = np.mean(odi_history) if odi_history else 0.0
        h52_pass = mean_odi > 0.0
        hypotheses['H52']['pass'] += int(h52_pass)
        hypotheses['H52']['total'] += 1
        hypotheses['H52']['detail'].append({'seed': int(seed), 'mean_odi': float(mean_odi), 'pass': bool(h52_pass)})

        # H53: L0-L2 相关性 > L1-L2 相关性（L2 主要从 L0 派生）
        l0_l2_corr = summary.get('l0_l2_correlation', None)
        if l0_l2_corr is not None and l1_l2_corr is not None:
            h53_pass = l0_l2_corr > l1_l2_corr and l0_l2_corr > H53_L0_L2_CORR_MIN
        else:
            h53_pass = False
        hypotheses['H53']['pass'] += int(h53_pass)
        hypotheses['H53']['total'] += 1
        hypotheses['H53']['detail'].append({
            'seed': int(seed),
            'l0_l2_corr': float(l0_l2_corr) if l0_l2_corr is not None else None,
            'l1_l2_corr': float(l1_l2_corr) if l1_l2_corr is not None else None,
            'pass': bool(h53_pass)
        })

    # 打印结果
    for h_name, h_data in hypotheses.items():
        pass_rate = h_data['pass'] / h_data['total'] if h_data['total'] > 0 else 0.0
        status = "PASS" if pass_rate >= 0.5 else "FAIL"
        print(f"\n{h_name}: {status} ({h_data['pass']}/{h_data['total']} = {pass_rate:.1%})")

    return hypotheses


def convert_for_json(obj):
    """递归转换对象为 JSON 可序列化"""
    if isinstance(obj, dict):
        return {k: convert_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_for_json(v) for v in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, bool):
        return obj  # JSON supports true/false
    elif isinstance(obj, (int, float, str, type(None))):
        return obj
    else:
        return str(obj)


def main():
    print("="*60)
    print(" Phase 5 Track B9: Constraint-Based Coupling (exp_123)")
    print("="*60)
    print(f"Seeds: {N_SEEDS}, Steps: {N_STEPS}, L0_N0={N0_L0}, L2_N0={N0_L2}")

    all_results = []
    for seed in range(N_SEEDS):
        result = run_seed(seed, N_STEPS, verbose=False)
        all_results.append(result)

    # 评估结果
    hypotheses = evaluate_hypotheses(all_results)

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(PROJECT_ROOT, f"experiments/results/exp_123_b9_{timestamp}.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    save_data = {
        'hypotheses': convert_for_json(hypotheses),
        'results': convert_for_json(all_results)
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")

    print(f"\n{'='*60}")
    print(" Track B9 experiment completed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
