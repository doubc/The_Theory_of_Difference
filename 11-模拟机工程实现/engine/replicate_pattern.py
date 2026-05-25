"""
engine/replicate_pattern.py — 复制模式 (ReplicatePattern)

Phase 2 P2 组件 #4

职责：实现"带着差异的延续"——复制保留关键关系，允许细节偏差。

理论依据：
- 《象界》第五章：再现 → 复制
  "复制不是同一物的再生，而是差异样式在变化中的延续。"
  "复制保留的是关键关系，不是所有细节；它允许的是组织方式的重构，不是原样的复印。"
- 《Appearing Before Appearing》§3.4：复制保真度
  "模式从条件依赖的重复变为相对条件独立的自我再生"

核心区分：
- 再现（reappearance）：依赖外部条件的重复
- 复制（replication）：内部支撑的样式延续

关键关系 vs 所有细节：
- 关键关系 = 组件之间的结构关系（拓扑、因果、时间序列）
- 所有细节 = 每个组件的具体状态值
- 复制保真 = 关键关系的保留程度（不是状态的完全一致）

工程指标：
- 复制保真度 = structural_similarity(key_relations_original, key_relations_replicated)
- 关键关系保留率 = 被保留的关键关系数 / 总关键关系数
- 细节偏差度 = 非关键细节的变化量（允许的）
- 跨实例稳定性 = 多次复制后关键关系的保持程度

语义防火墙：
- "复制" ≠ "自我表征"（没有自我模型）
- "复制" ≠ "同一性"（允许差异）
- 复制只是"差异样式在变化中的延续"
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field


@dataclass
class KeyRelation:
    """关键关系

    关键关系是组件之间的结构关系，而非组件的具体状态值。

    类型：
    - "topological": 拓扑关系（邻接、连通性）
    - "causal": 因果关系（A 的状态影响 B 的状态）
    - "temporal": 时间关系（A 在 B 之前/之后发生）
    - "binding": 绑定关系（A 和 B 被绑定在一起）
    """
    relation_type: str       # 关系类型
    source: str              # 源组件
    target: str              # 目标组件
    strength: float = 1.0    # 关系强度

    def __eq__(self, other):
        if not isinstance(other, KeyRelation):
            return False
        return (self.relation_type == other.relation_type and
                self.source == other.source and
                self.target == other.target)

    def __hash__(self):
        return hash((self.relation_type, self.source, self.target))


@dataclass
class ReplicationResult:
    """复制结果"""
    fidelity: float = 0.0           # 复制保真度 [0, 1]
    key_relations_preserved: int = 0  # 保留的关键关系数
    key_relations_total: int = 0    # 总关键关系数
    detail_deviation: float = 0.0   # 细节偏差度
    is_successful: bool = False     # 是否成功复制
    n_structural_changes: int = 0   # 结构变化数


class ReplicatePattern:
    """复制模式

    实现"带着差异的延续"——复制保留关键关系，允许细节偏差。

    核心逻辑：
    1. 从原始模式中提取关键关系
    2. 执行复制过程（可能引入差异）
    3. 从复制模式中提取关键关系
    4. 比较关键关系的保留程度 → 复制保真度
    5. 允许非关键细节的变化

    复制保真的判定：
    - 保真度超过阈值（默认 0.6）
    - 关键关系保留率超过阈值（默认 0.7）

    与 SixThresholdDetector 的关系：
    - SixThresholdDetector 使用 replicated_pattern 和 original_pattern
    - ReplicatePattern 提供更精细的关键关系保真度计算

    与 SelfSustainingCirculation 的关系：
    - SelfSustainingCirculation 检测扰动后重建的能力
    - ReplicatePattern 检测模式跨实例传递的能力
    - 两者共同构成"延续"的不同维度
    """

    def __init__(self,
                 fidelity_threshold: float = 0.6,
                 key_relation_threshold: float = 0.7,
                 max_instances: int = 100):
        """
        Args:
            fidelity_threshold: 复制保真度阈值
            key_relation_threshold: 关键关系保留率阈值
            max_instances: 最大实例数
        """
        self.fidelity_threshold = fidelity_threshold
        self.key_relation_threshold = key_relation_threshold
        self.max_instances = max_instances

        # 原始模式的关键关系
        self._original_relations: Set[KeyRelation] = set()

        # 复制历史
        self._replication_history: List[ReplicationResult] = []

        # 实例列表（每次复制产生一个实例）
        self._instances: List[Dict] = []

        # 步数
        self._step_count: int = 0

    def extract_key_relations(self, state: torch.Tensor,
                              binding_strength: Optional[torch.Tensor] = None,
                              active_bits: Optional[Set[int]] = None
                              ) -> Set[KeyRelation]:
        """从状态中提取关键关系

        提取策略：
        1. 拓扑关系：相邻比特之间的邻接关系
        2. 绑定关系：绑定强度超过阈值的比特对
        3. 因果关系：同时激活的比特对（简化版）

        Args:
            state: 状态向量
            binding_strength: 绑定强度矩阵
            active_bits: 活跃比特集合

        Returns:
            key_relations: 关键关系集合
        """
        relations = set()
        n = len(state)
        active = active_bits if active_bits is not None else set(range(n))

        # 拓扑关系：相邻比特
        sorted_active = sorted(active)
        for i in range(len(sorted_active) - 1):
            a, b = sorted_active[i], sorted_active[i + 1]
            if b - a <= 2:  # 邻近
                relations.add(KeyRelation(
                    relation_type="topological",
                    source=str(a),
                    target=str(b),
                    strength=1.0 / (b - a + 1),
                ))

        # 绑定关系：高绑定强度的比特对
        if binding_strength is not None:
            for i in sorted_active:
                for j in sorted_active:
                    if i < j and binding_strength[i][j].item() > 0.1:
                        relations.add(KeyRelation(
                            relation_type="binding",
                            source=str(i),
                            target=str(j),
                            strength=binding_strength[i][j].item(),
                        ))

        # 因果关系：同时激活的比特对（简化）
        active_ones = [i for i in sorted_active if state[i].item() > 0.5]
        for i in range(len(active_ones)):
            for j in range(i + 1, len(active_ones)):
                a, b = active_ones[i], active_ones[j]
                relations.add(KeyRelation(
                    relation_type="causal",
                    source=str(a),
                    target=str(b),
                    strength=0.5,  # 简化：同时激活 = 中等因果
                ))

        return relations

    def set_original(self, state: torch.Tensor,
                     binding_strength: Optional[torch.Tensor] = None,
                     active_bits: Optional[Set[int]] = None):
        """设置原始模式（被复制的源）

        Args:
            state: 原始状态
            binding_strength: 绑定强度矩阵
            active_bits: 活跃比特集合
        """
        self._original_relations = self.extract_key_relations(
            state, binding_strength, active_bits)

    def replicate(self, state: torch.Tensor,
                  noise_level: float = 0.05,
                  binding_strength: Optional[torch.Tensor] = None,
                  active_bits: Optional[Set[int]] = None) -> ReplicationResult:
        """执行复制

        复制过程：
        1. 对原始状态施加噪声（引入差异）
        2. 从复制状态中提取关键关系
        3. 与原始关键关系比较 → 保真度

        Args:
            state: 原始状态
            noise_level: 噪声水平（引入差异的程度）
            binding_strength: 绑定强度矩阵
            active_bits: 活跃比特集合

        Returns:
            ReplicationResult 复制结果
        """
        self._step_count += 1

        # 如果还没有设置原始模式，先设置
        if not self._original_relations:
            self.set_original(state, binding_strength, active_bits)

        # 施加噪声（引入差异）
        noise = torch.randn_like(state) * noise_level
        replicated_state = state + noise

        # 提取复制状态的关键关系
        replicated_relations = self.extract_key_relations(
            replicated_state, binding_strength, active_bits)

        # 计算保真度
        result = self._compute_fidelity(
            self._original_relations, replicated_relations)

        # 记录实例
        self._instances.append({
            'step': self._step_count,
            'state': replicated_state.clone(),
            'relations': replicated_relations,
            'fidelity': result.fidelity,
        })

        # 限制实例数
        if len(self._instances) > self.max_instances:
            self._instances = self._instances[-self.max_instances:]

        self._replication_history.append(result)
        return result

    def replicate_with_transform(self,
                                  state: torch.Tensor,
                                  transform_fn: callable,
                                  binding_strength: Optional[torch.Tensor] = None,
                                  active_bits: Optional[Set[int]] = None
                                  ) -> ReplicationResult:
        """使用自定义变换执行复制

        允许用户指定复制变换（如维度变化、结构重组等）。

        Args:
            state: 原始状态
            transform_fn: 变换函数 state → new_state
            binding_strength: 绑定强度矩阵
            active_bits: 活跃比特集合

        Returns:
            ReplicationResult 复制结果
        """
        self._step_count += 1

        if not self._original_relations:
            self.set_original(state, binding_strength, active_bits)

        # 应用变换
        replicated_state = transform_fn(state)

        # 提取关键关系
        replicated_relations = self.extract_key_relations(
            replicated_state, binding_strength, active_bits)

        # 计算保真度
        result = self._compute_fidelity(
            self._original_relations, replicated_relations)

        self._instances.append({
            'step': self._step_count,
            'state': replicated_state.clone(),
            'relations': replicated_relations,
            'fidelity': result.fidelity,
        })

        self._replication_history.append(result)
        return result

    def evaluate_cross_instance_stability(self) -> float:
        """评估跨实例稳定性

        计算多次复制后的关键关系保持程度。

        Returns:
            stability: 跨实例稳定性 [0, 1]
        """
        if len(self._instances) < 2:
            return 0.0

        # 比较所有实例对的关键关系重叠
        pairwise_overlaps = []
        for i in range(len(self._instances)):
            for j in range(i + 1, len(self._instances)):
                rel_i = self._instances[i]['relations']
                rel_j = self._instances[j]['relations']
                if rel_i and rel_j:
                    overlap = len(rel_i & rel_j) / max(len(rel_i | rel_j), 1)
                    pairwise_overlaps.append(overlap)

        return float(np.mean(pairwise_overlaps)) if pairwise_overlaps else 0.0

    def get_structural_similarity(self, state_a: torch.Tensor,
                                   state_b: torch.Tensor) -> float:
        """计算两个状态之间的结构相似性

        基于关键关系而非状态值。

        Args:
            state_a: 状态 A
            state_b: 状态 B

        Returns:
            similarity: 结构相似度 [0, 1]
        """
        rel_a = self.extract_key_relations(state_a)
        rel_b = self.extract_key_relations(state_b)

        if not rel_a and not rel_b:
            return 1.0  # 两者都无关系 → 完全相似
        if not rel_a or not rel_b:
            return 0.0  # 一个有关系一个没有 → 完全不相似

        intersection = len(rel_a & rel_b)
        union = len(rel_a | rel_b)
        return intersection / max(union, 1)

    def get_fidelity_for_detector(self, original: torch.Tensor,
                                   replicated: torch.Tensor) -> float:
        """获取 SixThresholdDetector 所需的复制保真度

        Args:
            original: 原始模式
            replicated: 复制模式

        Returns:
            fidelity: 复制保真度
        """
        return self.get_structural_similarity(original, replicated)

    @property
    def n_replications(self) -> int:
        """总复制次数"""
        return len(self._replication_history)

    @property
    def avg_fidelity(self) -> float:
        """平均保真度"""
        if not self._replication_history:
            return 0.0
        return float(np.mean([r.fidelity for r in self._replication_history]))

    @property
    def is_replicating(self) -> bool:
        """是否成功复制（最近一次保真度超过阈值）"""
        if not self._replication_history:
            return False
        return self._replication_history[-1].is_successful

    def get_summary(self) -> Dict:
        """获取摘要"""
        recent = self._replication_history[-10:] if self._replication_history else []
        return {
            'n_replications': self.n_replications,
            'avg_fidelity': self.avg_fidelity,
            'is_replicating': self.is_replicating,
            'cross_instance_stability': self.evaluate_cross_instance_stability(),
            'n_instances': len(self._instances),
            'n_original_relations': len(self._original_relations),
            'recent_fidelity': (
                float(np.mean([r.fidelity for r in recent])) if recent else 0.0
            ),
            'recent_key_relation_preservation': (
                float(np.mean([
                    r.key_relations_preserved / max(1, r.key_relations_total)
                    for r in recent
                ])) if recent else 0.0
            ),
        }

    def _compute_fidelity(self, original: Set[KeyRelation],
                          replicated: Set[KeyRelation]) -> ReplicationResult:
        """计算复制保真度

        Args:
            original: 原始关键关系
            replicated: 复制关键关系

        Returns:
            ReplicationResult
        """
        if not original:
            return ReplicationResult(
                fidelity=1.0 if not replicated else 0.0,
                key_relations_preserved=0,
                key_relations_total=0,
                detail_deviation=0.0,
                is_successful=True,
            )

        preserved = len(original & replicated)
        total = len(original)
        preservation_rate = preserved / total

        # 结构变化数 = 原始有但复制没有 + 复制有但原始没有
        structural_changes = len(original - replicated) + len(replicated - original)

        # 保真度 = 保留率（关键关系保留比例）
        fidelity = preservation_rate

        # 细节偏差 = 复制中新增的关系比例
        detail_deviation = len(replicated - original) / max(total, 1)

        is_successful = (fidelity > self.fidelity_threshold and
                         preservation_rate > self.key_relation_threshold)

        return ReplicationResult(
            fidelity=fidelity,
            key_relations_preserved=preserved,
            key_relations_total=total,
            detail_deviation=detail_deviation,
            is_successful=is_successful,
            n_structural_changes=structural_changes,
        )

    def reset(self):
        """重置所有状态"""
        self._original_relations.clear()
        self._replication_history.clear()
        self._instances.clear()
        self._step_count = 0
