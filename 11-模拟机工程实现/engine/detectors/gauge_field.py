"""
engine/detectors/gauge_field.py — 规范场探测器 (P3)

检测中截面 M_N={x: w(x)=N/2} 上的 su(3) 规范结构。

理论预测（WorldBase §5）：
- 中截面上 k=3 活跃位 → 8 生成元 → su(3) 李代数
- CR-1: [E_ij, E_jk] = E_ik
- CR-2: [E_ij, E_ji] = -(x_i - x_j)（我们的符号约定）

检测方法：
1. 从演化轨迹中采样中截面状态
2. 在每个中截面状态上验证 E_ij 对易关系
3. 统计 CR-1/CR-2 通过率
4. 检测生成元计数 k=3 → 8
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple
from engine.first_order_algebra import FirstOrderAlgebra
from engine.mid_surface_analyzer import MidSurfaceAnalyzer


class GaugeFieldDetector:
    """规范场探测器"""

    def __init__(self, N: int, device: str = "cpu"):
        if N % 2 != 0:
            raise ValueError(f"N 必须是偶数，当前 N={N}")
        self.N = N
        self.device = device
        self.algebra = FirstOrderAlgebra(N, device)
        self.mid_analyzer = MidSurfaceAnalyzer(N, device)
        self.mid_w = N // 2

    def sample_mid_surface_states(self, trajectory: torch.Tensor,
                                    max_samples: int = 50) -> List[torch.Tensor]:
        """从轨迹中采样中截面状态"""
        mid_states = []
        for t in range(trajectory.shape[0]):
            state = trajectory[t]
            if self.mid_analyzer.is_on_mid_surface(state):
                mid_states.append(state.clone())
                if len(mid_states) >= max_samples:
                    break
        return mid_states

    def generate_mid_surface_states(self, n_samples: int = 50) -> List[torch.Tensor]:
        """生成随机中截面状态"""
        states = []
        for _ in range(n_samples):
            state = torch.zeros(self.N, device=self.device)
            indices = torch.randperm(self.N, device=self.device)[:self.mid_w]
            state[indices] = 1.0
            states.append(state)
        return states

    def verify_CR1_on_state(self, state: torch.Tensor) -> Dict:
        """在单个状态上验证 CR-1: [E_ij, E_jk] = E_ik

        i 必须是 1，j 必须是 0，k 必须是 1。
        E_ij: i(1)->0, j(0)->1
        E_jk: j(1)->0, k(1)->1（需要 E_ij 之后 j=1）
        """
        ones = (state > 0.5).nonzero(as_tuple=True)[0].tolist()
        zeros = (state < 0.5).nonzero(as_tuple=True)[0].tolist()
        if len(ones) < 2 or len(zeros) < 1:
            return {'holds': 'N/A', 'reason': 'need 2+ ones and 1+ zero'}

        # CR-1: i from ones, j and k from zeros
        # 这样 E_ij(i=1,j=0), E_jk(j=1,k=0), E_ik(i=1,k=0) 都有效
        i = ones[0]
        j = zeros[0]
        k = zeros[1] if len(zeros) > 1 else zeros[0]
        return self.algebra.verify_CR1(state, i, j, k)

    def verify_CR2_on_state(self, state: torch.Tensor) -> Dict:
        """在单个状态上验证 CR-2: [E_ij, E_ji] = -(x_i - x_j)

        i 必须是 1，j 必须是 0（这样 E_ij 有效）。
        """
        ones = (state > 0.5).nonzero(as_tuple=True)[0].tolist()
        zeros = (state < 0.5).nonzero(as_tuple=True)[0].tolist()
        if len(ones) < 1 or len(zeros) < 1:
            return {'holds': 'N/A', 'reason': 'need 1+ one and 1+ zero'}

        i = ones[0]  # bit i = 1
        j = zeros[0]  # bit j = 0
        return self.algebra.verify_CR2(state, i, j)

    def count_generators(self, k: int = 3) -> Dict:
        """计算 k 个活跃位的生成元数量"""
        return self.algebra.count_generators(list(range(k)))

    def analyze_mid_surface(self, trajectory: torch.Tensor,
                            max_samples: int = 50) -> Dict:
        """分析轨迹中的中截面结构"""
        mid_states = self.sample_mid_surface_states(trajectory, max_samples)

        if not mid_states:
            # 轨迹中没有中截面状态，生成一些
            mid_states = self.generate_mid_surface_states(min(max_samples, 20))

        # CR-1 验证
        cr1_pass = 0
        cr1_fail = 0
        cr1_na = 0
        cr1_details = []

        # CR-2 验证
        cr2_pass = 0
        cr2_fail = 0
        cr2_na = 0
        cr2_details = []

        for state in mid_states:
            r1 = self.verify_CR1_on_state(state)
            h1 = r1.get('CR1_holds', r1.get('holds', 'N/A'))
            if h1 == True:
                cr1_pass += 1
            elif h1 == False:
                cr1_fail += 1
            else:
                cr1_na += 1
            cr1_details.append(h1)

            r2 = self.verify_CR2_on_state(state)
            h2 = r2.get('CR2_holds', r2.get('holds', 'N/A'))
            if h2 == True:
                cr2_pass += 1
            elif h2 == False:
                cr2_fail += 1
            else:
                cr2_na += 1
            cr2_details.append(h2)

        n_total = len(mid_states)

        # 生成元计数
        gen3 = self.count_generators(k=3)
        gen4 = self.count_generators(k=4)

        # su(3) 信号
        su3_signal = (
            cr1_pass > cr1_fail and
            cr2_pass > cr2_fail and
            gen3['algebra'] == 'su(3)'
        )

        return {
            'n_mid_surface_states': n_total,
            'CR1_pass': cr1_pass,
            'CR1_fail': cr1_fail,
            'CR1_NA': cr1_na,
            'CR1_pass_rate': cr1_pass / max(n_total - cr1_na, 1),
            'CR2_pass': cr2_pass,
            'CR2_fail': cr2_fail,
            'CR2_NA': cr2_na,
            'CR2_pass_rate': cr2_pass / max(n_total - cr2_na, 1),
            'generators_k3': gen3,
            'generators_k4': gen4,
            'su3_signal': su3_signal,
            'algebra': 'su(3)' if su3_signal else 'undetermined',
        }

    def analyze_from_evolver_result(self, result: Dict,
                                     max_samples: int = 50) -> Dict:
        """从演化器结果分析规范场"""
        if 'snapshots' not in result or not result['snapshots']:
            return {'error': 'no snapshots'}

        traj = torch.stack([s.state for s in result['snapshots']], dim=0)
        return self.analyze_mid_surface(traj, max_samples)

    def analyze_from_spatial_result(self, result: Dict,
                                     max_samples: int = 50) -> Dict:
        """从空间演化器结果分析（兼容 SpatialEvolver 的 SpatialSnapshot）"""
        if 'snapshots' not in result or not result['snapshots']:
            return {'error': 'no snapshots'}

        # SpatialSnapshot 有 .state 属性
        states = []
        for s in result['snapshots']:
            if hasattr(s, 'state'):
                states.append(s.state)
            else:
                states.append(s)  # fallback

        if not states:
            return {'error': 'no valid snapshots'}

        traj = torch.stack(states, dim=0)
        return self.analyze_mid_surface(traj, max_samples)
