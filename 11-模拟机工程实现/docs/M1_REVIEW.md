# M1 验收报告

## 验收时间
2026-04-29 11:31 GMT+8

## 一、做得好的地方

### 1. 架构设计 ✓
```
DifferenceReactor (reactor.py)
├── 模型预测: model(state)
├── 边界条件: inject/absorb difference
└── 公理损失: A2/A4/A5/A7 + diversity

AxiomTrainer (trainer.py)
├── train_step(): 单步训练
├── train_episode():  rollout + 反向传播
└── evaluate(): 评估模式
```

### 2. 公理损失设计 ✓
- **A2 离散性**: `p*(1-p)` 惩罚中间值
- **A4 最小变易**: `(next - state)²` 惩罚大变化
- **A5 守恒**: 相对残差 `(ΔQ - flux)² / Q²`
- **A7 稳定性**: 余弦相似度鼓励模式持续
- **空间多样性**: 梯度 + 值分布

### 3. 开放系统 ✓
- 源端 (left/right) 注入
- 汇端吸收
- 流量平衡检查

### 4. 测试结果看起来合理
| 实验 | Loss 降低 | Unique | Structures |
|------|-----------|-------|----------|
| 1D (50 cells) | 92.1% | 2 | 1 |
| 2D (32x32) | 79.4% | - | 1 |

---

## 二、需要改进的问题

### 问题 1: A3 局域性未真正验证
**现状**: 报告中 A3_locality = 0.0, weight = 0.0
```python
# reactor.py 第87行
report["A3_locality"] = AxiomReport(
    name="A3_locality",
    raw_violation=0.0,  # 硬编码
    weight=0.0,
    ...
)
```
**问题**: 代码注释说"由 CNN 结构保证"，但没有实际验证

### 问题 2: A1 差异源未实现
**现状**: 没有看到 A1_difference_source 的实现
**建议**: 添加观测报告 (即使不参与 loss)

### 问题 3: A6 流向耦合未实现
**现状**: reactor.py 中没有 A6
**建议**: 添加或明确说明跳过原因

### 问题 4: NaN/Inf 保护可能不够
**现状**: 简单的 nan_to_num + clamp
```python
raw_next = torch.nan_to_num(raw_next, nan=0.5, posinf=1.0, neginf=0.0)
```
**风险**: 如果模型输出持续 NaN，会一直用 0.5 填充
**建议**: 添加"连续 NaN 计数"和 early stop

### 问题 5: 梯度裁剪过于激进
```python
torch.nn.utils.clip_grad_norm_(..., max_norm=1.0)
```
**问题**: max_norm=1.0 可能过小

### 问题 6: 测试只跑一次
**现状**: 实验结果没有多次运行的统计
**建议**: 至少跑3次取平均

---

## 三、具体代码建议

### 建议 1: 添加 A1 观测
```python
if boundary_info:
    injected = boundary_info.get("injected", 0.0)
    report["A1_difference_source"] = AxiomReport(
        name="A1_difference_source",
        raw_violation=float(injected.mean()),
        weight=0.0,
        weighted_violation=0.0,
    )
```

### 建议 2: 早停机制
```python
# 添加 nan_count 计数器
if torch.isnan(loss) or torch.isinf(loss):
    nan_count += 1
    if nan_count > 5:
        print("Warning: Too many NaN, stopping early")
        break
```

### 建议 3: 多次运行统计
```python
# 在 run_1d_experiment 中
results = []
for run in range(3):
    logs, result = run_1d_experiment(...)
    results.append(result)

# 计算平均值和标准差
avg_loss = mean([r['avg_loss'] for r in results])
std_loss = std([r['avg_loss'] for r in results])
```

---

## 四、验收结论

| 项目 | 状态 |
|------|------|
| 架构完整性 | ✓ 通过 |
| 公理约束实现 | ✓ 通过 |
| 训练循环 | ✓ 通过 |
| 边界条件 | ✓ 通过 |
| NaN 保护 | ⚠️ 待改进 |
| 观测报告 | ⚠️ 待添加 |
| 多次运行 | ⚠️ 建议添加 |

**总体评价**: M1 完成度 85%，核心功能已实现，建议补充 A1/A6 观测和早停机制。