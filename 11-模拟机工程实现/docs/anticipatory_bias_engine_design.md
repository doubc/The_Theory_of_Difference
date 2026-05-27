# AnticipatoryBiasEngine 设计文档

> **版本**: v0.1 (设计草稿)
> **日期**: 2026-05-27
> **状态**: 设计阶段 — 待实现
> **前置**: MinimalSelfDetector (Phase 3 P0) 完成
> **理论依据**: 《差异论》高语义层 + 《象界》第四章 + ABA §4.4

---

## 一、核心问题

Phase 2 的 `PersistentBiasMemory` 实现了**回溯性偏置**：过去以偏置形式影响当下。

Phase 3 需要**前摄性偏置**：当下基于历史模式对未来产生预期偏置。

关键区分：
- **记忆**：路径对路径的限制（过去 → 当下）
- **预期**：基于路径外推的差异分布预偏置（当下 → 未来）

预期不是"猜测"，而是历史路径依赖的统计外推。它不能引入"意图"或"目的"——只是结构对自身路径依赖的延伸。

---

## 二、组件架构

```
AnticipatoryBiasEngine（预期偏置引擎）
├── PatternExtrapolator：从历史偏置序列外推未来差异分布
│   ├── 线性外推（一阶）
│   ├── 加速度外推（二阶）
│   └── 置信度加权外推（不确定性感知）
├── ExpectationField：预期差异场（与 BiasField 对偶）
│   ├── expected_vector：预期差异方向
│   ├── confidence：预期置信度 [0,1]
│   └── horizon：预期视野（多少步后的预期）
├── PredictionErrorTracker：预测误差追踪
│   ├── error_history：历史预测误差序列
│   ├── error_trend：误差趋势（下降=学习，上升=失配）
│   └── error_decay：误差衰减率
└── AnticipationConfidence：预期置信度综合评估
    ├── 基于历史预测准确率
    ├── 基于历史偏置稳定性
    └── 基于 ODI 值（高 ODI → 更稳定的预期）
```

---

## 三、数据类设计

### 3.1 ExpectationField（预期场）

```python
@dataclass
class ExpectationField:
    """预期差异场 — 对未来差异分布的结构性预偏置"""
    source_layer: int                   # 来源层
    target_layer: int                   # 目标层
    expected_vector: torch.Tensor       # 预期差异方向
    confidence: float                   # 预期置信度 [0,1]
    horizon: int                        # 预期视野（步数）
    timestamp: int                      # 生成时间戳
    method: str                         # 外推方法标识
    metadata: Dict                      # 附加信息
```

### 3.2 PredictionError（预测误差）

```python
@dataclass
class PredictionError:
    """单次预测误差记录"""
    timestamp: int
    predicted: torch.Tensor             # 预测值
    actual: torch.Tensor                # 实际值
    error_magnitude: float              # 误差范数
    relative_error: float               # 相对误差
    horizon: int                        # 预测视野
```

### 3.3 AnticipationResult（预期结果）

```python
@dataclass
class AnticipationResult:
    """预期偏置引擎的输出"""
    expectation: ExpectationField       # 预期场
    confidence: float                   # 综合置信度
    error_trend: float                  # 误差趋势（负=改善，正=恶化）
    n_predictions: int                  # 历史预测次数
    mean_error: float                   # 平均预测误差
    is_reliable: bool                   # 预期是否可靠（置信度 > 阈值）
    odi_gated: bool                     # 是否被 ODI 门控
    timestamp: int
```

---

## 四、PatternExtrapolator 算法

### 4.1 输入

历史偏置序列 `H = [(t_1, v_1), (t_2, v_2), ..., (t_n, v_n)]`，其中 `v_i` 是偏置向量。

### 4.2 外推方法

**方法一：线性外推（默认）**
```
v_predicted = v_n + (v_n - v_{n-1}) * horizon
```
适用于偏置方向稳定的情况。

**方法二：加速度外推**
```
a = (v_n - v_{n-1}) - (v_{n-1} - v_{n-2})  # 二阶差分
v_predicted = v_n + (v_n - v_{n-1}) * horizon + 0.5 * a * horizon^2
```
适用于偏置方向加速变化的情况。

**方法三：置信度加权外推**
```
w_i = confidence_i * exp(-decay * (n - i))  # 近期偏置权重更高
v_predicted = weighted_mean(H, w) + trend * horizon
```
适用于偏置方向不稳定的情况。

### 4.3 方法选择策略

- 历史偏置方向方差 < 低阈值 → 线性外推（方向稳定）
- 历史偏置方向方差 > 高阈值 → 置信度加权外推（方向不稳定）
- 否则 → 加速度外推

