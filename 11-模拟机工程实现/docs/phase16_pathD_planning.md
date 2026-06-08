# Phase 16 Path D: 多层同时演化 (Concurrent Multi-layer Evolution)

## 背景与动机

### Phase 16 回顾

| Path | Result | 核心教训 |
|------|--------|----------|
| A (开放系统) | ❌ 全部失败 | 环境扰动不足以打破"死秩序"刚性 |
| B (非局部交互) | ⚠️ 1/3 成功 | 全局场有效(B2)，但均匀化代价 |
| C (可变阈值) | ❌ 部分拒绝 | 解封后不重新密封，核心张力不可调和 |

### 根本问题

所有 Path A/B/C 实验中，**L0 和 L1 的演化是串行的**：

```
L0 演化 → L0 密封（死秩序） → 映射 L1 约束 → L1 演化 → L1 密封
```

L1 启动时，L0 已经"死了"（拓扑不变量）。L1 的演化空间完全被 L0 的冻结结构约束。即使有反馈（exp_169），也只是在已冻结的 L0 上做微小扰动。

**Path D 的核心想法**: 让 L0、L1、L2 同时演化，互相影响，在**系统还未达到稳态**时就开始跨层耦合。这模拟了现实世界多层系统（生物、社会、认知）的共演过程。

---

## D1: 并行更新 (Parallel Update)

### 核心机制

在 L0 的演化过程中（还未密封），提前启动 L1 甚至 L2。所有层同步更新。

```
时间 t=0:    L0 启动
时间 t=τ₁:    L0 演化中，L1 启动（基于当前 L0 的部分结构）
时间 t=τ₂:    L0、L1 演化中，L2 启动（基于当前 L1 的部分结构）
时间 t=τ₃+:  所有三层同步演化
```

### 与串行版的区别

| 特征 | 串行 (Phase 15 C / exp_169) | 并行 (Path D1) |
|------|---------------------------|-----------------|
| L1 启动时机 | L0 完全密封后 | L0 演化中 (τ₁ << seal_step) |
| L0→L1 映射 | 一次性，基于最终结构 | 多次/连续更新 |
| L1→L0 反馈 | 可选，L1 密封后一次性 | 实时，每步 |
| L2 启动 | 未实现 | 在 L1 演化中启动 |

### 实现方案

#### 修改 CrossLayerEvolver

当前版本:
```python
# Phase 15 C (serial)
def run(self):
    l0_result = self.l0_evolver.run()           # L0 → seal
    self.l1_constraints = mapper.map(l0_result)  # map once
    l1_evolver.apply_constraints(self.l1_constraints)
    l1_result = self.l1_evolver.run()            # L1 → seal
    apply_feedback()                              # optional
```

Path D1 版本:
```python
# Phase 16 D1 (parallel)
def run_parallel(self, t_lag_l1=100, t_lag_l2=300, total_steps=5000):
    # Initialize all three evolvers
    l0 = SpatialLongRangeEvolver(N=N0)
    l1 = Layer1Evolver(N=N1)  # starts later
    l2 = Layer1Evolver(N=N2)  # starts even later
    
    for step in range(total_steps):
        # Step 1: Update L0 (always active)
        l0_state = l0.step()
        
        # Step 2: If L1 active, update L1
        if step >= t_lag_l1:
            # Map L0's current (partial) structure to L1
            if step % l1_update_interval == 0:
                constraints = mapper.map_live(l0_state, l0.constraints)
                l1.update_constraints(constraints)
            l1_state = l1.step()
        
        # Step 3: If L2 active, update L2
        if step >= t_lag_l2:
            if step % l2_update_interval == 0:
                constraints_l2 = mapper.map_live(l1_state, l1.constraints)
                l2.update_constraints(constraints_l2)
            l2_state = l2.step()
        
        # Step 4: Real-time feedback
        if step >= t_lag_l1:
            # L1 modulates L0 transition probabilities
            l0.apply_live_feedback(l1_state, strength=feedback_alpha)
        if step >= t_lag_l2:
            # L2 modulates L1 transition probabilities
            l1.apply_live_feedback(l2_state, strength=feedback_alpha/2)
```

