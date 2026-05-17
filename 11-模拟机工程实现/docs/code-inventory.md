# 差异论模拟机工程 — 代码功能认定与里程碑总结

## 一、代码功能认定

### A. 核心公理层（acl/）

| 文件 | 功能 | 状态 |
|------|------|------|
| `axioms_v2.py` | **九公理硬性约束检查器**（当前主版本） | ✅ 主版本 |
| `axioms.py` | 九公理损失项版本（M0-M2 遗留） | ⚠️ 旧版 |
| `axioms_strict.py` | 九公理严格化版本（M4 批次4b） | ⚠️ 部分集成 |
| `axioms_v3.py` | 引入"排除历史"概念（M4 批次8） | ⚠️ 实验性 |
| `axiom_base.py` | 公理基类 | ⚠️ 未使用 |

**axioms_v2.py 详细功能**：
- `AxiomConstraints` 类：九公理硬性约束检查器
- `check_A1()`：差异源——只允许 0→1 翻转
- `check_A4()`：最小变易——汉明距离必须为 1
- `check_A5_inject/absorb()`：守恒——注入/吸收量限制
- `check_A6()`：DAG 不可逆——禁止逆向翻转
- `check_A7()`：循环闭合——精确+近似循环检测（d_H ≤ 2）
- `check_A9()`：自由度封口——两阶段封口机制
- `get_A8_source_strength()`：对称偏好——动态注入强度
- `get_A8_sink_strength()`：对称偏好——动态吸收强度（兼容 A9 封口）
- `get_A1_prime_candidates()`：横向涌现——绑定强度加权配对
- `strengthen_binding()`：A1' 绑定增强
- `get_clusters()`：基于绑定强度提取聚类

### B. 演化引擎层（engine/）

| 文件 | 功能 | 状态 |
|------|------|------|
| `long_range_evolver_v2.py` | **长程演化器 v2**（当前主版本） | ✅ 主版本 |
| `long_range_evolver.py` | 长程演化器 v1（M4 批次6） | ⚠️ 旧版 |
| `world_engine.py` | 世界引擎（M3 集成版） | ⚠️ 部分集成 |
| `reactor.py` | 差异反应堆（M1-M2） | ⚠️ 旧版 |
| `events.py` | 底图事件系统（M4 批次2） | ⚠️ 实验性 |
| `difference_layers.py` | 差异分层 D0-D4（M4 批次3） | ⚠️ 实验性 |
| `hamming_engine.py` | 汉明几何引擎（M4 批次4a） | ⚠️ 实验性 |
| `mid_surface_analyzer.py` | 中截面分析器（M4 批次5） | ⚠️ 实验性 |
| `first_order_algebra.py` | 一阶变易代数（M4 批次5） | ⚠️ 实验性 |
| `experiment_config.py` | 实验配置 | ⚠️ 未使用 |
| `experiment_logger.py` | 实验日志 | ⚠️ 未使用 |
| `region_classifier.py` | 区域分类器 | ⚠️ 未使用 |
| `trainer.py` | 训练器 | ⚠️ 未使用 |

**long_range_evolver_v2.py 详细功能**：
- `LongRangeEvolverV2` 类：长程演化器
- 每步演化流程：源注入 → 内部演化 → 横向演化 → 汇吸收 → A7 检测 → 记录
- 集成 A1/A4/A5/A6/A7/A8/A9 公理约束
- 支持 verbose 输出和快照采样
- 返回完整演化结果（状态历史、聚类、绑定强度、封口状态等）

### C. 格点层（layers/）

| 文件 | 功能 | 状态 |
|------|------|------|
| `hamming_layer.py` | 汉明格点层（M4 批次4c，增强版） | ✅ 主版本 |
| `L0_binary_lattice.py` | L0 二元格点（M1-M2） | ⚠️ 旧版 |
| `L1_abstract_layer.py` | L1 抽象层（M1-M2） | ⚠️ 旧版 |
| `coarse_grain.py` | 粗粒化（M1-M2） | ⚠️ 旧版 |
| `three_dim_hamming.py` | 三维汉明格点（M4 批次5） | ⚠️ 实验性 |
| `layer_base.py` | 层基类 | ⚠️ 未使用 |

**hamming_layer.py 详细功能**：
- `HammingLattice` 类：汉明格点层
- 多源多汇配置
- 动态位置选择
- 通量追踪
- 绑定强度矩阵（A1'）

### D. 探测器层（engine/detectors/）

| 文件 | 功能 | 状态 |
|------|------|------|
| `statistics.py` | 5 个统计量探测器（M4 批次6） | ⚠️ 实验性 |
| `mutual_info.py` | 互信息探测器（M4 批次6） | ⚠️ 实验性 |
| `trajectory_recorder.py` | 轨迹记录器（M4 批次6） | ⚠️ 实验性 |

### E. 象界层（xiangjie/）

| 文件 | 功能 | 状态 |
|------|------|------|
| `chain.py` | 象界显现链——八章门槛检测器（M3） | ✅ 已集成到 world_engine |

