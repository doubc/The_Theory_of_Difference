"""
engine/lateral_coupling.py — 横向耦合机制 (Lateral Coupling Mechanism)

Phase 2 P2 组件 #4

职责：管理同一层级内多个前主体态结构之间的横向相互作用。

理论依据：
- 《Appearing Before Appearing》§3.5：选择压力来自共同环境中的共存
  "多个复制模式共存于共享差异环境中，组织差异直接转化为延续概率差异"
- 《象界》第六章：共存 → 选择
  "选择不是外部机制从外部作用于模式，而是模式自身组织差异在连续中的统计结果"
- 横向耦合是选择压力的结构基础：没有横向交互，就没有真正的选择

与已有组件的区别：
- CrossLayerGravityModulator：跨层级（垂直）引力调制
- LateralCoupler：同层级（水平）耦合交互
- PreSubjectivityConvergence：单结构内部六机制耦合
- LateralCoupler：多结构之间的组织间耦合

横向耦合的三种模式：
1. 边界交互（boundary_interaction）：相邻结构的边界重叠/竞争/协作
2. 耦合场扩散（coupling_field_diffusion）：结构产生的耦合场向邻近区域扩散
3. 选择压力传导（selection_pressure_transmission）：一个结构的密度变化影响邻居的延续概率

设计原则：
- 纯低语义：不涉及"竞争"、"合作"等意图性概念
- 局部性：只与邻近结构交互（A1 局域性约束）
- 可叠加：多个邻居的耦合效应可以叠加
- 可逆：耦合强度随距离和密度差衰减
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

from engine.organizational_density_index import DensityIndexResult
from engine.six_threshold_detector import SixThresholdResult


# ─── 耦合类型 ───
class CouplingType(Enum):
    """横向耦合的交互类型（纯结构描述，无语义内容）"""
    BOUNDARY_OVERLAP = "boundary_overlap"           # 边界重叠
    COUPLING_FIELD_DIFFUSION = "field_diffusion"     # 耦合场扩散
    DENSITY_GRADIENT = "density_gradient"            # 密度梯度驱动


# ─── 默认配置 ───
DEFAULT_LATERAL_CONFIG = {
    'max_coupling_distance': 3.0,       # 最大耦合距离（网格单位）
    'coupling_decay_rate': 0.3,         # 耦合强度随距离的衰减率
    'boundary_overlap_threshold': 0.1,  # 边界重叠判定阈值
    'field_diffusion_rate': 0.05,       # 耦合场扩散速率
    'density_gradient_sensitivity': 0.2,  # 密度梯度敏感度
    'max_neighbors': 6,                 # 最大邻居数（六邻域）
    'coupling_cap': 1.0,               # 单对结构最大耦合强度
}


@dataclass
class StructureHandle:
    """同一层中一个结构的轻量引用"""
    structure_id: int
    position: np.ndarray                # 空间位置 (x, y) 或 (x, y, z)
    odi: float = 0.0                    # 组织密度指数
    boundary_radius: float = 1.0        # 边界半径
    coupling_field_strength: float = 0.0  # 当前耦合场强度


@dataclass
class LateralCouplingPair:
    """一对结构之间的横向耦合关系"""
    structure_a_id: int
    structure_b_id: int
    distance: float = 0.0
    coupling_type: CouplingType = CouplingType.BOUNDARY_OVERLAP
    coupling_strength: float = 0.0      # [0, 1]
    boundary_overlap_ratio: float = 0.0  # 边界重叠比例
    density_difference: float = 0.0     # ODI 差值
    is_active: bool = False             # 是否处于耦合状态

    def __repr__(self):
        return (f"Couple[{self.structure_a_id}↔{self.structure_b_id}] "
                f"d={self.distance:.2f} s={self.coupling_strength:.3f} "
                f"type={self.coupling_type.value}")


@dataclass
class LateralCouplingReport:
    """单步横向耦合报告"""
    timestamp: int
    n_structures: int = 0
    n_active_pairs: int = 0
    pairs: List[LateralCouplingPair] = field(default_factory=list)
    # 每个结构受到的净耦合影响: structure_id → net_coupling_effect
    net_effects: Dict[int, float] = field(default_factory=dict)
    # 选择压力变化: structure_id → selection_pressure_delta
    selection_pressure_deltas: Dict[int, float] = field(default_factory=dict)
    # 耦合场分布快照: structure_id → field_strength
    field_snapshot: Dict[int, float] = field(default_factory=dict)

    @property
    def total_coupling_strength(self) -> float:
        return sum(p.coupling_strength for p in self.pairs if p.is_active)

    @property
    def mean_coupling_strength(self) -> float:
        active = [p for p in self.pairs if p.is_active]
        if not active:
            return 0.0
        return sum(p.coupling_strength for p in active) / len(active)


class LateralCoupler:
    """横向耦合管理器

    管理同一层级内多个结构之间的横向耦合交互。

    核心循环：
    1. 注册/更新结构位置和状态
    2. 计算结构对之间的距离和耦合类型
    3. 计算每对结构的耦合强度
    4. 汇总每个结构受到的净耦合影响
    5. 计算选择压力变化

    使用方式:
        coupler = LateralCoupler(config={...})
        coupler.register_structure(structure_id=0, position=np.array([0, 0]), odi=0.6)
        coupler.register_structure(structure_id=1, position=np.array([1, 0]), odi=0.7)
        report = coupler.compute_step(timestamp=0)
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_LATERAL_CONFIG, **(config or {})}
        self._structures: Dict[int, StructureHandle] = {}
        self._coupling_pairs: Dict[Tuple[int, int], LateralCouplingPair] = {}
        self._reports: List[LateralCouplingReport] = []

    # ─── 结构注册 ───

    def register_structure(
        self,
        structure_id: int,
        position: np.ndarray,
        odi: float = 0.0,
        boundary_radius: float = 1.0,
        coupling_field_strength: float = 0.0,
    ) -> None:
        """注册或更新一个结构"""
        self._structures[structure_id] = StructureHandle(
            structure_id=structure_id,
            position=np.asarray(position, dtype=np.float64),
            odi=float(odi),
            boundary_radius=float(boundary_radius),
            coupling_field_strength=float(coupling_field_strength),
        )

    def remove_structure(self, structure_id: int) -> None:
        """移除一个结构及其所有耦合对"""
        if structure_id in self._structures:
            del self._structures[structure_id]
        # 清理相关耦合对
        to_remove = [
            key for key in self._coupling_pairs
            if structure_id in key
        ]
        for key in to_remove:
            del self._coupling_pairs[key]

    def update_structure(
        self,
        structure_id: int,
        position: Optional[np.ndarray] = None,
        odi: Optional[float] = None,
        boundary_radius: Optional[float] = None,
        coupling_field_strength: Optional[float] = None,
    ) -> None:
        """更新结构属性"""
        if structure_id not in self._structures:
            raise KeyError(f"Structure {structure_id} not registered")
        s = self._structures[structure_id]
        if position is not None:
            s.position = np.asarray(position, dtype=np.float64)
        if odi is not None:
            s.odi = float(odi)
        if boundary_radius is not None:
            s.boundary_radius = float(boundary_radius)
        if coupling_field_strength is not None:
            s.coupling_field_strength = float(coupling_field_strength)

    @property
    def n_structures(self) -> int:
        return len(self._structures)

    @property
    def structure_ids(self) -> List[int]:
        return list(self._structures.keys())

    # ─── 核心计算 ───

    def compute_step(self, timestamp: int) -> LateralCouplingReport:
        """执行单步横向耦合计算"""
        # 1. 发现/更新耦合对
        self._discover_pairs()

        # 2. 计算每对耦合强度
        for key, pair in self._coupling_pairs.items():
            self._compute_pair_coupling(pair)

        # 3. 汇总净影响
        net_effects = self._compute_net_effects()

        # 4. 计算选择压力变化
        sp_deltas = self._compute_selection_pressure(net_effects)

        # 5. 构建报告
        active_pairs = [p for p in self._coupling_pairs.values() if p.is_active]
        report = LateralCouplingReport(
            timestamp=timestamp,
            n_structures=len(self._structures),
            n_active_pairs=len(active_pairs),
            pairs=list(self._coupling_pairs.values()),
            net_effects=net_effects,
            selection_pressure_deltas=sp_deltas,
            field_snapshot={
                sid: s.coupling_field_strength
                for sid, s in self._structures.items()
            },
        )
        self._reports.append(report)
        return report

    def _discover_pairs(self) -> None:
        """发现所有在耦合距离内的结构对"""
        ids = sorted(self._structures.keys())
        max_dist = self.config['max_coupling_distance']

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a_id, b_id = ids[i], ids[j]
                key = (a_id, b_id)

                a = self._structures[a_id]
                b = self._structures[b_id]
                dist = float(np.linalg.norm(a.position - b.position))

                if dist > max_dist:
                    continue

                if key not in self._coupling_pairs:
                    self._coupling_pairs[key] = LateralCouplingPair(
                        structure_a_id=a_id,
                        structure_b_id=b_id,
                        distance=dist,
                    )
                else:
                    self._coupling_pairs[key].distance = dist

    def _compute_pair_coupling(self, pair: LateralCouplingPair) -> None:
        """计算单个耦合对的耦合强度和类型"""
        a = self._structures.get(pair.structure_a_id)
        b = self._structures.get(pair.structure_b_id)
        if a is None or b is None:
            pair.is_active = False
            return

        max_dist = self.config['max_coupling_distance']
        decay = self.config['coupling_decay_rate']

        # 距离衰减因子
        distance_factor = max(0.0, 1.0 - (pair.distance / max_dist) ** decay)

        # 判断耦合类型
        boundary_overlap = self._compute_boundary_overlap(a, b, pair.distance)
        pair.boundary_overlap_ratio = boundary_overlap
        pair.density_difference = a.odi - b.odi

        if boundary_overlap > self.config['boundary_overlap_threshold']:
            pair.coupling_type = CouplingType.BOUNDARY_OVERLAP
            pair.coupling_strength = boundary_overlap * distance_factor
        elif abs(a.odi - b.odi) > self.config['density_gradient_sensitivity']:
            pair.coupling_type = CouplingType.DENSITY_GRADIENT
            # 密度梯度驱动：高密度向低密度传导
            gradient = abs(a.odi - b.odi)
            pair.coupling_strength = gradient * distance_factor * self.config['density_gradient_sensitivity']
        else:
            pair.coupling_type = CouplingType.COUPLING_FIELD_DIFFUSION
            # 耦合场扩散：场强度的平均
            avg_field = (a.coupling_field_strength + b.coupling_field_strength) / 2
            pair.coupling_strength = avg_field * distance_factor * self.config['field_diffusion_rate']

        # 上限截断
        pair.coupling_strength = min(pair.coupling_strength, self.config['coupling_cap'])
        pair.is_active = pair.coupling_strength > 0.01

    def _compute_boundary_overlap(
        self, a: StructureHandle, b: StructureHandle, distance: float
    ) -> float:
        """计算两个结构的边界重叠比例"""
        combined_radius = a.boundary_radius + b.boundary_radius
        if distance >= combined_radius:
            return 0.0
        # 简化的线性重叠模型
        overlap = 1.0 - (distance / combined_radius)
        return max(0.0, min(1.0, overlap))

    def _compute_net_effects(self) -> Dict[int, float]:
        """计算每个结构受到的净耦合影响"""
        net: Dict[int, float] = {sid: 0.0 for sid in self._structures}

        for pair in self._coupling_pairs.values():
            if not pair.is_active:
                continue

            a_id = pair.structure_a_id
            b_id = pair.structure_b_id

            # 耦合效应方向：从高密度流向低密度
            a = self._structures.get(a_id)
            b = self._structures.get(b_id)
            if a is None or b is None:
                continue

            effect = pair.coupling_strength
            if a.odi > b.odi:
                # a 的密度高于 b：a 对 b 施加正向影响，b 对 a 施加负向影响
                net[b_id] += effect
                net[a_id] -= effect * 0.5  # 高密度端受影响较小
            elif b.odi > a.odi:
                net[a_id] += effect
                net[b_id] -= effect * 0.5
            else:
                # 密度相等：对称耦合
                net[a_id] += effect * 0.1
                net[b_id] += effect * 0.1

        return net

    def _compute_selection_pressure(
        self, net_effects: Dict[int, float]
    ) -> Dict[int, float]:
        """根据净耦合效应计算选择压力变化"""
        sp_deltas: Dict[int, float] = {}
        for sid, effect in net_effects.items():
            s = self._structures.get(sid)
            if s is None:
                continue
            # 选择压力变化 = 净耦合效应 × 当前密度（密度越高，压力放大越明显）
            sp_deltas[sid] = effect * s.odi
        return sp_deltas

    # ─── 查询接口 ───

    def get_neighbors(self, structure_id: int) -> List[LateralCouplingPair]:
        """获取一个结构的所有活跃耦合对"""
        return [
            p for p in self._coupling_pairs.values()
            if p.is_active and (p.structure_a_id == structure_id or p.structure_b_id == structure_id)
        ]

    def get_coupling_strength(self, a_id: int, b_id: int) -> float:
        """获取两个结构之间的耦合强度"""
        key = (min(a_id, b_id), max(a_id, b_id))
        pair = self._coupling_pairs.get(key)
        if pair is None:
            return 0.0
        return pair.coupling_strength if pair.is_active else 0.0

    def get_report_history(self, limit: int = 100) -> List[LateralCouplingReport]:
        return self._reports[-limit:]

    def reset(self) -> None:
        """重置所有状态"""
        self._structures.clear()
        self._coupling_pairs.clear()
        self._reports.clear()
