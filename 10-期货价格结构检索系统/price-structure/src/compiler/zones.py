"""
关键区识别 — 对极值点做 1D 价格聚类

修复：
1. 高低点用交替序列判定（不排除首尾）
2. 聚类用固定容差（避免动态中心漂移）

V1.6 P0 新增：
3. 共同反差推断 — V1.6 定义 2.2, 命题 2.3
   基于极值点的时序特征推断驱动聚簇的外部反差类型

V1.6 P1 增强（2026-04-24）：
4. 反差推断引入价格分位数 + 品种元数据 + 顺时序比较
   - 价格位置信号：Zone 在历史价格中的分位数
   - 品种特征信号：板块分类、典型波动率体制
   - 时序密集度信号：试探间隔的均匀性
   三路信号加权投票，替代原来的纯时序规则
"""

from __future__ import annotations
from src.models import Point, Zone, ZoneSource, ContrastType


def _classify_highs_lows(pivots: list[Point]) -> tuple[list[Point], list[Point]]:
    """
    把 pivot 分成高点与低点：
    - 交替序列中相邻点类型不同
    - 首点用与第二点的比较来定性
    """
    if len(pivots) < 2:
        return [], []

    highs, lows = [], []

    if pivots[0].x > pivots[1].x:
        highs.append(pivots[0])
        start_is_high = True
    else:
        lows.append(pivots[0])
        start_is_high = False

    is_high = not start_is_high
    for p in pivots[1:]:
        if is_high:
            highs.append(p)
        else:
            lows.append(p)
        is_high = not is_high

    return highs, lows


def _cluster_by_fixed_pct(
    points: list[Point],
    eps: float,
) -> list[list[Point]]:
    """
    基于"范围容差"的聚类，避免动态中心漂移。
    按价格排序后贪心合并：若新点与当前簇的价格范围差 <= eps*center，则合并。
    """
    if not points:
        return []
    sorted_pts = sorted(points, key=lambda p: p.x)
    clusters: list[list[Point]] = [[sorted_pts[0]]]

    for p in sorted_pts[1:]:
        last_cluster = clusters[-1]
        cmin = min(pt.x for pt in last_cluster)
        cmax = max(pt.x for pt in last_cluster)
        center = (cmin + cmax) / 2
        tol = center * eps
        if p.x - cmax <= tol:
            last_cluster.append(p)
        else:
            clusters.append([p])
    return clusters