#### 关键设计决策

1. **映射频率** (`l1_update_interval`): 每 N 步重新计算 L0→L1 约束。太频繁会导致 L1 不稳定，太稀疏则失去并行优势。推荐 `l1_update_interval=200`。

2. **实时反馈强度** (`feedback_alpha`): L1→L0 反馈的强度。串行版一次性扰动 10% 比特；并行版每步施加微小调制（α=0.01~0.05）。

3. **L2 的 L1 约束**: L2 的 hierarchy_map 基于 L1 的实时结构。在 L1 未密封时，L1 的结构可能不清晰，映射质量低。需要弱化约束（低 binding_bias）。

#### 实验配置

| Config | t_lag_l1 | t_lag_l2 | L1 Update Freq | Feedback Alpha |
|--------|----------|----------|----------------|----------------|
| baseline_serial | N/A (密封后) | N/A | 一次 | 0 (仅 exp_169 style) |
| d1_early | 50 | 150 | 200 | 0.05 |
| d1_medium | 200 | 500 | 200 | 0.03 |
| d1_late | 500 | 1000 | 200 | 0.03 |
| d1_continuous | 50 | 150 | 50 | 0.10 |
| d1_feedback_only | 50 | 150 | ∞ (不更新约束) | 0.10 |

#### 假设 H16-D1

**并行更新能使多层系统产生 L2 涌现**（即 L2 的密封模式具有 L2-level 结构，而不仅仅是 L1 的副本）。

**成功判据**:
1. ✅ L2 密封率 > 0%（必须能密封）
2. ✅ L2 的结构熵 < 0.5（非随机）
3. ✅ L2 的反射度 < 0.9（不是简单复制 L1）
4. ✅ 至少 3/6 configs 满足以上三条

---

## D2: 增强跨层反馈 (Enhanced Cross-layer Feedback)

### 核心机制

在 D1 的基础上，增强反馈的丰富性。当前反馈（exp_169）仅做比特扰动；增强反馈修改底层动力学参数。

### 反馈类型

#### 1. 约束调制 (Constraint Modulation)

当前: L1→L0 扰动 10% 比特值（暴力翻转）

增强: L1→L0 调节 L0 的约束参数:
- **binding_strength**: L1 指示 L0 中哪些比特更"重要"（增加 binding_strength 使其更稳定）
- **direction**: L1 的层次结构改变 L0 的 direction 偏好
- **hamming_weight_target**: L1 密封 HW 影响 L0 的目标 HW

#### 2. 过渡矩阵调制 (Transition Matrix Modulation)

在 `SpatialLongRangeEvolver` 中，差异计算使用 `comparison_matrix`。L1 可以调整这个矩阵。

```python
# L2 → L1 transition matrix modulation
def modulate_transition_matrix(l1_matrix, l2_state, strength=0.1):
    """L2's structure modulates L1's difference calculation.
    
    If L2 is highly structured (low entropy), L1's comparison matrix
    becomes more conservative (fewer flips). 
    If L2 is chaotic (high entropy), L1 becomes more exploratory.
    """
    l2_entropy = compute_state_entropy(l2_state)
    modulation = 1.0 - strength * (l2_entropy - 0.5) * 2  # range [1-strength, 1+strength]
    return l1_matrix * modulation
```

#### 3. 拓扑重组 (Topology Reorganization)

最激进的反馈: L1 的密封结构改变 L0 的交互拓扑。
- 如果 L1 发现某组比特形成稳定 cluster，L0 中对应比特建立长程连接
- 等同于 L1"反馈"创建了 L0 的非局部连接

```python
def reorganize_l0_topology(l0, l1_state, l1_constraints, step):
    """L1's sealing pattern creates long-range connections in L0.
    
    When L1 hierarchy bits are all 1 (activated cluster),
    the corresponding L0 bits get a new long-range connection.
    """
    n_connections = min(5, step // 1000 + 1)  # grows over time
    hierarchy_bits_1 = l1_state[l1_constraints.hierarchy_bits]
    active_clusters = (hierarchy_bits_1 > 0.5).nonzero()
    
    for _ in range(n_connections):
        if len(active_clusters) >= 2:
            src, dst = random.sample(active_clusters, 2)
            l0.add_long_range_connection(src.item(), dst.item())
```

