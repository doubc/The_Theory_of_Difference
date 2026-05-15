"""
axioms_v3.py — 九公理约束 v3（排除累积版）

核心改变：
- 差异不是比特翻转，而是翻转时被排除的可能性
- 每个比特携带排除历史 excluded[i] ∈ [0, ∞)
- 排除累积到阈值 → 层级提升 → 锁定
- 高层比特翻转 = 被排除之物的幽灵回归

对应理论：原初差异 = 0.000...1 = 系统闭合的代价
"""

import torch
import numpy as np
from typing import List, Optional, Tuple, Set, Dict


class ExclusionAccumulator:
    """排除累积器

    每个比特维护：
    - state: 当前状态 (0 或 1)
    - excluded: 累积的被排除量
    - hierarchy_level: 层级（由排除累积决定）
    - locked: 是否被锁定
    """

    def __init__(self, N: int, device: str = "cpu"):
        self.N = N
        self.device = device

        # 核心状态
        self.state = torch.zeros(N, device=device)  # 当前比特值
        self.excluded = torch.full((N,), 1e-10, device=device)  # 排除量（初始=原初差异）
        self.hierarchy_level = torch.zeros(N, dtype=torch.long, device=device)  # 层级
        self.locked = torch.zeros(N, dtype=torch.bool, device=device)  # 锁定状态

        # 层级阈值
        self.level_thresholds = [0.5, 1.0, 2.0, 4.0]  # 累积到阈值 → 升级

        # 统计
        self.total_exclusion = 1e-10 * N  # 总排除量（守恒量）
        self.n_transitions = 0  # 总翻转次数

    def get_exclusion_level(self, exclusion_value: float) -> int:
        """根据排除量确定层级"""
        for i, threshold in enumerate(self.level_thresholds):
            if exclusion_value < threshold:
                return i
        return len(self.level_thresholds)

    def accumulate_exclusion(self, bit_idx: int, amount: float):
        """累积排除量"""
        old_level = self.hierarchy_level[bit_idx].item()
        self.excluded[bit_idx] += amount
        new_level = self.get_exclusion_level(self.excluded[bit_idx].item())
        self.hierarchy_level[bit_idx] = new_level

        # 层级提升 → 锁定
        if new_level > old_level:
            self.locked[bit_idx] = True

    def transfer_exclusion(self, from_idx: int, to_idx: int, amount: float):
        """层间排除转移（守恒）"""
        self.excluded[from_idx] -= amount
        self.excluded[to_idx] += amount
        # 更新层级
        self.hierarchy_level[from_idx] = self.get_exclusion_level(self.excluded[from_idx].item())
        self.hierarchy_level[to_idx] = self.get_exclusion_level(self.excluded[to_idx].item())

    def get_available_bits(self) -> List[int]:
        """获取可翻转的比特（未锁定）"""
        return [i for i in range(self.N) if not self.locked[i].item()]

    def get_hierarchy_distribution(self) -> Dict[int, int]:
        """获取层级分布"""
        dist = {}
        for i in range(self.N):
            level = self.hierarchy_level[i].item()
            dist[level] = dist.get(level, 0) + 1
        return dist


