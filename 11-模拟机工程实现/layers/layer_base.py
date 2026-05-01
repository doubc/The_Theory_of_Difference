"""
layer_base.py — 层级统一接口

所有层级必须实现此接口。
五元组：(S, N, T, Q, C) = (状态空间, 邻域, 演化, 守恒量, 粗粒化)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import torch


class LayerBase(ABC):
    """所有层级必须实现的统一接口"""

    name: str
    stability_window: int = 16

    # --- 状态空间 ---

    @abstractmethod
    def initial_state(self, batch_size: int = 1) -> torch.Tensor:
        """生成初始状态"""
        ...

    @abstractmethod
    def project_state(self, raw_state: torch.Tensor,
                      mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """将模型输出投影回合法状态空间"""
        ...

    @abstractmethod
    def valid_state(self, state: torch.Tensor) -> bool:
        """检查状态是否合法"""
        ...

    # --- 差异度量 ---

    @abstractmethod
    def measure_difference(self, state: torch.Tensor) -> torch.Tensor:
        """度量当前层的差异分布"""
        ...

    @abstractmethod
    def measure_invariant(self, state: torch.Tensor) -> torch.Tensor:
        """度量当前层的守恒量"""
        ...

    @abstractmethod
    def transition_cost(self, state: torch.Tensor,
                        next_state: torch.Tensor) -> torch.Tensor:
        """计算状态转换成本（A4）"""
        ...

    @abstractmethod
    def discreteness_violation(self, state: torch.Tensor) -> torch.Tensor:
        """检查离散性违背（A2）"""
        ...

    @abstractmethod
    def locality_violation(self, state: torch.Tensor,
                           next_state: torch.Tensor) -> torch.Tensor:
        """检查局域性违背（A3）"""
        ...

    # --- 差异源与汇 ---

    @abstractmethod
    def inject_difference(self, state: torch.Tensor,
                          source_strength: float = 1.0) -> torch.Tensor:
        """A1：在源端注入差异"""
        ...

    @abstractmethod
    def absorb_difference(self, state: torch.Tensor,
                          sink_strength: float = 1.0) -> torch.Tensor:
        """A8：在汇端吸收差异"""
        ...

    # --- 稳定性 ---

    @abstractmethod
    def stability_violation(self, window: List[torch.Tensor]) -> torch.Tensor:
        """A7：计算稳定性违背度"""
        ...

    @abstractmethod
    def detect_stable_structures(self,
                                 history: List[torch.Tensor]) -> List:
        """A7：从演化历史中检测稳定结构"""
        ...

    # --- 粗粒化与升维 ---

    @abstractmethod
    def coarse_grain(self, structures: List) -> Optional['LayerBase']:
        """将稳定结构封装为下一层"""
        ...

    @abstractmethod
    def measure_ascent_pressure(self, history: List[torch.Tensor],
                                 structures: List) -> float:
        """A5+A9：度量升维压力"""
        ...

    # --- 配置 ---

    @abstractmethod
    def get_axiom_weight(self, axiom_name: str) -> float:
        """获取当前层各公理的权重"""
        ...
