"""core.py — 差异场 DifferenceField。

一个 DifferenceField 表示某一层级 L_k 上的离散差异世界:
    - state      : {0,1}^N   差异位 (A2 离散编码)
    - a1_source  : 差异源集合 (A1) —— 能够主动注入 0->1 的位
    - direction  : A6 流向     (+1 只允许 0->1, -1 只允许 1->0, 0 双向)
    - binding    : A1' 横向绑定矩阵 (共同反差 / Common Contrast)
    - color      : 潜在亲和标签, 决定绑定优先在同色位之间增长 -> 产生多个组织

关键: a1_source 非空 <=> 该层拥有"自己的差异源" <=> 能够自主演化(活秩序)。
原项目的致命缺陷正是: 封装(A9)只向上投影被冻结的位, 不生成新差异源,
因此 L1 的 a1_source 为空 -> Jaccard flux=0 -> 死秩序。
"""
from __future__ import annotations
import numpy as np


class DifferenceField:
    def __init__(self, N, active=None, a1_source=None, direction=None,
                 binding=None, color=None, layer=0, rng=None, naming_meta=None):
        self.N = int(N)
        self.rng = rng if rng is not None else np.random.default_rng()
        self.layer = int(layer)

        self.state = np.zeros(self.N, dtype=np.int8)
        if active is not None:
            idx = list(active)
            if idx:
                self.state[idx] = 1

        if a1_source is None:
            self.a1_source = set(np.where(self.state == 1)[0].tolist())
        else:
            self.a1_source = set(int(i) for i in a1_source)

        self.direction = (np.zeros(self.N, dtype=np.int8)
                          if direction is None else np.asarray(direction, dtype=np.int8))
        self.binding = (np.zeros((self.N, self.N), dtype=float)
                        if binding is None else np.asarray(binding, dtype=float))
        if color is None:
            self.color = self.rng.integers(0, max(1, self.N // 8 + 1), size=self.N)
        else:
            self.color = np.asarray(color)

        # 演化状态
        self.sealed = False
        self.seal_step = None
        self.sealed_bits = set()
        self.organizations = {}      # org_id -> set(bit)
        self.lock_level = np.zeros(self.N, dtype=float)
        self.candidates = set()      # 先天完备性: 本步候选翻转空间
        self.flux_budget = 0         # 守恒: 本步允许的净翻转预算
        self.active_history = []     # 每步活跃集合 (计算 Jaccard flux)
        self._cycle_counter = 0
        self.naming_meta = naming_meta or {}   # 自指来源信息
        self.encapsulated = False    # A9 是否已对本层执行过封装

    # --- helpers ---
    def active_set(self):
        return set(np.where(self.state == 1)[0].tolist())

    def n_active(self):
        return int(self.state.sum())

    def record(self):
        self.active_history.append(self.active_set())

    def admissible(self, bit):
        """A6: 某位是否允许翻转 (考虑流向与是否已冻结)。"""
        if bit in self.sealed_bits:
            return False
        d = self.direction[bit]
        v = self.state[bit]
        if d == 1:   # 只允许 0->1
            return v == 0
        if d == -1:  # 只允许 1->0
            return v == 1
        return True  # 双向
