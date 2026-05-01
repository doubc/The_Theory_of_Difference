"""
丛 (Bundle) 识别 — 共享生成约束的结构聚合
"""

from __future__ import annotations

from src.models import Structure, Bundle


def detect_bundles(
    structures: list[Structure],
    speed_tol: float = 0.4,
    time_tol: float = 0.5,
) -> list[Bundle]:
    """
    丛 = 共享生成约束的多个 Structure 的集合。

    判定规则：
    1. 速度比相近（反映同一类信息传播效率）
    2. 时间比相近（反映同一类节奏模式）

    丛的类型：
    - "slow_up_fast_down": 慢涨急跌类（speed_ratio > 1, entry慢 exit快）
    - "fast_up_slow_down": 急涨慢跌类（speed_ratio < 1, entry快 exit慢）
    - "balanced": 均衡类（speed_ratio ≈ 1）
    - "mixed": 混合类（不满足以上特征）
    """
    if len(structures) < 2:
        return []

    # 第一步：对每个结构分类
    classified: list[tuple[Structure, str]] = []
    for st in structures:
        sr = st.avg_speed_ratio
        tr = st.avg_time_ratio

        if sr > 1.5 and tr > 1.5:
            bundle_type = "slow_up_fast_down"
        elif sr < 0.67 and tr < 0.67:
            bundle_type = "fast_up_slow_down"
        elif 0.7 < sr < 1.4 and 0.7 < tr < 1.4:
            bundle_type = "balanced"
        else:
            bundle_type = "mixed"

        classified.append((st, bundle_type))

    # 第二步：按类型分组
    type_groups: dict[str, list[Structure]] = {}
    for st, btype in classified:
        type_groups.setdefault(btype, []).append(st)

    # 第三步：在每组内按速度比/时间比进一步聚类
    bundles: list[Bundle] = []
    for btype, group in type_groups.items():
        if len(group) < 2:
            bundles.append(Bundle(
                structures=group,
                generator_constraint=f"type={btype}, single structure",
            ))
            continue

        group.sort(key=lambda s: s.avg_speed_ratio)
        clusters: list[list[Structure]] = [[group[0]]]

        for st in group[1:]:
            ref = clusters[-1][0]
            sr_diff = abs(st.avg_speed_ratio - ref.avg_speed_ratio) / max(ref.avg_speed_ratio, 0.01)
            tr_diff = abs(st.avg_time_ratio - ref.avg_time_ratio) / max(ref.avg_time_ratio, 0.01)

            if sr_diff <= speed_tol and tr_diff <= time_tol:
                clusters[-1].append(st)
            else:
                clusters.append([st])

        for cluster in clusters:
            avg_sr = sum(s.avg_speed_ratio for s in cluster) / len(cluster)
            avg_tr = sum(s.avg_time_ratio for s in cluster) / len(cluster)
            constraint = (
                f"type={btype}, "
                f"speed_ratio≈{avg_sr:.2f}, "
                f"time_ratio≈{avg_tr:.2f}, "
                f"n={len(cluster)}"
            )
            bundles.append(Bundle(
                structures=cluster,
                generator_constraint=constraint,
            ))

    bundles.sort(key=lambda b: len(b.structures), reverse=True)
    return bundles
