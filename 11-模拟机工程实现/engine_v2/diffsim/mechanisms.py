"""mechanisms.py — 九机制闭环生成链。

理论来源: 《差异即世界》第三章 — 世界生成的中层语法。

九个机制不是九个独立齿轮, 而是一条有严格顺序的生成链:
    聚簇 → 层级 → 守恒 → 先天完备性 → 最小变易 → 破缺 → 循环 → 锁定 → 自指
每一环以前一环为条件, 同时为后一环开辟可能。

★ 闭环: 自指(m9) 生成下一层的差异源, 使下一层的聚簇(m1)重新启动。
   m9 的输出 = 下一层 DifferenceField = 下一层 m1 的输入。
   九机制咬合成闭环, 不是线性管道。

核心修正 (2026-06-16):
- m3 守恒: 从软预算改为硬约束差异账本
- m4 先天完备性: 统一候选集, 注入/吸收逻辑平等
- m5 最小变易: 从统一候选集中随机选取, 无先验优先级
- m9 自指: 命名位编码"组织存在"这一事实, 是全新的差异
"""
from __future__ import annotations
import numpy as np


def _union_find(n, edges):
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    comps = {}
    for i in range(n):
        comps.setdefault(find(i), []).append(i)
    return list(comps.values())


# ===========================================================
# 1. 聚簇 (A1') — 差异在共同约束下形成局部聚集。
# ===========================================================
def m1_clustering(layer):
    """聚簇: 共同反差使共活跃位的绑定增强 (同色优先)。
    
    理论: "差异并不自动构成结构...世界的第一步不是对象出现,
    而是差异之间开始形成某种相互关联、相互牵引、相互约束的局部聚集。"
    """
    f = layer.field
    act = np.where(f.state == 1)[0]
    if len(act) < 2:
        return
    same = f.color[act][:, None] == f.color[act][None, :]
    inc = np.where(same, layer.p.bind_inc, layer.p.bind_inc * 0.15)
    np.fill_diagonal(inc, 0.0)
    f.binding[np.ix_(act, act)] += inc
    np.clip(f.binding, 0.0, layer.p.bind_cap, out=f.binding)


# ===========================================================
# 2. 层级 — 聚簇整体成为更高层级的差异单位。
# ===========================================================
def m2_hierarchy(layer):
    """层级: 从绑定图提取聚簇, 形成组织。
    
    理论: "聚簇的结果不只是形成局部结构, 而且形成了新的可参与生成的单位。"
    """
    f = layer.field
    act = np.where(f.state == 1)[0]
    if len(act) < 2:
        layer.tentative_orgs = []
        return
    edges = []
    sub = f.binding[np.ix_(act, act)]
    ii, jj = np.where(sub > layer.p.bind_threshold)
    for a, b in zip(ii.tolist(), jj.tolist()):
        if a < b:
            edges.append((a, b))
    comps = _union_find(len(act), edges)
    orgs = [set(int(act[i]) for i in comp)
            for comp in comps if len(comp) >= layer.p.min_org_size]
    layer.tentative_orgs = orgs


