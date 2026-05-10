# Real_World 实验报告：Full-Topology-World

**实验ID**: exp_005_50
**运行步数**: 50
**总破缺事件**: 6

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_shortage | inventory | region_A | exchange_delivery | 102.6 | 63.7 | active |
| delivery_pressure | delivery | near_month | exchange | 87.4 | 0.0 | resolved |
| expectation_bullish | expectation | market | price | 41.6 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 35.0 | 经通道 warehouse_receipt_channel 转移 35.0 压力 |
| 1 | delivery_pressure | delivery_channel | 39.9 | 经通道 delivery_channel 转移 39.9 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.4 | 经通道 position_reduction_channel 转移 0.4 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.8 | 经通道 position_reduction_channel 转移 0.8 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 1.2 | 经通道 position_reduction_channel 转移 1.2 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 1.9 | 经通道 position_reduction_channel 转移 1.9 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 1.6 | 经通道 position_reduction_channel 转移 1.6 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.8 | 经通道 position_reduction_channel 转移 0.8 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 1.5 | 经通道 position_reduction_channel 转移 1.5 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.7 | 经通道 position_reduction_channel 转移 0.7 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.4 | 经通道 position_reduction_channel 转移 0.4 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.2 | 经通道 position_reduction_channel 转移 0.2 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 经通道 position_reduction_channel 转移 0.1 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 4 | inventory_shortage | warehouse_receipt_channel | 32.5 | 经通道 warehouse_receipt_channel 转移 32.5 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 10.5 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |
| 1 | delivery_pressure | delivery_channel | 12.0 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.4 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.8 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 1.2 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 1.7 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 1.4 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.7 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 1.3 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.3 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 4 | inventory_shortage | warehouse_receipt_channel | 9.8 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_short_001_1 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 7.5，杠杆 2.0x，产生保证金差异 4.5 |
| feedback_margin_speculative_long_001_1 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.0，杠杆 2.0x，产生保证金差异 0.0 |
| feedback_margin_speculator_002_1 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.0，杠杆 1.5x，产生保证金差异 0.0 |
| feedback_margin_speculative_long_001_3 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.2，杠杆 2.0x，产生保证金差异 0.1 |
| feedback_margin_speculator_002_3 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.1，杠杆 1.5x，产生保证金差异 0.0 |
| feedback_margin_industrial_short_001_4 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 3.8，杠杆 2.0x，产生保证金差异 2.2 |
| feedback_margin_speculative_long_001_4 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 8.6，杠杆 2.0x，产生保证金差异 5.2 |
| feedback_margin_speculator_002_4 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.0，杠杆 1.5x，产生保证金差异 0.0 |
| feedback_margin_speculative_long_001_8 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 1.8，杠杆 2.0x，产生保证金差异 1.1 |
| feedback_margin_speculator_002_8 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.1，杠杆 1.5x，产生保证金差异 0.0 |

## 五、干预记录

| 时间 | 类型 | 量 | 说明 |
|---|---|---|---|
| 2 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 2 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 2 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(24.0), speculator_002(18.0) |
| 2 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 7 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 7 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 7 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(21.4), speculator_002(15.2) |
| 7 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 8 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 8 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 8 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(16.9), speculator_002(10.9) |
| 8 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| warehouse_receipt_channel | inventory→delivery | 15.0 | 1351% | 0.14 | 0.135 | open |
| delivery_channel | delivery→basis | 20.0 | 798% | 0.08 | 0.080 | open |
| basis_channel | basis→price | 12.0 | 0% | 0.00 | 0.000 | open |
| futures_contract_channel | expectation→price | 10.0 | 0% | 0.00 | 0.000 | open |
| margin_clearing_channel | price→margin | 8.0 | 0% | 0.00 | 0.000 | open |
| position_reduction_channel | margin→liquidity | 12.0 | 192% | 0.02 | 0.019 | open |
| exchange_rule_channel | delivery→rule | 50.0 | 0% | 0.00 | 0.000 | open |

