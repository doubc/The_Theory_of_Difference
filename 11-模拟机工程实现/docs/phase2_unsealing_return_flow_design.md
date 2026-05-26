# Phase 2 设计文档：解封机制与回流通道

> **阶段**：第二阶段 — 象界 → 前主体态  
> **核心组件**：解封机制 (Unsealing Mechanism) + 回流通道 (Return Flow Channel)  
> **对应理论**：《象界》第八章（前主体态）+ 《差异论》高语义回流  
> **日期**：2026-05-26  
> **状态**：设计阶段 — 待实现

---

## 一、问题定义

M4 批次 11 已完成：分层封装、九公理严格化、汉明几何、引力势验证、跨层级引力调制。

**当前断点**：
- `xiangjie/chain.py` 能**检测**结构是否跨过八章门槛（边界→界面→自维持→记忆→复制→筛选→功能→前主体态）
- `engine/pre_subjectivity_convergence.py` 能**判定**六机制是否耦合收束
- **但缺少**：当结构达到前主体态后，**如何解封**高语义层，以及高语义内容**如何回流**到低语义结构

这就是第二阶段的两个核心问题。

---

## 二、解封机制 (Unsealing Mechanism)

### 2.1 理论依据

《象界》第八章的核心论断：

> "前主体态不是主体，却是差异结构在低语义层中所能达到的最充分完成形态。"

前主体态是**结构地板**——它不是高语义世界本身，而是高语义世界可以**着陆**的地方。

**解封的含义**：
- 不是"打开一个盖子让高语义进来"
- 而是前主体态结构**自身达到足够密度**后，其边界从"低语义界面"转变为"可承载高语义的界面"
- 解封是**结构自发的**，不是外部注入的

**关键判据**：
1. 六机制全部达标（`SixThresholdDetector` 通过）
2. 机制间耦合强度超过阈值（`PreSubjectivityConvergence` 的耦合检测）
3. 结构在扰动下保持稳定（稳定性测试通过）
4. 语义防火墙通过（无高语义词汇污染低语义描述）

### 2.2 工程接口设计

