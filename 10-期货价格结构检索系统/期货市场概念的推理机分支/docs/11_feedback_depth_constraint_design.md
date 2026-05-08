# P1: 反馈深度约束设计文档

版本：V1.0 | 日期：2026-05-08

---

## 问题陈述

### Phase 2 发现的问题

从 `08_phase2_results.md`：
> **反馈无上限**：margin 反馈可能在变形链的每一层递归生成，需要深度限制以外的约束

### 具体表现

当前 `runner.py` 的 `_run_transfers_with_chain` 中：
```python
# 收集反馈差异（仅在深度0生成，防止递归爆炸）
if chain_depth == 0:
    fb = entity.generate_feedback_differences(absorb_amount, time)
    feedback_diffs.extend(fb)
```

虽然限制了反馈只在深度0生成，但存在以下问题：
1. **无总量控制**：单个主体在一步内可能生成多个反馈差异
2. **无类型限制**：margin 反馈可能再次触发 margin 反馈，形成链式反应
3. **无衰减机制**：反馈差异的 magnitude 没有随深度衰减

### 目标

建立**反馈深度约束机制**，防止反馈差异指数级爆炸，同时保留合理的反馈效应。

---

## 工程设计

### 方案选择

| 方案 | 描述 | 优点 | 缺点 |
|-----|------|------|------|
| A | 仅限制生成深度（当前） | 简单 | 无法控制单步多反馈 |
| B | 添加反馈计数器 | 控制总量 | 不够灵活 |
| C | 反馈类型黑名单 | 防止循环 | 过于 rigid |
| **D** | **综合约束：深度+衰减+类型冷却** | **全面可控** | **实现稍复杂** |

**选择方案 D**：综合约束机制

### 详细设计

#### 1. 深度约束（已有）

```python
# 仅在深度0生成反馈
if chain_depth == 0:
    feedback_diffs = entity.generate_feedback(...)
```

#### 2. 衰减约束（新增）

反馈差异的 magnitude 应用衰减因子：

```python
feedback_decay = 0.5  # 每次反馈衰减50%
fb_magnitude = absorb_amount * leverage * feedback_decay
```

#### 3. 类型冷却（新增）

同一主体在同一步内，同一类型反馈只能生成一次：

```python
# Entity 添加反馈冷却记录
self._feedback_cooldown: Dict[str, int] = {}  # type -> last_time

def can_generate_feedback(self, fb_type: str, time: int) -> bool:
    return self._feedback_cooldown.get(fb_type, -1) < time
```

#### 4. 全局反馈上限（新增）

每步全局反馈差异数量上限：

```python
MAX_FEEDBACK_PER_STEP = 10  # 每步最多10个反馈差异
```

---

## 实现计划

### 修改文件

1. **real_world/core/entity.py**
   - 添加 `_feedback_cooldown` 字段
   - 修改 `generate_feedback_differences` 方法，应用衰减和冷却

2. **real_world/engine/runner.py**
   - 添加全局反馈计数
   - 应用全局上限

3. **experiments/futures/exp_008_feedback_constraint.yaml**（新增）
   - 专门验证反馈约束效果

---

## 预期效果

### 约束前（Phase 2）

```
Step 1: 主体A承接 100 压力
  -> 生成 margin 反馈 80（leverage=4）
  -> margin 反馈变形为 liquidity 反馈
  -> liquidity 反馈再次触发 margin 反馈（理论上可能）
```

### 约束后（Phase 3）

```
Step 1: 主体A承接 100 压力
  -> 生成 margin 反馈 40（leverage=4 × 衰减0.5）
  -> 同一步内，主体A不能再生成 margin 反馈（冷却）
  -> 全局反馈达到10个后，停止生成新反馈
```

---

## 验证指标

1. **单步反馈数量**：不超过 MAX_FEEDBACK_PER_STEP
2. **反馈衰减**：magnitude 符合衰减公式
3. **类型冷却**：同主体同类型每步最多1次
4. **系统稳定性**：高杠杆场景下不再出现压力爆炸

---

*下一步：代码落地*
