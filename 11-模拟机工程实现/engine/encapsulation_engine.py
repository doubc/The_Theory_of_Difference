"""
engine/encapsulation_engine.py — 分层封装引擎

将 A9 封口后的冻结比特分组封装为高层级比特。
对应差异论九机制中的"层级"机制：聚簇上升为层级。

核心流程：
1. 读取当前层的 frozen_bits 和 binding_strength 矩阵
2. 用 Union-Find 将高绑定强度的冻结比特分组
3. 每组封装为一个高层级比特（多数表决）
4. 生成索引映射关系（低层→高层）
5. 封装比特可以随基底状态变化更新（解封检测）

数据流：
Layer L → A9 封口 → frozen_bits → 分组 → 封装 → Layer L+1
"""

import torch
import numpy as np
from typing import List, Optional, Tuple, Dict, Set


class UnionFind:
    """并查集，用于绑定强度图连通分量分组"""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # 路径压缩
            x = self.parent[x]
        return x

    def union(self, x: int, y: int):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def groups(self) -> Dict[int, List[int]]:
        """返回所有连通分量 {root: [members]}"""
        result: Dict[int, List[int]] = {}
        for i in range(len(self.parent)):
            r = self.find(i)
            if r not in result:
                result[r] = []
            result[r].append(i)
        return result


class EncapsulatedBit:
    """一个高层级比特，由低层多个冻结比特封装而来"""

    def __init__(self, bit_id: int, layer: int,
                 source_bits: List[int], initial_value: float,
                 binding_score: float):
        self.bit_id = bit_id          # 在高层级中的索引
        self.layer = layer            # 所在层级
        self.source_bits = source_bits  # 低层比特索引列表
        self.value = initial_value    # 当前值 (0.0 或 1.0)
        self.binding_score = binding_score  # 封装组的平均绑定强度
        self.is_frozen = False        # 是否被再次冻结（高层级封口）
        self.direction = 0            # A6 DAG方向

    def update_value(self, base_state: torch.Tensor):
        """根据基底状态更新封装比特值（多数表决）"""
        if not self.source_bits:
            return
        ones = sum(1 for i in self.source_bits if base_state[i] > 0.5)
        self.value = 1.0 if ones > len(self.source_bits) / 2 else 0.0

    def should_unseal(self, base_state: torch.Tensor, threshold: float = 0.5) -> bool:
        """检测是否应该解封：基底状态变化导致封装值变化超过阈值"""
        if not self.source_bits:
            return False
        ones = sum(1 for i in self.source_bits if base_state[i] > 0.5)
        new_value = 1.0 if ones > len(self.source_bits) / 2 else 0.0
        return abs(new_value - self.value) > threshold

    def __repr__(self):
        return (f"EncapsulatedBit(id={self.bit_id}, L={self.layer}, "
                f"sources={self.source_bits}, val={self.value:.0f}, "
                f"bind={self.binding_score:.3f})")


class IndexMapping:
    """层级间比特索引映射"""

    def __init__(self):
        # 低层索引 → 高层索引（-1 表示被冻结封装）
        self.low_to_high: Dict[int, int] = {}
        # 高层封装比特 → 低层源比特列表
        self.high_to_low: Dict[int, List[int]] = {}
        # 活跃比特直接映射（低层索引 == 高层索引，直到重新编号）
        self.active_to_high: Dict[int, int] = {}

    def map_active(self, low_idx: int, high_idx: int):
        self.low_to_high[low_idx] = high_idx
        self.active_to_high[low_idx] = high_idx

    def map_encapsulated(self, high_idx: int, low_bits: List[int]):
        self.high_to_low[high_idx] = low_bits
        for b in low_bits:
            self.low_to_high[b] = high_idx

    def get_high_idx(self, low_idx: int) -> int:
        return self.low_to_high.get(low_idx, -1)

    def get_low_bits(self, high_idx: int) -> List[int]:
        return self.high_to_low.get(high_idx, [])


