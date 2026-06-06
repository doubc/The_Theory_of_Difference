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
from typing import List, Optional, Tuple, Set, Dict


class AxiomConstraints:
    """九公理硬性约束检查器

    每个方法返回 (allowed: bool, reason: str)
    allowed=True 表示该演化被公理允许
    """

    def __init__(self, N: int, n_hierarchy_bits: int = None, device: str = "cpu",
                 initial_state: Optional[torch.Tensor] = None):
        """
        Args:
            N: 总比特数
            n_hierarchy_bits: 层级比特数（A1），剩余为横向比特（A1'）
            device: 设备
            initial_state: 初始状态向量，用于派生初始A6方向
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
        # Fix (2026-06-01): 从initial_state派生初始方向，避免全零导致GBC无法激活
        # 规则：state > 0.5 → direction=+1（已持留，只能巩固）；state ≤ 0.5 → direction=-1（待激活）
        # 若initial_state为全零或None，则随机初始化（50/50 +1/-1），避免全+1导致约束过强
        if initial_state is not None and initial_state.numel() == N:
            self.direction = torch.where(initial_state > 0.5,
                                          torch.ones(N, dtype=torch.long, device=device),
                                          torch.full((N,), -1, dtype=torch.long, device=device))
            # 全零状态的特殊情况：随机初始化，平衡约束强度
            if self.direction.unique().numel() == 1 and self.direction[0].item() == -1:
                self.direction = torch.randint(0, 2, (N,), dtype=torch.long, device=device) * 2 - 1
        else:
            # 无initial_state时随机初始化（exp_94发现全+1导致GBC约束过强，CIV坍缩）
            self.direction = torch.randint(0, 2, (N,), dtype=torch.long, device=device) * 2 - 1

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

        # A9 活跃自由度追踪 — FIX (2026-06-03): 使用滑动窗口而非单调集合
        # 原 bug: active_bits 是 Set，只增不减 → 一旦超过 min_active_bits 就永远无法密封
        # 新设计: active_bits 记录每个比特的最近活跃步数，密封时只统计窗口内活跃的比特
        self.active_bits: Dict[int, int] = {}  # bit_idx -> last_active_step
        self.active_window = max(N // 2, 100)  # 滑动窗口大小（步数），默认 N/2 或 100
        # FIX (2026-06-03 Track B7): 独立追踪总唯一活跃比特数，用于触发密封
        # 原 bug: 密封触发条件 active_in_window >= N 太严格 — 早期活跃的比特若滑出窗口
        # 则永远无法凑齐 N 个，导致密封永远无法触发。
        # FIX v2: 使用百分比阈值而非 100% — 当 total_unique_active >= sealing_threshold
        # 时触发密封。sealing_threshold = max(0.75*N, 30)，确保在合理步数内可触发。
        self.total_unique_active: Set[int] = set()  # 所有曾经活跃过的比特
        self.sealing_activation_threshold = max(int(0.75 * N), 30)  # 触发密封的最低活跃比特数
        self.sealed = False  # 封口标志
        self.sealed_bits: Set[int] = set()  # 被封口的比特
        # P0 fix (2026-05-30): 提高最少活跃比特数，降低系统密封率
        # 原公式 max(3, N//4) 对 N=72 仅保留 18 比特（密封率 75%）
        # 新公式 max(N//3, 12) 对 N=72 保留 24 比特（密封率 67%），释放更多结构多样性
        # Fix (2026-05-31): cap at N to avoid impossible constraints for small N (e.g. N=8 -> min_active_bits=12 > 8)
        self.min_active_bits = min(N, max(N // 3, 12))  # 最少活跃比特数（≥33% 自由度，不超过 N）
        # 回流偏置场：跨层偏置的概率调制向量（由 HierarchyManager 注入）
        self.bias_profile: Optional[torch.Tensor] = None
        # 初始状态引用（用于调试/分析）
        self._initial_state = initial_state

        # ── A9 多隶属封口（可选，替代二元封口） ──
        self.mms: Optional[MultiMembershipSeal] = None  # Phase 10 P1 集成
        self._mms_setup_done = False
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
            # A5 守恒：吸收量不超过本步注入量（内部0→1翻转不额外触发吸收）
            return min(int(excess), n_injected)
        else:
            sink = n_injected
            sink = min(sink, int(w))
            sink = max(sink, 0)
            return sink

    # ============================================================
    # A9：自由度封口
    # ============================================================

    def enable_multi_membership(self, **mms_kwargs):
        """启用多隶属封口（Phase 10 P1 集成）

        替代二元 sealed_bits: Set[int]，改用 MultiMembershipSeal 的渐进式组织形成。
        - 比特同时隶属多个组织，锁定水平渐进增加
        - 未被完全锁定的比特持续参与演化
        - 向后兼容：self.sealed_bits / self.sealed 自动从 MMS 同步

        Args:
            **mms_kwargs: 传递给 MultiMembershipSeal 的额外参数
                (org_formation_interval, org_join_threshold, lock_threshold 等)

        Returns:
            MultiMembershipSeal 实例
        """
        if self.mms is not None:
            return self.mms

        # Lazy import to avoid circular dependency:
        # engine/__init__ → hierarchy_manager → axioms_v2 → engine/multi_membership_seal
        from engine.multi_membership_seal import MultiMembershipSeal

        self.mms = MultiMembershipSeal(
            N=self.N,
            binding_strength=self.binding_strength,
            **mms_kwargs
        )
        self._mms_setup_done = True
        return self.mms

    def _sync_from_mms(self):
        """将 MMS 状态同步到 legacy sealed 字段

        MultiMembershipSeal 的 sealed_bits 是计算属性（由 bit_memberships 派生），
        sealed 由 fully locked 比特数 >= threshold 决定。同步后，所有读取
        self.sealed_bits / self.sealed 的现有代码（hierarchy_manager、A3/A4/A8 等）
        无需修改即可使用多隶属封口的结果。
        """
        if self.mms is not None:
            self.sealed_bits = self.mms.sealed_bits
            self.sealed = self.mms.sealed

    def check_A9(self, flip_idx: int, partial_sealing: bool = False) -> Tuple[bool, str]:
        """A9：自由度封口

        阶段1（激活）：所有比特都可以激活
        阶段2（封口后）：只允许未被完全锁定的比特参与演化

        MMS 多隶属封口模式（Phase 10 P1）：
        - 使用 self.mms 判断比特是否完全锁定
        - MMS 的渐进式组织形成替代 _seal() 的二元冻结
        - 向后兼容：其他代码通过 self.sealed_bits / self.sealed 无缝读取

        Legacy 二元封口模式（当 self.mms is None）：
        - 激活阶段统计总唯一活跃比特数，达到阈值后触发 _seal()
        - 冻结绑定强度最低的比特，保留 min_active_bits
        """
        current_step = self._step_counter()

        # ════════════════════════════════════════════════
        # MMS 多隶属封口路径
        # ════════════════════════════════════════════════
        if self.mms is not None:
            self.mms.record_active(flip_idx, current_step)

            # 定期执行组织形成（渐进封口，非一次性 _seal()）
            if current_step % self.mms.org_formation_interval == 0:
                self.mms.form_organizations(current_step)
                self._sync_from_mms()

            # 比特完全锁定 → 禁止翻转
            if self.mms.is_fully_locked(flip_idx):
                return False, f"A9: bit {flip_idx} fully locked (MMS multi-membership)"

            # 同时更新 legacy fields（保障下游读取一致性）
            self.total_unique_active.add(flip_idx)
            self.active_bits[flip_idx] = current_step
            self._sync_from_mms()
            return True, "ok"

        # ════════════════════════════════════════════════
        # Legacy 二元封口路径（原始行为，完全不变）
        # ════════════════════════════════════════════════

        # 阶段1：激活阶段 — 统计总唯一活跃比特数（用于触发密封）
        self.total_unique_active.add(flip_idx)

        if len(self.total_unique_active) < self.sealing_activation_threshold:
            self.active_bits[flip_idx] = current_step
            return True, "ok"

        # 阶段2：封口 — 当活跃比特达到阈值，触发密封
        if not self.sealed:
            if partial_sealing:
                self._seal(current_step, partial=True)
            else:
                self._seal(current_step)

        # 封口后：只允许非冻结比特
        if flip_idx in self.sealed_bits:
            return False, f"A9: bit {flip_idx} sealed"

        self.active_bits[flip_idx] = current_step
        return True, "ok"

    def _step_counter(self) -> int:
        """返回当前步数计数器（由外层 evolver 设置）"""
        return getattr(self, '_current_step', 0)

    def _count_active_in_window(self, current_step: int) -> int:
        """统计滑动窗口内活跃的比特数"""
        cutoff = current_step - self.active_window
        return sum(1 for ts in self.active_bits.values() if ts >= cutoff)

    def _get_active_in_window(self, current_step: int) -> Set[int]:
        """获取滑动窗口内活跃的比特集合"""
        cutoff = current_step - self.active_window
        return {idx for idx, ts in self.active_bits.items() if ts >= cutoff}

    def _seal(self, current_step: int, partial: bool = False):
        """执行封口：冻结多余比特

        策略（Track B7 重构）：
        1. 只统计滑动窗口内活跃的比特（修复单调增长 bug）
        2. 优先保留参与 A7 循环的比特
        3. 其次保留绑定强度高的比特
        4. 冻结其余比特

        partial=True（Track B7）：部分封口模式
          - 横向比特和层级比特独立评估
          - 横向比特：按绑定强度排序，冻结底部 N_lateral/2
          - 层级比特：按绑定强度排序，冻结底部 N_hierarchy/2
          - 允许横向比特先封口，层级比特后封口
          - 返回 (sealed_lateral, sealed_hierarchy, sealed_bits)
        """
        # ── Root cause fix (2026-06-04): Separate size check from active set ──
        # Phase 5 added `set_current_step(step)` to SpatialLongRangeEvolver.run(),
        # which correctly timestamps active_bits entries. But _seal()
        # used active_window=100 to filter active_now, giving only 16-20 recent
        # bits at typical seal time (step 500-800). This hit the min_active_bits
        # threshold → premature sealing → reduced state diversity → CIV collapse.
        #
        # Fix: use ALL ever-active bits for the size check (prevents premature
        # sealing shortcut), but still freeze recently-active bits.
        all_active_bits = set(self.active_bits.keys())
        active_recent = self._get_active_in_window(current_step)

        if len(all_active_bits) <= self.min_active_bits:
            self.sealed = True
            print(f"[A9] Sealed at step {current_step}: {len(all_active_bits)} total active bits <= min {self.min_active_bits}")
            if partial:
                return True, True, set()
            return

        # Use recently active bits for scoring/freezing
        active_now = active_recent if active_recent else all_active_bits

        # 计算每个活跃比特的得分（绑定强度 + 循环参与）
        scores = {}
        for i in active_now:
            # 绑定强度得分 — 只在窗口内活跃比特间计算
            bind_score = sum(self.binding_strength[i][j].item() for j in active_now if j != i)
            bind_score = bind_score / max(len(active_now) - 1, 1)
            # 循环参与加成
            if i in self.cycle_participants:
                bind_score += 0.5
            scores[i] = bind_score

        if partial:
            # ── 部分封口模式：横向和层级独立 ──
            lateral_active = [i for i in active_now if i in self.lateral_indices]
            hierarchy_active = [i for i in active_now if i in self.hierarchy_indices]

            sealed_lateral = False
            sealed_hierarchy = False
            freeze = set()

            # 横向比特封口：冻结绑定强度最低的 50%
            if len(lateral_active) >= 4:
                lateral_sorted = sorted(lateral_active, key=lambda x: scores.get(x, 0), reverse=True)
                n_freeze_lat = max(1, len(lateral_active) // 2)
                freeze_lat = set(lateral_sorted[n_freeze_lat:])
                freeze |= freeze_lat
                sealed_lateral = True
                print(f"[A9 PARTIAL] Lateral: {len(lateral_active)} active, freezing {len(freeze_lat)}")
            else:
                print(f"[A9 PARTIAL] Lateral: only {len(lateral_active)} active, not enough to seal")

            # 层级比特封口：冻结绑定强度最低的 50%
            if len(hierarchy_active) >= 2:
                hierarchy_sorted = sorted(hierarchy_active, key=lambda x: scores.get(x, 0), reverse=True)
                n_freeze_hier = max(1, len(hierarchy_active) // 2)
                freeze_hier = set(hierarchy_sorted[n_freeze_hier:])
                freeze |= freeze_hier
                sealed_hierarchy = True
                print(f"[A9 PARTIAL] Hierarchy: {len(hierarchy_active)} active, freezing {len(freeze_hier)}")
            else:
                print(f"[A9 PARTIAL] Hierarchy: only {len(hierarchy_active)} active, not enough to seal")

            self.sealed_bits = freeze
            self.sealed = True
            print(f"[A9 PARTIAL] Sealed at step {current_step}: lateral={sealed_lateral}, hierarchy={sealed_hierarchy}, total frozen={len(freeze)}")
            return sealed_lateral, sealed_hierarchy, freeze
        else:
            # ── 全封口模式（原始行为） ──
            sorted_bits = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
            keep = set(sorted_bits[:self.min_active_bits])
            freeze = set(sorted_bits[self.min_active_bits:])

            self.sealed_bits = freeze
            self.sealed = True

            print(f"[A9] Sealed at step {current_step}: {len(active_now)} active in window, keeping {len(keep)}, freezing {len(freeze)}")
            print(f"[A9] Kept: {sorted(keep)}")
            print(f"[A9] Frozen: {sorted(freeze)}")

    def get_sealed_ratio(self) -> float:
        """获取封口比例"""
        if not self.sealed:
            return 0.0
        return len(self.sealed_bits) / self.N

    def get_sealing_status(self) -> Dict:
        """获取详细封口状态（Track B7 部分封口支持）

        Returns:
            {
                'sealed': bool,
                'sealed_lateral': bool,       # 横向比特是否已封口
                'sealed_hierarchy': bool,     # 层级比特是否已封口
                'sealed_bits': Set[int],
                'n_sealed_lateral': int,
                'n_sealed_hierarchy': int,
                'n_sealed_total': int,
                'n_lateral_total': int,
                'n_hierarchy_total': int,
            }
        """
        if not self.sealed:
            return {
                'sealed': False,
                'sealed_lateral': False,
                'sealed_hierarchy': False,
                'sealed_bits': set(),
                'n_sealed_lateral': 0,
                'n_sealed_hierarchy': 0,
                'n_sealed_total': 0,
                'n_lateral_total': len(self.lateral_indices),
                'n_hierarchy_total': len(self.hierarchy_indices),
            }

        sealed_lat = set(i for i in self.sealed_bits if i in self.lateral_indices)
        sealed_hier = set(i for i in self.sealed_bits if i in self.hierarchy_indices)
        lateral_total = len(self.lateral_indices)
        hierarchy_total = len(self.hierarchy_indices)

        # 横向封口：超过 50% 横向比特被冻结
        sealed_lateral = len(sealed_lat) >= lateral_total * 0.4
        # 层级封口：超过 50% 层级比特被冻结
        sealed_hierarchy = len(sealed_hier) >= hierarchy_total * 0.4

        return {
            'sealed': True,
            'sealed_lateral': sealed_lateral,
            'sealed_hierarchy': sealed_hierarchy,
            'sealed_bits': self.sealed_bits,
            'n_sealed_lateral': len(sealed_lat),
            'n_sealed_hierarchy': len(sealed_hier),
            'n_sealed_total': len(self.sealed_bits),
            'n_lateral_total': lateral_total,
            'n_hierarchy_total': hierarchy_total,
        }

    def record_active(self, flip_idx: int):
        """记录比特活跃 — 更新其最近活跃时间戳"""
        current_step = self._step_counter()
        self.active_bits[flip_idx] = current_step
        self.total_unique_active.add(flip_idx)  # FIX Track B7

    def set_current_step(self, step: int):
        """由外层 evolver 每步调用，更新步数计数器"""
        self._current_step = step

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
            # A9：自由度封口 — 只检查 sealed_bits（由_seal() 决定冻结哪些）
            # FIX Track B7: 移除冗余的窗口判断，密封决策统一在_seal() 中完成
            # FIX Track B7 v2: 使用百分比阈值触发密封
            if self.sealed and i in self.sealed_bits:
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