def _infer_contrast(
    cluster: list[Point],
    bars: list | None = None,
    symbol: str | None = None,
) -> tuple[ContrastType, str]:
    """
    V1.6 定义 2.2: 共同反差推断 — 增强版 (2026-04-24)

    三路信号加权投票：
    1. 时序密集度信号（权重 0.40）— 原有逻辑
    2. 价格位置信号（权重 0.35）— Zone 在历史价格中的分位数
    3. 品种特征信号（权重 0.25）— 板块分类、波动率体制

    所有比较严格顺时序：只用 cluster 中最晚时间点之前的数据。

    Args:
        cluster: 聚簇的极值点列表
        bars: 历史 Bar 数据（用于计算价格分位数，可选）
        symbol: 品种代码（用于查元数据，可选）

    Returns:
        (ContrastType, 描述字符串)
    """
    if len(cluster) < 2:
        return ContrastType.UNKNOWN, ""

    # ── 信号 A: 时序密集度（权重 0.40）──
    times = sorted([p.t for p in cluster])
    total_span = (times[-1] - times[0]).days if len(times) >= 2 else 0
    n = len(cluster)

    if len(times) >= 2:
        gaps = [(times[i + 1] - times[i]).days for i in range(len(times) - 1)]
        avg_gap = sum(gaps) / len(gaps)
        gap_cv = (sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)) ** 0.5 / avg_gap if avg_gap > 0 else 0
    else:
        gaps = []
        avg_gap = 0
        gap_cv = 0

    votes: dict[str, float] = {}  # contrast_type_value → confidence

    # 密集爆发 → 恐慌
    if total_span < 30 and n >= 3:
        confidence = 0.40 * min(n / 5.0, 1.0)
        votes["panic"] = votes.get("panic", 0) + confidence
    # 长时间缓慢堆积 → 过剩
    elif total_span > 180:
        confidence = 0.40 * min(total_span / 365.0, 1.0)
        votes["oversupply"] = votes.get("oversupply", 0) + confidence
    # 中等时间、间隔均匀 → 政策
    elif 30 <= total_span <= 180 and n >= 3 and gap_cv < 0.5:
        votes["policy"] = votes.get("policy", 0) + 0.40 * (1.0 - gap_cv)
    # 中等时间、间隔不均匀 → 投机
    elif 30 <= total_span <= 180 and n >= 3 and gap_cv >= 0.5:
        votes["speculation"] = votes.get("speculation", 0) + 0.40 * 0.5

    # ── 信号 B: 价格位置（权重 0.35）──
    # 严格顺时序：只用 cluster 最晚时间点之前的数据
    if bars and len(cluster) >= 2:
        zone_center = sum(p.x for p in cluster) / len(cluster)
        as_of = max(p.t for p in cluster)  # 不看未来

        # 计算价格分位数（顺时序）
        usable_bars = [b for b in bars if b.timestamp <= as_of]
        if len(usable_bars) >= 20:
            closes = [b.close for b in usable_bars[-252:]]  # 最近 1 年
            n_bars = len(closes)
            below = sum(1 for c in closes if c < zone_center)
            pct = below / n_bars if n_bars > 0 else 0.5

            # 历史高位 + 密集试探 → 恐慌/过剩（价格在顶部反复试探）
            if pct > 0.80:
                if total_span < 60:
                    votes["panic"] = votes.get("panic", 0) + 0.35 * 0.8
                else:
                    votes["oversupply"] = votes.get("oversupply", 0) + 0.35 * 0.7
            # 历史低位 + 密集试探 → 过剩/恐慌（底部反复试探）
            elif pct < 0.20:
                if total_span < 60:
                    votes["panic"] = votes.get("panic", 0) + 0.35 * 0.6
                else:
                    votes["oversupply"] = votes.get("oversupply", 0) + 0.35 * 0.8
            # 中位 → 更可能是政策或流动性驱动
            elif 0.40 <= pct <= 0.60:
                votes["policy"] = votes.get("policy", 0) + 0.35 * 0.4
                votes["liquidity"] = votes.get("liquidity", 0) + 0.35 * 0.3
            # 偏高/偏低 → 投机或流动性
            else:
                votes["speculation"] = votes.get("speculation", 0) + 0.35 * 0.3
                votes["liquidity"] = votes.get("liquidity", 0) + 0.35 * 0.3

            # 波动率信号：高波动率环境下密集试探更可能是恐慌
            if len(usable_bars) >= 40:
                recent_rets = []
                for i in range(-20, 0):
                    if usable_bars[i - 1].close > 0:
                        recent_rets.append(
                            (usable_bars[i].close - usable_bars[i - 1].close) / usable_bars[i - 1].close
                        )
                if recent_rets:
                    mean_r = sum(recent_rets) / len(recent_rets)
                    vol = (sum((r - mean_r) ** 2 for r in recent_rets) / len(recent_rets)) ** 0.5
                    # 高波动率 + 历史高位 → 强化恐慌信号
                    if vol > 0.015 and pct > 0.75:
                        votes["panic"] = votes.get("panic", 0) + 0.35 * 0.3

    # ── 信号 C: 品种特征（权重 0.25）──
    if symbol:
        from src.data.symbol_meta import load_symbol_meta
        meta = load_symbol_meta().get(symbol.upper().replace("000", "0"), {})
        sector = meta.get("sector", "")
        vol_regime = meta.get("vol_regime", "medium")

        # 贵金属 + 历史高位 → 更可能是恐慌（避险情绪）
        if sector == "贵金属" and votes.get("panic", 0) > 0:
            votes["panic"] = votes.get("panic", 0) + 0.25 * 0.5
        # 黑色系/能化 + 长时间堆积 → 更可能是供需失衡
        elif sector in ("黑色系", "能化") and total_span > 120:
            votes["oversupply"] = votes.get("oversupply", 0) + 0.25 * 0.6
        # 农产品 + 中等时间 → 更可能是政策（收储、进口配额等）
        elif sector == "农产品" and 30 <= total_span <= 180:
            votes["policy"] = votes.get("policy", 0) + 0.25 * 0.5
        # 高波动率品种 + 密集试探 → 强化恐慌
        elif vol_regime == "high" and total_span < 30 and n >= 3:
            votes["panic"] = votes.get("panic", 0) + 0.25 * 0.6
        # 低波动率品种 + 长时间 → 强化过剩
        elif vol_regime == "low" and total_span > 180:
            votes["oversupply"] = votes.get("oversupply", 0) + 0.25 * 0.5
        # 有色金属 → 流动性驱动更常见
        elif sector == "有色金属":
            votes["liquidity"] = votes.get("liquidity", 0) + 0.25 * 0.4

    # ── 投票决定 ──
    if not votes:
        return ContrastType.UNKNOWN, ""

    # 找到最高票的反差类型
    best = max(votes, key=votes.get)
    confidence = votes[best]

    # 置信度太低 → 未知
    if confidence < 0.20:
        return ContrastType.UNKNOWN, ""

    type_map = {
        "panic": ContrastType.PANIC,
        "oversupply": ContrastType.OVERSUPPLY,
        "policy": ContrastType.POLICY,
        "liquidity": ContrastType.LIQUIDITY,
        "speculation": ContrastType.SPECULATION,
    }

    contrast_type = type_map.get(best, ContrastType.UNKNOWN)

    # 生成人可读描述
    label_parts = []
    label_parts.append(f"{n}次试探")
    if total_span > 0:
        label_parts.append(f"跨度{total_span}天")
    if bars and len(cluster) >= 2:
        zone_center = sum(p.x for p in cluster) / len(cluster)
        as_of = max(p.t for p in cluster)
        usable_bars = [b for b in bars if b.timestamp <= as_of]
        if len(usable_bars) >= 20:
            closes = [b.close for b in usable_bars[-252:]]
            pct = sum(1 for c in closes if c < zone_center) / len(closes) if closes else 0.5
            label_parts.append(f"价格分位{pct:.0%}")
    if symbol:
        from src.data.symbol_meta import load_symbol_meta
        meta = load_symbol_meta().get(symbol.upper().replace("000", "0"), {})
        sector = meta.get("sector", "")
        if sector:
            label_parts.append(f"板块:{sector}")

    label = "，".join(label_parts)

    return contrast_type, label


