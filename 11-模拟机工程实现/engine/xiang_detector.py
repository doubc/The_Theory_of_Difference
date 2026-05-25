"""
engine/xiang_detector.py — 底象检测器 (XiàngDetector)

Phase 2 P0 组件 #1

职责：检测差异是否跨过组织门槛，从被动分布转为可追踪状态。
这是第二阶段生成链的起点——没有底象检测，后续无从谈起。

理论依据：
- 《象界》第一章：存在 → 底象
- 差异跨过组织门槛：从被动分布转为可追踪状态
- 与 M4 的区别：M4 基于引力势和汉明距离（结果导向）；
  底象检测是过程导向的，关注差异本身是否开始"留下自身"。

检测维度：
1. 组织密度 (organization_density)：局部差异梯度超过阈值的区域占比
2. 可追踪性 (traceability_score)：差异轨迹的连续性
3. 综合判定：两者同时超过阈值时，底象形成
"""

import torch
import numpy as np
from typing import Optional, List, Dict, Deque
from dataclasses import dataclass, field
from collections import deque


@dataclass
class XiangDetectionResult:
    """底象检测结果"""
    xiang_formed: bool = False          # 是否形成底象
    organization_density: float = 0.0   # 组织密度 [0, 1]
    traceability_score: float = 0.0     # 可追踪性评分 [0, 1]
    gradient_map: Optional[torch.Tensor] = None  # 差异梯度图
    n_gradient_surplus: int = 0         # 梯度超过阈值的区域数
    continuity_length: int = 0          # 最长连续轨迹长度
    timestamp: int = 0                  # 检测时间戳

    def __str__(self) -> str:
        status = "FORMED" if self.xiang_formed else "NOT_FORMED"
        return (
            f"XiàngDetector[{status}] "
            f"density={self.organization_density:.3f} "
            f"trace={self.traceability_score:.3f} "
            f"continuity={self.continuity_length}"
        )


