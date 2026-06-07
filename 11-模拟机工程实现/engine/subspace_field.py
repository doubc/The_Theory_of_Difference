"""
Phase 11 P1: Subspace Decomposition Infrastructure — subspace_field.py

将一个统一离散差异空间分解为多个并行的子空间（subspaces），
每个子空间受相同的九公理但不同的参数化约束，子空间之间通过
受控耦合端口通信。

核心概念:
  - SubspaceSpec: 子空间的规格定义（哪些比特 + 什么参数）
  - SubspaceCouplingPort: 跨子空间通信信道
  - SubspaceField: 子空间场的容器（管理所有子空间及其耦合）
  - 三种分配策略: 静态分区 / 交错分配 / 随机分区

设计目标:
  1. 向后兼容: N0=1 子空间 == 原始行为
  2. 纯粹的数据结构层: 不依赖 axioms_v2 / engine 运行时状态
  3. 所有分配策略可复现（seed-aware）
  4. 耦合端口支持多方向拓扑

Usage:
    from engine.subspace_field import (
        SubspaceField, SubspaceSpec, CouplingTopology, Rules,
        allocate_static, allocate_interleaved, allocate_random,
    )

    # 创建三个静态子空间
    indices = allocate_static(N0=60, k=3)
    field = SubspaceField(
        subspaces={
            "g": SubspaceSpec(indices[0], Rules(binding_multiplier=0.5)),
            "e": SubspaceSpec(indices[1], Rules(binding_multiplier=1.0)),
            "s": SubspaceSpec(indices[2], Rules(binding_multiplier=3.0)),
        },
        coupling_strength=0.3,
    )
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple


# =============================================================================
# 子空间参数化规则
# =============================================================================

@dataclass(frozen=True)
class Rules:
    """子空间特有的九公理参数化。

    每个参数可以独立配置，让不同子空间表现不同的"物理"行为。
    当所有参数取默认值时，行为与原始统一空间一致。
    """
    binding_multiplier: float = 1.0
    """绑定强度乘子 ∈ [0.2, 5.0]。

    >1.0 → 绑定更强（L1 形成更快、更紧密）
    <1.0 → 绑定更弱（L1 形成更慢或不形成）
    ≤0.2 → 理论上禁止任何绑定
    """

    direction_bias: float = 0.5
    """方向偏好 ∈ [0.0, 1.0]。

    0.5  = 无偏好（双向对称）
    >0.5 = 源→汇方向性更强（时间之箭）
    <0.5 = 汇→源方向性更强（逆时间）
    1.0  = 完全单向（纯源→汇）
    """

    conservation_tightness: float = 0.05
    """守恒紧度 ∈ [0.01, 0.1] — A5 残差容忍度。

    越小 → 越严格（升维压力更大）
    越大 → 越宽松（升维更难触发）
    """

    seal_threshold_multiplier: float = 1.0
    """封口阈值乘子 ∈ [0.5, 2.0]。

    影响 sealing_activation_threshold 的计算:
        effective_threshold = max(0.75 * N_sub, 30) * multiplier
    """

    def check(self) -> None:
        """参数边界检查。"""
        assert 0.2 <= self.binding_multiplier <= 5.0, \
            f"binding_multiplier={self.binding_multiplier} out of [0.2, 5.0]"
        assert 0.0 <= self.direction_bias <= 1.0, \
            f"direction_bias={self.direction_bias} out of [0.0, 1.0]"
        assert 0.01 <= self.conservation_tightness <= 0.1, \
            f"conservation_tightness={self.conservation_tightness} out of [0.01, 0.1]"
        assert 0.5 <= self.seal_threshold_multiplier <= 2.0, \
            f"seal_threshold_multiplier={self.seal_threshold_multiplier} out of [0.5, 2.0]"

    @staticmethod
    def default() -> Rules:
        """返回默认参数（等价于统一空间行为）。"""
        return Rules()


# =============================================================================
# 分配策略
# =============================================================================

def allocate_static(N0: int, k: int) -> List[Set[int]]:
    """静态分区：N0 个比特预先划分为 k 个等尺寸子空间。

    每个子空间获得 floor(N0/k) 或 ceil(N0/k) 个比特。
    前 N0 % k 个子空间多得一个比特。

    返回 List[Set[int]]，每个元素是子空间的比特索引集。

    示例: allocate_static(30, 3) → [{0..9}, {10..19}, {20..29}]
    """
    assert N0 > 0, f"N0 must be positive, got {N0}"
    assert 1 <= k <= N0, f"k must be in [1, N0], got k={k}, N0={N0}"

    base = N0 // k
    extra = N0 % k

    result: List[Set[int]] = []
    start = 0
    for i in range(k):
        size = base + (1 if i < extra else 0)
        result.append(set(range(start, start + size)))
        start += size

    return result


def allocate_interleaved(N0: int, k: int) -> List[Set[int]]:
    """交错（轮询）分配：bit_id % k 决定子空间归属。

    确保每个子空间均匀分布在索引空间上，避免"块边界"伪影。

    示例: allocate_interleaved(12, 3) → [{0,3,6,9}, {1,4,7,10}, {2,5,8,11}]
    """
    assert N0 > 0, f"N0 must be positive, got {N0}"
    assert 1 <= k <= N0, f"k must be in [1, N0], got k={k}, N0={N0}"

    result: List[Set[int]] = [set() for _ in range(k)]
    for bit in range(N0):
        result[bit % k].add(bit)

    return result


def allocate_random(N0: int, k: int, seed: int = 42) -> List[Set[int]]:
    """随机分区：每个比特随机分配到 k 个子空间之一。

    使用指定的 seed 确保可复现。

    **注意**: 随机分区可能导致子空间大小不均，
    且可能有子空间为空（k 接近 N0 时）。
    """
    assert N0 > 0, f"N0 must be positive, got {N0}"
    assert 1 <= k <= N0, f"k must be in [1, N0], got k={k}, N0={N0}"

    rng = random.Random(seed)
    result: List[Set[int]] = [set() for _ in range(k)]
    for bit in range(N0):
        result[rng.randint(0, k - 1)].add(bit)

    return result


# =============================================================================
# 耦合拓扑
# =============================================================================

class CouplingDirection(Enum):
    """耦合方向。"""
    BIDIRECTIONAL = auto()   # 双向对称耦合（默认）
    UNIDIRECTIONAL_FWD = auto()  # 单向：源→目标
    UNIDIRECTIONAL_REV = auto()  # 单向：目标→源
    FULLY_CONNECTED = auto()  # 全连通（所有子空间之间双向）


@dataclass
class CouplingTopology:
    """子空间之间的耦合拓扑。

    描述一个子空间如何连接到其 peer 子空间。
    """
    direction: CouplingDirection = CouplingDirection.BIDIRECTIONAL
    """耦合方向。"""

    strength: float = 0.0
    """耦合强度 ∈ [0.0, 1.0]。

    0.0 = 完全隔离（子空间独立演化）
    1.0 = 完全耦合（子空间边界模糊，趋近统一空间）
    """

    peer_names: Set[str] = field(default_factory=set)
    """此子空间连接到的目标子空间名称集合。

    FULLY_CONNECTED 模式下, peer_names 被忽略（自动全连通）。
    空集表示无耦合。
    """


# =============================================================================
# 子空间规格
# =============================================================================

@dataclass
class SubspaceSpec:
    """子空间的完整规格定义。"""
    bit_indices: Set[int]
    """属于该子空间的比特索引集（子集 [0, N0-1]）。"""

    rules: Rules = field(default_factory=Rules)
    """该子空间特有的参数化规则。"""

    coupling: CouplingTopology = field(default_factory=CouplingTopology)
    """该子空间的耦合拓扑（连接哪些 peer + 方向 + 强度）。"""

    name: str = ""
    """子空间名称（用于标识和日志；空字符串表示自动生成）。"""

    def __post_init__(self) -> None:
        if self.name == "":
            self.name = f"subspace_{id(self)}"
        self.rules.check()

    @property
    def size(self) -> int:
        """该子空间中的比特数。"""
        return len(self.bit_indices)

    def __repr__(self) -> str:
        return (
            f"SubspaceSpec("
            f"name={self.name!r}, size={self.size}, "
            f"binding={self.rules.binding_multiplier:.2f}, "
            f"coupling={self.coupling.strength:.2f})"
        )


# =============================================================================
# 子空间场（容器）
# =============================================================================

@dataclass
class _CouplingConnection:
    """内部使用的耦合连接记录。"""
    source: str
    target: str
    strength: float
    direction: CouplingDirection


class SubspaceField:
    """子空间场——管理所有子空间及其耦合的容器。

    这是 Phase 11 P1 的核心数据结构。它:
    - 维护所有子空间及其参数化
    - 管理子空间之间的耦合拓扑
    - 提供查询接口（某比特属于哪个子空间、跨子空间绑定强度等）
    - 向后兼容：N0 个子空间且全部默认规则等价于原始统一空间

    Examples:
        >>> indices = allocate_static(60, 3)
        >>> field = SubspaceField({
        ...     "g": SubspaceSpec(indices[0], Rules(binding_multiplier=0.5)),
        ...     "e": SubspaceSpec(indices[1]),
        ...     "s": SubspaceSpec(indices[2], Rules(binding_multiplier=3.0)),
        ... })
        >>> field.num_subspaces
        3
        >>> field.subspace_of_bit(5)
        'g'
        >>> field.bit_assignment  # 所有子空间的比特分配视图
    """

    def __init__(
        self,
        subspaces: Dict[str, SubspaceSpec],
        coupling_strength: float = 0.0,
        coupling_direction: CouplingDirection = CouplingDirection.BIDIRECTIONAL,
        global_coupling: bool = True,
    ):
        """
        Args:
            subspaces: 子空间名称 → SubspaceSpec 的映射
            coupling_strength: 全局耦合强度（覆盖各子空间独立设置）
            coupling_direction: 全局耦合方向（覆盖各子空间独立设置）
            global_coupling: 如果 True，所有子空间之间按全局耦合配置连接；
                             如果 False，使用各子空间独立设置的 coupling 拓扑
        """
        assert len(subspaces) > 0, "至少需要一个子空间"
        self._subspaces: Dict[str, SubspaceSpec] = dict(subspaces)
        self._global_coupling = global_coupling
        self._global_strength = coupling_strength
        self._global_direction = coupling_direction

        # 构建比特→子空间的反向索引
        self._bit_to_subspace: Dict[int, str] = {}
        for name, spec in self._subspaces.items():
            for bit in spec.bit_indices:
                if bit in self._bit_to_subspace:
                    raise ValueError(
                        f"比特 {bit} 同时属于 {self._bit_to_subspace[bit]} "
                        f"和 {name}——比特不可重叠分配给多个子空间"
                    )
                self._bit_to_subspace[bit] = name

        # 构建耦合连接列表
        self._connections: List[_CouplingConnection] = []
        self._build_connections()

    def _build_connections(self) -> None:
        """根据子空间拓扑配置构建耦合连接。"""
        names = list(self._subspaces.keys())

        if self._global_coupling:
            # 全局耦合：所有子空间之间按 global 配置连接
            for i, src in enumerate(names):
                for j, tgt in enumerate(names):
                    if i == j:
                        continue
                    # i < j: FWD direction; i > j: REV direction
                    # For BIDIRECTIONAL or UNIDIRECTIONAL direction, determine behavior
                    if self._global_direction == CouplingDirection.UNIDIRECTIONAL_FWD and i > j:
                        continue
                    if self._global_direction == CouplingDirection.UNIDIRECTIONAL_REV and i < j:
                        continue
                    self._connections.append(_CouplingConnection(
                        source=src, target=tgt,
                        strength=self._global_strength,
                        direction=self._global_direction,
                    ))
        else:
            # 各子空间独立拓扑
            for name, spec in self._subspaces.items():
                for peer in spec.coupling.peer_names:
                    strength = spec.coupling.strength
                    direction = spec.coupling.direction
                    self._connections.append(_CouplingConnection(
                        source=name, target=peer,
                        strength=strength, direction=direction,
                    ))

    # ── 属性 ────────────────────────────────────────────────────

    @property
    def num_subspaces(self) -> int:
        return len(self._subspaces)

    @property
    def space_names(self) -> List[str]:
        return list(self._subspaces.keys())

    @property
    def total_bits(self) -> int:
        return len(self._bit_to_subspace)

    @property
    def bit_assignment(self) -> Dict[int, str]:
        """返回 {比特索引: 子空间名称} 的只读视图。"""
        return dict(self._bit_to_subspace)

    @property
    def connections(self) -> List[_CouplingConnection]:
        """返回耦合连接的只读列表。"""
        return list(self._connections)

    # ── 查询接口 ─────────────────────────────────────────────────

    def subspace_of_bit(self, bit: int) -> str:
        """查询给定比特属于哪个子空间。"""
        if bit not in self._bit_to_subspace:
            raise KeyError(f"比特 {bit} 不在任何子空间中")
        return self._bit_to_subspace[bit]

    def get_spec(self, name: str) -> SubspaceSpec:
        """获取指定名称的子空间规格。"""
        return self._subspaces[name]

    def get_bits(self, name: str) -> Set[int]:
        """获取指定子空间的所有比特索引。"""
        return self._subspaces[name].bit_indices.copy()

    def coupled_pairs(self) -> List[Tuple[str, str, float]]:
        """返回所有耦合对 (源, 目标, 强度)。"""
        return [(c.source, c.target, c.strength) for c in self._connections]

    def coupling_strength_between(self, name_a: str, name_b: str) -> float:
        """查询两个子空间之间的耦合强度。

        如果两者之间无直接耦合，返回 0.0。
        """
        for c in self._connections:
            if {c.source, c.target} == {name_a, name_b}:
                return c.strength
        return 0.0

    def is_isolated(self) -> bool:
        """如果所有子空间之间耦合强度均为 0，返回 True。"""
        return all(c.strength == 0.0 for c in self._connections)

    def is_single(self) -> bool:
        """如果只有一个子空间（即原始统一空间模式），返回 True。"""
        return self.num_subspaces == 1

    def summary(self) -> Dict:
        """返回摘要字典（用于日志/实验报告）。"""
        subspaces_info = {}
        for name, spec in self._subspaces.items():
            subspaces_info[name] = {
                "size": spec.size,
                "rules": {
                    "binding_multiplier": spec.rules.binding_multiplier,
                    "direction_bias": spec.rules.direction_bias,
                    "conservation_tightness": spec.rules.conservation_tightness,
                    "seal_threshold_multiplier": spec.rules.seal_threshold_multiplier,
                },
            }
        return {
            "num_subspaces": self.num_subspaces,
            "total_bits": self.total_bits,
            "isolated": self.is_isolated(),
            "global_coupling": self._global_coupling,
            "global_strength": self._global_strength,
            "subspaces": subspaces_info,
            "connections": [
                {"source": c.source, "target": c.target,
                 "strength": c.strength, "direction": c.direction.name}
                for c in self._connections
            ],
        }

    def __repr__(self) -> str:
        return (
            f"SubspaceField("
            f"{self.num_subspaces} subspaces, "
            f"{self.total_bits} bits, "
            f"{'isolated' if self.is_isolated() else f'{len(self._connections)} coupling links'})"
        )


# =============================================================================
# 工厂函数
# =============================================================================

def make_uniform_field(N0: int) -> SubspaceField:
    """创建一个只有单个子空间的场（等价于原始统一空间行为）。

    用于向后兼容测试和基线对比。
    """
    return SubspaceField({
        "unified": SubspaceSpec(set(range(N0)), Rules.default()),
    })


def make_static_field(
    N0: int,
    k: int,
    rules_list: Optional[List[Rules]] = None,
    name_prefix: str = "S",
    coupling_strength: float = 0.0,
) -> SubspaceField:
    """创建静态分区的子空间场。

    Args:
        N0: 总比特数
        k: 子空间数
        rules_list: 每个子空间的规则列表（长度=k，为 None 则全默认）
        name_prefix: 子空间名称前缀，如 "S" → S0, S1, S2
        coupling_strength: 全局耦合强度

    Returns:
        配置好的 SubspaceField
    """
    indices = allocate_static(N0, k)
    if rules_list is None:
        rules_list = [Rules.default() for _ in range(k)]
    assert len(rules_list) == k, f"rules_list 长度 {len(rules_list)} ≠ k={k}"

    subspaces = {}
    for i in range(k):
        name = f"{name_prefix}{i}"
        subspaces[name] = SubspaceSpec(
            bit_indices=indices[i],
            rules=rules_list[i],
            name=name,
        )

    return SubspaceField(subspaces, coupling_strength=coupling_strength)


def make_interleaved_field(
    N0: int,
    k: int,
    rules_list: Optional[List[Rules]] = None,
    name_prefix: str = "I",
    coupling_strength: float = 0.0,
) -> SubspaceField:
    """创建交错分配的子空间场。"""
    indices = allocate_interleaved(N0, k)
    if rules_list is None:
        rules_list = [Rules.default() for _ in range(k)]
    assert len(rules_list) == k

    subspaces = {}
    for i in range(k):
        name = f"{name_prefix}{i}"
        subspaces[name] = SubspaceSpec(indices[i], rules_list[i], name=name)

    return SubspaceField(subspaces, coupling_strength=coupling_strength)


def make_random_field(
    N0: int,
    k: int,
    seed: int = 42,
    rules_list: Optional[List[Rules]] = None,
    name_prefix: str = "R",
    coupling_strength: float = 0.0,
) -> SubspaceField:
    """创建随机分区的子空间场。"""
    indices = allocate_random(N0, k, seed=seed)
    if rules_list is None:
        rules_list = [Rules.default() for _ in range(k)]
    assert len(rules_list) == k

    subspaces = {}
    for i in range(k):
        name = f"{name_prefix}{i}"
        subspaces[name] = SubspaceSpec(indices[i], rules_list[i], name=name)

    return SubspaceField(subspaces, coupling_strength=coupling_strength)
