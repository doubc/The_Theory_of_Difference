"""
docs/M4-global-architecture-v2.md — 全局架构蓝图 v2

## 核心认知

差异论模拟机 = 离散状态空间 + 九公理约束 + 源/汇通量 → 涌现物理

关键：
1. 源(A1)持续注入差异，汇(A8)持续吸收差异 → 形成通量
2. 九公理在通量中形成张力 → 差异不能自由消散 → 必须形成结构
3. 探测器从演化轨迹中检测涌现 → 不预设公式

## 全局模块图

```
┌─────────────────────────────────────────────────────────────────┐
│                        WorldEngine                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ 源/汇系统 │  │ 演化核心  │  │ 公理引擎  │  │  涌现探测器    │  │
│  │ (A1/A8)  │→ │(Hamming  │→ │(9 Axioms)│→ │ (6 Detectors) │  │
│  │          │  │ Lattice) │  │          │  │               │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
│       ↑              ↑             ↑              ↑             │
│  通量注入        单比特翻转    约束评估        统计检测          │
│  动态源/汇位置   DAG方向      loss计算        对照实验           │
│  通量调制       采样记录      violation报告   可视化             │
└─────────────────────────────────────────────────────────────────┘
```

## 模块清单（42个文件 → 重组为6大模块）

### 模块1：状态空间层（layers/）
- hamming_layer.py — 汉明格点层 {0,1}^N ✅
- three_dim_hamming.py — 3D汉明格点 ✅
- layer_base.py — 层基类 ✅
- L0_binary_lattice.py — 旧版（可保留）
- L1_abstract_layer.py — 旧版（可保留）
- coarse_grain.py — 粗粒化（待增强）

### 模块2：演化引擎（engine/）
- hamming_engine.py — 汉明跃迁算子 ✅
- reactor.py — 差异反应堆（需增强源/汇）
- world_engine.py — 世界引擎主循环（需增强）
- events.py — 事件分类器 ✅
- difference_layers.py — 差异分层分析 ✅

### 模块3：公理系统（acl/）
- axiom_base.py — 公理基类 ✅
- axioms_strict.py — 九公理严格化 ✅

### 模块4：涌现探测器（新，engine/detectors/）
- trajectory_recorder.py — 轨迹记录器
- mutual_info.py — 比特互信息 I(i;j)
- hamming_distribution.py — 汉明重量分布 P(w)
- return_time.py — 返回时间分布 τ
- bit_clustering.py — 活跃比特聚类
- dag_direction.py — DAG方向一致性
- effective_dof.py — 有效自由度
- control_experiment.py — 对照实验

### 模块5：实验框架（experiments/）
- exp_1~12 — 已有实验（保留）
- exp_13_emergence.py — 涌现实验（新）

### 模块6：测试（tests/）
- 已有257个测试 ✅
- 新增探测器测试

## 关键增强点

### 1. 源/汇系统（当前太简单）
当前：每次随机翻转固定数量比特
增强：
  - 源位置动态选择（基于A8对称偏好）
  - 汇位置动态选择（基于A5守恒量梯度）
  - 源/汇强度受公理约束调制
  - 多源多汇（不只是单一源/汇）
  - 通量路径追踪

### 2. 演化核心（当前是训练模式）
当前：model预测 + loss驱动
增强：
  - 纯演化模式（无训练，只看涌现）
  - 长程演化（T=100000步）
  - 采样记录（每100步存快照）
  - 多世界并行（多个独立演化同时跑）

### 3. 涌现探测器（全新）
6个统计量 + 对照实验框架

### 4. 可视化（全新）
- 轨迹热力图
- 互信息距离衰减曲线
- 汉明重量分布直方图
- 返回时间幂律检验
- 比特聚类树状图
- DAG方向场

## 施工顺序（全局优先，分批渲染）

批次6a：增强源/汇系统（hamming_layer.py）
批次6b：长程演化模式（reactor.py + world_engine.py）
批次6c：轨迹记录器（engine/detectors/trajectory_recorder.py）
批次6d：涌现探测器6个统计量（engine/detectors/）
批次6e：对照实验框架（engine/detectors/control_experiment.py）
批次6f：涌现实验（experiments/exp_13_emergence.py）
批次6g：数据分析 + 可视化
批次6h：全量测试 + git commit

## 参数默认值

N = 16（先小后大，N=16时状态空间=65536）
T_total = 100000 步
sample_interval = 100 → 1000个快照
source_strength = 每步注入 2 个比特
sink_strength = 每步吸收 2 个比特
n_parallel_worlds = 4（4个独立世界同时演化）
dag_enabled = True
a8_symmetry = True
"""
