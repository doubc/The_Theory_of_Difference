"""
models/narrative_self.py — 叙事递归算子 (NarrativeRecursionOperator)

Phase 3 P0 组件 #4 (缺失补全)

职责：实现 V1.7 形式化公式中的 N 函数，使系统能够"说出"自己正在做什么，
并根据"说出"的内容调整下一步行动，形成反馈回路。

理论依据：
- 《差异论V1.7升级提纲》：叙事递归从"方法论末位"上调为"世界生成核心机制"
- 五方法论螺旋循环：P_{t+1} = N(S(M(E(P_t))))
- 叙事递归三层：小叙事（组织行动）→ 制度正当化（稳定稳态）→ 文明级生成（改写坐标）

五中介动作（最小实现）：
1. 叙事筛选 (Narrative Filtering)   — 从差异中选择"重要差异"
2. 叙事命名 (Narrative Naming)       — 给差异赋予范畴标签
3. 叙事连接 (Narrative Connecting)   — 编织因果链
4. 叙事行动化 (Narrative Actioning)  — 转化为行动方案（偏置）
5. 叙事递归验证 (Narrative Verification) — 行动结果反馈修正叙事

与偏置算子的关系：
- 叙事递归的输出是偏置算子的修正：B'_ω = B_ω + ΔB_narrative
- 叙事不是外加的"意图"，而是差异组织内部自生的反馈信号
- 叙事验证失败时，系统应降低该叙事的权重（类似衰减）

与 Phase 2 已有组件的接口：
- 输入：PersistentBiasMemory 的历史偏置序列、ODI、解封事件
- 输出：叙事偏置修正 ΔB_narrative，写入 PersistentBiasMemory
"""

import torch
import numpy as np
from typing import List, Optional, Dict, Deque, Tuple, Set
from dataclasses import dataclass, field
from collections import deque
from enum import Enum


class NarrativeLevel(Enum):
    """叙事递归三层（V1.7）"""
    MINI_NARRATIVE = 0      # 小叙事：组织行动
    INSTITUTIONAL = 1       # 制度正当化：稳定稳态
    CIVILIZATION = 2        # 文明级生成：改写坐标


class ContentType(Enum):
    """叙事内容类型（与回流通道高语义载荷类型对齐）"""
    MEANING = "meaning"
    INSTITUTION = "institution"
    NARRATIVE = "narrative"
    IDENTITY = "identity"


@dataclass
class DifferenceSignal:
    """差异信号 — 叙事筛选的输入"""
    signal_id: str
    source_layer: int
    target_layer: int
    magnitude: float              # 差异强度
    direction: torch.Tensor       # 差异方向向量
    timestamp: int
    is_significant: bool = False  # 是否被筛选为"重要差异"


@dataclass
class NarrativeNode:
    """叙事节点 — 命名后的差异"""
    node_id: str
    original_signal_id: str
    category: str                  # 范畴标签
    content_type: ContentType      # 内容类型
    confidence: float              # 命名置信度
    timestamp: int
    parent_node_ids: List[str] = field(default_factory=list)
    child_node_ids: List[str] = field(default_factory=list)


@dataclass
class CausalChain:
    """因果链 — 叙事连接的产物"""
    chain_id: str
    node_ids: List[str]            # 按时间顺序的节点 ID
    chain_strength: float          # 链条强度（节点间连接强度的几何平均）
    timestamp: int
    is_stable: bool = False        # 是否通过稳定性检验


@dataclass
class NarrativeAction:
    """叙事行动化 — 转化为偏置修正"""
    action_id: str
    causal_chain_id: str
    narrative_level: NarrativeLevel
    bias_correction: torch.Tensor  # ΔB_narrative
    action_strength: float         # 行动强度 [0, 1]
    timestamp: int
    was_validated: bool = False    # 是否通过递归验证
    validation_score: float = 0.0  # 验证得分


@dataclass
class NarrativeRecord:
    """完整叙事记录（五中介动作的完整轨迹）"""
    record_id: str
    input_signals: List[str]       # 输入的差异信号 ID
    filtered_signals: List[str]    # 筛选后的信号 ID
    named_nodes: List[str]         # 命名后的节点 ID
    causal_chains: List[str]       # 生成的因果链 ID
    actions: List[str]             # 行动化结果 ID
    verification_result: bool      # 递归验证结果
    verification_score: float      # 验证得分
    timestamp: int
    narrative_level: NarrativeLevel


