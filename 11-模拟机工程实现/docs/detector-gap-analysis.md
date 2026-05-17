# 探测器缺口分析 — 空间嵌入层接入后

**日期**: 2026-05-17
**前提**: three_dim_hamming.py 已就绪，评估接入 long_range_evolver_v2 后的检测可行性

---

## 1. 空间嵌入层基础验证 (N=48)

ThreeDimHammingLattice 核心功能全部可运行：

| 功能 | 状态 | 说明 |
|------|------|------|
| `embed_3d()` | OK | {0,1}^48 → [0,1]^3，三组各 16 bits |
| `euclidean_distance()` | OK | 嵌入空间欧氏距离 |
| `hamming_distance_3d()` | OK | 分组汉明距离 (dx, dy, dz) |
| `potential_3d_at()` | OK | 3D 引力势 Φ(x) = -Σ 1/|ι(x)-ι(s)| |
| `apply_E_ij()` | OK | 一阶变易算符，中截面上闭合 |
| `get_valid_E_moves()` | OK | N=48 中截面有 576 个有效移动 |
| `random_mid_surface_state()` | OK | w=N/2=24 的随机中截面态 |

**关键数据**:
- 嵌入分辨率: ε = L/n = 1/16 = 0.0625
- 3D 距离与汉明距离的关系: d_E ∝ d_H (线性，因为每组独立编码一个坐标轴)
- 势场: Φ_3d 随 d_E 单调衰减（定性正确）

---

## 2. 现有探测器可用性

### 直接可用 (3/6)

| 探测器 | 状态 | 原因 |
|--------|------|------|
| `HammingDistributionDetector` | OK | 重量分布是基无关的 |
| `ReturnTimeDetector` | OK | 返回时间是 per-bit 的 |
| `DAGDirectionDetector` | OK | DAG 方向是 per-bit 的 |

### 需要改造 (3/6)

| 探测器 | 改造内容 | 改造量 |
|--------|----------|--------|
| `MutualInfoDetector` | 距离定义: \|i-j\| → \|ι(i)-ι(j)\| (3D 欧氏距离) | 低 — 只改距离函数 |
| `BitClusteringDetector` | 加入空间邻近性权重 | 中 — 需要 embed_3d 坐标 |
| `EffectiveDOFDetector` | 分别计算 x/y/z 三个方向的 DOF | 低 — 分组计算 |

### 全部失效 (1/6)

| 探测器 | 原因 |
|--------|------|
| `ControlExperiment` | 依赖旧的 LongRangeEvolver + HammingLattice，与新架构不兼容 |

---

## 3. 需要新建的探测器

### P0: MutualInfoDetector 距离定义改造

**改造方案**: 将 `dist_matrix` 从 bit-index 距离改为 3D 欧氏距离

```python
# 旧: |i-j| (循环比特索引距离)
dist_matrix = torch.abs(indices.unsqueeze(1) - indices.unsqueeze(0))

# 新: |ι(i)-ι(j)| (3D 嵌入空间距离)
coords = layer.embed_3d_basis()  # (N, 3) 每个比特的 3D 坐标
dist_matrix = torch.cdist(coords, coords)  # (N, N)
```

**检测目标**: I(r) ~ r^{-α}，引力信号 α≈1

### P1: GravitationalPotentialDetector (新建)

**功能**: 测量势场 Φ(x) = -Σ_s 1/|ι(x)-ι(s)|

**输入**: 轨迹 + 源位置
**输出**: Φ(r) 曲线，拟合 -1/r 标度律

**依赖**: `ThreeDimHammingLattice.potential_3d_at()`

**实现复杂度**: 低（已有势场计算函数）

### P2: DimensionLockingDetector (新建)

**功能**: 检测有效维度 D_eff

**方法 1**: 3D PCA → 3 个主成分解释方差比
**方法 2**: 随机游走均方位移 <r²> ~ t^{2/D}
**输出**: D_eff 估计值

**依赖**: `ThreeDimHammingLattice.embed_3d()`

**实现复杂度**: 中（需要 MSD 计算）

### P3: GaugeFieldDetector (新建)

