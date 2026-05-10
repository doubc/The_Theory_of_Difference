# Real_World 实验报告：Full-Topology-World

**实验ID**: exp_005_full_topology
**运行步数**: 30
**总破缺事件**: 5

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_shortage | inventory | region_A | exchange_delivery | 102.6 | 59.3 | active |
| delivery_pressure | delivery | near_month | exchange | 87.4 | 0.0 | resolved |
| expectation_bullish | expectation | market | price | 41.6 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 35.0 | 经通道 warehouse_receipt_channel 转移 35.0 压力 |
| 1 | delivery_pressure | delivery_channel | 39.9 | 经通道 delivery_channel 转移 39.9 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.4 | 经通道 position_reduction_channel 转移 0.4 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.8 | 经通道 position_reduction_channel 转移 0.8 压力 |
| 4 | inventory_shortage | warehouse_receipt_channel | 32.5 | 经通道 warehouse_receipt_channel 转移 32.5 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 10.5 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |
| 1 | delivery_pressure | delivery_channel | 12.0 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.4 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.8 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 4 | inventory_shortage | warehouse_receipt_channel | 9.8 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_short_001_1 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 7.5，杠杆 2.0x，产生保证金差异 4.5 |
| feedback_margin_speculative_long_001_1 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 30.0，杠杆 2.0x，产生保证金差异 18.0 |
| feedback_margin_speculator_002_1 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 22.1，杠杆 1.5x，产生保证金差异 10.0 |
| feedback_margin_speculative_long_001_3 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 4.7，杠杆 2.0x，产生保证金差异 2.8 |
| feedback_margin_industrial_short_001_4 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 3.8，杠杆 2.0x，产生保证金差异 2.2 |
| feedback_margin_speculative_long_001_9 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 4.7，杠杆 2.0x，产生保证金差异 2.8 |

## 五、干预记录

| 时间 | 类型 | 量 | 说明 |
|---|---|---|---|
| 2 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 2 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 2 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(23.2), speculator_002(17.1) |
| 2 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 8 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 8 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 8 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(18.6), speculator_002(14.9) |
| 8 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 11 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 11 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 11 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(15.0), speculator_002(10.5) |
| 11 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| warehouse_receipt_channel | inventory→delivery | 15.0 | 1351% | 0.14 | 0.135 | open |
| delivery_channel | delivery→basis | 20.0 | 798% | 0.08 | 0.080 | open |
| basis_channel | basis→price | 12.0 | 0% | 0.00 | 0.000 | open |
| futures_contract_channel | expectation→price | 10.0 | 0% | 0.00 | 0.000 | open |
| margin_clearing_channel | price→margin | 8.0 | 0% | 0.00 | 0.000 | open |
| position_reduction_channel | margin→liquidity | 12.0 | 24% | 0.00 | 0.002 | open |
| exchange_rule_channel | delivery→rule | 50.0 | 0% | 0.00 | 0.000 | open |

## 七、破缺事件

| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |
|---|---|---|---|---|
| 3 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 103.9 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 9 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 97.4 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 13 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 90.8 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 19 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 94.4 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 27 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 92.9 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |

## 八、最近稳态

**最终稳态判定**: unstable

**判定理由**: 近3步有15次破缺，系统不稳定

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 71.8 | 3 | 7 | high | margin_relief |
| 2 | 98.7 | 5 | 7 | critical | margin_relief |
| 3 | 58.3 | 4 | 7 | medium | margin_relief |
| 4 | 37.4 | 4 | 7 | medium | margin_relief |
| 5 | 52.1 | 4 | 7 | medium | unstable |
| 6 | 66.0 | 4 | 7 | high | unstable |
| 7 | 79.2 | 4 | 7 | high | unstable |
| 8 | 101.6 | 6 | 7 | critical | unstable |
| 9 | 60.1 | 5 | 7 | high | unstable |
| 10 | 71.5 | 5 | 7 | high | unstable |
| 11 | 92.1 | 7 | 7 | critical | unstable |
| 12 | 97.6 | 6 | 7 | critical | unstable |
| 13 | 61.9 | 6 | 7 | high | unstable |
| 14 | 71.1 | 6 | 7 | high | unstable |
| 15 | 79.9 | 6 | 7 | high | unstable |
| 16 | 88.3 | 6 | 7 | high | unstable |
| 17 | 96.2 | 6 | 7 | critical | unstable |
| 18 | 103.7 | 6 | 7 | critical | unstable |
| 19 | 63.7 | 6 | 7 | high | unstable |
| 20 | 70.5 | 6 | 7 | high | unstable |
| 21 | 76.9 | 6 | 7 | high | unstable |
| 22 | 83.0 | 6 | 7 | high | unstable |
| 23 | 88.9 | 6 | 7 | high | unstable |
| 24 | 94.4 | 6 | 7 | critical | unstable |
| 25 | 99.7 | 6 | 7 | critical | unstable |
| 26 | 104.6 | 6 | 7 | critical | unstable |
| 27 | 62.9 | 6 | 7 | high | unstable |
| 28 | 67.4 | 6 | 7 | high | unstable |
| 29 | 71.7 | 6 | 7 | high | unstable |
| 30 | 75.8 | 6 | 7 | high | unstable |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 59.3
- **承压主体**: industrial_short_001(stressed)
- **最近稳态**: unstable
- **变形链事件**: 5 次变形
- **反馈差异**: 6 个（已解决 6）