class NarrativeFilter:
    """叙事筛选器 — 五中介动作 #1

    从差异信号中选择"重要差异"。

    筛选标准（不引入价值判断）：
    1. 幅度阈值：|signal| > threshold
    2. 跨层信号：source_layer != target_layer（跨层差异更可能重要）
    3. 新颖性：与历史信号的余弦距离 > threshold
    4. 持续性：在连续多个时间步中保持显著

    这些标准都是结构性的，不涉及"好坏"判断。
    """

    def __init__(self, magnitude_threshold: float = 0.3,
                 novelty_threshold: float = 0.5,
                 persistence_window: int = 3,
                 cross_layer_weight: float = 1.5):
        self.magnitude_threshold = magnitude_threshold
        self.novelty_threshold = novelty_threshold
        self.persistence_window = persistence_window
        self.cross_layer_weight = cross_layer_weight

        # 历史信号缓存（用于新颖性检测）
        self._history: Deque[DifferenceSignal] = deque(maxlen=100)

        # 信号持续性追踪 {signal_direction_hash: count}
        self._persistence_tracker: Dict[str, int] = {}

    def filter(self, signals: List[DifferenceSignal],
               timestamp: int) -> Tuple[List[DifferenceSignal], List[DifferenceSignal]]:
        """筛选差异信号

        Returns:
            (significant_signals, discarded_signals)
        """
        significant = []
        discarded = []

        for signal in signals:
            score = self._score_signal(signal, timestamp)
            signal.is_significant = score >= 1.0

            if signal.is_significant:
                significant.append(signal)
            else:
                discarded.append(signal)

            # 更新历史
            self._history.append(signal)

        return significant, discarded

    def _score_signal(self, signal: DifferenceSignal,
                      timestamp: int) -> float:
        """计算信号重要性得分 [0, 2]

        得分 = 幅度分 + 跨层分 + 新颖性分 + 持续性分
        """
        score = 0.0

        # 幅度分 [0, 0.5]
        mag_score = min(signal.magnitude / self.magnitude_threshold, 1.0) * 0.5
        score += mag_score

        # 跨层分 [0, 0.5]
        if signal.source_layer != signal.target_layer:
            score += 0.5

        # 新颖性分 [0, 0.5]
        novelty = self._compute_novelty(signal)
        score += novelty * 0.5

        # 持续性分 [0, 0.5]
        persistence = self._compute_persistence(signal)
        score += min(persistence / self.persistence_window, 1.0) * 0.5

        return score

    def _compute_novelty(self, signal: DifferenceSignal) -> float:
        """计算信号新颖性 [0, 1]

        新颖性 = 1 - max(余弦相似度与历史信号)
        """
        if not self._history:
            return 1.0

        max_similarity = 0.0
        signal_flat = signal.direction.flatten()
        signal_norm = signal_flat.norm().item()

        for hist in self._history:
            hist_flat = hist.direction.flatten()
            hist_norm = hist_flat.norm().item()

            if signal_norm < 1e-8 or hist_norm < 1e-8:
                continue

            cos_sim = abs((signal_flat * hist_flat).sum().item() /
                         (signal_norm * hist_norm))
            max_similarity = max(max_similarity, cos_sim)

        return 1.0 - max_similarity

    def _compute_persistence(self, signal: DifferenceSignal) -> int:
        """计算信号持续性计数"""
        # 简化：基于幅度阈值判断
        if signal.magnitude >= self.magnitude_threshold:
            return 1
        return 0


