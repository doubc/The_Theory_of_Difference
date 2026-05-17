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

    def __init__(self, N: int, n_hierarchy_bits: int = None, device: str = "cpu"):
        """
        Args:
            N: 总比特数
            n_hierarchy_bits: 层级比特数（A1），剩余为横向比特（A1'）
            device: 设备
        """
        self.N = N
        self.device = device
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
        self.state_history: List[int] = []  # 状态历史（用于 SCC 检测）
        self.cycle_participants: Set[int] = set()  # 参与循环的比特

        # A5 守恒追踪
        self.total_injected = 0
        self.total_absorbed = 0

        # A1' 横向涌现：绑定强度矩阵
        self.binding_strength = torch.zeros(N, N, device=self.device)
        # 初始小的随机绑定（原初差异的体现）
        self.binding_strength += torch.randn(N, N, device=self.device) * 0.01
        self.binding_strength = (self.binding_strength + self.binding_strength.T) / 2  # 对称
        self.binding_strength.fill_diagonal_(0)

        # A9 活跃自由度追踪
        self.active_bits: Set[int] = set()
        self.sealed = False  # 封口标志
        self.sealed_bits: Set[int] = set()  # 被封口的比特
        self.min_active_bits = max(3, N // 4)  # 最少活跃比特数
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

        改进：不仅检测精确重复，还检测近似循环（汉明距离 ≤ 2）
        如果当前状态与历史中某个状态接近，认为参与了循环
        """
        state_key = self._state_key(state)
        self.state_history.append(state_key)

        # 精确重复
        if state_key in self.visited_states:
            self.cycle_states.add(state_key)
            return True, "A7: exact cycle detected"

        # 近似重复：与历史状态汉明距离 ≤ 2
        if len(self.visited_states) > 10:
            # 只检查最近 1000 个状态（性能考虑）
            recent = list(self.visited_states)[-1000:]
            for prev_key in recent:
                d_h = bin(state_key ^ prev_key).count('1')
                if d_h <= 2:
                    self.cycle_states.add(state_key)
                    self.cycle_states.add(prev_key)
                    return True, f"A7: near cycle detected (d_H={d_h})"

        self.visited_states.add(state_key)
        return True, "ok"

    def get_A7_cycle_participants(self, flip_history: List[int]) -> Set[int]:
        """获取参与循环的比特

        参与过循环状态的比特翻转 = 循环参与者
        """
        return self.cycle_participants

    def record_cycle_bit(self, bit_idx: int):
        """记录参与循环的比特"""
        self.cycle_participants.add(bit_idx)

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
        A9 封口后：基于未冻结比特计算有效目标
        """
        w = state.sum().item()

        # A9 封口后：基于未冻结比特计算
        if self.sealed and len(self.sealed_bits) > 0:
            # 未冻结比特中的 1 的数量
            unsealed_ones = sum(1 for i in range(self.N) if i not in self.sealed_bits and state[i] > 0.5)
            unsealed_zeros = sum(1 for i in range(self.N) if i not in self.sealed_bits and state[i] < 0.5)
            unsealed_total = unsealed_ones + unsealed_zeros
            if unsealed_total == 0:
                return 0
            target_unsealed = unsealed_total / 2.0
            diff = target_unsealed - unsealed_ones
        else:
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
        """A8：汇吸收强度

        A5 守恒 + A9 封口兼容：
        - 未封口：吸收 = 注入（严格平衡）
        - 封口后：只吸收过剩部分（让未冻结比特保持稳定）
        """
        w = state.sum().item()

        if self.sealed:
            # A9 封口后：只吸收超过目标的部分
            unsealed_ones = sum(1 for i in range(self.N) if i not in self.sealed_bits and state[i] > 0.5)
            unsealed_zeros = sum(1 for i in range(self.N) if i not in self.sealed_bits and state[i] < 0.5)
            unsealed_total = unsealed_ones + unsealed_zeros
            if unsealed_total == 0:
                return 0
            target_unsealed = unsealed_total / 2.0
            excess = max(0, unsealed_ones - target_unsealed)
            return int(excess)
        else:
            sink = n_injected
            sink = min(sink, int(w))
            sink = max(sink, 0)
            return sink

    # ============================================================
    # A9：自由度封口
    # ============================================================

    def check_A9(self, flip_idx: int) -> Tuple[bool, str]:
        """A9：自由度封口

        阶段1（未封口）：所有比特都可以激活
        阶段2（封口后）：只允许活跃比特中的一部分参与演化
          - 基于绑定强度选择最活跃的比特
          - 冻结多余比特（低于阈值的被冻结）
          - 保留最少 min_active_bits 个比特
        """
        # 阶段1：激活阶段
        if len(self.active_bits) < self.N:
            self.active_bits.add(flip_idx)
            return True, "ok"

        # 阶段2：封口
        if not self.sealed:
            self._seal()

        # 封口后：只允许非冻结比特
        if flip_idx in self.sealed_bits:
            return False, f"A9: bit {flip_idx} sealed"

        self.active_bits.add(flip_idx)
        return True, "ok"

    def _seal(self):
        """执行封口：冻结多余比特

        策略：
        1. 优先保留参与 A7 循环的比特
        2. 其次保留绑定强度高的比特
        3. 冻结其余比特
        """
        if len(self.active_bits) <= self.min_active_bits:
            self.sealed = True
            return

        # 计算每个比特的得分（绑定强度 + 循环参与）
        scores = {}
        for i in self.active_bits:
            # 绑定强度得分
            bind_score = sum(self.binding_strength[i][j].item() for j in self.active_bits if j != i)
            bind_score = bind_score / max(len(self.active_bits) - 1, 1)
            scores[i] = bind_score

        # 按得分排序，保留最高的
        sorted_bits = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        keep = set(sorted_bits[:self.min_active_bits])
        freeze = set(sorted_bits[self.min_active_bits:])

        self.sealed_bits = freeze
        self.sealed = True

        print(f"[A9] Sealed: keeping {len(keep)} bits, freezing {len(freeze)} bits")
        print(f"[A9] Kept: {sorted(keep)}")
        print(f"[A9] Frozen: {sorted(freeze)}")

    def get_sealed_ratio(self) -> float:
        """获取封口比例"""
        if not self.sealed:
            return 0.0
        return len(self.sealed_bits) / self.N

    def record_active(self, flip_idx: int):
        self.active_bits.add(flip_idx)

    # ============================================================
    # A1'：横向涌现
    # ============================================================

    def get_A1_prime_candidates(self, state: torch.Tensor) -> List[Tuple[int, int]]:
        """A1'：生成横向比特的循环翻转对

        关键改变：引入绑定强度，某些比特对倾向于一起翻转
        绑定强度随共现翻转次数增加 → 聚类涌现
        """
        candidates = []
        lateral_ones = [i for i in self.lateral_indices if state[i] > 0.5]
        lateral_zeros = [i for i in self.lateral_indices if state[i] < 0.5]

        if not lateral_ones or not lateral_zeros:
            return candidates

        # 基于绑定强度选择配对
        pairs = []
        for i in lateral_ones:
            for j in lateral_zeros:
                if i != j:
                    binding = self.binding_strength[i][j].item()
                    pairs.append((i, j, binding))

        if not pairs:
            return candidates

        # 按绑定强度加权采样
        bindings = torch.tensor([p[2] for p in pairs])
        bindings = bindings.clamp(min=0.01)
        bindings = bindings / bindings.sum()

        n_pairs = min(len(pairs), 2)
        if n_pairs > 0:
            indices = torch.multinomial(bindings, n_pairs, replacement=False)
            for idx in indices:
                i, j, _ = pairs[idx.item()]
                candidates.append((i, j))

        return candidates

    def strengthen_binding(self, i: int, j: int, amount: float = 0.1):
        """增强比特 i 和 j 之间的绑定强度"""
        if i in self.lateral_indices and j in self.lateral_indices:
            self.binding_strength[i][j] += amount
            self.binding_strength[j][i] += amount

    def get_clusters(self) -> List[List[int]]:
        """基于绑定强度提取聚类"""
        visited = set()
        clusters = []
        threshold = 0.5  # 绑定强度阈值

        for i in self.lateral_indices:
            if i in visited:
                continue
            cluster = [i]
            visited.add(i)
            for j in self.lateral_indices:
                if j not in visited and self.binding_strength[i][j].item() > threshold:
                    cluster.append(j)
                    visited.add(j)
            if len(cluster) >= 2:
                clusters.append(cluster)

        return clusters

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
