# Real_World 实验报告：Full-Topology-World

**实验ID**: exp_005_full_topology
**运行步数**: 30
**总破缺事件**: 30

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_shortage | inventory | region_A | exchange_delivery | 3049.6 | 2422.2 | active |
| delivery_pressure | delivery | near_month | exchange | 87.4 | 0.0 | resolved |
| expectation_bullish | expectation | market | price | 41.6 | 0.0 | resolved |
| transform_inventory_to_delivery_1_inventory_shortage | delivery | warehouse_receipt_channel | exchange_delivery | 12.9 | 0.0 | resolved |
| transform_delivery_to_basis_1_delivery_pressure | basis | delivery_channel | exchange | 17.0 | 0.0 | resolved |
| transform_expectation_to_price_1_expectation_bullish | price | futures_contract_channel | price | 0.8 | 0.0 | resolved |
| feedback_margin_industrial_short_001_1 | margin | industrial_short_001 | clearing | 3.0 | 0.0 | resolved |
| feedback_margin_speculative_long_001_1 | margin | speculative_long_001 | clearing | 9.7 | 0.0 | resolved |
| feedback_margin_speculator_002_1 | margin | speculator_002 | clearing | 0.4 | 0.0 | resolved |
| feedback_margin_exchange_001_1 | margin | exchange_001 | clearing | 2.1 | 0.0 | resolved |
| transform_delivery_to_basis_2_delivery_pressure | basis | delivery_channel | exchange | 9.4 | 0.0 | resolved |
| feedback_margin_exchange_001_2 | margin | exchange_001 | clearing | 3.8 | 0.0 | resolved |
| feedback_margin_industrial_short_001_2 | margin | industrial_short_001 | clearing | 1.5 | 0.0 | resolved |
| feedback_margin_speculator_002_2 | margin | speculator_002 | clearing | 1.9 | 0.0 | resolved |
| feedback_margin_speculative_long_001_2 | margin | speculative_long_001 | clearing | 3.6 | 0.0 | resolved |
| intervention_expectation_2 | expectation | exchange | market | 7.0 | 0.0 | resolved |
| intervention_rule_2 | rule | exchange | delivery | 2.7 | 2.7 | active |
| intervention_liquidity_2 | liquidity | exchange | market | 8.0 | 8.0 | active |
| feedback_margin_speculative_long_001_3 | margin | speculative_long_001 | clearing | 4.5 | 0.0 | resolved |
| feedback_margin_speculator_002_3 | margin | speculator_002 | clearing | 1.8 | 0.0 | resolved |
| intervention_expectation_3 | expectation | exchange | market | 7.0 | 0.0 | resolved |
| intervention_liquidity_3 | liquidity | exchange | market | 8.0 | 8.0 | active |
| feedback_margin_speculative_long_001_4 | margin | speculative_long_001 | clearing | 4.5 | 0.0 | resolved |
| intervention_expectation_4 | expectation | exchange | market | 7.0 | 0.0 | resolved |
| intervention_liquidity_4 | liquidity | exchange | market | 8.0 | 8.0 | active |
| intervention_expectation_5 | expectation | exchange | market | 7.0 | 0.0 | resolved |
| intervention_liquidity_5 | liquidity | exchange | market | 8.0 | 8.0 | active |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 35.0 | 经通道 warehouse_receipt_channel 转移 35.0 压力 |
| 1 | delivery_pressure | delivery_channel | 45.0 | 经通道 delivery_channel 转移 45.0 压力 |
| 1 | expectation_bullish | futures_contract_channel | 3.1 | 经通道 futures_contract_channel 转移 3.1 压力 |
| 2 | delivery_pressure | delivery_channel | 24.8 | 经通道 delivery_channel 转移 24.8 压力 |

## 三、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| warehouse_receipt_channel | inventory→delivery | 15.0 | 700% | 0.07 | 0.070 | open |
| delivery_channel | delivery→basis | 20.0 | 1396% | 0.14 | 0.140 | open |
| basis_channel | basis→price | 12.0 | 0% | 0.00 | 0.000 | open |
| futures_contract_channel | expectation→price | 10.0 | 63% | 0.01 | 0.006 | open |
| margin_clearing_channel | price→margin | 8.0 | 0% | 0.00 | 0.000 | open |
| position_reduction_channel | margin→liquidity | 12.0 | 0% | 0.00 | 0.000 | open |
| exchange_rule_channel | delivery→rule | 50.0 | 0% | 0.00 | 0.000 | open |

## 四、破缺事件

| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |
|---|---|---|---|---|
| 1 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 94.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 2 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 174.4 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 3 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 255.7 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 4 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 340.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 5 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 431.0 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 6 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 528.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 7 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 634.8 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 8 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 751.3 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 9 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 879.4 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 10 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 1020.5 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 11 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 1175.9 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 12 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 1347.0 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 13 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 1535.0 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 14 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 1741.1 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 15 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 1966.7 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 16 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 2212.9 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 17 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 2480.8 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 18 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 2771.7 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 19 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 3086.5 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 20 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 3426.4 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 21 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 3792.3 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 22 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 4185.1 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 23 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 4605.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 24 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 5054.7 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 25 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 5532.9 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 26 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 6041.0 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 27 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 3289.7 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 28 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 3801.1 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 29 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 4318.7 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 30 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 4844.5 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |

## 五、最近稳态

**最终稳态判定**: unstable

**判定理由**: 近3步有87次破缺，系统不稳定

## 六、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 77.4 | 6 | 7 | high | unstable |
| 2 | 115.7 | 8 | 7 | critical | unstable |
| 3 | 159.8 | 7 | 7 | critical | unstable |
| 4 | 208.6 | 7 | 7 | critical | unstable |
| 5 | 257.2 | 7 | 7 | critical | unstable |
| 6 | 299.0 | 6 | 7 | critical | unstable |
| 7 | 352.1 | 6 | 7 | critical | unstable |
| 8 | 410.4 | 6 | 7 | critical | unstable |
| 9 | 474.4 | 6 | 7 | critical | unstable |
| 10 | 544.9 | 6 | 7 | critical | unstable |
| 11 | 622.7 | 6 | 7 | critical | unstable |
| 12 | 708.2 | 6 | 7 | critical | unstable |
| 13 | 802.2 | 6 | 7 | critical | unstable |
| 14 | 905.3 | 6 | 7 | critical | unstable |
| 15 | 1018.0 | 6 | 7 | critical | unstable |
| 16 | 1141.1 | 6 | 7 | critical | unstable |
| 17 | 1275.1 | 6 | 7 | critical | unstable |
| 18 | 1420.5 | 6 | 7 | critical | unstable |
| 19 | 1578.0 | 6 | 7 | critical | unstable |
| 20 | 1747.9 | 6 | 7 | critical | unstable |
| 21 | 1930.9 | 6 | 7 | critical | unstable |
| 22 | 2127.2 | 6 | 7 | critical | unstable |
| 23 | 2337.5 | 6 | 7 | critical | unstable |
| 24 | 2562.0 | 6 | 7 | critical | unstable |
| 25 | 2801.2 | 6 | 7 | critical | unstable |
| 26 | 3055.2 | 6 | 7 | critical | unstable |
| 27 | 1679.5 | 6 | 7 | critical | unstable |
| 28 | 1935.3 | 6 | 7 | critical | unstable |
| 29 | 2194.0 | 6 | 7 | critical | unstable |
| 30 | 2456.9 | 6 | 7 | critical | unstable |

## 七、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 2422.2
- **最近稳态**: unstable