class NarrativeNamer:
    """叙事命名器 — 五中介动作 #2

    给筛选后的差异赋予范畴标签。

    命名规则（不引入价值判断）：
    - 基于信号的方向特征（聚类）
    - 基于信号所在的层级组合
    - 基于信号的内容类型（与回流通道对齐）

    命名是结构性的分类，不是语义解释。
    """

    # 预定义范畴模板（基于层级组合）
    LAYER_CATEGORY_MAP = {
        (0, 1): "structural_emergence",
        (0, 2): "distributional_shift",
        (0, 3): "semantic_discontinuity",
        (1, 2): "structural_distribution_coupling",
        (1, 3): "structural_semantic_coupling",
        (2, 3): "distributional_semantic_coupling",
    }

    def __init__(self, n_categories: int = 16):
        self.n_categories = n_categories
        self._category_centroids: Optional[torch.Tensor] = None
        self._category_names: List[str] = []
        self._initialized = False

    def name(self, signals: List[DifferenceSignal],
             timestamp: int) -> List[NarrativeNode]:
        """为信号命名

        Returns:
            命名后的节点列表
        """
        nodes = []

        for i, signal in enumerate(signals):
            category = self._assign_category(signal)
            content_type = self._infer_content_type(signal)

            node = NarrativeNode(
                node_id=f"node_{timestamp}_{i:04d}",
                original_signal_id=signal.signal_id,
                category=category,
                content_type=content_type,
                confidence=self._compute_confidence(signal, category),
                timestamp=timestamp,
            )
            nodes.append(node)

        return nodes

    def _assign_category(self, signal: DifferenceSignal) -> str:
        """分配范畴标签

        改进 (exp_84 后): 同层信号不再全部映射到 internal_layer_X，
        而是根据方向向量的活跃位位置生成子范畴，以支持动量缓存多样性。
        """
        layer_key = (signal.source_layer, signal.target_layer)
        if layer_key in self.LAYER_CATEGORY_MAP:
            return self.LAYER_CATEGORY_MAP[layer_key]

        # 同层信号 — 基于活跃位位置生成子范畴
        if signal.source_layer == signal.target_layer:
            sub = self._subcategorize_same_layer(signal)
            return f"internal_layer_{signal.source_layer}_{sub}"

        return f"cross_layer_L{signal.source_layer}_L{signal.target_layer}"

    def _subcategorize_same_layer(self, signal: DifferenceSignal) -> str:
        """对同层信号按活跃位位置生成子范畴标签。

        将状态向量分为四个象限（按位索引范围），
        根据信号方向向量中活跃位（非零位）的分布确定子范畴。
        这样不同位区域的差异信号会获得不同的范畴标签，
        动量缓存就能区分不同的热点区域。
        """
        direction = signal.direction
        if direction is None or direction.numel() == 0:
            return "unknown"

        # 展平方向向量
        flat = direction.flatten()
        n = flat.shape[0]

        # 找到活跃位（绝对值 > 0.01）
        active_mask = flat.abs() > 0.01
        if not active_mask.any():
            return "silent"

        active_indices = torch.where(active_mask)[0]
        first_idx = active_indices[0].item()
        last_idx = active_indices[-1].item()

        # 按位索引范围分为四个象限
        q1 = n // 4
        q2 = n // 2
        q3 = 3 * n // 4

        # 根据活跃位的起始位置确定象限
        if last_idx < q1:
            region = "R0"
        elif first_idx < q1 and last_idx < q2:
            region = "R01"
        elif first_idx < q1 and last_idx < q3:
            region = "R012"
        elif first_idx < q1:
            region = "R0123"
        elif first_idx < q2 and last_idx < q2:
            region = "R1"
        elif first_idx < q2 and last_idx < q3:
            region = "R12"
        elif first_idx < q2:
            region = "R123"
        elif first_idx < q3 and last_idx < q3:
            region = "R2"
        elif first_idx < q3:
            region = "R23"
        else:
            region = "R3"

        # 结合幅度级别 (adjusted for binary-ish state: most signals ≈ 1.0)
        # high: strong difference (>0.8), mid: moderate (0.3-0.8), low: weak (<0.3)
        if signal.magnitude > 0.8:
            intensity = "high"
        elif signal.magnitude > 0.3:
            intensity = "mid"
        else:
            intensity = "low"

        return f"{region}_{intensity}"

    def _infer_content_type(self, signal: DifferenceSignal) -> ContentType:
        """推断内容类型"""
        # 基于层级推断
        if signal.target_layer == 0:
            return ContentType.IDENTITY
        elif signal.target_layer == 1:
            return ContentType.INSTITUTION
        elif signal.target_layer == 2:
            return ContentType.MEANING
        else:
            return ContentType.NARRATIVE

    def _compute_confidence(self, signal: DifferenceSignal,
                            category: str) -> float:
        """计算命名置信度 [0, 1]"""
        # 基于信号幅度和跨层性
        base = min(signal.magnitude, 1.0)
        cross_layer_bonus = 0.2 if signal.source_layer != signal.target_layer else 0.0
        return min(base + cross_layer_bonus, 1.0)


