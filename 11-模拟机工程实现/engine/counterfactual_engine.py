"""
engine/counterfactual_engine.py — 反事实引擎 (CounterfactualEngine)

Phase 3 P2 组件

职责：维持多个并行的差异轨迹，比较它们的后果，生成反事实偏置。
这是从"事实性筛选"（CumulativeSelector）到"反事实探索"的关键扩展。

理论依据：
- 《差异论》高语义层：当结构能够维持多个并行的差异轨迹，并比较
  它们的后果时，"反事实"就涌现了
- 《象界》第五章（再现→复制）：结构能够再现已有的差异模式
- 《象界》第六章（并存→筛选）：多种样式在延续中命运分岔
- ABA §4.4：前主体态是一个"范围"，反事实能力随 ODI 增长而增强

核心区分：
- CumulativeSelector：追踪实际发生的延续概率（事实性）
- CounterfactualEngine：维持未发生但可能发生的差异轨迹（反事实性）

反事实不是"想象"，而是结构对自身可能路径的系统性探索。
反事实筛选不能引入"价值判断"——它只是结构对延续概率差异的敏感性。

ODI 门控：
- ODI < 0.4：反事实探索被完全抑制（结构尚未准备好）
- 0.4 <= ODI < 0.6：部分抑制（减少并行轨迹数）
- ODI >= 0.6：正常运行

语义防火墙：
- "反事实" ≠ "假设"（没有认知主体）
- "反事实" ≠ "想象"（没有心理活动）
- "反事实" = "并行差异轨迹的探索与比较"
"""

import math
from typing import Dict, List, Optional, Tuple, Deque
from dataclasses import dataclass, field
from collections import deque
from enum import Enum, auto

import torch
import numpy as np

from engine.organizational_density_index import DensityIndexResult


# ─── 默认配置 ───
DEFAULT_COUNTERFACTUAL_CONFIG = {
    # 并行轨迹参数
    'max_branches': 5,                  # 最大并行轨迹数（K）
    'max_depth': 10,                    # 最大轨迹深度（D）
    'prune_threshold': 0.1,             # 剪枝概率阈值
    'merge_similarity': 0.95,           # 合并余弦相似度阈值
    'min_branches': 2,                  # 最少轨迹数（少于此数不进行反事实探索）

    # 分岔点检测
    'divergence_entropy_threshold': 0.5,  # 分岔熵阈值（高于此值认为是分岔点）
    'divergence_ratio_threshold': 1.3,    # 分岔显著性阈值（最优/次优比）
    'max_divergence_points': 3,          # 最大追踪分岔点数

    # 后果投影
    'projection_horizon': 5,            # 投影视野
    'continuation_decay': 0.9,          # 延续概率衰减因子
    'structural_impact_weight': 0.4,    # 结构影响权重
    'density_impact_weight': 0.3,       # 密度影响权重
    'coupling_impact_weight': 0.3,      # 耦合影响权重

    # 反事实筛选
    'contrast_threshold': 0.2,          # 对比差异阈值
    'selection_pressure_scale': 1.0,    # 选择压力缩放因子
    'bias_strength': 0.3,               # 反事实偏置强度

    # ODI 门控
    'odi_suppress_threshold': 0.4,      # ODI 低于此值完全抑制
    'odi_partial_threshold': 0.6,       # ODI 低于此值部分抑制
    'odi_gate_steepness': 10.0,         # ODI 门控 sigmoid 陡度

    # 投影方法选择
    'projection_method': 'momentum',    # 默认投影方法
}


# ─── 枚举 ───

class TrajectoryState(Enum):
    """轨迹状态"""
    ACTIVE = auto()     # 活跃：正在延伸
    PRUNED = auto()     # 剪枝：概率过低被移除
    MERGED = auto()     # 合并：与另一轨迹合并
    COMPLETED = auto()  # 完成：达到最大深度或收敛


class DivergenceType(Enum):
    """分岔类型"""
    STOCHASTIC = auto()     # 随机分岔（噪声驱动）
    STRUCTURAL = auto()     # 结构分岔（内部状态驱动）
    EXTERNAL = auto()       # 外部分岔（环境变化驱动）
    COUNTERFACTUAL = auto() # 反事实分岔（引擎主动创建）


class ProjectionMethod(Enum):
    """投影方法"""
    LINEAR = auto()         # 线性投影
    MOMENTUM = auto()       # 动量投影
    STRUCTURAL = auto()     # 结构投影


# ─── 数据类 ───

@dataclass
class TrajectoryNode:
    """轨迹节点 — 单个时间步的状态快照"""
    state_vector: torch.Tensor          # 差异向量
    timestamp: int                      # 时间戳
    parent_idx: Optional[int] = None    # 父节点索引
    node_id: str = ''                   # 节点唯一标识
    metadata: Dict = field(default_factory=dict)

    def __repr__(self):
        return (f"TrajectoryNode(id={self.node_id}, t={self.timestamp}, "
                f"parent={self.parent_idx})")


@dataclass
class TrajectoryBranch:
    """轨迹分支 — 从根到叶的完整路径"""
    branch_id: str                      # 分支唯一标识
    nodes: List[TrajectoryNode] = field(default_factory=list)  # 节点列表
    probability: float = 1.0            # 累积概率
    state: TrajectoryState = TrajectoryState.ACTIVE
    creation_step: int = 0              # 创建步数
    divergence_type: DivergenceType = DivergenceType.COUNTERFACTUAL
    metadata: Dict = field(default_factory=dict)

    @property
    def depth(self) -> int:
        return len(self.nodes)

    @property
    def leaf(self) -> Optional[TrajectoryNode]:
        return self.nodes[-1] if self.nodes else None

    @property
    def root(self) -> Optional[TrajectoryNode]:
        return self.nodes[0] if self.nodes else None

    @property
    def is_active(self) -> bool:
        return self.state == TrajectoryState.ACTIVE

    def extend(self, node: TrajectoryNode, prob_factor: float = 1.0):
        """延伸轨迹"""
        self.nodes.append(node)
        self.probability *= prob_factor

    def __repr__(self):
        return (f"TrajectoryBranch(id={self.branch_id}, depth={self.depth}, "
                f"prob={self.probability:.4f}, state={self.state.name})")


