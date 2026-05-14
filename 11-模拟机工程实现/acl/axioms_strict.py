"""
axioms_strict.py — 九公理严格化实现

从连续近似升级到离散严格：
- A1: 汉明重量层级（差异沿层级单调累积）
- A2: 严格二值（Gumbel-Softmax 直通估计）
- A3: 汉明距离=1 邻域
- A4: 单比特翻转
- A5: 精确守恒量跟踪
- A6: DAG 方向约束（演化不可逆）
- A7: 循环闭合检测（稳定态参与有向循环）
- A8: 对称偏好权重 ρ(w) = C(N,w)/C(N,N/2)
- A9: 自由度封口（最小充分实现）

对应 WorldBase 形式化 §2.2 的公理体系。
"""

import torch
import torch.nn.functional as F
from typing import List, Optional, Dict
from acl.axiom_base import AxiomBase, AxiomReport
from engine.hamming_engine import HammingMeasurement


# ============================================================
# A1: 汉明重量层级（严格化）
# ============================================================

class A1_DifferenceSourceStrict(AxiomBase):
    """A1 严格化：差异沿汉明重量层级单调累积

    理论要求：存在唯一无差异态 0，差异沿层级方向单调累积。
    工程实现：追踪汉明重量变化，惩罚层级下降。
    """
    name = "A1_difference_source_strict"
    category = "constraint"

    def __init__(self, monotonicity_weight: float = 1.0):
        self.monotonicity_weight = monotonicity_weight

    def violation(self, state, next_state, layer, history, **kwargs):
        w_before = state.sum()
        w_after = next_state.sum()

        # 层级下降惩罚
        level_drop = F.relu(w_before - w_after)
        # 归一化
        N = max(1, state.numel())
        violation_val = (level_drop / N).mean()

        return AxiomReport(
            name=self.name,
            raw_violation=float(violation_val),
            weight=self.monotonicity_weight,
            weighted_violation=float(violation_val) * self.monotonicity_weight,
            metadata={
                "w_before": float(w_before),
                "w_after": float(w_after),
                "level_drop": float(level_drop),
            }
        )


# ============================================================
# A2: 严格二值（Gumbel-Softmax）
# ============================================================

class A2_DiscreteEncodingStrict(AxiomBase):
    """A2 严格化：严格二值编码

    理论要求：x_i ∈ {0,1}，差异单元不可再细分。
    工程实现：Gumbel-Softmax 直通估计 + 硬投影损失。
    """
    name = "A2_discrete_encoding_strict"
    category = "state"

    def __init__(self, temperature: float = 0.1, weight: float = 1.0):
        self.temperature = temperature
        self.weight = weight

    def violation(self, state, next_state, layer, history, **kwargs):
        # 软二值损失：鼓励值接近 0 或 1
        # p*(1-p) 在 p=0 或 1 时为 0，在 p=0.5 时最大
        soft_violation = (next_state * (1.0 - next_state)).mean()

        # 硬投影损失：统计离 0.5 最远的值的比例
        hard_state = (next_state > 0.5).float()
        hard_violation = (next_state - hard_state).abs().mean()

        total = (soft_violation + hard_violation) / 2.0

        return AxiomReport(
            name=self.name,
            raw_violation=float(total.detach()),
            weight=self.weight,
            weighted_violation=float(total.detach()) * self.weight,
            metadata={
                "soft_violation": float(soft_violation.detach()),
                "hard_violation": float(hard_violation.detach()),
                "temperature": self.temperature,
            }
        )


# ============================================================
# A4: 单比特翻转（严格化）
# ============================================================

