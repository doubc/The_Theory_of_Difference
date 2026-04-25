# 结构 DSL 规则规范

## 一、概述

结构 DSL（Domain Specific Language）是一种基于 YAML 的规则定义语言，用于将主观结构描述翻译为可执行的匹配规则。规则引擎读取 YAML 规则文件，逐条扫描编译后的结构（Structure），输出匹配结果与典型度评分。

规则文件统一存放在 `src/dsl/rules/` 目录下。引擎核心实现见 `src/dsl/rule.py`。

## 二、规则定义格式

```yaml
rules:
  - name: RuleName
    description: 规则描述
    zone_source: high_cluster | low_cluster
    cycles: {gte: 3}
    speed_ratio: {gt: 1.5}
    time_ratio: {gt: 1.5}
    high_cluster_cv: {lt: 0.02}
    high_cluster_stddev: {lt: 0.01}
    zone_rel_bw: {lt: 0.05}
    zone_strength: {gte: 0.7}
```

每条规则包含一个名称、一段描述，以及一组约束条件。约束条件之间是"与"关系——所有约束同时通过才算命中。

## 三、约束原语

约束值支持以下语法：

| 语法 | 含义 | 示例 |
|------|------|------|
| 单值 | 精确匹配（容差 1e-9） | `cycles: 3` |
| `[lo, hi]` | 区间包含（lo ≤ value ≤ hi） | `cycles: [2, 5]` |
| `{gt: x}` | 严格大于 | `{gt: 1.5}` |
| `{gte: x}` | 大于等于 | `{gte: 3}` |
| `{lt: x}` | 严格小于 | `{lt: 0.02}` |
| `{lte: x}` | 小于等于 | `{lte: 1.0}` |
| `{between: [lo, hi]}` | 区间包含（等价于 `[lo, hi]`） | `{between: [0.7, 1.4]}` |

## 四、可用约束字段

以下字段可在规则中使用，引擎从编译后的结构对象中提取对应值进行比较：

| 字段 | 数据来源 | 说明 |
|------|----------|------|
| `zone_source` | `Zone.source.value` | Zone 来源类型，取值 `high_cluster`（高点聚簇）或 `low_cluster`（低点聚簇） |
| `cycles` | `invariants.cycle_count` / `Structure.cycle_count` | 结构包含的周期（Cycle）数量 |
| `speed_ratio` | `invariants.avg_speed_ratio` / `Structure.avg_speed_ratio` | 平均速度比（上升段速度 / 下降段速度） |
| `time_ratio` | `invariants.avg_time_ratio` / `Structure.avg_time_ratio` | 平均时间比（上升段时间 / 下降段时间） |
| `high_cluster_cv` | `Structure.high_cluster_cv` | 高点聚簇的变异系数（Coefficient of Variation），值越小表示高点越集中 |
| `high_cluster_stddev` | `invariants.high_cluster_stddev` / `Structure.high_cluster_stddev` | 高点聚簇的标准差 |
| `zone_rel_bw` | `Zone.relative_bandwidth` | Zone 的相对带宽（bandwidth / price_center） |
| `zone_strength` | `Zone.strength` | Zone 强度，反映该价格区域的支撑/压力有效性 |

> **术语说明**：speed_ratio（速度比）和 time_ratio（时间比）用于刻画结构的对称性——值越偏离 1.0，结构越不对称。

## 五、匹配逻辑

1. 加载规则列表（`load_rules()`）
2. 对每个结构，逐条规则检查所有约束条件
3. 所有约束通过 → 命中该规则
4. 典型度（typicality）= 通过的约束数 / 总约束数，反映结构与规则原型的接近程度
5. 每个结构取典型度最高的命中规则，将规则名回写至 `Structure.label`

```python
# 核心匹配流程（伪代码）
for structure in structures:
    best_match = None
    for rule in rules:
        passed, checks = rule.match(structure)
        if passed:
            typicality = rule.typicality_score(checks)
            if best_match is None or typicality > best_match.typicality:
                best_match = (rule, checks, typicality)
    if best_match:
        structure.label = best_match.rule.name
        structure.typicality = best_match.typicality
```

## 六、内置规则集

当前默认规则集 `src/dsl/rules/default.yaml` 定义了六种结构类型：

| 规则名 | 类型 | zone_source | 关键约束 | 说明 |
|--------|------|-------------|---------|------|
| `SlowUpFastDown_TopReversal` | 顶部反转 | `high_cluster` | cycles≥2, speed>1.2, time>1.2 | 慢涨急跌，高点聚集后快速回落 |
| `FastUpSlowDown_TopDistribution` | 顶部派发 | `high_cluster` | cycles≥2, speed<0.8, time<0.8 | 急涨慢跌，快速冲高后缓慢回落 |
| `TripleTest_BottomBreakout` | 底部突破 | `low_cluster` | cycles≥2, speed>1.0, time>1.0 | 低点反复确认支撑后突破 |
| `SlowDownFastUp_BottomReversal` | 底部反转 | `low_cluster` | cycles≥2, speed>1.2, time>1.2 | 慢跌急涨，触及支撑后快速反弹 |
| `BalancedConsolidation` | 整理 | — | cycles≥2, speed∈[0.7,1.4], time∈[0.7,1.4] | 上下速度和时间大致对称 |
| `HighVolatilityZone` | 高波动 | — | cycles≥2, speed>2.0 | 速度比极端，进出不对称 |

## 七、扩展约束字段

如需在规则中使用额外的结构属性（如运动态、投影觉知等），需在 `src/dsl/rule.py` 的 `Rule` 类中添加对应字段，并在 `attr_map` 中建立属性映射关系。

当前引擎仅支持静态不变量约束，不支持动态条件（如"速度比正在加速上升"）或时序条件（如"连续两个周期速度比递增"）。

---

*相关文件：`src/dsl/rule.py` · `src/dsl/rules/default.yaml` · `src/models.py`*
