# Real_World 实验报告：Near-Month-Squeeze-World

**实验ID**: exp_003_near_month_squeeze
**运行步数**: 25
**总破缺事件**: 4

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| delivery_pressure | delivery | near_month | exchange | 81.2 | 0.0 | resolved |
| inventory_shortage | inventory | region_A | exchange_delivery | 61.2 | 49.9 | active |
| expectation_bullish | expectation | market | price | 35.7 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | delivery_pressure | delivery_channel | 40.0 | 经通道 delivery_channel 转移 40.0 压力 |
| 1 | inventory_shortage | warehouse_receipt_channel | 30.0 | 经通道 warehouse_receipt_channel 转移 30.0 压力 |
| 1 | expectation_bullish | futures_contract_channel | 41.7 | 经通道 futures_contract_channel 转移 41.7 压力 |
| 2 | delivery_pressure | delivery_channel | 28.0 | 经通道 delivery_channel 转移 28.0 压力 |
| 3 | delivery_pressure | delivery_channel | 28.0 | 经通道 delivery_channel 转移 28.0 压力 |
| 4 | delivery_pressure | delivery_channel | 48.0 | 经通道 delivery_channel 转移 48.0 压力 |
| 5 | delivery_pressure | delivery_channel | 35.1 | 经通道 delivery_channel 转移 35.1 压力 |
| 5 | intervention_expectation_4 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 6 | intervention_expectation_5 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 7 | intervention_expectation_6 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 9 | intervention_expectation_8 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 10 | intervention_expectation_9 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 11 | intervention_expectation_10 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 12 | intervention_expectation_11 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 13 | intervention_expectation_12 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 14 | intervention_expectation_13 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 15 | intervention_expectation_14 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 18 | intervention_expectation_17 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 19 | intervention_expectation_18 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 20 | intervention_expectation_19 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 21 | intervention_expectation_20 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 22 | intervention_expectation_21 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 23 | intervention_expectation_22 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 24 | intervention_expectation_23 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 25 | intervention_expectation_24 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | delivery_pressure | delivery_channel | 12.0 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 1 | inventory_shortage | warehouse_receipt_channel | 9.0 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |
| 1 | expectation_bullish | futures_contract_channel | 24.3 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 2 | delivery_pressure | delivery_channel | 8.4 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 3 | delivery_pressure | delivery_channel | 8.4 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 4 | delivery_pressure | delivery_channel | 14.4 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 5 | delivery_pressure | delivery_channel | 11.3 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 5 | intervention_expectation_4 | futures_contract_channel | 4.1 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 6 | intervention_expectation_5 | futures_contract_channel | 4.1 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 7 | intervention_expectation_6 | futures_contract_channel | 4.0 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 9 | intervention_expectation_8 | futures_contract_channel | 4.0 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 10 | intervention_expectation_9 | futures_contract_channel | 3.9 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 11 | intervention_expectation_10 | futures_contract_channel | 3.9 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 12 | intervention_expectation_11 | futures_contract_channel | 3.8 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 13 | intervention_expectation_12 | futures_contract_channel | 3.8 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 14 | intervention_expectation_13 | futures_contract_channel | 3.8 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 15 | intervention_expectation_14 | futures_contract_channel | 3.7 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 18 | intervention_expectation_17 | futures_contract_channel | 3.7 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 19 | intervention_expectation_18 | futures_contract_channel | 3.6 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 20 | intervention_expectation_19 | futures_contract_channel | 3.6 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 21 | intervention_expectation_20 | futures_contract_channel | 3.5 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 22 | intervention_expectation_21 | futures_contract_channel | 3.5 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 23 | intervention_expectation_22 | futures_contract_channel | 3.4 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 24 | intervention_expectation_23 | futures_contract_channel | 3.4 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 25 | intervention_expectation_24 | futures_contract_channel | 3.3 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_short_001_1 | margin | industrial_short_001 | 3.8 | active | 反馈: industrial_short_001 承压 10.0，杠杆 2.0x，产生保证金差异 6.0 |
| feedback_margin_exchange_001_2 | margin | exchange_001 | 8.5 | active | 反馈: exchange_001 承压 45.0，杠杆 1.0x，产生保证金差异 13.5 |
| feedback_margin_industrial_short_001_2 | margin | industrial_short_001 | 1.9 | active | 反馈: industrial_short_001 承压 5.0，杠杆 2.0x，产生保证金差异 3.0 |
| feedback_margin_exchange_001_3 | margin | exchange_001 | 4.3 | active | 反馈: exchange_001 承压 22.5，杠杆 1.0x，产生保证金差异 6.8 |
| feedback_margin_industrial_short_001_3 | margin | industrial_short_001 | 0.9 | active | 反馈: industrial_short_001 承压 2.5，杠杆 2.0x，产生保证金差异 1.5 |
| feedback_margin_exchange_001_4 | margin | exchange_001 | 2.1 | active | 反馈: exchange_001 承压 11.2，杠杆 1.0x，产生保证金差异 3.4 |
| feedback_margin_exchange_001_5 | margin | exchange_001 | 1.1 | active | 反馈: exchange_001 承压 5.6，杠杆 1.0x，产生保证金差异 1.7 |

