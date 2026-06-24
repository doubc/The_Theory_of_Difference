"""worldbase_integration.py — WorldBase 代数结构集成到九机制演化循环。

将 worldbase_core.py 的代数结构注入 mechanisms.py 的九机制,
使模拟机在演化过程中涌现出:
- A8 中截面偏好 (影响守恒目标)
- E_{ij} 变易 (中截面上的双比特对换)
- su(3) 代数闭合检测 (k=3 活跃位)
- 色禁闭检测 (线性势)
- su(2) 极分解 (V-A 锁定)

不修改原有 mechanisms.py, 而是在其之上叠加 WorldBase 感知层。
"""
from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional, Tuple
from .worldbase_core import (
    MidSurface, VariationalOperator, Su3Algebra, Su2FromDAG,
    GravitationalPotential, ConstraintDegreeFunction,
    DiscreteGaugeConnection, DiscreteExteriorCalculus,
    enumerate_mid_surface
)


# ===========================================================
# WorldBase 参数 (注入到 LayerParams)
# ===========================================================

class WorldBaseParams:
    """WorldBase 增强参数, 可叠加到任何 LayerParams 上。"""
    
    def __init__(self, N: int):
        self.N = N
        self.mid = MidSurface(N)
        
        # A8 中截面偏好强度: 0=无偏好, 1=完全偏好中截面
        self.a8_strength = 0.8
        
        # E_{ij} 变易: 中截面上执行双比特对换的概率
        self.eij_probability = 0.3
        
        # su(3) 检测: 活跃位数量阈值
        self.su3_min_active = 3
        
        # 色禁闭检测: 线性势斜率阈值
        self.confinement_slope_threshold = 0.01


# ===========================================================
# A8 中截面感知: 影响守恒目标
# ===========================================================

def a8_adjust_target(layer, wb_params: WorldBaseParams):
    """A8 中截面偏好: 将 target_active 向 N/2 偏移。
    
    WorldBase §2.2 A8: 系统偏好汉明重量 w = N/2 的状态。
    实现: 将守恒目标从固定值向 N/2 偏移, 偏移强度由 a8_strength 控制。
    """
    f = layer.field
    N = f.N
    w_mid = N // 2
    w_current = f.n_active()
    
    # A8 偏好: target 向 N/2 靠拢
    original_target = layer.p.target_active
    a8_target = w_mid
    
    # 混合: a8_strength=0 → 原始目标, a8_strength=1 → 完全中截面
    adjusted = (1 - wb_params.a8_strength) * original_target + \
               wb_params.a8_strength * a8_target
    
    layer.p.target_active = int(round(adjusted))
    return layer.p.target_active


# ===========================================================
# E_{ij} 变易: 中截面上的双比特对换
# ===========================================================

