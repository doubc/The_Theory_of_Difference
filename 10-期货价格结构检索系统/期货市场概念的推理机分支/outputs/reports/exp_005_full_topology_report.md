# Real_World 实验报告：Full-Topology-World

**实验ID**: exp_005_full_topology
**运行步数**: 30
**总破缺事件**: 16

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_shortage | inventory | region_A | exchange_delivery | 102.6 | 56.1 | active |
| delivery_pressure | delivery | near_month | exchange | 87.4 | 0.0 | resolved |
| expectation_bullish | expectation | market | price | 41.6 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 35.0 | 经通道 warehouse_receipt_channel 转移 35.0 压力 |
| 1 | delivery_pressure | delivery_channel | 45.0 | 经通道 delivery_channel 转移 45.0 压力 |
| 1 | expectation_bullish | futures_contract_channel | 3.1 | 经通道 futures_contract_channel 转移 3.1 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 15.3 | 经通道 position_reduction_channel 转移 15.3 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 9.1 | 经通道 position_reduction_channel 转移 9.1 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 6.1 | 经通道 position_reduction_channel 转移 6.1 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 5.5 | 经通道 position_reduction_channel 转移 5.5 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 1.2 | 经通道 position_reduction_channel 转移 1.2 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 2.1 | 经通道 position_reduction_channel 转移 2.1 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 1.0 | 经通道 position_reduction_channel 转移 1.0 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.5 | 经通道 position_reduction_channel 转移 0.5 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.2 | 经通道 position_reduction_channel 转移 0.2 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 经通道 position_reduction_channel 转移 0.1 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 经通道 position_reduction_channel 转移 0.1 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 2 | delivery_pressure | delivery_channel | 18.4 | 经通道 delivery_channel 转移 18.4 压力 |
| 7 | feedback_margin_speculative_long_001_7 | position_reduction_channel | 0.8 | 经通道 position_reduction_channel 转移 0.8 压力 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.6 | 经通道 position_reduction_channel 转移 0.6 压力 |
| 7 | feedback_margin_speculative_long_001_7 | position_reduction_channel | 0.1 | 经通道 position_reduction_channel 转移 0.1 压力 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.3 | 经通道 position_reduction_channel 转移 0.3 压力 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.2 | 经通道 position_reduction_channel 转移 0.2 压力 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.1 | 经通道 position_reduction_channel 转移 0.1 压力 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.1 | 经通道 position_reduction_channel 转移 0.1 压力 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 8 | feedback_margin_speculative_long_001_7 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 8 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 10.5 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |
| 1 | delivery_pressure | delivery_channel | 13.5 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 1 | expectation_bullish | futures_contract_channel | 3.1 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 10.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 4.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 2.4 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 1.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.4 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.3 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 2 | delivery_pressure | delivery_channel | 5.5 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 7 | feedback_margin_speculative_long_001_7 | position_reduction_channel | 0.7 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 7 | feedback_margin_speculative_long_001_7 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.3 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 4 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.2 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 4 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 4 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 4 |
| 7 | feedback_margin_speculator_002_7 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 4 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_short_001_1 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 7.5，杠杆 2.5x，产生保证金差异 5.6 |
| feedback_margin_speculative_long_001_1 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.0，杠杆 4.0x，产生保证金差异 0.0 |
| feedback_margin_speculator_002_1 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.0，杠杆 3.0x，产生保证金差异 0.0 |
| feedback_margin_exchange_001_2 | margin | exchange_001 | 0.0 | resolved | 反馈: exchange_001 承压 30.0，杠杆 1.0x，产生保证金差异 9.0 |
| feedback_margin_industrial_short_001_2 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 3.8，杠杆 2.5x，产生保证金差异 2.8 |
| feedback_margin_speculative_long_001_7 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.0，杠杆 4.0x，产生保证金差异 0.0 |
| feedback_margin_speculator_002_7 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.0，杠杆 3.0x，产生保证金差异 0.0 |
| feedback_margin_speculative_long_001_10 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 1.5，杠杆 4.0x，产生保证金差异 1.8 |
| feedback_margin_speculator_002_10 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 1.2，杠杆 3.0x，产生保证金差异 1.0 |
| feedback_margin_speculative_long_001_11 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.2，杠杆 4.0x，产生保证金差异 0.2 |
| feedback_margin_speculator_002_11 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.1，杠杆 3.0x，产生保证金差异 0.1 |
| feedback_margin_speculative_long_001_12 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.0，杠杆 4.0x，产生保证金差异 0.0 |
| feedback_margin_speculator_002_12 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.0，杠杆 3.0x，产生保证金差异 0.0 |
| feedback_margin_speculative_long_001_13 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 3.6，杠杆 4.0x，产生保证金差异 4.3 |