# ===========================================================
# 3. 守恒 (A5) — 差异不能被无代价湮灭, 只能转移。
#    ★ 硬约束: 追踪差异账本。
# ===========================================================
def m3_conservation(layer):
    """守恒: 计算本步的差异转移预算 (硬约束)。
    
    理论: "差异一旦形成并进入结构, 就不能被无代价地湮灭,
    只能以某种形式转移其位置、改变其分布、改变其形态或被更高层级重新吸纳。"
    
    硬约束: 源注入量与汇吸收量趋于平衡。
    - target_active: 系统试图维持的活跃位数
    - 偏离目标时, 预算拉回
    - 保留 churn (活秩序): 来自 a1_source 的注入能力
    """
    f = layer.field
    n = f.n_active()
    target = layer.p.target_active
    
    # 净翻转预算: 偏离目标越远, 拉回力越大
    net_budget = int(np.clip(target - n, -layer.p.max_flip, layer.p.max_flip))
    
    # ★ 注入和吸收独立运作: 注入由差异源驱动, 吸收由守恒约束驱动
    injectable = sum(1 for b in f.a1_source if f.state[b] == 0 and f.admissible(b))
    absorbable = sum(1 for b in np.where(f.state == 1)[0]
                      if f.admissible(b) and b not in f.sealed_bits
                      and f.binding[b, :].sum() <= layer.p.bind_threshold * 2)
    scale_churn = max(1, f.N // 10)
    # 注入能力: min(配置值, 可注入位数, 系统规模比例)
    layer.churn = min(layer.p.churn, injectable, scale_churn)
    # 吸收能力: 由守恒约束决定, 独立于注入
    layer._absorb_capacity = min(absorbable, scale_churn)
    
    # 守恒账本: 本步允许的注入量和吸收量
    layer._conservation_budget = {
        'max_inject': layer.churn,
        'max_absorb': layer._absorb_capacity,
        'net_budget': net_budget,
    }


# ===========================================================
# 4. 先天完备性 (A2/A3) — 所有候选路径在破缺前逻辑平等。
#    ★ 统一候选集: 注入和吸收没有先验优先级。
# ===========================================================
def m4_innate_completeness(layer):
    """先天完备性: 收集本步所有可共存的候选翻转。
    
    理论: "在给定约束条件下, 所有不自相矛盾、且可由该系统容纳的候选路径,
    在被实际选定之前, 都以逻辑平等的方式并存着。"
    
    ★ 关键: 注入候选(0→1)和吸收候选(1→0)在破缺前没有优先级。
    它们都是"差异可以发生的位", 只是方向不同。
    """
    f = layer.field
    
    # 统一候选集: 所有 admissible 的位, 不区分方向
    cand = set()
    
    # 注入候选: a1_source 中可被激活的位 (0→1)
    for b in f.a1_source:
        if f.state[b] == 0 and f.admissible(b):
            cand.add(('inject', b))
    
    # 吸收候选: 活跃位中可被释放的位 (1→0)
    # 但已被锁定的位(高绑定)不参与 — 守恒约束
    for b in np.where(f.state == 1)[0].tolist():
        if f.admissible(b) and b not in f.sealed_bits:
            # 高绑定位不参与候选 (已被"锁在一起")
            if f.binding[b, :].sum() <= layer.p.bind_threshold * 2:
                cand.add(('absorb', b))
    
    f.candidates = cand


# ===========================================================
# 5. 最小变易 (A4) — 从统一候选集中选择极小量翻转。
#    ★ 逻辑平等: 随机选取, 无先验优先级。
# ===========================================================
def m5_minimal_variation(layer):
    """最小变易: 从候选集中随机选择 Hamming=1 翻转。
    
    理论: "任何真实的变化都不能以无中介的整体跃迁方式发生,
    而必须通过局部、离散、可传递的单步变化逐步推进。"
    
    "系统并不会因为某条路径在价值上最好, 就自动优先走向它;
    它通常优先沿着阻力较小、代价较低、承接条件较多的方向推进,
    并先在最近能够维持自身的状态上停住。"
    
    ★ 实现: 从统一候选集中随机选取 (逻辑平等),
    但受守恒预算约束 (不是无限翻转)。
    """
    f = layer.field
    if f.sealed:
        return
    rng = f.rng
    
    # 从统一候选集中分离注入和吸收
    inject_cands = [b for (typ, b) in f.candidates if typ == 'inject']
    absorb_cands = [b for (typ, b) in f.candidates if typ == 'absorb']
    
    budget = layer._conservation_budget
    moves = 0
    
    # 注入: 差异源产生新差异 (0→1) — 活秩序的动力
    n_inject = min(len(inject_cands), budget['max_inject'])
    if n_inject > 0:
        chosen = rng.choice(inject_cands, size=n_inject, replace=False).tolist()
        for b in chosen:
            f.state[b] = 1
            moves += 1
    
    # 吸收: 释放活跃位 (1→0) — 守恒的回收
    n_absorb = min(len(absorb_cands), budget['max_absorb'])
    if n_absorb > 0 and absorb_cands:
        # 随机选取 (逻辑平等), 但受守恒预算约束
        chosen = rng.choice(absorb_cands, size=n_absorb, replace=False).tolist()
        for b in chosen:
            f.state[b] = 0
            moves += 1
    
    layer.moves_this_step = moves


# ===========================================================
# 6. 破缺 (A6) — 某条路径获得现实优先权。
# ===========================================================
def m6_breaking(layer):
    """破缺: 当组织绑定密度跨越临界, cascade 锁定。
    
    理论: "在原本逻辑平等并存的候选路径中, 某个离散节点上的变化打破了平衡,
    使某一路径获得现实优先权, 而其他可能性则被压缩、关闭或推迟。"
    """
    f = layer.field
    if f.sealed:
        return
    newly = []
    for org in getattr(layer, "tentative_orgs", []):
        org = set(b for b in org if f.state[b] == 1)
        if len(org) < layer.p.min_org_size:
            continue
        sub = f.binding[np.ix_(list(org), list(org))]
        density = sub.mean() if sub.size else 0.0
        if density >= layer.p.cascade_density:
            oid = f"L{f.layer}-org{len(f.organizations)}"
            if not any(org <= ex or ex <= org
                       for ex in f.organizations.values()):
                f.organizations[oid] = org
                newly.append(oid)
    layer.newly_broken = newly


# ===========================================================
# 7. 循环 (A7) — 被选中的路径通过反复返回维持自身。
# ===========================================================
def m7_cycle(layer):
    """循环: 检测活跃配置是否进入稳定闭合。
    
    理论: "循环并非简单重复, 而是使一个结构能够通过不断返回自身来维持自身的条件。"
    """
    f = layer.field
    hist = f.active_history
    if len(hist) >= 2 and hist[-1] == hist[-2]:
        f._cycle_counter += 1
    else:
        f._cycle_counter = 0
    layer.is_cyclic = f._cycle_counter >= layer.p.cycle_persistence


# ===========================================================
# 8. 锁定 — 循环持续 → 压缩替代路径 → 形成结构惯性。
# ===========================================================
def m8_locking(layer):
    """锁定: 稳定闭合 + 绑定饱和 → 冻结组织位。
    
    理论: "循环一旦稳定, 就不会停留在中性的重复上。
    它会逐渐压缩其他候选路径的空间, 形成惯性、黏滞性和路径依赖。"
    """
    f = layer.field
    if f.sealed:
        return
    for org in f.organizations.values():
        for b in org:
            f.lock_level[b] = min(1.0, f.lock_level[b] + layer.p.lock_inc)
    locked = set()
    for org in f.organizations.values():
        for b in org:
            if f.lock_level[b] >= layer.p.lock_threshold:
                locked.add(b)
    f.sealed_bits |= locked
    for b in locked:
        f.direction[b] = -1  # 锁定后只能衰减, 不再注入
    org_bits = (set().union(*f.organizations.values())
                if f.organizations else set())
    if (org_bits
            and len(f.sealed_bits & org_bits) >= layer.p.seal_fraction * len(org_bits)
            and len(f.organizations) >= 1
            and getattr(layer, "is_cyclic", False)):
        f.sealed = True
        f.seal_step = layer.step


# ===========================================================
# 9. 自指 (A9) — 结构把自身纳入自身的运作。
#    ★ 闭环: m9 的输出 = 下一层 m1 的输入。
# ===========================================================
def m9_self_reference(layer, self_encapsulate=True):
    """自指: A9 封装自身 — 生成下一层的差异源。
    
    理论: "自指是指系统不再只是被动地维持自身, 而开始把自身作为其运作的一部分来处理,
    能够表征自身、解释自身、调整自身、争夺自身的定义。"
    
    "当一个结构不仅能够维持自身, 而且能够把自身作为对象纳入自身的运作中时, 自指便出现了。"
    
    ★ 闭环咬合:
    - m9 的输出是一个新的 DifferenceField (下一层)
    - 该 Field 的 a1_source 来自自指行为本身 (命名位 = "组织存在"这一事实)
    - 下一层运行时, m1 聚簇作用于 m9 生成的 a1_source
    - 九机制因此咬合成闭环: m9 → [新层] → m1 → ... → m9 → ...
    
    ★ 命名位的本质:
    命名位不是 L0 比特的拷贝, 而是自指行为产生的全新差异。
    它编码的是"这个组织存在"这一事实本身 —— 这是 L0 上不存在的信息。
    """
    from .core import DifferenceField
    f = layer.field
    if not f.sealed or f.encapsulated:
        return None
    f.encapsulated = True
    orgs = [o for o in f.organizations.values()
            if len(o) >= layer.p.min_org_size]
    if not orgs:
        return None
    k = len(orgs)

    # --- (a) 身体位: 每个组织 → 一个粗粒化位 (多数表决) ---
    body_idx = list(range(k))

    if not self_encapsulate:
        # 基线 (死秩序): 只有被动投影, 无差异源
        nxt = DifferenceField(
            N=k, active=body_idx, a1_source=set(),
            direction=np.full(k, -1, dtype=np.int8),
            color=np.arange(k), layer=f.layer + 1, rng=f.rng,
            naming_meta={"mode": "passive_projection"},
        )
        return nxt

    # --- (b) 自指封装: 命名位 + 余差位 → 下一层的 a1_source ---
    
    # 命名位: 每个组织一个身份位
    # ★ 这是自指行为产生的全新差异, 不是 L0 比特的拷贝
    naming_idx = list(range(k, 2 * k))
    
    # 余差位: 未被完全锁定的活跃位, 递归参与下一层
    residual = sorted(f.active_set() - f.sealed_bits)
    n_res = min(len(residual), layer.p.max_residual)
    res_idx = list(range(2 * k, 2 * k + n_res))
    N1 = 2 * k + n_res

    # 色: 身体位继承组织签名, 命名位同签名 → body 与 naming 会聚簇
    # ★ 自指迹象: 结构把自身纳入自身
    color = np.zeros(N1, dtype=int)
    for i, org in enumerate(orgs):
        sig = int(np.mean(sorted(org)) % max(1, layer.p.n_meta_colors))
        color[i] = sig            # body 继承签名
        color[k + i] = sig        # naming 同签名 → 聚簇
    for j in range(n_res):
        color[2 * k + j] = layer.p.n_meta_colors + (j % 3)

    # 初始绑定: body ↔ naming (组织身份关系)
    # ★ 这是 L0 上不存在的新关系
    binding = np.zeros((N1, N1), dtype=float)
    for i in range(k):
        binding[i, k + i] = binding[k + i, i] = layer.p.bind_threshold * 1.5

    # ★ a1_source = 命名位 ∪ 余差位
    # 这是 L1 自己的、内生的差异源
    # 命名位编码"组织存在"这一事实 → 全新的差异
    # 余差位携带未锁定的活跃差异 → 递归参与
    a1 = set(naming_idx) | set(res_idx)

    direction = np.zeros(N1, dtype=np.int8)
    for b in body_idx:
        direction[b] = -1            # 身体位: 组织已存在, 只能衰减
    for b in naming_idx + res_idx:
        direction[b] = 0             # 命名/余差位: 可双向 → 产生 churn

    nxt = DifferenceField(
        N=N1, active=body_idx + naming_idx,
        a1_source=a1, direction=direction, binding=binding, color=color,
        layer=f.layer + 1, rng=f.rng,
        naming_meta={
            "mode": "self_reference", "k_orgs": k,
            "body_idx": body_idx, "naming_idx": naming_idx,
            "res_idx": res_idx, "parent_layer": f.layer,
        },
    )
    return nxt


# ===========================================================
# 九机制注册表 (不含 m9, m9 由 RecursiveWorld 调度)
# ===========================================================
NINE_MECHANISMS = [
    ("聚簇", m1_clustering),
    ("层级", m2_hierarchy),
    ("守恒", m3_conservation),
    ("先天完备性", m4_innate_completeness),
    ("最小变易", m5_minimal_variation),
    ("破缺", m6_breaking),
    ("循环", m7_cycle),
    ("锁定", m8_locking),
    # m9 自指由 RecursiveWorld 在密封后调度, 因为它跨层生成新场。
]
