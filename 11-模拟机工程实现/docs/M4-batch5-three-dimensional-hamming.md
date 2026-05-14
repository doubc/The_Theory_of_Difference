"""
docs/M4-batch5-three-dimensional-hamming.md — 批次5蓝图：三维汉明格点

## 目标

从 1D 比特串升级到 3D 汉明格点，实现 WorldBase 的核心预测：
- D=3 有效空间维度
- 三维空间中的引力势 Φ(r) ∝ -1/r
- 中截面结构（强力 su(3) 的前置条件）

## 理论依据

WorldBase §4.2 分块嵌入映射：
  ι_ε: {0,1}^N → [0,L]^3
  ι_ε(x)_k = ε_N Σ_{i∈G_k} x_i,  k=1,2,3

其中 G_k = {(k-1)N/3+1, ..., kN/3}，ε_N = L/n = 3L/N

WorldBase §5.2 中截面：
  M_N = {x ∈ {0,1}^N | w(x) = N/2}

WorldBase §5.3 一阶变易算符：
  E_ij|x> = |x'> 若 x_i=1, x_j=0, x'_i=0, x'_j=1
  保持汉明重量不变 → 中截面上闭合

## 设计

### 1. ThreeDimHammingLattice（layers/three_dim_hamming.py）

继承 HammingLattice，增加：
- 3D 坐标映射 (i → (x,y,z))
- 3D 汉明距离（分组汉明距离）
- 中截面检测（w = N/2 的层）
- 一阶变易算符 E_ij（中截面上的差异移动）

### 2. 中截面结构分析器（engine/mid_surface_analyzer.py）

- 枚举中截面状态
- 计算中截面上的距离分布
- 检测活跃位数量 k
- 验证 k=3 锁定（引理 S0）

### 3. 一阶变易代数（engine/first_order_algebra.py）

- 实现 E_ij 算符
- 验证 CR-1: [E_ij, E_jk] = E_ik
- 验证 CR-2: [E_ij, E_ji] = x_i - x_j
- 生成元计数：6非对角 + 2对角 = 8 → su(3)

## 施工顺序

批次5a：ThreeDimHammingLattice（3D坐标 + 中截面检测）
批次5b：MidSurfaceAnalyzer（中截面枚举 + 距离分布）
批次5c：FirstOrderAlgebra（E_ij + 对易关系验证）
批次5d：实验验证（exp_12：3D势场 + 中截面结构）

## 测试矩阵

- 3D 坐标映射正确性
- 中截面检测（w=N/2 层）
- E_ij 算符作用（保持 w 不变）
- 对易关系 CR-1, CR-2
- 生成元计数 = 8
- 3D 引力势测量

## 依赖

- layers/hamming_layer.py（已有）
- engine/hamming_engine.py（已有）
- acl/axioms_strict.py（已有）
"""
