"""
narrative_recursion.py — V1.7 叙事递归的工程实现

实现差异论 V1.7 中的五中介动作：
1. 筛选差异 (Filter differences) - 识别系统高熵区域
2. 命名差异 (Name differences) - 编码差异类型到约束参数
3. 连接差异 (Connect differences) - 通过多场耦合建立因果链
4. 行动化差异 (Act on differences) - 能量脉冲定向注入
5. 递归验证 (Recursive verification) - 对比 P_t vs P_{t-1}

对应 V1.7 螺旋递归公式：P_{t+1} = N(S(M(E(P_t))))
其中 N = 叙事递归（本模块）
"""

from __future__ import annotations
from dataclasses import dataclass, field as dfield
from typing import Optional, Callable, List, Dict, Tuple
import numpy as np


@dataclass
class NarrativeState:
    """叙事状态：记录一轮螺旋递归的完整状态"""
    round: int                      # 螺旋轮次 t
    entropy_map: np.ndarray         # 高熵区域分布
    constraint_params: dict         # 约束参数编码
    field_coupling: dict            # 多场耦合权重
    energy_injection: np.ndarray    # 能量注入分布
    state_snapshot: np.ndarray      # 系统状态快照 P_t
    delta: float = 0.0              # |P_t - P_{t-1}| 变化量
    
    def compute_delta(self, prev_state: Optional[np.ndarray]) -> float:
        """计算与上一轮的状态差异"""
        if prev_state is None:
            return 0.0
        # 使用 Jaccard 距离衡量状态差异
        intersection = np.sum((self.state_snapshot == 1) & (prev_state == 1))
        union = np.sum((self.state_snapshot == 1) | (prev_state == 1))
        if union == 0:
            return 0.0
        jaccard = intersection / union
        self.delta = 1.0 - jaccard  # 距离 = 1 - 相似度
        return self.delta


