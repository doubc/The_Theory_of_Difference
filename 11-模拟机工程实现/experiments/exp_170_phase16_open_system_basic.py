"""
exp_170 — Phase 16 Path A1: Basic Open System (Environment Bits Only)

科学问题：
  Phase 15 证明差异论在封闭系统假设下只能产生单层秩序（0% L2涌现）。
  开放系统扩展引入环境耦合，允许系统与外界交换信息/能量。
  
核心假设：
  H16-A1 (Environment Bits 假设)：环境比特的随机涨落能为已密封的 L0 提供持续扰动，
  使系统在密封后继续微小演化，为 L2 涌现创造条件。

实验设计：
  - 对比实验：封闭系统 vs 开放系统（仅环境比特，无能量流）
  - 测量指标：
    1. L0 密封后是否继续演化（Hamming weight 变化）
    2. 密封后比特翻转率
    3. 环境耦合强度对演化的影响
    4. 系统能量变化（如果有能量流）

理论意义：
  如果环境比特能使 L0 在密封后继续演化，说明开放系统扩展是打破"死秩序"的有效途径。
  这为后续实验（能量流、热力学扩展）奠定基础。

实现方法：
  使用 step_callback 机制，在每次演化步骤后添加环境耦合扰动。
  环境比特的随机翻转会影响系统边界比特，产生持续涨落。

用法：
  cd C:/Users/Administrator/Documents/the_theory_of_difference/11-模拟机工程实现
  python experiments/exp_170_phase16_open_system_basic.py
"""

import sys, os, math, json, time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver
from engine.open_system_extension import OpenSystemConfig, EnvironmentBits


# ============================================================
# 配置参数
# ============================================================
N = 48  # 网格大小
TOTAL_STEPS = 2000  # 总步数
N_RUNS = 3  # 每配置运行次数（测试用，正式实验用5-10）
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

# 确保结果目录存在
os.makedirs(RESULTS_DIR, exist_ok=True)

# 环境耦合配置
ENV_CONFIGS = [
    {
        'label': 'closed_system',
        'enable_environment': False,
        'env_bit_ratio': 0.0,
        'env_flip_prob': 0.0,
        'coupling_strength': 0.0,
    },
    {
        'label': 'open_weak_coupling',
        'enable_environment': True,
        'env_bit_ratio': 0.2,
        'env_flip_prob': 0.05,
        'coupling_strength': 0.3,
    },
    {
        'label': 'open_medium_coupling',
        'enable_environment': True,
        'env_bit_ratio': 0.2,
        'env_flip_prob': 0.1,
        'coupling_strength': 0.5,
    },
    {
        'label': 'open_strong_coupling',
        'enable_environment': True,
        'env_bit_ratio': 0.3,
        'env_flip_prob': 0.15,
        'coupling_strength': 0.8,
    },
]

print("=" * 80)
print("exp_170 — Phase 16 Path A1: Basic Open System (Environment Bits Only)")
print("=" * 80)
print(f"Grid size: {N}x{N}")
print(f"Total steps: {TOTAL_STEPS}")
print(f"Runs per config: {N_RUNS}")
print(f"Configs: {len(ENV_CONFIGS)}")
print(f"Total experiments: {len(ENV_CONFIGS) * N_RUNS}")
print("=" * 80)


# ============================================================
# 环境耦合回调
# ============================================================
def make_environment_callback(config: dict):
    """
    创建环境耦合 step_callback。
    
    在每次演化步骤后，环境比特随机翻转，并通过耦合强度影响系统边界比特。
    
    参数：
        config: 环境配置字典
    
    返回：
        step_callback 函数，或 None（如果是封闭系统）
    """
    if not config['enable_environment']:
        return None
    
    # 创建环境比特
    env_config = OpenSystemConfig(
        enable_environment_bits=True,
        env_bit_ratio=config['env_bit_ratio'],
        env_flip_prob=config['env_flip_prob'],
        coupling_strength=config['coupling_strength'],
        enable_energy_flow=False,  # exp_170 仅测试环境比特
        enable_dynamic_sealing=False,
    )
    
    # 环境比特在 callback 外部创建，避免重复初始化
    env_bits = None
    
    def environment_callback(step: int, state: torch.Tensor, snapshot, constraints):
        nonlocal env_bits
        
        # 初始化环境比特（首次调用）
        if env_bits is None:
            grid_shape = state.shape
            env_bits = EnvironmentBits(grid_shape, env_config)
            print(f"    [Environment] Initialized: {env_bits.num_env_bits} bits")
        
        # 提取系统边界比特
        boundary_bits = _extract_boundary_bits(state)
        
        # 更新环境比特，获取耦合信号
        coupling_signal = env_bits.step(boundary_bits)
        
        # 将环境耦合应用到系统边界
        _apply_coupling_to_boundary(state, coupling_signal, env_config.coupling_strength)
        
        # 记录环境能量（用于分析）
        if step % 100 == 0:
            print(f"    [Environment] Step {step}: env_energy={env_bits.energy:.1f}, "
                  f"coupling_strength={torch.norm(coupling_signal):.2f}")
    
    return environment_callback


