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
# 象界机制注册表
# ===========================================================
XIANG_MECHANISMS = [
    ("边界→界面", m10_boundary_interface),
    ("自维持", m11_self_maintenance),
]