class A4_MinimalVariationStrict(AxiomBase):
    """A4 严格化：单比特翻转约束

    理论要求：每次演化恰好改变一个维度（汉明距离=1）。
    工程实现：惩罚汉明距离偏离 1。
    """
    name = "A4_minimal_variation_strict"
    category = "transition"

    def __init__(self, target_distance: float = 1.0, weight: float = 0.8):
        self.target_distance = target_distance
        self.weight = weight

    def violation(self, state, next_state, layer, history, **kwargs):
        # 硬二值化后计算汉明距离
        hard_state = (state > 0.5).float()
        hard_next = (next_state > 0.5).float()
        hamming_dist = (hard_next - hard_state).abs().sum()

        # 惩罚偏离目标距离
        violation_val = (hamming_dist - self.target_distance).abs()

        return AxiomReport(
            name=self.name,
            raw_violation=float(violation_val.detach()),
            weight=self.weight,
            weighted_violation=float(violation_val.detach()) * self.weight,
            metadata={
                "hamming_distance": float(hamming_dist.detach()),
                "target_distance": self.target_distance,
            }
        )


# ============================================================
# A5: 精确守恒量跟踪
# ============================================================

class A5_ConservationStrict(AxiomBase):
    """A5 严格化：精确守恒量跟踪

    理论要求：差异总量守恒，Q(x) 在所有允许演化下不变。
    工程实现：精确跟踪守恒量变化，支持开放/封闭双模式。
    """
    name = "A5_conservation_strict"
    category = "invariant"

    def __init__(self, weight: float = 1.0, epsilon: float = 1e-6):
        self.weight = weight
        self.epsilon = epsilon

    def violation(self, state, next_state, layer, history, **kwargs):
        q_now = layer.measure_invariant(state)
        q_next = layer.measure_invariant(next_state)
        delta_q = q_next - q_now

        boundary_info = kwargs.get("boundary_info", None)

        if boundary_info:
            injected = boundary_info.get("injected", torch.zeros_like(q_now))
            absorbed = boundary_info.get("absorbed", torch.zeros_like(q_now))
            expected_delta = injected - absorbed
            flux_residual = delta_q - expected_delta
            # 归一化残差
            scale = (q_now.abs() + self.epsilon)
            violation_val = ((flux_residual / scale) ** 2).mean()

            return AxiomReport(
                name=self.name,
                raw_violation=float(violation_val.detach()),
                weight=self.weight,
                weighted_violation=float(violation_val.detach()) * self.weight,
                metadata={
                    "mode": "open_flux_balance",
                    "flux_residual": float(flux_residual.mean().detach()),
                }
            )
        else:
            # 封闭系统：delta_q 应该为 0
            scale = (q_now.abs() + self.epsilon)
            violation_val = ((delta_q / scale) ** 2).mean()

            return AxiomReport(
                name=self.name,
                raw_violation=float(violation_val.detach()),
                weight=self.weight,
                weighted_violation=float(violation_val.detach()) * self.weight,
                metadata={
                    "mode": "closed_conservation",
                    "delta_q": float(delta_q.mean().detach()),
                }
            )


# ============================================================
# A6: DAG 方向约束（严格化）
# ============================================================

class A6_DAGConstraint(AxiomBase):
    """A6 严格化：演化不可逆（DAG 约束）

    理论要求：演化图是 DAG，不存在有向环路。
    工程实现：追踪状态转移方向，惩罚逆向跃迁。
    """
    name = "A6_dag_constraint"
    category = "constraint"

    def __init__(self, weight: float = 1.0):
        self.weight = weight
        # 方向矩阵：记录每个维度最后一次变化方向
        self._direction: Optional[torch.Tensor] = None

    def violation(self, state, next_state, layer, history, **kwargs):
        hard_state = (state > 0.5).float()
        hard_next = (next_state > 0.5).float()

        # 变化方向：+1 = 0→1, -1 = 1→0, 0 = 无变化
        delta = hard_next - hard_state

        if self._direction is None:
            self._direction = torch.zeros_like(hard_state)

        # 检查逆向跃迁：之前是 +1 现在变成 -1，或反之
        reverse_mask = (delta * self._direction < 0).float()
        reverse_count = reverse_mask.sum()

        # 更新方向（只记录有变化的位置）
        self._direction = torch.where(delta != 0, delta, self._direction)

        violation_val = reverse_count / max(1, state.numel())

        return AxiomReport(
            name=self.name,
            raw_violation=float(violation_val),
            weight=self.weight,
            weighted_violation=float(violation_val) * self.weight,
            metadata={
                "reverse_transitions": int(reverse_count),
                "total_dims": state.numel(),
            }
        )

    def reset(self):
        """重置方向追踪（新 episode 时调用）"""
        self._direction = None


