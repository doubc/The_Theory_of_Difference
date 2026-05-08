# Phase 3：守恒检查精确化

版本：V1.0 | 日期：2026-05-08

---

## 问题背景

Phase 2 的守恒检查使用近似计算：
```python
channel_loss = max(0, transferred - transformed)
```

这会导致跨步骤的累积误差，因为 `transferred` 和 `transformed` 可能来自不同的变形步骤。

---

## 解决方案

### 1. 精确损耗追踪（transfer.py）

在 `transfer_and_transform` 中，每次变形时精确计算并记录损耗：

```python
transform_efficiency = max(0.3, 1.0 - channel.congestion)
transform_pressure = transferred * transform_efficiency
loss_amount = transferred - transform_pressure  # 精确损耗

# 记录变形事件（包含精确损耗）
trace.add_event(
    time=time,
    event_type="transform",
    difference_id=difference.id,
    channel_id=channel.id,
    amount=transform_pressure,
    reason=f"差异变形: {difference.type} → {new_type}，经通道 {channel.id}，深度 {chain_depth}，损耗={loss_amount:.2f}",
)

# 单独记录损耗事件（用于精确守恒检查）
if loss_amount > 0.01:
    trace.add_event(
        time=time,
        event_type="loss",
        difference_id=difference.id,
        channel_id=channel.id,
        amount=loss_amount,
        reason=f"通道损耗: 转移 {transferred:.2f}，效率 {transform_efficiency:.2f}，损耗 {loss_amount:.2f}",
    )
```

### 2. 精确守恒检查（conservation.py）

从 `loss` 事件读取精确损耗，而非近似计算：

```python
# Phase 3：精确通道损耗（从 loss 事件读取）
channel_loss = sum(
    e.amount for e in trace.events
    if e.event_type == "loss" and e.time == time
)
```

---

## 验证结果

运行 `exp_007a_no_break.yaml`：

```yaml
# transform 事件现在包含损耗信息
- event_type: transform
  amount: 10.5
  reason: '差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0，损耗=24.50'

# loss 事件单独记录精确损耗
- event_type: loss
  amount: 24.5
  reason: '通道损耗: 转移 35.00，效率 0.30，损耗 24.50'
```

验证计算：
- 转移量：35.00
- 变形效率：max(0.3, 1.0 - congestion) = 0.30（高拥堵）
- 变形后压力：35.00 × 0.30 = 10.5 ✓
- 损耗：35.00 - 10.5 = 24.50 ✓

---

## 改进效果

| 方面 | Phase 2 | Phase 3 |
|-----|---------|---------|
| 损耗计算 | 近似（transferred - transformed） | 精确（每步单独记录） |
| 误差来源 | 跨步骤累积 | 无累积误差 |
| 可追溯性 | 低 | 高（每个 loss 事件可追溯到具体转移） |
| 调试能力 | 差 | 强（可查看每步的损耗详情） |

---

## 下一步

- [ ] P1: 反馈深度约束（限制反馈在变形链中的递归层数）
- [ ] P1: 新实验设计（验证干预能否让系统从 unstable 走向 stable）
- [ ] P2: 多品种支持（Phase 3 前置）

---

*本文档随代码迭代更新。*
