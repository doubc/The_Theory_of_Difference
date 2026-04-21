# 结构 DSL 规则规范

## 规则定义格式

规则以 YAML 格式定义，存放在 `src/dsl/rules/` 目录下。

```yaml
rules:
  - name: RuleName
    description: 规则描述
    zone_source: high_cluster | low_cluster
    cycles: {gte: 3}
    speed_ratio: {gt: 1.5}
    time_ratio: {gt: 1.5}
    high_cluster_cv: {lt: 0.02}
```

## 约束原语

| 语法 | 含义 | 示例 |
|------|------|------|
| 单值 | 精确匹配 | `cycles: 3` |
| `[lo, hi]` | 区间包含 | `cycles: [2, 5]` |
| `{gt: x}` | 大于 | `{gt: 1.5}` |
| `{gte: x}` | 大于等于 | `{gte: 3}` |
| `{lt: x}` | 小于 | `{lt: 0.02}` |
| `{lte: x}` | 小于等于 | `{lte: 1.0}` |
| `{between: [lo, hi]}` | 区间 | `{between: [0.7, 1.4]}` |

## 可用约束字段

| 字段 | 数据来源 | 说明 |
|------|----------|------|
| zone_source | Zone.source.value | high_cluster / low_cluster |
| cycles | invariants.cycle_count | Cycle 数量 |
| speed_ratio | invariants.avg_speed_ratio | 平均速度比 |
| time_ratio | invariants.avg_time_ratio | 平均时间比 |
| high_cluster_cv | Structure.high_cluster_cv | 高点变异系数 |
| high_cluster_stddev | invariants.high_cluster_stddev | 高点标准差 |
| zone_rel_bw | Zone.relative_bandwidth | Zone 相对带宽 |
| zone_strength | Zone.strength | Zone 强度 |

## 匹配逻辑

1. 逐条规则检查所有约束
2. 所有约束通过 → 命中
3. 每个结构只匹配第一条命中的规则
4. 典型度 = 通过约束数 / 总约束数

## 内置规则集 (default.yaml)

| 规则名 | 类型 | 说明 |
|--------|------|------|
| SlowUpFastDown_TopReversal | 顶部反转 | 慢涨急跌，高点聚集 |
| FastUpSlowDown_TopDistribution | 顶部派发 | 急涨慢跌，高点聚集 |
| TripleTest_BottomBreakout | 底部突破 | 多次试探，低点确认 |
| SlowDownFastUp_BottomReversal | 底部反转 | 慢跌急涨 |
| BalancedConsolidation | 整理 | 速度/时间大致对称 |
| HighVolatilityZone | 高波动 | 速度比极端 |