## 七、破缺事件

| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |
|---|---|---|---|---|
| 3 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 103.9 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 9 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 97.4 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 13 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 90.8 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 19 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 94.4 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 27 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 92.9 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 40 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 90.3 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |

## 八、最近稳态

**最终稳态判定**: unstable

**判定理由**: 近3步有18次破缺，系统不稳定

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 73.1 | 6 | 7 | high | margin_relief |
| 2 | 100.0 | 8 | 7 | critical | margin_relief |
| 3 | 59.6 | 8 | 7 | medium | margin_relief |
| 4 | 38.7 | 8 | 7 | medium | margin_relief |
| 5 | 53.3 | 7 | 7 | medium | unstable |
| 6 | 67.3 | 7 | 7 | high | unstable |
| 7 | 90.3 | 9 | 7 | critical | unstable |
| 8 | 108.0 | 11 | 7 | critical | unstable |
| 9 | 66.5 | 9 | 7 | high | unstable |
| 10 | 77.8 | 9 | 7 | high | unstable |
| 11 | 88.6 | 9 | 7 | high | unstable |
| 12 | 98.8 | 9 | 7 | critical | unstable |
| 13 | 63.2 | 9 | 7 | high | unstable |
| 14 | 72.4 | 9 | 7 | high | unstable |
| 15 | 81.2 | 9 | 7 | high | unstable |
| 16 | 89.5 | 9 | 7 | high | unstable |
| 17 | 97.4 | 9 | 7 | critical | unstable |
| 18 | 105.0 | 9 | 7 | critical | unstable |
| 19 | 64.9 | 9 | 7 | high | unstable |
| 20 | 71.7 | 9 | 7 | high | unstable |
| 21 | 78.2 | 9 | 7 | high | unstable |
| 22 | 84.3 | 9 | 7 | high | unstable |
| 23 | 90.1 | 9 | 7 | critical | unstable |
| 24 | 95.7 | 9 | 7 | critical | unstable |
| 25 | 100.9 | 9 | 7 | critical | unstable |
| 26 | 105.9 | 9 | 7 | critical | unstable |
| 27 | 64.2 | 9 | 7 | high | unstable |
| 28 | 68.7 | 9 | 7 | high | unstable |
| 29 | 73.0 | 9 | 7 | high | unstable |
| 30 | 77.1 | 9 | 7 | high | unstable |
| 31 | 80.9 | 9 | 7 | high | unstable |
| 32 | 84.6 | 9 | 7 | high | unstable |
| 33 | 88.1 | 9 | 7 | high | unstable |
| 34 | 91.4 | 9 | 7 | critical | unstable |
| 35 | 94.5 | 9 | 7 | critical | unstable |
| 36 | 97.5 | 9 | 7 | critical | unstable |
| 37 | 100.4 | 9 | 7 | critical | unstable |
| 38 | 103.1 | 9 | 7 | critical | unstable |
| 39 | 105.6 | 9 | 7 | critical | unstable |
| 40 | 62.9 | 9 | 7 | high | unstable |
| 41 | 65.2 | 9 | 7 | high | unstable |
| 42 | 67.4 | 9 | 7 | high | unstable |
| 43 | 69.5 | 9 | 7 | high | unstable |
| 44 | 71.5 | 9 | 7 | high | unstable |
| 45 | 73.4 | 9 | 7 | high | unstable |
| 46 | 75.2 | 9 | 7 | high | unstable |
| 47 | 76.9 | 9 | 7 | high | unstable |
| 48 | 78.5 | 9 | 7 | high | unstable |
| 49 | 80.0 | 9 | 7 | high | unstable |
| 50 | 81.5 | 9 | 7 | high | unstable |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 63.7
- **承压主体**: industrial_short_001(stressed)
- **最近稳态**: unstable
- **变形链事件**: 17 次变形
- **反馈差异**: 10 个（已解决 10）
