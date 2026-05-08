# Experiment 009: 干预机制验证设计

**理论依据**：《期货市场的差异论解读》第十三章「最近稳态」、第四章「交易所」

**核心假设**：制度边界干预可以改变主体承接能力，迫使系统从 unstable 重新组织，形成新的最近稳态。

---

## 实验目的

验证以下干预类型的效果：
1. **保证金调整**：提高保证金比例 → 降低主体杠杆/承接能力
2. **通道限制**：降低通道容量 → 增加转移阻力
3. **综合干预**：同时调整多个参数

---

## 系统设计

### 新增组件

#### 1. Intervention 类（干预事件）

```python
@dataclass
class Intervention:
    """制度边界干预事件。
    
    干预不是外部强制，而是改变系统运行的条件结构，
    迫使系统在新的约束下重新组织。
    """
    time: int                    # 干预发生的时间步
    type: str                    # 干预类型: margin_adjust / channel_restrict / composite
    target: str                  # 干预目标: entity_id / channel_id / "global"
    params: Dict[str, float]     # 干预参数
    description: str = ""
    
    # 干预效果记录
    pre_state: Dict = field(default_factory=dict)   # 干预前状态快照
    post_state: Dict = field(default_factory=dict)  # 干预后状态快照
```

#### 2. InterventionEngine 类（干预引擎）

```python
class InterventionEngine:
    """干预执行引擎。
    
    职责：
    1. 在指定时间步执行干预
    2. 记录干预前后状态变化
    3. 评估干预效果
    """
    
    def __init__(self, world: World):
        self.world = world
        self.interventions: List[Intervention] = []
        self.executed: List[Intervention] = []
    
    def add_intervention(self, intervention: Intervention):
        """注册干预事件。"""
        self.interventions.append(intervention)
    
    def check_and_execute(self, time: int):
        """检查并执行当前时间步的干预。"""
        for inv in self.interventions:
            if inv.time == time and inv not in self.executed:
                self._execute(inv)
                self.executed.append(inv)
    
    def _execute(self, intervention: Intervention):
        """执行具体干预。"""
        # 记录干预前状态
        intervention.pre_state = self._capture_state()
        
        if intervention.type == "margin_adjust":
            self._apply_margin_adjust(intervention)
        elif intervention.type == "channel_restrict":
            self._apply_channel_restrict(intervention)
        elif intervention.type == "composite":
            self._apply_composite(intervention)
        
        # 记录干预后状态
        intervention.post_state = self._capture_state()
        
        # 记录干预事件到轨迹
        self.world.trace.add_event(Event(
            event_type="intervention",
            time=intervention.time,
            reason=f"干预执行: {intervention.description}",
            difference_id="",
            amount=0,
        ))
```

#### 3. 干预类型实现

**保证金调整干预**：
```python
def _apply_margin_adjust(self, inv: Intervention):
    """调整保证金比例。
    
    效果：
    - 提高保证金比例 → 降低主体可用承接能力
    - 模拟交易所提高保证金要求，迫使主体减仓
    """
    target_id = inv.target
    if target_id in self.world.entities:
        entity = self.world.entities[target_id]
        old_leverage = entity.leverage
        
        # 提高保证金 = 降低杠杆倍数
        new_leverage = inv.params.get("leverage", entity.leverage * 0.5)
        entity.leverage = new_leverage
        
        # 同步调整可用承接能力（保证金占用增加）
        margin_impact = entity.used_capacity * (old_leverage / new_leverage - 1)
        entity.available_capacity = max(0, entity.available_capacity - margin_impact)
        
        inv.description = f"{target_id} 杠杆 {old_leverage:.1f}x → {new_leverage:.1f}x, 承接能力 -{margin_impact:.1f}"
```

**通道限制干预**：
```python
def _apply_channel_restrict(self, inv: Intervention):
    """限制通道容量。
    
    效果：
    - 降低通道容量 → 增加转移阻力
    - 模拟交易所限制某类交易或提高交易成本
    """
    target_id = inv.target
    if target_id in self.world.channels:
        channel = self.world.channels[target_id]
        old_capacity = channel.capacity
        
        # 降低通道容量
        new_capacity = inv.params.get("capacity", channel.capacity * 0.5)
        channel.capacity = new_capacity
        
        # 增加拥堵度
        channel.congestion = min(1.0, channel.congestion + 0.3)
        
        inv.description = f"{target_id} 容量 {old_capacity:.0f} → {new_capacity:.0f}, 拥堵度 +0.3"
```