## 五、干预记录

| 时间 | 类型 | 量 | 说明 |
|---|---|---|---|
| 3 | exchange_intervene | 0.50 | 交易所扩大通道容量 50%，影响: delivery_channel(40→60) |
| 3 | intervention_side_effect | 12.50 | 干预副作用: 扩通道 → 规则差异 12.5 |
| 3 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(15.5) |
| 3 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 4 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 4 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 4 | exchange_intervene | 0.50 | 交易所扩大通道容量 50%，影响: delivery_channel(60→90) |
| 4 | intervention_side_effect | 12.50 | 干预副作用: 扩通道 → 规则差异 12.5 |
| 4 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(10.9) |
| 4 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 5 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 5 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 5 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(9.0) |
| 5 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 6 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 6 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 7 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(9.1) |
| 7 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 8 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 8 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 9 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 9 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 10 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 10 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 10 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(9.2) |
| 10 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 11 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 11 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 12 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 12 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 12 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(9.3) |
| 12 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 13 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 13 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 14 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 14 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 14 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(9.3) |
| 14 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 17 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 17 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 18 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 18 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 18 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(9.4) |
| 18 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 19 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 19 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 20 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 20 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 20 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(9.4) |
| 20 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 21 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 21 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 22 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 22 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 22 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(9.4) |
| 22 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 23 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 23 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 24 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 24 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 24 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(9.4) |
| 24 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 25 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 25 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| delivery_channel | delivery→basis | 20.0 | 3582% | 0.36 | 0.358 | open |
| warehouse_receipt_channel | inventory→delivery | 15.0 | 600% | 0.06 | 0.060 | open |
| futures_contract_channel | expectation→price | 10.4 | 2913% | 0.29 | 0.254 | open |
| exchange_rule_channel | delivery→rule | 50.0 | 0% | 0.00 | 0.000 | open |

## 七、破缺事件

| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |
|---|---|---|---|---|
| 1 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 72.7 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 3 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 73.7 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 7 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 73.2 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 15 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 71.5 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |

## 八、最近稳态

**最终稳态判定**: unstable

**判定理由**: 近3步有12次破缺，系统不稳定

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 132.7 | 6 | 4 | critical | unstable |
| 2 | 154.5 | 8 | 4 | critical | unstable |
| 3 | 143.0 | 12 | 4 | critical | unstable |
| 4 | 152.4 | 16 | 4 | critical | unstable |
| 5 | 156.6 | 18 | 4 | critical | unstable |
| 6 | 169.1 | 19 | 4 | critical | unstable |
| 7 | 144.4 | 20 | 4 | critical | unstable |
| 8 | 155.6 | 21 | 4 | critical | unstable |
| 9 | 165.4 | 22 | 4 | critical | unstable |
| 10 | 179.5 | 24 | 4 | critical | unstable |
| 11 | 187.8 | 25 | 4 | critical | unstable |
| 12 | 200.7 | 27 | 4 | critical | unstable |
| 13 | 207.9 | 28 | 4 | critical | unstable |
| 14 | 219.8 | 30 | 4 | critical | unstable |
| 15 | 185.7 | 30 | 4 | critical | unstable |
| 16 | 188.0 | 30 | 4 | critical | unstable |
| 17 | 194.8 | 31 | 4 | critical | unstable |
| 18 | 205.4 | 33 | 4 | critical | unstable |
| 19 | 210.6 | 34 | 4 | critical | unstable |
| 20 | 220.7 | 36 | 4 | critical | unstable |
| 21 | 225.5 | 37 | 4 | critical | unstable |
| 22 | 235.2 | 39 | 4 | critical | unstable |
| 23 | 239.6 | 40 | 4 | critical | unstable |
| 24 | 248.9 | 42 | 4 | critical | unstable |
| 25 | 253.0 | 43 | 4 | critical | unstable |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 49.9
- **承压主体**: industrial_short_001(stressed), exchange_001(stressed)
- **最近稳态**: unstable
- **变形链事件**: 25 次变形
- **反馈差异**: 7 个（已解决 0）
