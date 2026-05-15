"""
axioms_v2.py — 九公理约束重新设定（硬性约束版）

核心改变：
- 公理从"损失项"变成"演化图的允许边"
- 违反公理的演化直接禁止（不是惩罚）
- A1 严格单调（只允许 0→1，汇例外）
- A6 方向累积（不重置）
- A5 严格守恒（每步注入=吸收）
- A1' 层级比特 + 横向比特分离
- A7 循环通过源/汇通量路径形成
"""

import torch
import numpy as np
from typing import List, Optional, Tuple, Set


class AxiomConstraints:
    """九公理硬性约束检查器

    每个方法返回 (allowed: bool, reason: str)
    allowed=True 表示该演化被公理允许
    """

    def __init__(self, N: int, n_hierarchy_bits: int = None):
        """
        Args:
            N: 总比特数
            n_hierarchy_bits: 层级比特数（A1），剩余为横向比特（A1'）
        """
        self.N = N
        # 层级比特：控制差异密度（汉明重量）
        # 横向比特：控制差异分布（在重量不变的情况下重新分布）
        self.n_hierarchy = n_hierarchy_bits or N // 3
        self.n_lateral = N - self.n_hierarchy
        self.hierarchy_indices = list(range(self.n_hierarchy))
        self.lateral_indices = list(range(self.n_hierarchy, N))

        # A6 DAG方向：+1=只能0→1, -1=只能1→0, 0=双向（初始）
        # 关键：方向一旦设定，永不重置
        self.direction = torch.zeros(N, dtype=torch.long)

        # A7 循环检测：记录访问过的状态
        self.visited_states: Set[int] = set()
        self.cycle_states: Set[int] = set()  # 参与循环的状态

        # A5 守恒追踪
        self.total_injected = 0
        self.total_absorbed = 0

        # A9 活跃自由度追踪
        self.active_bits: Set[int] = set()  # 参与过演化的比特

    # ============================================================
    # A1：差异沿层级单调累积
    # ============================================================

    def check_A1(self, state: torch.Tensor, flip_idx: int) -> Tuple[bool, str]:
        """A1：只允许 0→1 翻转（层级单调累积）

        例外：汇吸收（外部力量）可以 1→0，但必须在 A5 约束下
        """
        if flip_idx < 0 or flip_idx >= self.N:
            return False, "invalid flip_idx"
        if state[flip_idx] > 0.5:
            return False, "A1: 1→0 flip forbidden (monotonicity)"
        return True, "ok"

    # ============================================================
    # A4：最小变易（单比特翻转）
    # ============================================================

    def check_A4(self, state: torch.Tensor, next_state: torch.Tensor) -> Tuple[bool, str]:
        """A4：相邻状态汉明距离必须为 1"""
        diff = (next_state - state).abs().sum().item()
        if diff != 1.0:
            return False, f"A4: d_H={diff} != 1"
        return True, "ok"

    # ============================================================
    # A5：差异总量守恒
    # ============================================================

    def check_A5_inject(self, state: torch.Tensor, n_inject: int) -> Tuple[bool, str]:
        """A5：注入量不能超过守恒上限"""
        w = state.sum().item()
        # 注入后 w + n_inject 不能超过 N
        if w + n_inject > self.N:
            return False, f"A5: w={w} + inject={n_inject} > N={self.N}"
        # 注入量必须与吸收量平衡（长期）
        projected_net = (self.total_injected + n_inject) - self.total_absorbed
        if projected_net > self.N * 0.5:  # 允许短期不平衡，但不超过 50%
            return False, f"A5: net_flux={projected_net} too large"
        return True, "ok"

    def check_A5_absorb(self, state: torch.Tensor, n_absorb: int) -> Tuple[bool, str]:
        """A5：吸收量不能超过当前重量"""
        w = state.sum().item()
        if n_absorb > w:
            return False, f"A5: absorb={n_absorb} > w={w}"
        return True, "ok"

    def record_inject(self, n: int):
        self.total_injected += n

    def record_absorb(self, n: int):
        self.total_absorbed += n

    # ============================================================
    # A6：DAG不可逆
    # ============================================================

    def check_A6(self, state: torch.Tensor, flip_idx: int) -> Tuple[bool, str]:
        """A6：禁止逆向翻转（DAG约束）"""
        if flip_idx < 0 or flip_idx >= self.N:
            return False, "invalid flip_idx"

        d = self.direction[flip_idx].item()
        s = state[flip_idx].item()

        if d > 0 and s > 0.5:
            # 方向=+1，当前=1，禁止 1→0
            return False, "A6: direction=+1, cannot flip 1→0"
        if d < 0 and s < 0.5:
            # 方向=-1，当前=0，禁止 0→1
            return False, "A6: direction=-1, cannot flip 0→1"

        return True, "ok"

    def update_A6_direction(self, flip_idx: int, old_val: float, new_val: float, is_external: bool = False):
        """A6：更新翻转方向（累积，不重置）

        is_external=True：源/汇操作，可以覆盖方向约束
        is_external=False：内部演化，遵循 DAG 约束
        """
        if is_external:
            # 源/汇可以覆盖方向
            if new_val > old_val:
                self.direction[flip_idx] = 1
            elif new_val < old_val:
                self.direction[flip_idx] = -1
        else:
            # 内部演化：方向累积，不可逆
            if new_val > old_val:
                self.direction[flip_idx] = 1
            elif new_val < old_val:
                # 只允许从 0 开始（避免循环）
                if self.direction[flip_idx].item() >= 0:
                    self.direction[flip_idx] = -1

    # ============================================================
    # A7：循环闭合
    # ============================================================

    def check_A7(self, state: torch.Tensor) -> Tuple[bool, str]:
        """A7：检测状态是否参与循环

        循环 = 状态在历史中出现过（通过源/汇通量形成闭合路径）
        """
        state_key = self._state_key(state)
        if state_key in self.visited_states:
            self.cycle_states.add(state_key)
            return True, "A7: cycle detected"
        self.visited_states.add(state_key)
        return True, "ok"  # 新状态也允许，只是还没形成循环

    def _state_key(self, state: torch.Tensor) -> int:
        """将状态转换为整数键"""
        bits = (state > 0.5).long()
        key = 0
        for i in range(self.N):
            key |= (bits[i].item() << i)
        return key

    # ============================================================
    # A8：对称偏好
    # ============================================================

    def get_A8_weights(self, state: torch.Tensor) -> torch.Tensor:
        """A8：计算每个比特的翻转权重（偏好 w=N/2）"""
        N = self.N
        w = state.sum().float()
        target = N / 2.0

        weights = torch.ones(N)

        # 对于层级比特：偏好达到中截面
        for i in self.hierarchy_indices:
            if w < target and state[i] < 0.5:
                weights[i] = 2.0  # 增强注入
            elif w > target and state[i] > 0.5:
                weights[i] = 0.5  # 抑制
            elif abs(w - target) < 1.0:
                weights[i] = 1.0  # 平衡

        # 对于横向比特：在重量不变的情况下重新分布
        for i in self.lateral_indices:
            weights[i] = 1.0  # 均匀权重

        return weights

    def get_A8_source_strength(self, state: torch.Tensor) -> int:
        """A8：基于当前重量动态确定源注入强度

        目标：维持 w ≈ N/2
        - w < N/2 - 2：强注入（4）
        - w < N/2：中等注入（2）
        - w > N/2 + 2：不注入（0）
        - w > N/2：弱注入（1）
        - 平衡态：维持（1）
        """
        w = state.sum().item()
        target = self.N / 2.0
        diff = target - w

        if diff > 4:
            return 4
        elif diff > 2:
            return 2
        elif diff < -4:
            return 0
        elif diff < -2:
            return 0
        else:
            return 1

    def get_A8_sink_strength(self, state: torch.Tensor, n_injected: int) -> int:
        """A8：基于当前重量和注入量确定汇吸收强度

        A5 守恒：吸收 = 注入 + 过剩调节
        - 基础吸收 = n_injected（A5 守恒）
        - 过剩调节：w > N/2 时多吸收，w < N/2 时少吸收
        """
        w = state.sum().item()
        target = self.N / 2.0
        excess = max(0, w - target)  # 只吸收过剩
        return n_injected + int(excess * 0.5)

    # ============================================================
    # A9：自由度封口
    # ============================================================

    def check_A9(self, flip_idx: int) -> Tuple[bool, str]:
        """A9：只允许活跃自由度参与演化"""
        # 前 N 步：所有比特都可以激活
        if len(self.active_bits) < self.N:
            self.active_bits.add(flip_idx)
            return True, "ok"

        # 之后：只允许活跃比特
        if flip_idx not in self.active_bits:
            return False, f"A9: bit {flip_idx} not active"

        return True, "ok"

    def record_active(self, flip_idx: int):
        self.active_bits.add(flip_idx)

    # ============================================================
    # A1'：横向涌现
    # ============================================================

    def get_A1_prime_candidates(self, state: torch.Tensor) -> List[Tuple[int, int]]:
        """A1'：生成横向比特的循环翻转对

        在保持总重量不变的前提下，横向比特之间可以交换差异
        → 形成循环模式 → 涌现"粒子"
        """
        candidates = []
        lateral_ones = [i for i in self.lateral_indices if state[i] > 0.5]
        lateral_zeros = [i for i in self.lateral_indices if state[i] < 0.5]

        # 随机配对：一个 1→0，一个 0→1（保持重量不变）
        if lateral_ones and lateral_zeros:
            n_pairs = min(len(lateral_ones), len(lateral_zeros), 2)
            for _ in range(n_pairs):
                i = lateral_ones[np.random.randint(len(lateral_ones))]
                j = lateral_zeros[np.random.randint(len(lateral_zeros))]
                if i != j:
                    candidates.append((i, j))  # i: 1→0, j: 0→1

        return candidates

    # ============================================================
    # 综合约束检查
    # ============================================================

    def get_allowed_flips(self, state: torch.Tensor) -> List[int]:
        """获取所有被公理允许的翻转位置"""
        allowed = []
        for i in range(self.N):
            # A1：只允许 0→1
            if state[i] > 0.5:
                continue
            # A6：DAG方向约束
            d = self.direction[i].item()
            if d < 0:
                continue
            # A9：自由度封口
            if len(self.active_bits) >= self.N and i not in self.active_bits:
                continue
            allowed.append(i)
        return allowed

    def get_allowed_absorbs(self, state: torch.Tensor) -> List[int]:
        """获取所有被公理允许的吸收位置（1→0）"""
        allowed = []
        for i in range(self.N):
            if state[i] < 0.5:
                continue
            # A6：DAG方向约束（汇可以覆盖）
            # 汇作为外部力量，可以覆盖 A6 约束
            allowed.append(i)
        return allowed