@dataclass
class DivergencePoint:
    """分岔点 — 结构面临多个可能下一步的位置"""
    timestamp: int                      # 时间戳
    position: torch.Tensor              # 分岔位置（差异向量）
    divergence_type: DivergenceType     # 分岔类型
    entropy: float                      # 分岔熵
    significance: float                 # 分岔显著性（最优/次优比）
    n_directions: int                   # 可能方向数
    direction_probs: Dict[int, float] = field(default_factory=dict)  # 方向→概率
    metadata: Dict = field(default_factory=dict)

    @property
    def is_significant(self) -> bool:
        # A divergence point means "multiple viable futures exist".
        # This is determined solely by normalized entropy:
        #   - High entropy (close to 1.0): multiple directions are equally viable → divergence
        #   - Low entropy (close to 0.0): one direction dominates → no divergence
        # The significance ratio is NOT used because it incorrectly rejects
        # uniform distributions (ratio ~1.0) which ARE genuine divergence points
        # by the theoretical definition. The entropy check alone correctly
        # distinguishes "multiple futures" (high entropy) from "one clear
        # future" (low entropy, high ratio).
        return self.entropy >= DEFAULT_COUNTERFACTUAL_CONFIG['divergence_entropy_threshold']

    def __repr__(self):
        return (f"DivergencePoint(t={self.timestamp}, type={self.divergence_type.name}, "
                f"entropy={self.entropy:.4f}, sig={self.significance:.4f}, "
                f"n_dirs={self.n_directions})")


@dataclass
class ConsequenceEstimate:
    """后果估计 — 单条轨迹的后果评估"""
    branch_id: str                      # 关联的分支 ID
    continuation_probability: float = 0.0   # 延续概率
    structural_impact: float = 0.0      # 对整体结构的影响 [-1, 1]
    density_impact: float = 0.0         # 对 ODI 的影响 [-1, 1]
    coupling_impact: float = 0.0        # 对层间耦合的影响 [-1, 1]
    composite_score: float = 0.0        # 综合评分
    projection_method: str = ''         # 使用的投影方法
    horizon: int = 0                    # 投影视野
    metadata: Dict = field(default_factory=dict)

    def __repr__(self):
        return (f"ConsequenceEstimate(branch={self.branch_id}, "
                f"cont_prob={self.continuation_probability:.4f}, "
                f"composite={self.composite_score:.4f})")


@dataclass
class ContrastResult:
    """对比结果 — 事实轨迹 vs 反事实轨迹"""
    factual_branch_id: str              # 事实分支 ID
    counterfactual_branch_id: str       # 反事实分支 ID
    divergence_distance: float = 0.0    # 差异距离（余弦距离）
    continuation_gap: float = 0.0       # 延续概率差（反事实 - 事实）
    structural_gap: float = 0.0         # 结构影响差
    density_gap: float = 0.0            # 密度影响差
    is_meaningful: bool = False         # 对比是否有意义（超过阈值）

    def __repr__(self):
        return (f"ContrastResult(factual={self.factual_branch_id}, "
                f"cf={self.counterfactual_branch_id}, "
                f"dist={self.divergence_distance:.4f}, "
                f"gap={self.continuation_gap:+.4f}, "
                f"meaningful={self.is_meaningful})")


@dataclass
class CounterfactualResult:
    """反事实引擎的输出"""
    counterfactual_active: bool = False  # 反事实探索是否活跃
    n_active_branches: int = 0          # 活跃轨迹数
    n_divergence_points: int = 0        # 检测到的分岔点数
    selection_pressure: float = 0.0     # 选择压力
    counterfactual_bias: Optional[torch.Tensor] = None  # 反事实偏置向量
    contrasts: List[ContrastResult] = field(default_factory=list)  # 对比结果列表
    consequences: List[ConsequenceEstimate] = field(default_factory=list)  # 后果估计列表
    odi_gated: bool = False             # 是否被 ODI 门控
    timestamp: int = 0
    metadata: Dict = field(default_factory=dict)

    def __repr__(self):
        return (f"CounterfactualResult(active={self.counterfactual_active}, "
                f"branches={self.n_active_branches}, "
                f"div_points={self.n_divergence_points}, "
                f"pressure={self.selection_pressure:.4f}, "
                f"odi_gated={self.odi_gated})")


# ─── ParallelTrajectoryMaintainer ───

