# 心跳任务总结 — 2026-05-26 11:16

**触发时间**: 2026-05-26 11:16 CST (Tue)
**心跳机制**: HEARTBEAT.md 强制行动
**阶段**: M4 批次11 完成后，第二阶段准备期

---

## 任务：修复 A3 局域性为零的根本问题

### 问题诊断

今日早间心跳（10:44）分析验证实验数据时发现：**A3_locality 在所有步数中均为 0.0**，导致系统持续扩散而非凝聚。

经过代码审查，发现 **两个相互关联的 bug**：

| 位置 | 问题 | 严重程度 |
|------|------|----------|
| `layers/L0_binary_lattice.py` → `locality_violation()` | 方法体直接返回 `torch.tensor(0.0)`，注释写"由 CNN 结构保证"，但从未实际测量 | 🔴 根本原因 |
| `engine/reactor.py` → `_compute_axiom_loss()` | A3 loss 硬编码为 0，weight=0，完全从损失函数中移除 | 🔴 根本原因 |

**核心问题**：A3 局域性约束在代码中是"纸面公理"——存在于九条公理列表中，但实际计算时始终为 0。这意味着模型在训练时完全没有受到局域性约束，注入的差异可以任意长程传播。

### 修复方案

#### Fix 1: `L0BinaryLattice.locality_violation()` — 实现真实测量

**算法**：
1. 计算变化图 `delta = |next_state - state|`
2. 对 delta 做 **3x3 平均池化**，模拟 LocalConvModel 的 3x3 卷积核影响范围
3. 如果某像素的变化 **> 3倍于其邻域平均**，说明是孤立变化（非局域跳跃）
4. 违背度 = 非局域变化量 / 总变化量

**理论依据**：LocalConvModel 使用 3x3 卷积（padding=1），其 receptive field 为 3x3。理论上，每一步的状态变化不应超出这个范围。如果检测到超出范围的变化，说明模型学习到了非局域依赖，违反了 A3。

#### Fix 2: `reactor._compute_axiom_loss()` — 启用 A3 loss

将硬编码的 `A3_locality = 0.0, weight = 0.0` 替换为：
```python
a3_val = self.layer.locality_violation(state, next_state)
w3 = self.layer.get_axiom_weight("A3_locality")  # = 1.0
a3_loss = a3_val * w3
loss_parts.append(a3_loss)
```

### 验证结果

| 测试 | 结果 |
|------|------|
| `test_l0_binary_lattice.py` (13 tests) | ✅ 全部通过 |
| `test_reactor_step.py` (9 tests) | ✅ 全部通过 |
| `test_axioms_strict.py` (15 tests) | ✅ 全部通过 |
| `test_local_conv_model.py` (9 tests) | ✅ 全部通过 |
| **全量测试套件** (545 tests) | ✅ **522 passed, 23 skipped** (与修复前一致，无回归) |

### Git 提交

```
d2dec8b fix(A3): enable locality violation measurement in L0 + reactor
```

### 后续影响与下一步

1. **训练行为变化**：A3 loss 现在会参与梯度下降，模型会被迫学习局域演化规则。这可能导致：
   - A2 discrete encoding 熵的单调增长趋势**可能减缓或出现平台期**
   - 结构形成率**可能提升**（因为变化被约束在局部）

2. **需要重新运行验证实验**：
   - 之前 `exp_validate_20260506_163319` 的 A3=0 结果不再有效
   - 建议重新运行 N=48, 5000 steps 的实验，观察 A3_locality 是否从 0 变为有意义的值

3. **公理执行顺序**（早间心跳已提出）：
   - 当前：A1→A6→A3→A4→A7→A5→A9
   - 建议：A1(注入) → A3(局域约束) → A4(最小变易) → ...
   - 这个调整尚未执行，留待下一步

---

*心跳笔记 — 2026-05-26 11:16 CST*
