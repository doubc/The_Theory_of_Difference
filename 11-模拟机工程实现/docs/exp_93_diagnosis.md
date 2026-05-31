# exp_93 诊断报告 — 2026-06-01

## 执行结果总览

| 指标 | 结果 | vs exp_90 |
|------|------|-----------|
| H1 (MSI active) | ✅ PASS | - |
| H2 (ODI > 0.2) | ✅ PASS | - |
| H3 (Narrative coh ≥ 0.2) | ✅ PASS (0.8333) | - |
| H4 (min CIV ≥ 3) | ✅ PASS (min=4) | - |
| CIV mean | **48.50** | exp_90: 5.25 (⚠️ 9.2×) |
| CIV min | **4** | exp_90: 2 |
| CIV max | **198** | exp_90: ~10 |
| GBC coherence | **0.0000** | ⚠️ 完全未激活 |
| GBC n_checks | **0** (所有种子) | ⚠️ 从未执行 |
| CSC csci_mean | 0.6697 | - |
| CSC emergence_events | **0** | ⚠️ 无涌现事件 |

## 两个核心问题

### 问题1: GBC 完全未激活 (n_checks=0)

**根因**: `AxiomConstraints.direction` 初始化为全零 (`torch.zeros(N)`), 导致:

1. `self_sustaining` 计算: `mean_dir = 0` → `abs(mean_dir) > 1e-8` 永远失败 → `self_sustaining = 0.0`
2. `boundary` 机制: `boundary_vec = constraints.direction.float().clone()` → 全零向量 → 不被添加到 `local_biases`
3. 所有其他机制 (`memory`, `replication`, `selection`, `function`) 也依赖 `direction` 或相关条件
4. `local_biases` 永远为空 → `if local_biases:` 永远为假 → `gbc_result = evaluate(...)` 从未执行

**代码位置**:
- `acl/axioms_v2.py` L46: `self.direction = torch.zeros(N, dtype=torch.long)`
- `hierarchical_evolver.py` L886-894: `self_sustaining` 计算依赖 `direction` 非零
- `hierarchical_evolver.py` L922: `boundary_vec = constraints.direction.float().clone()`

**修复方案**: 将 `direction` 初始化为从初始状态派生的值:
- 状态值 > 0.5 的比特 → direction = +1
- 状态值 ≤ 0.5 的比特 → direction = -1
- 这样确保初始方向有正有负，mean ≠ 0，机制可以激活

### 问题2: CIV 值异常偏高 (mean=48.5 vs exp_90: 5.25)

**根因**: GBC 未激活 → 缺少全局偏置约束 → 高层级 (CIVILIZATION) 缺乏约束压力
- Seed 542: CIV=131 (层结构: MINI=2, INST=27, CIV=131) → 系统几乎完全坍缩到 CIV 层
- Seed 742: CIV=198 (层结构: MINI=10, INST=32, CIV=198) → 同样极端
- Seed 242/642: CIV=4/5 (层结构: MINI=147/150, INST=9/5, CIV=4/5) → 相反极端

**GBC 的作用**: 通过 `global_bias_constraint.evaluate()` 检测各机制的相干性，对违反机制施加软约束 (`gbc_soft_nudge=0.2`)。没有 GBC，层间演化完全不受全局一致性约束。

**修复后预期**: GBC 激活后，CIV 值应回归到 exp_90 水平 (~5-10)，层结构分布更均衡。

### 问题3: 涌现事件为 0

CSC 的 `emergence_min_stability_threshold=0.6`，但所有种子的 `msi_mean` 仅 0.23-0.38，远低于阈值。
GBC 激活后，通过约束调节可能提升 MSI，但可能需要调整 `emergence_stability_threshold`。

## 修复优先级

1. **P0**: 修复 `direction` 初始化 → 激活 GBC → 解决 CIV 异常
2. **P1**: 验证 GBC 激活后 CIV 回归正常范围
3. **P2**: 调整涌现阈值或 MSI 计算，使 emergence 事件能够触发