def _extract_boundary_bits(state: torch.Tensor) -> torch.Tensor:
    """提取系统边界比特"""
    if len(state.shape) == 2:
        h, w = state.shape
        boundary = torch.cat([
            state[0, :],  # top
            state[h-1, :],  # bottom
            state[1:h-1, 0],  # left (excluding corners)
            state[1:h-1, w-1]  # right (excluding corners)
        ])
        return boundary
    else:
        # 对于1D或其他形状，返回整个状态
        return state.flatten()


def _apply_coupling_to_boundary(
    state: torch.Tensor, 
    coupling_signal: torch.Tensor,
    coupling_strength: float
):
    """将环境耦合信号应用到系统边界比特"""
    if len(state.shape) == 2:
        h, w = state.shape
        
        # 耦合信号长度可能不匹配，取最小长度
        min_len = min(len(coupling_signal), 2*h + 2*(w-2))
        
        idx = 0
        
        # Top boundary
        n_top = min(w, min_len - idx)
        if n_top > 0:
            noise = torch.randn(n_top) * coupling_strength * 0.01
            state[0, :n_top] = torch.clamp(state[0, :n_top] + noise, 0, 1)
            idx += n_top
        
        # Bottom boundary
        if idx < min_len:
            n_bottom = min(w, min_len - idx)
            if n_bottom > 0:
                noise = torch.randn(n_bottom) * coupling_strength * 0.01
                state[h-1, :n_bottom] = torch.clamp(state[h-1, :n_bottom] + noise, 0, 1)
                idx += n_bottom
        
        # Left boundary
        if idx < min_len:
            n_left = min(h-2, min_len - idx)
            if n_left > 0:
                noise = torch.randn(n_left) * coupling_strength * 0.01
                state[1:1+n_left, 0] = torch.clamp(state[1:1+n_left, 0] + noise, 0, 1)
                idx += n_left
        
        # Right boundary
        if idx < min_len:
            n_right = min(h-2, min_len - idx)
            if n_right > 0:
                noise = torch.randn(n_right) * coupling_strength * 0.01
                state[1:1+n_right, -1] = torch.clamp(state[1:1+n_right, -1] + noise, 0, 1)


# ============================================================
# 实验函数
# ============================================================
def run_single_experiment(config: dict, seed: int, run_idx: int) -> dict:
    """
    运行单次实验。
    
    参数：
        config: 配置字典
        seed: 随机种子
        run_idx: 运行索引（用于日志）
    
    返回：
        实验结果字典
    """
    np.random.seed(seed)
    torch.manual_seed(seed)
    
    print(f"  Run {run_idx+1} (seed={seed})...", end=' ', flush=True)
    start_time = time.time()
    
    # 创建模拟器（total_steps 在 __init__ 中设置）
    evolver = SpatialLongRangeEvolver(N=N, device='cpu', total_steps=TOTAL_STEPS)
    
    # 创建环境回调（如果是开放系统）
    step_callback = make_environment_callback(config)
    
    # 运行模拟
    results = evolver.run(
        verbose=False,
        step_callback=step_callback
    )
    
    elapsed = time.time() - start_time
    print(f"done ({elapsed:.1f}s)")
    
    # 提取关键指标
    sealed = results.get('sealed', False)
    sealed_bits = results.get('sealed_bits', 0)
    sealed_ratio = results.get('sealed_ratio', 0.0)
    hamming_weight_history = results.get('hamming_weight_history', [])
    
    hw_final = hamming_weight_history[-1] if hamming_weight_history else -1
    
    # 分析密封后演化
    post_seal_flips = 0.0
    if sealed and len(hamming_weight_history) > 100:
        # 假设密封发生在约 20% 的步数
        seal_point = len(hamming_weight_history) // 5
        post_seal_hw = hamming_weight_history[seal_point:]
        # 计算密封后 Hamming weight 的标准差（衡量波动）
        if len(post_seal_hw) > 10:
            # 转换为 float tensor 再计算 std
            hw_tensor = torch.tensor(post_seal_hw, dtype=torch.float32)
            post_seal_flips = float(hw_tensor.std().item())
    
    return {
        'config': config['label'],
        'seed': seed,
        'run_idx': run_idx,
        'sealed': sealed,
        'sealed_bits': sealed_bits,
        'sealed_ratio': sealed_ratio,
        'hw_final': hw_final,
        'hw_history_len': len(hamming_weight_history),
        'post_seal_flips_std': post_seal_flips,
        'elapsed_time': elapsed,
    }


