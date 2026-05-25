"""
engine/persistent_bias_memory.py — 历史累积偏置记忆 (PersistentBiasMemory)

Phase 2 P0 组件 #2

职责：记录路径偏置的历史累积，使过去通过结构对未来施加持续限制。
这是"历史进入结构"的关键，是前主体态的必要条件。

理论依据：
- 《象界》第四章：痕迹 → 记忆
- 偏置不是单次事件，而是"跨多次重构连续偏置"
- 偏置携带时间衰减因子，但核心结构偏置可长期保留
- 支持偏置的"冻结"与"解冻"（对应解封机制）

与现有 BiasField 的关系：
- BiasField 是同步的、当下的偏置传播（M4 已有）
- PersistentBiasMemory 是异步的、历史的偏置累积（Phase 2 新增）
- 两者通过 apply_bias() 接口统一：当前偏置 = 同步偏置 + 历史累积偏置
"""

import torch
import numpy as np
from typing import List, Optional, Dict, Deque
from dataclasses import dataclass, field
from collections import deque
from engine.hierarchy_manager import BiasField


@dataclass
class BiasEntry:
    """单条偏置记录"""
    entry_id: str                           # 唯一标识
    source_layer: int                       # 来源层
    target_layer: int                       # 目标层
    bias_vector: torch.Tensor               # 偏置向量
    initial_strength: float                 # 初始强度
    current_strength: float                 # 当前强度（衰减后）
    timestamp: int                          # 记录时间戳
    decay_rate: float                       # 衰减率
    is_frozen: bool = False                 # 是否被冻结
    metadata: Dict = field(default_factory=dict)  # 附加信息

    def decay(self):
        """衰减偏置强度（仅对未冻结的条目）"""
        if not self.is_frozen:
            self.current_strength *= self.decay_rate
        return self.current_strength

    @property
    def is_active(self) -> bool:
        """是否仍然有效（强度 > 阈值）"""
        return self.current_strength > 1e-4

    def __repr__(self):
        frozen_tag = " [FROZEN]" if self.is_frozen else ""
        return (f"BiasEntry({self.entry_id}, L{self.source_layer}->L{self.target_layer}, "
                f"str={self.current_strength:.4f}{frozen_tag})")


@dataclass
class BiasFieldSnapshot:
    """偏置场快照（用于历史回溯）"""
    timestamp: int
    accumulated_vector: torch.Tensor
    n_active_entries: int
    n_frozen_entries: int
    total_strength: float


