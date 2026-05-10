# Real_World 实验报告：Comparison-World

**实验ID**: exp_007a_no_break
**运行步数**: 10
**总破缺事件**: 0

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_shortage | inventory | region_A | exchange_delivery | 85.5 | 151.7 | active |
| delivery_pressure | delivery | near_month | exchange | 69.9 | 0.0 | resolved |
| expectation_bullish | expectation | market | price | 35.7 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 35.0 | 经通道 warehouse_receipt_channel 转移 35.0 压力 |
| 1 | delivery_pressure | delivery_channel | 20.0 | 经通道 delivery_channel 转移 20.0 压力 |
| 2 | inventory_shortage | warehouse_receipt_channel | 24.5 | 经通道 warehouse_receipt_channel 转移 24.5 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_shortage | warehouse_receipt_channel | 10.5 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0，损耗=24.50 |
| 1 | delivery_pressure | delivery_channel | 11.1 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0，损耗=8.91 |
| 2 | inventory_shortage | warehouse_receipt_channel | 7.3 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0，损耗=17.15 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_short_001_1 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 7.5，杠杆 2.0x，产生保证金差异 4.5 |
| feedback_margin_speculative_long_001_1 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 30.0，杠杆 2.0x，产生保证金差异 18.0 |
| feedback_margin_industrial_short_001_2 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 3.8，杠杆 2.0x，产生保证金差异 2.2 |
| feedback_margin_speculative_long_001_6 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 4.7，杠杆 2.0x，产生保证金差异 2.8 |

## 五、干预记录

| 时间 | 类型 | 量 | 说明 |
|---|---|---|---|
| 5 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 5 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 5 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(22.6), speculator_002(16.4) |
| 5 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 6 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 6 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 6 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(17.8), speculator_002(11.5) |
| 6 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| warehouse_receipt_channel | inventory→delivery | 15.0 | 1190% | 0.12 | 0.119 | open |
| delivery_channel | delivery→basis | 20.0 | 400% | 0.04 | 0.040 | open |
| basis_channel | basis→price | 12.0 | 0% | 0.00 | 0.000 | open |
| futures_contract_channel | expectation→price | 10.0 | 0% | 0.00 | 0.000 | open |
| margin_clearing_channel | price→margin | 8.0 | 0% | 0.00 | 0.000 | open |
| position_reduction_channel | margin→liquidity | 12.0 | 0% | 0.00 | 0.000 | open |
| exchange_rule_channel | delivery→rule | 50.0 | 0% | 0.00 | 0.000 | open |

## 七、破缺事件

*无破缺事件*

## 八、最近稳态

**最终稳态判定**: basis_widening

**判定理由**: 主导差异类型为 inventory，库存差异经基差通道显影，基差扩大稳态

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 53.5 | 1 | 7 | medium | margin_relief |
| 2 | 42.3 | 1 | 7 | medium | margin_relief |
| 3 | 58.6 | 1 | 7 | medium | margin_relief |
| 4 | 74.0 | 1 | 7 | high | margin_relief |
| 5 | 98.5 | 3 | 7 | critical | margin_relief |
| 6 | 117.5 | 4 | 7 | critical | basis_widening |
| 7 | 126.0 | 3 | 7 | critical | basis_widening |
| 8 | 138.6 | 3 | 7 | critical | basis_widening |
| 9 | 150.6 | 3 | 7 | critical | basis_widening |
| 10 | 161.9 | 3 | 7 | critical | basis_widening |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 151.7
- **承压主体**: industrial_short_001(stressed), speculative_long_001(stressed)
- **最近稳态**: basis_widening
- **变形链事件**: 3 次变形
- **反馈差异**: 4 个（已解决 4）
