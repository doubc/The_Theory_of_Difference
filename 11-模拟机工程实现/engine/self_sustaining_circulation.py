"""
engine/self_sustaining_circulation.py — 自维持循环 (SelfSustainingCirculation)

Phase 2 P2 组件 #1

职责：实现并检测"自维持"能力——循环在开放环境中通过扰动重建自身。

理论依据：
- 《象界》第三章：闭合 → 自维持
  "自维持不是意图，而是结果；不是追求，而是结构上能够不断重建自身条件的一种能力。"
- 《Appearing Before Appearing》§3.2：自维持稳健性
  "循环从封闭回返转为在开放中重建自身的持续能力"

核心区分：
- 闭合（closed loop）：系统内循环，与环境无交换
- 自维持（self-sustaining）：开放环境中，系统通过扰动后重建来维持自身组织

工程指标：
- 重建成功率 = rebuild_success_count / perturbation_count
- 重建速度 = 恢复到原始状态所需的步数
- 重建完整性 = 重建后状态与原始状态的相似度
- 稳健性曲线 = 不同扰动强度下的重建成功率

语义防火墙：
- "自维持" ≠ "意志"（没有意图驱动）
- "自维持" ≠ "目的"（没有目标导向）
- 自维持是结构属性：系统组织使得扰动后自然回归
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field


@dataclass
class RebuildAttempt:
    """单次重建尝试记录"""
    perturbation_step: int          # 施加扰动的步数
    success: bool                   # 是否成功重建
    rebuild_steps: int = 0          # 重建所需步数
    similarity: float = 0.0         # 重建后与原始状态的相似度
    perturbation_magnitude: float = 0.0  # 扰动强度


@dataclass
class CirculationState:
    """自维持循环的状态"""
    is_self_sustaining: bool = False    # 当前是否处于自维持状态
    robustness: float = 0.0             # 自维持稳健性 [0, 1]
    n_perturbations: int = 0            # 总扰动次数
    n_successful_rebuilds: int = 0      # 成功重建次数
    avg_rebuild_steps: float = 0.0      # 平均重建步数
    avg_similarity: float = 0.0         # 平均重建相似度
    recent_robustness: float = 0.0      # 最近窗口的稳健性
    trend: str = "stable"               # 趋势: improving / stable / degrading


class SelfSustainingCirculation:
    """自维持循环

    检测和管理系统在扰动后重建自身结构的能力。

    核心逻辑：
    1. 保存参考状态（系统的"自身"模式）
    2. 施加扰动（随机噪声、比特翻转等）
    3. 运行重建过程（不施加外部干预）
    4. 评估重建结果（是否回到参考状态附近）
    5. 统计稳健性（多次扰动-重建的成功率）

    自维持的判定：
    - 稳健性超过阈值（默认 0.5）
    - 最近 N 次扰动中至少 M 次成功重建
    - 重建相似度超过阈值（默认 0.7）

    与 SixThresholdDetector 的关系：
    - SixThresholdDetector 使用 rebuild_success_count / perturbation_count
    - SelfSustainingCirculation 提供这些数据的采集和管理
    """

    def __init__(self,
                 robustness_threshold: float = 0.5,
                 similarity_threshold: float = 0.7,
                 window_size: int = 20,
                 max_rebuild_steps: int = 100,
                 reference_update_interval: int = 50):
        """
        Args:
            robustness_threshold: 稳健性阈值（超过此值认为自维持）
            similarity_threshold: 重建相似度阈值
            window_size: 稳健性计算窗口
            max_rebuild_steps: 最大重建步数（超过则判定为重建失败）
            reference_update_interval: 参考状态更新间隔
        """
        self.robustness_threshold = robustness_threshold
        self.similarity_threshold = similarity_threshold
        self.window_size = window_size
        self.max_rebuild_steps = max_rebuild_steps
        self.reference_update_interval = reference_update_interval

        # 参考状态（系统的"自身"模式）
        self._reference_state: Optional[torch.Tensor] = None
        self._reference_step: int = 0

        # 重建历史
        self._rebuild_history: List[RebuildAttempt] = []

        # 当前状态
        self._state = CirculationState()

        # 步数
        self._step_count: int = 0

    def set_reference(self, state: torch.Tensor):
        """设置参考状态（系统的"自身"模式）

        Args:
            state: 参考状态
        """
        self._reference_state = state.clone()
        self._reference_step = self._step_count

    def apply_perturbation(self, state: torch.Tensor,
                           magnitude: float = 0.1,
                           mode: str = "noise") -> torch.Tensor:
        """施加扰动

        Args:
            state: 当前状态
            magnitude: 扰动强度
            mode: 扰动模式
            - "noise": 加性高斯噪声
            - "flip": 随机比特翻转
            - "dropout": 随机置零

        Returns:
            perturbed_state: 扰动后的状态
        """
        if mode == "noise":
            noise = torch.randn_like(state) * magnitude
            perturbed = state + noise
        elif mode == "flip":
            mask = torch.rand_like(state) < magnitude
            perturbed = state.clone()
            perturbed[mask] = 1.0 - perturbed[mask]
        elif mode == "dropout":
            mask = torch.rand_like(state) < magnitude
            perturbed = state.clone()
            perturbed[mask] = 0.0
        else:
            raise ValueError(f"Unknown perturbation mode: {mode}")

        return perturbed

    def evaluate_rebuild(self,
                         current_state: torch.Tensor,
                         evolution_fn: Callable[[torch.Tensor], torch.Tensor],
                         perturbation_magnitude: float = 0.1,
                         perturbation_mode: str = "noise") -> RebuildAttempt:
        """评估一次扰动-重建循环

        流程：
        1. 施加扰动
        2. 运行重建（反复调用 evolution_fn）
        3. 检查是否回到参考状态附近

        Args:
            current_state: 当前状态
            evolution_fn: 演化函数 state → new_state
            perturbation_magnitude: 扰动强度
            perturbation_mode: 扰动模式

        Returns:
            RebuildAttempt 重建尝试结果
        """
        if self._reference_state is None:
            # 首次调用，设置参考状态
            self.set_reference(current_state)
            return RebuildAttempt(
                perturbation_step=self._step_count,
                success=True,
                rebuild_steps=0,
                similarity=1.0,
                perturbation_magnitude=0.0,
            )

        self._step_count += 1

        # 施加扰动
        perturbed = self.apply_perturbation(
            current_state, perturbation_magnitude, perturbation_mode)

        # 重建循环
        state = perturbed.clone()
        success = False
        rebuild_steps = self.max_rebuild_steps

        for step in range(self.max_rebuild_steps):
            state = evolution_fn(state)
            similarity = self._compute_similarity(state, self._reference_state)

            if similarity > self.similarity_threshold:
                success = True
                rebuild_steps = step + 1
                break

        # 最终相似度
        final_similarity = self._compute_similarity(state, self._reference_state)

        attempt = RebuildAttempt(
            perturbation_step=self._step_count,
            success=success,
            rebuild_steps=rebuild_steps if success else self.max_rebuild_steps,
            similarity=final_similarity,
            perturbation_magnitude=perturbation_magnitude,
        )

        self._rebuild_history.append(attempt)
        self._update_state()

        # 定期更新参考状态（适应漂移）
        if (self._step_count - self._reference_step) >= self.reference_update_interval:
            if self._state.is_self_sustaining:
                self.set_reference(current_state)

        return attempt

    def evaluate_batch(self,
                       state: torch.Tensor,
                       evolution_fn: Callable[[torch.Tensor], torch.Tensor],
                       n_perturbations: int = 10,
                       magnitude: float = 0.1,
                       mode: str = "noise") -> Dict:
        """批量评估扰动-重建

        Args:
            state: 当前状态
            evolution_fn: 演化函数
            n_perturbations: 扰动次数
            magnitude: 扰动强度
            mode: 扰动模式

        Returns:
            批量评估结果摘要
        """
        results = []
        for _ in range(n_perturbations):
            attempt = self.evaluate_rebuild(
                state, evolution_fn, magnitude, mode)
            results.append(attempt)

        n_success = sum(1 for r in results if r.success)
        success_rate = n_success / max(1, len(results))

        return {
            'n_perturbations': n_perturbations,
            'n_success': n_success,
            'success_rate': success_rate,
            'avg_rebuild_steps': float(np.mean([
                r.rebuild_steps for r in results if r.success])) if n_success > 0 else 0.0,
            'avg_similarity': float(np.mean([r.similarity for r in results])),
            'is_self_sustaining': success_rate > self.robustness_threshold,
        }

    def check_robustness_curve(self,
                               state: torch.Tensor,
                               evolution_fn: Callable[[torch.Tensor], torch.Tensor],
                               magnitudes: Optional[List[float]] = None,
                               n_trials: int = 5) -> Dict[float, float]:
        """检查稳健性曲线（不同扰动强度下的成功率）

        Args:
            state: 当前状态
            evolution_fn: 演化函数
            magnitudes: 扰动强度列表
            n_trials: 每个强度的试验次数

        Returns:
            robustness_curve: {magnitude: success_rate}
        """
        if magnitudes is None:
            magnitudes = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]

        curve = {}
        for mag in magnitudes:
            batch_result = self.evaluate_batch(
                state, evolution_fn, n_trials, mag)
            curve[mag] = batch_result['success_rate']

        return curve

    @property
    def state(self) -> CirculationState:
        """当前自维持状态"""
        return self._state

    @property
    def is_self_sustaining(self) -> bool:
        """是否处于自维持状态"""
        return self._state.is_self_sustaining

    @property
    def robustness(self) -> float:
        """当前稳健性"""
        return self._state.robustness

    def get_summary(self) -> Dict:
        """获取摘要"""
        recent = self._rebuild_history[-self.window_size:] if self._rebuild_history else []
        return {
            'is_self_sustaining': self._state.is_self_sustaining,
            'robustness': self._state.robustness,
            'recent_robustness': self._state.recent_robustness,
            'n_perturbations': self._state.n_perturbations,
            'n_successful_rebuilds': self._state.n_successful_rebuilds,
            'avg_rebuild_steps': self._state.avg_rebuild_steps,
            'avg_similarity': self._state.avg_similarity,
            'trend': self._state.trend,
            'n_history': len(self._rebuild_history),
            'recent_success_rate': (
                sum(1 for r in recent if r.success) / max(1, len(recent))
            ) if recent else 0.0,
        }

    def _compute_similarity(self, state: torch.Tensor,
                            reference: torch.Tensor) -> float:
        """计算状态与参考状态的相似度（余弦相似度）"""
        min_len = min(len(state), len(reference))
        s = state[:min_len].float()
        r = reference[:min_len].float()

        dot = (s * r).sum().item()
        norm_s = (s ** 2).sum().item() ** 0.5
        norm_r = (r ** 2).sum().item() ** 0.5

        if norm_s < 1e-8 or norm_r < 1e-8:
            return 0.0

        return max(0.0, min(1.0, dot / (norm_s * norm_r)))

    def _update_state(self):
        """更新自维持状态"""
        history = self._rebuild_history
        if not history:
            return

        n_total = len(history)
        n_success = sum(1 for h in history if h.success)
        robustness = n_success / max(1, n_total)

        # 最近窗口的稳健性
        recent = history[-self.window_size:] if len(history) >= self.window_size else history
        recent_success = sum(1 for h in recent if h.success)
        recent_robustness = recent_success / max(1, len(recent))

        # 平均重建指标
        successful = [h for h in history if h.success]
        avg_steps = float(np.mean([h.rebuild_steps for h in successful])) if successful else 0.0
        avg_sim = float(np.mean([h.similarity for h in history]))

        # 趋势判断（比较前半和后半的稳健性）
        mid = len(recent) // 2
        if mid > 0:
            first_half = sum(1 for h in recent[:mid] if h.success) / mid
            second_half = sum(1 for h in recent[mid:] if h.success) / (len(recent) - mid)
            if second_half > first_half + 0.1:
                trend = "improving"
            elif second_half < first_half - 0.1:
                trend = "degrading"
            else:
                trend = "stable"
        else:
            trend = "stable"

        self._state = CirculationState(
            is_self_sustaining=recent_robustness > self.robustness_threshold,
            robustness=robustness,
            n_perturbations=n_total,
            n_successful_rebuilds=n_success,
            avg_rebuild_steps=avg_steps,
            avg_similarity=avg_sim,
            recent_robustness=recent_robustness,
            trend=trend,
        )

    def reset(self):
        """重置所有状态"""
        self._reference_state = None
        self._reference_step = 0
        self._rebuild_history.clear()
        self._state = CirculationState()
        self._step_count = 0