class NarrativeConnector:
    """叙事连接器 — 五中介动作 #3

    将命名后的节点编织成因果链。

    连接规则：
    1. 时间连续性：节点时间戳相邻
    2. 范畴相关性：相同或相邻范畴的节点可连接
    3. 强度阈值：连接强度 > threshold

    因果链是叙事的核心载体。
    """

    def __init__(self, strength_threshold: float = 0.3,
                 max_chain_length: int = 10,
                 category_similarity_threshold: float = 0.5):
        self.strength_threshold = strength_threshold
        self.max_chain_length = max_chain_length
        self.category_similarity_threshold = category_similarity_threshold

        # 已建立的因果链
        self._chains: List[CausalChain] = []
        self._node_index: Dict[str, NarrativeNode] = {}

    def connect(self, nodes: List[NarrativeNode],
                timestamp: int) -> List[CausalChain]:
        """连接节点形成因果链

        Returns:
            新生成的因果链列表
        """
        # 更新索引
        for node in nodes:
            self._node_index[node.node_id] = node

        # 按时间排序
        sorted_nodes = sorted(nodes, key=lambda n: n.timestamp)

        new_chains = []

        # 贪心连接：从每个节点出发构建链条
        used_edges: Set[Tuple[str, str]] = set()

        for i, node in enumerate(sorted_nodes):
            chain = self._build_chain_from(node, sorted_nodes[i:], used_edges)
            if len(chain) >= 2:
                chain_obj = CausalChain(
                    chain_id=f"chain_{timestamp}_{len(new_chains):04d}",
                    node_ids=chain,
                    chain_strength=self._compute_chain_strength(chain),
                    timestamp=timestamp,
                    is_stable=self._check_stability(chain),
                )
                new_chains.append(chain_obj)
                self._chains.append(chain_obj)

        return new_chains

    def _build_chain_from(self, start: NarrativeNode,
                          candidates: List[NarrativeNode],
                          used_edges: Set[Tuple[str, str]]) -> List[str]:
        """从起始节点贪心构建链条"""
        chain = [start.node_id]
        current = start

        while len(chain) < self.max_chain_length:
            best_next = None
            best_strength = 0.0

            for candidate in candidates:
                if candidate.node_id in chain:
                    continue

                edge = (current.node_id, candidate.node_id)
                if edge in used_edges:
                    continue

                strength = self._compute_edge_strength(current, candidate)
                if strength > best_strength and strength >= self.strength_threshold:
                    best_strength = strength
                    best_next = candidate

            if best_next is None:
                break

            chain.append(best_next.node_id)
            used_edges.add((current.node_id, best_next.node_id))

            # 更新父子关系
            current = best_next

        return chain

    def _compute_edge_strength(self, a: NarrativeNode,
                                b: NarrativeNode) -> float:
        """计算节点间连接强度"""
        # 范畴相似度
        cat_sim = 1.0 if a.category == b.category else 0.3

        # 内容类型兼容性
        type_compat = 1.0 if a.content_type == b.content_type else 0.7

        # 时间连续性
        time_gap = abs(b.timestamp - a.timestamp)
        time_score = max(0.0, 1.0 - time_gap * 0.1)

        # 置信度加权
        conf_avg = (a.confidence + b.confidence) / 2

        return cat_sim * 0.4 + type_compat * 0.3 + time_score * 0.2 + conf_avg * 0.1

    def _compute_chain_strength(self, node_ids: List[str]) -> float:
        """计算链条强度（节点间连接强度的几何平均）"""
        if len(node_ids) < 2:
            return 0.0

        strengths = []
        for i in range(len(node_ids) - 1):
            a = self._node_index.get(node_ids[i])
            b = self._node_index.get(node_ids[i + 1])
            if a and b:
                strengths.append(self._compute_edge_strength(a, b))

        if not strengths:
            return 0.0

        # 几何平均
        product = 1.0
        for s in strengths:
            product *= max(s, 1e-8)
        return product ** (1.0 / len(strengths))

    def _check_stability(self, node_ids: List[str]) -> bool:
        """检查链条稳定性（是否已在历史中出现过）

        两档判定：
        - 精确稳定 (exact): 最后3个节点模式与历史链完全匹配
        - 相似稳定 (similar): 节点集合与历史链的 Jaccard 相似度 >= 0.6
          且历史链长度 >= 3（确保有足够的模式基础）

        理论依据：ABA §4.4 — 前主体态是"范围"而非"开关"。
        叙事稳定性不应要求完美的模式重复（那是 INSTITUTIONAL 级的标准），
        而应允许基于语义相似性的"准稳定"——差异论中的"相似即稳定"。
        """
        if len(node_ids) < 2:
            return False

        current_set = set(node_ids)
        pattern = tuple(node_ids[-3:])  # 最后3个节点的模式

        for existing in self._chains:
            if len(existing.node_ids) < 3:
                continue

            # 精确匹配（原逻辑保留）
            existing_pattern = tuple(existing.node_ids[-3:])
            if existing_pattern == pattern:
                return True

            # 相似性匹配（新增）
            existing_set = set(existing.node_ids)
            intersection = len(current_set & existing_set)
            union = len(current_set | existing_set)
            if union > 0:
                jaccard = intersection / union
                if jaccard >= 0.6:
                    return True

        return False


