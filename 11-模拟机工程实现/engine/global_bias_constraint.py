"""
GlobalBiasConstraint — 全局偏置算子约束机制

Phase 3 核心组件：对各局部偏置算子施加统一约束，确保前主体态的"统一内部视角"。

理论依据：
  - 《象界》第八章：前主体态具有统一的内部视角
  - 偏置算子统一语言：B_G 是各 B_M(k) 的加权几何整合

设计文档：docs/phase3_global_bias_constraint_design.md
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import torch
import numpy as np


@dataclass
class GlobalBiasConstraintResult:
    """全局偏置约束检测结果"""
    passed: bool                      # 是否通过所有约束
    coherence: float                  # 方向一致性 [0, 1]
    balance: float                    # 强度平衡度 [0, 1]
    global_bias: torch.Tensor         # 计算出的全局偏置向量
    local_biases: Dict[str, torch.Tensor]  # 各机制的局部偏置
    coherence_by_mechanism: Dict[str, float]  # 各机制与全局的夹角余弦
    violating_mechanisms: List[str]   # 违反约束的机制名称
    description: str                  # 结果描述


class GlobalBiasConstraint:
    """
    全局偏置算子约束 — 对各局部偏置施加统一约束，确保前主体态的"统一内部视角"。

    理论依据：
      - 《象界》第八章：前主体态具有统一的内部视角
      - 偏置算子统一语言：B_G 是各 B_M(k) 的整合

    核心功能：
      1. 从各机制收集局部偏置算子
      2. 计算全局偏置算子 B_G（加权几何平均）
      3. 检测方向一致性约束
      4. 检测强度一致性约束
      5. 返回约束检测结果和违反机制列表

    使用方式：
        gbc = GlobalBiasConstraint()
        result = gbc.evaluate(
            local_biases={
                'boundary': bias_boundary,
                'self_sustaining': bias_self_sustaining,
                'memory': bias_memory,
                'replication': bias_replication,
                'selection': bias_selection,
                'function': bias_function,
            },
            coupling_strengths={
                'boundary': 0.8,
                'self_sustaining': 0.6,
                ...
            },
        )
        if not result.passed:
            print(f"全局偏置约束失败: {result.description}")
    """

    # 六机制名称（与 Phase 2 的六阈值保持一致）
    MECHANISMS = [
        'boundary',
        'self_sustaining',
        'memory',
        'replication',
        'selection',
        'function',
    ]

    def __init__(
        self,
        coherence_threshold: float = 0.6,
        balance_threshold: float = 0.5,
        min_mechanisms_required: int = 4,  # 最少需要几个机制提供偏置
        geometric_weighting: bool = True,   # 使用几何平均 vs 算术平均
    ):
        """
        Args:
            coherence_threshold: 方向一致性阈值
            balance_threshold: 强度平衡度阈值
            min_mechanisms_required: 最少需要几个机制提供有效偏置
            geometric_weighting: 是否使用几何平均（推荐 True）
        """
        self.coherence_threshold = coherence_threshold
        self.balance_threshold = balance_threshold
        self.min_mechanisms_required = min_mechanisms_required
        self.geometric_weighting = geometric_weighting

        # 历史检测结果
        self._history: List[GlobalBiasConstraintResult] = []

    def evaluate(
        self,
        local_biases: Dict[str, torch.Tensor],
        coupling_strengths: Optional[Dict[str, float]] = None,
    ) -> GlobalBiasConstraintResult:
        """
        评估全局偏置约束。

        Args:
            local_biases: {mechanism_name: bias_vector}
            coupling_strengths: {mechanism_name: strength}（可选，用于加权）

        Returns:
            GlobalBiasConstraintResult 约束检测结果
        """
        # 1. 过滤有效偏置（非零向量）
        valid_biases = {}
        for name, bias in local_biases.items():
            if bias.norm() > 1e-8:
                valid_biases[name] = bias

        if len(valid_biases) < self.min_mechanisms_required:
            ref_tensor = list(local_biases.values())[0] if local_biases else torch.tensor([])
            return GlobalBiasConstraintResult(
                passed=False,
                coherence=0.0,
                balance=0.0,
                global_bias=torch.zeros_like(ref_tensor) if ref_tensor.numel() > 0 else torch.tensor([]),
                local_biases=local_biases,
                coherence_by_mechanism={},
                violating_mechanisms=[
                    m for m in self.MECHANISMS
                    if m not in valid_biases
                ],
                description=f"有效偏置数量不足: {len(valid_biases)}/{self.min_mechanisms_required}",
            )

        # 2. 计算权重（默认均匀，或使用耦合强度）
        if coupling_strengths is not None:
            weights = {
                name: coupling_strengths.get(name, 1.0)
                for name in valid_biases
            }
        else:
            weights = {name: 1.0 for name in valid_biases}

        # 归一化权重
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}

        # 3. 计算全局偏置 B_G
        if self.geometric_weighting:
            global_bias = self._geometric_mean(
                list(valid_biases.values()),
                list(weights.values()),
            )
        else:
            global_bias = self._arithmetic_mean(
                list(valid_biases.values()),
                list(weights.values()),
            )

        # 4. 计算方向一致性
        coherence_by_mechanism = {}
        for name, bias in valid_biases.items():
            cos_sim = self._cosine_similarity(bias, global_bias)
            coherence_by_mechanism[name] = cos_sim

        avg_coherence = float(np.mean(list(coherence_by_mechanism.values())))

        # 5. 计算强度平衡度
        # 使用归一化强度：将每个机制的偏置强度归一化到 [0, 1] 后比较
        # 避免不同机制因向量维度/来源不同导致的量纲差异
        # 每个机制有其理论最大强度，归一化后进行比较
        INTENSITY_NORMALIZATION = {
            'boundary': 1.0,           # direction 值域 [-1, 1], mean_abs 最大 1.0
            'self_sustaining': 1.0,    # 与 boundary 同维度
            'memory': 1.0,             # 累积偏置场，理论最大 1.0
            'replication': 1.0,        # binding_strength 行均值，理论最大 1.0
            'selection': 1.0,          # variant probs, 理论最大 1.0
            'function': 1.0,           # direction_agreement ∈ [0, 1]
        }
        
        intensities = []
        norm_debug = {}
        for name, bias in valid_biases.items():
            raw_norm = float(bias.norm().item())
            mean_abs = float(bias.abs().mean().item())
            # 归一化到 [0, 1]
            max_int = INTENSITY_NORMALIZATION.get(name, 1.0)
            normalized_int = min(1.0, mean_abs / max_int) if max_int > 0 else 0.0
            norm_debug[name] = {'raw_norm': raw_norm, 'mean_abs': mean_abs, 'normalized': normalized_int}
            intensities.append(normalized_int)
        
        if len(intensities) >= 2:
            # 使用对数尺度计算平衡度：对比例差异更公平
            # balance = 1 - std(log(intensities)) / max_std
            # 这样 10x 和 100x 的差异被视为可比的比例差异
            log_ints = [np.log10(max(i, 1e-10)) for i in intensities]
            log_std = float(np.std(log_ints))
            max_log_std = 2.0  # log10(100) ≈ 2，即 100 倍差异作为最大参考
            balance = max(0.0, 1.0 - log_std / max_log_std)
        else:
            balance = 1.0

        # 6. 判定违反的机制
        violating = [
            name for name, cos_sim in coherence_by_mechanism.items()
            if cos_sim < self.coherence_threshold
        ]

        # 7. 判定是否通过
        passed = (
            avg_coherence >= self.coherence_threshold
            and balance >= self.balance_threshold
            and len(violating) == 0
        )

        # 8. 构建描述
        description = self._build_description(
            passed, avg_coherence, balance, violating, len(valid_biases),
            norm_debug if 'norm_debug' in dir() else {}
        )

        result = GlobalBiasConstraintResult(
            passed=passed,
            coherence=avg_coherence,
            balance=balance,
            global_bias=global_bias,
            local_biases=valid_biases,
            coherence_by_mechanism=coherence_by_mechanism,
            violating_mechanisms=violating,
            description=description,
        )

        self._history.append(result)
        return result

    def _geometric_mean(
        self,
        vectors: List[torch.Tensor],
        weights: List[float],
    ) -> torch.Tensor:
        """加权几何平均：在单位球面上进行加权平均（Karcher 均值近似）"""
        # 归一化所有向量到单位长度
        normalized = [v / (v.norm() + 1e-10) for v in vectors]

        # 在切空间中进行加权平均
        result = torch.zeros_like(vectors[0])
        for v, w in zip(normalized, weights):
            result = result + w * v

        # 归一化回单位球面
        result = result / (result.norm() + 1e-10)

        # 恢复原始强度的加权平均
        original_norms = [float(v.norm().item()) for v in vectors]
        avg_norm = sum(w * n for w, n in zip(weights, original_norms))
        result = result * avg_norm

        return result

    def _arithmetic_mean(
        self,
        vectors: List[torch.Tensor],
        weights: List[float],
    ) -> torch.Tensor:
        """加权算术平均"""
        result = torch.zeros_like(vectors[0])
        for v, w in zip(vectors, weights):
            result = result + w * v
        return result

    @staticmethod
    def _cosine_similarity(a: torch.Tensor, b: torch.Tensor) -> float:
        """计算两个向量的余弦相似度"""
        norm_a = a.norm().item()
        norm_b = b.norm().item()
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0
        return float(torch.dot(a, b).item() / (norm_a * norm_b))

    def _build_description(
        self,
        passed: bool,
        coherence: float,
        balance: float,
        violating: List[str],
        n_valid: int,
        norm_debug: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> str:
        """构建结果描述"""
        if passed:
            return (
                f"全局偏置约束通过: 一致性={coherence:.3f}, "
                f"平衡度={balance:.3f}, {n_valid}个机制参与"
            )

        parts = []
        if coherence < self.coherence_threshold:
            parts.append(f"方向一致性不足({coherence:.3f}<{self.coherence_threshold})")
        if balance < self.balance_threshold:
            parts.append(f"强度不平衡({balance:.3f}<{self.balance_threshold})")
        if violating:
            parts.append(f"偏离机制: {', '.join(violating)}")
        
        # 附加强度诊断
        if norm_debug:
            intensity_str = ", ".join(
                f"{k}(|·|_mean={v['mean_abs']:.4f}, norm={v['normalized']:.3f})" for k, v in norm_debug.items()
            )
            parts.append(f"强度分布: [{intensity_str}]")

        return "全局偏置约束失败: " + "; ".join(parts)

    # ─── 查询接口 ───

    def get_history(self, limit: int = 100) -> List[GlobalBiasConstraintResult]:
        """获取约束检测历史（最近 N 条）"""
        return self._history[-limit:]

    def get_coherence_trend(self) -> List[float]:
        """获取方向一致性时间序列"""
        return [r.coherence for r in self._history]

    def get_balance_trend(self) -> List[float]:
        """获取强度平衡度时间序列"""
        return [r.balance for r in self._history]

    def get_pass_rate(self) -> float:
        """获取约束通过率"""
        if not self._history:
            return 0.0
        passed = sum(1 for r in self._history if r.passed)
        return passed / len(self._history)

    def reset(self):
        """重置历史"""
        self._history.clear()

    def __repr__(self) -> str:
        if not self._history:
            return "GlobalBiasConstraint[empty]"
        latest = self._history[-1]
        status = "PASS" if latest.passed else "FAIL"
        return (
            f"GlobalBiasConstraint[{status}] "
            f"coh={latest.coherence:.3f} bal={latest.balance:.3f} "
            f"n_checks={len(self._history)}"
        )
