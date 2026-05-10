# Phase 2 设计：反馈、干预、变形

版本：V0.1 ｜ 日期：2026-05-08
定位：Phase 1 验证发现的三个结构性缺口，从差异论角度重新定义

---

## 零、设计原则

**拓扑即智慧。** 这份文本不是待做清单，而是推理结构。它会回流到每一次思考中，改变推理路径。

Phase 1 证明了六个核心机制可以跑出符合差异论预期的动力学行为。但 Phase 1 的结构是**单向的**：

```
差异源 ──→ 通道 ──→ 承接体 ──→ 状态
                ↑
            破缺释放压力
```

Phase 2 要补上**回流**：

```
差异源 ──→ 通道 ──→ 承接体 ──→ 状态
  ↑         ↑         │         │
  │         │         ▼         │
  │         │    反馈生成新差异  │
  │         │         │         │
  │         └─────┘   │         │
  │                   │         │
  └──── 变形链 ───────┘         │
                                │
              交易所干预 ────────┘
```

---

## 一、反馈循环（Feedback Loop）

### 1.1 理论基础

差异论的核心判断：**差异不能凭空消失，只能换位置、形式或承接体。**

但 Phase 1 的代码隐含了一个假设：差异被承接后，承接体只是"容量减少"。这忽略了承接本身会产生**新差异**。

现实中的反馈链：
- 承压 → 占用保证金 → 流动性下降
- 流动性下降 → 承接力进一步下降（无法开新仓）
- 承接力下降 → 差异更难转移 → 差异继续积累
- 差异积累 → 更多破缺 → 更多保证金追缴
- 保证金追缴 → 强制平仓 → 释放承接力，但产生新的流动性差异

**这不是"因果循环"，而是"差异生成差异"。** 承接体在承接差异的过程中，自身成为一个新的差异源。

### 1.2 结构定义

**反馈差异（Feedback Difference）**：承接体在承接差异时，因自身状态变化而产生的新差异。

```yaml
# 反馈差异的结构
feedback_difference:
  source_entity: 承压的主体
  trigger: 承压超过阈值
  new_diff_type: margin / liquidity / position
  generation_rate: 与承压量和杠杆成正比
  decay: 反馈差异自身也会衰减
```

**反馈的三个层次**：

| 层次 | 触发条件 | 产生的新差异 | 现实对应 |
|---|---|---|---|
| 保证金反馈 | capacity_ratio > 0.6 | margin 差异 | 保证金追缴 |
| 流动性反馈 | liquidity < risk_tolerance * 0.3 | liquidity 差异 | 流动性枯竭 |
| 强平反馈 | available_capacity <= 0 | position 差异 + liquidity 差异 | 强制平仓 |

### 1.3 代码结构

当前 `Entity._apply_absorption_feedback` 已经有反馈逻辑的雏形，但它只修改 Entity 自身属性，**没有生成新的 DifferenceSource**。

Phase 2 的改动：

```python
# Entity 新增方法
def generate_feedback_differences(self, absorb_amount: float) -> List[dict]:
    """承压后生成反馈差异。
    
    返回差异定义列表，由 runner 注入世界。
    这不是"副作用"，而是差异生成差异的正向过程。
    """
    feedback = []
    if self.capacity_ratio > 0.6:
        feedback.append({
            "id": f"feedback_margin_{self.id}_{time}",
            "type": "margin",
            "source_node": self.id,
            "target_node": "clearing",
            "magnitude": absorb_amount * 0.3 * self.leverage,
            "recurrent": False,  # 反馈差异是一次性的
        })
    if self.liquidity < self.risk_tolerance * 0.3:
        feedback.append({
            "id": f"feedback_liquidity_{self.id}_{time}",
            "type": "liquidity",
            "source_node": self.id,
            "target_node": "market",
            "magnitude": absorb_amount * 0.2,
            "recurrent": False,
        })
    return feedback
```

Runner 在 `_run_transfers` 中收集反馈差异，注入世界：

