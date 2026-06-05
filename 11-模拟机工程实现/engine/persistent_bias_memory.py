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

保持的可重调用性（Retention Revocability）：
- ABA §3.3：保持不是惰性标记，而是能偏置未来构型的操作力
- 保持深度 = 偏置信号在经历 N 次重建循环后仍有效的比例
- 当前深度为 0 表示仅影响下一步；深度 >= 3 表示跨多步持续影响
"""

import torch
import numpy as np
from typing import List, Optional, Dict, Deque, Tuple
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

    # 保持可重调用性追踪
    n_reconstruction_cycles: int = 0        # 经历的重建循环次数
    n_successful_reinvocations: int = 0     # 成功重调用次数
    first_active_timestamp: int = 0         # 首次激活时间戳
    last_active_timestamp: int = 0          # 最近激活时间戳

    def decay(self):
        """衰减偏置强度（仅对未冻结的条目）"""
        if not self.is_frozen:
            self.current_strength *= self.decay_rate
        return self.current_strength

    @property
    def is_active(self) -> bool:
        """是否仍然有效（强度 > 阈值）"""
        return self.current_strength > 1e-4

    @property
    def retention_depth(self) -> float:
        """保持深度 = 成功重调用次数 / 重建循环次数

        衡量偏置信号在多次重建循环中的持续有效性。
        - 0.0: 仅影响下一步（无重调用）
        - (0, 1): 部分重建循环中保持有效
        - 1.0: 所有重建循环中均保持有效（完美保持）
        """
        if self.n_reconstruction_cycles == 0:
            return 0.0
        return self.n_successful_reinvocations / self.n_reconstruction_cycles

    @property
    def retention_span(self) -> int:
        """保持跨度 = 最近激活 - 首次激活（时间步数）

        衡量偏置信号在时间维度上的持续范围。
        """
        if self.first_active_timestamp == 0:
            return 0
        return self.last_active_timestamp - self.first_active_timestamp

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


@dataclass
class RetentionDepthRecord:
    """单条保持深度记录（对应一次重建循环的评估结果）"""
    entry_id: str
    cycle_index: int                        # 重建循环序号
    strength_before: float                  # 重建前强度
    strength_after: float                   # 重建后强度
    was_reinvoked: bool                     # 是否被成功重调用
    cosine_similarity: float                # 重建前后偏置方向余弦相似度
    timestamp: int                          # 评估时间戳

    @property
    def strength_ratio(self) -> float:
        """重建后/重建前强度比"""
        if self.strength_before < 1e-8:
            return 0.0
        return self.strength_after / self.strength_before


class RetentionDepthTracker:
    """保持深度追踪器

    追踪偏置条目在多次重建循环中的持续有效性。

    理论依据（ABA §3.3）：
    - 保持不是"专用检索系统"，而是"差异路径的持续偏置"
    - 保持的可重调用性：偏置需要在递归重建中持续存在
    - 保持深度指标：测量偏置信号在经历 N 次重建循环后仍然有效的比例

    工作流程：
    1. register_cycle() — 注册一次重建循环，记录重建前后偏置状态
    2. 自动更新 BiasEntry 的 n_reconstruction_cycles 和 n_successful_reinvocations
    3. get_retention_stats() — 获取保持深度统计
    """

    def __init__(self, similarity_threshold: float = 0.7,
                 strength_persistence_threshold: float = 0.3):
        """
        Args:
            similarity_threshold: 余弦相似度阈值，高于此值视为方向一致
            strength_persistence_threshold: 强度持续阈值，
                重建后/重建前强度比高于此值视为有效保持
        """
        self.similarity_threshold = similarity_threshold
        self.strength_persistence_threshold = strength_persistence_threshold

        # 保持深度记录 {entry_id: [RetentionDepthRecord]}
        self._records: Dict[str, List[RetentionDepthRecord]] = {}

        # 当前循环序号（全局递增）
        self._cycle_index: int = 0

        # 每个条目的重建前状态快照 {entry_id: (strength, bias_vector)}
        self._pre_cycle_snapshots: Dict[str, Tuple[float, torch.Tensor]] = {}

    def begin_cycle(self, entries: List[BiasEntry]):
        """记录重建循环前的偏置状态快照

        Args:
            entries: 当前所有活跃的偏置条目
        """
        self._pre_cycle_snapshots.clear()
        for entry in entries:
            if entry.is_active:
                self._pre_cycle_snapshots[entry.entry_id] = (
                    entry.current_strength,
                    entry.bias_vector.clone(),
                )

    def end_cycle(self, entries: List[BiasEntry], timestamp: int) -> Dict[str, bool]:
        """评估重建循环后的保持深度

        对每个在前快照中存在的条目：
        1. 计算重建前后偏置方向的余弦相似度
        2. 计算重建后/重建前强度比
        3. 判断是否被成功重调用（方向一致且强度持续）

        Args:
            entries: 重建后的活跃偏置条目
            timestamp: 当前时间戳

        Returns:
            reinvocation_results: {entry_id: was_reinvoked}
        """
        self._cycle_index += 1
        results: Dict[str, bool] = {}

        # 构建重建后条目的查找表
        post_entries = {e.entry_id: e for e in entries if e.is_active}

        for entry_id, (pre_strength, pre_vector) in self._pre_cycle_snapshots.items():
            post_entry = post_entries.get(entry_id)

            if post_entry is not None:
                # 条目仍然存在且活跃
                post_strength = post_entry.current_strength
                post_vector = post_entry.bias_vector

                # 计算方向余弦相似度
                cos_sim = self._cosine_similarity(pre_vector, post_vector)

                # 计算强度比
                strength_ratio = post_strength / max(pre_strength, 1e-8)

                # 判断是否成功重调用
                was_reinvoked = (
                    cos_sim >= self.similarity_threshold and
                    strength_ratio >= self.strength_persistence_threshold
                )

                record = RetentionDepthRecord(
                    entry_id=entry_id,
                    cycle_index=self._cycle_index,
                    strength_before=pre_strength,
                    strength_after=post_strength,
                    was_reinvoked=was_reinvoked,
                    cosine_similarity=cos_sim,
                    timestamp=timestamp,
                )
                results[entry_id] = was_reinvoked

                # 更新 BiasEntry 的追踪计数
                post_entry.n_reconstruction_cycles = max(
                    post_entry.n_reconstruction_cycles, self._cycle_index)
                if was_reinvoked:
                    post_entry.n_successful_reinvocations += 1
                if post_entry.first_active_timestamp == 0:
                    post_entry.first_active_timestamp = timestamp
                post_entry.last_active_timestamp = timestamp

            else:
                # 条目已失效或被移除
                record = RetentionDepthRecord(
                    entry_id=entry_id,
                    cycle_index=self._cycle_index,
                    strength_before=pre_strength,
                    strength_after=0.0,
                    was_reinvoked=False,
                    cosine_similarity=0.0,
                    timestamp=timestamp,
                )
                results[entry_id] = False

            # 保存记录
            if entry_id not in self._records:
                self._records[entry_id] = []
            self._records[entry_id].append(record)

        return results

    def get_retention_stats(self, entry_id: str) -> Optional[Dict]:
        """获取单条偏置的保持深度统计

        Args:
            entry_id: 偏置条目 ID

        Returns:
            stats: 保持深度统计字典，无记录则返回 None
        """
        records = self._records.get(entry_id, [])
        if not records:
            return None

        n_cycles = len(records)
        n_reinvoked = sum(1 for r in records if r.was_reinvoked)
        avg_similarity = sum(r.cosine_similarity for r in records) / n_cycles
        avg_strength_ratio = sum(r.strength_ratio for r in records) / n_cycles

        return {
            'entry_id': entry_id,
            'n_cycles': n_cycles,
            'n_successful_reinvocations': n_reinvoked,
            'retention_depth': n_reinvoked / n_cycles if n_cycles > 0 else 0.0,
            'avg_direction_similarity': avg_similarity,
            'avg_strength_ratio': avg_strength_ratio,
            'latest_strength_ratio': records[-1].strength_ratio,
            'is_deep_retention': n_reinvoked >= 3 and n_cycles >= 3,
        }

    def get_all_retention_stats(self) -> Dict[str, Dict]:
        """获取所有条目的保持深度统计"""
        return {
            entry_id: stats
            for entry_id in self._records
            if (stats := self.get_retention_stats(entry_id)) is not None
        }

    def get_aggregate_retention_depth(self) -> float:
        """获取聚合保持深度（所有条目的平均保持深度）"""
        stats_list = self.get_all_retention_stats()
        if not stats_list:
            return 0.0
        return sum(s['retention_depth'] for s in stats_list.values()) / len(stats_list)

    def get_deep_retention_entries(self) -> List[str]:
        """获取具有深度保持的条目 ID 列表（重调用 >= 3 次）"""
        return [
            entry_id for entry_id, stats in self.get_all_retention_stats().items()
            if stats['is_deep_retention']
        ]

    @property
    def n_cycles_tracked(self) -> int:
        """已追踪的重建循环数"""
        return self._cycle_index

    def _cosine_similarity(self, a: torch.Tensor, b: torch.Tensor) -> float:
        """计算两个向量的余弦相似度"""
        a_flat = a.flatten()
        b_flat = b.flatten()

        # 对齐长度
        min_len = min(len(a_flat), len(b_flat))
        if min_len == 0:
            return 0.0
        a_flat = a_flat[:min_len]
        b_flat = b_flat[:min_len]

        dot = (a_flat * b_flat).sum().item()
        norm_a = (a_flat * a_flat).sum().item() ** 0.5
        norm_b = (b_flat * b_flat).sum().item() ** 0.5

        if norm_a < 1e-8 or norm_b < 1e-8:
            return 0.0
        return dot / (norm_a * norm_b)


class PersistentBiasMemory:
    """历史累积偏置记忆

    记录路径偏置的历史累积，使过去通过结构对未来施加持续限制。

    核心功能：
    1. record(): 记录一次偏置
    2. get_accumulated(): 获取当前累积偏置
    3. freeze() / unseal(): 冻结/解冻偏置
    4. get_historical(): 获取历史偏置序列
    5. begin_reconstruction_cycle() / end_reconstruction_cycle(): 重建循环追踪
    6. get_retention_stats(): 获取保持深度统计
    """

    def __init__(self, max_history_depth: int = 100,
                 decay_rate: float = 0.95,
                 freeze_threshold: float = 0.8,
                 snapshot_interval: int = 10,
                 retention_similarity_threshold: float = 0.7,
                 retention_strength_threshold: float = 0.3,
                 enable_retention_tracking: bool = True):
        """
        Args:
            max_history_depth: 历史保留深度（最大条目数）
            decay_rate: 默认时间衰减率
            freeze_threshold: 偏置强度超过此值时自动冻结
            snapshot_interval: 快照间隔（每 N 次记录取一次快照）
            retention_similarity_threshold: 保持追踪的余弦相似度阈值
            retention_strength_threshold: 保持追踪的强度持续阈值
            enable_retention_tracking: 是否启用保持深度追踪
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

        # 保持深度追踪器
        self._enable_retention_tracking = enable_retention_tracking
        self._retention_tracker = RetentionDepthTracker(
            similarity_threshold=retention_similarity_threshold,
            strength_persistence_threshold=retention_strength_threshold,
        )

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

    def begin_reconstruction_cycle(self):
        """开始一次重建循环 — 记录当前偏置状态快照

        必须在重建操作之前调用。
        用于追踪保持的可重调用性（ABA §3.3）。

        工作流程：
        memory.begin_reconstruction_cycle()
        # ... 执行重建操作 ...
        memory.end_reconstruction_cycle(timestamp)
        """
        if not self._enable_retention_tracking:
            return
        active = [e for e in self._entries if e.is_active]
        self._retention_tracker.begin_cycle(active)

    def end_reconstruction_cycle(self, timestamp: int) -> Dict[str, bool]:
        """结束一次重建循环 — 评估保持深度

        必须在重建操作之后调用。

        Args:
            timestamp: 当前时间戳

        Returns:
            reinvocation_results: {entry_id: was_reinvoked}
        """
        if not self._enable_retention_tracking:
            return {}
        active = [e for e in self._entries if e.is_active]
        return self._retention_tracker.end_cycle(active, timestamp)

    def get_retention_stats(self, entry_id: str) -> Optional[Dict]:
        """获取单条偏置的保持深度统计

        Args:
            entry_id: 偏置条目 ID

        Returns:
            stats: 保持深度统计字典
        """
        return self._retention_tracker.get_retention_stats(entry_id)

    def get_all_retention_stats(self) -> Dict[str, Dict]:
        """获取所有条目的保持深度统计"""
        return self._retention_tracker.get_all_retention_stats()

    def get_aggregate_retention_depth(self) -> float:
        """获取聚合保持深度（所有条目的平均保持深度）"""
        return self._retention_tracker.get_aggregate_retention_depth()

    def get_deep_retention_entries(self) -> List[str]:
        """获取具有深度保持的条目 ID 列表（重调用 >= 3 次）"""
        return self._retention_tracker.get_deep_retention_entries()

    @property
    def n_cycles_tracked(self) -> int:
        """已追踪的重建循环数"""
        return self._retention_tracker.n_cycles_tracked

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
                vec = entry.bias_vector
                # 防御：如果存储的偏置向量长度与目标 n_bits 不一致，自动调整
                # 场景：空间演化器将 N 对齐到 3 的倍数后，存储的偏置向量长度可能变化
                if vec.shape[0] != n_bits:
                    if vec.shape[0] > n_bits:
                        vec = vec[:n_bits]  # 截断
                    else:
                        # 补零到目标长度
                        padded = torch.zeros(n_bits, device=vec.device, dtype=vec.dtype)
                        padded[:vec.shape[0]] = vec
                        vec = padded
                accumulated += vec * effective_strength
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
            'retention_tracking_enabled': self._enable_retention_tracking,
            'n_cycles_tracked': self.n_cycles_tracked,
            'aggregate_retention_depth': self.get_aggregate_retention_depth(),
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
        self._retention_tracker = RetentionDepthTracker(
            similarity_threshold=self._retention_tracker.similarity_threshold,
            strength_persistence_threshold=self._retention_tracker.strength_persistence_threshold,
        )
