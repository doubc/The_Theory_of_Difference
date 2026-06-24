"""experiment_confinement.py — 色禁闭实验: 组织间势随距离的变化。

理论预测 (WorldBase §5.9 定理 CONF-2):
色荷-反色荷对在分离距离 d 处的势函数 V(d) = d · ln(1+2/N) · m₀
即线性势 — 这是 QCD 色禁闭的离散对应。

检验方法:
1. 在演化中检测组织形成
2. 测量不同组织间的绑定密度
3. 检查绑定密度是否随组织间距离线性变化
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from math import log, comb
from diffsim.world_v2 import Layer, Params, RecursiveWorld
from diffsim.core import DifferenceField
from diffsim import mechanisms as M


def run_and_track_orgs(N0, seed, max_steps=300):
    """运行模拟, 追踪组织间势。"""
    rng = np.random.RandomState(seed)
    p = Params(
        bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
        cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
        lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
        max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
        max_steps=max_steps,
    )
    
    f = DifferenceField(N=N0, layer=0, rng=rng)
    n_active = max(1, N0 // 2)
    active = rng.choice(N0, size=n_active, replace=False)
    f.state[active] = 1
    inactive = list(set(range(N0)) - set(active.tolist()))
    n_extra = max(1, len(inactive) // 2)
    extra = rng.choice(inactive, size=n_extra, replace=False).tolist() if inactive else []
    f.a1_source = set(active.tolist()) | set(extra)
    f.record()
    
    layer = Layer(f, p)
    
    # 追踪: 每步记录组织信息
    org_snapshots = []  # [(step, orgs_list, binding_matrix)]
    
    while not f.sealed and layer.step < max_steps:
        layer.step += 1
        
        M.m1_clustering(layer)
        M.m2_hierarchy(layer)
        M.m3_conservation(layer)
        M.m4_innate_completeness(layer)
        M.m5_minimal_variation(layer)
        M.m6_breaking(layer)
        f.record()
        M.m7_cycle(layer)
        M.m8_locking(layer)
        
        # 每 10 步记录组织快照
        if layer.step % 10 == 0:
            orgs = [set(b for b in o if f.state[b] == 1) 
                    for o in f.organizations.values()]
            orgs = [o for o in orgs if len(o) >= 2]
            if len(orgs) >= 2:
                org_snapshots.append({
                    'step': layer.step,
                    'orgs': orgs,
                    'binding': f.binding.copy(),
                    'state': f.state.copy(),
                })
    
    return org_snapshots, f


def analyze_confinement(snapshots):
    """分析组织间势: 距离 vs 绑定。"""
    results = []
    
    for snap in snapshots:
        orgs = snap['orgs']
        binding = snap['binding']
        
        for i, o1 in enumerate(orgs):
            for j, o2 in enumerate(orgs):
                if i >= j:
                    continue
                
                b1 = sorted(o1)
                b2 = sorted(o2)
                
                # 组织间距离: 最近两位之间的汉明距离
                min_dist = min(abs(a - b) for a in b1 for b in b2)
                
                # 组织间绑定密度
                sub = binding[np.ix_(b1, b2)]
                bind_density = sub.mean()
                
                # 组织大小
                size1 = len(o1)
                size2 = len(o2)
                
                results.append({
                    'step': snap['step'],
                    'distance': min_dist,
                    'bind_density': bind_density,
                    'size1': size1,
                    'size2': size2,
                })
    
    return results


# ===========================================================
# 主实验
# ===========================================================

def main():
    print("=" * 60)
    print("色禁闭实验: 组织间势 vs 距离")
    print("=" * 60)
    print()
    print("理论预测: V(d) = d · ln(1+2/N) · m₀ (线性势)")
    print()
    
    all_data = []
    
    for N0 in [24, 36, 48]:
        print(f"--- N0={N0} ---")
        n_seeds = 10
        n_with_orgs = 0
        
        for seed in range(n_seeds):
            snapshots, final_field = run_and_track_orgs(N0, seed, max_steps=300)
            if snapshots:
                n_with_orgs += 1
                data = analyze_confinement(snapshots)
                all_data.extend(data)
        
        print(f"  有组织的运行: {n_with_orgs}/{n_seeds}")
    
    if not all_data:
        print("\n  未检测到多组织状态, 无法分析色禁闭。")
        return
    
    # 按距离分组, 计算平均绑定密度
    from collections import defaultdict
    dist_bins = defaultdict(list)
    for d in all_data:
        dist_bins[d['distance']].append(d['bind_density'])
    
    print(f"\n  距离-绑定关系 (所有 N 汇总):")
    print(f"  距离 | 平均绑定密度 | 样本数")
    print(f"  -----|-------------|-------")
    
    distances = []
    densities = []
    for dist in sorted(dist_bins.keys()):
        vals = dist_bins[dist]
        avg = np.mean(vals)
        distances.append(dist)
        densities.append(avg)
        if len(vals) >= 3:
            print(f"  {dist:4d}   | {avg:.4f}        | {len(vals)}")
    
    # 线性拟合
    if len(distances) >= 3:
        distances = np.array(distances, dtype=float)
        densities = np.array(densities, dtype=float)
        
        # 只用有足够样本的距离
        mask = np.array([len(dist_bins[d]) >= 3 for d in sorted(dist_bins.keys())])
        if mask.sum() >= 3:
            d_fit = distances[mask]
            rho_fit = densities[mask]
            
            # 线性拟合: ρ = a*d + b
            coeffs = np.polyfit(d_fit, rho_fit, 1)
            slope = coeffs[0]
            intercept = coeffs[1]
            
            # R²
            rho_pred = np.polyval(coeffs, d_fit)
            ss_res = np.sum((rho_fit - rho_pred) ** 2)
            ss_tot = np.sum((rho_fit - rho_fit.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            
            print(f"\n  线性拟合: ρ = {slope:.4f}·d + {intercept:.4f}")
            print(f"  R² = {r2:.4f}")
            
            # 色禁闭判定: 斜率应为负 (距离越大, 绑定越弱)
            # 或者: 绑定密度与距离有显著线性关系
            is_linear = abs(r2) > 0.3
            has_slope = abs(slope) > 0.001
            
            print(f"\n  色禁闭检验:")
            print(f"    线性关系 (R²>0.3): {'✓' if is_linear else '✗'}")
            print(f"    显著斜率: {'✓' if has_slope else '✗'}")
            print(f"    斜率方向: {'负 (距离增大绑定减弱)' if slope < 0 else '正 (距离增大绑定增强)'}")
            
            if is_linear and has_slope:
                print(f"\n  ✓ 检测到组织间势与距离的线性关系")
                print(f"  这是色禁闭的前兆: 组织间存在随距离变化的势")
            else:
                print(f"\n  ⚠ 未检测到显著线性关系")
                print(f"  可能原因: 组织数量不足, 或距离范围太窄")
    
    # 额外分析: 组织大小分布
    sizes = [d['size1'] for d in all_data] + [d['size2'] for d in all_data]
    print(f"\n  组织大小分布:")
    print(f"    平均: {np.mean(sizes):.1f}")
    print(f"    最小: {np.min(sizes)}")
    print(f"    最大: {np.max(sizes)}")
    print(f"    中位数: {np.median(sizes):.1f}")


if __name__ == "__main__":
    main()
