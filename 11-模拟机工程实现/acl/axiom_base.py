"""
axiom_base.py — 公理基础类与数据结构

所有公理继承 AxiomBase，返回 AxiomReport。
AxiomEngine 统一调度所有公理的计算。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import torch


@dataclass
class AxiomReport:
    """单条公理的违背报告"""
    name: str
    raw_violation: float
    weight: float = 0.0
    weighted_violation: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepReport:
    """单步演化报告"""
    step: int
    layer_name: str
    total_loss: float
    axiom_reports: Dict[str, AxiomReport]
    regions: Optional[Dict[str, torch.Tensor]] = None
    ascent_triggered: bool = False
    ascent_target: Optional[str] = None


@dataclass
class StableStructure:
    """一个稳定结构的描述"""
    mask: torch.Tensor
    lifetime: int
    pattern_signature: torch.Tensor
    boundary_map: torch.Tensor
    material_turnover: float
    source_layer: str
    source_trace: List = field(default_factory=list)


@dataclass
class LayerToken:
    """封装后的高层单元"""
    token_id: int
    features: torch.Tensor
    source_structures: List[StableStructure]
    internal_state: Dict = field(default_factory=dict)


class AxiomBase(ABC):
    """所有公理必须实现的接口"""

    name: str
    category: str  # state / transition / invariant / rollout / observation / ascent_trigger

    @abstractmethod
    def violation(self, state: torch.Tensor, next_state: torch.Tensor,
                  layer: 'LayerBase', history: List[torch.Tensor]) -> AxiomReport:
        """计算当前公理的违背度"""
        ...


class AxiomEngine:
    """公理调度器：统一管理所有公理的计算和报告"""

    def __init__(self, axioms: List[AxiomBase]):
        self.axioms = {a.name: a for a in axioms}
        self.loss_axioms = [a for a in axioms if a.category in
                           ("state", "transition", "invariant", "rollout")]
        self.observation_axioms = [a for a in axioms if a.category == "observation"]
        self.ascent_axiom = next((a for a in axioms if a.category == "ascent_trigger"), None)

    def evaluate(self, state: torch.Tensor, next_state: torch.Tensor,
                 layer: 'LayerBase', history: List[torch.Tensor]) -> tuple:
        """返回总 loss 和完整报告"""
        total_loss = 0.0
        report = {}

        for axiom in self.loss_axioms:
            r = axiom.violation(state, next_state, layer, history)
            w = layer.get_axiom_weight(axiom.name)
            r.weight = w
            r.weighted_violation = r.raw_violation * w
            total_loss += r.weighted_violation
            report[axiom.name] = r

        for axiom in self.observation_axioms:
            r = axiom.violation(state, next_state, layer, history)
            report[axiom.name] = r

        return total_loss, report

    def check_ascent(self, layer: 'LayerBase', history: List[torch.Tensor],
                     structures: List[StableStructure]) -> bool:
        """检查是否触发升维"""
        if self.ascent_axiom is None:
            return False
        return self.ascent_axiom.check_ascent(layer, history, structures)
