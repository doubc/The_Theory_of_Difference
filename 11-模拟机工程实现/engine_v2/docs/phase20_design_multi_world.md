# Phase 20: 并行子空间（多世界模拟）

## 设计日期
2026-06-11

## 理论动机

差异论 Phase 17-19 验证了**单链自指闭环**：L0→L1→L2→... 的串行涌现。
但真实世界（生命、意识、社会）不是孤立链条——**多个自指链并行存在，相互耦合**。

核心问题：
1. **多个世界并行演化时，涌现深度是否叠加？**（整体 > 各部分之和）
2. **弱耦合能否传递结构？**（L1 结构能否跨世界传播）
3. **世界间竞争/协同如何改变单个世界的密封动力学？**

---

## 实验设计

### P0: 基线 — 多世界独立演化 (exp_190)

**目的**: 确认多世界框架不产生伪影（各世界行为 ≈ 单世界）。

**配置**:
- `n_worlds = 4`, 各世界独立（耦合强度=0）
- 每世界: N0=48, seed 不同
- 测量: 各世界涌现深度、L1 flux、密封步长
- **H20-P0**: 各世界涌现深度分布 ≈ 单世界基线（depth ~4.6, L2 涌现率 ~95%）

---

### P1: 弱耦合 — 世界间结构传递 (exp_191)

**目的**: 测试弱耦合能否让一个世界的 L1 结构影响另一个世界。

**耦合机制** (`MultiWorldCoupling`):
```
对于每个 step:
  world_i 的 m9 输出 (a1_source_i) → 作为 world_j 的 environment coupling bias
  耦合强度 α ∈ [0.05, 0.10, 0.20]
```

**假设**:
- **H20-P1a**: α=0.10 时，世界对之间 L1 结构相关性 > 0.3
- **H20-P1b**: 弱耦合不破坏各世界自身的涌现深度（depth 下降 < 20%）
- **H20-P1c**: 存在最优耦合强度（过小无效，过大压制自主性）

---

### P2: 竞争动力学 — 资源约束下的世界选择 (exp_192)

**目的**: 模拟"资源有限"时，多个自指链如何竞争。

**机制**:
- 总"能量"预算: `total_energy = n_worlds × energy_per_world × 0.6`（稀缺）
- 每世界每步消耗能量 = `n_active_bits`
- 能量耗尽的世界 → 停止演化（"灭绝"）
- 观察：哪些世界存活？存活世界的涌现深度是否更高？

**假设**:
- **H20-P2a**: 涌现深度更高的世界有更高存活概率
- **H20-P2b**: 竞争导致平均涌现深度**上升**（选择压力）

---

### P3: 协同涌现 — 跨世界 L2 共享 (exp_193)

**目的**: 测试多个世界的 L2 能否**汇聚为同一个更高层实体**（L3 跨世界共享）。

**机制**:
- 4 个世界独立演化到 L1
- L2 计算时：取 4 个世界 L1 的 `a1_source` 并集 → 单个共享 L2
- 测量：共享 L2 的 NSI / flux vs 独立 L2

**假设**:
- **H20-P3a**: 共享 L2 的 NSI > 任意单世界 L2 的 NSI（协同增益）
- **H20-P3b**: 共享 L2 的 Jaccard flux > 0（跨世界激活）

---

## 实现架构

### 新增文件

```
engine_v2/
├── diffsim/
│   ├── multi_world.py      ← 新增：MultiWorld + coupling mechanisms
│   └── ...
├── experiments/
│   ├── exp_190_phase20_p0_baseline.py
│   ├── exp_191_phase20_p1_coupling.py
│   ├── exp_192_phase20_p2_competition.py
│   └── exp_193_phase20_p3_synergy.py
└── docs/
    └── phase20_design_multi_world.md    ← 本文档
```

### multi_world.py 核心接口

```python
class MultiWorld:
    """管理 n 个并行 RecursiveWorld，支持弱耦合。"""
    
    def __init__(self, n_worlds, N0=48, coupling_strength=0.0, seed=0):
        self.worlds = [RecursiveWorld(N0=N0, seed=seed+i) for i in range(n_worlds)]
        self.coupling_strength = coupling_strength
        self.coupling_matrix = np.eye(n_worlds)  # 对角 = 自耦合
    
    def set_coupling(self, matrix):
        """设置世界间耦合矩阵。"""
        ...
    
    def step_all(self):
        """所有世界各演化一步，然后应用耦合。"""
        for w in self.worlds:
            w.step()  # 单步（非 run_until_seal）
        self._apply_coupling()
    
    def _apply_coupling(self):
        """将世界 i 的 m9 输出作为世界 j 的环境偏置。"""
        ...
    
    def run_all(self, max_layers=6):
        """所有世界独立运行到整体不动点。"""
        for w in self.worlds:
            w.run(max_layers=max_layers)
        return self.collect_report()
    
    def collect_report(self):
        """汇总所有世界的涌现深度、flux、密封步长。"""
        ...
```

---

## 与 Phase 19 的关系

Phase 19 研究了**单世界 + 环境**的交互。
Phase 20 将"环境"推广为**其他并行世界**——环境不再是被动约束场，而是**主动的、自身也涌现的其他自指链**。

理论意义：**他者即环境**。

---

## 成功标准

| 实验 | 假设 | 成功标准 |
|------|------|----------|
| P0 | H20-P0 | 4/4 世界涌现深度 ≈ 单世界基线 |
| P1 | H20-P1a | α=0.10 时 L1 结构 corr > 0.3 |
| P1 | H20-P1b | depth 下降 < 20% |
| P2 | H20-P2a | 深度 top-50% 世界存活率 > 70% |
| P3 | H20-P3a | 共享 L2 NSI > max(独立 L2 NSI) |

---

## 预期时间与资源

| 实验 | 运行次数 | 预估时间 |
|------|----------|----------|
| P0 (exp_190) | 4 worlds × 8 seeds | ~2 min |
| P1 (exp_191) | 3 α × 4 worlds × 8 seeds | ~10 min |
| P2 (exp_192) | 3 budgets × 4 worlds × 8 seeds | ~10 min |
| P3 (exp_193) | 8 seeds | ~5 min |

---

## 理论延伸

如果 P1 确认**弱耦合可传递结构**，则差异论可解释：
- **语言**: 个体自指链（大脑）通过弱耦合（声音/文字）共享 L2（概念）
- **文化**: 群体自指链通过弱耦合（仪式/制度）共享 L3（意义）

如果 P3 确认**协同涌现**，则差异论可解释：
- **集体意识**: 多个体 L1 汇聚为共享 L2（"主体间性"的差异论表述）

---

*设计：doubc | 2026-06-11*
*项目：差异论生成式世界 · 模拟机工程 · Phase 20*
