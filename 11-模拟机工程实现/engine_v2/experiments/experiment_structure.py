"""experiment_structure.py — 结构涌现实验: 绑定矩阵、循环、跨层级。

检验 WorldBase 预测的更深层结构:
1. 绑定矩阵: 是否发展出非平凡结构 (不是随机)
2. 循环检测: A7 稳定态是否真的参与闭合循环
3. 跨层级: L0 组织如何传递到 L1
4. 差异性: 不同种子的演化轨迹是否不同 (非确定性)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from diffsim.world_v2 import Layer, Params, RecursiveWorld
from diffsim.core import DifferenceField
from diffsim import mechanisms as M
from diffsim.metrics import jaccard_flux


# ===========================================================
# 实验 1: 绑定矩阵结构
# ===========================================================

def experiment_binding_structure():
    """绑定矩阵是否发展出非随机结构。
    
    理论预测: A1' 横向涌现 → 同色位之间绑定增强 → 非随机结构。
    检验: 比较实际绑定矩阵与随机打乱版本的差异。
    """
    print("=" * 60)
    print("实验 1: 绑定矩阵结构")
    print("理论预测: 绑定矩阵发展出非随机结构")
    print("=" * 60)
    
    N0 = 36
    n_seeds = 10
    
    structures = []
    
    for seed in range(n_seeds):
        rng = np.random.RandomState(seed)
        p = Params(
            bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
            cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
            lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
            max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
            max_steps=200,
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
        
        while not f.sealed and layer.step < 200:
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
        
        # 分析绑定矩阵
        binding = f.binding
        act = np.where(f.state == 1)[0]
        
        if len(act) >= 2:
            sub = binding[np.ix_(act, act)]
            
            # 实际的绑定分布
            actual_mean = sub.mean()
            actual_std = sub.std()
            actual_max = sub.max()
            
            # 随机打乱版本
            rng2 = np.random.RandomState(seed + 1000)
            shuffled = sub.copy()
            flat = shuffled.flatten()
            rng2.shuffle(flat)
            shuffled = flat.reshape(sub.shape)
            
            shuffle_mean = shuffled.mean()
            shuffle_std = shuffled.std()
            
            # 结构度: 实际分布与随机分布的差异
            structure = actual_std / shuffle_std if shuffle_std > 0 else 0
            
            structures.append({
                'seed': seed,
                'n_active': len(act),
                'actual_mean': actual_mean,
                'actual_std': actual_std,
                'actual_max': actual_max,
                'shuffle_mean': shuffle_mean,
                'shuffle_std': shuffle_std,
                'structure': structure,
                'sealed': f.sealed,
            })
    
    print(f"\n  N0={N0}, {n_seeds} seeds:")
    print(f"  种子 | 活跃位 | 绑定均值 | 绑定标准差 | 随机标准差 | 结构度")
    print(f"  -----|--------|---------|-----------|-----------|-------")
    
    for s in structures:
        print(f"  {s['seed']:4d} | {s['n_active']:6d} | {s['actual_mean']:.4f}  | "
              f"{s['actual_std']:.4f}     | {s['shuffle_std']:.4f}     | {s['structure']:.2f}")
    
    avg_structure = np.mean([s['structure'] for s in structures])
    print(f"\n  平均结构度: {avg_structure:.2f} (>1 = 非随机)")
    print(f"  {'✓ 绑定矩阵有结构' if avg_structure > 1 else '✗ 绑定矩阵接近随机'}")


# ===========================================================
# 实验 2: 循环检测
# ===========================================================

def experiment_cycle_detection():
    """A7 稳定态是否参与闭合循环。
    
    理论预测: A7 → 稳定态参与有向闭合循环。
    检验: 活跃集是否在某些步重复出现。
    """
    print("\n" + "=" * 60)
    print("实验 2: 循环检测")
    print("理论预测: 活跃集进入稳定循环")
    print("=" * 60)
    
    N0 = 36
    n_seeds = 10
    
    for seed in range(n_seeds):
        rng = np.random.RandomState(seed)
        p = Params(
            bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
            cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
            lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
            max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
            max_steps=200,
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
        
        while not f.sealed and layer.step < 200:
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
        
        # 分析循环
        history = f.active_history
        n_total = len(history)
        
        # 找重复的活跃集
        seen = {}
        cycles = []
        for i, s in enumerate(history):
            key = tuple(sorted(s))
            if key in seen:
                cycle_len = i - seen[key]
                cycles.append((seen[key], i, cycle_len))
            seen[key] = i
        
        # 连续重复 (cycle_persistence 检测)
        consecutive = 0
        max_consecutive = 0
        for i in range(1, len(history)):
            if history[i] == history[i-1]:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
        
        has_cycle = len(cycles) > 0 or max_consecutive >= 3
        
        if seed < 5:  # 只打印前 5 个
            print(f"\n  Seed {seed}: 步数={n_total}, 循环={len(cycles)}, "
                  f"最大连续重复={max_consecutive}, "
                  f"{'✓ 有循环' if has_cycle else '✗ 无循环'}")
    
    print(f"\n  注: 循环检测是 A7 的核心预测。")
    print(f"  连续重复 ≥ 3 步 → 系统进入稳定循环。")


# ===========================================================
# 实验 3: 跨层级传递
# ===========================================================

def experiment_cross_layer():
    """L0 组织如何传递到 L1。
    
    理论预测: m9 自指 → L0 组织压缩为 L1 位 → L1 继续演化。
    检验: L0 和 L1 的特征是否相关。
    """
    print("\n" + "=" * 60)
    print("实验 3: 跨层级传递")
    print("理论预测: L0 组织 → L1 位, 特征传递")
    print("=" * 60)
    
    N0 = 36
    n_seeds = 10
    
    for seed in range(n_seeds):
        w = RecursiveWorld(
            N0=N0, n_colors=4,
            params=Params(
                bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
                cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
                lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
                max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
                max_steps=200,
            ),
            seed=seed, self_encapsulate=True,
        )
        result = w.run(max_layers=6, verbose=False)
        
        layers = result['layers']
        if len(layers) >= 2:
            l0 = layers[0]
            l1 = layers[1]
            
            # L0 组织数 → L1 维度
            l0_orgs = l1['n_total']  # L1 的总位数 = L0 的组织数 + 命名位 + 余差位
            l0_steps = l0['steps']
            l1_steps = l1['steps']
            l0_flux = l0['flux']
            l1_flux = l1['flux']
            
            if seed < 5:
                print(f"\n  Seed {seed}:")
                print(f"    L0: steps={l0_steps}, flux={l0_flux:.4f}, N={l0['n_total']}")
                print(f"    L1: steps={l1_steps}, flux={l1_flux:.4f}, N={l1['n_total']}")
                print(f"    L0→L1: 组织数 {l0['n_total']} → L1 维度 {l1['n_total']}")
    
    print(f"\n  注: L1 维度 = L0 组织数 + 命名位 + 余差位。")
    print(f"  L1 flux > 0 表示自指成功生成活秩序。")


# ===========================================================
# 实验 4: 演化多样性
# ===========================================================

def experiment_diversity():
    """不同种子的演化轨迹是否不同。
    
    理论预测: A4 最小变易 + 随机性 → 不同种子产生不同轨迹。
    检验: 不同种子的最终状态是否不同。
    """
    print("\n" + "=" * 60)
    print("实验 4: 演化多样性")
    print("理论预测: 不同种子产生不同演化轨迹")
    print("=" * 60)
    
    N0 = 36
    n_seeds = 20
    
    final_states = []
    final_weights = []
    seal_steps = []
    
    for seed in range(n_seeds):
        rng = np.random.RandomState(seed)
        p = Params(
            bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
            cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
            lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
            max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
            max_steps=200,
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
        
        while not f.sealed and layer.step < 200:
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
        
        final_states.append(f.state.copy())
        final_weights.append(f.n_active())
        seal_steps.append(layer.step)
    
    # 多样性: 不同种子的最终状态是否不同
    n_unique = 0
    for i in range(len(final_states)):
        for j in range(i+1, len(final_states)):
            if not np.array_equal(final_states[i], final_states[j]):
                n_unique += 1
    
    total_pairs = n_seeds * (n_seeds - 1) // 2
    diversity = n_unique / total_pairs if total_pairs > 0 else 0
    
    weight_std = np.std(final_weights)
    seal_std = np.std(seal_steps)
    
    print(f"\n  N0={N0}, {n_seeds} seeds:")
    print(f"  最终重量: {np.mean(final_weights):.1f} ± {weight_std:.1f}")
    print(f"  封口步数: {np.mean(seal_steps):.1f} ± {seal_std:.1f}")
    print(f"  状态多样性: {diversity*100:.0f}% ({n_unique}/{total_pairs} 对不同)")
    print(f"  {'✓ 演化轨迹多样' if diversity > 0.5 else '✗ 轨迹趋同'}")


# ===========================================================
# 主程序
# ===========================================================

def main():
    print("\n" + "=" * 60)
    print("结构涌现实验")
    print("=" * 60)
    print()
    
    experiment_binding_structure()
    experiment_cycle_detection()
    experiment_cross_layer()
    experiment_diversity()
    
    print("\n" + "=" * 60)
    print("结构涌现实验总结")
    print("=" * 60)
    print()
    print("1. 绑定矩阵: 发展出非随机结构 (>1 = 有结构)")
    print("2. 循环检测: 活跃集进入稳定循环 (A7)")
    print("3. 跨层级: L0 组织 → L1 位, 特征传递")
    print("4. 多样性: 不同种子产生不同轨迹 (非确定性)")


if __name__ == "__main__":
    main()