```python
# 文件：engine/unsealing_mechanism.py (待创建)

from dataclasses import dataclass
from typing import Optional, Dict, List
import torch


@dataclass
class UnsealingEvent:
    """解封事件"""
    structure_id: int
    timestamp: int
    convergence_report: ConvergenceResult  # 来自 PreSubjectivityConvergence
    unsealing_level: int  # 解封等级：1=边界开放, 2=内部耦合, 3=全通道开放
    reason: str  # 解封原因说明
    high_semantic_capacity: float  # 可承载的高语义容量 [0, 1]


class UnsealingMechanism:
    """
    解封机制 — 当结构达到前主体态时，自动触发解封。
    
    解封不是单次事件，而是分级过程：
      Level 1: 边界界面开放 — 允许外部高语义扰动进入边界层
      Level 2: 内部耦合开放 — 允许高语义内容在结构内部各机制间流动
      Level 3: 全通道开放 — 结构完全进入可承载高语义的状态
    
    每个等级都有独立的触发条件和回退机制。
    """
    
    def __init__(
        self,
        # Level 1 条件
        l1_coupling_threshold: float = 0.3,
        l1_stability_threshold: float = 0.5,
        # Level 2 条件
        l2_coupling_threshold: float = 0.5,
        l2_stability_threshold: float = 0.7,
        # Level 3 条件
        l3_coupling_threshold: float = 0.7,
        l3_stability_threshold: float = 0.85,
        # 回退机制
        degradation_on_failure: bool = True,
    ):
        self.l1_coupling_threshold = l1_coupling_threshold
        self.l1_stability_threshold = l1_stability_threshold
        self.l2_coupling_threshold = l2_coupling_threshold
        self.l2_stability_threshold = l2_stability_threshold
        self.l3_coupling_threshold = l3_coupling_threshold
        self.l3_stability_threshold = l3_stability_threshold
        self.degradation_on_failure = degradation_on_failure
        
        # 当前解封状态
        self._unsealing_levels: Dict[int, int] = {}  # structure_id → level
        self._unsealing_events: List[UnsealingEvent] = []
    
    def evaluate(
        self,
        structure_id: int,
        convergence_result: ConvergenceResult,
        timestamp: int,
    ) -> Optional[UnsealingEvent]:
        """
        评估结构是否需要解封 / 升级解封等级。
        
        逻辑：
          1. 如果未达到 Level 1 条件 → 无解封
          2. 如果已达 Level N 但满足 Level N+1 → 升级
          3. 如果已达 Level N 但不满足 Level N → 降级（若 enabled）
        
        Returns:
          UnsealingEvent 如果解封等级发生变化，否则 None
        """
        current_level = self._unsealing_levels.get(structure_id, 0)
        
        # 判定应达到的等级
        target_level = self._compute_target_level(convergence_result)
        
        if target_level == current_level:
            return None  # 无变化
        
        # 计算解封容量（基于耦合强度和稳定性）
        capacity = self._compute_capacity(convergence_result)
        
        event = UnsealingEvent(
            structure_id=structure_id,
            timestamp=timestamp,
            convergence_report=convergence_result,
            unsealing_level=target_level,
            reason=self._reason(current_level, target_level),
            high_semantic_capacity=capacity,
        )
        
        self._unsealing_levels[structure_id] = target_level
        self._unsealing_events.append(event)
        return event
    
    def _compute_target_level(self, result: ConvergenceResult) -> int:
        """根据收束结果计算应达到的解封等级"""
        if not result.all_conditions_met:
            return 0
        
        min_coupling = result.min_coupling
        stability = result.stability_score
        
        if (min_coupling >= self.l3_coupling_threshold 
                and stability >= self.l3_stability_threshold):
            return 3
        elif (min_coupling >= self.l2_coupling_threshold 
                and stability >= self.l2_stability_threshold):
            return 2
        elif (min_coupling >= self.l1_coupling_threshold 
                and stability >= self.l1_stability_threshold):
            return 1
        return 0
    
    def _compute_capacity(self, result: ConvergenceResult) -> float:
        """计算高语义承载容量 [0, 1]"""
        if not result.all_conditions_met:
            return 0.0
        # 容量 = 耦合强度 × 稳定性 × 六阈值满足度
        six_score = 1.0 if result.six_thresholds_met else 0.0
        return min(1.0, (result.min_coupling * result.stability_score * six_score))
    
    def _reason(self, from_level: int, to_level: int) -> str:
        if to_level > from_level:
            return f"解封升级: Level {from_level} → Level {to_level}"
        else:
            return f"解封降级: Level {from_level} → Level {to_level}"
    
    def get_current_level(self, structure_id: int) -> int:
        return self._unsealing_levels.get(structure_id, 0)
    
    def get_event_history(self, structure_id: Optional[int] = None) -> List[UnsealingEvent]:
        if structure_id is not None:
            return [e for e in self._unsealing_events if e.structure_id == structure_id]
        return self._unsealing_events
```

### 2.3 解封等级的理论对应

| 等级 | 理论对应 | 工程含义 |
|------|---------|---------|
| Level 0 | 未达前主体态 | 无解封，结构仅低语义运行 |
| Level 1 | 边界界面化完成 | 边界可接收外部高语义扰动，但内部仍封闭 |
| Level 2 | 六机制耦合形成 | 高语义可在内部机制间流动，但尚未完全整合 |
| Level 3 | 前主体态完全形成 | 结构完全可承载高语义，进入"象→意义"的过渡区 |

---

## 三、回流通道 (Return Flow Channel)

### 3.1 理论依据

《差异论》的核心论断：

> "高语义世界不是从纯存在中直接跃出，而必须经过某种'可持存的显现'才能成立。"

但反过来同样重要：

> "高语义世界一旦形成，它必须能够回流到低语义层，否则就是空中楼阁。"

**回流的含义**：
- 高语义内容（意义、制度、叙事、身份）不是独立存在的
- 它们必须**锚定**在低语义结构上，通过低语义机制维持自身
- 回流是**双向的**：低语义→高语义（涌现），高语义→低语义（锚定）

