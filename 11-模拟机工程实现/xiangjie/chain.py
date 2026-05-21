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
    门槛：边界不仅是被动分隔，而是选择性中介——调控什么流入流出。

    理论依据（Appearing Before Appearing Section 3.1 + 象界第二章）：
      界面 = 边界从被动分隔变为功能界面——选择性中介。
      A1（局域性）+ A4（最小变易）→ 开放环境下纯被动分隔不稳定
      （梯度抹平差异），纯封闭则断绝输入。界面是"调控的开口"，不是墙。

    三维检测（v2 重设计）：
      1. 选择性渗透（selective permeability）：
         边界对状态的不同维度有不同的通透性——某些维度被过滤，某些通过。
         判据：边界像素上各维度的方差存在显著差异（不是均匀透过或均匀阻挡）。
      2. 方向不对称（directional asymmetry）：
         外→内梯度 ≠ 内→外梯度 → 边界对流入流出区别对待。
      3. 时间调控（temporal regulation，需要 history）：
         边界状态与外部扰动相关，但与内部变化部分解耦 → 边界在主动缓冲外部冲击。

    降级策略：
      - 有 state 但无 history：仅检测选择性渗透 + 方向不对称
      - 无 state：降级为旧版几何代理
    """

    name = "界面"
    stage = "II"
    threshold = 0.20  # 综合中介得分 ≥ 0.20 → 通过（v2 提升，因检测更严格）

    def evaluate(self, struct: StableStructure,
                 state: Optional[torch.Tensor] = None,
                 history: Optional[List[torch.Tensor]] = None) -> ThresholdReport:
        # ---- 降级：无 state 时用几何代理 ----
        if state is None or state.numel() == 0:
            mask = struct.mask.float().unsqueeze(0).unsqueeze(0)
            kernel = torch.ones(1, 1, 3, 3, device=mask.device)
            boundary_expanded = F.conv2d(mask, kernel, padding=1) > 0
            boundary_area = int(boundary_expanded.sum().item())
            area = int(struct.mask.sum().item())
            geometric_proxy = boundary_area / max(1, area)
            score = min(1.0, geometric_proxy)
            passed = score >= self.threshold
            return ThresholdReport(
                name=self.name, stage=self.stage,
                passed=passed, score=score,
                threshold=self.threshold,
                detail=f"[降级] 几何代理 {geometric_proxy:.3f} → "
                       f"{'通过' if passed else '未通过'}",
                meta={"mode": "geometric_proxy", "gradient": geometric_proxy}
            )

        # ---- 提取空间区域 ----
        # state: (B,C,H,W) 或 (H,W)
        s = state.squeeze()  # 去掉 batch 维
        if s.dim() < 2:
            return ThresholdReport(
                name=self.name, stage=self.stage,
                passed=False, score=0.0,
                threshold=self.threshold,
                detail="状态维度不足",
                meta={"mode": "error"}
            )

        # 确保维度对齐：s 应为 (C,H,W) 或 (H,W)
        if s.dim() == 3:
            n_channels = s.shape[0]
        else:
            n_channels = 1
            s = s.unsqueeze(0)

        mask_bool = struct.mask.bool()
        boundary_bool = struct.boundary_map.bool()

        # 外部区域：结构膨胀 1px 后不属于结构的部分
        mask_f = struct.mask.float().unsqueeze(0).unsqueeze(0)
        kernel = torch.ones(1, 1, 3, 3, device=mask_f.device)
        dilated = F.conv2d(mask_f, kernel, padding=1) > 0
        exterior_bool = dilated.squeeze() & ~mask_bool
        interior_bool = mask_bool & ~boundary_bool  # 内部 = 结构 - 边界

        # ---- 维度 1：选择性渗透 ----
        # 在边界像素上，各通道的方差是否显著不同
        # 如果边界对所有通道同等通透或同等阻挡，则各通道方差相近
        # 如果边界选择性过滤，则各通道方差差异大
        permeability_score = 0.0
        if n_channels >= 2 and boundary_bool.sum() > 0:
            # 边界像素上各通道的方差
            channel_variances = []
            for c in range(n_channels):
                vals = s[c][boundary_bool]
                if vals.numel() > 1:
                    channel_variances.append(vals.var().item())
                else:
                    channel_variances.append(0.0)
            if len(channel_variances) >= 2:
                var_arr = np.array(channel_variances, dtype=np.float64)
                max_var = var_arr.max()
                if max_var > 1e-12:
                    # 选择性 = 各通道方差的变异系数（CV）
                    # CV 高 → 有些通道方差大（被渗透），有些小（被阻挡）→ 选择性中介
                    cv = var_arr.std() / max_var
                    permeability_score = min(1.0, cv * 2.0)  # 缩放到 [0,1]
        else:
            # 单通道：用边界值方差与内部值方差的比值作为代理
            # 如果边界方差 < 内部方差 → 边界在过滤高频变化（选择性阻挡）
            if boundary_bool.sum() > 0 and interior_bool.sum() > 0:
                boundary_var = s[0][boundary_bool].var().item()
                interior_var = s[0][interior_bool].var().item()
                if interior_var > 1e-12:
                    # 边界方差/内部方差 < 1 → 边界在平滑/过滤
                    ratio = boundary_var / interior_var
                    # 选择性：比值远离 1（太接近 1 说明无选择性）
                    permeability_score = 1.0 - min(1.0, abs(ratio - 1.0))
                    # 但我们需要区分：ratio < 1 是过滤（好），ratio > 1 是放大（也有选择性）
                    # 重新设计：选择性 = |1 - ratio|，越偏离 1 越有选择性
                    permeability_score = min(1.0, abs(1.0 - ratio) * 2.0)

        # ---- 维度 2：方向不对称 ----
        # 外→内梯度 vs 内→外梯度
        # 如果边界是选择性中介，流入和流出的梯度应该不同
        asymmetry_score = 0.0
        if (boundary_bool.sum() > 0 and exterior_bool.sum() > 0
                and interior_bool.sum() > 0):
            # 对每个通道计算
            asym_per_channel = []
            for c in range(n_channels):
                boundary_mean = s[c][boundary_bool].mean().item()
                exterior_mean = s[c][exterior_bool].mean().item()
                interior_mean = s[c][interior_bool].mean().item()
                # 外→内梯度
                grad_in = boundary_mean - exterior_mean
                # 内→外梯度（符号相反方向）
                grad_out = boundary_mean - interior_mean
                # 不对称性 = 两个梯度的差异
                # 如果 |grad_in| ≠ |grad_out|，边界在区别对待
                denom = max(abs(grad_in) + abs(grad_out), 1e-12)
                asym = abs(grad_in - grad_out) / denom
                asym_per_channel.append(min(1.0, asym))
            if asym_per_channel:
                asymmetry_score = float(np.mean(asym_per_channel))

        # ---- 维度 3：时间调控（需要 history） ----
        temporal_score = 0.0
        temporal_detail = ""
        if (history is not None and len(history) >= 4
                and boundary_bool.sum() > 0
                and interior_bool.sum() > 0):
            # 检测：边界状态变化与外部变化的关联性
            # 是否强于与内部变化的关联性？
            # 如果是 → 边界在主动响应外部变化，缓冲内部
            window = history[-8:]
            boundary_series = []
            interior_series = []
            exterior_series = []

            for h in window:
                h_s = h.squeeze()
                if h_s.dim() < 2:
                    continue
                if h_s.dim() == 2:
                    h_s = h_s.unsqueeze(0)
                # 取第一个通道
                c0 = h_s[0] if h_s.shape[0] <= h_s.shape[-1] else h_s[:, :, 0]
                # shape 对齐
                if c0.shape != mask_bool.shape:
                    continue
                if boundary_bool.sum() > 0:
                    boundary_series.append(c0[boundary_bool].mean().item())
                if interior_bool.sum() > 0:
                    interior_series.append(c0[interior_bool].mean().item())
                if exterior_bool.sum() > 0:
                    exterior_series.append(c0[exterior_bool].mean().item())

            if (len(boundary_series) >= 4 and len(exterior_series) >= 4
                    and len(interior_series) >= 4):
                b_arr = np.array(boundary_series, dtype=np.float64)
                e_arr = np.array(exterior_series, dtype=np.float64)
                i_arr = np.array(interior_series, dtype=np.float64)

                # 边界-外部相关性
                if b_arr.std() > 1e-12 and e_arr.std() > 1e-12:
                    corr_be = float(np.corrcoef(b_arr, e_arr)[0, 1])
                    if np.isnan(corr_be):
                        corr_be = 0.0
                else:
                    corr_be = 0.0

                # 边界-内部相关性
                if b_arr.std() > 1e-12 and i_arr.std() > 1e-12:
                    corr_bi = float(np.corrcoef(b_arr, i_arr)[0, 1])
                    if np.isnan(corr_bi):
                        corr_bi = 0.0
                else:
                    corr_bi = 0.0

                # 时间调控：边界与外部强相关 + 与内部弱相关
                # = 边界在主动跟随外部，同时缓冲内部
                # 理想情况：corr_be > 0.5 且 corr_bi < corr_be
                if corr_be > 0:
                    temporal_score = max(0.0, corr_be - corr_bi) * 0.5
                    temporal_score = min(1.0, temporal_score)
                temporal_detail = (
                    f"corr(边界,外部)={corr_be:.3f}, "
                    f"corr(边界,内部)={corr_bi:.3f}"
                )
            else:
                temporal_detail = "历史序列不足4步"
        else:
            temporal_detail = "无历史数据"

        # ---- 综合中介得分 ----
        if history is not None and len(history) >= 4 and temporal_score > 0:
            # 有时间调控数据：三维综合
            # 权重：选择性渗透 0.35 + 方向不对称 0.35 + 时间调控 0.30
            score = (0.35 * permeability_score
                     + 0.35 * asymmetry_score
                     + 0.30 * temporal_score)
            mode = "full"
        else:
            # 仅有空间数据：二维综合
            # 权重：选择性渗透 0.50 + 方向不对称 0.50
            score = 0.50 * permeability_score + 0.50 * asymmetry_score
            mode = "spatial"

        score = max(0.0, min(1.0, score))
        passed = score >= self.threshold
        detail = (
            f"[{mode}] 渗透={permeability_score:.3f}, "
            f"不对称={asymmetry_score:.3f}, "
            f"调控={temporal_score:.3f}"
            f"{' (' + temporal_detail + ')' if temporal_detail else ''} → "
            f"综合={score:.3f} → "
            f"{'通过' if passed else '未通过'}"
        )
        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=score,
            threshold=self.threshold, detail=detail,
            meta={
                "mode": mode,
                "permeability_score": permeability_score,
                "asymmetry_score": asymmetry_score,
                "temporal_score": temporal_score,
                "gradient": score,  # 兼容旧接口
            }
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
    门槛：结构不仅持续存在，而且过去的状态路径对当前状态形成偏置约束。

    理论依据（象界.md 第四章）：
      记忆 ≠ 储存（静态积压），记忆 = 过去对未来施加的偏向性约束。
      核心判据是「路径偏置」——过去经历的差异关系使当前构型偏离无历史基线。
      用偏置算子 B_ω 的语言：记忆 = 同一结构内不同历史路径留下的可区分偏置。

    工程实现：
      1. lifetime 仍是必要前提（不持续的结构不可能有记忆）
      2. 新增路径偏置检测：
         - autocorrelation：最近N步 pattern_signature 的自相关性，
           高自相关 = 过去状态约束当前状态（偏置存在）
         - convergence：pattern_signature 方差在时间上递减，
           递减 = 结构被历史「锁定」在特定构型附近（偏置生效）
      3. 无 history 时降级为纯 lifetime 判断（兼容旧调用方式）
    """

    name = "记忆"
    stage = "IV"
    LIFETIME_MIN = 16        # 存活步数下限（必要前提）
    BIAS_THRESHOLD = 0.50   # 路径偏置得分阈值 [0, 1]
    AUTOCORR_WINDOW = 8     # 自相关检测窗口长度

    def evaluate(self, struct: StableStructure,
                 history: Optional[List[torch.Tensor]] = None) -> ThresholdReport:
        lifetime = struct.lifetime

        # ---- 必要前提：lifetime 不够则不可能有记忆 ----
        lifetime_ok = lifetime >= self.LIFETIME_MIN
        lifetime_score = min(1.0, lifetime / (self.LIFETIME_MIN * 2))

        # ---- 路径偏置检测 ----
        bias_score = 0.0
        bias_detail = ""

        if history is not None and len(history) >= 4:
            # 取最近 AUTOCORR_WINDOW 步（或全部可用步）
            window = history[-self.AUTOCORR_WINDOW:]
            mask_bool = struct.mask.bool()

            # 提取每步中结构区域的 pattern 均值序列
            pattern_means = []
            for h in window:
                # 适配各种 shape: (B,C,H,W) / (H,W) / ...
                h_squeezed = h.squeeze()
                if h_squeezed.shape == mask_bool.shape:
                    vals = h_squeezed[mask_bool]
                elif h_squeezed.numel() >= mask_bool.sum().item():
                    # shape 不匹配但元素足够，取前 N 个
                    vals = h_squeezed.flatten()[:mask_bool.sum().item()]
                else:
                    vals = h_squeezed.flatten()
                pattern_means.append(vals.mean().item() if vals.numel() > 0 else 0.0)

            if len(pattern_means) >= 4:
                arr = np.array(pattern_means, dtype=np.float64)

                # (a) 自相关性：lag-1 自相关 → 过去状态约束当前状态
                if arr.std() > 1e-12:
                    autocorr = float(np.corrcoef(arr[:-1], arr[1:])[0, 1])
                    # nan 保护（常量序列）
                    if np.isnan(autocorr):
                        autocorr = 0.0
                else:
                    autocorr = 0.0

                # (b) 收敛性：前半方差 vs 后半方差的递减比
                mid = len(arr) // 2
                var_first = max(arr[:mid].var(), 1e-12)
                var_second = max(arr[mid:].var(), 1e-12)
                convergence = 1.0 - min(1.0, var_second / var_first)
                # convergence > 0 → 后半方差更小 → 被历史锁定的偏置生效

                # 综合：自相关权重 0.6（直接证据），收敛权重 0.4（辅助证据）
                bias_score = 0.6 * max(0.0, autocorr) + 0.4 * convergence
                bias_score = max(0.0, min(1.0, bias_score))

                bias_detail = (
                    f"自相关={autocorr:.3f}, 收敛={convergence:.3f}, "
                    f"偏置={bias_score:.3f}"
                )
            else:
                bias_detail = "历史步数不足4，无法计算偏置"
        else:
            bias_detail = "无历史数据，降级为lifetime判断"

        # ---- 综合判定 ----
        # lifetime 是必要前提，偏置是充分条件
        # 总得分 = lifetime_score * 0.3 + bias_score * 0.7
        # （偏置权重更高，因为它是记忆本质的直接检测）
        if history is not None and len(history) >= 4 and bias_detail != "历史步数不足4，无法计算偏置":
            total_score = lifetime_score * 0.3 + bias_score * 0.7
            passed = lifetime_ok and bias_score >= self.BIAS_THRESHOLD
        else:
            # 降级模式：纯 lifetime 判断（兼容旧调用）
            total_score = lifetime_score
            passed = lifetime_ok

        detail = (
            f"lifetime={lifetime}(阈值{self.LIFETIME_MIN}), "
            f"{bias_detail} → "
            f"总得分={total_score:.3f}, "
            f"{'通过' if passed else '未通过'}"
        )

        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=total_score,
            threshold=self.BIAS_THRESHOLD, detail=detail,
            meta={
                "lifetime": lifetime,
                "lifetime_ok": lifetime_ok,
                "bias_score": bias_score,
                "bias_detail": bias_detail,
            }
        )