**功能**: 检测中截面上的 su(3) 规范结构

**方法**: 
1. 生成中截面状态 (w=N/2)
2. 计算 E_ij 对易关系 [E_ij, E_kl] = δ_jk E_il - δ_il E_kj
3. 验证 su(3) 李代数

**输出**: 对易关系矩阵，su(3) 代数验证

**依赖**: `ThreeDimHammingLattice.apply_E_ij()`

**实现复杂度**: 高（需要符号计算或数值验证）

### P4: SpatialCorrelationDetector (新建)

**功能**: 空间关联函数 C(r) = <x_i · x_j> for |ι(i)-ι(j)|=r

**检测**: 关联长度 ξ，长程有序 vs 短程有序

**实现复杂度**: 中

### P5: TopologicalChargeDetector (新建)

**功能**: 检测拓扑荷（环绕数/链接数）

**方法**: 3D 闭合曲面上的通量

**实现复杂度**: 高

---

## 4. 可行性评估

### 基础设施就绪度

| 组件 | 状态 | 说明 |
|------|------|------|
| 空间嵌入层 | OK | ThreeDimHammingLattice 完整实现 |
| 3D 距离 | OK | embed_3d() + euclidean_distance() |
| 势场计算 | OK | potential_3d_at() |
| 一阶变易 | OK | apply_E_ij() |
| 中截面 | OK | random_mid_surface_state() |
| 演化器集成 | GAP | three_dim_hamming 未接入 long_range_evolver_v2 |
| 源/汇空间定位 | GAP | 当前随机比特选择，需要空间定位 |

### 关键 GAP

**GAP 1**: 演化器未集成空间嵌入层

当前 long_range_evolver_v2.py 直接操作比特串，没有使用 ThreeDimHammingLattice。

**解决方案**: 
- 方案 A: 在演化器中嵌入 ThreeDimHammingLattice 作为坐标提供器
- 方案 B: 新建 SpatialEvolver，完全基于 3D 坐标

**GAP 2**: 源/汇缺少空间定位

当前源/汇是随机选择比特位置，没有空间意义。

**解决方案**:
- 源定位: 在 3D 空间中选择特定位置注入差异
- 汇定位: 在 3D 空间中选择特定位置吸收差异
- 空间调制: A8 权重基于 3D 距离计算

---

## 5. 结论

### 检测手段可行性: 可行

接入空间嵌入层后，**所有 5 类物理检测都可以实现**：

| 检测目标 | 方法 | 可行性 |
|----------|------|--------|
| 引力势 -1/r | GravitationalPotentialDetector (P1) | 高 — 已有势场函数 |
| 维度锁定 D=3 | DimensionLockingDetector (P2) | 高 — 已有 embed_3d |
| 规范场 su(3) | GaugeFieldDetector (P3) | 中 — 需要中截面代数 |
| 空间关联 | SpatialCorrelationDetector (P4) | 高 — 已有 embed_3d |
| 拓扑荷 | TopologicalChargeDetector (P5) | 低 — 需要 3D 网格 |

### 工作量估计

| 任务 | 复杂度 | 预计文件数 |
|------|--------|------------|
| MutualInfoDetector 改造 | 低 | 1 文件修改 |
| GravitationalPotentialDetector | 低 | 1 文件新建 |
| DimensionLockingDetector | 中 | 1 文件新建 |
| GaugeFieldDetector | 高 | 1-2 文件新建 |
| SpatialCorrelationDetector | 中 | 1 文件新建 |
| 演化器集成 | 高 | 1 文件修改 |
| 源/汇空间定位 | 中 | 1 文件修改 |

**总计**: 约 5-7 个文件新建/修改

### 建议优先级

1. **P0**: MutualInfoDetector 改造（1 小时）
2. **P1**: GravitationalPotentialDetector（2 小时）
3. **演化器集成空间嵌入层**（4 小时）
4. **源/汇空间定位**（2 小时）
5. **P2**: DimensionLockingDetector（3 小时）
6. **P4**: SpatialCorrelationDetector（3 小时）
7. **P3**: GaugeFieldDetector（6 小时）