### 4.4 置信度计算

```
confidence = base_confidence * stability_factor * odi_factor

其中：
- base_confidence = 1.0 - normalized_error（基于最近预测误差）
- stability_factor = 1.0 - direction_variance（偏置方向稳定性）
- odi_factor = min(1.0, odi / odi_threshold)（ODI 门控）
```

---

## 五、与 PersistentBiasMemory 的集成

### 5.1 扩展点

`AnticipatoryBiasEngine` 不替换 `PersistentBiasMemory`，而是在其之上增加前摄层：

```
PersistentBiasMemory（已有）
├── 记录历史偏置
├── 累积回溯性偏置
└── 提供 get_historical() 接口
         ↓
AnticipatoryBiasEngine（新增）
├── 从 PersistentBiasMemory 读取历史
├── 外推未来偏置
├── 生成 ExpectationField
└── 追踪预测误差
```

### 5.2 接口设计

```python
class AnticipatoryBiasEngine:
    def __init__(self, memory: PersistentBiasMemory, ...):
        """绑定到已有的 PersistentBiasMemory"""
        
    def predict(self, target_layer: int, horizon: int = 1,
                timestamp: int = 0, odi_result = None) -> AnticipationResult:
        """基于历史偏置外推未来差异分布"""
        
    def update(self, actual: torch.Tensor, timestamp: int):
        """用实际差异更新预测误差追踪"""
        
    def get_expectation_field(self, target_layer: int) -> Optional[ExpectationField]:
        """获取当前预期场"""
        
    def get_prediction_accuracy(self) -> float:
        """获取历史预测准确率"""
```

---

## 六、ODI 门控

与 `MinimalSelfDetector` 一致，`AnticipatoryBiasEngine` 也受 ODI 门控：

- ODI < 0.3：预期被完全抑制（结构尚未准备好）
- 0.3 ≤ ODI < 0.5：预期被部分抑制（confidence *= odi_factor）
- ODI ≥ 0.5：预期正常运行

这确保预期机制只在前主体态地板之上才被激活。

---

## 七、语义防火墙

| 禁止引入 | 原因 | 允许替代 |
|---------|------|---------|
| "预测未来" | 预设目的论 | "基于历史路径依赖的统计外推" |
| "期望" | 预设心理状态 | "结构对差异分布的前摄性偏置" |
| "意图" | 预设目的论 | "路径依赖的延伸" |
| "目标" | 预设目的论 | "差异分布的趋势方向" |
| "计划" | 预设认知能力 | "多步外推的差异预偏置" |

---

## 八、实现计划

### 第一步：核心数据类 + PatternExtrapolator
- `ExpectationField`, `PredictionError`, `AnticipationResult` 数据类
- `PatternExtrapolator` 三种外推方法
- 单元测试：~20 个测试

### 第二步：AnticipatoryBiasEngine 主体
- 绑定 `PersistentBiasMemory`
- `predict()` / `update()` / `get_expectation_field()` 方法
- ODI 门控
- 单元测试：~15 个测试

### 第三步：集成到 HierarchicalEvolver
- Phase 3 callback 集成
- 与 `MinimalSelfDetector` 协同
- 集成测试：~10 个测试

### 第四步：端到端实验
- 预期涌现检测实验（Phase 3 实验一）
- 数据收集 + 路线 A vs 路线 B 判定

---

## 九、与 MinimalSelfDetector 的协同

`MinimalSelfDetector` 追踪结构的内在不对称性（MSI）。
`AnticipatoryBiasEngine` 追踪结构的前摄性偏置能力。

两者的协同：
- MSI 高 → 结构有稳定的"视角" → 预期更可靠
- 预期准确率高 → 结构能预测自身演化 → 自我参照回路更强 → MSI 可能增长

这形成了一个正反馈回路：自我追踪能力增强预期能力，预期能力增强自我追踪。

---

## 十、测试策略

### 单元测试（~35 个）
1. PatternExtrapolator 线性外推正确性
2. PatternExtrapolator 加速度外推正确性
3. PatternExtrapolator 置信度加权外推
4. 方法选择策略
5. 置信度计算
6. ODI 门控（低 ODI 抑制、高 ODI 正常）
7. PredictionErrorTracker 误差追踪
8. 预测准确率计算
9. 历史偏置序列不足时的降级行为
10. 空历史时的安全返回

### 集成测试（~10 个）
1. 与 PersistentBiasMemory 绑定
2. 预测 → 更新 → 再预测的闭环
3. 多目标层独立预测
4. 与 MinimalSelfDetector 协同
5. 与 HierarchicalEvolver Phase 3 callback 集成
6. 端到端：从底象到预期涌现