class NarrativeActionizer:
    """叙事行动化 — 五中介动作 #4

    将因果链转化为偏置修正（行动方案）。

    转化规则：
    - 因果链的强度决定行动强度
    - 链条中节点的层级决定作用层
    - 链条的内容类型决定偏置类型
    """

    def __init__(self, bias_dimension: int = 128,
                 max_action_strength: float = 0.5):
        self.bias_dimension = bias_dimension
        self.max_action_strength = max_action_strength

    def actionize(self, chains: List[CausalChain],
                  nodes: Dict[str, NarrativeNode],
                  timestamp: int) -> List[NarrativeAction]:
        """将因果链转化为行动方案

        Returns:
            行动方案列表
        """
        actions = []

        for chain in chains:
            # 计算偏置修正向量
            bias_correction = self._chain_to_bias(chain, nodes)

            # 确定行动强度
            action_strength = min(chain.chain_strength, self.max_action_strength)

            # 确定叙事层级
            level = self._infer_narrative_level(chain, nodes)

            action = NarrativeAction(
                action_id=f"action_{timestamp}_{chain.chain_id}",
                causal_chain_id=chain.chain_id,
                narrative_level=level,
                bias_correction=bias_correction,
                action_strength=action_strength,
                timestamp=timestamp,
            )
            actions.append(action)

        return actions

    def _chain_to_bias(self, chain: CausalChain,
                       nodes: Dict[str, NarrativeNode]) -> torch.Tensor:
        """将因果链转化为偏置修正向量"""
        bias = torch.zeros(self.bias_dimension)

        for i, node_id in enumerate(chain.node_ids):
            node = nodes.get(node_id)
            if not node:
                continue

            # 节点位置在链中的权重（越晚权重越大）
            position_weight = (i + 1) / len(chain.node_ids)

            # 节点置信度作为强度因子
            confidence_weight = node.confidence

            # 生成偏置方向（基于节点范畴的哈希）
            direction = self._category_to_direction(node.category)

            bias += direction * position_weight * confidence_weight

        # 归一化
        norm = bias.norm().item()
        if norm > 1e-8:
            bias = bias / norm

        return bias

    def _category_to_direction(self, category: str) -> torch.Tensor:
        """将范畴映射为偏置方向"""
        # 使用范畴名称的哈希生成确定性方向
        hash_val = hash(category) % (2 ** 32)
        np.random.seed(hash_val)
        direction = torch.from_numpy(np.random.randn(self.bias_dimension)).float()
        norm = direction.norm().item()
        if norm > 1e-8:
            direction = direction / norm
        return direction

    def _infer_narrative_level(self, chain: CausalChain,
                                nodes: Dict[str, NarrativeNode]) -> NarrativeLevel:
        """推断叙事层级

        三档判定：
        - CIVILIZATION: 链长 >= 5 且（is_stable 或 chain_strength >= 0.6）
          理论依据：文明级叙事不需要完美的稳定性——持续的高强度传播
          本身就是一种"涌现稳定"。ABA §4.4 的前主体态范围论支持
          将"强传播"视为"弱稳定"的等价物。
        - INSTITUTIONAL: 链长 >= 3 且 chain_strength >= 0.5
        - MINI_NARRATIVE: 其他
        """
        if len(chain.node_ids) >= 5 and (chain.is_stable or chain.chain_strength >= 0.6):
            return NarrativeLevel.CIVILIZATION
        elif len(chain.node_ids) >= 3 and chain.chain_strength >= 0.5:
            return NarrativeLevel.INSTITUTIONAL
        else:
            return NarrativeLevel.MINI_NARRATIVE