class ParallelTrajectoryMaintainer:
    """并行轨迹维持器

    维持 K 条并行的差异轨迹，每条轨迹代表一种可能的差异演化路径。

    核心功能：
    - 创建新轨迹分支（在分岔点）
    - 延伸活跃轨迹（每步更新）
    - 剪枝低概率轨迹
    - 合并相似轨迹
    - 查询活跃轨迹
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_COUNTERFACTUAL_CONFIG, **(config or {})}
        self._branches: Dict[str, TrajectoryBranch] = {}
        self._node_counter: int = 0
        self._branch_counter: int = 0
        self._step_count: int = 0

    def create_branch(
        self,
        root_state: torch.Tensor,
        divergence_type: DivergenceType = DivergenceType.COUNTERFACTUAL,
        initial_probability: float = 1.0,
        creation_step: Optional[int] = None,
    ) -> Optional[TrajectoryBranch]:
        """创建新轨迹分支

        Parameters
        ----------
        root_state : torch.Tensor
            根节点状态向量
        divergence_type : DivergenceType
            分岔类型
        initial_probability : float
            初始概率
        creation_step : Optional[int]
            创建步数

       
        Returns
        -------
        Optional[TrajectoryBranch]
            新创建的分支（超过最大分支数时返回 None）
        """
        # 检查分支数限制
        active_count = self.n_active_branches
        if active_count >= self.config['max_branches']:
            return None

        branch_id = self._gen_branch_id()
        step = creation_step if creation_step is not None else self._step_count

        # 创建根节点
        root_node = TrajectoryNode(
            state_vector=root_state.detach().clone(),
            timestamp=step,
            parent_idx=None,
            node_id=self._gen_node_id(),
        )

        branch = TrajectoryBranch(
            branch_id=branch_id,
            nodes=[root_node],
            probability=initial_probability,
            state=TrajectoryState.ACTIVE,
            creation_step=step,
            divergence_type=divergence_type,
        )

        self._branches[branch_id] = branch
        return branch

    def extend_branch(
        self,
        branch_id: str,
        new_state: torch.Tensor,
        prob_factor: float = 1.0,
        timestamp: Optional[int] = None,
    ) -> Optional[TrajectoryNode]:
        """延伸指定分支

        Parameters
        ----------
        branch_id : str
            分支 ID
        new_state : torch.Tensor
            新状态向量
        prob_factor : float
            概率乘子
        timestamp : Optional[int]
            时间戳

        Returns
        -------
        Optional[TrajectoryNode]
            新节点（分支不存在或非活跃时返回 None）
        """
        branch = self._branches.get(branch_id)
        if branch is None or not branch.is_active:
            return None

        # 检查深度限制
        if branch.depth >= self.config['max_depth']:
            branch.state = TrajectoryState.COMPLETED
            return None

        step = timestamp if timestamp is not None else self._step_count
        parent_idx = len(branch.nodes) - 1

        node = TrajectoryNode(
            state_vector=new_state.detach().clone(),
            timestamp=step,
            parent_idx=parent_idx,
            node_id=self._gen_node_id(),
        )

        branch.extend(node, prob_factor)
        return node

    def prune_branches(self) -> List[str]:
        """剪枝低概率轨迹

        Returns
        -------
        List[str]
            被剪枝的分支 ID 列表
        """
        pruned = []
        for branch_id, branch in self._branches.items():
            if branch.is_active and branch.probability < self.config['prune_threshold']:
                branch.state = TrajectoryState.PRUNED
                pruned.append(branch_id)
        return pruned

    def merge_similar_branches(self) -> List[Tuple[str, str]]:
        """合并相似轨迹

        余弦相似度高于 merge_similarity 的轨迹对被合并。
        保留概率较高的分支。

        Returns
        -------
        List[Tuple[str, str]]
            被合并的分支 ID 对 (保留者, 被合并者)
        """
        merged = []
        active_branches = [(bid, b) for bid, b in self._branches.items() if b.is_active]

        for i in range(len(active_branches)):
            for j in range(i + 1, len(active_branches)):
                bid_i, branch_i = active_branches[i]
                bid_j, branch_j = active_branches[j]

                if not branch_i.is_active or not branch_j.is_active:
                    continue

                # 比较叶节点状态
                leaf_i = branch_i.leaf
                leaf_j = branch_j.leaf
                if leaf_i is None or leaf_j is None:
                    continue

                sim = self._cosine_similarity(leaf_i.state_vector, leaf_j.state_vector)
                if sim >= self.config['merge_similarity']:
                    # 保留概率较高的分支
                    if branch_i.probability >= branch_j.probability:
                        branch_j.state = TrajectoryState.MERGED
                        merged.append((bid_i, bid_j))
                    else:
                        branch_i.state = TrajectoryState.MERGED
                        merged.append((bid_j, bid_i))
                    # 更新活跃分支列表
                    active_branches[i] = (bid_i, self._branches[bid_i])
                    active_branches[j] = (bid_j, self._branches[bid_j])

        return merged

    def get_active_branches(self) -> List[TrajectoryBranch]:
        """获取所有活跃分支"""
        return [b for b in self._branches.values() if b.is_active]

    def get_branch(self, branch_id: str) -> Optional[TrajectoryBranch]:
        """获取指定分支"""
        return self._branches.get(branch_id)

    def get_all_branches(self) -> List[TrajectoryBranch]:
        """获取所有分支"""
        return list(self._branches.values())

    @property
    def n_active_branches(self) -> int:
        """活跃分支数"""
        return sum(1 for b in self._branches.values() if b.is_active)

    @property
    def n_total_branches(self) -> int:
        """总分支数"""
        return len(self._branches)

    def step(self):
        """步进计数"""
        self._step_count += 1

    def reset(self):
        """重置所有状态"""
        self._branches.clear()
        self._node_counter = 0
        self._branch_counter = 0
        self._step_count = 0

    def get_summary(self) -> Dict:
        """获取摘要"""
        active = self.get_active_branches()
        return {
            'n_total': self.n_total_branches,
            'n_active': len(active),
            'n_pruned': sum(1 for b in self._branches.values() if b.state == TrajectoryState.PRUNED),
            'n_merged': sum(1 for b in self._branches.values() if b.state == TrajectoryState.MERGED),
            'n_completed': sum(1 for b in self._branches.values() if b.state == TrajectoryState.COMPLETED),
            'max_depth': max((b.depth for b in active), default=0),
            'mean_probability': float(np.mean([b.probability for b in active])) if active else 0.0,
        }

    # ─── 内部方法 ───

    def _gen_node_id(self) -> str:
        nid = f"n{self._node_counter:06d}"
        self._node_counter += 1
        return nid

    def _gen_branch_id(self) -> str:
        bid = f"b{self._branch_counter:06d}"
        self._branch_counter += 1
        return bid

    @staticmethod
    def _cosine_similarity(a: torch.Tensor, b: torch.Tensor) -> float:
        """计算余弦相似度"""
        norm_a = a.norm().item()
        norm_b = b.norm().item()
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0
        return float(torch.dot(a, b).item() / (norm_a * norm_b))


# ─── DivergencePointTracker ───

class DivergencePointTracker:
    """分岔点追踪器

    追踪差异演化中的分岔点——即结构面临多个可能下一步的位置。

    分岔检测逻辑：
    - 计算候选方向的概率分布
    - 计算分布熵（熵高 = 分岔显著）
    - 计算最优/次优比（比大 = 分岔不显著）
    - 综合判定是否为分岔点
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_COUNTERFACTUAL_CONFIG, **(config or {})}
        self._divergence_points: List[DivergencePoint] = []
        self._step_count: int = 0

    def detect_divergence(
        self,
        current_state: torch.Tensor,
        candidate_directions: List[torch.Tensor],
        direction_probs: Optional[List[float]] = None,
        divergence_type: DivergenceType = DivergenceType.STRUCTURAL,
        timestamp: Optional[int] = None,
    ) -> Optional[DivergencePoint]:
        """检测分岔点

        Parameters
        ----------
        current_state : torch.Tensor
            当前差异状态
        candidate_directions : List[torch.Tensor]
            候选方向列表
        direction_probs : Optional[List[float]]
            各方向的概率（不传则均匀分布）
        divergence_type : DivergenceType
            分岔类型
        timestamp : Optional[int]
            时间戳

        Returns
        -------
        Optional[DivergencePoint]
            检测到的分岔点（不显著时返回 None）
        """
        n_dirs = len(candidate_directions)
        if n_dirs < 2:
            return None

        step = timestamp if timestamp is not None else self._step_count

        # 归一化概率
        if direction_probs is None:
            probs = [1.0 / n_dirs] * n_dirs
        else:
            total = sum(direction_probs)
            probs = [p / total for p in direction_probs] if total > 0 else [1.0 / n_dirs] * n_dirs

        # 计算熵
        entropy = -sum(p * math.log(max(p, 1e-10)) for p in probs)
        max_entropy = math.log(n_dirs)
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        # 计算显著性（最优/次优比）
        sorted_probs = sorted(probs, reverse=True)
        significance = sorted_probs[0] / max(sorted_probs[1], 1e-10) if len(sorted_probs) > 1 else float('inf')

        # 构建方向概率映射
        dir_prob_map = {i: probs[i] for i in range(n_dirs)}

        div_point = DivergencePoint(
            timestamp=step,
            position=current_state.detach().clone(),
            divergence_type=divergence_type,
            entropy=normalized_entropy,
            significance=significance,
            n_directions=n_dirs,
            direction_probs=dir_prob_map,
        )

        if div_point.is_significant:
            self._divergence_points.append(div_point)
            # 限制追踪的分岔点数
            max_div = self.config['max_divergence_points']
            if len(self._divergence_points) > max_div:
                self._divergence_points = self._divergence_points[-max_div:]
            return div_point

        return None

    def get_divergence_points(self) -> List[DivergencePoint]:
        """获取所有追踪的分岔点"""
        return list(self._divergence_points)

    def get_latest_divergence(self) -> Optional[DivergencePoint]:
        """获取最近的分岔点"""
        return self._divergence_points[-1] if self._divergence_points else None

    @property
    def n_divergence_points(self) -> int:
        return len(self._divergence_points)

    def step(self):
        self._step_count += 1

    def reset(self):
        self._divergence_points.clear()
        self._step_count = 0