class XiàngDetector:
    """底象检测器

    检测差异是否跨过组织门槛，从被动分布转为可追踪状态。

    核心算法：
    1. 计算局部差异梯度 ∇D
    2. 统计梯度超过阈值的区域占比 → organization_density
    3. 追踪差异轨迹的连续性 → traceability_score
    4. 当 organization_density > ρ_threshold 且 traceability_score > τ 时，判定底象形成
    """

    def __init__(self, rho_threshold: float = 0.3,
                 tau_threshold: float = 0.5,
                 continuity_window: int = 5,
                 gradient_kernel_size: int = 3):
        """
        Args:
            rho_threshold: 组织密度阈值，超过此值认为有足够组织
            tau_threshold: 可追踪性阈值，超过此值认为轨迹连续
            continuity_window: 连续性检测窗口大小（步数）
            gradient_kernel_size: 梯度计算的核大小（奇数）
        """
        self.rho_threshold = rho_threshold
        self.tau_threshold = tau_threshold
        self.continuity_window = continuity_window
        self.gradient_kernel_size = gradient_kernel_size

        # 历史记录（用于轨迹追踪）
        self._gradient_history: Deque[torch.Tensor] = deque(maxlen=continuity_window * 2)
        self._organization_history: Deque[float] = deque(maxlen=continuity_window * 2)
        self._detection_results: List[XiangDetectionResult] = []
        self._step_count: int = 0

    def detect(self, difference_matrix: torch.Tensor,
               timestamp: Optional[int] = None) -> XiangDetectionResult:
        """执行底象检测

        Args:
            difference_matrix: 差异分布矩阵 D ∈ ℝ^{n×n}
            timestamp: 当前时间戳（步数），不传则自动递增

        Returns:
            XiangDetectionResult 检测结果
        """
        if timestamp is not None:
            self._step_count = timestamp
        else:
            self._step_count += 1

        # Step 1: 计算局部差异梯度
        gradient_map = self._compute_gradient(difference_matrix)

        # Step 2: 统计组织密度
        organization_density, n_surplus = self._compute_organization_density(gradient_map)

        # Step 3: 追踪可追踪性
        traceability_score, continuity_length = self._compute_traceability(gradient_map)

        # Step 4: 综合判定
        xiang_formed = (organization_density > self.rho_threshold and
                        traceability_score > self.tau_threshold)

        result = XiangDetectionResult(
            xiang_formed=xiang_formed,
            organization_density=organization_density,
            traceability_score=traceability_score,
            gradient_map=gradient_map,
            n_gradient_surplus=n_surplus,
            continuity_length=continuity_length,
            timestamp=self._step_count,
        )

        # 记录历史
        self._gradient_history.append(gradient_map.clone())
        self._organization_history.append(organization_density)
        self._detection_results.append(result)

        return result

    def _compute_gradient(self, D: torch.Tensor) -> torch.Tensor:
        """计算局部差异梯度 ∇D

        使用中心差分近似梯度。对于边界，使用前向/后向差分。
        """
        # 确保是浮点张量
        D = D.float()
        n = D.shape[0]

        if n < 2:
            return torch.zeros_like(D)

        # 使用 Sobel-like 算子计算梯度
        gradient = torch.zeros_like(D)

        # 内部点：中心差分
        if n > 2:
            # 水平梯度
            gradient[:, 1:-1] += (D[:, 2:] - D[:, :-2]).abs() / 2.0
            # 垂直梯度
            gradient[1:-1, :] += (D[2:, :] - D[:-2, :]).abs() / 2.0

        # 边界：前向/后向差分
        gradient[:, 0] += (D[:, 1] - D[:, 0]).abs()
        gradient[:, -1] += (D[:, -1] - D[:, -2]).abs()
        gradient[0, :] += (D[1, :] - D[0, :]).abs()
        gradient[-1, :] += (D[-1, :] - D[-2, :]).abs()

        # 归一化到 [0, 1]
        max_val = gradient.max()
        if max_val > 1e-8:
            gradient = gradient / max_val

        return gradient

    def _compute_organization_density(self, gradient_map: torch.Tensor) -> tuple:
        """计算组织密度：梯度超过阈值的区域占比

        Returns:
            (density, n_surplus): 组织密度和超过阈值的区域数
        """
        # 使用 ρ_threshold 作为梯度阈值
        threshold = self.rho_threshold
        surplus_mask = gradient_map > threshold
        n_surplus = int(surplus_mask.sum().item())
        total = gradient_map.numel()
        density = n_surplus / max(1, total)
        return density, n_surplus

    def _compute_traceability(self, gradient_map: torch.Tensor) -> tuple:
        """计算可追踪性：差异轨迹的连续性

        追踪连续 N 步中梯度模式的稳定性。
        如果高梯度区域在连续多步中保持在相似位置，则认为可追踪。

        Returns:
            (traceability_score, continuity_length): 可追踪性评分和最长连续长度
        """
        history_len = len(self._gradient_history)

        if history_len < 2:
            return 0.0, 0

        # 计算当前梯度与历史梯度的相似度
        max_continuity = 0
        current_continuity = 0
        total_similarity = 0.0
        comparison_count = 0

        # 从最近的历史开始比较
        for i, hist_gradient in enumerate(reversed(self._gradient_history)):
            # 确保尺寸匹配
            if hist_gradient.shape != gradient_map.shape:
                continue

            # 计算结构相似性（余弦相似度的简化版）
            flat_current = gradient_map.flatten()
            flat_hist = hist_gradient.flatten()

            dot = (flat_current * flat_hist).sum().item()
            norm_current = (flat_current ** 2).sum().item() ** 0.5
            norm_hist = (flat_hist ** 2).sum().item() ** 0.5

            if norm_current < 1e-8 or norm_hist < 1e-8:
                similarity = 0.0
            else:
                similarity = dot / (norm_current * norm_hist)
                similarity = max(0.0, similarity)  # 只考虑正相关

            total_similarity += similarity
            comparison_count += 1

            # 连续计数：相似度 > 0.5 认为连续
            if similarity > 0.5:
                current_continuity += 1
                max_continuity = max(max_continuity, current_continuity)
            else:
                current_continuity = 0

        # 可追踪性 = 平均相似度 * 连续性因子
        avg_similarity = total_similarity / max(1, comparison_count)
        continuity_factor = min(1.0, max_continuity / self.continuity_window)
        traceability = avg_similarity * continuity_factor

        return float(traceability), max_continuity

    @property
    def is_formed(self) -> bool:
        """最近一次检测是否形成了底象"""
        if not self._detection_results:
            return False
        return self._detection_results[-1].xiang_formed

    @property
    def formation_step(self) -> Optional[int]:
        """底象首次形成的时间戳"""
        for result in self._detection_results:
            if result.xiang_formed:
                return result.timestamp
        return None

    def get_history_summary(self, last_n: int = 10) -> Dict:
        """获取最近 N 次检测的摘要"""
        recent = self._detection_results[-last_n:] if self._detection_results else []
        if not recent:
            return {'n_detections': 0}

        return {
            'n_detections': len(self._detection_results),
            'n_recent': len(recent),
            'formation_count': sum(1 for r in recent if r.xiang_formed),
            'avg_density': float(np.mean([r.organization_density for r in recent])),
            'avg_traceability': float(np.mean([r.traceability_score for r in recent])),
            'max_continuity': max(r.continuity_length for r in recent),
            'first_formation_step': self.formation_step,
        }

    def reset(self):
        """重置检测器状态"""
        self._gradient_history.clear()
        self._organization_history.clear()
        self._detection_results.clear()
        self._step_count = 0