```python
# runner.py 修改
def _run_transfers(self, time: int):
    feedback_diffs = []
    for diff_id, diff in list(self.world.differences.items()):
        # ... 现有转移逻辑 ...
        for entity in entities:
            entity.absorb(absorb_amount)
            # 新增：收集反馈差异
            feedback = entity.generate_feedback_differences(absorb_amount, time)
            feedback_diffs.extend(feedback)
    
    # 注入反馈差异到世界
    for fb in feedback_diffs:
        self.world.add_difference(fb)
```

### 1.4 关键约束

**反馈差异不是"修复"，而是"差异生成差异"。** 它不消除原有差异，而是在差异结构中增加新的节点。这意味着：

- 反馈可能让系统更快破缺（正反馈）
- 也可能让系统找到新的转移路径（负反馈）
- 但**不会让差异归零**

---

## 二、干预多动作（Intervention Multi-Action）

### 2.1 理论基础

Phase 1 验证报告的关键发现：**交易所干预重组差异结构，但不消除差异本身。**

当前干预只有两种动作（提保证金、强制减仓），都只作用于**承接端**。但差异论的框架下，交易所作为二阶承接位置，可以作用于三个节点：

| 作用节点 | 动作 | 效果 | 现实对应 |
|---|---|---|---|
| 差异源 | 降低差异生成率 | 减少 recurrent 压力 | 限仓、限制新开仓 |
| 通道 | 扩大通道容量 | 增加转移能力 | 放宽交割品等级、增加交割库 |
| 承接体 | 释放承接力 | 恢复承接能力 | 降保证金、释放冻结资金 |

**关键判断**：Phase 1 exp_003 持续破缺的原因是——干预只削减投机者承接力，既未降低差异生成率，也未扩通道容量。**如果 recurrent 不停，单靠承接端干预拦不住。**

### 2.2 结构定义

**干预动作（Intervention Action）**：

```yaml
# 干预动作的结构
intervention_action:
  target_node: difference_source / channel / entity
  action_type: reduce_recurrent / expand_capacity / release_capacity
  magnitude: 干预力度
  side_effects: 干预产生的新差异
```

**三种干预动作的详细设计**：

#### 动作一：降低差异生成率（Reduce Recurrent）

```python
def intervene_reduce_recurrent(self, world, time: int, reduction: float = 0.3):
    """限制新开仓，降低差异生成率。
    
    效果：recurrent_rate *= (1 - reduction)
    限制对象：投机性差异源（expectation, liquidity）
    不限制：结构性差异源（inventory, delivery）——这些是真实供需
    """
    for diff in world.differences.values():
        if diff.recurrent and diff.type in ("expectation", "liquidity", "margin"):
            old_rate = diff.recurrent_rate
            diff.recurrent_rate *= (1 - reduction)
            # 记录
            world.trace.add_event(...)
```

#### 动作二：扩大通道容量（Expand Channel）

```python
def intervene_expand_channel(self, world, time: int, channel_type: str, expansion: float = 0.5):
    """扩大通道容量。
    
    效果：channel.capacity *= (1 + expansion)
    现实对应：放宽交割品等级、增加交割库、放宽持仓限制
    """
    for ch in world.channels.values():
        if ch.from_type == channel_type or ch.id.startswith(channel_type):
            old_cap = ch.capacity
            ch.capacity *= (1 + expansion)
            # 记录
            world.trace.add_event(...)
```

#### 动作三：释放承接力（Release Capacity）

```python
def intervene_release_entity(self, world, time: int, entity_type: str, release: float = 0.3):
    """释放承接力。
    
    效果：entity.release(entity.used_capacity * release)
    现实对应：降保证金、释放冻结资金
    """
    for entity in world.entities.values():
        if entity.type == entity_type:
            release_amount = entity.used_capacity * release
            entity.release(release_amount)
            # 记录
            world.trace.add_event(...)
```

### 2.3 干预策略

干预不是随机的，应该有一个**策略函数**，根据当前状态选择干预动作：