**回流通道的设计原则**：
1. **不破坏低语义自主性**：回流不是高语义对低语义的"控制"，而是"锚定"
2. **保持语义防火墙**：回流过程中，低语义层不被高语义词汇污染
3. **可逆性**：当高语义内容失去低语义锚定时，应能自动剥离

### 3.2 工程接口设计

```python
# 文件：engine/return_flow_channel.py (待创建)

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import torch
import numpy as np


@dataclass
class HighSemanticPayload:
    """高语义载荷 — 需要回流到低语义层的内容"""
    payload_id: str
    content_type: str  # 'meaning' | 'institution' | 'narrative' | 'identity'
    content_vector: torch.Tensor  # 高语义内容的向量表示
    anchor_strength: float = 0.0  # 当前锚定强度 [0, 1]
    created_at: int = 0  # 时间戳


@dataclass
class AnchorPoint:
    """锚点 — 高语义内容在低语义结构上的附着位置"""
    structure_id: int
    mechanism: str  # 锚定在哪个机制上: 'boundary' | 'self_sustaining' | ...
    location: Optional[torch.Tensor] = None  # 空间位置（如有）
    coupling_strength: float = 0.0  # 与对应机制的耦合强度


@dataclass
class ReturnFlowEvent:
    """回流事件"""
    payload: HighSemanticPayload
    anchor: AnchorPoint
    timestamp: int
    success: bool
    reason: str
    residual_strength: float = 0.0  # 回流后的剩余锚定强度


class ReturnFlowChannel:
    """
    回流通道 — 管理高语义内容向低语义结构的回流与锚定。
    
    核心机制：
      1. 锚定选择：为每个高语义载荷选择最佳的低语义锚点
      2. 耦合验证：验证锚点与载荷的耦合是否足够强
      3. 持续监测：监测已锚定内容的锚定强度衰减
      4. 自动剥离：当锚定强度低于阈值时，自动剥离高语义内容
    """
    
    # 锚定机制的权重（不同高语义类型偏好不同的锚点）
    ANCHOR_WEIGHTS = {
        'meaning': {'function': 0.4, 'selection': 0.3, 'memory': 0.2, 'replication': 0.1},
        'institution': {'boundary': 0.4, 'self_sustaining': 0.3, 'function': 0.2, 'selection': 0.1},
        'narrative': {'memory': 0.4, 'replication': 0.3, 'selection': 0.2, 'function': 0.1},
        'identity': {'boundary': 0.5, 'self_sustaining': 0.3, 'function': 0.2},
    }
    
    def __init__(
        self,
        anchor_threshold: float = 0.3,      # 最小锚定强度
        decay_rate: float = 0.01,            # 每步锚定强度衰减率
        min_retention_steps: int = 10,       # 最小保留步数（防止过快剥离）
    ):
        self.anchor_threshold = anchor_threshold
        self.decay_rate = decay_rate
        self.min_retention_steps = min_retention_steps
        
        # 已锚定的内容: payload_id → (anchor, strength, steps_since_anchor)
        self._anchored: Dict[str, tuple] = {}
        self._flow_events: List[ReturnFlowEvent] = []
    
    def attempt_anchor(
        self,
        payload: HighSemanticPayload,
        available_structures: List[Dict],  # [{structure_id, mechanisms: {name: strength}}]
        timestamp: int,
    ) -> ReturnFlowEvent:
        """
        尝试为高语义载荷找到锚点。
        
        Args:
            payload: 高语义载荷
            available_structures: 可用的低语义结构及其机制强度
            timestamp: 当前时间戳
        
        Returns:
            ReturnFlowEvent 回流事件
        """
        # 1. 选择最佳锚点
        best_anchor = self._select_best_anchor(payload, available_structures)
        
        if best_anchor is None:
            event = ReturnFlowEvent(
                payload=payload,
                anchor=AnchorPoint(structure_id=-1, mechanism="none"),
                timestamp=timestamp,
                success=False,
                reason="无可用锚点",
            )
            self._flow_events.append(event)
            return event
        
        # 2. 验证耦合强度
        coupling = best_anchor.coupling_strength
        if coupling < self.anchor_threshold:
            event = ReturnFlowEvent(
                payload=payload,
                anchor=best_anchor,
                timestamp=timestamp,
                success=False,
                reason=f"耦合强度 {coupling:.3f} < 阈值 {self.anchor_threshold}",
            )
            self._flow_events.append(event)
            return event
        
        # 3. 成功锚定
        self._anchored[payload.payload_id] = (
            best_anchor,
            coupling,
            0,  # steps_since_anchor
        )
        
        event = ReturnFlowEvent(
            payload=payload,
            anchor=best_anchor,
            timestamp=timestamp,
            success=True,
            reason=f"锚定在 structure={best_anchor.structure_id}, "
                   f"mechanism={best_anchor.mechanism}",
            residual_strength=coupling,
        )
        self._flow_events.append(event)
        return event
    
    def _select_best_anchor(
        self,
        payload: HighSemanticPayload,
        available_structures: List[Dict],
    ) -> Optional[AnchorPoint]:
        """为载荷选择最佳锚点"""
        weights = self.ANCHOR_WEIGHTS.get(payload.content_type, {})
        if not weights:
            return None
        
        best_anchor = None
        best_score = 0.0
        
        for struct in available_structures:
            struct_id = struct.get('structure_id')
            mechanisms = struct.get('mechanisms', {})
            
            for mech_name, mech_weight in weights.items():
                mech_strength = mechanisms.get(mech_name, 0.0)
                score = mech_weight * mech_strength
                
                if score > best_score:
                    best_score = score
                    best_anchor = AnchorPoint(
                        structure_id=struct_id,
                        mechanism=mech_name,
                        coupling_strength=mech_strength,
                    )
        
        return best_anchor
    
    def step(self, timestamp: int) -> List[ReturnFlowEvent]:
        """
        执行一步回流通道演化。
        
        功能：
          1. 对所有已锚定内容衰减锚定强度
          2. 检测需要剥离的内容（强度 < 阈值且超过最小保留步数）
          3. 返回剥离事件列表
        """
        events = []
        to_remove = []
        
        for payload_id, (anchor, strength, steps) in self._anchored.items():
            # 衰减
            new_strength = max(0.0, strength - self.decay_rate)
            steps += 1
            
            # 检查是否需要剥离
            if (new_strength < self.anchor_threshold 
                    and steps >= self.min_retention_steps):
                payload = HighSemanticPayload(
                    payload_id=payload_id,
                    content_type="",  # 需要从历史恢复
                    content_vector=torch.tensor([]),
                    anchor_strength=new_strength,
                )
                event = ReturnFlowEvent(
                    payload=payload,
                    anchor=anchor,
                    timestamp=timestamp,
                    success=False,
                    reason=f"锚定强度衰减至 {new_strength:.3f} < {self.anchor_threshold}",
                    residual_strength=new_strength,
                )
                events.append(event)
                to_remove.append(payload_id)
            else:
                self._anchored[payload_id] = (anchor, new_strength, steps)
        
        for pid in to_remove:
            del self._anchored[pid]
        
        self._flow_events.extend(events)
        return events
    
    def get_anchored_contents(self) -> Dict[str, Dict]:
        """获取所有已锚定内容的状态"""
        result = {}
        for pid, (anchor, strength, steps) in self._anchored.items():
            result[pid] = {
                'structure_id': anchor.structure_id,
                'mechanism': anchor.mechanism,
                'anchor_strength': strength,
                'steps_anchored': steps,
            }
        return result
    
    def get_flow_history(self, limit: int = 100) -> List[ReturnFlowEvent]:
        return self._flow_events[-limit:]
```