### 实验配置

| Config | Feedback Type | Strength | Notes |
|--------|--------------|----------|-------|
| d2_baseline | 仅扰动 (exp_169) | 0.1 | 对照 |
| d2_constraint | 约束调制 | 0.05 | Binding + direction |
| d2_matrix | 过渡矩阵调制 | 0.10 | 差异计算调整 |
| d2_topology | 拓扑重组 | 动态 | 随时间增加 |
| d2_full | 全部三种 | 组合 | 最强耦合 |

#### 假设 H16-D2

**增强跨层反馈能使多层系统产生 L2 涌现**。

**成功判据** (同 H16-D1):
1. ✅ L2 密封率 > 0%
2. ✅ L2 结构熵 < 0.5
3. ✅ L2 反射度 < 0.9
4. ✅ 至少 2/5 configs 满足

---

## D3: 竞争与协同 (Competition & Synergy)

### 核心机制

现实世界的多层系统（生态系统、神经网络、社会）中，层次之间的关系是竞争与协同并存的。层次间争夺有限资源（比特、能量），但协同产生整体涌现。

### 资源分配模型

引入有限资源池 `Resource(t)`:
```python
Resource(t) = R_total * (1 - decay(t))  # 随时间衰减
```

资源分配:
- L0 获得 `α₀ * Resource(t)` 比特
- L1 获得 `α₁ * Resource(t)` 比特
- L2 获得 `α₂ * Resource(t)` 比特
- `α₀ + α₁ + α₂ = 1`

**竞争机制**: 如果 L1 结构熵低（高质量），α₁ 增加，α₀ 减少
**协同机制**: 如果 L0 结构熵低（稳定），α₁ 获得 +10% 额外资源

### 适应性层级分配

在 D1/D2 中，hierarchy_bits 数量是固定的。在 D3 中，**hierarchy_bits 数量动态调整**:

```python
def adaptive_hierarchy_allocation(l0, l1, l2, step, max_bits=48):
    """Dynamically allocate hierarchy bits across layers.
    
    Rule:
    - L0 hierarchy_bits = max(8, max_bits * (1 - l1_structure_quality))
    - L1 hierarchy_bits = max(8, max_bits * l1_structure_quality * (1 - l2_structure_quality))
    - L2 hierarchy_bits = max(4, max_bits * l1_structure_quality * l2_structure_quality)
    """
    # Compute structure quality (inverse entropy)
    l1_quality = 1.0 - min(l1_entropy, 1.0)
    l2_quality = 1.0 - min(l2_entropy, 1.0) if l2_active else 0.0
    
    # Allocate
    l2_bits = max(4, int(max_bits * l1_quality * l2_quality * 2))
    l1_bits = max(8, int(max_bits * l1_quality * 0.5))
    l0_bits = max_bits - l1_bits - l2_bits
    l0_bits = max(8, l0_bits)
    
    return l0_bits, l1_bits, l2_bits
```

### 层次间信号传递

L0 的信号可以作为 L1 的"输入"，L1 的信号可以作为 L2 的"输入"。这种信号传递在神经网络中就是前馈过程。

```python
def signal_coupling(l0_state, l1_state, coupling_strength=0.1):
    """L0 signal → partial L1 input.
    
    L1 bits that correspond to active L0 clusters get a bias toward their state.
    """
    for l1_idx, l0_cluster in l1_hierarchy_map.items():
        if l0_cluster >= 0:
            # Average L0 state in this cluster
            l0_avg = l0_state[l0_cluster_members[l0_cluster]].mean()
            bias = coupling_strength * (l0_avg - 0.5) * 2  # [-coupling, +coupling]
            l1_state[l1_idx] += bias
            l1_state[l1_idx] = torch.clamp(l1_state[l1_idx], 0, 1)
```

### 实验配置

