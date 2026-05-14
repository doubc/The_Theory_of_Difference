"""
events.py — 事件分类器：结构事件 vs 底图事件

基于差异论V1.7的区分：
- 结构事件（Structural Event）：在既有可能性空间内的路径变化
- 底图事件（Base-Map Event）：可能性空间本身的突然改写

工程映射：
- 结构事件 = reactor.step() 的正常演化
- 底图事件 = 外部注入的、大幅改变状态分布的操作
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import torch


class EventType(Enum):
    STRUCTURAL = "structural"    # 结构事件：路径变化
    BASE_MAP = "base_map"        # 底图事件：可能性空间改写


@dataclass
class StructuralEvent:
    """结构事件：在既有可能性空间内的演化步"""
    step: int
    state_before: torch.Tensor
    state_after: torch.Tensor
    loss: float
    axiom_violations: dict = field(default_factory=dict)

    @property
    def delta(self) -> torch.Tensor:
        return (self.state_after - self.state_before).abs()

    @property
    def delta_magnitude(self) -> float:
        return self.delta.mean().item()


@dataclass
class BaseMapEvent:
    """底图事件：可能性空间的突然改写"""
    step: int
    state_before: torch.Tensor
    state_after: torch.Tensor
    trigger: str                    # 触发原因描述
    intensity: float                # 改写强度 [0, 1]
    affected_region: Optional[torch.Tensor] = None  # 受影响区域掩码

    @property
    def delta(self) -> torch.Tensor:
        return (self.state_after - self.state_before).abs()

    @property
    def delta_magnitude(self) -> float:
        return self.delta.mean().item()


@dataclass
class PossibilitySpace:
    """可能性空间的显式建模

    用状态分布的统计参数来描述"当前世界允许什么"。
    这是差异论中 P_t 的工程近似。
    """
    mean: float = 0.0
    std: float = 0.0
    activity: float = 0.0          # 活动度：状态均值
    volatility: float = 0.0        # 波动度：相邻步差异
    persistence: float = 0.0       # 持续性：模式保持程度
    unique_ratio: float = 0.0      # 离散值比例（差异密度代理）
    history_length: int = 0

    @classmethod
    def from_state(cls, state: torch.Tensor,
                   history: Optional[List[torch.Tensor]] = None) -> "PossibilitySpace":
        """从当前状态和历史推断可能性空间"""
        s = state
        mean = s.mean().item()
        std = s.std().item()
        activity = mean

        # 波动度
        volatility = 0.0
        if history and len(history) >= 2:
            diffs = [
                (history[i+1] - history[i]).abs().mean().item()
                for i in range(len(history)-1)
            ]
            volatility = sum(diffs) / len(diffs)

        # 持续性
        persistence = 0.0
        if history and len(history) >= 2:
            corrs = []
            for i in range(max(0, len(history)-8), len(history)-1):
                a = history[i].flatten()
                b = history[i+1].flatten()
                if a.numel() > 0 and b.numel() > 0:
                    sim = torch.nn.functional.cosine_similarity(
                        a.unsqueeze(0), b.unsqueeze(0)
                    ).item()
                    corrs.append(sim)
            persistence = sum(corrs) / len(corrs) if corrs else 0.0

        # 差异密度（离散值比例）
        unique_vals = torch.unique(s.round())
        unique_ratio = unique_vals.numel() / max(1, s.numel())

        return cls(
            mean=mean, std=std, activity=activity,
            volatility=volatility, persistence=persistence,
            unique_ratio=unique_ratio,
            history_length=len(history) if history else 0,
        )

    def distance_to(self, other: "PossibilitySpace") -> float:
        """两个可能性空间之间的距离（归一化）"""
        attrs = ['mean', 'std', 'activity', 'volatility', 'persistence', 'unique_ratio']
        diffs = []
        for a in attrs:
            v1 = getattr(self, a)
            v2 = getattr(other, a)
            diffs.append(abs(v1 - v2))
        return sum(diffs) / len(diffs)


class EventClassifier:
    """事件分类器：判断是结构事件还是底图事件

    核心判据：
    - 结构事件：delta_magnitude < threshold，可能性空间连续变化
    - 底图事件：delta_magnitude >= threshold，可能性空间突变
    """

    def __init__(self, base_map_threshold: float = 0.3):
        self.threshold = base_map_threshold
        self.event_log: List = []
        self.possibility_spaces: List[PossibilitySpace] = []

    def classify(self, state_before: torch.Tensor,
                 state_after: torch.Tensor,
                 step: int,
                 history: Optional[List[torch.Tensor]] = None,
                 external_trigger: Optional[str] = None):
        """分类一个事件"""
        delta = (state_after - state_before).abs().mean().item()

        # 可能性空间
        ps = PossibilitySpace.from_state(state_after, history)
        self.possibility_spaces.append(ps)

        if external_trigger or delta >= self.threshold:
            event = BaseMapEvent(
                step=step,
                state_before=state_before,
                state_after=state_after,
                trigger=external_trigger or f"auto-detected (delta={delta:.3f})",
                intensity=min(1.0, delta / self.threshold),
            )
        else:
            event = StructuralEvent(
                step=step,
                state_before=state_before,
                state_after=state_after,
                loss=0.0,
            )

        self.event_log.append(event)
        return event

    @property
    def base_map_count(self) -> int:
        return sum(1 for e in self.event_log if isinstance(e, BaseMapEvent))

    @property
    def structural_count(self) -> int:
        return sum(1 for e in self.event_log if isinstance(e, StructuralEvent))

    def summary(self) -> str:
        total = len(self.event_log)
        return (
            f"Events: {total} total, "
            f"{self.structural_count} structural, "
            f"{self.base_map_count} base-map"
        )


class BaseMapOperator:
    """底图事件操作符：在模拟机中注入可能性空间改写

    对应差异论中的"底图事件"——改写世界的基本条件。
    """

    @staticmethod
    def region_reset(state: torch.Tensor, region: torch.Tensor,
                     value: float = 0.0) -> torch.Tensor:
        """区域重置：将某个区域的状态重置为特定值"""
        new_state = state.clone()
        new_state[region] = value
        return new_state

    @staticmethod
    def noise_injection(state: torch.Tensor, intensity: float = 0.5,
                        region: Optional[torch.Tensor] = None) -> torch.Tensor:
        """噪声注入：向状态中添加随机扰动"""
        new_state = state.clone()
        noise = torch.randn_like(state) * intensity
        if region is not None:
            new_state[region] = new_state[region] + noise[region]
        else:
            new_state = new_state + noise
        return new_state

    @staticmethod
    def boundary_shift(state: torch.Tensor, shift: float = 0.3) -> torch.Tensor:
        """边界条件突变：整体偏移状态值"""
        return state + shift

    @staticmethod
    def activity_compression(state: torch.Tensor,
                             factor: float = 0.5) -> torch.Tensor:
        """活动度压缩：将状态值向均值压缩（降低差异密度）"""
        mean = state.mean()
        return state * factor + mean * (1 - factor)

    @staticmethod
    def activity_expansion(state: torch.Tensor,
                           factor: float = 2.0) -> torch.Tensor:
        """活动度扩张：将状态值远离均值（增加差异密度）"""
        mean = state.mean()
        return (state - mean) * factor + mean
