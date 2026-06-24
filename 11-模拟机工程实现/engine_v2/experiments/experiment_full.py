"""experiment_full.py — 完整模拟机实验：独立检验 WorldBase 理论预测。

实验 A: 自指闭环基础检验 (P1)
实验 B: 力效应涌现检验 (P2-P7)
实验 C: 封口机制检验 (P8)
实验 D: 规模效应 (N 依赖)

运行后自动保存结果到 results/ 目录。
"""
import sys, os, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from math import comb, log, sqrt
from diffsim.world_v2 import RecursiveWorld, Params
from diffsim.core import DifferenceField
from diffsim import mechanisms as M
from diffsim.metrics import jaccard_flux


# ===========================================================
# 工具函数
# ===========================================================

def make_params(max_steps=200):
    return Params(
        bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
        cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
        lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
        max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
        max_steps=max_steps,
    )

def make_world(N0, seed, self_encapsulate=True, max_steps=200):
    return RecursiveWorld(
        N0=N0, n_colors=4, params=make_params(max_steps),
        seed=seed, self_encapsulate=self_encapsulate,
    )


# ===========================================================
# 力检测器
# ===========================================================

class ForceDetector:
    """从演化数据中独立测量力效应。"""
    
    def __init__(self, N):
        self.N = N
        self.w_mid = N // 2
        self.weights = []
        self.tensions = []      # 组织间绑定
        self.mid_deviations = [] # 中截面偏离
        self.bindings = []       # 活跃位间绑定
        self.org_counts = []     # 组织数量
        self.sealed = False
        self.seal_step = None
    
    def detect(self, field, step):
        w = field.n_active()
        self.weights.append(w)
        self.mid_deviations.append(abs(w - self.w_mid))
        
        # 组织间绑定
        orgs = list(field.organizations.values())
        self.org_counts.append(len(orgs))
        
        if len(orgs) >= 2:
            tensions = []
            for i, o1 in enumerate(orgs):
                for j, o2 in enumerate(orgs):
                    if i >= j:
                        continue
                    b1, b2 = list(o1), list(o2)
                    if b1 and b2:
                        tensions.append(field.binding[np.ix_(b1, b2)].mean())
            self.tensions.append(np.mean(tensions) if tensions else 0)
        else:
            self.tensions.append(0)
        
        # 活跃位间绑定
        act = np.where(field.state == 1)[0]
        if len(act) >= 2:
            self.bindings.append(field.binding[np.ix_(act, act)].mean())
        else:
            self.bindings.append(0)
        
        if field.sealed and not self.sealed:
            self.sealed = True
            self.seal_step = step
    
    def trend(self, data):
        if len(data) < 3:
            return 0
        x = np.arange(len(data))
        return np.polyfit(x, data, 1)[0]
    
    def report(self):
        w = np.array(self.weights)
        return {
            'gravity_trend': self.trend(self.weights),
            'strong_nonzero_steps': sum(1 for t in self.tensions if t > 0.01),
            'strong_mean': np.mean(self.tensions),
            'weak_trend': self.trend(self.mid_deviations),
            'weak_mean_deviation': np.mean(self.mid_deviations),
            'em_variance': np.var(w),
            'binding_trend': self.trend(self.bindings),
            'binding_mean': np.mean(self.bindings),
            'org_max': max(self.org_counts) if self.org_counts else 0,
            'org_mean': np.mean(self.org_counts),
            'sealed': self.sealed,
            'seal_step': self.seal_step,
            'n_steps': len(self.weights),
        }


# ===========================================================
# 带检测的单次模拟
# ===========================================================

def run_detected(N0, seed, self_encapsulate=True, max_steps=200):
    """运行一次模拟，带力检测。"""
    from diffsim.world_v2 import Layer
    from diffsim.energy_v2 import EnergyManager, EnergyConfig
    
    rng = np.random.RandomState(seed)
    p = make_params(max_steps)
    
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
    detector = ForceDetector(N0)
    
    while not f.sealed and layer.step < max_steps:
        layer.step += 1
        prev = f.active_set()
        
        M.m1_clustering(layer)
        M.m2_hierarchy(layer)
        M.m3_conservation(layer)
        M.m4_innate_completeness(layer)
        M.m5_minimal_variation(layer)
        M.m6_breaking(layer)
        f.record()
        M.m7_cycle(layer)
        M.m8_locking(layer)
        
        detector.detect(f, layer.step)
    
    return detector.report()


# ===========================================================
# 实验 A: 自指闭环基础检验 (P1)
# ===========================================================