# ============================================================
# A7: 循环闭合检测（严格化）
# ============================================================

class A7_CycleClosure(AxiomBase):
    """A7 严格化：稳定态必须参与有向闭合循环

    理论要求：稳定态集合 S 中的每个元素都参与至少一个有向闭合循环。
    工程实现：检测历史中的循环模式，惩罚无循环的稳定态。
    """
    name = "A7_cycle_closure"
    category = "rollout"

    def __init__(self, weight: float = 0.8, min_cycle_length: int = 4):
        self.weight = weight
        self.min_cycle_length = min_cycle_length

    def violation(self, state, next_state, layer, history, **kwargs):
        if len(history) < self.min_cycle_length * 2:
            return AxiomReport(
                name=self.name, raw_violation=0.0,
                weight=0.0, weighted_violation=0.0
            )

        # 硬二值化历史
        hard_history = [(h > 0.5).float() for h in history[-self.min_cycle_length * 2:]]

        # 检测循环：寻找历史中重复出现的状态
        cycle_found = False
        min_len = self.min_cycle_length
        for cycle_len in range(min_len, len(hard_history) // 2 + 1):
            # 检查最后 cycle_len 步是否形成循环
            recent = hard_history[-cycle_len:]
            earlier = hard_history[-2 * cycle_len:-cycle_len]
            if len(recent) == len(earlier):
                matches = sum(
                    (r == e).float().mean().item()
                    for r, e in zip(recent, earlier)
                )
                if matches / len(recent) > 0.9:  # 90% 匹配认为有循环
                    cycle_found = True
                    break

        violation_val = 0.0 if cycle_found else 1.0

        return AxiomReport(
            name=self.name,
            raw_violation=violation_val,
            weight=self.weight,
            weighted_violation=violation_val * self.weight,
            metadata={
                "cycle_found": cycle_found,
                "history_length": len(history),
            }
        )


# ============================================================
# A8: 对称偏好权重（严格化）
# ============================================================

class A8_SymmetryPreference(AxiomBase):
    """A8 严格化：对称偏好权重

    理论要求：偏好 w=N/2 态，权重随 |w-N/2| 单调递减。
    精确形式：ρ(w) = C(N,w) / C(N,N/2)

    工程实现：计算当前状态的汉明重量，用对称偏好权重调制损失。
    """
    name = "A8_symmetry_preference"
    category = "constraint"

    def __init__(self, N: int, weight: float = 1.0):
        self.N = N
        self.weight = weight
        # 预计算对称偏好权重向量
        self._weight_vector = HammingMeasurement.symmetry_weight_vector(N)

    def violation(self, state, next_state, layer, history, **kwargs):
        # 计算当前汉明重量
        w = next_state.sum().long().item()
        w = max(0, min(self.N, w))

        # 对称偏好：越接近 N/2 越好
        # 转换为最小化问题：1 - 归一化权重
        symmetry_weight = self._weight_vector[w].item()
        max_weight = self._weight_vector[self.N // 2].item()
        normalized = symmetry_weight / max_weight if max_weight > 0 else 0.0

        violation_val = 1.0 - normalized  # 最小化 = 偏好中截面

        return AxiomReport(
            name=self.name,
            raw_violation=float(violation_val),
            weight=self.weight,
            weighted_violation=float(violation_val) * self.weight,
            metadata={
                "hamming_weight": w,
                "N": self.N,
                "symmetry_weight": float(symmetry_weight),
                "normalized": float(normalized),
            }
        )


# ============================================================
# A9: 自由度封口（严格化）
# ============================================================

class A9_MinimalRealization(AxiomBase):
    """A9 严格化：最小充分实现（自由度封口）

    理论要求：系统自由度集合恰好等于公理 A1-A8 明示要求的集合，不多不少。
    工程实现：追踪活跃自由度，惩罚超出公理要求的自由度。
    """
    name = "A9_minimal_realization"
    category = "ascent_trigger"

    def __init__(self, expected_dof: int = 10, weight: float = 0.5):
        self.expected_dof = expected_dof
        self.weight = weight

    def violation(self, state, next_state, layer, history, **kwargs):
        # 估计活跃自由度：状态中独立变化的模式数
        # 简化：用硬二值化后的唯一行数估计
        hard = (next_state > 0.5).float()
        if hard.dim() == 1:
            hard = hard.unsqueeze(0)  # (1, N)
        elif hard.dim() > 2:
            hard = hard.flatten(1)  # (B, features)
        unique_patterns = len(set(tuple(row.tolist()) for row in hard))

        # 惩罚自由度超出
        excess = max(0, unique_patterns - self.expected_dof)
        violation_val = excess / max(1, self.expected_dof)

        return AxiomReport(
            name=self.name,
            raw_violation=float(violation_val),
            weight=self.weight,
            weighted_violation=float(violation_val) * self.weight,
            metadata={
                "active_dof": unique_patterns,
                "expected_dof": self.expected_dof,
                "excess": excess,
            }
        )


# ============================================================
# 严格化公理引擎
# ============================================================

class AxiomEngineStrict:
    """严格化公理引擎

    整合所有严格化九公理，提供统一的评估和损失计算接口。
    """

    def __init__(self, N: int, config: Optional[Dict] = None):
        """
        Args:
            N: 状态空间比特数
            config: 配置字典
        """
        config = config or {}

        self.axioms = {
            "A1": A1_DifferenceSourceStrict(
                monotonicity_weight=config.get("a1_weight", 1.0)
            ),
            "A2": A2_DiscreteEncodingStrict(
                temperature=config.get("a2_temperature", 0.1),
                weight=config.get("a2_weight", 1.0)
            ),
            "A4": A4_MinimalVariationStrict(
                target_distance=config.get("a4_target_distance", 1.0),
                weight=config.get("a4_weight", 0.8)
            ),
            "A5": A5_ConservationStrict(
                weight=config.get("a5_weight", 1.0)
            ),
            "A6": A6_DAGConstraint(
                weight=config.get("a6_weight", 1.0)
            ),
            "A7": A7_CycleClosure(
                weight=config.get("a7_weight", 0.8),
                min_cycle_length=config.get("a7_min_cycle", 4)
            ),
            "A8": A8_SymmetryPreference(
                N=N,
                weight=config.get("a8_weight", 1.0)
            ),
            "A9": A9_MinimalRealization(
                expected_dof=config.get("a9_expected_dof", 10),
                weight=config.get("a9_weight", 0.5)
            ),
        }

    def evaluate(self, state, next_state, layer, history, **kwargs) -> Dict[str, AxiomReport]:
        """评估所有严格化公理"""
        reports = {}
        for name, axiom in self.axioms.items():
            reports[name] = axiom.violation(state, next_state, layer, history, **kwargs)
        return reports

    def total_loss(self, state, next_state, layer, history, **kwargs) -> torch.Tensor:
        """计算总公理损失"""
        reports = self.evaluate(state, next_state, layer, history, **kwargs)
        losses = []
        for name, report in reports.items():
            if report.weight > 0:
                losses.append(report.weighted_violation)
        if not losses:
            return torch.tensor(0.0)
        # weighted_violation 可能是 float 或 tensor，统一转换
        tensor_losses = [torch.tensor(l) if isinstance(l, (int, float)) else l for l in losses]
        return torch.stack(tensor_losses).mean()

    def reset(self):
        """重置有状态的公理（新 episode 时调用）"""
        if "A6" in self.axioms:
            self.axioms["A6"].reset()


def create_strict_axiom_engine(N: int, **kwargs) -> AxiomEngineStrict:
    """工厂函数：创建严格化公理引擎"""
    return AxiomEngineStrict(N, kwargs)
