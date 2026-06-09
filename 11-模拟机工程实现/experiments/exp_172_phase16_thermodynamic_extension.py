"""
exp_172 — Phase 16 Path A3: Thermodynamic Extension

科学问题：
  exp_170 证明仅有环境比特不能打破密封刚性（H16-A1 REJECTED）
  exp_171 证明仅有能量流不能打破密封刚性（H16-A2 REJECTED）
  本实验引入完整的热力学扩展（显式热耗散 + 温度概念），
  测试非平衡热力学是否能打破"死秩序"，产生 post-seal 演化。
  
核心假设：
  H16-A3 (Thermodynamic Extension 假设)：显式建模热耗散（温度、熵产生）
  能使系统在密封后继续演化，为 L2 涌现创造条件。

实验设计：
  - 对比实验：无热力学扩展 vs 有热力学扩展（不同温度、耗散率）
  - 测量指标：
    1. L0 密封后 Hamming weight 是否持续变化
    2. 系统温度、熵产生率变化
    3. 热力学参数对 post-seal 演化的影响
    4. 是否出现 L2 涌现（跨层结构传递）

理论意义：
  如果热力学扩展能打破密封刚性，说明非平衡态热力学（温度、熵流）
  是生命/意识等多层级系统涌现的关键。
  这为差异论提供了物理基础。

实现方法：
  1. 引入温度 T：系统平均动能（bit flip 频率的度量）
  2. 引入熵 S：系统无序度的度量（基于 Hamming weight 分布）
  3. 热耗散：dQ/dt = -γ * (T - T_env) （γ=热传导系数，T_env=环境温度）
  4. 熵产生：dS/dt = dS_internal/dt + dS_external/dt
  5. 使用 step_callback 在每个演化步骤更新热力学变量

用法：
  cd C:/Users/Administrator/Documents/the_theory_of_difference/11-模拟机工程实现
  python experiments/exp_172_phase16_thermodynamic_extension.py
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
# 热力学扩展核心类
# ============================================================

class ThermodynamicExtension:
    """
    热力学扩展：显式建模温度、熵、热耗散
    
    核心思想：
    - 系统是开放的热力学系统，与环境交换热量
    - 温度 T 衡量系统平均动能（bit flip 倾向）
    - 熵 S 衡量系统无序度
    - 热耗散使系统趋向环境温度
    """
    
    def __init__(self, config):
        self.config = config
        self.enable = config.get('enable_thermodynamics', False)
        self.T_env = config.get('T_env', 1.0)  # 环境温度
        self.heat_conductivity = config.get('heat_conductivity', 0.01)  # 热传导系数
        self.initial_T = config.get('initial_T', 1.0)  # 初始温度
        
        # 运行时状态
        self.T_system = self.initial_T  # 系统温度
        self.entropy = 0.0  # 系统熵
        self.heat_dissipation_rate = 0.0  # 热耗散率
        self.entropy_production_rate = 0.0  # 熵产生率
        
        # 历史记录
        self.T_history = []
        self.entropy_history = []
        self.heat_history = []
        
    def compute_temperature(self, grid, step):
        """
        计算系统温度 T
        
        方法：基于 bit flip 频率（动态度量）
        T ∝ 平均翻转概率 ∝ 系统活跃度
        """
        if not self.enable:
            return 0.0
        
        # 简化：用 Hamming weight 变化率近似温度
        # 在真实实现中，应该追踪每个 bit 的 flip 历史
        hw = torch.sum(grid).item()
        hw_expected = grid.numel() / 2
        deviation = abs(hw - hw_expected) / hw_expected
        
        # 温度与偏离度成反比（越有序，温度越低）
        T = 1.0 / (1.0 + deviation)
        
        return T
    
    def compute_entropy(self, grid):
        """
        计算系统熵 S
        
        方法：基于 Hamming weight 分布的 Shannon 熵
        S = -Σ p_i * log(p_i)
        """
        if not self.enable:
            return 0.0
        
        # 简化：用网格的 Hamming weight 分布计算熵
        # 真实实现应该统计所有可能状态的概率分布
        hw = torch.sum(grid).item()
        N = grid.numel()
        
        # 二元系统：p0 = (N-hw)/N, p1 = hw/N
        p0 = (N - hw) / N
        p1 = hw / N
        
        # Shannon 熵
        S = 0.0
        if p0 > 0:
            S -= p0 * math.log(p0)
        if p1 > 0:
            S -= p1 * math.log(p1)
        
        return S
    
    def compute_heat_dissipation(self):
        """
        计算热耗散率 dQ/dt
        
        公式：dQ/dt = -γ * (T_system - T_env)
        """
        if not self.enable:
            return 0.0
        
        dQ_dt = -self.heat_conductivity * (self.T_system - self.T_env)
        return dQ_dt
    
    def compute_entropy_production(self, grid, step):
        """
        计算熵产生率 dS/dt
        
        公式：dS/dt = dS_internal/dt + dS_external/dt
        - dS_internal/dt：内部熵产生（不可逆过程）
        - dS_external/dt：外部熵流（与环境交换）
        """
        if not self.enable:
            return 0.0
        
        # 简化：用熵变化率近似熵产生率
        S_new = self.compute_entropy(grid)
        dS_dt = S_new - self.entropy
        
        # 外部熵流（热耗散导致）
        dQ_dt = self.compute_heat_dissipation()
        dS_external = dQ_dt / self.T_env if self.T_env > 0 else 0.0
        
        # 总熵产生
        dS_total = dS_dt + dS_external
        
        return dS_total
    
    def update(self, grid, step):
        """
        在每个演化步骤更新热力学状态
        """
        if not self.enable:
            return
        
        # 1. 计算温度
        self.T_system = self.compute_temperature(grid, step)
        self.T_history.append(self.T_system)
        
        # 2. 计算熵
        self.entropy = self.compute_entropy(grid)
        self.entropy_history.append(self.entropy)
        
        # 3. 计算热耗散
        self.heat_dissipation_rate = self.compute_heat_dissipation()
        self.heat_history.append(self.heat_dissipation_rate)
        
        # 4. 计算熵产生率
        self.entropy_production_rate = self.compute_entropy_production(grid, step)
        
    def get_thermodynamic_state(self):
        """
        返回当前热力学状态（用于记录）
        """
        return {
            'T_system': self.T_system,
            'T_env': self.T_env,
            'entropy': self.entropy,
            'heat_dissipation_rate': self.heat_dissipation_rate,
            'entropy_production_rate': self.entropy_production_rate,
        }


# ============================================================
# 配置参数
# ============================================================

N = 48  # 网格大小
TOTAL_STEPS = 2000  # 总步数
N_RUNS = 3  # 每配置运行次数（测试用，正式实验用5-10）
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

# 确保结果目录存在
os.makedirs(RESULTS_DIR, exist_ok=True)

# 热力学配置
THERMODYNAMIC_CONFIGS = [
    {
        'label': 'no_thermodynamics',
        'enable_environment': True,
        'env_bit_ratio': 0.2,
        'env_flip_prob': 0.1,
        'coupling_strength': 0.5,
        'enable_energy_flow': False,
        'enable_thermodynamics': False,
        'T_env': 1.0,
        'heat_conductivity': 0.01,
        'initial_T': 1.0,
    },
    {
        'label': 'weak_thermodynamics',
        'enable_environment': True,
        'env_bit_ratio': 0.2,
        'env_flip_prob': 0.1,
        'coupling_strength': 0.5,
        'enable_energy_flow': False,
        'enable_thermodynamics': True,
        'T_env': 0.5,  # 较低环境温度
        'heat_conductivity': 0.01,  # 弱热传导
        'initial_T': 1.0,
    },
    {
        'label': 'medium_thermodynamics',
        'enable_environment': True,
        'env_bit_ratio': 0.2,
        'env_flip_prob': 0.1,
        'coupling_strength': 0.5,
        'enable_energy_flow': False,
        'enable_thermodynamics': True,
        'T_env': 1.0,  # 中等环境温度
        'heat_conductivity': 0.05,  # 中等热传导
        'initial_T': 1.0,
    },
    {
        'label': 'strong_thermodynamics',
        'enable_environment': True,
        'env_bit_ratio': 0.2,
        'env_flip_prob': 0.1,
        'coupling_strength': 0.5,
        'enable_energy_flow': False,
        'enable_thermodynamics': True,
        'T_env': 2.0,  # 较高环境温度
        'heat_conductivity': 0.1,  # 强热传导
        'initial_T': 1.0,
    },
]


# ============================================================
# 主实验函数
# ============================================================

def run_single_experiment(config, run_id, total_runs):
    """
    运行单次实验
    """
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Running {config['label']} (run {run_id+1}/{total_runs})...")
    
    start_time = time.time()
    
    # 1. 初始化网格
    grid = torch.randint(0, 2, (N, N), dtype=torch.float32)
    
    # 2. 初始化演化器
    evolver = SpatialLongRangeEvolver(N, device='cpu')
    
    # 3. 初始化环境比特
    if config.get('enable_environment', False):
        env_config = OpenSystemConfig(
            enable_environment_bits=True,
            env_bit_ratio=config['env_bit_ratio'],
            env_flip_prob=config['env_flip_prob'],
            coupling_strength=config['coupling_strength'],
            enable_energy_flow=config.get('enable_energy_flow', False),
            enable_thermodynamic=config.get('enable_thermodynamics', False),
            temperature=config.get('T_env', 1.0),
        )
        env_bits = EnvironmentBits(N, env_config)
    else:
        env_bits = None
    
    # 4. 初始化热力学扩展
    thermo = ThermodynamicExtension(config)
    
    # 5. 演化循环
    history = {
        'config': config['label'],
        'run_id': run_id,
        'steps': [],
        'sealed': False,
        'seal_step': None,
        'post_seal_flips': 0,
        'thermo_history': [],
    }
    
    sealed = False
    
    for step in range(TOTAL_STEPS):
        # 记录当前状态
        hw = torch.sum(grid).item()
        
        # 环境耦合
        if env_bits is not None:
            boundary_bits = grid[0, :]  # 简化：仅上边界
            coupling_signal = env_bits.step(boundary_bits)
            # 应用耦合信号到边界
            if coupling_signal is not None:
                grid[0, :] = torch.clamp(grid[0, :] + coupling_signal, 0, 1)
        
        # 演化一步
        grid, _ = evolver.evolve(grid, steps=1)
        
        # 更新热力学状态
        thermo.update(grid, step)
        thermo_state = thermo.get_thermodynamic_state()
        history['thermo_history'].append(thermo_state)
        
        # 检查是否密封
        if not sealed and evolver.is_sealed(grid):
            sealed = True
            history['sealed'] = True
            history['seal_step'] = step
            print(f"  Sealed at step {step}")
        
        # 如果已密封，统计 post-seal flips
        if sealed:
            # 简化：用 Hamming weight 变化判断是否有 flip
            if step > 0:
                hw_prev = history['steps'][-1]['hw']
                if hw != hw_prev:
                    history['post_seal_flips'] += 1
        
        # 记录
        history['steps'].append({
            'step': step,
            'hw': hw,
            'sealed': sealed,
            'T_system': thermo_state['T_system'],
            'entropy': thermo_state['entropy'],
            'heat_dissipation': thermo_state['heat_dissipation_rate'],
        })
        
        # 早停：如果已密封且稳定 500 步，提前结束
        if sealed and step - history['seal_step'] > 500:
            # 检查是否稳定
            recent_steps = history['steps'][-500:]
            recent_hws = [s['hw'] for s in recent_steps]
            if np.std(recent_hws) < 1.0:  # 标准差很小，说明稳定
                print(f"  Early stop at step {step} (stable after seal)")
                break
    
    # 6. 收集结果
    hw_final = history['steps'][-1]['hw']
    hw_history = [s['hw'] for s in history['steps']]
    
    result = {
        'config': config['label'],
        'run_id': run_id,
        'sealed': history['sealed'],
        'seal_step': history['seal_step'],
        'hw_final': hw_final,
        'hw_history': hw_history,
        'post_seal_flips': history['post_seal_flips'],
        'thermo_history': history['thermo_history'],
        'total_steps': len(history['steps']),
        'elapsed_time': time.time() - start_time,
    }
    
    print(f"  Result: sealed={result['sealed']}, seal_step={result['seal_step']}, "
          f"hw_final={result['hw_final']}, post_seal_flips={result['post_seal_flips']}")
    
    return result


def run_all_experiments():
    """
    运行所有实验配置
    """
    print("=" * 80)
    print("exp_172 — Phase 16 Path A3: Thermodynamic Extension")
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
    
    # 汇总统计
    print("\n" + "=" * 80)
    print("Summary Statistics")
    print("=" * 80)
    
    for config in THERMODYNAMIC_CONFIGS:
        label = config['label']
        config_results = [r for r in all_results if r['config'] == label]
        
        seal_rates = [r['sealed'] for r in config_results]
        seal_rate = sum(seal_rates) / len(seal_rates) if seal_rates else 0
        
        hw_finals = [r['hw_final'] for r in config_results if r['sealed']]
        hw_final_mean = np.mean(hw_finals) if hw_finals else 0
        hw_final_std = np.std(hw_finals) if hw_finals else 0
        
        post_seal_flips = [r['post_seal_flips'] for r in config_results if r['sealed']]
        post_seal_flips_mean = np.mean(post_seal_flips) if post_seal_flips else 0
        
        print(f"\n{label}:")
        print(f"  Seal rate: {seal_rate*100:.1f}% ({sum(seal_rates)}/{len(seal_rates)})")
        print(f"  HW final: {hw_final_mean:.1f} ± {hw_final_std:.1f}")
        print(f"  Post-seal flips: {post_seal_flips_mean:.4f}")
        
        if config.get('enable_thermodynamics', False):
            # 统计热力学变量
            thermo_histories = [r['thermo_history'] for r in config_results if r['sealed']]
            if thermo_histories:
                # 取最后一次运行的热力学历史
                last_thermo = thermo_histories[-1]
                T_final = last_thermo[-1]['T_system'] if last_thermo else 0
                S_final = last_thermo[-1]['entropy'] if last_thermo else 0
                print(f"  Final T: {T_final:.4f}")
                print(f"  Final S: {S_final:.4f}")
    
    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = os.path.join(RESULTS_DIR, f'exp_172_results_{timestamp}.json')
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {result_file}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return all_results, result_file


if __name__ == '__main__':
    results, result_file = run_all_experiments()
    print("\nDone!")
