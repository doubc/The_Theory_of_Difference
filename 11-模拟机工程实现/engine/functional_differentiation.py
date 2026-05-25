"""
engine/functional_differentiation.py — 功能分化 (FunctionalDifferentiation)

Phase 2 P2 组件 #2

职责：追踪和管理内部组件因对整体延续的不对称贡献而形成的功能分化。

理论依据：
- 《象界》第七章：耦合 → 功能
  "功能不是先验规定的任务，而是被延续过程稳定出来的作用差异。"
  "功能不是永恒固定的属性，而是在组织延续中不断被重新确认、重新强化、重新调整的作用差异。"
- 《Appearing Before Appearing》§3.6：功能分化指数
  "内部组件因对整体延续的不对称贡献而分化"

核心区分：
- 耦合（coupling）：组件之间的相互依赖
- 功能（function）：组件因对整体延续的不对称贡献而获得的差异化地位

工程指标：
- 功能分化指数 = GiniCoefficient(component_contributions)
  - 0 = 完全均匀（所有组件贡献相同）
  - 1 = 极度不均匀（一个组件贡献全部）
- 贡献不对称度 = 各组件对整体延续的贡献差异
- 功能稳定性 = 功能分化模式在扰动下的保持能力
- 功能动态调整 = 贡献度随时间的变化率

语义防火墙：
- "功能" ≠ "意义"（没有语义内容）
- "功能" ≠ "用途"（没有目的论）
- "功能" ≠ "角色"（没有社会建构）
- 功能只是"被延续过程稳定出来的作用差异"
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ComponentContribution:
    """单个组件的贡献记录"""
    component_id: str
    contributions: List[float] = field(default_factory=list)  # 每次展开的贡献值
    creation_step: int = 0
    last_active_step: int = 0

    @property
    def n_observations(self) -> int:
        return len(self.contributions)

    @property
    def mean_contribution(self) -> float:
        if not self.contributions:
            return 0.0
        return float(np.mean(self.contributions))

    @property
    def recent_contribution(self) -> float:
        """最近窗口的平均贡献"""
        if not self.contributions:
            return 0.0
        window = min(10, len(self.contributions))
        return float(np.mean(self.contributions[-window:]))

    @property
    def contribution_trend(self) -> float:
        """贡献趋势（正 = 增加，负 = 减少）"""
        if len(self.contributions) < 4:
            return 0.0
        mid = len(self.contributions) // 2
        first_half = np.mean(self.contributions[:mid])
        second_half = np.mean(self.contributions[mid:])
        return float(second_half - first_half)


@dataclass
class FunctionalState:
    """功能分化状态"""
    is_differentiated: bool = False     # 是否已功能分化
    differentiation_index: float = 0.0   # 功能分化指数（基尼系数）
    n_components: int = 0                # 组件数
    n_distinct_roles: int = 0            # 不同功能角色数
    stability: float = 0.0               # 功能稳定性
    dominant_component: str = ""         # 主导组件
    weakest_component: str = ""          # 最弱组件


class FunctionalDifferentiation:
    """功能分化

    追踪和管理内部组件因对整体延续的不对称贡献而形成的功能分化。

    核心逻辑：
    1. 记录各组件对整体延续的贡献
    2. 计算贡献的不对称度（基尼系数）→ 功能分化指数
    3. 识别功能角色（核心/辅助/边缘）
    4. 追踪功能稳定性（分化模式在扰动下的保持）
    5. 支持动态调整（贡献度随时间变化 → 功能重新分配）

    功能分化的判定：
    - 分化指数超过阈值（默认 0.3）
    - 至少存在 2 个不同的功能角色
    - 分化模式在扰动下保持稳定

    与 CumulativeSelector 的关系：
    - CumulativeSelector 追踪变体的延续概率
    - FunctionalDifferentiation 追踪组件对延续的贡献
    - 两者共同构成"筛选"的完整图景

    与 SixThresholdDetector 的关系：
    - SixThresholdDetector 使用 component_contributions 的基尼系数
    - FunctionalDifferentiation 提供这些数据的采集和管理
    """

    # 功能角色分类阈值
    ROLE_CORE_THRESHOLD = 0.7        # 贡献排名前30% → 核心
    ROLE_PERIPHERAL_THRESHOLD = 0.3  # 贡献排名后30% → 边缘

    def __init__(self,
                 differentiation_threshold: float = 0.3,
                 min_components: int = 2,
                 min_observations: int = 5,
                 stability_window: int = 10,
                 role_decay: float = 0.95):
        """
        Args:
            differentiation_threshold: 分化指数阈值（超过此值认为已分化）
            min_components: 最少组件数
            min_observations: 最少观察次数（少于此数不做分化判定）
            stability_window: 稳定性计算窗口
            role_decay: 角色衰减因子（旧贡献的影响力衰减）
        """
        self.differentiation_threshold = differentiation_threshold
        self.min_components = min_components
        self.min_observations = min_observations
        self.stability_window = stability_window
        self.role_decay = role_decay

        # 组件贡献记录 {component_id: ComponentContribution}
        self._components: Dict[str, ComponentContribution] = {}

        # 分化历史
        self._differentiation_history: List[float] = []

        # 功能角色历史 {step: {component_id: role}}
        self._role_history: List[Dict[str, str]] = []

        # 当前状态
        self._state = FunctionalState()

        # 步数
        self._step_count: int = 0

    def register_component(self, component_id: str):
        """注册一个新组件

        Args:
            component_id: 组件标识
        """
        if component_id not in self._components:
            self._components[component_id] = ComponentContribution(
                component_id=component_id,
                creation_step=self._step_count,
            )

    def record_contribution(self, component_id: str, contribution: float,
                            step: Optional[int] = None):
        """记录一个组件的贡献

        Args:
            component_id: 组件标识
            contribution: 贡献值（非负）
            step: 当前步数
        """
        if step is not None:
            self._step_count = step
        else:
            self._step_count += 1

        if component_id not in self._components:
            self.register_component(component_id)

        comp = self._components[component_id]
        comp.contributions.append(max(0.0, contribution))
        comp.last_active_step = self._step_count

        # 更新状态
        self._update_state()

    def record_contributions(self, contributions: Dict[str, float],
                             step: Optional[int] = None):
        """批量记录多个组件的贡献

        Args:
            contributions: {component_id: contribution_value}
            step: 当前步数
        """
        for cid, val in contributions.items():
            self.record_contribution(cid, val, step)

    def evaluate_differentiation(self) -> FunctionalState:
        """评估当前功能分化状态

        Returns:
            FunctionalState 功能分化状态
        """
        return self._state

    def get_component_roles(self) -> Dict[str, str]:
        """获取各组件的功能角色

        角色分类：
        - "core": 核心组件（贡献排名前30%）
        - "auxiliary": 辅助组件（贡献排名中间40%）
        - "peripheral": 边缘组件（贡献排名后30%）
        - "inactive": 不活跃组件（无贡献记录）

        Returns:
            {component_id: role}
        """
        if len(self._components) < self.min_components:
            return {cid: "inactive" for cid in self._components}

        # 按最近贡献排序
        items = [(cid, comp.recent_contribution)
                 for cid, comp in self._components.items()]
        items.sort(key=lambda x: x[1], reverse=True)

        n = len(items)
        roles = {}
        for i, (cid, _) in enumerate(items):
            if n > 0:
                rank = i / n  # 0 = 最高, 1 = 最低
                if rank < (1 - self.ROLE_CORE_THRESHOLD):
                    roles[cid] = "core"
                elif rank > self.ROLE_PERIPHERAL_THRESHOLD:
                    roles[cid] = "peripheral"
                else:
                    roles[cid] = "auxiliary"
            else:
                roles[cid] = "inactive"

        return roles

    def get_contribution_distribution(self) -> Dict[str, float]:
        """获取当前贡献分布

        Returns:
            {component_id: mean_contribution}
        """
        return {cid: comp.mean_contribution
                for cid, comp in self._components.items()}

    def get_differentiation_index(self) -> float:
        """计算功能分化指数（基尼系数）

        Returns:
            gini: 基尼系数 [0, 1]
        """
        contributions = [comp.recent_contribution for comp in self._components.values()]
        if len(contributions) < 2:
            return 0.0

        contributions = sorted(contributions)
        n = len(contributions)
        total = sum(contributions)

        if total < 1e-10:
            return 0.0

        numerator = sum((2 * i - n - 1) * v for i, v in enumerate(contributions, 1))
        gini = numerator / (n * total)
        return max(0.0, min(1.0, gini))

    def get_component_contributions_for_detector(self) -> Dict[str, float]:
        """获取 SixThresholdDetector 所需的 component_contributions 格式

        Returns:
            {component_id: contribution_value}
        """
        return {cid: comp.recent_contribution
                for cid, comp in self._components.items()}

    @property
    def state(self) -> FunctionalState:
        """当前功能分化状态"""
        return self._state

    @property
    def is_differentiated(self) -> bool:
        """是否已功能分化"""
        return self._state.is_differentiated

    @property
    def differentiation_index_value(self) -> float:
        """当前分化指数"""
        return self._state.differentiation_index

    def get_summary(self) -> Dict:
        """获取摘要"""
        roles = self.get_component_roles()
        distribution = self.get_contribution_distribution()
        return {
            'is_differentiated': self._state.is_differentiated,
            'differentiation_index': self._state.differentiation_index,
            'n_components': self._state.n_components,
            'n_distinct_roles': self._state.n_distinct_roles,
            'stability': self._state.stability,
            'dominant_component': self._state.dominant_component,
            'weakest_component': self._state.weakest_component,
            'roles': roles,
            'distribution': distribution,
            'n_history': len(self._differentiation_history),
        }

    def _update_state(self):
        """更新功能分化状态"""
        n_components = len(self._components)
        if n_components < self.min_components:
            self._state = FunctionalState(n_components=n_components)
            return

        # 检查最少观察次数
        min_obs = min(comp.n_observations for comp in self._components.values())
        if min_obs < self.min_observations:
            gini = self.get_differentiation_index()
            self._state = FunctionalState(
                n_components=n_components,
                differentiation_index=gini,
            )
            return

        # 计算分化指数
        gini = self.get_differentiation_index()
        self._differentiation_history.append(gini)

        # 功能角色
        roles = self.get_component_roles()
        distinct_roles = len(set(roles.values()))

        # 主导/最弱组件
        distribution = self.get_contribution_distribution()
        if distribution:
            dominant = max(distribution, key=distribution.get)
            weakest = min(distribution, key=distribution.get)
        else:
            dominant = ""
            weakest = ""

        # 稳定性（最近窗口内分化指数的方差）
        recent = self._differentiation_history[-self.stability_window:]
        if len(recent) >= 3:
            stability = 1.0 - min(1.0, float(np.std(recent)))
        else:
            stability = 0.0

        self._state = FunctionalState(
            is_differentiated=(gini > self.differentiation_threshold and
                               distinct_roles >= 2),
            differentiation_index=gini,
            n_components=n_components,
            n_distinct_roles=distinct_roles,
            stability=stability,
            dominant_component=dominant,
            weakest_component=weakest,
        )

        self._role_history.append(roles)

    def reset(self):
        """重置所有状态"""
        self._components.clear()
        self._differentiation_history.clear()
        self._role_history.clear()
        self._state = FunctionalState()
        self._step_count = 0
