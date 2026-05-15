"""
结构自动发现 — 从不变量空间中用聚类发现新结构类型

P2-8: 对应"自指 + 先天完备"机制。
从历史样本的不变量向量中，用 HDBSCAN 发现自然聚类，
自动生成候选规则，人工审核后加入规则集。

设计原则：
1. 只发现，不自动生效 — 输出候选规则供人工审核
2. 不变量空间维度固定（当前 10 维）— 可用 FAISS 加速
3. 与现有规则兼容 — 候选规则不覆盖已有规则
4. 幂等 — 同样输入产生同样候选

用法:
    from src.structure_discovery import discover_structure_types
    candidates = discover_structure_types(structures, existing_rules)
    for c in candidates:
        print(c['name'], c['description'], c['member_count'])
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ─── 不变量向量键 ──────────────────────────────────────────

INVARIANT_KEYS = [
    "cycle_count",
    "avg_speed_ratio",
    "avg_log_speed_ratio",
    "avg_time_ratio",
    "high_dispersion",
    "low_dispersion",
    "high_trend",
    "low_trend",
    "zone_rel_bw",
    "zone_strength",
]

INVARIANT_SCALES = {
    "cycle_count": 10.0,
    "avg_speed_ratio": 2.0,
    "avg_log_speed_ratio": 2.0,
    "avg_time_ratio": 2.0,
    "high_dispersion": 1.0,
    "low_dispersion": 1.0,
    "high_trend": 1.0,
    "low_trend": 1.0,
    "zone_rel_bw": 1.0,
    "zone_strength": 10.0,
}


def _normalized_vector(inv: dict) -> list[float]:
    """从 invariants dict 提取归一化向量"""
    return [
        (inv.get(k, 0) or 0) / INVARIANT_SCALES[k]
        for k in INVARIANT_KEYS
    ]


def _simple_kmeans(
    vectors: list[list[float]],
    k: int,
    max_iter: int = 50,
    seed: int = 42,
) -> tuple[list[int], list[list[float]]]:
    """
    简易 K-Means — 不引入 sklearn 依赖

    返回: (labels, centroids)
    """
    import random
    rng = random.Random(seed)
    n = len(vectors)
    dim = len(vectors[0]) if vectors else 0
    if n == 0 or dim == 0 or k <= 0:
        return [], []

    k = min(k, n)

    # 随机初始化
    indices = rng.sample(range(n), k)
    centroids = [vectors[i][:] for i in indices]

    labels = [0] * n

    for _ in range(max_iter):
        # 分配
        new_labels = []
        for v in vectors:
            best_c = 0
            best_d = float("inf")
            for ci, c in enumerate(centroids):
                d = sum((a - b) ** 2 for a, b in zip(v, c))
                if d < best_d:
                    best_d = d
                    best_c = ci
            new_labels.append(best_c)

        # 检查收敛
        if new_labels == labels:
            break
        labels = new_labels

        # 更新质心
        for ci in range(k):
            members = [vectors[i] for i in range(n) if labels[i] == ci]
            if not members:
                continue
            centroids[ci] = [
                sum(m[d] for m in members) / len(members)
                for d in range(dim)
            ]

    return labels, centroids


def _describe_cluster(
    members_invariants: list[dict],
    cluster_id: int,
) -> dict[str, Any]:
    """
    从聚类成员的不变量统计中生成规则描述

    返回候选规则定义（YAML 兼容格式）
    """
    if not members_invariants:
        return {}

    # 统计每个不变量的范围
    stats = {}
    for key in INVARIANT_KEYS:
        vals = [inv.get(key, 0) or 0 for inv in members_invariants]
        if not vals:
            continue
        lo, hi = min(vals), max(vals)
        mean = sum(vals) / len(vals)
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals)) if len(vals) > 1 else 0
        stats[key] = {"lo": lo, "hi": hi, "mean": mean, "std": std}

    # 生成约束条件（用 1σ 范围作为区间）
    constraints = {}
    readable_parts = []

    # cycle_count
    cc_stat = stats.get("cycle_count", {})
    if cc_stat:
        cc_lo = max(2, round(cc_stat["mean"] - cc_stat["std"]))
        cc_hi = round(cc_stat["mean"] + cc_stat["std"])
        constraints["cycles"] = {"gte": cc_lo}
        readable_parts.append(f"cycle数 {cc_lo}~{cc_hi}")

    # speed_ratio
    sr_stat = stats.get("avg_speed_ratio", {})
    if sr_stat:
        sr_mean = sr_stat["mean"]
        sr_std = sr_stat["std"]
        if sr_mean > 1.3:
            constraints["speed_ratio"] = {"gt": round(max(1.0, sr_mean - sr_std), 2)}
            readable_parts.append("速度比偏高(快进慢出)")
        elif sr_mean < 0.7:
            constraints["speed_ratio"] = {"lt": round(min(1.0, sr_mean + sr_std), 2)}
            readable_parts.append("速度比偏低(慢进快出)")
        else:
            sr_lo = round(max(0.5, sr_mean - sr_std), 2)
            sr_hi = round(min(1.5, sr_mean + sr_std), 2)
            constraints["speed_ratio"] = {"between": [sr_lo, sr_hi]}
            readable_parts.append("速度比均衡")

    # time_ratio
    tr_stat = stats.get("avg_time_ratio", {})
    if tr_stat:
        tr_mean = tr_stat["mean"]
        tr_std = tr_stat["std"]
        if tr_mean > 1.5:
            constraints["time_ratio"] = {"gt": round(max(1.0, tr_mean - tr_std), 2)}
            readable_parts.append("时间比偏高(长驻)")
        elif tr_mean < 0.7:
            constraints["time_ratio"] = {"lt": round(min(1.0, tr_mean + tr_std), 2)}
            readable_parts.append("时间比偏低(快速通过)")
        else:
            tr_lo = round(max(0.5, tr_mean - tr_std), 2)
            tr_hi = round(min(1.5, tr_mean + tr_std), 2)
            constraints["time_ratio"] = {"between": [tr_lo, tr_hi]}
            readable_parts.append("时间比均衡")

    # 生成名称和描述
    name = f"AutoCluster_{cluster_id}"
    description = "自动发现：".join(readable_parts) if readable_parts else "自动发现的结构聚类"

    return {
        "name": name,
        "description": description,
        "member_count": len(members_invariants),
        "constraints": constraints,
        "centroid_stats": {k: round(v["mean"], 3) for k, v in stats.items()},
    }


def discover_structure_types(
    structures: list,
    n_clusters: int = 6,
    existing_rule_names: set[str] | None = None,
    min_cluster_size: int = 2,
) -> list[dict[str, Any]]:
    """
    从不变量空间中发现新结构类型

    Args:
        structures: Structure 列表
        n_clusters: 目标聚类数
        existing_rule_names: 已有规则名集合（避免重复）
        min_cluster_size: 最小聚类成员数

    Returns:
        候选规则列表，每项含 name/description/constraints/member_count
    """
    from src.relations import structure_invariants

    if not structures:
        return []

    # 提取不变量向量
    inv_list = []
    vec_list = []
    for s in structures:
        inv = structure_invariants(s)
        inv_list.append(inv)
        vec_list.append(_normalized_vector(inv))

    if len(vec_list) < n_clusters:
        n_clusters = max(1, len(vec_list) // 2)

    # 聚类
    labels, centroids = _simple_kmeans(vec_list, n_clusters)

    # 生成候选规则
    candidates = []
    for ci in range(n_clusters):
        members = [inv_list[i] for i in range(len(labels)) if labels[i] == ci]
        if len(members) < min_cluster_size:
            continue

        candidate = _describe_cluster(members, ci)

        # 检查是否与现有规则重叠
        if existing_rule_names and candidate.get("name") in existing_rule_names:
            continue

        if candidate:
            candidates.append(candidate)

    # 按成员数降序排列
    candidates.sort(key=lambda c: c.get("member_count", 0), reverse=True)

    return candidates