class EncapsulationEngine:
    """分层封装引擎

    职责：
    1. 将 A9 封口后的冻结比特分组封装
    2. 管理层级间索引映射
    3. 维护封装比特的值（随基底更新）
    4. 检测解封条件
    """

    def __init__(self, binding_threshold: float = 0.1,
                 min_group_size: int = 2):
        """
        Args:
            binding_threshold: 绑定强度阈值，高于此值的比特对视为连通
            min_group_size: 最小组大小，小于此值的组不封装（直接丢弃）
        """
        self.binding_threshold = binding_threshold
        self.min_group_size = min_group_size

        # 所有层级的封装比特 {layer: [EncapsulatedBit]}
        self.encapsulated_bits: Dict[int, List[EncapsulatedBit]] = {}
        # 层级间索引映射 {layer: IndexMapping}
        self.index_mappings: Dict[int, IndexMapping] = {}
        # 基底状态历史（用于解封检测）
        self.base_states: Dict[int, torch.Tensor] = {}

    def encapsulate(self, state: torch.Tensor,
                    frozen_bits: Set[int],
                    binding_strength: torch.Tensor,
                    active_bits: Set[int],
                    layer: int = 0) -> Tuple[torch.Tensor, List[EncapsulatedBit], IndexMapping]:
        """执行封装：将第 layer 层的冻结比特封装为第 layer+1 层的比特

        Args:
            state: 当前层状态 (N,)
            frozen_bits: 冻结比特索引集合
            binding_strength: 绑定强度矩阵 (N, N)
            active_bits: 活跃比特索引集合（未冻结）
            layer: 当前层级编号

        Returns:
            new_state: 新层状态 (N_new,)
            enc_bits: 新生成的封装比特列表
            mapping: 层级间索引映射
        """
        N = len(state)
        frozen_list = sorted(frozen_bits)
        active_list = sorted(active_bits)

        # ====== 1. Union-Find 分组 ======
        if frozen_list:
            # 只在冻结比特之间建索引映射
            frozen_index = {b: idx for idx, b in enumerate(frozen_list)}
            uf = UnionFind(len(frozen_list))

            for i_idx, i in enumerate(frozen_list):
                for j_idx, j in enumerate(frozen_list):
                    if i_idx < j_idx and binding_strength[i][j].item() > self.binding_threshold:
                        uf.union(i_idx, j_idx)

            groups = uf.groups()
            # 转换为原始比特索引
            raw_groups: List[List[int]] = []
            for members in groups.values():
                group = [frozen_list[m] for m in members]
                if len(group) >= self.min_group_size:
                    raw_groups.append(group)
        else:
            raw_groups = []

        # ====== 2. 生成封装比特 ======
        enc_bits: List[EncapsulatedBit] = []
        for gid, group in enumerate(raw_groups):
            # 多数表决
            ones = sum(1 for i in group if state[i] > 0.5)
            value = 1.0 if ones > len(group) / 2 else 0.0
            # 平均绑定强度
            if len(group) > 1:
                bindings = [binding_strength[i][j].item()
                           for i in group for j in group if i != j]
                avg_binding = sum(bindings) / len(bindings)
            else:
                avg_binding = 0.0

            enc = EncapsulatedBit(
                bit_id=gid,
                layer=layer + 1,
                source_bits=group,
                initial_value=value,
                binding_score=avg_binding
            )
            enc_bits.append(enc)

        # ====== 3. 构建新层状态 ======
        # 新层比特顺序：[活跃比特..., 封装比特...]
        n_active = len(active_list)
        n_enc = len(enc_bits)
        n_new = n_active + n_enc

        new_state = torch.zeros(n_new, dtype=state.dtype, device=state.device)

        # 活跃比特直接复制
        for new_idx, old_idx in enumerate(active_list):
            new_state[new_idx] = state[old_idx]

        # 封装比特
        for enc in enc_bits:
            new_idx = n_active + enc.bit_id
            new_state[new_idx] = enc.value

        # ====== 4. 构建索引映射 ======
        mapping = IndexMapping()
        for new_idx, old_idx in enumerate(active_list):
            mapping.map_active(old_idx, new_idx)
        for enc in enc_bits:
            high_idx = n_active + enc.bit_id
            mapping.map_encapsulated(high_idx, enc.source_bits)

        # ====== 5. 记录 ======
        self.encapsulated_bits[layer + 1] = enc_bits
        self.index_mappings[layer] = mapping
        self.base_states[layer] = state.clone()

        return new_state, enc_bits, mapping

    def update_encapsulated_values(self, base_state: torch.Tensor, layer: int):
        """更新指定层级的封装比特值（基底状态变化后调用）"""
        if layer + 1 not in self.encapsulated_bits:
            return
        for enc in self.encapsulated_bits[layer + 1]:
            enc.update_value(base_state)

    def check_unseal(self, base_state: torch.Tensor, layer: int,
                     threshold: float = 0.5) -> List[int]:
        """检查哪些封装比特应该解封

        Returns:
            应该解封的封装比特在高层级中的索引列表
        """
        unsealed = []
        if layer + 1 not in self.encapsulated_bits:
            return unsealed
        for enc in self.encapsulated_bits[layer + 1]:
            if not enc.is_frozen and enc.should_unseal(base_state, threshold):
                unsealed.append(enc.bit_id)
        return unsealed

    def compute_base_gravity(self, base_state: torch.Tensor,
                             layer: int) -> torch.Tensor:
        """计算基底引力势（冻结比特作为质量分布）

        用于调制高层级的源/汇权重。
        引力势 Φ(i) = -Σ_{j in frozen_ones} 1/d(i,j)

        Args:
            base_state: 基底状态
            layer: 基底层级

        Returns:
            gravity: 每个高层级比特的引力势
        """
        if layer + 1 not in self.encapsulated_bits:
            return torch.zeros(len(base_state))

        frozen_ones = [i for i in range(len(base_state))
                       if base_state[i] > 0.5]

        if not frozen_ones:
            return torch.zeros(len(base_state))

        n_high = (len(self.index_mappings[layer].active_to_high)
                  if layer in self.index_mappings else 0)

        gravity = torch.zeros(n_high)

        # 计算每个活跃比特位置的引力势
        for high_idx in range(n_high):
            # 找到低层索引
            low_idx = None
            for lo, hi in self.index_mappings[layer].active_to_high.items():
                if hi == high_idx:
                    low_idx = lo
                    break
            if low_idx is None:
                continue

            # 引力势 = -Σ 1/d_H(i, j)
            phi = 0.0
            for j in frozen_ones:
                d = abs(low_idx - j) + 1  # 避免除零
                phi -= 1.0 / d
            gravity[high_idx] = phi

        return gravity

    def get_summary(self, enc_layer: int) -> Dict:
        """获取指定封装层级的摘要

        Args:
            enc_layer: 封装比特所在的层级（= 基底层 + 1）
        """
        enc_bits = self.encapsulated_bits.get(enc_layer, [])
        base_layer = enc_layer - 1
        mapping = self.index_mappings.get(base_layer, IndexMapping())
        return {
            'enc_layer': enc_layer,
            'base_layer': base_layer,
            'n_encapsulated_bits': len(enc_bits),
            'n_active_mapped': len(mapping.active_to_high),
            'n_frozen_mapped': len(mapping.high_to_low),
            'encapsulated_bits': [
                {'id': e.bit_id, 'sources': e.source_bits,
                 'value': e.value, 'binding': e.binding_score}
                for e in enc_bits
            ]
        }
