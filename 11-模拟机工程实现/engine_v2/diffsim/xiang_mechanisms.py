"""xiang_mechanisms.py — 象界显现链 (m10-m16)

理论来源: 01-核心理论-差异论/象界.md

象界七步显现链:
  m10: 边界→界面 (从分隔到调节交换)
  m11: 闭合→自维持 (循环在开放中维持自身)
  m12: 痕迹→记忆 (路径被保留并影响未来)
  m13: 再现→复制 (样式在新条件下重新构造)
  m14: 并存→筛选 (不同样式面临不同延续命运)
  m15: 耦合→功能 (内部不对称贡献)
  m16: 汇聚→前主体态 (以上机制的初步汇聚)

★ 象界不是新法则, 而是同一法则在结构层的加厚。
  m10-m16 建立在 m1-m9 之上, 不替代它们。

当前实现: m10 + m11 (最基础的两步)
"""
from __future__ import annotations
import numpy as np
from typing import Set, Dict, List, Tuple


# ===========================================================
# 10. 边界→界面 (m10) — 从分隔到调节交换
# ===========================================================
def m10_boundary_interface(layer):
    """边界→界面: 组织的边界位开始调节内外交换。
    
    理论: "边界的真正起点不在视觉轮廓, 而在交换的不均匀。
    一个结构之所以开始拥有边界, 不是因为它看起来像一个整体,
    而是因为它与周围差异之间的交换方式发生了变化。"
    
    实现:
    - 识别组织的"边界位": 与组织外部有连接的位
    - 边界位的绑定强度决定界面的"渗透性"
    - 渗透性影响下一轮的注入/吸收行为
    """
    f = layer.field
    if not f.organizations:
        return
    
    boundary_bits = set()
    interface_strength = {}
    
    for org_id, org_bits in f.organizations.items():
        org_list = list(org_bits)
        non_org_bits = set(range(f.N)) - org_bits
        
        for b in org_list:
            # 检查该位是否与组织外部有连接
            external_binding = sum(f.binding[b, j] for j in non_org_bits if j < f.N)
            if external_binding > 0:
                boundary_bits.add(b)
                # 界面强度 = 内部绑定 / (内部绑定 + 外部绑定)
                internal_binding = sum(f.binding[b, j] for j in org_list if j != b)
                total = internal_binding + external_binding
                interface_strength[b] = internal_binding / total if total > 0 else 0.5
    
    # 存储界面信息
    layer._boundary_bits = boundary_bits
    layer._interface_strength = interface_strength


# ===========================================================
# 11. 闭合→自维持 (m11) — 循环在开放中维持自身
# ===========================================================
def m11_self_maintenance(layer):
    """自维持: 循环不仅闭合, 而且在交换中维持自身。
    
    理论: "自维持要求一种更强的关系: 循环不仅发生,
    而且其发生本身会持续地再生产其发生条件。"
    
    "自维持不是封闭的极端形式, 恰恰相反, 它是开放中的闭合。"
    
    实现:
    - 检测组织是否在多次循环中保持其关键关系
    - 计算"自维持得分": 关键绑定在循环中的稳定性
    - 高自维持得分的组织更不容易被扰动破坏
    """
    f = layer.field
    if not f.organizations:
        return
    
    self_maintenance_scores = {}
    
    for org_id, org_bits in f.organizations.items():
        org_list = list(org_bits)
        if len(org_list) < 2:
            self_maintenance_scores[org_id] = 0.0
            continue
        
        # 计算关键绑定的稳定性
        # 关键绑定 = 组织内部的平均绑定强度
        sub_binding = f.binding[np.ix_(org_list, org_list)]
        key_binding_strength = sub_binding.mean()
        
        # 检查关键位是否在循环中保持活跃
        # (通过检查 active_history 中的连续性)
        hist = f.active_history
        if len(hist) >= 3:
            # 最近 3 步中, 组织位保持活跃的比例
            recent = hist[-3:]
            stability = 0.0
            for b in org_list:
                active_count = sum(1 for s in recent if b in s)
                stability += active_count / len(recent)
            stability /= len(org_list)
        else:
            stability = 1.0  # 默认稳定
        
        # 自维持得分 = 关键绑定强度 × 稳定性
        self_maintenance_scores[org_id] = key_binding_strength * stability
    
    # 存储自维持信息
    layer._self_maintenance_scores = self_maintenance_scores
    
    # 高自维持得分的组织获得"保护": 降低其位被吸收的概率
    for org_id, score in self_maintenance_scores.items():
        if score > 0.5:  # 阈值
            org_bits = f.organizations[org_id]
            for b in org_bits:
                # 提高锁定速度
                f.lock_level[b] = min(1.0, f.lock_level[b] + 0.05 * score)




