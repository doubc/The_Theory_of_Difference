"""quick_sealed_cycle_test.py — 测试封口后作为整体参与新一轮九机制循环"""
import torch
import numpy as np
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver
from acl.axioms_v2 import AxiomConstraints

print("=" * 70)
print("测试：封口后作为整体参与新一轮九机制循环")
print("=" * 70)

# ====== 第一轮：N=48，封口 ======
print("\n[Round 1] N=48, T=5000")
evolver1 = SpatialLongRangeEvolver(N=48, total_steps=5000, sample_interval=500)
result1 = evolver1.run(verbose=False)

print(f"  Sealed: {result1['sealed']}")
print(f"  Sealed bits: {result1['sealed_bits']} / 48 = {result1['sealed_ratio']:.0%}")
print(f"  Active bits: {result1['active_bits']}")
print(f"  Final w: {result1['final_state'].sum().item():.0f}")
print(f"  Cycles: {result1['cycle_states']}")
print(f"  Clusters: {len(result1['clusters'])}")

# 获取封口后的状态
final_state = result1['final_state']
active_bits = [i for i in range(48) if i not in evolver1.constraints.sealed_bits]
n_active = len(active_bits)
print(f"  Active bit indices: {active_bits}")

# ====== 第二轮：把封口后的状态映射到更小的系统 ======
print(f"\n[Round 2] 把 {n_active} 个活跃比特作为新系统的全部比特")

# 提取活跃比特的状态
new_state = final_state[active_bits]
print(f"  New state shape: {new_state.shape}")
print(f"  New state w: {new_state.sum().item():.0f}")
print(f"  New system N: {n_active}")

# 用新的 N 运行第二轮
evolver2 = SpatialLongRangeEvolver(N=n_active, total_steps=5000, sample_interval=500)
# 设置初始状态
result2 = evolver2.run(initial_state=new_state, verbose=False)

print(f"  Sealed: {result2['sealed']}")
print(f"  Sealed bits: {result2['sealed_bits']} / {n_active} = {result2['sealed_ratio']:.0%}")
print(f"  Final w: {result2['final_state'].sum().item():.0f}")
print(f"  Cycles: {result2['cycle_states']}")
print(f"  Clusters: {len(result2['clusters'])}")

# ====== 分析 ======
print(f"\n{'=' * 70}")
print("分析：封口后作为整体的九机制循环")
print(f"{'=' * 70}")

# 第一轮的九机制状态
print(f"\n第一轮 (N=48):")
print(f"  聚簇: {len(result1['clusters'])} 个聚类")
print(f"  层级: {'有' if result1['sealed'] else '无'} (封口 = 层级分离)")
print(f"  守恒: inj={result1['total_injected']}, abs={result1['total_absorbed']}")
print(f"  循环: {result1['cycle_states']} 个循环状态")
print(f"  锁定: {'有' if result1['cycle_states'] > 100 else '无'}")
print(f"  封口: {result1['sealed_ratio']:.0%} 比特被冻结")

# 第二轮的九机制状态
print(f"\n第二轮 (N={n_active}):")
print(f"  聚簇: {len(result2['clusters'])} 个聚类")
print(f"  层级: {'有' if result2['sealed'] else '无'}")
print(f"  守恒: inj={result2['total_injected']}, abs={result2['total_absorbed']}")
print(f"  循环: {result2['cycle_states']} 个循环状态")
print(f"  锁定: {'有' if result2['cycle_states'] > 100 else '无'}")
if result2['sealed']:
    print(f"  再次封口: {result2['sealed_ratio']:.0%} 比特被冻结")

# 关键问题：第二轮是否产生了新的涌现？
print(f"\n关键问题：")
print(f"  1. 第二轮是否再次封口? {'是' if result2['sealed'] else '否'}")
print(f"  2. 第二轮的循环数 vs 第一轮: {result2['cycle_states']} vs {result1['cycle_states']}")
print(f"  3. 第二轮的聚类数 vs 第一轮: {len(result2['clusters'])} vs {len(result1['clusters'])}")

# 理论分析
print(f"\n{'=' * 70}")
print("理论分析")
print(f"{'=' * 70}")
print("""
九机制循环：聚簇→层级→守恒→完备性→最小变易→破缺→循环→锁定→自指

当前系统的映射：
- 聚簇 ≈ A1' 绑定聚类
- 层级 ≈ A9 封口（冻结/活跃分离）
- 守恒 ≈ A5 源汇平衡
- 循环 ≈ A7 状态循环
- 锁定 ≈ A6 DAG方向累积
- 自指 ≈ 尚未实现

关键问题：封口后作为整体参与新一轮循环，意味着：
1. 被冻结的 75% 比特 = "低层级"（不再活跃）
2. 被保留的 25% 比特 = "高层级"（活跃自由度）
3. 新一轮循环应该在高层级内部重新运行九机制

当前代码的问题：
- 第二轮重新初始化了 AxiomConstraints，丢失了第一轮的：
  - A6 DAG方向（全部重置为 0）
  - A7 循环历史（全部清空）
  - A1' 绑定强度（重新随机初始化）
  - A5 守恒计数（重置为 0）

这意味着第二轮不是"同一系统的升维"，而是"全新系统的从头开始"。

要实现真正的升维循环，需要：
1. 保留 A6 方向（映射到新比特索引）
2. 保留 A7 循环信息（作为新系统的初始循环历史）
3. 保留 A1' 绑定强度（映射到新比特索引）
4. 保留 A5 守恒计数（作为新系统的初始平衡状态）
5. 新系统的 N = 活跃比特数
6. 新系统的初始状态 = 活跃比特的当前状态
""")