def detect_zones(
    pivots: list[Point],
    zone_bandwidth: float = 0.01,
    cluster_eps: float = 0.015,
    cluster_min_points: int = 2,
    bars: list | None = None,
    symbol: str | None = None,
) -> list[Zone]:
    """
    关键区识别

    Args:
        pivots: 极值点列表
        zone_bandwidth: Zone 带宽（相对比例）
        cluster_eps: 聚类容差（相对比例）
        cluster_min_points: 最小聚类点数
        bars: 历史 Bar 数据（用于增强反差推断，可选）
        symbol: 品种代码（用于查元数据，可选）

    Returns:
        Zone 列表，按强度降序排列
    """
    if len(pivots) < 2:
        return []

    highs, lows = _classify_highs_lows(pivots)

    def _build(points: list[Point], source: ZoneSource) -> list[Zone]:
        if not points:
            return []
        clusters = _cluster_by_fixed_pct(points, cluster_eps)
        zones: list[Zone] = []
        for cl in clusters:
            if len(cl) < cluster_min_points:
                continue
            center = sum(p.x for p in cl) / len(cl)
            bw = center * zone_bandwidth
            price_range = max(p.x for p in cl) - min(p.x for p in cl)
            compactness = 1.0 / (1.0 + price_range / center)
            strength = len(cl) * compactness

            # ── V1.6 P0+: 共同反差推断（增强版）──
            contrast_type, contrast_label = _infer_contrast(cl, bars=bars, symbol=symbol)

            zones.append(Zone(
                price_center=center,
                bandwidth=bw,
                source=source,
                strength=strength,
                touches=list(cl),
                context_contrast=contrast_type,
                contrast_label=contrast_label,
            ))
        return zones

    zones: list[Zone] = []
    zones.extend(_build(highs, ZoneSource.HIGH_CLUSTER))
    zones.extend(_build(lows, ZoneSource.LOW_CLUSTER))
    zones.sort(key=lambda z: z.strength, reverse=True)
    return zones