```python
def choose_intervention(self, world) -> List[InterventionAction]:
    """根据当前状态选择干预动作组合。
    
    策略：
    1. 差异源压力高 → 降低差异生成率
    2. 通道拥堵 → 扩大通道容量
    3. 主体承压 → 释放承接力
    4. 持续破缺 → 三者同时执行
    """
    actions = []
    
    # 检查差异源压力
    high_recurrent_diffs = [d for d in world.differences.values() 
                           if d.recurrent and d.pressure > 50]
    if high_recurrent_diffs:
        actions.append(InterventionAction("reduce_recurrent", 0.3))
    
    # 检查通道拥堵
    congested = [c for c in world.channels.values() 
                if c.status == ChannelStatus.CONGESTED]
    if congested:
        actions.append(InterventionAction("expand_channel", 0.5))
    
    # 检查主体承压
    stressed = [e for e in world.entities.values() 
               if e.status in (EntityStatus.STRESSED, EntityStatus.MARGIN_CALLED)]
    if stressed:
        actions.append(InterventionAction("release_entity", 0.3))
    
    return actions
```

### 2.4 干预的副作用

**干预本身产生新差异。** 这是差异论的核心判断——干预不是消除差异，而是重组差异结构。

- 提保证金 → 产生流动性差异（投机者资金被锁定）
- 扩通道容量 → 产生规则差异（交割标准放宽可能引发质量争议）
- 限仓 → 产生预期差异（市场预期交易所进一步干预）

```python
def generate_intervention_differences(self, action, world, time) -> List[dict]:
    """干预产生的副作用差异。"""
    side_effects = []
    if action.type == "reduce_recurrent":
        # 限仓产生预期差异
        side_effects.append({
            "id": f"intervention_expectation_{time}",
            "type": "expectation",
            "magnitude": action.magnitude * 20,
            "recurrent": False,
        })
    return side_effects
```

---

## 三、变形链（Transformation Chain）

### 3.1 理论基础

Phase 1 的差异转移是**单步的**：差异经通道转移后，形式可能变化（如 inventory→basis），但变化后的差异没有继续转移。

现实中的差异运动是**链式的**：
```
库存差异 → 基差差异 → 价格差异 → 保证金差异 → 流动性差异
```

每一步变形都是**差异生成新差异**的过程，不是简单的"类型改变"。

### 3.2 结构定义

**变形链（Transformation Chain）**：

```yaml
# 变形链的结构
transformation_chain:
  - step: 1
    from: inventory
    via: basis_channel
    to: basis
  - step: 2
    from: basis
    via: futures_contract_channel
    to: price
  - step: 3
    from: price
    via: margin_clearing_channel
    to: margin
  - step: 4
    from: margin
    via: position_reduction_channel
    to: liquidity
```

**变形规则已经存在**（`futures_rules.py` 中的 `DIFF_TRANSFORM_RULES`），但 runner 没有递归执行。

### 3.3 代码结构

**变形不是"继续转移同一个差异"，而是"转移后产生的新差异继续寻找通道"。**

```python
# runner.py 修改
def _run_transfers(self, time: int):
    # 使用队列处理变形链
    pending_diffs = list(self.world.differences.items())
    max_chain_depth = 5  # 防止无限循环
    chain_depth = 0
    
    while pending_diffs and chain_depth < max_chain_depth:
        next_round = []
        for diff_id, diff in pending_diffs:
            if diff.status != DifferenceStatus.ACTIVE or diff.pressure <= 0:
                continue
            
            channel = choose_channel(diff, list(self.world.channels.values()))
            if channel is None:
                diff.accumulate(diff.pressure)
                continue
            
            # 转移
            transferred, remaining = transfer_difference(diff, channel, self.world.trace, time)
            
            # 检查变形
            new_type = get_transform_type(diff.type, channel.from_type)
            if new_type and new_type != diff.type and transferred > 0:
                # 生成变形差异
                transform_diff = self._create_transform_diff(diff, new_type, transferred, time)
                if transform_diff:
                    next_round.append((transform_diff.id, transform_diff))
                    self.world.add_difference(transform_diff)
                    self.world.trace.add_event(
                        time=time,
                        event_type="transform",
                        difference_id=diff.id,
                        amount=transferred,
                        reason=f"差异变形: {diff.type} → {new_type}，经通道 {channel.id}",
                    )
            
            if remaining > 0:
                diff.accumulate(remaining)
        
        pending_diffs = next_round
        chain_depth += 1
```