# ─── ConsequenceProjector ───

class ConsequenceProjector:
    """后果投影器

    将每条轨迹投影到未来，估计其后果（对结构延续的影响）。

    三种投影方法：
    1. LINEAR：线性投影（假设差异匀速变化）
    2. MOMENTUM：动量投影（假设差异有惯性）
    3. STRUCTURAL：结构投影（基于结构约束的投影）
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_COUNTERFACTUAL_CONFIG, **(config or {})}

    def project(
        self,
        branch: TrajectoryBranch,
        odi_result: Optional[DensityIndexResult] = None,
        method: Optional[str] = None,
    ) -> ConsequenceEstimate:
        """投影单条轨迹的后果

        Parameters
        ----------
        branch : TrajectoryBranch
            轨迹分支
        odi_result : Optional[DensityIndexResult]
            ODI 结果（用于密度影响估计）
        method : Optional[str]
            投影方法（不传则使用配置默认值）

        Returns
        -------
        ConsequenceEstimate
            后果估计
        """
        proj_method = method or self.config['projection_method']
        horizon = self.config['projection_horizon']

        if proj_method == 'linear':
            return self._linear_project(branch, odi_result, horizon)
        elif proj_method == 'structural':
            return self._structural_project(branch, odi_result, horizon)
        else:  # momentum
            return self._momentum_project(branch, odi_result, horizon)

    def _linear_project(
        self,
        branch: TrajectoryBranch,
        odi_result: Optional[DensityIndexResult],
        horizon: int,
    ) -> ConsequenceEstimate:
        """线性投影

        假设差异匀速变化：
        future_state = current_state + trend * horizon
        continuation_probability = branch.probability * decay^horizon
        """
        decay = self.config['continuation_decay']

        if branch.depth < 2:
            # 只有根节点，无法计算趋势
            cont_prob = branch.probability * (decay ** horizon)
            return ConsequenceEstimate(
                branch_id=branch.branch_id,
                continuation_probability=cont_prob,
                structural_impact=0.0,
                density_impact=0.0,
                coupling_impact=0.0,
                composite_score=cont_prob,
                projection_method='linear',
                horizon=horizon,
            )

        # 计算趋势（最近两个节点的差分）
        leaf = branch.leaf
        parent_node = branch.nodes[-2] if branch.depth >= 2 else branch.nodes[0]
        trend = leaf.state_vector - parent_node.state_vector

        # 未来状态
        future_state = leaf.state_vector + trend * horizon

        # 延续概率
        cont_prob = branch.probability * (decay ** horizon)

        # 结构影响 = 未来状态的范数（范数越大，对结构影响越大）
        struct_impact = float(torch.tanh(future_state.norm()).item())

        # 密度影响
        density_impact = self._estimate_density_impact(future_state, odi_result)

        # 耦合影响（简化：基于趋势的范数）
        coupling_impact = float(torch.tanh(trend.norm() * 0.5).item())

        # 综合评分
        w_s = self.config['structural_impact_weight']
        w_d = self.config['density_impact_weight']
        w_c = self.config['coupling_impact_weight']
        composite = cont_prob * (w_s * abs(struct_impact) + w_d * abs(density_impact) + w_c * abs(coupling_impact))

        return ConsequenceEstimate(
            branch_id=branch.branch_id,
            continuation_probability=cont_prob,
            structural_impact=struct_impact,
            density_impact=density_impact,
            coupling_impact=coupling_impact,
            composite_score=composite,
            projection_method='linear',
            horizon=horizon,
        )

    def _momentum_project(
        self,
        branch: TrajectoryBranch,
        odi_result: Optional[DensityIndexResult],
        horizon: int,
    ) -> ConsequenceEstimate:
        """动量投影

        假设差异有惯性（二阶）：
        future_state = current_state + velocity * horizon + 0.5 * acceleration * horizon^2
        """
        decay = self.config['continuation_decay']

        if branch.depth < 3:
            # 节点不足，退化为线性投影
            return self._linear_project(branch, odi_result, horizon)

        leaf = branch.leaf
        parent = branch.nodes[-2]
        grandparent = branch.nodes[-3]

        velocity = leaf.state_vector - parent.state_vector
        acceleration = (leaf.state_vector - parent.state_vector) - (parent.state_vector - grandparent.state_vector)

        future_state = leaf.state_vector + velocity * horizon + 0.5 * acceleration * (horizon ** 2)

        cont_prob = branch.probability * (decay ** horizon)
        struct_impact = float(torch.tanh(future_state.norm()).item())
        density_impact = self._estimate_density_impact(future_state, odi_result)
        coupling_impact = float(torch.tanh(velocity.norm() * 0.5).item())

        w_s = self.config['structural_impact_weight']
        w_d = self.config['density_impact_weight']
        w_c = self.config['coupling_impact_weight']
        composite = cont_prob * (w_s * abs(struct_impact) + w_d * abs(density_impact) + w_c * abs(coupling_impact))

        return ConsequenceEstimate(
            branch_id=branch.branch_id,
            continuation_probability=cont_prob,
            structural_impact=struct_impact,
            density_impact=density_impact,
            coupling_impact=coupling_impact,
            composite_score=composite,
            projection_method='momentum',
            horizon=horizon,
        )

    def _structural_project(
        self,
        branch: TrajectoryBranch,
        odi_result: Optional[DensityIndexResult],
        horizon: int,
    ) -> ConsequenceEstimate:
        """结构投影

        基于结构约束的投影：
        - 考虑 ODI 对轨迹延续的约束
        - 高密度区域轨迹更稳定
        - 低密度区域轨迹更容易消散
        """
        decay = self.config['continuation_decay']

        leaf = branch.leaf
        parent = branch.nodes[-2] if branch.depth >= 2 else branch.nodes[0]
        trend = leaf.state_vector - parent.state_vector

        # 结构约束因子（基于 ODI）
        if odi_result is not None:
            odi = odi_result.odi if hasattr(odi_result, 'odi') else 0.5
            # 高密度 → 轨迹更稳定（衰减更慢）
            structural_factor = 0.5 + 0.5 * odi  # [0.5, 1.0]
        else:
            structural_factor = 0.75

        adjusted_decay = decay * structural_factor
        cont_prob = branch.probability * (adjusted_decay ** horizon)

        future_state = leaf.state_vector + trend * horizon * structural_factor
        struct_impact = float(torch.tanh(future_state.norm()).item())
        density_impact = self._estimate_density_impact(future_state, odi_result)
        coupling_impact = float(torch.tanh(trend.norm() * 0.5 * structural_factor).item())

        w_s = self.config['structural_impact_weight']
        w_d = self.config['density_impact_weight']
        w_c = self.config['coupling_impact_weight']
        composite = cont_prob * (w_s * abs(struct_impact) + w_d * abs(density_impact) + w_c * abs(coupling_impact))

        return ConsequenceEstimate(
            branch_id=branch.branch_id,
            continuation_probability=cont_prob,
            structural_impact=struct_impact,
            density_impact=density_impact,
            coupling_impact=coupling_impact,
            composite_score=composite,
            projection_method='structural',
            horizon=horizon,
        )

    def _estimate_density_impact(
        self,
        future_state: torch.Tensor,
        odi_result: Optional[DensityIndexResult],
    ) -> float:
        """估计密度影响"""
        if odi_result is None:
            return 0.0

        odi = odi_result.odi if hasattr(odi_result, 'odi') else 0.5
        state_norm = float(future_state.norm().item())

        # 高密度 + 大状态变化 → 更大的密度影响
        impact = float(torch.tanh(torch.tensor(state_norm * odi)).item())
        return impact


# ─── CounterfactualSelector ───

class CounterfactualSelector:
    """反事实筛选器

    比较事实轨迹与反事实轨迹，计算选择压力。

    核心算法：
    1. 计算每条反事实轨迹与事实轨迹的差异度
    2. 计算每条反事实轨迹的延续概率
    3. 选择压力 = 反事实轨迹与事实轨迹的延续概率差
    4. 反事实偏置 = 选择压力加权的方向向量
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_COUNTERFACTUAL_CONFIG, **(config or {})}

    def contrast(
        self,
        factual_consequence: ConsequenceEstimate,
        counterfactual_consequences: List[ConsequenceEstimate],
    ) -> List[ContrastResult]:
        """比较事实轨迹与反事实轨迹

        Parameters
        ----------
        factual_consequence : ConsequenceEstimate
            事实轨迹的后果估计
        counterfactual_consequences : List[ConsequenceEstimate]
            反事实轨迹的后果估计列表

        Returns
        -------
        List[ContrastResult]
            对比结果列表
        """
        results = []
        threshold = self.config['contrast_threshold']

        for cf_conseq in counterfactual_consequences:
            # 差异距离（使用分支 ID 查找对应分支的叶节点）
            # 这里简化为延续概率差的绝对值
            cont_gap = cf_conseq.continuation_probability - factual_consequence.continuation_probability
            struct_gap = cf_conseq.structural_impact - factual_consequence.structural_impact
            density_gap = cf_conseq.density_impact - factual_consequence.density_impact

            # 综合差异距离
            divergence_dist = math.sqrt(cont_gap ** 2 + struct_gap ** 2 + density_gap ** 2)

            is_meaningful = divergence_dist >= threshold

            result = ContrastResult(
                factual_branch_id=factual_consequence.branch_id,
                counterfactual_branch_id=cf_conseq.branch_id,
                divergence_distance=divergence_dist,
                continuation_gap=cont_gap,
                structural_gap=struct_gap,
                density_gap=density_gap,
                is_meaningful=is_meaningful,
            )
            results.append(result)

        return results

    def compute_selection_pressure(
        self,
        contrasts: List[ContrastResult],
    ) -> float:
        """计算选择压力

        选择压力 = 所有有意义的对比中，延续概率差的均值。
        正值表示反事实轨迹整体上比事实轨迹有更高的延续概率。

        Parameters
        ----------
        contrasts : List[ContrastResult]
            对比结果列表

        Returns
        -------
        float
            选择压力值
        """
        meaningful = [c for c in contrasts if c.is_meaningful]
        if not meaningful:
            return 0.0

        scale = self.config['selection_pressure_scale']
        mean_gap = np.mean([c.continuation_gap for c in meaningful])
        return float(np.clip(mean_gap * scale, -1.0, 1.0))

    def compute_counterfactual_bias(
        self,
        contrasts: List[ContrastResult],
        branch_states: Dict[str, torch.Tensor],
        factual_state: torch.Tensor,
    ) -> torch.Tensor:
        """计算反事实偏置向量

        反事实偏置 = 选择压力加权的方向向量
        方向 = 反事实轨迹相对于事实轨迹的差异方向

        Parameters
        ----------
        contrasts : List[ContrastResult]
            对比结果列表
        branch_states : Dict[str, torch.Tensor]
            分支 ID → 叶节点状态向量
        factual_state : torch.Tensor
            事实轨迹的当前状态

        Returns
        -------
        torch.Tensor
            反事实偏置向量
        """
        meaningful = [c for c in contrasts if c.is_meaningful]
        if not meaningful:
            return torch.zeros_like(factual_state)

        bias = torch.zeros_like(factual_state)
        total_weight = 0.0

        for contrast in meaningful:
            cf_state = branch_states.get(contrast.counterfactual_branch_id)
            if cf_state is None:
                continue

            # 方向 = 反事实状态 - 事实状态
            direction = cf_state - factual_state
            # 权重 = 延续概率差（正 = 反事实更好）
            weight = contrast.continuation_gap

            bias += weight * direction
            total_weight += abs(weight)

        if total_weight > 1e-10:
            bias = bias / total_weight

        # 缩放
        bias_strength = self.config['bias_strength']
        bias = bias * bias_strength

        return bias


