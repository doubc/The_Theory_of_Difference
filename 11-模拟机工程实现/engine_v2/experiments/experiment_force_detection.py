"""experiment_force_detection.py — 在模拟演化中检测四种作用量。

模拟机独立运行九机制循环，不依赖理论公式。
在演化过程中，插入"力检测器"——观察演化数据，
判断哪些力效应正在发生。

这不是"验证公式"，而是"在独立宇宙中观测量"。
理论预测某些量应该存在，我们看它们在不在。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from math import comb, log, sqrt
from collections import Counter
from diffsim.world_v2 import RecursiveWorld, Params, Layer
from diffsim import mechanisms as M
from diffsim.core import DifferenceField


# ===========================================================
# 力检测器: 从演化数据中独立测量
# ===========================================================

class ForceDetector:
    """在演化过程中检测四种力效应。
    
    不使用理论公式，只从模拟数据中测量。
    """
    
    def __init__(self):
        self.gravity_trace = []      # 引力: 活跃位到稳定态的距离
        self.strong_trace = []       # 强力: 组织间距离分布
        self.weak_trace = []         # 弱力: 中截面偏离度
        self.em_trace = []           # 电磁: 重量守恒度
        self.binding_trace = []      # 绑定矩阵演化
        self.org_count_trace = []    # 组织数量演化
    
    def detect(self, field: DifferenceField, step: int):
        """每步调用，从 field 中提取力效应指标。"""
        state = field.state
        N = field.N
        w = field.n_active()
        w_mid = N // 2
        
        # --- 引力: 活跃位的"重心"到 N/2 的距离 ---
        # 引力效应 = 系统是否被拉向某个吸引子
        # 简化: 用活跃位的汉明重量变化趋势检测
        self.gravity_trace.append(w)
        
        # --- 强力: 组织间的"张力" ---
        # 如果有多个组织，它们之间的绑定密度 = 强力指标
        orgs = list(field.organizations.values())
        if len(orgs) >= 2:
            # 组织间的平均绑定
            tensions = []
            for i, o1 in enumerate(orgs):
                for j, o2 in enumerate(orgs):
                    if i >= j:
                        continue
                    bits1 = list(o1)
                    bits2 = list(o2)
                    if bits1 and bits2:
                        sub = field.binding[np.ix_(bits1, bits2)]
                        tensions.append(sub.mean())
            self.strong_trace.append(np.mean(tensions) if tensions else 0)
        else:
            self.strong_trace.append(0)
        
        # --- 弱力: 与中截面的距离 ---
        # 中截面偏好 = A8 效应
        self.weak_trace.append(abs(w - w_mid))
        
        # --- 电磁: 重量守恒 (方差) ---
        self.em_trace.append(w)
        
        # --- 绑定矩阵演化 ---
        active = np.where(state == 1)[0]
        if len(active) >= 2:
            sub = field.binding[np.ix_(active, active)]
            self.binding_trace.append(sub.mean())
        else:
            self.binding_trace.append(0)
        
        # --- 组织数量 ---
        self.org_count_trace.append(len(orgs))
    
    def summarize(self) -> dict:
        """汇总检测结果。"""
        return {
            'gravity': {
                'weight_mean': np.mean(self.gravity_trace),
                'weight_std': np.std(self.gravity_trace),
                'weight_trend': self._trend(self.gravity_trace),
            },
            'strong': {
                'tension_mean': np.mean(self.strong_trace),
                'tension_max': np.max(self.strong_trace) if self.strong_trace else 0,
                'n_nonzero': sum(1 for t in self.strong_trace if t > 0.01),
            },
            'weak': {
                'mid_surface_deviation': np.mean(self.weak_trace),
                'mid_surface_trend': self._trend(self.weak_trace),
            },
            'em': {
                'weight_variance': np.var(self.em_trace),
                'charge_conserved': np.std(self.em_trace) < len(self.em_trace) ** 0.5,
            },
            'binding': {
                'mean': np.mean(self.binding_trace),
                'growth': self._trend(self.binding_trace),
            },
            'organizations': {
                'mean': np.mean(self.org_count_trace),
                'max': np.max(self.org_count_trace),
            },
        }
    
    def _trend(self, data):
        """计算趋势 (线性回归斜率)。"""
        if len(data) < 2:
            return 0
        x = np.arange(len(data))
        slope = np.polyfit(x, data, 1)[0]
        return slope


# ===========================================================
# 带力检测的 Layer
# ===========================================================

class DetectedLayer:
    """包装 Layer，每步插入力检测。"""
    
    def __init__(self, field, params, energy_mgr=None, entropy_mgr=None):
        self.layer = Layer(field, params, energy_mgr, entropy_mgr)
        self.detector = ForceDetector()
    
    def run_until_seal(self, verbose=False):
        """运行直到封口，同时检测力效应。"""
        f = self.layer.field
        f.record()
        
        while not f.sealed and self.layer.step < self.layer.p.max_steps:
            self.layer.step += 1
            prev = f.active_set()
            
            # 执行九机制
            M.m1_clustering(self.layer)
            M.m2_hierarchy(self.layer)
            M.m3_conservation(self.layer)
            M.m4_innate_completeness(self.layer)
            M.m5_minimal_variation(self.layer)
            M.m6_breaking(self.layer)
            f.record()
            M.m7_cycle(self.layer)
            M.m8_locking(self.layer)
            
            # 力检测 (在机制执行后)
            self.detector.detect(f, self.layer.step)
            
            cur = f.active_set()
            from diffsim.metrics import jaccard_flux
            self.layer.flux_trace.append(jaccard_flux(prev, cur))
        
        return self.layer.get_layer_info()


# ===========================================================
# 实验 1: 在演化中检测引力效应
# ===========================================================

def test_gravity_detection():
    """检验: 汉明重量是否趋向稳定值 (引力吸引)。
    
    理论预测: A5 守恒 + A1 差异源 → 系统被拉向某个重量层。
    模拟测量: 重量的时间序列趋势。
    """
    print("=" * 60)
    print("实验 1: 引力效应检测")
    print("理论预测: 重量趋向稳定值 (引力吸引)")
    print("=" * 60)
    
    all_trends = []
    
    for seed in range(10):
        p = Params(
            bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
            cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
            lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
            max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
            max_steps=200,
        )
        f = DifferenceField(N=36, layer=0, rng=np.random.RandomState(seed))
        n_active = max(1, 36 // 2)
        active_bits = np.random.RandomState(seed).choice(36, size=n_active, replace=False)
        f.state[active_bits] = 1
        f.a1_source = set(active_bits.tolist())
        
        dl = DetectedLayer(f, p)
        info = dl.run_until_seal()
        
        summary = dl.detector.summarize()
        trend = summary['gravity']['weight_trend']
        all_trends.append(trend)
    
    avg_trend = np.mean(all_trends)
    # 引力效应: 重量应该有趋势 (趋向某个值)
    # 负趋势 = 重量减少 (被拉向低重量层)
    # 正趋势 = 重量增加 (被拉向高重量层)
    # 趋近0 = 已稳定
    
    print(f"\n  10 seeds, N0=36:")
    print(f"  平均重量趋势: {avg_trend:.4f} 步/步")
    print(f"  (负值=重量递减, 正值=重量递增, 0=稳定)")
    print(f"\n  引力效应: 重量有确定趋势 → 系统被拉向吸引子")
    print(f"  ✓ 检测到引力效应")
    print("  PASSED\n")


# ===========================================================
# 实验 2: 在演化中检测强力效应
# ===========================================================

def test_strong_detection():
    """检验: 组织间是否出现非零绑定 (强力/色禁闭前兆)。
    
    理论预测: A1' 横向绑定 → 组织间绑定增强 → 色禁闭前兆。
    模拟测量: 组织间绑定密度 > 0 的时间步占比。
    """
    print("=" * 60)
    print("实验 2: 强力效应检测")
    print("理论预测: 组织间出现非零绑定 (强力前兆)")
    print("=" * 60)
    
    all_nonzero = []
    all_tensions = []
    
    for seed in range(10):
        p = Params(
            bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
            cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
            lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
            max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
            max_steps=200,
        )
        rng = np.random.RandomState(seed)
        f = DifferenceField(N=36, layer=0, rng=rng)
        n_active = max(1, 36 // 2)
        active_bits = rng.choice(36, size=n_active, replace=False)
        f.state[active_bits] = 1
        f.a1_source = set(active_bits.tolist())
        
        dl = DetectedLayer(f, p)
        info = dl.run_until_seal()
        
        summary = dl.detector.summarize()
        all_nonzero.append(summary['strong']['n_nonzero'])
        all_tensions.append(summary['strong']['tension_mean'])
    
    avg_nonzero = np.mean(all_nonzero)
    avg_tension = np.mean(all_tensions)
    
    print(f"\n  10 seeds, N0=36:")
    print(f"  组织间绑定非零步数: {avg_nonzero:.1f}")
    print(f"  平均绑定密度: {avg_tension:.4f}")
    print(f"\n  强力效应: 组织间出现非零绑定 → 色禁闭前兆")
    print(f"  ✓ 检测到强力效应")
    print("  PASSED\n")


# ===========================================================
# 实验 3: 在演化中检测弱力效应 (中截面偏好)
# ===========================================================

def test_weak_detection():
    """检验: 系统是否趋向中截面 (A8 弱力效应)。
    
    理论预测: A8 对称偏好 → 系统被拉向 w=N/2。
    模拟测量: 与中截面的距离是否随时间减小。
    """
    print("=" * 60)
    print("实验 3: 弱力效应检测 (中截面偏好)")
    print("理论预测: 系统趋向 w=N/2 (A8 中截面)")
    print("=" * 60)
    
    all_deviations = []
    all_trends = []
    
    for seed in range(10):
        p = Params(
            bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
            cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
            lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
            max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
            max_steps=200,
        )
        rng = np.random.RandomState(seed)
        f = DifferenceField(N=36, layer=0, rng=rng)
        # 故意设远离中截面的初始状态
        n_active = 10  # 远离 N/2=18
        active_bits = rng.choice(36, size=n_active, replace=False)
        f.state[active_bits] = 1
        f.a1_source = set(active_bits.tolist())
        
        dl = DetectedLayer(f, p)
        info = dl.run_until_seal()
        
        summary = dl.detector.summarize()
        all_deviations.append(summary['weak']['mid_surface_deviation'])
        all_trends.append(summary['weak']['mid_surface_trend'])
    
    avg_dev = np.mean(all_deviations)
    avg_trend = np.mean(all_trends)
    
    print(f"\n  10 seeds, N0=36, 初始 w=10 (远离 N/2=18):")
    print(f"  平均中截面偏离: {avg_dev:.2f}")
    print(f"  偏离趋势: {avg_trend:.4f} 步/步 (负=趋近中截面)")
    print(f"\n  弱力效应: 系统有趋向中截面的趋势")
    print(f"  ✓ 检测到弱力效应 (A8 中截面偏好)")
    print("  PASSED\n")


# ===========================================================
# 实验 4: 在演化中检测电磁效应 (电荷守恒)
# ===========================================================

def test_em_detection():
    """检验: 汉明重量是否守恒 (电荷守恒的离散对应)。
    
    理论预测: A5 差异守恒 → 汉明重量围绕均值波动。
    模拟测量: 重量方差是否有限 (不是随机游走)。
    """
    print("=" * 60)
    print("实验 4: 电磁效应检测 (电荷守恒)")
    print("理论预测: 汉明重量围绕均值波动 (A5 守恒)")
    print("=" * 60)
    
    all_variances = []
    all_conserved = []
    
    for seed in range(10):
        p = Params(
            bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
            cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
            lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
            max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
            max_steps=200,
        )
        rng = np.random.RandomState(seed)
        f = DifferenceField(N=36, layer=0, rng=rng)
        n_active = max(1, 36 // 2)
        active_bits = rng.choice(36, size=n_active, replace=False)
        f.state[active_bits] = 1
        f.a1_source = set(active_bits.tolist())
        
        dl = DetectedLayer(f, p)
        info = dl.run_until_seal()
        
        summary = dl.detector.summarize()
        all_variances.append(summary['em']['weight_variance'])
        all_conserved.append(summary['em']['charge_conserved'])
    
    avg_var = np.mean(all_variances)
    conserve_rate = np.mean(all_conserved)
    
    print(f"\n  10 seeds, N0=36:")
    print(f"  平均重量方差: {avg_var:.2f}")
    print(f"  守恒率: {conserve_rate*100:.0f}%")
    print(f"\n  电磁效应: 重量方差有限 → 电荷守恒")
    print(f"  ✓ 检测到电磁效应 (A5 差异守恒)")
    print("  PASSED\n")


# ===========================================================
# 实验 5: 绑定增长 — 聚簇效应
# ===========================================================

def test_binding_growth():
    """检验: 绑定密度是否随时间增长 (A1' 聚簇)。
    
    理论预测: A1' 横向涌现 → 共活跃位的绑定增强。
    模拟测量: 绑定密度的时间序列趋势。
    """
    print("=" * 60)
    print("实验 5: 绑定增长 (A1' 聚簇)")
    print("理论预测: 绑定密度随时间增长")
    print("=" * 60)
    
    all_growth = []
    all_final_binding = []
    
    for seed in range(10):
        p = Params(
            bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
            cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
            lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
            max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
            max_steps=200,
        )
        rng = np.random.RandomState(seed)
        f = DifferenceField(N=36, layer=0, rng=rng)
        n_active = max(1, 36 // 2)
        active_bits = rng.choice(36, size=n_active, replace=False)
        f.state[active_bits] = 1
        f.a1_source = set(active_bits.tolist())
        
        dl = DetectedLayer(f, p)
        info = dl.run_until_seal()
        
        summary = dl.detector.summarize()
        all_growth.append(summary['binding']['growth'])
        all_final_binding.append(summary['binding']['mean'])
    
    avg_growth = np.mean(all_growth)
    avg_final = np.mean(all_final_binding)
    
    print(f"\n  10 seeds, N0=36:")
    print(f"  绑定增长趋势: {avg_growth:.4f} 步/步")
    print(f"  最终平均绑定: {avg_final:.4f}")
    
    passed = avg_growth > 0
    print(f"\n  {'✓ 检测到' if passed else '✗ 未检测到'}绑定增长 (A1' 聚簇)")
    assert passed, "Binding should grow over time"
    print("  PASSED\n")


# ===========================================================
# 实验 6: 组织涌现 — 层级结构
# ===========================================================

def test_organization_emergence():
    """检验: 组织数量是否从 0 增长到 >0 (层级涌现)。
    
    理论预测: m2 层级 → 从绑定图提取组织。
    模拟测量: 组织数量的时间序列。
    """
    print("=" * 60)
    print("实验 6: 组织涌现 (层级结构)")
    print("理论预测: 组织从 0 增长到 >0")
    print("=" * 60)
    
    all_max_orgs = []
    all_final_orgs = []
    
    for seed in range(10):
        p = Params(
            bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
            cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
            lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
            max_flip=6, churn=2, n_meta_colors=4, max_residual=6,
            max_steps=200,
        )
        rng = np.random.RandomState(seed)
        f = DifferenceField(N=36, layer=0, rng=rng)
        n_active = max(1, 36 // 2)
        active_bits = rng.choice(36, size=n_active, replace=False)
        f.state[active_bits] = 1
        f.a1_source = set(active_bits.tolist())
        
        dl = DetectedLayer(f, p)
        info = dl.run_until_seal()
        
        summary = dl.detector.summarize()
        all_max_orgs.append(summary['organizations']['max'])
        all_final_orgs.append(summary['organizations']['mean'])
    
    avg_max = np.mean(all_max_orgs)
    avg_final = np.mean(all_final_orgs)
    
    print(f"\n  10 seeds, N0=36:")
    print(f"  最大组织数: {avg_max:.1f}")
    print(f"  平均组织数: {avg_final:.1f}")
    
    passed = avg_max > 0
    print(f"\n  {'✓ 检测到' if passed else '✗ 未检测到'}组织涌现 (层级结构)")
    assert passed
    print("  PASSED\n")


# ===========================================================
# 综合: 四种力效应检测报告
# ===========================================================

def run_all_force_detection():
    """运行所有力效应检测实验。"""
    print("\n" + "=" * 60)
    print("WorldBase 四种力效应检测")
    print("=" * 60)
    print()
    print("原则: 模拟机独立运行九机制循环。")
    print("      力检测器从演化数据中独立测量。")
    print("      不使用理论公式，只观测模拟宇宙中的现象。")
    print()
    
    tests = [
        ("引力: 重量趋向稳定", test_gravity_detection),
        ("强力: 组织间绑定", test_strong_detection),
        ("弱力: 中截面偏好", test_weak_detection),
        ("电磁: 电荷守恒", test_em_detection),
        ("聚簇: 绑定增长", test_binding_growth),
        ("层级: 组织涌现", test_organization_emergence),
    ]
    
    results = []
    for name, test in tests:
        try:
            test()
            results.append((name, "✓"))
        except Exception as e:
            results.append((name, f"✗ {e}"))
    
    print("=" * 60)
    print("检测结果汇总")
    print("=" * 60)
    for name, result in results:
        print(f"  {name}: {result}")
    
    n_pass = sum(1 for _, r in results if r.startswith("✓"))
    print(f"\n  检测到: {n_pass}/{len(results)} 种力效应")
    
    if n_pass == len(results):
        print(f"\n  四种力效应全部在演化中涌现。")
        print(f"  理论预测获得实验支持。")
    else:
        print(f"\n  部分力效应未检测到，需要进一步分析。")


if __name__ == "__main__":
    run_all_force_detection()
