"""
chain.py — 象界显现链检测器

对应《象界》八章生成链（边界→界面→自维持→记忆→复制→筛选→功能→前主体态）。
每个门槛检测器判断结构是否跨越了对应的组织密度门槛。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import torch
import torch.nn.functional as F
import numpy as np

from acl.axiom_base import StableStructure


# =============================================================================
# 门槛报告
# =============================================================================

@dataclass
class ThresholdReport:
    """单个门槛的检测结果"""
    name: str           # 门槛名称（中文）
    stage: str          # 对应阶段（英文）
    passed: bool       # 是否通过
    score: float       # 当前得分 [0, 1]
    threshold: float   # 通过阈值
    detail: str        # 人类可读说明
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class XiangjieReport:
    """完整象界显现链报告"""
    thresholds: List[ThresholdReport]
    overall_score: float      # 综合得分 [0, 1]
    max_stage_reached: int      # 最高到达阶段 (1-8)
    max_stage_name: str        # 最高阶段名称
    is_pre_subjective: bool    # 是否达到前主体态
    chain_summary: str = ""

    def __str__(self) -> str:
        lines = ["=== Xiangjie Chain Report ==="]
        for t in self.thresholds:
            flag = "Y" if t.passed else "N"
            lines.append(
                f"{flag} [{t.stage}] {t.name}: {t.score:.3f}/{t.threshold:.3f}"
                f" — {t.detail}"
            )
        lines.append("")
        lines.append(
            f"Overall: {self.overall_score:.3f} | "
            f"Max Stage: {self.max_stage_reached}. {self.max_stage_name} | "
            f"Pre-subjective: {'YES' if self.is_pre_subjective else 'NO'}"
        )
        return "\n".join(lines)


# =============================================================================
# 八章门槛检测器
# =============================================================================

class BoundaryGate:
    """
    【第一章：边界】
    门槛：结构具有清晰的内外区分，边界闭合度良好。
    使用 struct.boundary_closure_score（越低越闭合）和 connectivity_ratio
    作为综合判据。
    对应《象界》第一章：边界不只是隔离，而是调节交换的通道。
    """

    name = "边界"
    stage = "I"
    threshold = 0.30  # 综合得分 ≥ 0.30 → 通过

    def evaluate(self, struct: StableStructure) -> ThresholdReport:
        area = struct.mask.sum().item()
        boundary = struct.boundary_map.sum().item()

        if area == 0:
            score = 0.0
            ratio = 0.0
        else:
            ratio = boundary / area
            # 使用两个维度：
            #   connectivity_ratio 越高越好（内部完整性）
            #   boundary_closure_score 越低越好（边缘紧致）
            # 综合 = connectivity * (1 - boundary_closure)
            cr = getattr(struct, 'connectivity_ratio', 0.5)
            bc = getattr(struct, 'boundary_closure_score', 0.5)
            score = cr * (1.0 - min(1.0, bc))

        passed = score >= self.threshold
        detail = (
            f"边界像素 {int(boundary)}, 面积 {int(area)}, "
            f"比例 {ratio:.3f}, 综合得分 {score:.3f} → "
            f"{'通过' if passed else '未通过'}"
        )
        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=score,
            threshold=self.threshold, detail=detail,
            meta={"ratio": ratio, "area": area, "boundary": boundary}
        )


class InterfaceGate:
    """
    【第二章：界面】
    门槛：边界区域与内部区域之间存在差异梯度（界面 ≠ 边界）。
    对应《象界》第二章：界面是成熟边界的功能形态，是调节交换的通道。
    """

    name = "界面"
    stage = "II"
    threshold = 0.15  # 界面梯度 > 0.15 → 通过

    def evaluate(self, struct: StableStructure,
                 state: Optional[torch.Tensor] = None) -> ThresholdReport:
        # 用 boundary_map 的膨胀来近似内部-边界交界
        mask = struct.mask.float().unsqueeze(0).unsqueeze(0)  # (1,1,H,W)
        kernel = torch.ones(1, 1, 3, 3, device=mask.device)

        # 边界膨胀 1 pixel = 内部-边界交界
        boundary_expanded = F.conv2d(
            mask, kernel, padding=1
        ) > 0  # 结构膨胀（含边界）

        interior = boundary_expanded & ~(struct.mask.unsqueeze(0).unsqueeze(0).bool())

        # 计算界面梯度：在 boundary_expanded 区域内，边界与内部的差异
        # 如果 state 可用，用状态值差异；否则用边界膨胀区作为代理
        if state is not None and state.numel() > 0:
            # state: (B,C,H,W)，取第一帧
            s = state[0, 0]
            boundary_values = s[struct.boundary_map.bool()]
            interior_values = s[interior.squeeze()]
            if boundary_values.numel() > 0 and interior_values.numel() > 0:
                gradient = (
                    boundary_values.mean() - interior_values.mean()
                ).abs().item()
            else:
                gradient = 0.0
        else:
            # 代理：boundary 膨胀区面积 / 结构面积
            boundary_area = int(boundary_expanded.sum().item())
            area = int(struct.mask.sum().item())
            gradient = boundary_area / max(1, area)

        score = min(1.0, gradient)
        passed = score >= self.threshold
        detail = f"界面梯度 {gradient:.3f} → {'通过' if passed else '未通过'}"
        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=score,
            threshold=self.threshold, detail=detail,
            meta={"gradient": gradient}
        )


class SelfMaintenanceGate:
    """
    【第三章：自维持】
    门槛：结构的物质更替率在合理范围，说明在开放交换中持续重建自身。
    对应《象界》第三章：自维持 = 在开放环境中通过循环不断重建自身条件。
    """

    name = "自维持"
    stage = "III"
    # 更替率在 (0.05, 0.40) 之间为活跃自维持
    threshold_low = 0.05
    threshold_high = 0.40

    def evaluate(self, struct: StableStructure) -> ThresholdReport:
        turnover = struct.material_turnover
        # 活跃自维持：更替率 > 0 且不太高
        score = 1.0 - abs(
            turnover - (self.threshold_low + self.threshold_high) / 2
        ) / (self.threshold_high - self.threshold_low)
        score = max(0.0, min(1.0, score))
        passed = (
            turnover > self.threshold_low
            and turnover < self.threshold_high
        )
        detail = (
            f"更替率 {turnover:.3f}, 区间 "
            f"[{self.threshold_low:.2f}, {self.threshold_high:.2f}] → "
            f"{'通过' if passed else '未通过'}"
        )
        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=score,
            threshold=self.threshold_high, detail=detail,
            meta={"turnover": turnover}
        )


class MemoryGate:
    """
    【第四章：记忆】
    门槛：结构的时间持续性（lifetime）超过阈值，说明过去路径对未来形成限制。
    对应《象界》第四章：记忆 = 过去差异关系对未来差异关系的持续限制。
    """

    name = "记忆"
    stage = "IV"
    threshold = 16  # 存活步数 ≥ 16（一个稳定性窗口）

    def evaluate(self, struct: StableStructure) -> ThresholdReport:
        lifetime = struct.lifetime
        score = min(1.0, lifetime / (self.threshold * 2))
        passed = lifetime >= self.threshold
        detail = f"存活 {lifetime} 步, 阈值 {self.threshold} → {'通过' if passed else '未通过'}"
        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=score,
            threshold=self.threshold, detail=detail,
            meta={"lifetime": lifetime}
        )


class ReplicationGate:
    """
    【第五章：复制】
    门槛：结构模式签名在历史中保持相似（pattern_signature 一致性）。
    对应《象界》第五章：复制 = 关系样式的跨次延续，非机械重现。
    """

    name = "复制"
    stage = "V"
    threshold = 0.70  # pattern 一致性 ≥ 0.70

    def evaluate(self, struct: StableStructure,
                 history: Optional[List[torch.Tensor]] = None) -> ThresholdReport:
        pattern = struct.pattern_signature

        if history is not None and len(history) >= 4:
            # 检查历史中相似模式的出现频率
            recent = history[-8:]
            matches = 0
            for h in recent:
                if h.dim() >= 2:
                    # 适配 mask 和 history 的 shape
                    mask_bool = struct.mask.bool()
                    # h 可能是 (B,C,H,W) 或 (H,W)
                    while h.dim() > mask_bool.dim():
                        h = h.squeeze(0)
                    # 如果 h 仍然比 mask 多维，对齐
                    if h.dim() > mask_bool.dim():
                        h = h.reshape(mask_bool.shape)
                    if h.shape == mask_bool.shape:
                        h_masked = h[mask_bool]
                    else:
                        # 形状不匹配，降级处理
                        h_masked = h.flatten()[:mask_bool.sum().item()]
                    if h_masked.numel() > 0:
                        hist_mean = h_masked.mean().item()
                        struct_mean = pattern.mean().item()
                        if abs(hist_mean - struct_mean) < 0.1:
                            matches += 1
            consistency = matches / len(recent)
        else:
            # 降级：只用 pattern_signature 本身的值稳定性作为代理
            consistency = float(pattern.std().item()) if pattern.numel() > 1 else 1.0

        score = consistency
        passed = score >= self.threshold
        detail = f"模式一致性 {score:.3f}, 阈值 {self.threshold} → {'通过' if passed else '未通过'}"
        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=score,
            threshold=self.threshold, detail=detail,
            meta={"consistency": consistency}
        )


class SelectionGate:
    """
    【第六章：筛选】
    门槛：结构间的连通性（connectivity_ratio）差异体现延续概率的不对称。
    对应《象界》第六章：筛选 = 不同样式在延续能力上的差异所导致的分流。
    """

    name = "筛选"
    stage = "VI"
    threshold = 0.50  # connectivity_ratio ≥ 0.50

    def evaluate(self, struct: StableStructure,
                 all_structures: Optional[List[StableStructure]] = None) -> ThresholdReport:
        cr = struct.connectivity_ratio

        # 如果有多个结构，额外检查相对延续概率
        if all_structures is not None and len(all_structures) > 1:
            # 计算各结构的连通性，排序后看当前结构排第几
            crs = [s.connectivity_ratio for s in all_structures]
            crs_sorted = sorted(crs, reverse=True)
            rank = crs_sorted.index(cr) + 1
            total = len(crs_sorted)
            relative_score = (total - rank + 1) / total
            score = (cr + relative_score) / 2.0
        else:
            score = cr

        passed = score >= self.threshold
        detail = f"连通性 {cr:.3f}, 综合得分 {score:.3f} → {'通过' if passed else '未通过'}"
        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=score,
            threshold=self.threshold, detail=detail,
            meta={"connectivity_ratio": cr}
        )


class FunctionGate:
    """
    【第七章：功能】
    门槛：结构在整体中具有不对称的贡献关系（局部与整体的耦合不对称性）。
    对应《象界》第七章：功能 = 耦合在延续、复制与筛选中被沉积出的不对称贡献。
    """

    name = "功能"
    stage = "VII"
    threshold = 0.40  # 局部对整体的贡献不对称性 ≥ 0.40

    def evaluate(self, struct: StableStructure,
                 global_activity: Optional[float] = None) -> ThresholdReport:
        # 功能 = 结构对整体的贡献能力
        # 简化实现：结构活跃度与整体活跃度的比值
        if global_activity is not None and global_activity > 0:
            struct_activity = struct.pattern_signature.mean().item()
            ratio = struct_activity / global_activity
            # ratio > 1 说明结构贡献超出平均水平
            contribution = min(1.0, ratio)
        else:
            # 降级：连通性本身（连通结构通常对整体有贡献）
            contribution = struct.connectivity_ratio

        score = contribution
        passed = score >= self.threshold
        detail = (
            f"贡献度 {score:.3f}, 阈值 {self.threshold} → "
            f"{'通过' if passed else '未通过'}"
        )
        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=score,
            threshold=self.threshold, detail=detail,
            meta={"contribution": contribution}
        )


class PreSubjectiveGate:
    """
    【第八章：前主体态】
    门槛：前七个门槛中通过 ≥ 5 个，且结构内部连通性 > 0.6。
    对应《象界》第八章：前主体态是边界、自维持、记忆、复制、筛选与功能
    在同一结构中形成稳定耦合后的整体状态。
    """

    name = "前主体态"
    stage = "VIII"
    min_gates_passed = 5   # 八章中至少通过 5 个
    min_connectivity = 0.6  # 内部连通性 > 0.6

    def evaluate(self, sub_reports: List[ThresholdReport],
                 struct: StableStructure) -> ThresholdReport:
        # 统计前七章通过数量
        passed_count = sum(1 for r in sub_reports if r.passed)
        connectivity = struct.connectivity_ratio

        score = (passed_count / 7.0 + connectivity) / 2.0
        passed = (
            passed_count >= self.min_gates_passed
            and connectivity > self.min_connectivity
        )

        detail = (
            f"通过 {passed_count}/7 个门槛, "
            f"连通性 {connectivity:.3f} > {self.min_connectivity} → "
            f"{'达到前主体态' if passed else '未达到'}"
        )
        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=score,
            threshold=0.5, detail=detail,
            meta={
                "passed_count": passed_count,
                "connectivity": connectivity,
            }
        )


# =============================================================================
# 象界显现链主类
# =============================================================================

class XiangjieChain:
    """
    象界显现链评估器。

    评估结构是否通过《象界》八章生成链的每一道门槛，
    并给出综合报告。
    """

    def __init__(self):
        self.gates = [
            BoundaryGate(),
            InterfaceGate(),
            SelfMaintenanceGate(),
            MemoryGate(),
            ReplicationGate(),
            SelectionGate(),
            FunctionGate(),
        ]
        self.pre_subjective_gate = PreSubjectiveGate()

    def evaluate(
        self,
        structures: List[StableStructure],
        history: List[torch.Tensor],
        layer=None,
        current_state: Optional[torch.Tensor] = None,
    ) -> XiangjieReport:
        """
        评估所有结构，返回完整象界显现链报告。

        Args:
            structures: 检测到的稳定结构列表
            history: 演化历史（用于记忆、复制等门槛）
            layer: 当前层级（用于全局活跃度等）
            current_state: 当前状态（用于界面梯度）

        Returns:
            XiangjieReport：综合评估结果
        """
        if not structures:
            # 无结构：全部门槛失败
            return self._empty_report()

        # 对每个结构计算八章门槛
        all_reports: List[List[ThresholdReport]] = []

        for struct in structures:
            struct_reports = []

            # 前六章各自评估
            for gate in self.gates:
                if isinstance(gate, InterfaceGate):
                    r = gate.evaluate(struct, current_state)
                elif isinstance(gate, ReplicationGate):
                    r = gate.evaluate(struct, history)
                elif isinstance(gate, SelectionGate):
                    r = gate.evaluate(struct, structures)
                elif isinstance(gate, FunctionGate):
                    global_activity = None
                    if layer is not None and history:
                        global_activity = history[-1].mean().item()
                    r = gate.evaluate(struct, global_activity)
                elif isinstance(gate, MemoryGate):
                    r = gate.evaluate(struct)
                elif isinstance(gate, SelfMaintenanceGate):
                    r = gate.evaluate(struct)
                elif isinstance(gate, BoundaryGate):
                    r = gate.evaluate(struct)
                else:
                    r = gate.evaluate(struct)
                struct_reports.append(r)

            # 第八章 前主体态
            ps_report = self.pre_subjective_gate.evaluate(struct_reports, struct)
            struct_reports.append(ps_report)

            all_reports.append(struct_reports)

        # 取综合得分最高的结构作为代表
        best_idx = max(
            range(len(all_reports)),
            key=lambda i: sum(r.score for r in all_reports[i]) / len(all_reports[i])
        )
        best_reports = all_reports[best_idx]
        best_struct = structures[best_idx]

        # 综合得分
        overall_score = sum(r.score for r in best_reports) / len(best_reports)

        # 最高到达阶段：连续通过的门槛数
        stage_order = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
        max_stage_reached = 0
        for r in best_reports:
            if r.passed:
                idx = stage_order.index(r.stage) + 1
                max_stage_reached = max(max_stage_reached, idx)
            else:
                break

        max_stage_name = (
            best_reports[max_stage_reached - 1].name
            if max_stage_reached > 0 else "无"
        )
        is_pre_subjective = best_reports[-1].passed

        return XiangjieReport(
            thresholds=best_reports,
            overall_score=overall_score,
            max_stage_reached=max_stage_reached,
            max_stage_name=max_stage_name,
            is_pre_subjective=is_pre_subjective,
        )

    def _empty_report(self) -> XiangjieReport:
        """无结构时的空报告"""
        stages = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
        names = ["边界", "界面", "自维持", "记忆", "复制", "筛选", "功能", "前主体态"]
        thresholds = [
            ThresholdReport(
                name=n, stage=s, passed=False,
                score=0.0, threshold=0.3, detail="无稳定结构"
            )
            for s, n in zip(stages, names)
        ]
        return XiangjieReport(
            thresholds=thresholds,
            overall_score=0.0,
            max_stage_reached=0,
            max_stage_name="无",
            is_pre_subjective=False,
        )