| Config | Resource Model | Coupling | Topology | Notes |
|--------|---------------|----------|----------|-------|
| d3_baseline | 固定分配 (D1) | 无 | 固定 | 对照 |
| d3_competitive | α 竞争 | 无 | 固定 | 资源争夺 |
| d3_synergistic | α 固定 + 奖励 | 信号耦合 | 固定 | 协同 |
| d3_adaptive | 自适应 | 信号耦合 | 自适应 | 完全版 |
| d3_full | 自适应 + 竞争 | 全部 | 自适应+拓扑重组 | 最强版 |

#### 假设 H16-D3

**竞争与协同机制能使多层系统产生 L2 涌现，且涌现质量高于纯并行(D1)或纯反馈(D2)**。

**成功判据**:
1. ✅ L2 密封率 > 30%
2. ✅ L2 结构熵 < 0.3
3. ✅ L2 反射度 < 0.7
4. ✅ 涌现质量高于 D1/D2 最佳 config

---

## 总体实施规划

### 优先级排序

1. **D1 (exp_179)** — 最基础，改动最小，最容易实现
2. **D2 (exp_180)** — 中等难度，依赖 D1 的基础设施
3. **D3 (exp_181)** — 最复杂，依赖 D1+D2 的经验

### 实现步骤

#### Step 1: 创建 ParallelCrossLayerEvolver 核心类

```python
# experiments/exp_179_phase16_parallel_cross_layer.py

class ParallelCrossLayerEvolver:
    """Parallel multi-layer evolver for Path D1.
    
    All three layers evolve simultaneously with periodic cross-layer mapping.
    """
    
    def __init__(self, N0=48, N1=48, N2=48, t_lag_l1=100, t_lag_l2=300,
                 l1_update_interval=200, feedback_alpha=0.05,
                 total_steps=5000, device='cpu'):
        ...
    
    def step(self):
        """Single step update for all active layers."""
        ...
    
    def run(self):
        """Run parallel evolution for total_steps."""
        ...
```

关键方法:
- `_init_layers()`: 初始化 L0/L1/L2 evolvers
- `_live_map_l0_to_l1(l0_state)`: 从实时 L0 状态提取 L1 约束
- `_live_map_l1_to_l2(l1_state)`: 从实时 L1 状态提取 L2 约束
- `_apply_live_feedback(src_layer, dst_layer)`: 实时跨层反馈
- `_check_sealing()`: 检测各层密封状态
- `_collect_results()`: 收集实验结果

#### Step 2: 实现实时映射

实时映射与一次性映射的关键区别:

1. **部分结构化状态**: L0 演化中，cluster 可能不完整。需要用**软聚类** (soft clustering)，给每个比特一个 cluster 概率。
2. **动态约束**: L1 的 hierarchy_map 可以随时间变化（不像串行版是一次性固定）。
3. **自适应强度**: 早期 L0 结构弱，约束强度低；后期 L0 趋近密封，约束强度增加。

```python
def soft_cluster_mapping(state, n_clusters=3):
    """Soft cluster based on current state similarity.
    
    Uses pairwise XOR distance within a sliding window.
    Returns: membership_matrix: Tensor (N, n_clusters)
    """
    N = len(state)
    # Pairwise distance matrix
    dist = torch.zeros(N, N)
    for i in range(N):
        for j in range(N):
            dist[i,j] = (state[i] != state[j]).float().item()
    
    # K-medoids clustering
    centroids = torch.randperm(N)[:n_clusters]
    membership = torch.zeros(N, n_clusters)
    
    for _ in range(10):  # EM iteration
        # Assignment
        for i in range(N):
            d = dist[i, centroids]
            nearest = d.argmin().item()
            membership[i] = 0
            membership[i, nearest] = 1.0 - d[nearest].item() / N  # soft
        
        # Update centroids
        for k in range(n_clusters):
            members = (membership[:, k] > 0.3).nonzero(as_tuple=True)[0]
            if len(members) > 0:
                intra_dist = dist[members][:, members].sum(dim=1)
                centroids[k] = members[intra_dist.argmin().item()]
    
    return membership
```

#### Step 3: 指标与分析

