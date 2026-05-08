# Real_World 实验报告：Full-Topology-World

**实验ID**: exp_005_full_topology
**运行步数**: 5
**总破缺事件**: 6

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_shortage | inventory | region_A | exchange_delivery | 102.6 | 36.8 | active |
| delivery_pressure | delivery | near_month | exchange | 87.4 | 0.0 | resolved |
| expectation_bullish | expectation | market | price | 41.6 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 35.0 | 经通道 warehouse_receipt_channel 转移 35.0 压力 |
| 1 | delivery_pressure | delivery_channel | 45.0 | 经通道 delivery_channel 转移 45.0 压力 |
| 1 | expectation_bullish | futures_contract_channel | 55.6 | 经通道 futures_contract_channel 转移 55.6 压力 |
| 1 | transform_inventory_to_basis_0_inventory_shortage | basis_channel | 10.5 | 经通道 basis_channel 转移 10.5 压力 |
| 1 | transform_delivery_to_basis_0_delivery_pressure | basis_channel | 13.5 | 经通道 basis_channel 转移 13.5 压力 |
| 1 | transform_expectation_to_price_0_expectation_bullish | margin_clearing_channel | 24.7 | 经通道 margin_clearing_channel 转移 24.7 压力 |
| 1 | feedback_margin_industrial_short_001_1 | position_reduction_channel | 7.1 | 经通道 position_reduction_channel 转移 7.1 压力 |
| 1 | feedback_margin_industrial_short_001_1 | position_reduction_channel | 3.5 | 经通道 position_reduction_channel 转移 3.5 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 12.8 | 经通道 position_reduction_channel 转移 12.8 压力 |
| 1 | transform_basis_to_price_1_transform_inventory_to_basis_0_inventory_shortage | margin_clearing_channel | 9.1 | 经通道 margin_clearing_channel 转移 9.1 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 6.4 | 经通道 position_reduction_channel 转移 6.4 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 1.7 | 经通道 position_reduction_channel 转移 1.7 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 1.6 | 经通道 position_reduction_channel 转移 1.6 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.8 | 经通道 position_reduction_channel 转移 0.8 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.4 | 经通道 position_reduction_channel 转移 0.4 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.2 | 经通道 position_reduction_channel 转移 0.2 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 经通道 position_reduction_channel 转移 0.1 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 经通道 position_reduction_channel 转移 0.1 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.0 | 经通道 position_reduction_channel 转移 0.0 压力 |
| 2 | delivery_pressure | delivery_channel | 54.0 | 经通道 delivery_channel 转移 54.0 压力 |
| 2 | transform_basis_to_price_1_transform_delivery_to_basis_0_delivery_pressure | margin_clearing_channel | 9.4 | 经通道 margin_clearing_channel 转移 9.4 压力 |
| 2 | transform_price_to_margin_1_transform_expectation_to_price_0_expectation_bullish | position_reduction_channel | 14.5 | 经通道 position_reduction_channel 转移 14.5 压力 |
| 2 | transform_price_to_margin_2_transform_basis_to_price_1_transform_inventory_to_basis_0_inventory_shortage | position_reduction_channel | 4.0 | 经通道 position_reduction_channel 转移 4.0 压力 |
| 2 | intervention_expectation_1 | futures_contract_channel | 4.7 | 经通道 futures_contract_channel 转移 4.7 压力 |
| 2 | transform_delivery_to_basis_0_delivery_pressure | basis_channel | 16.2 | 经通道 basis_channel 转移 16.2 压力 |
| 2 | transform_price_to_margin_0_transform_basis_to_price_1_transform_delivery_to_basis_0_delivery_pressure | position_reduction_channel | 6.4 | 经通道 position_reduction_channel 转移 6.4 压力 |
| 2 | transform_expectation_to_price_0_intervention_expectation_1 | margin_clearing_channel | 3.7 | 经通道 margin_clearing_channel 转移 3.7 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 10.5 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |
| 1 | delivery_pressure | delivery_channel | 13.5 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 1 | expectation_bullish | futures_contract_channel | 24.7 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 1 | transform_inventory_to_basis_0_inventory_shortage | basis_channel | 9.1 | 差异变形: basis → price，经通道 basis_channel，深度 1 |
| 1 | transform_delivery_to_basis_0_delivery_pressure | basis_channel | 9.4 | 差异变形: basis → price，经通道 basis_channel，深度 1 |
| 1 | transform_expectation_to_price_0_expectation_bullish | margin_clearing_channel | 14.5 | 差异变形: price → margin，经通道 margin_clearing_channel，深度 1 |
| 1 | feedback_margin_industrial_short_001_1 | position_reduction_channel | 6.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 1 | feedback_margin_industrial_short_001_1 | position_reduction_channel | 2.8 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 6.8 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 1 | transform_basis_to_price_1_transform_inventory_to_basis_0_inventory_shortage | margin_clearing_channel | 4.0 | 差异变形: price → margin，经通道 margin_clearing_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 2.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculative_long_001_1 | position_reduction_channel | 0.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.5 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.3 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 1 | feedback_margin_speculator_002_1 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 2 | delivery_pressure | delivery_channel | 16.2 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 2 | transform_basis_to_price_1_transform_delivery_to_basis_0_delivery_pressure | margin_clearing_channel | 6.4 | 差异变形: price → margin，经通道 margin_clearing_channel，深度 0 |
| 2 | transform_price_to_margin_1_transform_expectation_to_price_0_expectation_bullish | position_reduction_channel | 7.3 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 0 |
| 2 | transform_price_to_margin_2_transform_basis_to_price_1_transform_inventory_to_basis_0_inventory_shortage | position_reduction_channel | 1.7 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 0 |
| 2 | intervention_expectation_1 | futures_contract_channel | 3.7 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 2 | transform_delivery_to_basis_0_delivery_pressure | basis_channel | 11.5 | 差异变形: basis → price，经通道 basis_channel，深度 1 |
| 2 | transform_price_to_margin_0_transform_basis_to_price_1_transform_delivery_to_basis_0_delivery_pressure | position_reduction_channel | 1.9 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 2 | transform_expectation_to_price_0_intervention_expectation_1 | margin_clearing_channel | 2.3 | 差异变形: price → margin，经通道 margin_clearing_channel，深度 1 |
| 2 | feedback_margin_exchange_001_2 | position_reduction_channel | 1.7 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 2 | feedback_margin_industrial_short_001_2 | position_reduction_channel | 0.5 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 2 | feedback_margin_speculative_long_001_2 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 2 | feedback_margin_speculator_002_2 | position_reduction_channel | 0.2 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 2 | feedback_margin_speculator_002_2 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 2 | feedback_margin_speculator_002_2 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 2 | feedback_margin_speculator_002_2 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 2 | feedback_margin_speculator_002_2 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 3 | delivery_pressure | delivery_channel | 17.7 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 3 | transform_basis_to_price_1_transform_delivery_to_basis_0_delivery_pressure | margin_clearing_channel | 7.9 | 差异变形: price → margin，经通道 margin_clearing_channel，深度 0 |
| 3 | transform_price_to_margin_1_transform_expectation_to_price_0_intervention_expectation_1 | position_reduction_channel | 1.8 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 0 |
| 3 | intervention_expectation_2 | futures_contract_channel | 3.9 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 3 | transform_delivery_to_basis_0_delivery_pressure | basis_channel | 12.2 | 差异变形: basis → price，经通道 basis_channel，深度 1 |
| 3 | transform_price_to_margin_0_transform_basis_to_price_1_transform_delivery_to_basis_0_delivery_pressure | position_reduction_channel | 5.5 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 3 | transform_expectation_to_price_0_intervention_expectation_2 | margin_clearing_channel | 2.5 | 差异变形: price → margin，经通道 margin_clearing_channel，深度 1 |
| 3 | feedback_margin_exchange_001_3 | position_reduction_channel | 1.8 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 3 | feedback_margin_speculator_002_3 | position_reduction_channel | 0.8 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 3 | feedback_margin_speculator_002_3 | position_reduction_channel | 1.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 3 | feedback_margin_speculator_002_3 | position_reduction_channel | 0.9 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 3 | feedback_margin_speculator_002_3 | position_reduction_channel | 0.4 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 3 | feedback_margin_speculator_002_3 | position_reduction_channel | 0.2 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 3 | feedback_margin_speculator_002_3 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 3 | feedback_margin_speculator_002_3 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 3 | feedback_margin_speculator_002_3 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 3 | feedback_margin_speculator_002_3 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 4 | transform_basis_to_price_1_transform_delivery_to_basis_0_delivery_pressure | margin_clearing_channel | 8.2 | 差异变形: price → margin，经通道 margin_clearing_channel，深度 0 |
| 4 | transform_price_to_margin_1_transform_expectation_to_price_0_intervention_expectation_2 | position_reduction_channel | 1.9 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 0 |
| 4 | intervention_expectation_3 | futures_contract_channel | 3.9 | 差异变形: expectation → price，经通道 futures_contract_channel，深度 0 |
| 4 | transform_price_to_margin_0_transform_basis_to_price_1_transform_delivery_to_basis_0_delivery_pressure | position_reduction_channel | 5.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 4 | transform_expectation_to_price_0_intervention_expectation_3 | margin_clearing_channel | 2.4 | 差异变形: price → margin，经通道 margin_clearing_channel，深度 1 |
| 4 | feedback_margin_speculative_long_001_4 | position_reduction_channel | 5.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 4 | feedback_margin_speculator_002_4 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 4 | feedback_margin_speculator_002_4 | position_reduction_channel | 0.8 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 4 | feedback_margin_speculator_002_4 | position_reduction_channel | 1.3 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 1 |
| 4 | transform_price_to_margin_1_transform_expectation_to_price_0_intervention_expectation_3 | position_reduction_channel | 1.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 4 | feedback_margin_speculator_002_4 | position_reduction_channel | 0.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 4 | feedback_margin_speculator_002_4 | position_reduction_channel | 0.6 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 4 | feedback_margin_speculative_long_001_4 | position_reduction_channel | 0.4 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 4 | feedback_margin_speculator_002_4 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 4 | feedback_margin_speculative_long_001_4 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 2 |
| 4 | feedback_margin_speculator_002_4 | position_reduction_channel | 0.1 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 4 | feedback_margin_speculator_002_4 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |
| 4 | feedback_margin_speculator_002_4 | position_reduction_channel | 0.0 | 差异变形: margin → liquidity，经通道 position_reduction_channel，深度 3 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_short_001_1 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 7.5，杠杆 2.5x，产生保证金差异 5.6 |
| feedback_margin_speculative_long_001_1 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.0，杠杆 4.0x，产生保证金差异 0.0 |
| feedback_margin_speculator_002_1 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.0，杠杆 3.0x，产生保证金差异 0.0 |
| feedback_margin_exchange_001_2 | margin | exchange_001 | 0.0 | resolved | 反馈: exchange_001 承压 30.0，杠杆 1.0x，产生保证金差异 9.0 |
| feedback_margin_industrial_short_001_2 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 3.8，杠杆 2.5x，产生保证金差异 2.8 |
| feedback_margin_speculative_long_001_2 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.0，杠杆 4.0x，产生保证金差异 0.0 |
| feedback_margin_speculator_002_2 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.0，杠杆 3.0x，产生保证金差异 0.0 |
| feedback_margin_exchange_001_3 | margin | exchange_001 | 0.0 | resolved | 反馈: exchange_001 承压 15.0，杠杆 1.0x，产生保证金差异 4.5 |
| feedback_margin_speculative_long_001_3 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.0，杠杆 4.0x，产生保证金差异 0.0 |
| feedback_margin_speculator_002_3 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.0，杠杆 3.0x，产生保证金差异 0.0 |
| feedback_margin_speculative_long_001_4 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.0，杠杆 4.0x，产生保证金差异 0.0 |
| feedback_margin_speculator_002_4 | margin | speculator_002 | 0.0 | resolved | 反馈: speculator_002 承压 0.0，杠杆 3.0x，产生保证金差异 0.0 |
| feedback_liquidity_speculative_long_001_4 | liquidity | speculative_long_001 | 0.0 | active | 反馈: speculative_long_001 流动性 18.4 低于阈值，产生流动性差异 0.0 |
| feedback_margin_speculative_long_001_5 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 0.0，杠杆 4.0x，产生保证金差异 0.0 |

