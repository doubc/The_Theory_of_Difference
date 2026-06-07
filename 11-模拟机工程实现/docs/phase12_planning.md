# Phase 12: 聚簇时空动力学 — 规划文档

> **版本**: v0.1 (DRAFT)  
> **日期**: 2026-06-07  
> **前接**: Phase 11 (子空间分解与多场耦合) ✅  
> **驱动文档**: theory_synthesis_v2.md §3.6 (待深化矩阵)  

---

## 一、动机：从"是否形成"到"如何形成"

Phase 1-11 回答了核心问题：**在九公理约束下，L1 是否形成？**

关键发现：
- N0*=30.5 一阶相变（Phase 9 P3）
- 子空间隔离存在（Phase 11 P2）
- 耦合通过 **coupling_bias** 传递差异偏置（Phase 11 P4）

但所有实验回答的都是 **"是否形成"**，尚无人回答：**"如何形成"**。

这对应于差异论的一个深层问题：**聚簇不是瞬间事件，它是有时空结构的。** 一个 bit 从"自由"到"封入 L1"的轨迹是怎样的？bits 之间如何协调进入同一个 L1？这个过程是否展现出可观测的时空模式？

### 1.1 理论缺口

| 已回答 | 未回答 |
|--------|--------|
| L1 是否形成？ | L1 的实时形成过程是怎样的？ |
| N0 多大时 L1 形成？ | bits 聚簇的先后顺序是怎样的？ |
| 耦合是否影响 L1？ | 耦合是否改变聚簇的时空模式？ |
| 子空间是否隔离？ | 子空间间的聚簇时序如何关联？ |

### 1.2 Phase 12 的定位

Phase 12 不是"新功能工程"而是"新观测工程"。不引入新引擎组件，而是引入**高时间分辨率的观测框架**，使聚簇的时空动态可分析、可量化、可理论化。

---

## 二、P0：TemporalTrace 观测框架

### 2.1 需求

现有实验记录的是 **终态**（是否 L1、最终权重、seal_step）。无法回答：
- L1 形成前哪些 bits 已经"趋近"密封？
- 密封顺序是随机的还是结构化的？
- 耦合是否改变密封时序？

### 2.2 设计

`TemporalTrace`：一种轻量级观测包装器，包裹现有 Solver 类，在每个 step 记录：

```python
class TemporalTrace:
    """Attach to any Solver: records per-step state snapshots."""
    
    def __init__(self, solver, record_every=1):
        self.solver = solver
        self.record_every = record_every
        self.history = []  # List of StepSnapshot
    
    def step(self):
        # 1. Call original solver.step()
        # 2. If step % record_every == 0, record StepSnapshot
        pass
    
    def get_seal_order(self):
        """Return list of bit indices in order they sealed."""
        pass
    
    def get_convergence_trace(self):
        """Per-bit convergence measure over time (e.g., weight stability)."""
        pass
```

**StepSnapshot** 包含：
- step 编号
- 每个 bit：密封状态 (bool)、权重 (float)、累积偏置 (float)、局部场强 (float)
- 耦合子空间：当前耦合注入值
- 全局度量：活动 bit 数、总密封数、层编号

### 2.3 观测指标

| 指标 | 定义 | 理论对应 |
|------|------|---------|
| **seal_order** | bits 达到 sealed 的时间顺序 | 差异吸引子的不同引力半径 |
| **convergence_rate** | 每个 step 新 sealed bits 数 | 聚簇的"凝聚速度" |
| **pre_seal_fluctuation** | 密封前 N 步权重的波动程度 | 最小变易原则的局部表现 |
| **cascade_size** | 单个 step 内密封的最大 bit 数 | 雪崩——差异压缩的爆发性 |
| **coupling_lag** | 耦合子空间聚簇之间的时间差 | 因果箭头的传播时间 |

### 2.4 实现方式

**不修改现有 engine 代码**。`TemporalTrace` 是一个独立的观测层，通过包装器模式接入：

```python
# Usage in experiment
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver
from observations.temporal_trace import TemporalTrace

solver = SpatialLongRangeEvolver(...)
trace = TemporalTrace(solver, record_every=5)  # Record every 5 steps

# Run with trace
while not all(layer_solver.is_sealed for layer_solver in solver.solvers):
    trace.step()  # Replaces direct solver.step()
```

**文件**: `observations/temporal_trace.py`（新建模块）

---

## 三、P1：单空间聚簇时序实验 (exp_153)

### 3.1 实验设计

| 参数 | 值 |
|------|-----|
| N0 | 40（>> N0*，确保 L1 形成） |
| k | 1（单子空间，聚焦聚簇本身） |
| runs | 50（统计聚簇模式的稳定性） |
| record_every | 1（最高时间分辨率） |

### 3.2 待回答的问题

1. **密封顺序**：bits 密封的先后是随机的，还是跟位置/拓扑有关？
2. **凝聚速度**：从第一个 sealed bit 到最后一个，过程中是否有爆发期（cascade）？
3. **预密封活动**：bits 在密封前是否有可观测的"趋近"行为（权重收敛/偏置累积）？
4. **cascade 分布**：cascade size 服从什么分布？幂律？指数？

### 3.3 理论预测

基于差异论的最小变易原则与稳定闭合公理：

