"""
axioms.py — 九条公理的具体实现

公理分类：
- 约束类（A2/A3/A4/A5/A7）：参与 loss 计算
- 观测类（A1/A6/A8）：记录但不直接影响演化
- 触发类（A9）：不参与训练，只做升维判定
"""

import torch
import torch.nn.functional as F
from acl.axiom_base import AxiomBase, AxiomReport


# ============================================================
# 观测类公理
# ============================================================

class A1_DifferenceSource(AxiomBase):
    """A1：差异源。不作为 loss，作为观测指标。
    差异注入由 layer.inject_difference() 执行。"""
    name = "A1_difference_source"
    category = "observation"

    def violation(self, state, next_state, layer, history):
        diff_level = layer.measure_difference(next_state)
        return AxiomReport(
            name=self.name, raw_violation=0.0,
            weight=0.0, weighted_violation=0.0,
            metadata={"difference_level": float(diff_level.mean())}
        )


class A6_FlowCoupling(AxiomBase):
    """A6：差异流向耦合。不作为 loss，作为观测指标。
    方向性由源-汇边界条件隐式保证。"""
    name = "A6_flow_coupling"
    category = "observation"

    def violation(self, state, next_state, layer, history):
        diff = layer.measure_difference(next_state)
        return AxiomReport(
            name=self.name, raw_violation=0.0,
            weight=0.0, weighted_violation=0.0,
            metadata={"gradient_magnitude": float(diff.mean())}
        )


class A8_SymmetrySink(AxiomBase):
    """A8：差异汇/耗散。不作为 loss，作为观测指标。
    差异吸收由 layer.absorb_difference() 执行。"""
    name = "A8_symmetry_sink"
    category = "observation"

    def violation(self, state, next_state, layer, history):
        return AxiomReport(
            name=self.name, raw_violation=0.0,
            weight=0.0, weighted_violation=0.0,
            metadata={"sink_active": True}
        )


# ============================================================
# 约束类公理
# ============================================================

class A2_DiscreteEncoding(AxiomBase):
    """A2：离散编码约束。保证状态不漂到无限连续空间。"""
    name = "A2_discrete_encoding"
    category = "state"

    def violation(self, state, next_state, layer, history):
        v = layer.discreteness_violation(next_state)
        return AxiomReport(
            name=self.name, raw_violation=float(v),
            weight=1.0, weighted_violation=float(v)
        )


class A3_Locality(AxiomBase):
    """A3：局域性。优先由模型结构（CNN 小卷积核）保证，loss 作为补充。"""
    name = "A3_locality"
    category = "state"

    def violation(self, state, next_state, layer, history):
        v = layer.locality_violation(state, next_state)
        return AxiomReport(
            name=self.name, raw_violation=float(v),
            weight=1.0, weighted_violation=float(v)
        )


class A4_MinimalVariation(AxiomBase):
    """A4：局部最小变易。变化有代价，偏好较小代价路径。"""
    name = "A4_minimal_variation"
    category = "transition"

    def violation(self, state, next_state, layer, history):
        v = layer.transition_cost(state, next_state)
        return AxiomReport(
            name=self.name, raw_violation=float(v),
            weight=0.8, weighted_violation=float(v) * 0.8
        )


class A5_Conservation(AxiomBase):
    """A5：守恒律。追踪守恒残差，与 A9 联动检测升维压力。"""
    name = "A5_conservation"
    category = "invariant"

    def violation(self, state, next_state, layer, history):
        q_now = layer.measure_invariant(state)
        q_next = layer.measure_invariant(next_state)
        residual = ((q_next - q_now) ** 2).mean()
        return AxiomReport(
            name=self.name, raw_violation=float(residual),
            weight=1.0, weighted_violation=float(residual),
            metadata={"conservation_residual": float(residual)}
        )


class A7_Stability(AxiomBase):
    """A7：稳定闭合。区分活结构（模式持续+物质更换）、
    死结构（模式持续+物质不换）和噪声（模式不持续）。"""
    name = "A7_stability"
    category = "rollout"

    def violation(self, state, next_state, layer, history):
        if len(history) < layer.stability_window:
            return AxiomReport(
                name=self.name, raw_violation=0.0,
                weight=0.0, weighted_violation=0.0
            )

        window = history[-layer.stability_window:]
        v = layer.stability_violation(window)
        return AxiomReport(
            name=self.name, raw_violation=float(v),
            weight=1.0, weighted_violation=float(v)
        )


# ============================================================
# 触发类公理
# ============================================================

class A9_MinimalSufficient(AxiomBase):
    """A9：升维触发器。检测当前层表达是否耗尽。
    不作为训练 loss，作为层级升级的判定条件。
    对应差异论中的"素数"——不可再约，必须升维。"""
    name = "A9_minimal_sufficient"
    category = "ascent_trigger"
    ascent_threshold: float = 0.5

    def violation(self, state, next_state, layer, history):
        return AxiomReport(
            name=self.name, raw_violation=0.0,
            weight=0.0, weighted_violation=0.0,
            metadata={"ascent_ready": False}
        )

    def check_ascent(self, layer, history, structures) -> bool:
        """独立的升维判定：A5 守恒残差 + A9 不可约性"""
        if len(structures) == 0:
            return False
        pressure = layer.measure_ascent_pressure(history, structures)
        return pressure > self.ascent_threshold


# ============================================================
# 默认公理集合
# ============================================================

def create_default_axioms(ascent_threshold: float = 0.5):
    """创建默认的九条公理实例"""
    a9 = A9_MinimalSufficient()
    a9.ascent_threshold = ascent_threshold

    return [
        A1_DifferenceSource(),
        A2_DiscreteEncoding(),
        A3_Locality(),
        A4_MinimalVariation(),
        A5_Conservation(),
        A6_FlowCoupling(),
        A7_Stability(),
        A8_SymmetrySink(),
        a9,
    ]


def build_default_axiom_engine(ascent_threshold: float = 0.5):
    """构建默认的 AxiomEngine 实例"""
    from acl.axiom_base import AxiomEngine
    axioms = create_default_axioms(ascent_threshold)
    return AxiomEngine(axioms)
