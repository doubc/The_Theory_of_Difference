# Real_World 实验报告：Comparison-World

**实验ID**: exp_007c_double_channel
**运行步数**: 40
**总破缺事件**: 0

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_shortage | inventory | region_A | exchange_delivery | 85.5 | 0.0 | resolved |
| delivery_pressure | delivery | near_month | exchange | 69.9 | 0.0 | resolved |
| expectation_bullish | expectation | market | price | 35.7 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 70.0 | 经通道 warehouse_receipt_channel 转移 70.0 压力 |
| 1 | delivery_pressure | delivery_channel | 20.0 | 经通道 delivery_channel 转移 20.0 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 3.7 | 经通道 position_reduction_channel 转移 3.7 压力 |
| 2 | inventory_shortage | warehouse_receipt_channel | 31.8 | 经通道 warehouse_receipt_channel 转移 31.8 压力 |
| 2 | transform_inventory_to_basis_0_inventory_shortage | basis_channel | 5.7 | 经通道 basis_channel 转移 5.7 压力 |
| 2 | transform_basis_to_price_1_transform_inventory_to_basis_0_inventory_shortage | margin_clearing_channel | 4.1 | 经通道 margin_clearing_channel 转移 4.1 压力 |
| 2 | transform_price_to_margin_2_transform_basis_to_price_1_transform_inventory_to_basis_0_inventory_shortage | position_reduction_channel | 3.3 | 经通道 position_reduction_channel 转移 3.3 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 21.0 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |
| 1 | delivery_pressure | delivery_channel | 15.6 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 3.4 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 2 | inventory_shortage | warehouse_receipt_channel | 9.6 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |
| 2 | transform_inventory_to_basis_0_inventory_shortage | basis_channel | 5.3 | 差异变形: basis → price，经通道 basis_channel，深度 1 |
| 2 | transform_basis_to_price_1_transform_inventory_to_basis_0_inventory_shortage | margin_clearing_channel | 3.9 | 差异变形: price → margin，经通道 margin_clearing_channel，深度 2 |
| 2 | transform_price_to_margin_2_transform_basis_to_price_1_transform_inventory_to_basis_0_inventory_shortage | position_reduction_channel | 3.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_short_001_1 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 7.5，杠杆 2.0x，产生保证金差异 4.5 |
| feedback_margin_speculative_long_001_1 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 30.0，杠杆 2.0x，产生保证金差异 18.0 |
| feedback_margin_industrial_short_001_2 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 3.8，杠杆 2.0x，产生保证金差异 2.2 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| warehouse_receipt_channel | inventory→delivery | 15.0 | 2037% | 0.20 | 0.204 | open |
| delivery_channel | delivery→basis | 20.0 | 400% | 0.04 | 0.040 | open |
| basis_channel | basis→price | 12.0 | 115% | 0.01 | 0.011 | open |
| futures_contract_channel | expectation→price | 10.0 | 0% | 0.00 | 0.000 | open |
| margin_clearing_channel | price→margin | 8.0 | 83% | 0.01 | 0.008 | open |
| position_reduction_channel | margin→liquidity | 12.0 | 140% | 0.01 | 0.014 | open |
| exchange_rule_channel | delivery→rule | 50.0 | 0% | 0.00 | 0.000 | open |

## 七、破缺事件

*无破缺事件*

## 八、最近稳态

**最终稳态判定**: margin_relief

**判定理由**: 超过75%主体处于压力状态，等待保证金缓解

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 21.9 | 2 | 7 | low | margin_relief |
| 2 | 6.4 | 2 | 7 | low | margin_relief |
| 3 | 6.4 | 2 | 7 | low | margin_relief |
| 4 | 6.4 | 2 | 7 | low | margin_relief |
| 5 | 6.4 | 2 | 7 | low | margin_relief |
| 6 | 6.4 | 2 | 7 | low | margin_relief |
| 7 | 6.4 | 2 | 7 | low | margin_relief |
| 8 | 6.4 | 2 | 7 | low | margin_relief |
| 9 | 6.4 | 2 | 7 | low | margin_relief |
| 10 | 6.4 | 2 | 7 | low | margin_relief |
| 11 | 6.4 | 2 | 7 | low | margin_relief |
| 12 | 6.4 | 2 | 7 | low | margin_relief |
| 13 | 6.4 | 2 | 7 | low | margin_relief |
| 14 | 6.4 | 2 | 7 | low | margin_relief |
| 15 | 6.4 | 2 | 7 | low | margin_relief |
| 16 | 6.4 | 2 | 7 | low | margin_relief |
| 17 | 6.4 | 2 | 7 | low | margin_relief |
| 18 | 6.4 | 2 | 7 | low | margin_relief |
| 19 | 6.4 | 2 | 7 | low | margin_relief |
| 20 | 6.4 | 2 | 7 | low | margin_relief |
| 21 | 6.4 | 2 | 7 | low | margin_relief |
| 22 | 6.4 | 2 | 7 | low | margin_relief |
| 23 | 6.4 | 2 | 7 | low | margin_relief |
| 24 | 6.4 | 2 | 7 | low | margin_relief |
| 25 | 6.4 | 2 | 7 | low | margin_relief |
| 26 | 6.4 | 2 | 7 | low | margin_relief |
| 27 | 6.4 | 2 | 7 | low | margin_relief |
| 28 | 6.4 | 2 | 7 | low | margin_relief |
| 29 | 6.4 | 2 | 7 | low | margin_relief |
| 30 | 6.4 | 2 | 7 | low | margin_relief |
| 31 | 6.4 | 2 | 7 | low | margin_relief |
| 32 | 6.4 | 2 | 7 | low | margin_relief |
| 33 | 6.4 | 2 | 7 | low | margin_relief |
| 34 | 6.4 | 2 | 7 | low | margin_relief |
| 35 | 6.4 | 2 | 7 | low | margin_relief |
| 36 | 6.4 | 2 | 7 | low | margin_relief |
| 37 | 6.4 | 2 | 7 | low | margin_relief |
| 38 | 6.4 | 2 | 7 | low | margin_relief |
| 39 | 6.4 | 2 | 7 | low | margin_relief |
| 40 | 6.4 | 2 | 7 | low | margin_relief |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: transform_margin_to_liquidity_1_feedback_margin_speculative_long_001_1（liquidity），压力 3.4
- **承压主体**: industrial_short_001(stressed), speculative_long_001(stressed), speculator_002(stressed)
- **最近稳态**: margin_relief
- **变形链事件**: 7 次变形
- **反馈差异**: 3 个（已解决 3）