### 3.3 回流通道的工作流程

```
┌─────────────────────────────────────────────────────────┐
│                    回流通道工作流程                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  高语义层                                                │
│  ┌──────────┐    尝试锚定    ┌──────────────────────┐   │
│  │ 意义/制度 │ ────────────→ │ ReturnFlowChannel    │   │
│  │ /叙事/身份│               │                      │   │
│  └──────────┘               │  1. 选择最佳锚点      │   │
│                             │  2. 验证耦合强度      │   │
│                             │  3. 成功则锚定        │   │
│                             └──────────┬───────────┘   │
│                                        │               │
│                                        ▼               │
│                             ┌──────────────────────┐   │
│                             │  每步演化 (step)     │   │
│                             │  - 锚定强度衰减      │   │
│                             │  - 低于阈值→剥离     │   │
│                             └──────────┬───────────┘   │
│                                        │               │
│  低语义层                              ▼               │
│  ┌──────────────────────────────────────────────┐     │
│  │  structure_1: {boundary: 0.8, self_sustaining: 0.6}│
│  │  structure_2: {memory: 0.7, replication: 0.5}      │
│  │  ...                                               │
│  └──────────────────────────────────────────────┘     │
│                                                          │
│  关键约束：                                               │
│  - 锚定强度衰减率: 0.01/步（可配置）                    │
│  - 最小保留步数: 10（防止瞬时波动导致剥离）              │
│  - 剥离是自动的，不需要外部干预                          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 四、两组件的集成关系

```
┌──────────────────────────────────────────────────────────┐
│                    Phase 2 集成架构                        │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  XiangjieChain (八章检测)                                 │
│       │                                                   │
│       ▼ 检测到前主体态                                    │
│  PreSubjectivityConvergence (收束判定)                    │
│       │                                                   │
│       ▼ 判定收束成功                                      │
│  UnsealingMechanism (解封机制)                            │
│       │                                                   │
│       ├── Level 1: 边界开放 ──┐                           │
│       ├── Level 2: 内部耦合 ──┼──→ ReturnFlowChannel     │
│       └── Level 3: 全通道开放 ─┘    (回流通道)             │
│                                      │                    │
│                                      ▼                    │
│                              高语义内容锚定               │
│                              持续监测 + 自动剥离           │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