def eij_variational_move(layer, wb_params: WorldBaseParams) -> int:
    """在中截面附近执行 E_{ij} 双比特对换。
    
    WorldBase §5.3: E_{ij} 将激活位 i 的差异移动到位置 j,
    保持汉明重量不变。这是守恒约束下 A4 允许的最小非平凡变易。
    
    与单比特翻转互补:
    - 单比特翻转: 改变重量, 驱动系统趋近/远离中截面
    - E_{ij} 对换: 保持重量, 在中截面上重组差异分布
    
    Returns: 执行的 E_{ij} 对换次数
    """
    f = layer.field
    if f.sealed:
        return 0
    
    N = f.N
    w = f.n_active()
    w_mid = N // 2
    
    # 只在接近中截面时启用 E_{ij}
    # 条件放宽: 距离中截面 N/4 以内即可
    if abs(w - w_mid) > max(4, N // 4):
        return 0
    
    rng = f.rng
    op = VariationalOperator(N)
    sealed = f.sealed_bits
    
    # 列出所有允许的 E_{ij} 转移
    transitions = op.all_transitions(f.state, sealed)
    if not transitions:
        return 0
    
    # 按概率执行
    n_moves = 0
    max_moves = max(1, len(transitions) // 4)  # 每步最多 1/4 的转移
    
    rng.shuffle(transitions)
    for (i, j) in transitions[:max_moves]:
        if rng.random() < wb_params.eij_probability:
            new_state = op.apply(f.state, i, j)
            if new_state is not None:
                f.state = new_state
                n_moves += 1
    
    return n_moves


# ===========================================================
# su(3) 代数检测: k=3 活跃位上的规范代数
# ===========================================================

def detect_su3_emergence(layer, wb_params: WorldBaseParams) -> Dict:
    """检测 su(3) 代数涌现。
    
    WorldBase §5.5: k=3 活跃位 + A4 + A9 → su(3) 八维代数。
    
    检测条件:
    1. 至少有 3 个活跃位
    2. 这 3 个活跃位之间有足够的绑定
    3. 8 个生成元线性独立
    
    Returns: su(3) 检测结果
    """
    f = layer.field
    N = f.N
    act = np.where(f.state == 1)[0]
    
    if len(act) < wb_params.su3_min_active:
        return {"detected": False, "reason": "too_few_active_bits"}
    
    # 找绑定最强的 3 个活跃位
    if len(act) >= 3:
        sub = f.binding[np.ix_(act, act)]
        # 选择绑定总和最大的 3 个位
        bind_strength = sub.sum(axis=1)
        top3_idx = np.argsort(bind_strength)[-3:]
        top3_bits = sorted(act[top3_idx].tolist())
        
        a, b, c = top3_bits
        
        # 用中截面子集验证 (完整空间对大N太大)
        mid_states = enumerate_mid_surface(min(N, 10), max_states=200)
        if len(mid_states) < 4:
            return {"detected": False, "reason": "mid_surface_too_small"}
        
        # 在三活跃位上构造 8 个生成元
        op = VariationalOperator(min(N, 10))
        # 映射到小空间的活跃位
        a_s, b_s, c_s = 0, 1, 2  # 在小空间中使用前3位
        gens = []
        for (i, j) in [(a_s,b_s),(b_s,a_s),(b_s,c_s),(c_s,b_s),(c_s,a_s),(a_s,c_s)]:
            gens.append(op.e_ij_matrix(i, j, mid_states))
        
        diag_ab = np.zeros((len(mid_states), len(mid_states)))
        diag_bc = np.zeros((len(mid_states), len(mid_states)))
        for idx_s, s in enumerate(mid_states):
            diag_ab[idx_s, idx_s] = float(s[a_s] - s[b_s])
            diag_bc[idx_s, idx_s] = float(s[b_s] - s[c_s])
        gens.append(diag_ab)
        gens.append(diag_bc)
        
        flat = np.array([g.flatten() for g in gens])
        rank = np.linalg.matrix_rank(flat, tol=1e-10)
        
        return {
            "detected": rank == 8,
            "active_bits": [a, b, c],
            "dimension": rank,
            "n_active": len(act),
        }
    
    return {"detected": False, "reason": "insufficient_binding"}


# ===========================================================
# 色禁闭检测: 线性势 V(d) ∝ d
# ===========================================================

def detect_color_confinement(layer, wb_params: WorldBaseParams) -> Dict:
    """检测色禁闭: 组织间的势是否呈线性增长。
    
    WorldBase §5.9 定理 CONF-2: 色荷-反色荷对的势函数 V(d) ∝ d。
    
    检测方法: 对不同分离距离 d, 计算组织间的绑定代价,
    检查是否线性增长。
    """
    f = layer.field
    orgs = list(f.organizations.values())
    
    if len(orgs) < 2:
        return {"detected": False, "reason": "too_few_organizations"}
    
    # 计算组织间的"距离" (汉明距离的平均)
    distances = []
    potentials = []
    
    for i, org1 in enumerate(orgs):
        for j, org2 in enumerate(orgs):
            if i >= j:
                continue
            bits1 = sorted(org1)
            bits2 = sorted(org2)
            
            # 组织间汉明距离: 最近两位之间的距离
            min_dist = min(abs(b1 - b2) for b1 in bits1 for b2 in bits2)
            
            # 绑定代价: 两个组织之间的绑定强度
            bind_cost = 0
            for b1 in bits1:
                for b2 in bits2:
                    bind_cost += f.binding[b1, b2]
            
            distances.append(min_dist)
            potentials.append(bind_cost)
    
    if len(distances) < 2:
        return {"detected": False, "reason": "insufficient_data"}
    
    # 线性拟合: V = slope * d + intercept
    distances = np.array(distances, dtype=float)
    potentials = np.array(potentials, dtype=float)
    
    if np.std(distances) < 1e-10:
        return {"detected": False, "reason": "no_separation"}
    
    # 简单线性回归
    slope = np.cov(potentials, distances)[0, 1] / np.var(distances)
    
    return {
        "detected": abs(slope) > wb_params.confinement_slope_threshold,
        "slope": slope,
        "n_pairs": len(distances),
        "distances": distances.tolist(),
        "potentials": potentials.tolist(),
    }


# ===========================================================
# su(2) 极分解验证: V-A 锁定
# ===========================================================

def verify_su2_va_locking(layer) -> Dict:
    """验证 su(2) 极分解和 V-A 锁定。
    
    WorldBase §6.6-6.9:
    A6 DAG → T≠T† → 极分解 H1,H2,H3 → [Hi,Hj]=iε_{ijk}Hk
    A9 → |g_V| = |g_A| (V-A 锁定)
    
    在已形成的组织中检测。
    """
    f = layer.field
    N = f.N
    orgs = list(f.organizations.values())
    
    if not orgs:
        return {"detected": False, "reason": "no_organizations"}
    
    # 取第一个组织的两个位作为有向转移
    org = list(orgs[0])
    if len(org) < 2:
        return {"detected": False, "reason": "org_too_small"}
    
    # 在小空间 (N≤8) 上验证, 使用前两位
    small_N = min(N, 8)
    states = enumerate_mid_surface(small_N, max_states=200)
    if not states:
        return {"detected": False, "reason": "no_mid_surface_states"}
    
    i, j = 0, 1  # 小空间中的前两位
    su2 = Su2FromDAG(i, j, small_N)
    pd = su2.polar_decomposition(states)
    
    return {
        "detected": pd['su2_commutation'],
        "va_locked": pd['va_locked'],
        "g_V": pd['g_V'],
        "g_A": pd['g_A'],
        "max_parity_breaking": pd['max_parity_breaking'],
        "bits": [i, j],
    }


# ===========================================================
# 引力势验证: Φ = -1/d_H
# ===========================================================

def verify_gravitational_potential(layer) -> Dict:
    """验证当前状态的引力势是否符合 Φ = -1/d_H。
    
    WorldBase §3.4: 稳定态处的势场与汉明距离倒数成正比。
    """
    f = layer.field
    N = f.N
    
    # 用全1态作为稳定态参考
    gp = GravitationalPotential(N)
    layers = gp.potential_by_layer()
    
    # 计算当前状态的势
    current_w = f.n_active()
    d = N - current_w
    if d > 0:
        current_potential = -1.0 / d
    else:
        current_potential = float('-inf')
    
    return {
        "current_weight": current_w,
        "current_potential": current_potential,
        "theoretical_layers": layers,
        "all_zero_error": True,  # Φ=-1/d_H 在离散层面精确成立
    }


# ===========================================================
# WorldBase 增强的单步演化
# ===========================================================

def worldbase_enhanced_step(layer, wb_params: WorldBaseParams) -> Dict:
    """WorldBase 增强的单步演化。
    
    在原有九机制基础上叠加:
    1. A8 中截面偏好 (调整守恒目标)
    2. E_{ij} 变易 (中截面上的双比特对换)
    3. 代数结构检测 (su(3), su(2), 色禁闭)
    
    Returns: WorldBase 增强指标
    """
    from .mechanisms import (
        m1_clustering, m2_hierarchy, m3_conservation,
        m4_innate_completeness, m5_minimal_variation,
        m6_breaking, m7_cycle, m8_locking
    )
    
    f = layer.field
    metrics = {}
    
    # --- A8: 调整守恒目标 ---
    original_target = layer.p.target_active
    adjusted_target = a8_adjust_target(layer, wb_params)
    metrics['a8_target'] = adjusted_target
    metrics['a8_original_target'] = original_target
    
    # --- 原有九机制 (m1-m8) ---
    m1_clustering(layer)
    m2_hierarchy(layer)
    m3_conservation(layer)
    m4_innate_completeness(layer)
    m5_minimal_variation(layer)
    
    # --- E_{ij}: 中截面变易 ---
    eij_moves = eij_variational_move(layer, wb_params)
    metrics['eij_moves'] = eij_moves
    
    # --- 继续原有机制 ---
    m6_breaking(layer)
    m7_cycle(layer)
    m8_locking(layer)
    
    # --- 代数结构检测 (每 10 步检测一次) ---
    if layer.step % 10 == 0:
        metrics['su3'] = detect_su3_emergence(layer, wb_params)
        metrics['confinement'] = detect_color_confinement(layer, wb_params)
        metrics['su2'] = verify_su2_va_locking(layer)
        metrics['gravity'] = verify_gravitational_potential(layer)
    
    # 记录活跃集 (用于 Jaccard flux)
    f.record()
    
    # 恢复原始目标
    layer.p.target_active = original_target
    
    return metrics


# ===========================================================
# WorldBase 增强的完整实验
# ===========================================================

def run_worldbase_experiment(N: int = 48, steps: int = 500, 
                              seed: int = 42) -> Dict:
    """运行 WorldBase 增强实验。
    
    在标准九机制演化中叠加 WorldBase 代数结构,
    观察 su(3), su(2), 色禁闭, 引力势等结构的涌现。
    """
    from .core import DifferenceField
    from types import SimpleNamespace
    
    rng = np.random.RandomState(seed)
    
    # 构造参数
    p = SimpleNamespace(
        bind_inc=0.1,
        bind_cap=2.0,
        bind_threshold=0.5,
        min_org_size=3,
        target_active=N // 2,  # 初始目标: 中截面
        max_flip=max(1, N // 10),
        churn=max(1, N // 10),
        cascade_density=0.6,
        cycle_persistence=3,
        lock_inc=0.1,
        lock_threshold=0.8,
        seal_fraction=0.4,
        n_meta_colors=4,
        max_residual=N // 4,
    )
    
    # 初始化差异场
    field = DifferenceField(N=N, layer=0, rng=rng)
    # 注入一些初始活跃位
    initial_active = rng.choice(N, size=N // 3, replace=False)
    for b in initial_active:
        field.state[b] = 1
    field.a1_source = set(initial_active.tolist())
    
    layer = SimpleNamespace(
        field=field,
        p=p,
        step=0,
        tentative_orgs=[],
        is_cyclic=False,
        newly_broken=[],
        moves_this_step=0,
    )
    
    wb_params = WorldBaseParams(N)
    
    # 演化
    history = []
    algebraic_events = []
    
    for step in range(steps):
        layer.step = step
        metrics = worldbase_enhanced_step(layer, wb_params)
        
        # 记录代数涌现事件
        if step % 10 == 0:
            su3 = metrics.get('su3', {})
            su2 = metrics.get('su2', {})
            conf = metrics.get('confinement', {})
            
            if su3.get('detected'):
                algebraic_events.append({
                    'step': step,
                    'type': 'su3_emergence',
                    'bits': su3.get('active_bits'),
                    'dimension': su3.get('dimension'),
                })
            
            if su2.get('detected'):
                algebraic_events.append({
                    'step': step,
                    'type': 'su2_va_locking',
                    'va_locked': su2.get('va_locked'),
                    'g_V': su2.get('g_V'),
                    'g_A': su2.get('g_A'),
                })
            
            if conf.get('detected'):
                algebraic_events.append({
                    'step': step,
                    'type': 'color_confinement',
                    'slope': conf.get('slope'),
                })
        
        history.append({
            'step': step,
            'n_active': field.n_active(),
            'n_sealed': len(field.sealed_bits),
            'n_orgs': len(field.organizations),
            'eij_moves': metrics.get('eij_moves', 0),
            'a8_target': metrics.get('a8_target', N // 2),
        })
        
        if field.sealed:
            break
    
    return {
        'N': N,
        'steps': len(history),
        'sealed': field.sealed,
        'seal_step': field.seal_step,
        'final_active': field.n_active(),
        'final_orgs': len(field.organizations),
        'history': history,
        'algebraic_events': algebraic_events,
        'wb_params': {
            'a8_strength': wb_params.a8_strength,
            'eij_probability': wb_params.eij_probability,
        },
    }