class ReplicationGate:
    """
    【第五章：复制】
    门槛：结构的关系样式在历史中跨次延续——模板效应，而非机械重现。

    理论依据（Appearing Before Appearing Section 3.4 + 象界第五章）：
      复制 = 关系样式的跨次延续。核心不是状态值的精确重复，而是
      **关键关系特征的结构连续性**——即便个体比特的值变化了，
      整体关系模式（谁与谁强相关、谁与谁反相关）仍能跨时间重建。
      模板效应：过去构型为当前构型提供了重建模板——不是复制品，
      而是偏置方向的来源。

      复制与记忆的区别：记忆是同一结构内部的路径偏置，
      复制是关系样式跨多个独立涌现周期的延续。
      复制不要求完美保真（只要求关键关系特征的结构连续性），
      不要求专用复制机制，不要求离散个体单元。

    工程实现（v2 重设计）：
      三维检测替代旧的均值比较：
      1. 结构相似度（structural similarity）：
         不仅比较均值，还比较方差和协方差——捕捉关系结构而不仅是数值水平。
         使用简化版 SSIM 思想：luminance * contrast * structure。
      2. 模板效应（template effect）：
         历史中是否存在反复出现的结构模式（不止一次），
         且其关系特征保持稳定——用 pattern_signature 的自聚类检测。
      3. 条件独立性（conditional independence，需要多周期 history）：
         模式是否能在不同条件下重建自身——在不同时间窗口中是否
         出现结构相似的构型。降级为单周期时跳过此维。
    """

    name = "复制"
    stage = "V"
    threshold = 0.45  # v2：综合复制得分 ≥ 0.45 → 通过（因检测更严格，阈值下调）

    def evaluate(self, struct: StableStructure,
                 history: Optional[List[torch.Tensor]] = None) -> ThresholdReport:
        pattern = struct.pattern_signature
        mask_bool = struct.mask.bool()

        # ---- 降级：无 history ----
        if history is None or len(history) < 4:
            # 仅用 pattern_signature 的内部稳定性代理
            if pattern.numel() > 1:
                cv = float(pattern.std().item() / max(pattern.mean().item(), 1e-12))
                consistency = max(0.0, 1.0 - min(1.0, cv))
            else:
                consistency = 0.0
            score = consistency
            passed = score >= self.threshold
            return ThresholdReport(
                name=self.name, stage=self.stage,
                passed=passed, score=score,
                threshold=self.threshold,
                detail=f"[降级] 无历史, 内部稳定性={consistency:.3f} → "
                       f"{'通过' if passed else '未通过'}",
                meta={"mode": "degraded", "consistency": consistency}
            )

        # ---- 维度 1：结构相似度 ----
        # 在历史窗口中，提取结构区域的 (均值, 方差) 对，计算 SSIM-like 指标
        recent = history[-8:]
        struct_mean = pattern.mean().item()
        struct_var = pattern.var().item() if pattern.numel() > 1 else 0.0

        similarity_scores = []
        for h in recent:
            h_s = h.squeeze()
            # shape 对齐
            while h_s.dim() > mask_bool.dim():
                h_s = h_s.squeeze(0)
            if h_s.dim() > mask_bool.dim():
                h_s = h_s.reshape(mask_bool.shape)
            if h_s.shape != mask_bool.shape:
                h_flat = h_s.flatten()
                n = min(h_flat.numel(), mask_bool.sum().item())
                h_masked = h_flat[:n]
            else:
                h_masked = h_s[mask_bool]

            if h_masked.numel() == 0:
                continue

            h_mean = h_masked.mean().item()
            h_var = h_masked.var().item() if h_masked.numel() > 1 else 0.0

            # 亮度相似度（均值接近程度）
            C1 = 0.01 ** 2  # 稳定常数
            luminance = (2 * struct_mean * h_mean + C1) / (
                struct_mean ** 2 + h_mean ** 2 + C1
            )

            # 对比度相似度（方差接近程度）
            C2 = 0.03 ** 2
            contrast = (2 * struct_var * h_var + C2) / (
                struct_var ** 2 + h_var ** 2 + C2
            )

            # 结构相似度 = luminance * contrast
            ss = luminance * contrast
            similarity_scores.append(max(0.0, min(1.0, ss)))

        if similarity_scores:
            # 取最高的几个（允许部分时间步不匹配——复制不需要每次都出现）
            similarity_scores.sort(reverse=True)
            top_k = max(1, len(similarity_scores) // 2)
            structural_similarity = float(np.mean(similarity_scores[:top_k]))
        else:
            structural_similarity = 0.0

        # ---- 维度 2：模板效应 ----
        # pattern_signature 在历史中的自聚类：是否有多次出现的相似模式
        # 用 K-means（k=2）检测是否有一个聚类包含 > 60% 的点
        # 简化版：用 pattern 均值序列的双峰性检测
        pattern_series = []
        for h in recent:
            h_s = h.squeeze()
            while h_s.dim() > mask_bool.dim():
                h_s = h_s.squeeze(0)
            if h_s.dim() > mask_bool.dim():
                h_s = h_s.reshape(mask_bool.shape)
            if h_s.shape != mask_bool.shape:
                h_flat = h_s.flatten()
                n = min(h_flat.numel(), mask_bool.sum().item())
                vals = h_flat[:n]
            else:
                vals = h_s[mask_bool]
            if vals.numel() > 0:
                pattern_series.append(vals.mean().item())

        template_score = 0.0
        if len(pattern_series) >= 4:
            arr = np.array(pattern_series, dtype=np.float64)
            arr_mean = arr.mean()
            arr_std = arr.std()
            if arr_std > 1e-12:
                # 检测：值是否反复回到 pattern_mean 附近
                # 「回到」= 距离 pattern_mean < 0.5*std 的比例
                dists = np.abs(arr - struct_mean)
                close_ratio = float(np.mean(dists < 0.5 * max(arr_std, abs(struct_mean) * 0.1 + 1e-12)))
                # 反复回到 = 至少出现过 2 次「接近」
                n_close = int(np.sum(dists < 0.5 * max(arr_std, abs(struct_mean) * 0.1 + 1e-12)))
                if n_close >= 2:
                    template_score = min(1.0, close_ratio * 1.5)
                else:
                    template_score = 0.0

        # ---- 维度 3：条件独立性 ----
        # 将历史分为前后两半，分别检测结构相似度
        # 如果两半都出现相似模式 → 模式在不同条件下都能重建
        conditional_score = 0.0
        if len(recent) >= 6:
            mid = len(recent) // 2
            first_half = recent[:mid]
            second_half = recent[mid:]

            def _mean_similarity(half):
                sims = []
                for h in half:
                    h_s = h.squeeze()
                    while h_s.dim() > mask_bool.dim():
                        h_s = h_s.squeeze(0)
                    if h_s.dim() > mask_bool.dim():
                        h_s = h_s.reshape(mask_bool.shape)
                    if h_s.shape != mask_bool.shape:
                        h_flat = h_s.flatten()
                        n = min(h_flat.numel(), mask_bool.sum().item())
                        vals = h_flat[:n]
                    else:
                        vals = h_s[mask_bool]
                    if vals.numel() > 0:
                        sims.append(1.0 - min(1.0, abs(vals.mean().item() - struct_mean) / max(abs(struct_mean), 1e-12)))
                return float(np.mean(sims)) if sims else 0.0

            sim_first = _mean_similarity(first_half)
            sim_second = _mean_similarity(second_half)
            # 条件独立性：两个半段都有合理相似度 → 模式跨条件延续
            conditional_score = min(sim_first, sim_second)  # 取弱者
        else:
            conditional_score = 0.0  # 数据不足，跳过

        # ---- 综合复制得分 ----
        # 权重：结构相似度 0.40 + 模板效应 0.35 + 条件独立性 0.25
        if len(recent) >= 6 and conditional_score > 0:
            score = (0.40 * structural_similarity
                     + 0.35 * template_score
                     + 0.25 * conditional_score)
            mode = "full"
        else:
            # 数据不足条件独立性：只用前两维
            score = (0.55 * structural_similarity
                     + 0.45 * template_score)
            mode = "partial"

        score = max(0.0, min(1.0, score))
        passed = score >= self.threshold
        detail = (
            f"[{mode}] 结构相似={structural_similarity:.3f}, "
            f"模板={template_score:.3f}, "
            f"条件独立={conditional_score:.3f} → "
            f"综合={score:.3f} → "
            f"{'通过' if passed else '未通过'}"
        )
        return ThresholdReport(
            name=self.name, stage=self.stage,
            passed=passed, score=score,
            threshold=self.threshold, detail=detail,
            meta={
                "mode": mode,
                "structural_similarity": structural_similarity,
                "template_score": template_score,
                "conditional_score": conditional_score,
                "consistency": score,  # 兼容旧接口
            }
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
                    r = gate.evaluate(struct, current_state, history)
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
                    r = gate.evaluate(struct, history)  # v2: 传入 history 以启用路径偏置检测
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