## 五、干预记录

| 时间 | 类型 | 量 | 说明 |
|---|---|---|---|
| 1 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 1 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 1 | exchange_intervene | 0.50 | 交易所扩大通道容量 50%，影响: warehouse_receipt_channel(35→52), delivery_channel(45→68) |
| 1 | intervention_side_effect | 12.50 | 干预副作用: 扩通道 → 规则差异 12.5 |
| 1 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(24.0), speculator_002(18.0) |
| 1 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 2 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 2 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 2 | exchange_intervene | 0.50 | 交易所扩大通道容量 50%，影响: delivery_channel(68→101), position_reduction_channel(50→75) |
| 2 | intervention_side_effect | 12.50 | 干预副作用: 扩通道 → 规则差异 12.5 |
| 2 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(24.0), speculator_002(18.0) |
| 2 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 3 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 3 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 3 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(24.0), speculator_002(18.0) |
| 3 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 4 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(24.0), speculator_002(18.0) |
| 4 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 5 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(16.8), speculator_002(12.6) |
| 5 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| warehouse_receipt_channel | inventory→delivery | 15.0 | 700% | 0.07 | 0.070 | open |
| delivery_channel | delivery→basis | 20.0 | 3160% | 0.32 | 0.316 | open |
| basis_channel | basis→price | 12.0 | 1158% | 0.12 | 0.116 | open |
| futures_contract_channel | expectation→price | 10.0 | 1397% | 0.14 | 0.140 | open |
| margin_clearing_channel | price→margin | 8.0 | 1569% | 0.16 | 0.157 | open |
| position_reduction_channel | margin→liquidity | 12.0 | 2379% | 0.24 | 0.238 | open |
| exchange_rule_channel | delivery→rule | 50.0 | 0% | 0.00 | 0.000 | open |

## 七、破缺事件

| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |
|---|---|---|---|---|
| 1 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 109.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 1 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 82.4 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 2 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 94.7 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 3 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 85.3 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 4 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 78.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 5 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 73.5 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |

## 八、最近稳态

**最终稳态判定**: unstable

**判定理由**: 近3步有15次破缺，系统不稳定

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 148.1 | 13 | 7 | critical | unstable |
| 2 | 131.9 | 21 | 7 | critical | unstable |
| 3 | 117.7 | 27 | 7 | critical | unstable |
| 4 | 109.9 | 33 | 7 | critical | unstable |
| 5 | 112.4 | 33 | 7 | critical | unstable |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 36.8
- **承压主体**: industrial_short_001(stressed), exchange_001(stressed)
- **最近稳态**: unstable
- **变形链事件**: 69 次变形
- **反馈差异**: 14 个（已解决 13）