class RecursiveNarrativeLoop:
    """V1.7 叙事递归的工程实现
    
    封装五中介动作，实现螺旋递归动力学。
    """
    
    def __init__(self, system, energy_field, 
                 entropy_threshold: float = 0.5,
                 coupling_strength: float = 0.3,
                 injection_rate: float = 0.1):
        """
        Args:
            system: 差异引擎系统 (Layer or RecursiveWorld)
            energy_field: 能量场管理器
            entropy_threshold: 高熵区域阈值 (默认 0.5)
            coupling_strength: 多场耦合强度 (默认 0.3)
            injection_rate: 能量注入率 (默认 0.1)
        """
        self.system = system
        self.energy_field = energy_field
        self.entropy_threshold = entropy_threshold
        self.coupling_strength = coupling_strength
        self.injection_rate = injection_rate
        
        self.history: List[NarrativeState] = []  # 螺旋递归历史
        self.round = 0
        
    def step(self) -> NarrativeState:
        """执行一轮完整螺旋递归 (五中介动作)
        
        Returns:
            NarrativeState: 本轮螺旋的状态
        """
        # 获取当前系统状态
        current_state = self._get_system_state()
        
        # === 动作 1: 筛选差异 ===
        entropy_map = self._scan_entropy(current_state)
        
        # === 动作 2: 命名差异 ===
        constraint_params = self._encode_differences(entropy_map)
        
        # === 动作 3: 连接差异 ===
        field_coupling = self._couple_fields(entropy_map)
        
        # === 动作 4: 行动化差异 ===
        energy_injection = self._inject_energy(entropy_map)
        
        # === 关键修复: 动作 5: 实际修改系统状态 ===
        self._apply_narrative_to_system(entropy_map, constraint_params)
        
        # === 重新获取修改后的系统状态 ===
        modified_state = self._get_system_state()
        
        # === 创建叙事状态 ===
        narrative_state = NarrativeState(
            round=self.round,
            entropy_map=entropy_map,
            constraint_params=constraint_params,
            field_coupling=field_coupling,
            energy_injection=energy_injection,
            state_snapshot=modified_state.copy()  # 使用修改后的状态
        )
        
        # === 递归验证 ===
        prev_state = self.history[-1].state_snapshot if self.history else None
        narrative_state.compute_delta(prev_state)
        
        # 记录历史
        self.history.append(narrative_state)
        self.round += 1
        
        return narrative_state
    
    def _apply_narrative_to_system(self, entropy_map: np.ndarray, constraint_params: Dict):
        """将叙事递归结果应用到系统，实际修改系统状态
        
        关键: 这是叙事递归的核心动作 — 改变系统状态，
        使下一轮递归看到不同的可能性空间拓扑。
        """
        if not hasattr(self.system, 'field'):
            return
        
        field = self.system.field
        N = len(field.state)
        
        # 策略: 根据熵分布，翻转一些位
        # 高熵区域 → 增加活跃位 (创造差异)
        # 低熵区域 → 减少活跃位 (消灭差异)
        
        high_entropy_mask = entropy_map > self.entropy_threshold
        n_high = np.sum(high_entropy_mask)
        
        if n_high > N * 0.5:
            # 太多高熵区域 → 随机减少一些活跃位
            n_flip = int(N * 0.1)
            active_indices = np.where(field.state == 1)[0]
            if len(active_indices) > 0:
                flip_idx = np.random.choice(active_indices, size=min(n_flip, len(active_indices)), replace=False)
                field.state[flip_idx] = 0
        else:
            # 适度高熵区域 → 在高熵区域增加活跃位
            high_indices = np.where(high_entropy_mask)[0]
            if len(high_indices) > 0:
                n_flip = min(len(high_indices), int(N * 0.05))
                flip_idx = np.random.choice(high_indices, size=n_flip, replace=False)
                field.state[flip_idx] = 1
        
        # 记录修改
        if not hasattr(self, '_narrative_modifications'):
            self._narrative_modifications = []
        self._narrative_modifications.append({
            'round': self.round,
            'n_high_entropy': int(n_high),
            'modified': True
        })
    
    def _get_system_state(self) -> np.ndarray:
        """获取当前系统状态 P_t"""
        if hasattr(self.system, 'field'):
            # Layer object
            return self.system.field.state.copy()
        elif hasattr(self.system, 'layers'):
            # RecursiveWorld object - return top layer state
            return self.system.layers[-1].field.state.copy()
        else:
            raise ValueError("Unknown system type")
    
    def _scan_entropy(self, state: np.ndarray) -> np.ndarray:
        """动作 1: 筛选差异 - 识别系统高熵区域
        
        使用滑动窗口计算局部信息熵。
        
        Args:
            state: 系统状态数组
            
        Returns:
            entropy_map: 每个位置的熵值 (0-1)
        """
        N = len(state)
        entropy_map = np.zeros(N)
        window_size = min(10, N // 10)  # 自适应窗口大小
        
        for i in range(N):
            # 计算滑动窗口
            start = max(0, i - window_size // 2)
            end = min(N, i + window_size // 2 + 1)
            window = state[start:end]
            
            # 计算信息熵 (-p*log(p))
            p1 = np.sum(window == 1) / len(window)
            p0 = 1 - p1
            
            if p1 > 0 and p1 < 1:
                entropy = -p1 * np.log2(p1) - p0 * np.log2(p0)
            else:
                entropy = 0.0
                
            entropy_map[i] = entropy / 1.0  # 归一化到 [0, 1]
        
        return entropy_map
    
    def _encode_differences(self, entropy_map: np.ndarray) -> Dict:
        """动作 2: 命名差异 - 编码差异类型到约束参数
        
        将高熵区域编码为约束场的参数。
        
        Args:
            entropy_map: 熵分布图
            
        Returns:
            constraint_params: 约束参数字典
        """
        # 识别高熵区域
        high_entropy_mask = entropy_map > self.entropy_threshold
        n_high = np.sum(high_entropy_mask)
        
        # 编码为约束参数
        constraint_params = {
            'high_entropy_count': int(n_high),
            'high_entropy_ratio': float(n_high / len(entropy_map)),
            'max_entropy': float(np.max(entropy_map)),
            'mean_entropy': float(np.mean(entropy_map)),
            'entropy_variance': float(np.var(entropy_map)),
        }
        
        # 如果有多场管理器，更新场参数
        if hasattr(self.energy_field, 'fields'):
            # 调整场的振幅基于熵分布
            for field in self.energy_field.fields:
                if hasattr(field, 'amplitude'):
                    # 高熵区域 → 增强约束
                    field.amplitude = 0.5 + 0.5 * constraint_params['high_entropy_ratio']
        
        return constraint_params
    
    def _couple_fields(self, entropy_map: np.ndarray) -> Dict:
        """动作 3: 连接差异 - 通过多场耦合建立因果链
        
        调整多场之间的耦合权重，使高熵区域产生强耦合。
        
        Args:
            entropy_map: 熵分布图
            
        Returns:
            field_coupling: 场耦合权重字典
        """
        coupling = {}
        
        # 如果有多场管理器
        if hasattr(self.energy_field, 'fields') and len(self.energy_field.fields) > 1:
            n_fields = len(self.energy_field.fields)
            
            # 计算每对场之间的耦合权重 (基于熵相关性)
            for i in range(n_fields):
                for j in range(i+1, n_fields):
                    # 简化：使用固定耦合强度
                    weight = self.coupling_strength
                    coupling[f'field_{i}_field_{j}'] = weight
        
        return coupling
    
    def _inject_energy(self, entropy_map: np.ndarray) -> np.ndarray:
        """动作 4: 行动化差异 - 向高熵区域定向注入能量
        
        Args:
            entropy_map: 熵分布图
            
        Returns:
            injection_map: 能量注入分布
        """
        # 计算注入量：高熵区域获得更多能量
        injection_map = entropy_map * self.injection_rate
        
        # 执行注入 (如果能量场支持)
        if hasattr(self.energy_field, 'inject'):
            self.energy_field.inject(injection_map)
        elif hasattr(self.energy_field, 'budget'):
            # EnergyManager 对象
            # 记录注入计划，在实际机制执行时扣除
            self._pending_injection = injection_map
        
        return injection_map
    
    def _verify_recursion(self) -> Dict:
        """动作 5: 递归验证 - 对比 P_t vs P_{t-1}
        
        Returns:
            verification: 验证结果字典
        """
        if len(self.history) < 2:
            return {'status': 'insufficient_history'}
        
        curr = self.history[-1]
        prev = self.history[-2]
        
        verification = {
            'round': curr.round,
            'delta': curr.delta,
            'is_non_repeat': curr.delta > 0.05,  # 非重复性阈值
            'entropy_change': np.mean(curr.entropy_map) - np.mean(prev.entropy_map),
            'constraint_change': curr.constraint_params != prev.constraint_params,
        }
        
        return verification
    
    def run_spiral(self, n_rounds: int = 5, verbose: bool = False) -> List[NarrativeState]:
        """运行多轮螺旋递归
        
        Args:
            n_rounds: 螺旋轮数
            verbose: 是否打印详细信息
            
        Returns:
            history: 螺旋递归历史
        """
        for r in range(n_rounds):
            state = self.step()
            
            if verbose:
                print(f"[Spiral Round {r}] "
                      f"delta={state.delta:.4f}, "
                      f"high_entropy={state.constraint_params['high_entropy_count']}, "
                      f"max_entropy={state.constraint_params['max_entropy']:.4f}")
            
            # 检查非重复性 (防止退化)
            if state.delta < 0.01:
                if verbose:
                    print(f"  Warning: spiral degenerating (delta={state.delta:.4f})")
        
        return self.history
    
    def get_spiral_trajectory(self) -> Dict:
        """获取螺旋轨迹分析
        
        Returns:
            trajectory: 螺旋轨迹统计数据
        """
        if not self.history:
            return {}
        
        deltas = [s.delta for s in self.history]
        entropies = [s.constraint_params['mean_entropy'] for s in self.history]
        
        trajectory = {
            'n_rounds': len(self.history),
            'delta_mean': float(np.mean(deltas)),
            'delta_std': float(np.std(deltas)),
            'delta_monotonic': all(deltas[i] <= deltas[i+1] for i in range(len(deltas)-1)),
            'entropy_mean': float(np.mean(entropies)),
            'entropy_trend': float(np.polyfit(range(len(entropies)), entropies, 1)[0]),
        }
        
        return trajectory


def test_narrative_recursion():
    """测试叙事递归实现"""
    print("=== Testing RecursiveNarrativeLoop ===")
    
    # 创建模拟系统
    class MockSystem:
        def __init__(self, N=100):
            self.field = MockField(N)
    
    class MockField:
        def __init__(self, N=100):
            self.state = np.random.randint(0, 2, N)
            self.N = N
    
    class MockEnergyField:
        def __init__(self):
            self.budget = 100.0
    
    # 测试初始化
    system = MockSystem(100)
    energy = MockEnergyField()
    loop = RecursiveNarrativeLoop(system, energy)
    
    # 测试单步
    state = loop.step()
    print(f"Round 0: delta={state.delta:.4f}, "
          f"high_entropy={state.constraint_params['high_entropy_count']}")
    
    # 测试多轮
    history = loop.run_spiral(n_rounds=5, verbose=True)
    print(f"\nCompleted {len(history)} rounds")
    
    # 分析轨迹
    trajectory = loop.get_spiral_trajectory()
    print(f"\nSpiral trajectory: {trajectory}")
    
    return loop


if __name__ == "__main__":
    test_narrative_recursion()