class PersistentBiasMemory:
    """历史累积偏置记忆

    记录路径偏置的历史累积，使过去通过结构对未来施加持续限制。

    核心功能：
    1. record(): 记录一次偏置
    2. get_accumulated(): 获取当前累积偏置
    3. freeze() / unseal(): 冻结/解冻偏置
    4. get_historical(): 获取历史偏置序列
    """

    def __init__(self, max_history_depth: int = 100,
                 decay_rate: float = 0.95,
                 freeze_threshold: float = 0.8,
                 snapshot_interval: int = 10):
        """
        Args:
            max_history_depth: 历史保留深度（最大条目数）
            decay_rate: 默认时间衰减率
            freeze_threshold: 偏置强度超过此值时自动冻结
            snapshot_interval: 快照间隔（每 N 次记录取一次快照）
        """
        self.max_history_depth = max_history_depth
        self.decay_rate = decay_rate
        self.freeze_threshold = freeze_threshold
        self.snapshot_interval = snapshot_interval

        # 偏置条目列表（按时间排序）
        self._entries: List[BiasEntry] = []

        # 按层分组的偏置索引 {target_layer: [entry_indices]}
        self._layer_index: Dict[int, List[int]] = {}

        # 历史快照
        self._history: Deque[BiasFieldSnapshot] = deque(maxlen=max_history_depth)

        # 当前累积偏置场缓存
        self._cached_accumulated: Optional[torch.Tensor] = None
        self._cached_target_layer: Optional[int] = None
        self._cache_dirty: bool = True

        # 计数器
        self._record_count: int = 0
        self._next_entry_id: int = 0

    def record(self, bias_field: BiasField, timestamp: int,
               metadata: Optional[Dict] = None) -> str:
        """记录一次偏置

        Args:
            bias_field: 偏置场（来自 BiasField）
            timestamp: 当前时间戳
            metadata: 附加信息

        Returns:
            entry_id: 新条目的唯一标识
        """
        entry_id = f"bias_{self._next_entry_id:06d}"
        self._next_entry_id += 1

        entry = BiasEntry(
            entry_id=entry_id,
            source_layer=bias_field.source_layer,
            target_layer=bias_field.target_layer,
            bias_vector=bias_field.bias_vector.clone(),
            initial_strength=bias_field.strength,
            current_strength=bias_field.strength,
            timestamp=timestamp,
            decay_rate=self.decay_rate,
            is_frozen=bias_field.strength >= self.freeze_threshold,
            metadata=metadata or {},
        )

        self._entries.append(entry)
        self._record_count += 1

        # 更新层索引
        target = entry.target_layer
        if target not in self._layer_index:
            self._layer_index[target] = []
        self._layer_index[target].append(len(self._entries) - 1)

        # 标记缓存失效
        self._cache_dirty = True

        # 按间隔取快照
        if self._record_count % self.snapshot_interval == 0:
            self._take_snapshot()

        # 裁剪超出历史深度的条目
        self._trim_history()

        return entry_id

    def get_accumulated(self, target_layer: int,
                        n_bits: Optional[int] = None) -> torch.Tensor:
        """获取目标层的当前累积偏置

        累积偏置 = 所有活跃条目的偏置向量按强度加权和

        Args:
            target_layer: 目标层 ID
            n_bits: 偏置向量长度（首次调用时需要）

        Returns:
            accumulated: 累积偏置向量
        """
        # 检查缓存
        if (not self._cache_dirty and
                self._cached_target_layer == target_layer and
                self._cached_accumulated is not None):
            return self._cached_accumulated

        # 获取目标层的所有活跃条目
        active_entries = self._get_active_entries(target_layer)

        if not active_entries:
            if n_bits is not None:
                return torch.zeros(n_bits)
            return torch.zeros(0)

        # 确定向量长度
        if n_bits is None:
            n_bits = len(active_entries[0].bias_vector)

        # 加权累积
        accumulated = torch.zeros(n_bits)
        total_strength = 0.0

        for entry in active_entries:
            # 先衰减
            effective_strength = entry.decay()
            if entry.is_active:
                accumulated += entry.bias_vector * effective_strength
                total_strength += effective_strength

        # 归一化
        if total_strength > 1e-8:
            accumulated = accumulated / total_strength

        # 更新缓存
        self._cached_accumulated = accumulated
        self._cached_target_layer = target_layer
        self._cache_dirty = False

        return accumulated

    def freeze(self, entry_id: str) -> bool:
        """冻结某条偏置（使其不受衰减影响）

        Args:
            entry_id: 条目 ID

        Returns:
            success: 是否成功冻结
        """
        for entry in self._entries:
            if entry.entry_id == entry_id:
                entry.is_frozen = True
                return True
        return False

    def unseal(self, entry_id: str) -> Optional[torch.Tensor]:
        """解封被冻结的偏置，返回其偏置场

        Args:
            entry_id: 条目 ID

        Returns:
            bias_vector: 解封的偏置向量，未找到则返回 None
        """
        for entry in self._entries:
            if entry.entry_id == entry_id:
                if entry.is_frozen:
                    entry.is_frozen = False
                    self._cache_dirty = True
                    return entry.bias_vector.clone()
                return None  # 未被冻结
        return None  # 未找到

    def get_historical(self, target_layer: int,
                       depth: int = 10) -> List[torch.Tensor]:
        """获取目标层的历史偏置序列

        Args:
            target_layer: 目标层 ID
            depth: 返回最近多少条

        Returns:
            history: 历史偏置向量列表（按时间排序）
        """
        indices = self._layer_index.get(target_layer, [])
        recent_indices = indices[-depth:]

        result = []
        for idx in recent_indices:
            entry = self._entries[idx]
            result.append(entry.bias_vector.clone())

        return result

    def get_snapshots(self, last_n: int = 10) -> List[BiasFieldSnapshot]:
        """获取最近的快照"""
        return list(self._history)[-last_n:]

    @property
    def n_entries(self) -> int:
        """总条目数"""
        return len(self._entries)

    @property
    def n_active_entries(self) -> int:
        """活跃条目数"""
        return sum(1 for e in self._entries if e.is_active)

    @property
    def n_frozen_entries(self) -> int:
        """冻结条目数"""
        return sum(1 for e in self._entries if e.is_frozen)

    def get_summary(self) -> Dict:
        """获取摘要"""
        return {
            'n_entries': self.n_entries,
            'n_active': self.n_active_entries,
            'n_frozen': self.n_frozen_entries,
            'n_snapshots': len(self._history),
            'record_count': self._record_count,
            'target_layers': list(self._layer_index.keys()),
        }

    def _get_active_entries(self, target_layer: int) -> List[BiasEntry]:
        """获取目标层的所有活跃条目"""
        indices = self._layer_index.get(target_layer, [])
        return [self._entries[i] for i in indices if self._entries[i].is_active]

    def _take_snapshot(self):
        """取当前快照"""
        for target_layer in self._layer_index:
            active = self._get_active_entries(target_layer)
            if not active:
                continue

            n_bits = len(active[0].bias_vector)
            accumulated = torch.zeros(n_bits)
            total_strength = 0.0
            n_frozen = 0

            for entry in active:
                accumulated += entry.bias_vector * entry.current_strength
                total_strength += entry.current_strength
                if entry.is_frozen:
                    n_frozen += 1

            if total_strength > 1e-8:
                accumulated = accumulated / total_strength

            snapshot = BiasFieldSnapshot(
                timestamp=self._record_count,
                accumulated_vector=accumulated,
                n_active_entries=len(active),
                n_frozen_entries=n_frozen,
                total_strength=total_strength,
            )
            self._history.append(snapshot)

    def _trim_history(self):
        """裁剪超出历史深度的条目"""
        if len(self._entries) <= self.max_history_depth:
            return

        # 保留最近的条目，但始终保留冻结的条目
        n_remove = len(self._entries) - self.max_history_depth
        frozen_indices = [i for i, e in enumerate(self._entries) if e.is_frozen]
        removable = [i for i in range(len(self._entries))
                     if i not in frozen_indices and self._entries[i].is_active is False or
                     (i not in frozen_indices and not self._entries[i].is_active)]

        # 只移除已失效的非冻结条目
        to_remove = set(removable[:n_remove])

        if not to_remove:
            return

        # 重建条目列表和索引
        new_entries = []
        old_to_new = {}
        for i, entry in enumerate(self._entries):
            if i not in to_remove:
                old_to_new[i] = len(new_entries)
                new_entries.append(entry)

        self._entries = new_entries

        # 重建层索引
        self._layer_index.clear()
        for new_idx, entry in enumerate(self._entries):
            target = entry.target_layer
            if target not in self._layer_index:
                self._layer_index[target] = []
            self._layer_index[target].append(new_idx)

        self._cache_dirty = True

    def reset(self):
        """重置所有状态"""
        self._entries.clear()
        self._layer_index.clear()
        self._history.clear()
        self._cached_accumulated = None
        self._cached_target_layer = None
        self._cache_dirty = True
        self._record_count = 0
        self._next_entry_id = 0