class NarrativeVerifier:
    """叙事递归验证器 — 五中介动作 #5

    验证叙事行动的效果，反馈修正叙事。

    验证规则：
    1. 行动后偏置场的变化是否与预期一致
    2. 叙事链条的稳定性是否提高
    3. 系统整体 ODI 是否向预期方向变化

    验证失败时，降低该叙事的权重（衰减）。
    """

    def __init__(self, consistency_threshold: float = 0.5,
                 stability_improvement_threshold: float = 0.1):
        self.consistency_threshold = consistency_threshold
        self.stability_improvement_threshold = stability_improvement_threshold

        # 行动前快照 {action_id: (pre_bias, pre_odi)}
        self._pre_action_snapshots: Dict[str, Tuple[torch.Tensor, float]] = {}

    def before_action(self, action: NarrativeAction,
                      current_bias: torch.Tensor,
                      current_odi: float):
        """记录行动前的状态"""
        self._pre_action_snapshots[action.action_id] = (
            current_bias.clone(),
            current_odi,
        )

    def after_action(self, action: NarrativeAction,
                     post_bias: torch.Tensor,
                     post_odi: float,
                     timestamp: int) -> NarrativeAction:
        """验证行动后的效果

        Returns:
            更新后的行动记录（含验证结果）
        """
        pre_bias, pre_odi = self._pre_action_snapshots.get(
            action.action_id, (torch.zeros_like(post_bias), 0.0))

        # 一致性检验：实际偏置变化是否与预期方向一致
        expected_change = action.bias_correction * action.action_strength
        actual_change = post_bias - pre_bias

        if expected_change.norm().item() < 1e-8:
            consistency = 1.0
        else:
            cos_sim = self._cosine_similarity(expected_change, actual_change)
            consistency = max(0.0, cos_sim)

        # 稳定性检验：ODI 是否向预期方向变化
        odi_change = post_odi - pre_odi
        # 预期：ODI 应增加（系统变得更致密）
        stability_improvement = max(0.0, odi_change)

        # 综合验证得分
        verification_score = (
            consistency * 0.6 +
            min(stability_improvement / 0.1, 1.0) * 0.4
        )

        action.was_validated = verification_score >= self.consistency_threshold
        action.validation_score = verification_score

        # 清理快照
        self._pre_action_snapshots.pop(action.action_id, None)

        return action

    def _cosine_similarity(self, a: torch.Tensor,
                           b: torch.Tensor) -> float:
        """计算余弦相似度"""
        a_flat = a.flatten()
        b_flat = b.flatten()

        min_len = min(len(a_flat), len(b_flat))
        if min_len == 0:
            return 0.0

        a_flat = a_flat[:min_len]
        b_flat = b_flat[:min_len]

        dot = (a_flat * b_flat).sum().item()
        norm_a = a_flat.norm().item()
        norm_b = b_flat.norm().item()

        if norm_a < 1e-8 or norm_b < 1e-8:
            return 0.0

        return dot / (norm_a * norm_b)