每个实验需要收集:

1. **各层密封时间**: L0_seal_step, L1_seal_step, L2_seal_step
2. **各层最终 HW**: L0_HW, L1_HW, L2_HW
3. **结构熵**: 每层 final state 的熵
4. **跨层反射度**: L1 是否反映 L0, L2 是否反映 L1
5. **涌现检测**: L2 的结构是否不能简化为 L1+L0 的线性组合
6. **耦合强度**: 反馈实际改变了多少比特

#### Step 4: 统计测试

每个 config 至少运行 N=5 次（与前期实验一致）。

---

## 预期结果与理论意义

### 乐观 (40%)

- D1 产生至少部分 L2 涌现
- D2 显著增强涌现质量
- D3 最优解: 竞争与协同产生非平凡 L2 结构

**理论意义**: 并行演化是打破"死秩序"的关键。跨层反馈 + 资源竞争使系统脱离拓扑不变量的固定点。

### 中性 (40%)

- D1 能产生 L2 但结构接近随机
- D2 改善有限
- D3 略好于 D1/D2

**理论意义**: 并行演化确实能产生多层，但结构质量受限于基础动力学。"死秩序"不只是拓扑问题，也是动力学问题。

### 悲观 (20%)

- 所有 D1-D3 均失败
- L2 密封率 = 0% 或 L2 完全复制 L1

**理论意义**: "死秩序"是更深层的约束，不是并行化能解决的。差异论可能确实只能描述单层秩序。

### 整体影响

无论结果如何，Path D 将最终确定差异论模拟机的边界：

| Result | 对理论的结论 |
|--------|-------------|
| ✅ 成功 | 差异论可以扩展为多层涌现理论 |
| ❌ 失败 | 差异论精确描述"从混沌到第一次秩序"，需要根本性扩展 |
| ⚠️ 部分成功 | 差异论 + 并行演化 ≈ 多层涌现，但需要外部条件 |

---

## 附录: 与已有实验的关联

| 前期实验 | 关键教训 | 如何用在 Path D |
|----------|---------|-----------------|
| exp_169 (Cross-layer) | 串行映射产生 100% L1 密封 | D1 保留映射机制，但改为实时 |
| exp_173 (长程连接) | 非局部连接无系统性效应 | D3 中 L1→L0 拓扑重组尝试类似机制 |
| exp_174 (全局场) | 全局场有效但均匀化 | D2 中 L1 的"全局信号"替代外部场 |
| exp_176 (动态阈值) | 解封后不重新密封 | D1 在密封前就启动上层，避免此问题 |
| exp_170/171 (开放系统) | 环境扰动不足以破刚性 | D1/D2 的跨层耦合是"内部环境"，可能更强 |

---

## 实施时间预估

| 任务 | 预估时间 | 依赖 |
|------|---------|------|
| D1 代码实现 | 2-3 小时 | 现有 cross_layer_evolver |
| D1 实验运行 (6 configs × 5 runs) | 1-2 小时 | D1 代码完成 |
| D1 结果分析 | 30 分钟 | 实验完成 |
| D2 代码实现 | 1.5 小时 | D1 代码 |
| D2 实验运行 | 1-1.5 小时 | D2 代码完成 |
| D2 结果分析 | 30 分钟 | 实验完成 |
| D3 代码实现 | 2 小时 | D1+D2 代码 |
| D3 实验运行 | 1.5 小时 | D3 代码完成 |
| D3 结果分析 + 综合报告 | 1 小时 | 所有实验完成 |

**总计**: ~12 小时（一个完整工作日）

---

## 下一步行动

1. ✅ 编写本规划文档
2. 📋 **实现 exp_179 (D1: 并行更新)**
3. 📋 运行 exp_179 实验
4. 📋 分析结果，决定是否继续 D2/D3
5. 📋 如果 D1 完全失败: 撰写 Phase 16 综合报告，结束项目

---

**创建时间**: 2026-06-09 04:11 CST  
**创建者**: OpenClaw AI (heartbeat 强制行动)  
**关联**: phase16_planning_v1.md, HEARTBEAT.md