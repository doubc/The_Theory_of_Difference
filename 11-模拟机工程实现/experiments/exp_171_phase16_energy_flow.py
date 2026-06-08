"""
exp_171 — Phase 16 Path A2: Energy Flow Extension

科学问题：
  exp_170 证明仅有环境比特（无能量流）不能使系统在密封后继续演化（H16-A1 REJECTED）。
  本实验引入"能量流"概念，测试能量注入是否能打破密封的刚性，产生 post-seal 演化。
  
核心假设：
  H16-A2 (Energy Flow 假设)：能量流（系统与外界交换能量）能使 L0 在密封后继续演化，
  为 L2 涌现创造条件。

实验设计：
  - 对比实验：无能量流 vs 有能量流（不同注入率）
  - 测量指标：
    1. L0 密封后 Hamming weight 是否持续变化
    2. 系统能量变化（注入 vs 耗散）
    3. 能量流强度对 post-seal 演化的影响
    4. 是否出现 L2 涌现（跨层结构传递）

理论意义：
  如果能量流能使密封系统重新激活，说明非平衡态热力学是打破"死秩序"的关键。
  这为实现多层级涌现提供了理论基础。

实现方法：
  1. 引入能量概念：每次 bit flip 消耗 1 单位能量
  2. 环境向系统注入能量（维持非平衡态）
  3. 密封的层级释放能量（类似"代谢"）
  4. 使用 step_callback 在每个演化步骤更新能量

用法：
  cd C:/Users/Administrator/Documents/the_theory_of_difference/11-模拟机工程实现
  python experiments/exp_171_phase16_energy_flow.py
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

# 能量流配置
ENERGY_CONFIGS = [
    {
        'label': 'no_energy_flow',
        'enable_environment': True,
        'env_bit_ratio': 0.2,
        'env_flip_prob': 0.1,
        'coupling_strength': 0.5,
        'enable_energy_flow': False,
        'energy_injection_rate': 0.0,
        'energy_dissipation_rate': 0.01,
        'initial_energy': 100.0,
    },
    {
        'label': 'weak_energy_flow',
        'enable_environment': True,
        'env_bit_ratio': 0.2,
        'env_flip_prob': 0.1,
        'coupling_strength': 0.5,
        'enable_energy_flow': True,
        'energy_injection_rate': 0.1,  # 每步注入 0.1 能量
        'energy_dissipation_rate': 0.01,
        'initial_energy': 100.0,
    },
    {
        'label': 'medium_energy_flow',
        'enable_environment': True,
        'env_bit_ratio': 0.2,
        'env_flip_prob': 0.1,
        'coupling_strength': 0.5,
        'enable_energy_flow': True,
        'energy_injection_rate': 0.5,  # 每步注入 0.5 能量
        'energy_dissipation_rate': 0.01,
        'initial_energy': 100.0,
    },
    {
        'label': 'strong_energy_flow',
        'enable_environment': True,
        'env_bit_ratio': 0.2,
        'env_flip_prob': 0.1,
        'coupling_strength': 0.5,
        'enable_energy_flow': True,
        'energy_injection_rate': 1.0,  # 每步注入 1.0 能量
        'energy_dissipation_rate': 0.01,
        'initial_energy': 100.0,
    },
]

print("=" * 80)
print("exp_171 — Phase 16 Path A2: Energy Flow Extension")
print("=" * 80)
print(f"Grid size: {N}x{N}")
print(f"Total steps: {TOTAL_STEPS}")
print(f"Runs per config: {N_RUNS}")
print(f"Configs: {len(ENERGY_CONFIGS)}")
print(f"Total experiments: {len(ENERGY_CONFIGS) * N_RUNS}")
print("=" * 80)


# ============================================================
# 能量流管理
# ============================================================
class EnergyFlowManager:
    """
    管理系统的能量流。
    
    属性：
        energy: 当前系统能量
        injection_rate: 能量注入率（每步）
        dissipation_rate: 能量耗散率
        enable: 是否启用能量流
    """
    
    def __init__(self, config: dict):
        """
        初始化能量流管理器。
        
        参数：
            config: 能量流配置字典
        """
        self.enable = config.get('enable_energy_flow', False)
        self.injection_rate = config.get('energy_injection_rate', 0.0)
        self.dissipation_rate = config.get('energy_dissipation_rate', 0.01)
        self.energy = config.get('initial_energy', 100.0)
        self.initial_energy = self.energy
        self.step_count = 0
        self.energy_history = []
        
    def step(self, state: torch.Tensor, flips: int) -> float:
        """
        执行一步能量更新。
        
        参数：
            state: 当前系统状态
            flips: 本次步骤发生的 bit 翻转次数
            
        返回：
            当前能量值
        """
        if not self.enable:
            return self.energy
        
        # 能量耗散：每次翻转消耗 1 单位能量
        energy_consumed = flips * 1.0
        self.energy -= energy_consumed
        
        # 能量注入：环境向系统注入能量
        self.energy += self.injection_rate
        
        # 能量耗散（热耗散）
        self.energy *= (1.0 - self.dissipation_rate)
        
        # 防止能量为负
        self.energy = max(0.0, self.energy)
        
        # 记录历史
        self.step_count += 1
        self.energy_history.append(self.energy)
        
        return self.energy
    
    def get_statistics(self) -> dict:
        """
        获取能量流统计信息。
        
        返回：
            统计字典
        """
        if not self.energy_history:
            return {}
        
        return {
            'initial_energy': self.initial_energy,
            'final_energy': self.energy,
            'min_energy': min(self.energy_history),
            'max_energy': max(self.energy_history),
            'avg_energy': np.mean(self.energy_history),
            'energy_history_len': len(self.energy_history),
        }


# ============================================================
# 能量流回调
# ============================================================
def make_energy_flow_callback(config: dict):
    """
    创建能量流 step_callback。
    
    在每次演化步骤后更新系统能量，并根据能量水平影响 bit flip 概率。
    
    参数：
        config: 能量流配置字典
    
    返回：
        step_callback 函数，或 None（如果未启用能量流）
    """
    if not config.get('enable_energy_flow', False):
        return None
    
    # 创建能量流管理器
    energy_manager = EnergyFlowManager(config)
    
    # 创建环境比特（如果启用）
    env_bits = None
    if config.get('enable_environment', False):
        env_config = OpenSystemConfig(
            enable_environment_bits=True,
            env_bit_ratio=config.get('env_bit_ratio', 0.2),
            env_flip_prob=config.get('env_flip_prob', 0.1),
            coupling_strength=config.get('coupling_strength', 0.5),
            enable_energy_flow=False,  # 在 EnergyFlowManager 中处理
            enable_dynamic_sealing=False,
        )
    
    def energy_flow_callback(step: int, state: torch.Tensor, snapshot, constraints):
        nonlocal env_bits
        
        # 初始化环境比特（首次调用）
        if config.get('enable_environment', False) and env_bits is None:
            grid_shape = state.shape
            env_bits = EnvironmentBits(grid_shape, env_config)
            print(f"    [EnergyFlow] Environment bits initialized: {env_bits.num_env_bits} bits")
        
        # 计算本次步骤的 bit 翻转次数（通过对比 snapshot 或 state）
        flips = _count_flips(state, snapshot)
        
        # 更新能量
        current_energy = energy_manager.step(state, flips)
        
        # 如果能量充足，允许更多翻转（降低翻转阈值）
        if current_energy > 50.0:
            # 能量充足时，降低 constraints 的阈值（允许更多翻转）
            if hasattr(constraints, 'sealing_threshold'):
                constraints.sealing_threshold *= 0.995  # 缓慢降低阈值
        
        # 环境耦合（如果启用）
        if env_bits is not None:
            boundary_bits = _extract_boundary_bits(state)
            coupling_signal = env_bits.step(boundary_bits)
            _apply_coupling_to_boundary(state, coupling_signal, config.get('coupling_strength', 0.5))
        
        # 定期打印能量信息
        if step % 100 == 0:
            threshold = getattr(constraints, 'sealing_threshold', 'N/A')
            print(f"    [EnergyFlow] Step {step}: energy={current_energy:.1f}, "
                  f"flips={flips}, threshold={threshold}")
    
    # 保存 energy_manager 引用，方便后续分析
    energy_flow_callback.energy_manager = energy_manager
    
    return energy_flow_callback


def _count_flips(state: torch.Tensor, snapshot) -> int:
    """
    计算本次步骤的 bit 翻转次数。
    
    参数：
        state: 当前状态
        snapshot: 上一步的快照，或 None
    
    返回：
        翻转次数
    """
    # 如果 snapshot 没有记录上一步状态，返回 0
    if snapshot is None:
        return 0
    
    # 尝试从 snapshot 中提取上一步状态
    if isinstance(snapshot, dict) and 'state' in snapshot:
        prev_state = snapshot['state']
        if isinstance(prev_state, torch.Tensor) and prev_state.shape == state.shape:
            return int((prev_state != state).sum().item())
    
    return 0


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
    
    # 创建能量流回调（如果启用）
    step_callback = make_energy_flow_callback(config)
    
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
    post_seal_hw_change = 0.0
    if sealed and len(hamming_weight_history) > 100:
        # 假设密封发生在约 20% 的步数
        seal_point = len(hamming_weight_history) // 5
        post_seal_hw = hamming_weight_history[seal_point:]
        
        # 计算密封后 Hamming weight 的标准差（衡量波动）
        if len(post_seal_hw) > 10:
            hw_tensor = torch.tensor(post_seal_hw, dtype=torch.float32)
            post_seal_flips = float(hw_tensor.std().item())
            
            # 计算密封后 Hamming weight 的变化趋势（线性回归斜率）
            x = torch.arange(len(post_seal_hw), dtype=torch.float32)
            y = hw_tensor
            if len(x) > 1:
                slope = ((x * y).mean() - x.mean() * y.mean()) / (x.pow(2).mean() - x.mean().pow(2))
                post_seal_hw_change = float(slope.item())
    
    # 提取能量流统计（如果启用）
    energy_stats = {}
    if step_callback is not None and hasattr(step_callback, 'energy_manager'):
        energy_stats = step_callback.energy_manager.get_statistics()
    
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
        'post_seal_hw_change': post_seal_hw_change,
        'energy_stats': energy_stats,
        'elapsed_time': elapsed,
    }


def run_all_experiments() -> list:
    """
    运行所有实验配置。
    
    返回：
        所有实验结果的列表
    """
    all_results = []
    
    for config_idx, config in enumerate(ENERGY_CONFIGS):
        print(f"\n[{config_idx+1}/{len(ENERGY_CONFIGS)}] Config: {config['label']}")
        
        for run in range(N_RUNS):
            seed = config_idx * 1000 + run
            
            try:
                result = run_single_experiment(config, seed, run)
                all_results.append(result)
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()
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
    
    for config in ENERGY_CONFIGS:
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
        
        post_seal_hw_change = [r.get('post_seal_hw_change', 0) for r in config_results]
        avg_hw_change = np.mean(post_seal_hw_change) if post_seal_hw_change else 0
        
        # 能量统计
        energy_stats_list = [r.get('energy_stats', {}) for r in config_results if r.get('energy_stats')]
        avg_final_energy = np.mean([s.get('final_energy', 0) for s in energy_stats_list]) if energy_stats_list else 0
        
        # 打印结果
        print(f"\n{label}:")
        print(f"  Valid runs: {n_runs}/{N_RUNS}")
        print(f"  Seal rate: {n_sealed}/{n_runs} = {seal_rate:.1%}")
        print(f"  Avg HW final: {avg_hw_final:.1f}")
        print(f"  Avg post-seal flips (std): {avg_post_seal_flips:.4f}")
        print(f"  Avg post-seal HW change (slope): {avg_hw_change:.4f}")
        
        if config.get('enable_energy_flow', False):
            print(f"  Avg final energy: {avg_final_energy:.1f}")
            print(f"  Note: Energy flow enabled (injection_rate={config['energy_injection_rate']})")
        
        # 保存结果
        analysis[label] = {
            'n_runs': n_runs,
            'n_sealed': n_sealed,
            'seal_rate': seal_rate,
            'avg_hw_final': float(avg_hw_final),
            'avg_post_seal_flips_std': float(avg_post_seal_flips),
            'avg_post_seal_hw_change': float(avg_hw_change),
            'avg_final_energy': float(avg_final_energy),
        }
    
    return analysis


# ============================================================
# 主程序
# ============================================================
def main():
    print("\nStarting experiment exp_171 (Phase 16 Path A2)...")
    print("Testing energy flow extension...\n")
    start_time = time.time()
    
    # 运行所有实验
    all_results = run_all_experiments()
    
    # 分析结果
    analysis = analyze_results(all_results)
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(
        RESULTS_DIR,
        f"exp_171_results_{timestamp}.json"
    )
    
    output = {
        'experiment': 'exp_171_phase16_energy_flow',
        'timestamp': timestamp,
        'phase': 'Phase 16 Path A2',
        'hypothesis': 'H16-A2: Energy flow enables post-seal evolution',
        'configs': ENERGY_CONFIGS,
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
    no_energy = analysis.get('no_energy_flow', {})
    weak_energy = analysis.get('weak_energy_flow', {})
    medium_energy = analysis.get('medium_energy_flow', {})
    strong_energy = analysis.get('strong_energy_flow', {})
    
    if no_energy:
        print(f"No energy flow:")
        print(f"  Seal rate: {no_energy.get('seal_rate', 0):.1%}")
        print(f"  Post-seal flips: {no_energy.get('avg_post_seal_flips_std', 0):.4f}")
    
    if weak_energy:
        print(f"\nWeak energy flow:")
        print(f"  Seal rate: {weak_energy.get('seal_rate', 0):.1%}")
        print(f"  Post-seal flips: {weak_energy.get('avg_post_seal_flips_std', 0):.4f}")
        print(f"  Post-seal HW change: {weak_energy.get('avg_post_seal_hw_change', 0):.4f}")
        print(f"  Final energy: {weak_energy.get('avg_final_energy', 0):.1f}")
    
    if medium_energy:
        print(f"\nMedium energy flow:")
        print(f"  Seal rate: {medium_energy.get('seal_rate', 0):.1%}")
        print(f"  Post-seal flips: {medium_energy.get('avg_post_seal_flips_std', 0):.4f}")
        print(f"  Post-seal HW change: {medium_energy.get('avg_post_seal_hw_change', 0):.4f}")
        print(f"  Final energy: {medium_energy.get('avg_final_energy', 0):.1f}")
    
    if strong_energy:
        print(f"\nStrong energy flow:")
        print(f"  Seal rate: {strong_energy.get('seal_rate', 0):.1%}")
        print(f"  Post-seal flips: {strong_energy.get('avg_post_seal_flips_std', 0):.4f}")
        print(f"  Post-seal HW change: {strong_energy.get('avg_post_seal_hw_change', 0):.4f}")
        print(f"  Final energy: {strong_energy.get('avg_final_energy', 0):.1f}")
    
    # 判断假设
    print(f"\n{'=' * 80}")
    print("Hypothesis Test:")
    print("-" * 40)
    
    # 比较有无能量流的 post-seal 演化
    if no_energy and (weak_energy or medium_energy or strong_energy):
        no_energy_flips = no_energy.get('avg_post_seal_flips_std', 0)
        
        # 检查是否有能量流配置的 post-seal flips 显著更高
        for label, data in [('weak', weak_energy), ('medium', medium_energy), ('strong', strong_energy)]:
            if data:
                energy_flips = data.get('avg_post_seal_flips_std', 0)
                energy_change = data.get('avg_post_seal_hw_change', 0)
                
                if energy_flips > no_energy_flips * 2 and abs(energy_change) > 0.01:
                    print(f"[PASS] {label} energy flow DOES cause post-seal evolution!")
                    print(f"  -> H16-A2 supported (preliminary)")
                    break
        else:
            print("[FAIL] Energy flow does NOT significantly increase post-seal evolution")
            print("  -> H16-A2 not supported (need stronger flow or different mechanism)")
    
    print(f"{'=' * 80}\n")
    
    return output


if __name__ == "__main__":
    main()