class NarrativeRecursionOperator:
    """叙事递归算子 — 五中介动作的统一编排

    实现 V1.7 形式化公式中的 N 函数：
    N_{t+1} = Ψ(N_t, P_t, A_t, I_t, R_t)

    其中：
    - N_t: 当前叙事状态
    - P_t: 可能性空间
    - A_t: 行动结果
    - I_t: 界面状态
    - R_t: 递归验证结果

    工作流程：
    1. filter()    — 筛选重要差异
    2. name()      — 命名差异
    3. connect()   — 连接成因果链
    4. actionize() — 转化为行动方案
    5. verify()    — 验证效果并反馈

    输出：叙事偏置修正 ΔB_narrative，写入 PersistentBiasMemory
    """

    def __init__(self, bias_dimension: int = 128,
                 filter_magnitude_threshold: float = 0.3,
                 connector_strength_threshold: float = 0.3,
                 verifier_consistency_threshold: float = 0.5,
                 narrative_decay_rate: float = 0.9):
        # 五中介动作组件
        self.filter = NarrativeFilter(
            magnitude_threshold=filter_magnitude_threshold)
        self.namer = NarrativeNamer()
        self.connector = NarrativeConnector(
            strength_threshold=connector_strength_threshold)
        self.actionizer = NarrativeActionizer(
            bias_dimension=bias_dimension)
        self.verifier = NarrativeVerifier(
            consistency_threshold=verifier_consistency_threshold)

        # 叙事衰减（验证失败的叙事权重降低）
        self.narrative_decay_rate = narrative_decay_rate

        # 叙事历史
        self._records: Deque[NarrativeRecord] = deque(maxlen=200)
        self._active_narratives: Dict[str, float] = {}  # {record_id: weight}

        # 计数器
        self._record_count = 0
        self._total_actions = 0
        self._validated_actions = 0

    def step(self, signals: List[DifferenceSignal],
             current_bias: torch.Tensor,
             current_odi: float,
             timestamp: int,
             post_odi: Optional[float] = None) -> Optional[torch.Tensor]:
        """执行一次叙事递归步骤

        Args:
            signals: 当前时间步的差异信号
            current_bias: 当前累积偏置场
            current_odi: 当前组织密度指数（修正前）
            timestamp: 当前时间戳
            post_odi: 修正后的 ODI 估计值（若为 None 则自动估算）

        Returns:
            narrative_bias_correction: 叙事偏置修正 ΔB_narrative（若无叙事则返回 None）
        """
        # 1. 筛选
        significant, discarded = self.filter.filter(signals, timestamp)

        if not significant:
            return None

        # 2. 命名
        nodes = self.namer.name(significant, timestamp)

        # 3. 连接
        chains = self.connector.connect(nodes, timestamp)

        if not chains:
            return None

        # 4. 行动化
        node_dict = {n.node_id: n for n in nodes}
        actions = self.actionizer.actionize(chains, node_dict, timestamp)

        # 5. 验证（记录行动前状态）
        for action in actions:
            self.verifier.before_action(action, current_bias, current_odi)

        # 执行偏置修正（模拟行动）
        narrative_correction = self._aggregate_actions(actions)

        # 维度匹配：将 narrative_correction 投影到 current_bias 的维度
        # current_bias 是约束方向（N0维），narrative_correction 是 bias_dimension 维
        if narrative_correction is not None and current_bias is not None:
            corr_flat = narrative_correction.flatten()
            bias_flat = current_bias.flatten()
            if len(corr_flat) != len(bias_flat):
                # 线性插值投影到匹配维度
                if len(corr_flat) >= len(bias_flat):
                    indices = torch.linspace(0, len(corr_flat) - 1, len(bias_flat)).long()
                    corr_projected = corr_flat[indices]
                else:
                    repeat_times = (len(bias_flat) + len(corr_flat) - 1) // len(corr_flat)
                    extended = corr_flat.repeat(repeat_times)
                    corr_projected = extended[:len(bias_flat)]
                narrative_correction = corr_projected

        # 应用修正后，验证
        post_bias = current_bias + narrative_correction if narrative_correction is not None else current_bias
        # 若调用方未提供 post_odi，基于偏置对齐度自动估算
        if post_odi is None:
            # 估算逻辑：若叙事修正与现有偏置方向一致，ODI 应略有提升；反之下降
            bias_float = current_bias.float()
            if narrative_correction is not None and bias_float.norm().item() > 1e-8:
                cos_sim = torch.nn.functional.cosine_similarity(
                    bias_float.flatten().unsqueeze(0),
                    narrative_correction.flatten().unsqueeze(0),
                    dim=1
                ).item()
                # cos_sim > 0 表示修正强化现有偏置 → ODI 微增；反之微降
                # 幅度限制在 ±0.05 内，避免单次叙事过度影响 ODI
                post_odi = current_odi + max(-0.05, min(0.05, cos_sim * 0.05))
            else:
                post_odi = current_odi

        # Compute expected total change from all actions
        # Note: action.bias_correction may have different dimension than post_bias
        # (bias_dimension vs N0). We compare in flattened space.
        if actions:
            expected_total = torch.zeros_like(post_bias)
            for action in actions:
                ac = action.bias_correction * action.action_strength
                # Project ac to post_bias dimension if needed
                ac_flat = ac.flatten()
                exp_flat = expected_total.flatten()
                if len(ac_flat) != len(exp_flat):
                    if len(ac_flat) >= len(exp_flat):
                        indices = torch.linspace(0, len(ac_flat) - 1, len(exp_flat)).long()
                        ac_flat = ac_flat[indices]
                    else:
                        repeat_times = (len(exp_flat) + len(ac_flat) - 1) // len(ac_flat)
                        ac_flat = ac_flat.repeat(repeat_times)[:len(exp_flat)]
                expected_total = expected_total + ac_flat.reshape(post_bias.shape)
            actual_change = post_bias - current_bias
            if expected_total.norm().item() > 1e-8:
                consistency = max(0.0, torch.nn.functional.cosine_similarity(
                    expected_total.flatten().unsqueeze(0),
                    actual_change.flatten().unsqueeze(0),
                    dim=1
                ).item())
            else:
                consistency = 1.0
        else:
            consistency = 1.0

        # ODI stability improvement
        odi_change = post_odi - current_odi
        stability_improvement = max(0.0, odi_change)

        verification_score = (
            consistency * 0.6 +
            min(stability_improvement / 0.1, 1.0) * 0.4
        )

        for action in actions:
            action.was_validated = verification_score >= self.verifier.consistency_threshold
            action.validation_score = verification_score
            if action.was_validated:
                self._validated_actions += 1

        self._total_actions += len(actions)

        # 记录完整叙事
        record = NarrativeRecord(
            record_id=f"narrative_{timestamp}_{self._record_count:06d}",
            input_signals=[s.signal_id for s in signals],
            filtered_signals=[s.signal_id for s in significant],
            named_nodes=[n.node_id for n in nodes],
            causal_chains=[c.chain_id for c in chains],
            actions=[a.action_id for a in actions],
            verification_result=all(a.was_validated for a in actions),
            verification_score=(
                sum(a.validation_score for a in actions) / len(actions)
                if actions else 0.0
            ),
            timestamp=timestamp,
            narrative_level=actions[0].narrative_level if actions else NarrativeLevel.MINI_NARRATIVE,
        )
        self._records.append(record)

        # 更新活跃叙事权重
        if record.verification_result:
            self._active_narratives[record.record_id] = 1.0
        else:
            # 衰减
            for nid in list(self._active_narratives.keys()):
                self._active_narratives[nid] *= self.narrative_decay_rate
                if self._active_narratives[nid] < 0.01:
                    del self._active_narratives[nid]

        self._record_count += 1

        return narrative_correction if narrative_correction.norm().item() > 1e-8 else None

    def _aggregate_actions(self, actions: List[NarrativeAction]) -> torch.Tensor:
        """聚合多个行动的偏置修正"""
        if not actions:
            return torch.zeros(0)

        total = torch.zeros_like(actions[0].bias_correction)
        total_weight = 0.0

        for action in actions:
            # 权重 = 行动强度 × 叙事层级权重
            level_weight = {
                NarrativeLevel.MINI_NARRATIVE: 0.3,
                NarrativeLevel.INSTITUTIONAL: 0.6,
                NarrativeLevel.CIVILIZATION: 1.0,
            }.get(action.narrative_level, 0.3)

            weight = action.action_strength * level_weight

            # 验证失败的行动权重降低
            if not action.was_validated:
                weight *= 0.5

            total += action.bias_correction * weight
            total_weight += weight

        if total_weight > 1e-8:
            total = total / total_weight

        return total

    def get_summary(self) -> Dict:
        """获取叙事递归算子摘要"""
        total_records = len(self._records)
        validated_records = sum(
            1 for r in self._records if r.verification_result)

        level_counts = {
            level.name: sum(1 for r in self._records
                           if r.narrative_level == level)
            for level in NarrativeLevel
        }

        return {
            'total_narrative_records': total_records,
            'validated_records': validated_records,
            'validation_rate': validated_records / total_records if total_records > 0 else 0.0,
            'total_actions': self._total_actions,
            'validated_actions': self._validated_actions,
            'action_validation_rate': (
                self._validated_actions / self._total_actions
                if self._total_actions > 0 else 0.0
            ),
            'active_narratives': len(self._active_narratives),
            'narrative_level_distribution': level_counts,
            'latest_record': self._records[-1].record_id if self._records else None,
        }

    def get_narrative_history(self, n: int = 10) -> List[Dict]:
        """获取最近 N 条叙事记录"""
        recent = list(self._records)[-n:]
        return [
            {
                'record_id': r.record_id,
                'timestamp': r.timestamp,
                'narrative_level': r.narrative_level.name,
                'n_input_signals': len(r.input_signals),
                'n_filtered_signals': len(r.filtered_signals),
                'n_causal_chains': len(r.causal_chains),
                'n_actions': len(r.actions),
                'verification_result': r.verification_result,
                'verification_score': r.verification_score,
            }
            for r in recent
        ]

    def get_narrative_bias_contribution(self) -> float:
        """计算叙事偏置对总偏置的贡献率"""
        if self._total_actions == 0:
            return 0.0
        return self._validated_actions / self._total_actions