**综合干预**：
```python
def _apply_composite(self, inv: Intervention):
    """综合干预：同时调整多个参数。"""
    # 同时调整所有主体的保证金
    if "global_leverage_multiplier" in inv.params:
        multiplier = inv.params["global_leverage_multiplier"]
        for entity in self.world.entities.values():
            entity.leverage *= multiplier
    
    # 同时调整所有通道容量
    if "global_capacity_multiplier" in inv.params:
        multiplier = inv.params["global_capacity_multiplier"]
        for channel in self.world.channels.values():
            channel.capacity *= multiplier
    
    inv.description = f"全局干预: 杠杆×{inv.params.get('global_leverage_multiplier', 1)}, 容量×{inv.params.get('global_capacity_multiplier', 1)}"
```

---

## 实验配置

### 基础场景（无干预对照组）

使用 Exp 008 的配置，观察系统自然演化。

### 干预组 1：保证金调整

```yaml
interventions:
  - time: 5                    # 第5步执行干预
    type: margin_adjust
    target: high_leverage_speculator
    params:
      leverage: 2.5            # 杠杆从 5.0 降至 2.5
    description: "高杠杆主体保证金调整"
```

**预期效果**：
- 高杠杆主体承接能力骤降
- 系统压力重新分配
- 可能触发新的稳态形成

### 干预组 2：通道限制

```yaml
interventions:
  - time: 5
    type: channel_restrict
    target: warehouse_receipt_channel
    params:
      capacity: 40             # 容量从 80 降至 40
    description: "库存通道容量限制"
```

**预期效果**：
- 库存差异转移受阻
- 压力在源头积累
- 可能迫使其他通道承接更多压力

### 干预组 3：综合干预

```yaml
interventions:
  - time: 5
    type: composite
    target: global
    params:
      global_leverage_multiplier: 0.6   # 全局杠杆降至 60%
      global_capacity_multiplier: 0.7   # 全局容量降至 70%
    description: "系统性风险管控"
```

**预期效果**：
- 全局承接能力下降
- 系统压力整体降低
- 可能从 unstable 转向 stable

---

## 评估指标

### 1. 稳态指标

```python
def assess_stability(world: World) -> Dict[str, Any]:
    """评估系统稳态程度。"""
    total_pressure = world.total_pressure()
    active_diffs = len(world.get_active_differences())
    
    # 稳态判断标准
    is_stable = (
        total_pressure < 50 and           # 总压力低于阈值
        active_diffs <= 3 and             # 活跃差异数少
        world.time > 5                    # 运行超过5步
    )
    
    return {
        "is_stable": is_stable,
        "total_pressure": total_pressure,
        "active_differences": active_diffs,
        "dominant_type": world.dominant_difference().type if world.dominant_difference() else None,
    }
```

### 2. 干预效果指标

- **压力变化率**：(干预后压力 - 干预前压力) / 干预前压力
- **稳态达成时间**：从干预到系统 stable 的步数
- **稳态维持步数**：stable 状态持续的步数
- **差异重组程度**：干预后新出现的差异类型数量

---

## 实验流程

```
Step 1-4: 系统自然演化至 unstable 状态
Step 5:   执行干预
Step 6-15: 观察系统重新组织过程
          - 压力变化
          - 稳态形成
          - 差异重组
```

---

## 预期结论

**如果假设成立**：
- 干预组比对照组更快达到 stable 状态
- 综合干预效果 > 单一干预
- 干预后系统压力降低，活跃差异减少

**理论意义**：
- 验证差异论「最近稳态」概念：干预改变条件结构，迫使系统重新组织
- 验证交易所作为「有权力的参与者」：制度边界调整可以改变市场稳态

---

## 实现计划

1. **新增文件**：
   - `real_world/core/intervention.py` - Intervention 类
   - `real_world/engine/intervention_engine.py` - InterventionEngine 类

2. **修改文件**：
   - `real_world/core/world.py` - 添加干预引擎集成
   - `real_world/engine/runner.py` - 每步检查并执行干预
   - `real_world/io/yaml_loader.py` - 支持从 YAML 加载干预配置

3. **实验配置**：
   - `experiments/futures/exp_009a_intervention_margin.yaml`
   - `experiments/futures/exp_009b_intervention_channel.yaml`
   - `experiments/futures/exp_009c_intervention_composite.yaml`

---

*设计完成，等待实现。*