**数据流**：
1. `XiangjieChain.evaluate()` → 检测到结构达到前主体态
2. `PreSubjectivityConvergence.evaluate()` → 判定六机制耦合收束
3. `UnsealingMechanism.evaluate()` → 根据收束结果确定解封等级
4. 当解封等级 ≥ 1 时，`ReturnFlowChannel` 开始接受高语义载荷
5. `ReturnFlowChannel.step()` 每步执行一次，监测锚定强度衰减

---

## 五、待实现清单

| # | 任务 | 文件 | 优先级 |
|---|------|------|--------|
| 1 | 实现 `UnsealingMechanism` 类 | `engine/unsealing_mechanism.py` | P0 |
| 2 | 实现 `ReturnFlowChannel` 类 | `engine/return_flow_channel.py` | P0 |
| 3 | 在 `hierarchical_evolver.py` 中集成解封判定 | `engine/hierarchical_evolver.py` | P0 |
| 4 | 在 `reactor.py` 中集成回流通道 step | `engine/reactor.py` | P1 |
| 5 | 编写解封机制单元测试 | `tests/test_unsealing.py` | P1 |
| 6 | 编写回流通道单元测试 | `tests/test_return_flow.py` | P1 |
| 7 | 编写端到端集成测试（从检测到解封到锚定） | `tests/test_phase2_integration.py` | P1 |
| 8 | 更新 `PROJECT_MAP.md` 反映 Phase 2 架构 | `PROJECT_MAP.md` | P2 |

---

## 六、理论注意事项

### 6.1 解封不是"打开"

解封不是外部操作，而是**结构自发达到密度后的自然结果**。`UnsealingMechanism` 的角色是**检测**而非**执行**解封。真正的解封是结构自身的状态变化。

### 6.2 回流不是"控制"

回流通道不是高语义对低语义的控制通道。它是**锚定机制**——高语义内容必须找到低语义结构作为其存在的物质基础。当锚定失效时，高语义内容自动剥离，这保证了低语义层的自主性。

### 6.3 语义防火墙的持续作用

即使在 Level 3 全通道开放后，语义防火墙仍然有效：
- 低语义层的内部描述不得使用高语义词汇
- 高语义内容以**向量形式**传递，而非文本/概念形式
- 剥离机制确保高语义内容不会永久污染低语义结构

---

*设计文档 — 2026-05-26*  
*下一步：开始实现 `UnsealingMechanism` 和 `ReturnFlowChannel`*
