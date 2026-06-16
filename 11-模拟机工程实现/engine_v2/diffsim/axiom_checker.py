"""axiom_checker.py — NumPy 版公理约束检查器

从 acl/axioms_v2.py 提取核心约束, 转为 NumPy 实现,
与 engine_v2/diffsim/mechanisms.py 对接。

公理→机制映射:
  A1(原初差异) → m1(聚簇): 差异沿层级累积
  A1'(横向涌现) → m1(聚簇): 同色优先绑定
  A2(二元具象) → core: {0,1}^N 状态空间
  A3(有限离散) → core: N 有限
  A4(最小变易) → m5(变易): 每步 d_H=1
  A5(差异守恒) → m3(守恒): 注入=吸收
  A6(不可逆性) → m8(锁定): 方向累积, 不重置
  A7(循环闭合) → m7(循环): 稳定态参与循环
  A8(对称偏好) → m3(守恒): 偏好 w≈N/2
  A9(内生完备) → m9(自指): 自由度=公理要求的最小值
"""
from __future__ import annotations
import numpy as np
from typing import Tuple, Set, Dict


class AxiomChecker:
    """公理约束检查器 (NumPy 版)
    
    与 Layer.field (DifferenceField) 配合使用。
    每个 check_* 方法返回 (allowed: bool, reason: str)。
    """
    
    def __init__(self, N: int, rng: np.random.RandomState = None):
        self.N = N
        self.rng = rng or np.random.RandomState()
        
        # A6: DAG 方向 (+1=只能0→1, -1=只能1→0, 0=双向)
        # 初始随机, 一旦设定不重置
        self.direction = self.rng.choice([-1, 1], size=N).astype(np.int8)
        
        # A5: 守恒追踪
        self.total_injected = 0
        self.total_absorbed = 0
        
        # A7: 循环检测
        self.state_history: list = []  # 活跃集历史
        self.cycle_participants: Set[int] = set()
        
        # A9: 活跃自由度追踪
        self.active_bits_history: Dict[int, int] = {}  # bit -> last_active_step
        self.total_unique_active: Set[int] = set()
        self.sealed = False
        self.sealed_bits: Set[int] = set()
        self.current_step = 0
    
    # ================================================================
    # A1: 原初差异 — 只允许 0→1 (层级单调累积)
    # ================================================================
    def check_A1(self, state: np.ndarray, flip_idx: int) -> Tuple[bool, str]:
        """A1: 0→1 翻转允许, 1→0 需要 A5 守恒平衡"""
        if flip_idx < 0 or flip_idx >= self.N:
            return False, "A1: invalid flip_idx"
        if state[flip_idx] == 1:
            return False, "A1: 1→0 forbidden (monotonicity), need A5 balance"
        return True, "ok"
    
    # ================================================================
    # A4: 最小变易 — 每步只改变一个比特
    # ================================================================
    def check_A4(self, state: np.ndarray, next_state: np.ndarray) -> Tuple[bool, str]:
        """A4: 相邻状态汉明距离必须为 1"""
        d_H = int(np.sum(state != next_state))
        if d_H != 1:
            return False, f"A4: d_H={d_H} != 1"
        return True, "ok"
    
    # ================================================================
    # A5: 差异守恒 — 注入和吸收必须平衡
    # ================================================================
    def check_A5_inject(self, state: np.ndarray, n_inject: int) -> Tuple[bool, str]:
        """A5: 注入量不能超过守恒上限"""
        w = int(np.sum(state))
        if w + n_inject > self.N:
            return False, f"A5: w={w} + inject={n_inject} > N={self.N}"
        # 长期平衡: 净流量不能超过 50%
        net = (self.total_injected + n_inject) - self.total_absorbed
        if net > self.N * 0.5:
            return False, f"A5: net_flux={net} too large"
        return True, "ok"
    
    def check_A5_absorb(self, state: np.ndarray, n_absorb: int) -> Tuple[bool, str]:
        """A5: 吸收量不能超过当前活跃位数"""
        w = int(np.sum(state))
        if n_absorb > w:
            return False, f"A5: absorb={n_absorb} > w={w}"
        return True, "ok"
    
    def record_inject(self, n: int):
        self.total_injected += n
    
    def record_absorb(self, n: int):
        self.total_absorbed += n
    
    # ================================================================
    # A6: 不可逆性 — DAG 方向累积
    # ================================================================
    def check_A6(self, state: np.ndarray, flip_idx: int) -> Tuple[bool, str]:
        """A6: 检查翻转是否符合 DAG 方向"""
        if flip_idx < 0 or flip_idx >= self.N:
            return False, "A6: invalid flip_idx"
        d = self.direction[flip_idx]
        v = state[flip_idx]
        if d == 1 and v == 1:
            return False, "A6: direction=+1 but already 1"
        if d == -1 and v == 0:
            return False, "A6: direction=-1 but already 0"
        return True, "ok"
    
    def update_A6_direction(self, flip_idx: int, old_val: int, new_val: int):
        """A6: 翻转后更新方向 (累积, 不重置)"""
        if new_val > old_val:  # 0→1
            self.direction[flip_idx] = 1
        elif new_val < old_val:  # 1→0
            self.direction[flip_idx] = -1
    
    # ================================================================
    # A7: 循环闭合 — 稳定态参与有向循环
    # ================================================================
    def check_A7(self, active_set: set) -> Tuple[bool, str]:
        """A7: 检查当前活跃集是否参与循环"""
        self.state_history.append(frozenset(active_set))
        # 简单循环检测: 如果活跃集重复出现, 则形成循环
        if len(self.state_history) >= 2:
            if self.state_history[-1] == self.state_history[-2]:
                self.cycle_participants.update(active_set)
                return True, "A7: cycle detected"
        return False, "A7: no cycle yet"
    
    # ================================================================
    # A8: 对称偏好 — 偏好 w ≈ N/2
    # ================================================================
    def get_A8_bias(self, state: np.ndarray) -> float:
        """A8: 返回偏好权重 (越高越偏好)"""
        w = int(np.sum(state))
        # 权重 = C(N,w) / C(N,N/2)
        # 对于大 N, 用对数计算
        from scipy.special import comb
        N = self.N
        w_mid = N // 2
        weight = comb(N, w, exact=True) / comb(N, w_mid, exact=True)
        return float(weight)
    
    # ================================================================
    # A9: 内生完备 — 自由度 = 公理要求的最小值
    # ================================================================
    def check_A9_sealing(self, active_set: set, organizations: dict) -> bool:
        """A9: 检查是否应该密封 (封口)"""
        if self.sealed:
            return True
        
        # 更新活跃位追踪
        for b in active_set:
            self.active_bits_history[b] = self.current_step
            self.total_unique_active.add(b)
        
        # 密封条件: 足够多的位曾经活跃 + 有组织
        if (len(self.total_unique_active) >= self.N * 0.75
                and len(organizations) >= 1):
            self.sealed = True
            self.sealed_bits = set(active_set)
            return True
        
        return False
    
    def step(self):
        """每步调用, 更新内部状态"""
        self.current_step += 1
    
    def get_summary(self) -> dict:
        """返回公理状态摘要"""
        return {
            'N': self.N,
            'step': self.current_step,
            'sealed': self.sealed,
            'total_injected': self.total_injected,
            'total_absorbed': self.total_absorbed,
            'net_flux': self.total_injected - self.total_absorbed,
            'n_cycle_participants': len(self.cycle_participants),
            'n_unique_active': len(self.total_unique_active),
            'n_sealed_bits': len(self.sealed_bits),
        }
