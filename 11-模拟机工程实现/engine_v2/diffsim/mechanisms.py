"""mechanisms.py — 九个机制作为显式齿轮。

每个函数接受一个 Layer, 读/写 layer.field。调用顺序严格按照理论环:
    聚簇 → 层级 → 守恒 → 先天完备性 → 最小变易 → 破缺 → 循环 → 锁定 → 自指
这是一个 *闭环*: 自指(m9) 生成下一层的差异源, 使下一层的聚簇(m1)重新启动。
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


# ---------------------------------------------------------------------------
# 1. 聚簇 (A1') — 共同反差使共活跃位的绑定增强 (同色优先)。
# ---------------------------------------------------------------------------
def m1_clustering(layer, throttle: float = 1.0):
    """聚簇机制，接受节流因子调制。
    
    throttle=1.0: 全功率运行 (原始行为)
    throttle=0.0: 不增强绑定 (能量耗尽)
    throttle=0.5: 绑定增强减半
    """
    f = layer.field
    act = np.where(f.state == 1)[0]
    if len(act) < 2:
        return
    same = f.color[act][:, None] == f.color[act][None, :]
    # 用 throttle 调制绑定增强强度
    effective_inc = layer.p.bind_inc * throttle
    inc = np.where(same, effective_inc, effective_inc * 0.15)
    np.fill_diagonal(inc, 0.0)
    f.binding[np.ix_(act, act)] += inc
    np.clip(f.binding, 0.0, layer.p.bind_cap, out=f.binding)


# ---------------------------------------------------------------------------
# 2. 层级 — 从绑定图提取聚簇, 多重隶属地形成(暂定)组织。
# ---------------------------------------------------------------------------
def m2_hierarchy(layer):
    f = layer.field
    act = np.where(f.state == 1)[0]
    if len(act) < 2:
        layer.tentative_orgs = []
        return
    idx = {b: i for i, b in enumerate(act.tolist())}
    edges = []
    sub = f.binding[np.ix_(act, act)]
    ii, jj = np.where(sub > layer.p.bind_threshold)
    for a, b in zip(ii.tolist(), jj.tolist()):
        if a < b:
            edges.append((a, b))
    comps = _union_find(len(act), edges)
    orgs = [set(int(act[i]) for i in comp) for comp in comps if len(comp) >= layer.p.min_org_size]
    layer.tentative_orgs = orgs


# ---------------------------------------------------------------------------
# 3. 守恒 (A5/A8) — 计算本步净翻转预算: 源注入(0->1) 与 汇吸收(1->0) 趋于平衡。
# ---------------------------------------------------------------------------
def m3_conservation(layer):
    f = layer.field
    n = f.n_active()
    target = layer.p.target_active
    # 偏离目标越远, 预算越倾向于拉回; 同时保留一些 churn(活秩序)。
    f.flux_budget = int(np.clip(target - n, -layer.p.max_flip, layer.p.max_flip))
    layer.churn = min(layer.p.churn, max(0, len(f.a1_source)))


# ---------------------------------------------------------------------------
# 4. 先天完备性 (A2/A3) — 本步所有可共存的候选翻转(未冻结、合乎流向)。
#    "完备"= 所有可能性在破缺之前同时存在。
# ---------------------------------------------------------------------------
def m4_innate_completeness(layer):
    f = layer.field
    cand = set()
    # 源位可被注入 (0->1)
    for b in f.a1_source:
        if f.admissible(b):
            cand.add(b)
    # 活跃位可被吸收 (1->0), 要求流向允许
    for b in np.where(f.state == 1)[0].tolist():
        if f.admissible(b):
            cand.add(b)
    f.candidates = cand


# ---------------------------------------------------------------------------
# 5. 最小变易 (A4) — 从候选中只选择极小量单位(Hamming=1)翻转并提交。
# ---------------------------------------------------------------------------
def m5_minimal_variation(layer, throttle: float = 1.0):
    """最小变易机制，接受节流因子调制。
    
    throttle=1.0: 全功率运行 (原始行为)
    throttle=0.0: 不允许翻转 (能量耗尽)
    throttle=0.5: 翻转数量减半
    """
    f = layer.field
    if f.sealed:
        return
    rng = f.rng
    inject = [b for b in f.a1_source if f.state[b] == 0 and f.admissible(b)]
    absorbable = [b for b in np.where(f.state == 1)[0].tolist()
                  if f.admissible(b) and b not in f.sealed_bits]
    moves = 0
    # 用 throttle 调制翻转数量
    throttle = max(0.0, min(1.0, throttle))  # 确保在 [0, 1] 范围内
    # 注入: 差异源产生新差异 (0->1) —— 这是"活秩序"的动力
    n_inject = int(min(len(inject), layer.churn) * throttle)
    if n_inject > 0:
        for b in rng.choice(inject, size=n_inject, replace=False).tolist():
            f.state[b] = 1
            moves += 1
    # 守恒回收: 优先吸收孤立(低绑定)的活跃位
    if absorbable:
        deg = f.binding[absorbable, :].sum(axis=1)
        order = np.argsort(deg)  # 低绑定优先被吸收
        budget = int((layer.churn + max(0, -f.flux_budget)) * throttle)
        for k in order[:budget].tolist():
            b = absorbable[k]
            # 高绑定位不被吸收(已被"锁在一起")
            if f.binding[b, :].sum() > layer.p.bind_threshold * 2:
                continue
            f.state[b] = 0
            moves += 1
    layer.moves_this_step = moves


# ---------------------------------------------------------------------------
# 6. 破缺 (A6) — 对称性破缺: 当某组织的绑定密度跨越临界, 一次性 cascade 锁定它。
#    这是一阶相变的源头。
# ---------------------------------------------------------------------------
def m6_breaking(layer, throttle: float = 1.0):
    """破缺机制，接受节流因子调制。
    
    throttle=1.0: 全功率运行 (原始行为)
    throttle=0.0: 极度难以触发破缺 (cascade_density 阈值提高)
    throttle=0.5: cascade_density 阈值提高 50%
    """
    f = layer.field
    if f.sealed:
        return
    newly = []
    # 用 throttle 调制 cascade_density 阈值
    # throttle 低时，需要更高的密度才能触发破缺
    effective_density = layer.p.cascade_density * (2.0 - throttle)  # throttle=0 -> 2x threshold, throttle=1 -> 1x threshold
    for org in getattr(layer, "tentative_orgs", []):
        org = set(b for b in org if f.state[b] == 1)
        if len(org) < layer.p.min_org_size:
            continue
        sub = f.binding[np.ix_(list(org), list(org))]
        density = sub.mean() if sub.size else 0.0
        if density >= effective_density:
            oid = f"L{f.layer}-org{len(f.organizations)}"
            if not any(org <= ex or ex <= org for ex in f.organizations.values()):
                f.organizations[oid] = org
                newly.append(oid)
    layer.newly_broken = newly


# ---------------------------------------------------------------------------
# 7. 循环 (A7) — 检测活跃配置是否进入稳定闭合(反复出现)。
# ---------------------------------------------------------------------------
def m7_cycle(layer):
    f = layer.field
    hist = f.active_history
    if len(hist) >= 2 and hist[-1] == hist[-2]:
        f._cycle_counter += 1
    else:
        f._cycle_counter = 0
    layer.is_cyclic = f._cycle_counter >= layer.p.cycle_persistence


# ---------------------------------------------------------------------------
# 8. 锁定 — 稳定闭合 + 绑定饱和 => 锁定(冻结)组织位; 锁定比例达阈则密封。
# ---------------------------------------------------------------------------
def m8_locking(layer):
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
    org_bits = set().union(*f.organizations.values()) if f.organizations else set()
    if org_bits and len(f.sealed_bits & org_bits) >= layer.p.seal_fraction * len(org_bits) \
            and len(f.organizations) >= 1 and getattr(layer, "is_cyclic", False):
        f.sealed = True
        f.seal_step = layer.step


# ---------------------------------------------------------------------------
# 9. 自指 (A9) ★ 缺失的动作 — A9 封装自身。
#
#  (a) 向外封装[原行为]: 每个组织 -> 一个粗粒化"身体位"(多数表决)。
#  (b) 自指封装[补回的动作]: 将"封装这个动作本身"纳入结构 ——
#      为每个组织生成一个"命名/身份位"(naming bit)。该位编码"组织存在这一事实"
#      本身, 是 L0 上不存在的、全新的差异(不是被冻结的 L0 位的拷贝)。
#      这些命名位成为下一层的 a1_source(新 A1), 组织间关系成为下一层的初始绑定。
#      余差(未被完全锁定的活跃位)递归参与下一层的装配。
#
#  => 下一层拥有 *内生的* 差异源 -> 非零 Jaccard flux -> 可运行自己的九机制 -> 咬合。
# ---------------------------------------------------------------------------
def m9_self_reference(layer, self_encapsulate=True):
    from .core import DifferenceField
    f = layer.field
    if not f.sealed or f.encapsulated:
        return None
    f.encapsulated = True
    orgs = [o for o in f.organizations.values() if len(o) >= layer.p.min_org_size]
    if not orgs:
        return None
    k = len(orgs)

    # --- (a) 向外封装: 身体位 (每组织一位) ---
    body_idx = list(range(k))

    if not self_encapsulate:
        # 基线(原项目行为): 只有被动投影, 无差异源 -> 死秩序。
        nxt = DifferenceField(
            N=k, active=body_idx, a1_source=set(),  # ← 空差异源
            direction=np.full(k, -1, dtype=np.int8),
            color=np.arange(k), layer=f.layer + 1, rng=f.rng,
            naming_meta={"mode": "passive_projection"},
        )
        return nxt

    # --- (b) 自指封装: 命名/身份位 + 组织间关系 + 余差 ---
    naming_idx = list(range(k, 2 * k))           # 每组织一个身份位 (全新差异)
    residual = sorted((f.active_set() - f.sealed_bits))
    n_res = min(len(residual), layer.p.max_residual)
    res_idx = list(range(2 * k, 2 * k + n_res))  # 余差携带位
    N1 = 2 * k + n_res

    # 身份位的 *色* 由组织的成员签名决定(自指迹象): 结构把自身纳入自身。
    color = np.zeros(N1, dtype=int)
    for i, org in enumerate(orgs):
        sig = int(np.mean(sorted(org)) % max(1, layer.p.n_meta_colors))
        color[i] = sig            # body 继承签名
        color[k + i] = sig        # naming 位同签名 -> body 与 naming 会聚簇
    for j in range(n_res):
        color[2 * k + j] = layer.p.n_meta_colors + (j % 3)

    # 初始绑定: 组织间关系(由同一余差划分而来) -> 跨组织边, 这是 L0 上不存在的新关系。
    binding = np.zeros((N1, N1), dtype=float)
    for i in range(k):
        binding[i, k + i] = binding[k + i, i] = layer.p.bind_threshold * 1.5  # body<->naming

    # a1_source = 命名位 + 余差位 —— 这是 L1 自己的、内生的差异源。
    a1 = set(naming_idx) | set(res_idx)
    direction = np.zeros(N1, dtype=np.int8)
    for b in body_idx:
        direction[b] = -1            # 身体位代表“组织已存在”, 只能衰减
    for b in naming_idx + res_idx:
        direction[b] = 0             # 命名/余差位可双向 -> 产生 churn

    nxt = DifferenceField(
        N=N1, active=body_idx + naming_idx,  # naming 位初始激活(身份被声明)
        a1_source=a1, direction=direction, binding=binding, color=color,
        layer=f.layer + 1, rng=f.rng,
        naming_meta={
            "mode": "self_reference", "k_orgs": k,
            "body_idx": body_idx, "naming_idx": naming_idx, "res_idx": res_idx,
            "parent_layer": f.layer,
        },
    )
    return nxt


NINE_MECHANISMS = [
    ("聚簇", m1_clustering),
    ("层级", m2_hierarchy),
    ("守恒", m3_conservation),
    ("先天完备性", m4_innate_completeness),
    ("最小变易", m5_minimal_variation),
    ("破缺", m6_breaking),
    ("循环", m7_cycle),
    ("锁定", m8_locking),
    # 自指(m9)由 world 在密封后调度, 因为它跨层生成新场。
]