def run_all_experiments() -> list:
    """
    运行所有实验配置。
    
    返回：
        所有实验结果的列表
    """
    all_results = []
    
    for config_idx, config in enumerate(ENV_CONFIGS):
        print(f"\n[{config_idx+1}/{len(ENV_CONFIGS)}] Config: {config['label']}")
        
        for run in range(N_RUNS):
            seed = config_idx * 1000 + run
            
            try:
                result = run_single_experiment(config, seed, run)
                all_results.append(result)
            except Exception as e:
                print(f"  ERROR: {e}")
                all_results.append({
                    'config': config['label'],
                    'seed': seed,
                    'run_idx': run,
                    'error': str(e),
                })
    
    return all_results


def analyze_results(all_results: list) -> dict:
    """
    分析实验结果，生成统计报告。
    
    参数：
        all_results: 所有实验结果的列表
    
    返回：
        统计分析字典
    """
    print("\n" + "=" * 80)
    print("Analysis Results")
    print("=" * 80)
    
    analysis = {}
    
    for config in ENV_CONFIGS:
        label = config['label']
        config_results = [r for r in all_results if r.get('config') == label and 'error' not in r]
        
        if not config_results:
            print(f"\n{label}: No valid results")
            continue
        
        # 统计指标
        n_runs = len(config_results)
        n_sealed = sum(1 for r in config_results if r.get('sealed', False))
        seal_rate = n_sealed / n_runs if n_runs > 0 else 0
        
        hw_finals = [r.get('hw_final', -1) for r in config_results if r.get('hw_final', -1) > 0]
        avg_hw_final = np.mean(hw_finals) if hw_finals else -1
        
        post_seal_flips = [r.get('post_seal_flips_std', 0) for r in config_results]
        avg_post_seal_flips = np.mean(post_seal_flips) if post_seal_flips else 0
        
        # 打印结果
        print(f"\n{label}:")
        print(f"  Valid runs: {n_runs}/{N_RUNS}")
        print(f"  Seal rate: {n_sealed}/{n_runs} = {seal_rate:.1%}")
        print(f"  Avg HW final: {avg_hw_final:.1f}")
        print(f"  Avg post-seal flips (std): {avg_post_seal_flips:.4f}")
        
        if label != 'closed_system':
            print(f"  Note: Environment coupling enabled (strength={config['coupling_strength']})")
        
        # 保存结果
        analysis[label] = {
            'n_runs': n_runs,
            'n_sealed': n_sealed,
            'seal_rate': seal_rate,
            'avg_hw_final': float(avg_hw_final),
            'avg_post_seal_flips_std': float(avg_post_seal_flips),
        }
    
    return analysis


# ============================================================
# 主程序
# ============================================================
def main():
    print("\nStarting experiment exp_170 (Phase 16 Path A1)...")
    print("Testing basic open system with environment bits...\n")
    start_time = time.time()
    
    # 运行所有实验
    all_results = run_all_experiments()
    
    # 分析结果
    analysis = analyze_results(all_results)
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(
        RESULTS_DIR,
        f"exp_170_results_{timestamp}.json"
    )
    
    output = {
        'experiment': 'exp_170_phase16_open_system_basic',
        'timestamp': timestamp,
        'phase': 'Phase 16 Path A1',
        'hypothesis': 'H16-A1: Environment bits enable post-seal evolution',
        'configs': ENV_CONFIGS,
        'n_runs_per_config': N_RUNS,
        'total_steps': TOTAL_STEPS,
        'results': all_results,
        'analysis': analysis,
        'theory_ref': 'docs/phase16_theoretical_analysis_OpenSystem_v1.md',
    }
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    total_elapsed = time.time() - start_time
    print(f"\n{'=' * 80}")
    print(f"Experiment complete! Total time: {total_elapsed:.1f}s")
    print(f"Results saved to: {result_file}")
    print(f"{'=' * 80}\n")
    
    # 打印简要结论
    print("Preliminary Conclusions:")
    print("-" * 40)
    closed = analysis.get('closed_system', {})
    open_weak = analysis.get('open_weak_coupling', {})
    open_medium = analysis.get('open_medium_coupling', {})
    
    if closed and open_weak:
        print(f"Closed system seal rate: {closed.get('seal_rate', 0):.1%}")
        print(f"Open (weak) seal rate: {open_weak.get('seal_rate', 0):.1%}")
        print(f"Open (weak) post-seal flips: {open_weak.get('avg_post_seal_flips_std', 0):.4f}")
        
        if open_weak.get('avg_post_seal_flips_std', 0) > 0.01:
            print("✓ Environment bits DO cause post-seal evolution!")
            print("  → H16-A1 supported (preliminary)")
        else:
            print("✗ Environment bits do NOT cause significant post-seal evolution")
            print("  → H16-A1 not supported (need stronger coupling or energy flow)")
    
    print(f"{'=' * 80}\n")
    
    return output


if __name__ == "__main__":
    main()