# ─── CounterfactualEngine ───

class CounterfactualEngine:
    """反事实引擎

    协调四个子组件，提供统一的 explore/maintain/project/select/update 接口。

    工作流程：
    1. explore()：在当前位置探索可能的分岔
    2. maintain()：维持所有活跃轨迹
    3. project()：投影所有轨迹的后果
    4. select()：比较事实与反事实，生成偏置
    5. update()：用实际差异更新轨迹状态

    语义防火墙：
    - "反事实" ≠ "假设"（没有认知主体）
    - "反事实" ≠ "想象"（没有心理活动）
    - "反事实" = "并行差异轨迹的探索与比较"
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_COUNTERFACTUAL_CONFIG, **(config or {})}
        self.trajectory_maintainer = ParallelTrajectoryMaintainer(self.config)
        self.divergence_tracker = DivergencePointTracker(self.config)
        self.consequence_projector = ConsequenceProjector(self.config)
        self.selector = CounterfactualSelector(self.config)

        # 事实分支 ID（始终维护一条事实轨迹）
        self._factual_branch_id: Optional[str] = None
        self._step_count: int = 0

        # 结果历史
        self._results: List[CounterfactualResult] = []

    def explore(
        self,
        current_state: torch.Tensor,
        candidate_directions: Optional[List[torch.Tensor]] = None,
        direction_probs: Optional[List[float]] = None,
        odi_result: Optional[DensityIndexResult] = None,
        timestamp: Optional[int] = None,
    ) -> CounterfactualResult:
        """在当前位置探索可能的分岔

        1. 检测分岔点
        2. 如检测到分岔，创建反事实轨迹分支
        3. 返回探索结果

        Parameters
        ----------
        current_state : torch.Tensor
            当前差异状态
        candidate_directions : Optional[List[torch.Tensor]]
            候选方向（不传则自动生成）
        direction_probs : Optional[List[float]]
            各方向概率
        odi_result : Optional[DensityIndexResult]
            ODI 结果（用于门控）
        timestamp : Optional[int]
            时间戳

        Returns
        -------
        CounterfactualResult
            探索结果
        """
        step = timestamp if timestamp is not None else self._step_count

        # ODI 门控
        odi_gated = False
        if odi_result is not None:
            odi = odi_result.odi if hasattr(odi_result, 'odi') else 0.5
            if odi < self.config['odi_suppress_threshold']:
                odi_gated = True
                return CounterfactualResult(
                    counterfactual_active=False,
                    odi_gated=True,
                    timestamp=step,
                    metadata={'reason': 'ODI too low'},
                )
            elif odi < self.config['odi_partial_threshold']:
                odi_gated = True

        # 确保事实分支存在
        if self._factual_branch_id is None:
            factual_branch = self.trajectory_maintainer.create_branch(
                root_state=current_state,
                divergence_type=DivergenceType.STRUCTURAL,
                initial_probability=1.0,
                creation_step=step,
            )
            if factual_branch:
                self._factual_branch_id = factual_branch.branch_id

        # 自动生成候选方向（如未提供）
        if candidate_directions is None:
            candidate_directions = self._generate_candidate_directions(current_state)

        # 检测分岔点
        div_point = self.divergence_tracker.detect_divergence(
            current_state=current_state,
            candidate_directions=candidate_directions,
            direction_probs=direction_probs,
            timestamp=step,
        )

        # 创建反事实分支
        new_branches = []
        if div_point is not None and div_point.is_significant:
            for i, direction in enumerate(candidate_directions):
                # 每个候选方向创建一个分支
                branch_state = current_state + direction * 0.1  # 小步偏移
                prob = direction_probs[i] / sum(direction_probs) if direction_probs else 1.0 / len(candidate_directions)

                branch = self.trajectory_maintainer.create_branch(
                    root_state=branch_state,
                    divergence_type=DivergenceType.COUNTERFACTUAL,
                    initial_probability=prob,
                    creation_step=step,
                )
                if branch:
                    new_branches.append(branch)

        # 剪枝和合并
        pruned = self.trajectory_maintainer.prune_branches()
        merged = self.trajectory_maintainer.merge_similar_branches()

        result = CounterfactualResult(
            counterfactual_active=self.trajectory_maintainer.n_active_branches >= self.config['min_branches'],
            n_active_branches=self.trajectory_maintainer.n_active_branches,
            n_divergence_points=self.divergence_tracker.n_divergence_points,
            odi_gated=odi_gated,
            timestamp=step,
            metadata={
                'new_branches': len(new_branches),
                'pruned': len(pruned),
                'merged': len(merged),
                'divergence_detected': div_point is not None,
            },
        )

        self._results.append(result)
        return result

    def maintain(
        self,
        current_state: torch.Tensor,
        timestamp: Optional[int] = None,
    ) -> List[TrajectoryBranch]:
        """维持所有活跃轨迹

        将所有活跃分支的叶节点更新为当前状态的变体。

        Parameters
        ----------
        current_state : torch.Tensor
            当前差异状态
        timestamp : Optional[int]
            时间戳

        Returns
        -------
        List[TrajectoryBranch]
            更新后的活跃分支列表
        """
        step = timestamp if timestamp is not None else self._step_count
        active_branches = self.trajectory_maintainer.get_active_branches()

        for branch in active_branches:
            # 添加小偏移以维持轨迹差异性
            noise_scale = 0.01 * (hash(branch.branch_id) % 10) / 10.0
            noise = torch.randn_like(current_state) * noise_scale
            new_state = current_state + noise

            self.trajectory_maintainer.extend_branch(
                branch_id=branch.branch_id,
                new_state=new_state,
                prob_factor=0.99,
                timestamp=step,
            )

        # 剪枝和合并
        self.trajectory_maintainer.prune_branches()
        self.trajectory_maintainer.merge_similar_branches()

        return self.trajectory_maintainer.get_active_branches()

    def project(
        self,
        odi_result: Optional[DensityIndexResult] = None,
        method: Optional[str] = None,
    ) -> List[ConsequenceEstimate]:
        """投影所有活跃轨迹的后果

        Parameters
        ----------
        odi_result : Optional[DensityIndexResult]
            ODI 结果
        method : Optional[str]
            投影方法

        Returns
        -------
        List[ConsequenceEstimate]
            后果估计列表
        """
        active_branches = self.trajectory_maintainer.get_active_branches()
        consequences = []

        for branch in active_branches:
            consequence = self.consequence_projector.project(
                branch=branch,
                odi_result=odi_result,
                method=method,
            )
            consequences.append(consequence)

        return consequences

    def select(
        self,
        consequences: List[ConsequenceEstimate],
    ) -> CounterfactualResult:
        """比较事实与反事实，生成偏置

        Parameters
        ----------
        consequences : List[ConsequenceEstimate]
            后果估计列表

        Returns
        -------
        CounterfactualResult
            选择结果（含反事实偏置）
        """
        # 分离事实和反事实后果
        factual_conseq = None
        cf_conseqs = []

        for c in consequences:
            if c.branch_id == self._factual_branch_id:
                factual_conseq = c
            else:
                cf_conseqs.append(c)

        if factual_conseq is None or not cf_conseqs:
            return CounterfactualResult(
                counterfactual_active=False,
                n_active_branches=self.trajectory_maintainer.n_active_branches,
                timestamp=self._step_count,
                metadata={'reason': 'insufficient branches for contrast'},
            )

        # 对比
        contrasts = self.selector.contrast(factual_conseq, cf_conseqs)

        # 选择压力
        pressure = self.selector.compute_selection_pressure(contrasts)

        # 反事实偏置
        branch_states = {}
        active_branches = self.trajectory_maintainer.get_active_branches()
        for branch in active_branches:
            if branch.leaf is not None:
                branch_states[branch.branch_id] = branch.leaf.state_vector

        factual_state = branch_states.get(self._factual_branch_id, torch.zeros(1))
        bias = self.selector.compute_counterfactual_bias(
            contrasts=contrasts,
            branch_states=branch_states,
            factual_state=factual_state,
        )

        result = CounterfactualResult(
            counterfactual_active=True,
            n_active_branches=self.trajectory_maintainer.n_active_branches,
            n_divergence_points=self.divergence_tracker.n_divergence_points,
            selection_pressure=pressure,
            counterfactual_bias=bias,
            contrasts=contrasts,
            consequences=consequences,
            timestamp=self._step_count,
        )

        self._results.append(result)
        return result

    def update(
        self,
        actual_state: torch.Tensor,
        timestamp: Optional[int] = None,
    ) -> Optional[CounterfactualResult]:
        """用实际差异更新轨迹状态

        更新事实分支，并检查反事实分支的延续概率。

        Parameters
        ----------
        actual_state : torch.Tensor
            实际差异状态
        timestamp : Optional[int]
            时间戳

        Returns
        -------
        Optional[CounterfactualResult]
            更新结果
        """
        step = timestamp if timestamp is not None else self._step_count

        # 更新事实分支
        if self._factual_branch_id is not None:
            self.trajectory_maintainer.extend_branch(
                branch_id=self._factual_branch_id,
                new_state=actual_state,
                prob_factor=1.0,  # 事实分支概率不变
                timestamp=step,
            )

        # 更新反事实分支（概率衰减）
        active_branches = self.trajectory_maintainer.get_active_branches()
        for branch in active_branches:
            if branch.branch_id != self._factual_branch_id:
                # 反事实分支概率衰减
                noise = torch.randn_like(actual_state) * 0.01
                self.trajectory_maintainer.extend_branch(
                    branch_id=branch.branch_id,
                    new_state=actual_state + noise,
                    prob_factor=self.config['continuation_decay'],
                    timestamp=step,
                )

        # 剪枝
        pruned = self.trajectory_maintainer.prune_branches()

        result = CounterfactualResult(
            counterfactual_active=self.trajectory_maintainer.n_active_branches >= self.config['min_branches'],
            n_active_branches=self.trajectory_maintainer.n_active_branches,
            n_divergence_points=self.divergence_tracker.n_divergence_points,
            timestamp=step,
            metadata={'pruned': len(pruned)},
        )

        self._results.append(result)
        return result

    def step(self):
        """步进"""
        self._step_count += 1
        self.trajectory_maintainer.step()
        self.divergence_tracker.step()

    @property
    def latest_result(self) -> Optional[CounterfactualResult]:
        """最近一次结果"""
        return self._results[-1] if self._results else None

    @property
    def is_active(self) -> bool:
        """反事实探索是否活跃"""
        return self.trajectory_maintainer.n_active_branches >= self.config['min_branches']

    @property
    def n_active_branches(self) -> int:
        """活跃分支数"""
        return self.trajectory_maintainer.n_active_branches

    def get_summary(self) -> Dict:
        """获取摘要"""
        return {
            'n_total_branches': self.trajectory_maintainer.n_total_branches,
            'n_active_branches': self.trajectory_maintainer.n_active_branches,
            'n_divergence_points': self.divergence_tracker.n_divergence_points,
            'n_results': len(self._results),
            'factual_branch_id': self._factual_branch_id,
            'is_active': self.is_active,
            'trajectory_summary': self.trajectory_maintainer.get_summary(),
        }

    def reset(self):
        """重置所有状态"""
        self.trajectory_maintainer.reset()
        self.divergence_tracker.reset()
        self._factual_branch_id = None
        self._step_count = 0
        self._results.clear()

    # ─── 内部方法 ───

    def _generate_candidate_directions(
        self,
        current_state: torch.Tensor,
    ) -> List[torch.Tensor]:
        """自动生成候选方向

        基于当前状态生成几个扰动方向作为候选。
        """
        dim = current_state.shape[0]
        directions = []

        # 主方向（当前状态的归一化）
        norm = current_state.norm().item()
        if norm > 1e-8:
            directions.append(current_state / norm)
        else:
            directions.append(torch.ones(dim) / math.sqrt(dim))

        # 正交扰动方向
        for i in range(min(3, dim)):
            perturbation = torch.randn(dim)
            # 与主方向正交化
            if directions:
                main_dir = directions[0]
                perturbation = perturbation - torch.dot(perturbation, main_dir) * main_dir
            pert_norm = perturbation.norm().item()
            if pert_norm > 1e-8:
                directions.append(perturbation / pert_norm)
            else:
                directions.append(torch.randn(dim))
                directions[-1] = directions[-1] / directions[-1].norm().item()

        return directions[:4]  # 最多4个候选方向