class AxiomConstraintsV3:
    """九公理约束 v3（排除累积版）"""

    def __init__(self, N: int, device: str = "cpu"):
        self.N = N
        self.device = device

        # 排除累积器
        self.accumulator = ExclusionAccumulator(N, device)

        # A1：原初差异 = 初始排除量（每个比特 1e-10）
        self.prime_difference = 1e-10

        # A7：循环检测
        self.visited_states: Set[int] = set()
        self.cycle_states: Set[int] = set()

        # A9：活跃自由度
        self.active_bits: Set[int] = set()

    # ============================================================
    # A1：原初差异（排除版）
    # ============================================================

    def check_A1(self, bit_idx: int) -> Tuple[bool, str]:
        """A1：只允许 0→1 翻转（差异单调累积）"""
        if self.accumulator.locked[bit_idx].item():
            return False, "A1: bit locked"
        if self.accumulator.state[bit_idx] > 0.5:
            return False, "A1: 1→0 forbidden"
        return True, "ok"

    # ============================================================
    # A4：最小变易
    # ============================================================

    def check_A4(self, bit_idx: int) -> Tuple[bool, str]:
        """A4：单比特翻转"""
        if bit_idx < 0 or bit_idx >= self.N:
            return False, "invalid bit_idx"
        return True, "ok"

    # ============================================================
    # A5：差异守恒（排除总量守恒）
    # ============================================================

    def check_A5(self) -> Tuple[bool, str]:
        """A5：总排除量守恒"""
        current_total = self.accumulator.excluded.sum().item()
        expected_total = self.accumulator.total_exclusion
        if abs(current_total - expected_total) > 1e-8:
            return False, f"A5: total exclusion {current_total} != {expected_total}"
        return True, "ok"

    def record_transition(self, bit_idx: int, direction: int):
        """记录翻转并累积排除"""
        # 翻转
        old_val = self.accumulator.state[bit_idx].item()
        new_val = 1.0 if direction > 0 else 0.0
        self.accumulator.state[bit_idx] = new_val
        self.accumulator.n_transitions += 1

        # 累积排除
        # 0→1：排除的是"保持为0"的可能性 → 排除量 = 当前排除量的一半
        # 1→0：排除的是"保持为1"的可能性 → 排除量 = 当前排除量
        if direction > 0:  # 0→1
            exclusion_amount = self.accumulator.excluded[bit_idx].item() * 0.5
        else:  # 1→0
            exclusion_amount = self.accumulator.excluded[bit_idx].item()

        self.accumulator.accumulate_exclusion(bit_idx, exclusion_amount)

        # 活跃记录
        self.active_bits.add(bit_idx)

    # ============================================================
    # A6：DAG不可逆
    # ============================================================

    def check_A6(self, bit_idx: int, direction: int) -> Tuple[bool, str]:
        """A6：DAG方向约束"""
        if self.accumulator.locked[bit_idx].item():
            return False, "A6: locked"
        # 只允许 0→1（direction > 0）
        if direction < 0:
            return False, "A6: 1→0 forbidden (DAG)"
        return True, "ok"

    # ============================================================
    # A7：循环闭合
    # ============================================================

    def check_A7(self) -> Tuple[bool, str]:
        """A7：检测循环"""
        state_key = self._state_key()
        if state_key in self.visited_states:
            self.cycle_states.add(state_key)
            return True, "cycle"
        self.visited_states.add(state_key)
        return True, "ok"

    def _state_key(self) -> int:
        bits = (self.accumulator.state > 0.5).long()
        key = 0
        for i in range(self.N):
            key |= (bits[i].item() << i)
        return key

    # ============================================================
    # A8：对称偏好
    # ============================================================

    def get_A8_source_strength(self) -> int:
        """A8：基于当前重量动态确定源注入强度"""
        w = self.accumulator.state.sum().item()
        target = self.N / 2.0
        diff = target - w

        if diff > 4:
            return 4
        elif diff > 2:
            return 2
        elif diff < -2:
            return 0
        else:
            return 1

    def get_A8_sink_strength(self) -> int:
        """A8：基于当前重量动态确定汇吸收强度"""
        w = self.accumulator.state.sum().item()
        target = self.N / 2.0
        diff = w - target

        if diff > 4:
            return 4
        elif diff > 2:
            return 2
        elif diff < -2:
            return 0
        else:
            return 1

    # ============================================================
    # A9：自由度封口
    # ============================================================

    def check_A9(self, bit_idx: int) -> Tuple[bool, str]:
        """A9：只允许活跃自由度"""
        if len(self.active_bits) >= self.N:
            if bit_idx not in self.active_bits:
                return False, "A9: not active"
        return True, "ok"

    # ============================================================
    # 综合约束
    # ============================================================

    def get_allowed_flips(self) -> List[int]:
        """获取所有允许的翻转位置（0→1）"""
        allowed = []
        for i in range(self.N):
            if self.accumulator.locked[i].item():
                continue
            if self.accumulator.state[i] > 0.5:
                continue
            allowed.append(i)
        return allowed

    def get_allowed_absorbs(self) -> List[int]:
        """获取所有允许的吸收位置（1→0）"""
        allowed = []
        for i in range(self.N):
            if self.accumulator.locked[i].item():
                continue
            if self.accumulator.state[i] < 0.5:
                continue
            allowed.append(i)
        return allowed

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            'total_exclusion': self.accumulator.total_exclusion,
            'current_exclusion': self.accumulator.excluded.sum().item(),
            'n_transitions': self.accumulator.n_transitions,
            'hierarchy_distribution': self.accumulator.get_hierarchy_distribution(),
            'n_locked': self.accumulator.locked.sum().item(),
            'n_active': len(self.active_bits),
            'n_cycles': len(self.cycle_states),
            'weight': self.accumulator.state.sum().item(),
        }