def experiment_A():
    """P1: 自指闭环 vs 被动投影。"""
    print("=" * 60)
    print("实验 A: 自指闭环基础检验 (P1)")
    print("=" * 60)
    
    N0 = 36
    n_seeds = 20
    depths_self, depths_passive = [], []
    fluxes_self, fluxes_passive = [], []
    
    for seed in range(n_seeds):
        r1 = run_detected(N0, seed, self_encapsulate=True, max_steps=300)
        r2 = run_detected(N0, seed, self_encapsulate=False, max_steps=300)
        
        # 涌现深度用 RecursiveWorld 测量
        w1 = make_world(N0, seed, True, 300)
        w2 = make_world(N0, seed, False, 300)
        res1 = w1.run(max_layers=6, verbose=False)
        res2 = w2.run(max_layers=6, verbose=False)
        
        depths_self.append(res1['depth'])
        depths_passive.append(res2['depth'])
        
        if len(res1['layers']) >= 2:
            fluxes_self.append(res1['layers'][1]['flux'])
        if len(res2['layers']) >= 2:
            fluxes_passive.append(res2['layers'][1]['flux'])
    
    avg_ds = np.mean(depths_self)
    avg_dp = np.mean(depths_passive)
    avg_fs = np.mean(fluxes_self) if fluxes_self else 0
    avg_fp = np.mean(fluxes_passive) if fluxes_passive else 0
    
    print(f"\n  N0={N0}, {n_seeds} seeds:")
    print(f"  涌现深度: 自指={avg_ds:.2f}, 被动={avg_dp:.2f}")
    print(f"  L1 flux:  自指={avg_fs:.4f}, 被动={avg_fp:.4f}")
    
    p1a = avg_ds > avg_dp
    p1b = avg_fs > 0.05
    p1c = avg_fp < 0.05
    
    print(f"\n  P1a 深度自指>被动: {'✓' if p1a else '✗'}")
    print(f"  P1b L1 flux>0 (活秩序): {'✓' if p1b else '✗'}")
    print(f"  P1c 被动 flux≈0 (死秩序): {'✓' if p1c else '✗'}")
    
    return {'P1a': p1a, 'P1b': p1b, 'P1c': p1c,
            'depth_self': avg_ds, 'depth_passive': avg_dp,
            'flux_self': avg_fs, 'flux_passive': avg_fp}


# ===========================================================
# 实验 B: 力效应涌现检验 (P2-P7)
# ===========================================================

def experiment_B():
    """P2-P7: 四种力效应 + 聚簇 + 层级。"""
    print("\n" + "=" * 60)
    print("实验 B: 力效应涌现检验 (P2-P7)")
    print("=" * 60)
    
    N0 = 36
    n_seeds = 10
    
    all_reports = []
    for seed in range(n_seeds):
        r = run_detected(N0, seed, self_encapsulate=True, max_steps=200)
        all_reports.append(r)
    
    # 汇总
    def avg(key):
        return np.mean([r[key] for r in all_reports])
    
    gravity_trend = avg('gravity_trend')
    strong_nz = avg('strong_nonzero_steps')
    strong_mean = avg('strong_mean')
    weak_trend = avg('weak_trend')
    weak_mean = avg('weak_mean_deviation')
    em_var = avg('em_variance')
    bind_trend = avg('binding_trend')
    bind_mean = avg('binding_mean')
    org_max = avg('org_max')
    org_mean = avg('org_mean')
    
    print(f"\n  N0={N0}, {n_seeds} seeds:")
    print(f"  P2 引力: 重量趋势={gravity_trend:.4f}")
    print(f"  P3 强力: 非零步={strong_nz:.1f}, 平均={strong_mean:.4f}")
    print(f"  P4 弱力: 偏离趋势={weak_trend:.4f}, 平均偏离={weak_mean:.2f}")
    print(f"  P5 电磁: 重量方差={em_var:.2f}")
    print(f"  P6 聚簇: 绑定趋势={bind_trend:.4f}, 平均={bind_mean:.4f}")
    print(f"  P7 层级: 最大组织={org_max:.1f}, 平均={org_mean:.1f}")
    
    p2 = abs(gravity_trend) > 0.01
    p3 = strong_nz > 0
    p4 = weak_trend < 0  # 趋向中截面
    p5 = em_var < N0  # 方差有限
    p6 = bind_trend > 0
    p7 = org_max > 0
    
    print(f"\n  P2 引力效应: {'✓' if p2 else '✗'}")
    print(f"  P3 强力效应: {'✓' if p3 else '✗'}")
    print(f"  P4 弱力效应: {'✓' if p4 else '✗'}")
    print(f"  P5 电磁效应: {'✓' if p5 else '✗'}")
    print(f"  P6 聚簇效应: {'✓' if p6 else '✗'}")
    print(f"  P7 层级涌现: {'✓' if p7 else '✗'}")
    
    return {'P2': p2, 'P3': p3, 'P4': p4, 'P5': p5, 'P6': p6, 'P7': p7,
            'gravity_trend': gravity_trend, 'strong_nz': strong_nz,
            'weak_trend': weak_trend, 'em_var': em_var,
            'bind_trend': bind_trend, 'org_max': org_max}


# ===========================================================
# 实验 C: 封口机制检验 (P8)
# ===========================================================

