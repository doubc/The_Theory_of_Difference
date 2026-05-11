"""
structure_validator.py — 稳定结构验证器

五标准验证：lifetime, boundary, closure, turnover, interaction。
对应《差异即世界》中"循环"机制的可验证条件。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import torch
import numpy as np


@dataclass
class SingleValidation:
    """单个结构的验证结果"""
    structure_id: int
    lifetime_pass: bool
    lifetime_value: int
    boundary_pass: bool
    boundary_stability: float
    closure_pass: bool
    closure_ratio: float
    turnover_pass: bool
    turnover_value: float
    overall_pass: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """完整验证报告"""
    total_structures: int
    passed_structures: int
    lifetime_passed: int
    boundary_passed: int
    closure_passed: int
    turnover_passed: int
    interaction_detected: bool
    interaction_score: float
    single_validations: List[SingleValidation] = field(default_factory=list)
    summary: str = ""


class StructureValidator:
    """稳定结构五标准验证器

    验证标准：
    1. lifetime: 结构存活时间 ≥ 阈值
    2. boundary_stability: 边界区域时间稳定性
    3. connectivity: 内部连通性（值越高越完整，审计报告拆分指标 #5）
    4. boundary_closure: 边界紧致度（值越低越闭合，审计报告拆分指标 #5）
    5. turnover: 物质周转率低
    6. interaction: 空间接近代理指标（不等价于严格作用关系，审计报告 Section 4.2）
    """

    def __init__(
        self,
        min_lifetime: int = 8,
        boundary_stability_threshold: float = 0.3,
        connectivity_threshold: float = 0.5,
        boundary_closure_threshold: float = 0.5,
        max_turnover: float = 0.2,
        interaction_distance: float = 3.0,
        recompute_boundary: bool = False,
    ):
        self.min_lifetime = min_lifetime
        self.boundary_stability_threshold = boundary_stability_threshold
        self.connectivity_threshold = connectivity_threshold
        self.boundary_closure_threshold = boundary_closure_threshold
        self.max_turnover = max_turnover
        self.interaction_distance = interaction_distance
        self.recompute_boundary = recompute_boundary

    def validate(
        self,
        structures: list,
        history: List[torch.Tensor],
    ) -> ValidationReport:
        """验证所有结构"""
        if not structures:
            return ValidationReport(
                total_structures=0,
                passed_structures=0,
                lifetime_passed=0,
                boundary_passed=0,
                closure_passed=0,
                turnover_passed=0,
                interaction_detected=False,
                interaction_score=0.0,
                summary="No structures to validate.",
            )

        single_validations = []
        for i, struct in enumerate(structures):
            sv = self.validate_single(i, struct, history)
            single_validations.append(sv)

        # 结构间相互作用检测
        interaction_detected, interaction_score = self._check_interaction(structures)

        # 统计
        lifetime_passed = sum(1 for sv in single_validations if sv.lifetime_pass)
        boundary_passed = sum(1 for sv in single_validations if sv.boundary_pass)
        closure_passed = sum(1 for sv in single_validations if sv.closure_pass)
        turnover_passed = sum(1 for sv in single_validations if sv.turnover_pass)
        passed = sum(1 for sv in single_validations if sv.overall_pass)

        summary = self._build_summary(
            len(structures), passed, lifetime_passed, boundary_passed,
            closure_passed, turnover_passed, interaction_detected, interaction_score,
        )

        return ValidationReport(
            total_structures=len(structures),
            passed_structures=passed,
            lifetime_passed=lifetime_passed,
            boundary_passed=boundary_passed,
            closure_passed=closure_passed,
            turnover_passed=turnover_passed,
            interaction_detected=interaction_detected,
            interaction_score=interaction_score,
            single_validations=single_validations,
            summary=summary,
        )

    def validate_single(
        self,
        struct_id: int,
        struct,
        history: List[torch.Tensor],
    ) -> SingleValidation:
        """验证单个结构

        对应审计报告 Section 3：closure 拆分为 connectivity_ratio 和
        boundary_closure_score；Section 4.1：boundary 重算一致性检查。
        """
        warnings = []

        # 1. Lifetime
        lifetime_pass = struct.lifetime >= self.min_lifetime

        # 2. Boundary stability（时间维度稳定性）
        boundary_stability = self._measure_boundary_stability(struct, history)
        boundary_pass = boundary_stability < self.boundary_stability_threshold

        # 3. boundary 一致性检查（审计报告 Section 4.1）
        boundary_consistent = None
        if self.recompute_boundary:
            boundary_consistent = self._check_boundary_consistency(struct)
            if boundary_consistent is False:
                warnings.append(
                    "boundary_map inconsistent with recomputed boundary from mask "
                    "(IoU < 0.5) — possible upstream mismatch"
                )

        # 4. Connectivity（v2 字段优先，降级兼容旧 struct）
        if hasattr(struct, 'connectivity_ratio') and struct.connectivity_ratio is not None:
            connectivity_ratio = struct.connectivity_ratio
        else:
            connectivity_ratio = self._measure_closure(struct)
        connectivity_pass = connectivity_ratio >= self.connectivity_threshold

        # 5. Boundary closure（v2 字段优先：值越低越闭合）
        if hasattr(struct, 'boundary_closure_score') and struct.boundary_closure_score is not None:
            boundary_closure_val = struct.boundary_closure_score
        else:
            boundary_closure_val = 0.5  # 旧数据无此字段，默认中性
        boundary_closure_pass = boundary_closure_val <= self.boundary_closure_threshold
        if not boundary_closure_pass:
            warnings.append(
                f"boundary_closure={boundary_closure_val:.3f} > threshold "
                f"{self.boundary_closure_threshold:.3f} (边界过于开放/碎片化)"
            )

        # 6. Turnover
        turnover_value = struct.material_turnover
        turnover_pass = turnover_value < self.max_turnover

        overall = (
            lifetime_pass and boundary_pass and connectivity_pass
            and boundary_closure_pass and turnover_pass
        )

        return SingleValidation(
            structure_id=struct_id,
            lifetime_pass=lifetime_pass,
            lifetime_value=struct.lifetime,
            boundary_pass=boundary_pass,
            boundary_stability=boundary_stability,
            closure_pass=connectivity_pass,
            closure_ratio=connectivity_ratio,
            turnover_pass=turnover_pass,
            turnover_value=turnover_value,
            overall_pass=overall,
            details={
                "min_lifetime": self.min_lifetime,
                "boundary_stability_threshold": self.boundary_stability_threshold,
                "connectivity_threshold": self.connectivity_threshold,
                "boundary_closure_threshold": self.boundary_closure_threshold,
                "max_turnover": self.max_turnover,
                "connectivity_ratio": connectivity_ratio,
                "boundary_closure_score": boundary_closure_val,
                "boundary_closure_pass": boundary_closure_pass,
                "boundary_consistent": boundary_consistent,
                "warnings": warnings,
            },
        )

    def _check_boundary_consistency(self, struct) -> Optional[bool]:
        """从 struct.mask 重算边界，与 struct.boundary_map 做 IoU 一致性检查。

        返回 True（一致）/ False（不一致）/ None（无 boundary_map 无法比较）。
        对应审计报告 Section 4.1：验证器应能检测 boundary_map 与 mask 的不一致。
        """
        import torch.nn.functional as F

        if not hasattr(struct, 'boundary_map') or struct.boundary_map is None:
            return None
        mask = struct.mask.float()
        # squeeze to (H, W)
        while mask.dim() > 2:
            mask = mask.squeeze(0)
        mask_4d = mask.unsqueeze(0).unsqueeze(0)  # (1,1,H,W)

        kernel = torch.tensor(
            [[0., 1., 0.], [1., 0., 1.], [0., 1., 0.]],
            device=mask.device
        ).view(1, 1, 3, 3)
        neighbor_sum = F.conv2d(mask_4d, kernel, padding=1)
        recomputed = (mask_4d > 0) & (neighbor_sum < 4 * mask_4d) & (neighbor_sum > 0)
        recomputed = recomputed.squeeze()  # (H, W)

        stored = struct.boundary_map.float()
        while stored.dim() > 2:
            stored = stored.squeeze(0)

        both = (recomputed > 0) & (stored > 0)
        either = (recomputed > 0) | (stored > 0)
        if either.sum() == 0:
            return True
        iou = both.sum().item() / max(1, either.sum().item())
        return iou >= 0.5

    def _measure_boundary_stability(self, struct, history: List[torch.Tensor]) -> float:
        """测量边界区域的时间稳定性

        取历史中边界位置的状态值，计算时间维度标准差。
        标准差越小，边界越稳定。
        """
        if len(history) < 2:
            return 0.0

        boundary_map = struct.boundary_map
        if boundary_map.dim() < 4:
            boundary_map = boundary_map.unsqueeze(0)

        # 扩展到 batch 维度
        mask = boundary_map.bool()
        if mask.dim() == 4:
            mask = mask.unsqueeze(0)

        # 取最后几步的历史
        window = min(len(history), 8)
        recent = history[-window:]

        # 堆叠历史
        stacked = torch.stack(recent, dim=0)  # (T, B, C, H, W)

        # 在边界位置上计算时间标准差
        # 扩展 mask 以匹配 stacked
        while mask.dim() < stacked.dim():
            mask = mask.unsqueeze(0)
        mask_expanded = mask.expand_as(stacked)

        if mask_expanded.any():
            boundary_values = stacked[mask_expanded]
            stability = float(boundary_values.std())
        else:
            stability = 0.0

        return stability

    def _measure_closure(self, struct) -> float:
        """测量结构的连通性

        使用连通域分析：最大连通域占总稳定区域的比例。
        比例越高，结构越"闭合"。
        """
        mask = struct.mask
        if mask.dim() >= 2:
            mask_np = mask.float().cpu().numpy().squeeze()
        else:
            mask_np = mask.cpu().numpy()

        if mask_np.ndim != 2:
            return 1.0

        # 简单连通域分析（不依赖 scipy）
        labeled, num_features = self._label_connected_components(mask_np)

        if num_features == 0:
            return 0.0

        # 最大连通域大小
        component_sizes = []
        for label_id in range(1, num_features + 1):
            size = int((labeled == label_id).sum())
            component_sizes.append(size)

        total_pixels = int(mask_np.sum())
        if total_pixels == 0:
            return 0.0

        max_component = max(component_sizes)
        return max_component / total_pixels

    def _label_connected_components(self, binary_mask: np.ndarray):
        """简单的 4-连通域标记（不依赖 scipy）"""
        h, w = binary_mask.shape
        labeled = np.zeros((h, w), dtype=np.int32)
        current_label = 0

        for i in range(h):
            for j in range(w):
                if binary_mask[i, j] == 0 or labeled[i, j] != 0:
                    continue

                # BFS 标记连通域
                current_label += 1
                queue = [(i, j)]
                labeled[i, j] = current_label

                while queue:
                    ci, cj = queue.pop(0)
                    for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        ni, nj = ci + di, cj + dj
                        if 0 <= ni < h and 0 <= nj < w:
                            if binary_mask[ni, nj] == 1 and labeled[ni, nj] == 0:
                                labeled[ni, nj] = current_label
                                queue.append((ni, nj))

        return labeled, current_label

    def _check_interaction(self, structures: list):
        """检测结构间的相互作用

        计算每对结构之间的最小距离。
        距离 < interaction_distance 视为存在相互作用。
        """
        if len(structures) < 2:
            return False, 0.0

        interaction_count = 0
        total_pairs = 0

        for i in range(len(structures)):
            for j in range(i + 1, len(structures)):
                total_pairs += 1
                dist = self._structure_distance(structures[i], structures[j])
                if dist < self.interaction_distance:
                    interaction_count += 1

        score = interaction_count / total_pairs if total_pairs > 0 else 0.0
        detected = interaction_count > 0

        return detected, score

    def _structure_distance(self, s1, s2) -> float:
        """计算两个结构之间的最小距离（mask 中心距离）"""
        def center_of_mass(mask):
            if mask.dim() >= 2:
                mask_np = mask.float().cpu().numpy().squeeze()
            else:
                mask_np = mask.cpu().numpy()
            if mask_np.ndim != 2:
                return (0.0, 0.0)
            ys, xs = np.where(mask_np > 0)
            if len(ys) == 0:
                return (0.0, 0.0)
            return (float(ys.mean()), float(xs.mean()))

        c1 = center_of_mass(s1.mask)
        c2 = center_of_mass(s2.mask)
        return float(np.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2))

    def _build_summary(
        self, total, passed, lifetime, boundary, closure, turnover, interaction, interaction_score,
    ) -> str:
        """构建人类可读的验证摘要"""
        lines = [
            f"=== Structure Validation Report ===",
            f"Total structures: {total}",
            f"Passed (all criteria): {passed}/{total}",
            f"",
            f"Criterion breakdown:",
            f"  Lifetime          (>= {self.min_lifetime} steps): {lifetime}/{total}",
            f"  Boundary Stability (< {self.boundary_stability_threshold}): {boundary}/{total}",
            f"  Connectivity      (>= {self.connectivity_threshold}): {closure}/{total}",
            f"  Boundary Closure  (<= {self.boundary_closure_threshold}): {closure}/{total}",
            f"  Turnover          (< {self.max_turnover}): {turnover}/{total}",
            f"  Interaction (spatial proxy): {'detected' if interaction else 'none'} (score={interaction_score:.2f})",
        ]

        if passed == total and total > 0:
            lines.append(f"\n[PASS] All structures passed validation.")
        elif passed > 0:
            lines.append(f"\n[WARN] {total - passed} structures failed validation.")
        else:
            lines.append(f"\n[FAIL] No structures passed validation.")

        return "\n".join(lines)
