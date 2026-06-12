"""entropy.py -- 熵与自由能计算模块。

Phase 21: 为差异论模拟机添加热力学/信息论基础。

核心概念:
- Shannon 熵: 比特状态的均匀度度量
- 组织熵: 各组织内部的差异多样性
- 自由能: F = E - T * S (能量 - 温度 * 熵)
- 熵产生: 每步熵的变化量 (不可逆性指标)
"""

from __future__ import annotations
from dataclasses import dataclass, field as dfield
from typing import List, Dict, Optional
import numpy as np


@dataclass
class EntropyConfig:
    """熵计算配置。"""
    temperature: float = 1.0          # 温度参数 (用于自由能计算)
    use_log2: bool = True              # True=bits, False=nats
    track_production: bool = True      # 是否追踪熵产生
    irreversibility_window: int = 10  # 不可逆性检测窗口


@dataclass
class EntropyHistory:
    """熵历史记录。"""
    steps: List[int] = dfield(default_factory=list)
    shannon_entropy: List[float] = dfield(default_factory=list)
    organization_entropy: List[float] = dfield(default_factory=list)
    free_energy: List[float] = dfield(default_factory=list)
    entropy_production: List[float] = dfield(default_factory=list)
    negentropy: List[float] = dfield(default_factory=list)

    def record(self, step: int, shannon: float, org_entropy: float,
               free_energy: float, production: float, neg: float):
        self.steps.append(step)
        self.shannon_entropy.append(shannon)
        self.organization_entropy.append(org_entropy)
        self.free_energy.append(free_energy)
        self.entropy_production.append(production)
        self.negentropy.append(neg)

    def mean_production(self, window: int = 10) -> float:
        if len(self.entropy_production) < window:
            return 0.0
        return float(np.mean(self.entropy_production[-window:]))

    def is_irreversible(self, window: int = 10) -> bool:
        """检测是否不可逆 (熵产生持续 > 0)。"""
        if len(self.entropy_production) < window:
            return False
        recent = self.entropy_production[-window:]
        return any(abs(p) > 1e-10 for p in recent)


def shannon_entropy(bits: np.ndarray, log2: bool = True) -> float:
    """计算比特数组的 Shannon 熵。

    Args:
        bits: shape (N,) 的 0/1 数组
        log2: True 用 log2 (bits), False 用 ln (nats)
    Returns:
        熵值 (0 表示全0或全1, 1.0 表示完全均匀)
    """
    if len(bits) == 0:
        return 0.0
    p = np.mean(bits)
    if p == 0.0 or p == 1.0:
        return 0.0
    if log2:
        from math import log2
        return - (p * log2(p) + (1 - p) * log2(1 - p))
    else:
        from math import log
        return - (p * log(p) + (1 - p) * log(1 - p))


def organization_entropy(assignments: Dict[int, List[int]],
                        bits: np.ndarray) -> float:
    """计算组织内部的熵（组织间的差异多样性）。

    Args:
        assignments: {org_id: [bit_indices]}
        bits: 完整比特数组
    Returns:
        平均组织熵 (越高表示组织内差异越丰富)
    """
    if not assignments:
        return 0.0
    entropies = []
    for org_id, indices in assignments.items():
        if len(indices) <= 1:
            continue
        org_bits = bits[indices]
        ent = shannon_entropy(org_bits)
        entropies.append(ent)
    return float(np.mean(entropies)) if entropies else 0.0


class EntropyTracker:
    """熵追踪器，集成到 World 中每步更新。"""

    def __init__(self, config: Optional[EntropyConfig] = None):
        self.config = config or EntropyConfig()
        self.history = EntropyHistory()
        self._prev_shannon: Optional[float] = None

    def step(self, bits: np.ndarray,
             organizations: Dict[int, List[int]],
             energy_budget: float) -> Dict[str, float]:
        """执行一步熵计算。

        Returns:
            包含各项熵度量的字典
        """
        cfg = self.config

        # 1. Shannon 熵
        h = shannon_entropy(bits, log2=cfg.use_log2)

        # 2. 组织熵
        h_org = organization_entropy(organizations, bits)

        # 3. 负熵 (Negentropy = 最大熵 - 实际熵, 表示"有序度")
        max_entropy = 1.0 if cfg.use_log2 else float(np.log(2))
        neg = max_entropy - h

        # 4. 自由能 (F = E - T*S)
        # 这里用负熵代替 S (因为 S 越大越无序, 负熵越大越有序)
        # F = energy_budget - T * (-neg) = energy_budget + T * neg
        free_energy = energy_budget + cfg.temperature * neg

        # 5. 熵产生 (当前 Shannon 熵 - 上一步 Shannon 熵)
        if self._prev_shannon is None:
            production = 0.0
        else:
            production = h - self._prev_shannon
        self._prev_shannon = h

        # 6. 记录
        self.history.record(
            step=len(self.history.steps),
            shannon=h,
            org_entropy=h_org,
            free_energy=free_energy,
            production=production,
            neg=neg
        )

        return {
            'shannon_entropy': h,
            'organization_entropy': h_org,
            'negentropy': neg,
            'free_energy': free_energy,
            'entropy_production': production,
        }

    def summary(self) -> Dict:
        if not self.history.steps:
            return {}
        return {
            'mean_shannon': float(np.mean(self.history.shannon_entropy)),
            'mean_org_entropy': float(np.mean(self.history.organization_entropy)),
            'mean_free_energy': float(np.mean(self.history.free_energy)),
            'final_negentropy': self.history.negentropy[-1],
            'cumulative_production': sum(self.history.entropy_production),
            'is_irreversible': self.history.is_irreversible(),
            'n_steps': len(self.history.steps),
        }