def experiment_C():
    """P8: 封口涌现。"""
    print("\n" + "=" * 60)
    print("实验 C: 封口机制检验 (P8)")
    print("=" * 60)
    
    N0 = 36
    n_seeds = 20
    
    sealed_count = 0
    seal_steps = []
    
    for seed in range(n_seeds):
        w = make_world(N0, seed, True, 300)
        res = w.run(max_layers=6, verbose=False)
        
        l0 = res['layers'][0]
        if l0['sealed']:
            sealed_count += 1
            seal_steps.append(l0['steps'])
    
    seal_rate = sealed_count / n_seeds
    avg_seal = np.mean(seal_steps) if seal_steps else 0
    
    print(f"\n  N0={N0}, {n_seeds} seeds:")
    print(f"  封口率: {sealed_count}/{n_seeds} ({seal_rate*100:.0f}%)")
    print(f"  平均封口步数: {avg_seal:.1f}")
    
    p8 = seal_rate > 0.5
    print(f"\n  P8 封口涌现: {'✓' if p8 else '✗'}")
    
    return {'P8': p8, 'seal_rate': seal_rate, 'avg_seal_steps': avg_seal}


# ===========================================================
# 实验 D: 规模效应
# ===========================================================

def experiment_D():
    """规模效应: N 对涌现质量的影响。"""
    print("\n" + "=" * 60)
    print("实验 D: 规模效应 (N 依赖)")
    print("=" * 60)
    
    n_seeds = 10
    results = {}
    
    for N0 in [16, 24, 36, 48]:
        depths = []
        fluxes = []
        sealed = 0
        
        for seed in range(n_seeds):
            w = make_world(N0, seed, True, 300)
            res = w.run(max_layers=6, verbose=False)
            depths.append(res['depth'])
            if len(res['layers']) >= 2:
                fluxes.append(res['layers'][1]['flux'])
            if res['layers'][0]['sealed']:
                sealed += 1
        
        results[N0] = {
            'depth': np.mean(depths),
            'flux': np.mean(fluxes) if fluxes else 0,
            'seal_rate': sealed / n_seeds,
        }
    
    print(f"\n  {n_seeds} seeds per N:")
    print(f"  N0 | 深度  | L1 flux | 封口率")
    print(f"  ---|-------|---------|-------")
    for N0, r in results.items():
        print(f"  {N0:2d} | {r['depth']:.2f}  | {r['flux']:.4f}  | {r['seal_rate']*100:.0f}%")
    
    # 规模效应: N 越大，涌现越深
    depths = [results[N]['depth'] for N in sorted(results.keys())]
    scale_effect = depths[-1] > depths[0]
    
    print(f"\n  规模效应: N 越大涌现越深 → {'✓' if scale_effect else '✗'}")
    
    return {'scale_effect': scale_effect, 'results': results}


# ===========================================================
# 主程序
# ===========================================================

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("\n" + "=" * 60)
    print("WorldBase 模拟机完整实验")
    print(f"时间: {timestamp}")
    print("=" * 60)
    print()
    print("原则: 模拟机独立运行，理论对它做预测，")
    print("      我们跑模拟看预测对不对。")
    print()
    
    # 运行所有实验
    res_A = experiment_A()
    res_B = experiment_B()
    res_C = experiment_C()
    res_D = experiment_D()
    
    # 汇总
    all_results = {
        'timestamp': timestamp,
        'experiment_A': res_A,
        'experiment_B': res_B,
        'experiment_C': res_C,
        'experiment_D': res_D,
    }
    
    print("\n" + "=" * 60)
    print("最终汇总")
    print("=" * 60)
    
    predictions = {
        'P1a 自指深度>被动': res_A['P1a'],
        'P1b 自指flux>0': res_A['P1b'],
        'P1c 被动flux≈0': res_A['P1c'],
        'P2 引力效应': res_B['P2'],
        'P3 强力效应': res_B['P3'],
        'P4 弱力效应': res_B['P4'],
        'P5 电磁效应': res_B['P5'],
        'P6 聚簇效应': res_B['P6'],
        'P7 层级涌现': res_B['P7'],
        'P8 封口涌现': res_C['P8'],
    }
    
    for name, passed in predictions.items():
        print(f"  {name}: {'✓' if passed else '✗'}")
    
    n_pass = sum(1 for v in predictions.values() if v)
    n_total = len(predictions)
    print(f"\n  通过: {n_pass}/{n_total}")
    
    if n_pass == n_total:
        print(f"\n  所有预测通过。理论获得实验支持。")
    else:
        failed = [k for k, v in predictions.items() if not v]
        print(f"\n  失败: {failed}")
        print(f"  需要检查理论推导。")
    
    # 保存结果
    os.makedirs('results', exist_ok=True)
    outfile = f'results/experiment_{timestamp}.json'
    with open(outfile, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  结果已保存: {outfile}")
    
    return n_pass == n_total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