1. **密封不是均匀的**：bits 会有"先行者"——某些 bit 因其在场中的位置（更高的局部差异密度），更早满足密封条件
2. **Cascade 现象**：一旦某个 bit 密封，它的场被重排，可能导致相邻 bits 的密封阈值被"带动"降低，形成雪崩
3. **收敛率曲线**：对于 N0=40，可能呈现 S 形——早期缓慢、中期爆发、后期拖尾

---

## 四、P2：子空间聚簇耦合时序 (exp_154)

### 4.1 实验设计

| 参数 | 值 |
|------|-----|
| N0 | 40 per subspace |
| k | 2 |
| coupling_levels | [0.0, 1.0, 5.0] |
| topology | symmetric / unidirectional |
| runs | 30 per coupling level |
| record_every | 1 |

### 4.2 待回答的问题

1. **耦合是否同步密封时序？** 强耦合下两个子空间的聚簇是否趋于同步？
2. **耦合滞后**：单向耦合中，从子空间的聚簇滞后主空间多少步？
3. **耦合改变 seal_order 吗？** 耦合偏置是否改变 bits 密封的顺序（比如使某些位"被优先带动"）？
4. **cascade 相互影响**：一个子空间的 cascade 是否会触发另一个子空间的 cascade？

### 4.3 理论预测

1. **耦合注入 = 偏置方向提示**：耦合偏置相当于对从子空间说"某些方向更可能产生差异"。这会加速从子空间沿着耦合方向 bits 的密封
2. **不完全同步**：即使在强耦合下，子空间也不会完全同步，因为每个子空间的 6 方向场是独立的（Phase 11 P2 已验证）
3. **耦合有延迟阈值**：需要最小耦合强度才能产生可观测的 seal_order 改变

---

## 五、P3：聚簇临界行为 (exp_155)

### 5.1 动机

Phase 9 发现了 N0*≈30.5 的一阶相变。但那是 **是否**形成 L1 的相变。Phase 12 要问的是：

**相变点附近的聚簇时空模式是怎样的？**

### 5.2 实验设计

| 参数 | 值 |
|------|-----|
| N0 | [28, 29, 30, 31, 32, 33, 35]（跨越相变点） |
| k | 1 |
| runs | 100 per N0（统计聚簇模式的可靠性） |
| record_every | 1 |

### 5.3 待回答的问题

1. **N0=N0* 附近，cascade 大小是否发散？** 这是临界点标志
2. **N0 接近 N0* 时，预密封活动是否延长？** 即聚簇过程是否"犹豫"更久？
3. **靠近临界点，密封顺序是否更随机？**
4. **临界点附近，是否有"伪聚簇"——部分 bits 暂时密封后又松开？**

### 5.4 理论预测

1. Cascade size 在 N0* 附近应达到最大值（临界涨落）
2. 预密封时间（第一个到最后一个 sealed bit 之间的步数）在 N0* 附近也应达到峰值
3. 如果 cascade size 在 N0* 附近服从幂律，这将是"差异论世界"的自组织临界性证据

---

## 六、时间线与风险

### 6.1 预估时间

| 子阶段 | 内容 | 预估运行时间 |
|--------|------|-------------|
| P0 | TemporalTrace 实现 | 工程时间 ~30min |
| P1 | exp_153（50 runs × N0=40） | ~30min |
| P2 | exp_154（90 runs × coupling scans） | ~90min |
| P3 | exp_155（700 runs × N0=28-35） | ~7h（可分 batch 运行） |
| P4 | 分析综合 + 理论回写 | ~60min |

### 6.2 风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| TemporalTrace 产生大面积日志导致 I/O 瓶颈 | 中 | 高 | record_every 可调；支持压缩存储（npz） |
| exp_155 700 runs 时间过长 | 中 | 中 | 先跑 50 runs/N0 确认信号，再扩展 |
| 聚簇模式过于随机，无统计意义 | 低 | 高 | 设计熵度量量化密封顺序的结构性 |
| TemporalTrace 引入观测偏差 | 低 | 中 | 对照实验：trace 开启 vs 关闭，比较 seal_step |

---

## 七、与差异论理论的连接

### 7.1 直接映射

| 实验发现 | 差异论概念 |
|----------|-----------|
| 密封顺序的结构性 | 差异的"引力梯度"——不同差异点的"差异密度"不同 |
| Cascade 现象 | 差异压缩的"雪崩"——一个差异的压缩带动相邻差异 |
| 耦合同步 | 共同反差的时间传递 |
| 临界点涨落 | 可能性空间的边界——相变前的"最不确定"时刻 |

### 7.2 升级 V1.7 的意义

Phase 12 的结果将直接回答 V1.7 升级提纲中的一个核心问题：

> "差异压缩是一个事件还是一个过程？"

如果 cascade 是爆发性的（单个 step 密封多个 bits），则聚簇是"事件"。如果有可观测的预密封趋近过程，则聚簇是"过程"。Phase 12 的时域数据将首次给出实验证据。

---

## 八、依赖与前置条件

- [ ] 确认当前 engine 代码（尤其是 `SpatialLongRangeEvolver.step()`）的接口稳定
- [ ] 确认 `subspace_evolver.py` 的封装层次允许 TemporalTrace 以包装器模式接入
- [ ] 确认分析脚本栈（numpy + 绘图）可用
- [ ] 准备结果存储目录 `results/phase12_p*/`

---

**文档状态**: DRAFT  
**最后更新**: 2026-06-07 11:46 CST  
**下一步**: 实现 TemporalTrace（观测框架 P0）
