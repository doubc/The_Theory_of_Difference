# M4 深度构型 v2：多子空间耦合系统

## 理论根基：WorldBase 形式化框架

### 核心领悟

WorldBase 不是抽象哲学，而是一套从离散比特到物理结构的严格推导链：

**输入端**：{0,1}^N 超立方体 + 十公理约束
**推导过程**：约束 → 维度锁定 → 子空间分解 → 规范结构涌现 → 参数系统闭合
**输出端**：引力(1/r势)、强力(su(3))、弱力(su(2)+V-A)、电磁(U(1))、Higgs机制、费米子结构

### 当前模拟机的位置

当前引擎只实现了"公理约束"这一层：
- 九公理的损失函数 → 训练模型满足公理约束
- 在均匀二维网格上运行
- 用 XiangjieChain 事后检测象界门槛

### 真正的 Gap

WorldBase 形式化揭示的架构需求：

| WorldBase 需求 | 当前引擎状态 | Gap |
|---------------|-------------|-----|
| 子空间分解（引力/弱力/强力/电磁） | 单一均匀网格 | 无子空间概念 |
| 各子空间有效维度不同 | 固定2D网格 | 无维度差异 |
| 子空间通过中截面(w=N/2)耦合 | 无耦合机制 | 无跨子空间交互 |
| 规范结构从约束中涌现 | 无规范对称性 | 无规范场 |
| 汉明距离几何 | 欧氏网格距离 | 无汉明几何 |

## M4 架构升级方案

### 架构对比

**当前（M3）**：
```
[Uniform 2D Grid] → [Reactor + Axiom Loss] → [Structure Detector] → [Xiangjie Checker]
     单均匀网格         单套公理损失            单结构检测          事后门槛检测
```

**目标（M4）**：
```
[Multi-Subspace Grid] → [Coupled Reactors] → [Emergent Structures] → [Layer Tracker]
  多子空间耦合网格       耦合反应堆              涌现结构              层级追踪
       ↓                      ↓                      ↓                    ↓
[Gravitational Subspace] [Weak Subspace] [Strong Subspace] [EM Subspace]
   N_grav bits             N_weak=12 bits    N_strong bits      N_EM bits
   (层级深度)               (手征结构)         (色荷轨道)          (规范联络)
```

### 关键新增组件

#### 1. SubspaceDecomposition（子空间分解）
- 将全局比特组分解为物理子空间
- 每个子空间有自己的有效维度、比特数、约束
- 子空间通过中截面（w=N/2）耦合

#### 2. HammingGeometry（汉明几何）
- 用汉明距离替代欧氏距离
- 汉明重量 = 差异密度
- 中截面（w=N/2）= 最大差异层 = 物理活跃层

#### 3. CrossSubspaceCoupling（跨子空间耦合）
- 引力子空间提供"容器"（维度约束）
- 弱力子空间提供"手征性"（DAG方向）
- 强力子空间提供"色禁闭"（轨道约束）
- 电磁子空间提供"规范联络"（相位结构）

#### 4. EmergenceHierarchy（涌现层级追踪器）
- 追踪从公理约束到物理结构的涌现过程
- 记录各子空间的涌现状态
- 对应象界生成链的各章门槛

## 施工顺序

### 批次1 ✅ M3收尾（已完成）
### 批次2 ✅ 底图事件系统（已完成）
### 批次3 ✅ 差异分层（已完成）

### 批次4：汉明几何 + 子空间分解（当前）
- `engine/hamming_geometry.py`：汉明距离、汉明重量、中截面
- `engine/subspaces.py`：子空间分解、比特分配、耦合接口
- 修改 `layers/L0_binary_lattice.py`：支持子空间视图

### 批次5：跨子空间耦合 + 涌现层级追踪
- `engine/cross_subspace.py`：子空间耦合动力学
- `engine/emergence_hierarchy.py`：涌现层级追踪器
- 修改 `world_engine.py`：集成多子空间演化

### 批次6：实验验证
- `exp_10`：子空间耦合实验
- `exp_11`：涌现层级追踪实验

## 关键约束
- 不声称模拟现实物理
- 不做完整力/量子
- 不训练大模型
- 不用视觉图案替代验证器
- 子空间维度保持小规模（N_grav≤6, N_weak≤12），避免组合爆炸