# ===========================================================
# 12. 痕迹→记忆 (m12) — 路径被保留并影响未来
# ===========================================================
def m12_path_memory(layer):
    """记忆: 曾经发生过的路径持续改变未来的结构分布。
    
    理论: "记忆要求某条曾经发生过的路径, 不仅被走过,
    而且被后续结构反复调用; 要求某种过去的关系安排,
    不仅留下残留, 而且持续改变未来耦合的概率。"
    
    实现:
    - 追踪每个位的"历史活跃度" (曾经在组织中的次数)
    - 历史活跃度高的位更容易被注入 (路径偏置)
    - 这是"无叙事的记忆" — 结构中的偏置, 不是意识中的回忆
    """
    f = layer.field
    
    # 初始化历史追踪
    if not hasattr(f, '_path_memory'):
        f._path_memory = np.zeros(f.N, dtype=float)
    
    # 更新: 当前在组织中的位获得记忆加成
    for org_bits in f.organizations.values():
        for b in org_bits:
            f._path_memory[b] += 1.0
    
    # 记忆衰旧: 防止单一位永远占优
    f._path_memory *= 0.95
    
    # 存储: 高记忆位更容易被注入
    layer._path_memory = f._path_memory.copy()


# ===========================================================
# 13. 再现→复制 (m13) — 样式在新条件下重新构造
# ===========================================================
def m13_pattern_replication(layer):
    """复制: 关键关系在新条件下被再次构造。
    
    理论: "复制不是同一物的机械重现, 而是某种组织样式
    得以在不同条件下重新构造自身的能力。"
    
    实现:
    - 检测当前组织是否与历史组织有相似的"签名"
    - 签名 = 组织位的颜色分布 + 绑定模式
    - 相似签名的组织被视为"同一样式的不同实例"
    """
    f = layer.field
    if not f.organizations:
        return
    
    # 初始化样式历史
    if not hasattr(f, '_pattern_history'):
        f._pattern_history = []
    
    # 计算当前组织的签名
    current_patterns = {}
    for org_id, org_bits in f.organizations.items():
        org_list = sorted(org_bits)
        # 签名 = 颜色分布的哈希
        colors = tuple(sorted(f.color[b] for b in org_list))
        binding_pattern = tuple(round(f.binding[org_list[i], org_list[j]], 2)
                               for i in range(len(org_list))
                               for j in range(i+1, len(org_list)))
        signature = (colors, binding_pattern)
        current_patterns[org_id] = signature
    
    # 检查是否有历史样式被复制
    replicated = []
    for org_id, sig in current_patterns.items():
        for hist_sig in f._pattern_history:
            # 简单匹配: 颜色分布相同
            if sig[0] == hist_sig[0]:
                replicated.append(org_id)
                break
    
    # 记录当前样式
    f._pattern_history.extend(current_patterns.values())
    # 保留最近 20 个样式
    if len(f._pattern_history) > 20:
        f._pattern_history = f._pattern_history[-20:]
    
    layer._replicated_orgs = replicated


# ===========================================================
# 14. 并存→筛选 (m14) — 不同样式面临不同延续命运
# ===========================================================
def m14_selection(layer):
    """筛选: 不同组织样式在延续中显出差异。
    
    理论: "筛选并不是一种外加机制, 而是延续能力差异的结果显现。
    它不是额外发生在结构之上的事情, 而是结构样式一旦进入并存与延续,
    其命运自然开始分化的方式。"
    
    实现:
    - 比较各组织的自维持得分
    - 低自维持组织的位更容易被释放 (衰减)
    - 高自维持组织的位获得额外保护
    """
    f = layer.field
    scores = getattr(layer, '_self_maintenance_scores', {})
    if not scores:
        return
    
    # 计算得分分布
    score_values = list(scores.values())
    if not score_values:
        return
    mean_score = np.mean(score_values)
    
    # 筛选: 低于平均的组织衰减更快
    for org_id, score in scores.items():
        if score < mean_score * 0.5:
            # 弱组织: 加速衰减
            org_bits = f.organizations.get(org_id, set())
            for b in org_bits:
                f.lock_level[b] = max(0, f.lock_level[b] - 0.02)
    
    # 筛选压力 = 得分方差 (有差异就有筛选)
    score_std = np.std(score_values) if len(score_values) > 1 else 0
    score_cv = score_std / mean_score if mean_score > 0 else 0
    layer._selection_pressure = {
        'mean_score': mean_score,
        'score_cv': score_cv,
        'has_selection': score_cv > 0.05,  # 变异系数 > 5% 表示有筛选压力
    }


