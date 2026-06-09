"""
exp_172 — Phase 16 Path A3: Thermodynamic Extension (Simplified Version)

科学问题：
  exp_170 证明仅有环境比特不能打破密封刚性（H16-A1 REJECTED）
  exp_171 证明仅有能量流不能打破密封刚性（H16-A2 REJECTED）
  本实验引入完整的热力学扩展（显式热耗散 + 温度概念），
  测试非平衡热力学是否能打破"死秩序"，产生 post-seal 演化。
  
核心假设：
  H16-A3 (Thermodynamic Extension 假设)：显式建模热耗散（温度、熵产生）
  能使系统在密封后继续演化，为 L2 涌现创造条件。

简化实现：
  - 不修改核心引擎，多次调用 evolver.run()
  - 在每次调用之间，随机翻转一些比特（模拟热涨落）
  - 测量密封后系统是否继续演化

用法：
  cd C:/Users/Administrator/Documents/the_theory_of_difference/11-模拟机工程实现
  python experiments/exp_172_phase16_thermodynamic_extension_v3.py
"""

import sys, os, math, json, time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver


# ============================================================
# 配置参数
# ============================================================

N = 48  # 总比特数（必须是 3 的倍数）
TOTAL_STEPS = 2000  # 总步数
N_RUNS = 3  # 每配置运行次数（测试用）
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

# 确保结果目录存在
os.makedirs(RESULTS_DIR, exist_ok=True)

# 热力学配置
THERMODYNAMIC_CONFIGS = [
    {
        'label': 'no_thermodynamics',
        'enable_thermodynamics': False,
        'T_env': 1.0,
        'heat_conductivity': 0.01,
        'flip_probability': 0.0,  # 随机翻转概率
    },
    {
        'label': 'weak_thermodynamics',
        'enable_thermodynamics': True,
        'T_env': 0.5,  # 较低环境温度
        'heat_conductivity': 0.01,  # 弱热传导
        'flip_probability': 0.01,  # 弱随机翻转
    },
    {
        'label': 'medium_thermodynamics',
        'enable_thermodynamics': True,
        'T_env': 1.0,  # 中等环境温度
        'heat_conductivity': 0.05,  # 中等热传导
        'flip_probability': 0.05,  # 中等随机翻转
    },
    {
        'label': 'strong_thermodynamics',
        'enable_thermodynamics': True,
        'T_env': 2.0,  # 较高环境温度
        'heat_conductivity': 0.1,  # 强热传导
        'flip_probability': 0.1,  # 强随机翻转
    },
]


# ============================================================
# 热力学扰动函数
# ============================================================

def apply_thermodynamic_perturbation(state: torch.Tensor, config: dict) -> torch.Tensor:
    """
    应用热力学扰动（随机翻转一些比特）
    
    模拟热涨落：高温下，比特更容易随机翻转
    """
    if not config.get('enable_thermodynamics', False):
        return state
    
    flip_prob = config.get('flip_probability', 0.0)
    if flip_prob <= 0.0:
        return state
    
    # 生成随机掩码
    mask = torch.rand(state.shape) < flip_prob
    
    # 翻转选中的比特
    state[mask] = 1.0 - state[mask]
    
    return state


# ============================================================
# 主实验函数
# ============================================================

def run_single_experiment(config: dict, run_id: int, total_runs: int) -> dict:
    """
    运行单次实验
    """
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Running {config['label']} (run {run_id+1}/{total_runs})...")
    
    start_time = time.time()
    
    # 1. 创建模拟器
    evolver = SpatialLongRangeEvolver(N, total_steps=TOTAL_STEPS, device='cpu')
    
    # 2. 运行模拟
    state = torch.randint(0, 2, (N,), dtype=torch.float32)
    
    sealed = False
    seal_step = None
    post_seal_flips = 0
    hw_history = []
    
    # 运行演化
    results = evolver.run(state, verbose=False)
    
    state = results.get('final_grid', state)
    sealed = evolver.constraints.sealed
    seal_step = evolver.constraints.seal_step if sealed else None
    
    hw_history.append(torch.sum(state).item())
    
    # 3. 如果密封，应用热力学扰动，继续演化
    if sealed:
        print(f"  Sealed at step {seal_step}, applying thermodynamic perturbation...")
        
        # 继续演化若干步，期间应用热力学扰动
        post_seal_steps = 1000
        evolver_post = SpatialLongRangeEvolver(N*N, total_steps=post_seal_steps, device='cpu')
        
        # 禁用密封（允许继续演化）
        evolver_post.constraints.sealed = False
        evolver_post.constraints.sealed_bits = set()
        
        # 应用热力学扰动
        state = apply_thermodynamic_perturbation(state, config)
        
        # 继续演化
        results_post = evolver_post.run(state, verbose=False)
        state_post = results_post.get('final_grid', state)
        
        # 统计 post-seal flips
        post_seal_flips = torch.sum(state != state_post).item()
        
        hw_history.append(torch.sum(state_post).item())
        state = state_post
    
    # 4. 收集结果
    elapsed = time.time() - start_time
    
    result = {
        'config': config['label'],
        'run_id': run_id,
        'sealed': sealed,
        'seal_step': seal_step,
        'hw_final': torch.sum(state).item(),
        'hw_history': hw_history,
        'post_seal_flips': post_seal_flips,
        'enable_thermodynamics': config.get('enable_thermodynamics', False),
        'flip_probability': config.get('flip_probability', 0.0),
        'elapsed_time': elapsed,
    }
    
    print(f"  Sealed: {sealed}, Post-seal flips: {post_seal_flips}, HW final: {result['hw_final']:.1f}")
    
    return result


def run_all_experiments():
    """
    运行所有实验配置
    """
    print("=" * 80)
    print("exp_172 — Phase 16 Path A3: Thermodynamic Extension (Simplified)")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Grid size: {N}x{N}")
    print(f"Total steps per run: {TOTAL_STEPS}")
    print(f"Runs per config: {N_RUNS}")
    print(f"Total configs: {len(THERMODYNAMIC_CONFIGS)}")
    print("=" * 80)
    
    all_results = []
    
    for config in THERMODYNAMIC_CONFIGS:
        print(f"\n### Config: {config['label']} ###")
        
        for run_id in range(N_RUNS):
            result = run_single_experiment(config, run_id, N_RUNS)
            all_results.append(result)
    
    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = os.path.join(RESULTS_DIR, f"exp_172_results_{timestamp}.json")
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {result_file}")
    
    # 汇总统计
    print("\n" + "=" * 80)
    print("Summary Statistics")
    print("=" * 80)
    
    for config in THERMODYNAMIC_CONFIGS:
        config_results = [r for r in all_results if r['config'] == config['label']]
        
        seal_rate = sum(1 for r in config_results if r['sealed']) / len(config_results)
        avg_post_seal_flips = np.mean([r['post_seal_flips'] for r in config_results])
        avg_hw_final = np.mean([r['hw_final'] for r in config_results])
        
        print(f"\n{config['label']}:")
        print(f"  Seal rate: {seal_rate*100:.1f}%")
        print(f"  Avg post-seal flips: {avg_post_seal_flips:.4f}")
        print(f"  Avg HW final: {avg_hw_final:.1f}")
    
    return all_results, result_file


if __name__ == '__main__':
    results, result_file = run_all_experiments()
    
    print("\n" + "=" * 80)
    print("Experiment completed!")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