**chain.py 详细功能**：
- 8 个门槛检测器：BoundaryGate, InterfaceGate, SelfMaintenanceGate, MemoryGate, ReplicationGate, SelectionGate, FunctionGate, PreSubjectiveGate
- 检测象界显现的 8 个阶段（I-VIII）

### F. 验证器层（validators/）

| 文件 | 功能 | 状态 |
|------|------|------|
| `structure_validator.py` | 结构验证器（M1-M2） | ⚠️ 旧版 |

### G. 模型层（models/）

| 文件 | 功能 | 状态 |
|------|------|------|
| `local_conv_model.py` | 局部卷积模型（M1-M2） | ⚠️ 旧版 |

### H. 测试层（tests/）

| 文件 | 测试对象 | 测试数 |
|------|----------|--------|
| `test_axioms_v2.py` | axioms_v2 | 16 |
| `test_detectors.py` | detectors | 15 |
| `test_events.py` | events | 20 |
| `test_first_order_algebra.py` | first_order_algebra | 13 |
| `test_hamming_layer.py` | hamming_layer | 23 |
| `test_mid_surface_analyzer.py` | mid_surface_analyzer | 20 |
| `test_three_dim_hamming.py` | three_dim_hamming | 25 |
| `test_xiangjie.py` | xiangjie/chain | 19 |
| `test_hamming.py` | hamming_engine | 12 |
| `test_structure_validator.py` | structure_validator | 16 |
| `test_reactor_step.py` | reactor | 10 |
| `test_l0_binary_lattice.py` | L0_binary_lattice | 11 |
| `test_l1_layer.py` | L1_abstract_layer | 10 |
| `test_local_conv_model.py` | local_conv_model | 7 |
| `test_coarse_grain.py` | coarse_grain | 9 |
| `test_difference_layers.py` | difference_layers | 6 |
| `test_property_*.py* | 性质验证 | 14 |
| **总计** | | **246** |

### I. 文档层（docs/）

| 文件 | 内容 |
|------|------|
| `M4-batch9-axiom-analysis.md` | A5/A6/A7/A9 公理行为分析 |
| `M4-batch10-axiom-fix.md` | A5/A7/A9 修复记录 |
| `M4-batch10b-sealed.md` | A9 封口触发记录 |

## 二、里程碑回顾

### M0-M2（已完成）
- 差异反应堆、L0/L1 格点、局部卷积模型
- 92+ 测试通过

### M3（已完成）
- 象界显现链（8 个门槛检测器）
- 111 测试通过
- exp_8 实验成功

### M4（进行中）

| 批次 | 内容 | 状态 |
|------|------|------|
| 1 | M3 收尾 | ✅ |
| 2 | 底图事件系统 | ✅ |
| 3 | 差异分层 D0-D4 | ✅ |
| 4a | 汉明几何引擎 | ✅ |
| 4b | 九公理严格化 | ✅ |
| 4c | 汉明格点层 | ✅ |
| 4d | 实验验证（exp_10/11） | ✅ |
| 5 | 三维汉明 + 中截面 + 一阶代数 | ✅ |
| 6 | 涌现探测器框架 | ✅ |
| 7 | 公理重设计（硬性约束） | ✅ |
| 8 | A1' 绑定聚类 | ✅ |
| 9 | A5/A6/A7/A9 行为分析 | ✅ |
| 10 | A5/A7/A9 修复 | ✅ |
| 10b | A9 封口触发 | ✅ |

### 当前测试覆盖
- 全量测试：约 246 个
- 核心测试（axioms_v2 + long_range_evolver_v2 + hamming_layer）：约 54 个

## 三、当前系统状态

### 已涌现的结构
1. **聚类**（A1' 横向涌现）：绑定强度加权配对 → 稳定聚类
2. **层级**（九机制）：聚类内部核心-外围结构
3. **循环**（A7）：925+ 循环状态
4. **自由度封口**（A9）：75% 比特冻结，25% 保持活跃

### 各公理出场状态
| 公理 | 状态 | 说明 |
|------|------|------|
| A1 差异源 | ✅ | 单调累积 |
| A1' 横向涌现 | ✅ | 聚类+层级 |
| A2 二元具象 | ✅ | {0,1}^N |
| A3 有限离散 | ✅ | N 固定 |
| A4 最小变易 | ✅ | 单比特翻转 |
| A5 守恒 | ✅ | 严格平衡 |
| A6 DAG | ✅ | 方向约束 |
| A7 循环 | ✅ | 近似循环检测 |
| A8 对称偏好 | ✅ | w≈N/2 |
| A9 自由度 | ✅ | 封口机制 |

### 可扩展方向
1. **增大 N**：当前 N=48，可扩展到 N=64/128
2. **更长的 T**：当前 T=20000，可扩展到 T=100000
3. **多源多汇**：hamming_layer.py 已支持
4. **探测器完善**：statistics.py 中的 5 个统计量探测器