# ===========================================================
# 15. 耦合→功能 (m15) — 内部不对称贡献
# ===========================================================
def m15_functional_differentiation(layer):
    """功能: 结构内部某部分因对整体持存的贡献而被优先保留。
    
    理论: "功能之出现, 使结构内部第一次拥有了层次,
    拥有了某种局部与整体之间的持续关系。"
    
    实现:
    - 计算每个位对组织稳定性的贡献
    - 高贡献位获得"功能"标记
    - 功能位在吸收时被优先保护
    """
    f = layer.field
    if not f.organizations:
        return
    
    functional_bits = {}
    
    for org_id, org_bits in f.organizations.items():
        org_list = list(org_bits)
        if len(org_list) < 2:
            continue
        
        # 计算每个位的"功能贡献" = 移除该位后绑定密度的变化
        full_binding = f.binding[np.ix_(org_list, org_list)]
        full_density = full_binding.mean()
        
        contributions = {}
        for b in org_list:
            remaining = [x for x in org_list if x != b]
            if len(remaining) < 2:
                contributions[b] = 0
                continue
            sub = f.binding[np.ix_(remaining, remaining)]
            reduced_density = sub.mean()
            contributions[b] = full_density - reduced_density
        
        # 标记高贡献位为"功能位"
        if contributions:
            mean_contrib = np.mean(list(contributions.values()))
            for b, contrib in contributions.items():
                if contrib > mean_contrib * 1.5:
                    functional_bits[b] = contrib
    
    layer._functional_bits = functional_bits


# ===========================================================
# 16. 汇聚→前主体态 (m16) — 以上机制的初步汇聚
# ===========================================================
def m16_pre_subject(layer):
    """前主体态: 边界、自维持、记忆、复制、筛选、功能的初步汇聚。
    
    理论: "前主体态不是自我, 也不是意识, 不是认同,
    不是叙事中的'我', 还不是高层意义上的生命实体。
    它只是差异组织达到了这样一种密度: 能够区分内外,
    能够在开放中维持自身, 能够保留路径, 能够重现样式,
    能够在筛选中延续, 能够形成内部功能性差异。"
    
    实现:
    - 检查是否所有象界条件都已满足
    - 边界: 有边界位
    - 自维持: 有高自维持得分的组织
    - 记忆: 有路径偏置
    - 复制: 有被复制的样式
    - 筛选: 有弱/强组织的分化
    - 功能: 有功能位
    """
    f = layer.field
    
    conditions = {
        'boundary': len(getattr(layer, '_boundary_bits', set())) > 0,
        'self_maintenance': any(
            s > 0.5 for s in getattr(layer, '_self_maintenance_scores', {}).values()
        ) if hasattr(layer, '_self_maintenance_scores') else False,
        'memory': hasattr(f, '_path_memory') and np.max(f._path_memory) > 1.0,
        'replication': len(getattr(layer, '_replicated_orgs', [])) > 0,
        'selection': getattr(layer, '_selection_pressure', {}).get('has_selection', False),
        'function': len(getattr(layer, '_functional_bits', {})) > 0,
    }
    
    n_satisfied = sum(conditions.values())
    layer._pre_subject_conditions = conditions
    layer._pre_subject_score = n_satisfied / len(conditions)
    
    # 前主体态 = 所有条件都满足
    layer.is_pre_subject = n_satisfied == len(conditions)


# ===========================================================
# 象界机制注册表 (完整)
# ===========================================================
XIANG_MECHANISMS = [
    ("边界→界面", m10_boundary_interface),
    ("自维持", m11_self_maintenance),
    ("记忆", m12_path_memory),
    ("复制", m13_pattern_replication),
    ("筛选", m14_selection),
    ("功能", m15_functional_differentiation),
    ("前主体态", m16_pre_subject),
]