### 3.4 变形链的守恒

**变形不消灭差异，只改变形式。** 守恒检查需要覆盖整个变形链：

```
初始差异压力 = Σ(每步转移量) + Σ(每步剩余积累) + Σ(每步成本)
```

如果变形链中途有差异"消失"，就是模型错误。

### 3.5 变形链的终止条件

变形链在以下情况终止：
1. **无可用通道**：变形后的差异类型没有匹配的通道
2. **压力耗尽**：转移过程中压力被消耗到阈值以下
3. **达到最大深度**：防止无限循环
4. **进入稳态**：差异被完全承接

---

## 四、三个机制的拓扑关系

反馈、干预、变形不是三个独立模块，而是**同一拓扑的三个视角**：

```
                    ┌─────────────────────────────────────┐
                    │           差异源 (Difference)        │
                    │  inventory / delivery / expectation  │
                    └──────────────┬──────────────────────┘
                                   │
                          ┌────────▼────────┐
                          │   通道 (Channel) │
                          │  转移 + 变形     │
                          └────────┬────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │        承接体 (Entity)               │
                    │  承接 → 反馈生成新差异               │
                    │  ┌─────────────────────────┐        │
                    │  │ 保证金反馈 → margin diff │        │
                    │  │ 流动性反馈 → liq diff    │        │
                    │  │ 强平反馈 → position diff │        │
                    │  └─────────┬───────────────┘        │
                    └────────────│─────────────────────────┘
                                 │
                    ┌────────────▼────────────────────────┐
                    │      变形链 (Transform Chain)        │
                    │  inventory → basis → price → margin  │
                    │           → liquidity                │
                    └────────────┬─────────────────────────┘
                                 │
                    ┌────────────▼────────────────────────┐
                    │    交易所干预 (Intervention)          │
                    │  作用于：差异源 / 通道 / 承接体       │
                    │  副作用：产生新差异                   │
                    └─────────────────────────────────────┘
```

**核心洞察**：
- **反馈**是承接体内部的差异生成
- **变形**是通道上的差异形式转换
- **干预**是外部对差异结构的重组

三者共同构成差异运动的**完整拓扑**。

---

## 五、Phase 2 开发路线

| 阶段 | 目标 | 完成标准 |
|---|---|---|
| 2.1 反馈循环 | Entity 生成反馈差异，注入世界 | exp_003 中反馈差异可见，影响后续转移 |
| 2.2 干预多动作 | 三种干预动作 + 策略函数 + 副作用差异 | exp_003 中干预能降低破缺次数 |
| 2.3 变形链 | 递归转移 + 变形差异生成 | exp_001 中 inventory→basis→price 链式可见 |
| 2.4 集成验证 | 三个机制同时运行 | 新实验 exp_005 验证完整拓扑 |
| 2.5 回写 | 验证结果回写到设计文本 | docs/08_phase2_results.md |

---

## 六、新实验设计

### exp_005：完整拓扑验证

```yaml
experiment:
  id: exp_005
  name: 完整拓扑验证
  description: 验证反馈循环+干预多动作+变形链的完整拓扑

world:
  name: Full-Topology-World
  max_steps: 30

# 差异源：库存短缺 + 近月交割压力
# 承接体：产业空头 + 投机多头 + 交易所
# 通道：仓单→交割→基差→期货合约→保证金
# 预期：变形链 inventory→delivery→basis→price→margin→liquidity
# 预期：反馈差异 margin/liquidity 从承接体生成
# 预期：交易所三重干预后破缺减少
```

---

## 七、铁律补充

Phase 2 新增铁律：
- **反馈差异不是修复**：它增加差异节点，不消除原有差异
- **干预不消除差异**：干预重组差异结构，副作用产生新差异
- **变形不消灭差异**：变形改变形式，守恒贯穿整条链
- **变形链有深度限制**：防止无限循环，最大深度 5