## 五、干预记录

| 时间 | 类型 | 量 | 说明 |
|---|---|---|---|
| 6 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 6 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 6 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(24.0), speculator_002(18.0) |
| 6 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 9 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 9 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 9 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(24.0), speculator_002(18.0) |
| 9 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 12 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 12 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 12 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(20.0), speculator_002(14.0) |
| 12 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 14 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 14 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 14 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(16.5), speculator_002(10.6) |
| 14 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| warehouse_receipt_channel | inventory→delivery | 15.0 | 700% | 0.07 | 0.070 | open |
| delivery_channel | delivery→basis | 20.0 | 1267% | 0.13 | 0.127 | open |
| basis_channel | basis→price | 12.0 | 0% | 0.00 | 0.000 | open |
| futures_contract_channel | expectation→price | 10.0 | 63% | 0.01 | 0.006 | open |
| margin_clearing_channel | price→margin | 8.0 | 0% | 0.00 | 0.000 | open |
| position_reduction_channel | margin→liquidity | 12.0 | 870% | 0.09 | 0.087 | open |
| exchange_rule_channel | delivery→rule | 50.0 | 0% | 0.00 | 0.000 | open |

## 七、破缺事件

| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |
|---|---|---|---|---|
| 1 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 94.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 2 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 87.2 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 3 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 81.5 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 4 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 76.8 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 5 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 72.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 7 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 99.7 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 8 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 79.2 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 10 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 93.9 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 11 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 72.1 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 13 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 82.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 15 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 83.4 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 17 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 79.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 19 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 74.1 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 22 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 82.2 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 25 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 79.9 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 28 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 73.2 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |

## 八、最近稳态

**最终稳态判定**: unstable

**判定理由**: 近3步有48次破缺，系统不稳定

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 78.4 | 8 | 7 | high | unstable |
| 2 | 72.7 | 10 | 7 | high | unstable |
| 3 | 69.9 | 10 | 7 | high | unstable |
| 4 | 67.5 | 10 | 7 | high | unstable |
| 5 | 65.4 | 10 | 7 | high | unstable |
| 6 | 107.8 | 12 | 7 | critical | unstable |
| 7 | 71.9 | 12 | 7 | high | unstable |
| 8 | 61.6 | 10 | 7 | high | unstable |
| 9 | 99.3 | 12 | 7 | critical | unstable |
| 10 | 74.7 | 12 | 7 | high | unstable |
| 11 | 63.2 | 12 | 7 | high | unstable |
| 12 | 96.9 | 14 | 7 | critical | unstable |
| 13 | 73.5 | 12 | 7 | high | unstable |
| 14 | 104.9 | 14 | 7 | critical | unstable |
| 15 | 79.0 | 13 | 7 | high | unstable |
| 16 | 98.5 | 13 | 7 | critical | unstable |
| 17 | 77.1 | 13 | 7 | high | unstable |
| 18 | 94.7 | 13 | 7 | critical | unstable |
| 19 | 74.3 | 13 | 7 | high | unstable |
| 20 | 90.2 | 13 | 7 | critical | unstable |
| 21 | 105.3 | 13 | 7 | critical | unstable |
| 22 | 78.4 | 13 | 7 | high | unstable |
| 23 | 92.0 | 13 | 7 | critical | unstable |
| 24 | 104.9 | 13 | 7 | critical | unstable |
| 25 | 77.3 | 13 | 7 | high | unstable |
| 26 | 88.9 | 13 | 7 | high | unstable |
| 27 | 100.0 | 13 | 7 | critical | unstable |
| 28 | 73.9 | 13 | 7 | high | unstable |
| 29 | 83.9 | 13 | 7 | high | unstable |
| 30 | 93.4 | 13 | 7 | critical | unstable |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 56.1
- **承压主体**: industrial_short_001(stressed)
- **最近稳态**: unstable
- **变形链事件**: 23 次变形
- **反馈差异**: 14 个（已解决 14）
