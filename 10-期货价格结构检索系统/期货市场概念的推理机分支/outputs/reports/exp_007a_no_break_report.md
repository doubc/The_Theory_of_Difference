# Real_World 实验报告：Comparison-World

**实验ID**: exp_007a_no_break
**运行步数**: 40
**总破缺事件**: 0

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_shortage | inventory | region_A | exchange_delivery | 85.5 | 321.0 | active |
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
| 1 | inventory_shortage | warehouse_receipt_channel | 10.5 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |
| 1 | delivery_pressure | delivery_channel | 11.1 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 2 | inventory_shortage | warehouse_receipt_channel | 7.3 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_short_001_1 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 7.5，杠杆 2.0x，产生保证金差异 4.5 |
| feedback_margin_speculative_long_001_1 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 30.0，杠杆 2.0x，产生保证金差异 18.0 |
| feedback_margin_industrial_short_001_2 | margin | industrial_short_001 | 0.0 | resolved | 反馈: industrial_short_001 承压 3.8，杠杆 2.0x，产生保证金差异 2.2 |

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

**最终稳态判定**: margin_relief

**判定理由**: 超过75%主体处于压力状态，等待保证金缓解

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 53.5 | 1 | 7 | medium | margin_relief |
| 2 | 42.3 | 1 | 7 | medium | margin_relief |
| 3 | 58.6 | 1 | 7 | medium | margin_relief |
| 4 | 74.0 | 1 | 7 | high | margin_relief |
| 5 | 88.7 | 1 | 7 | high | margin_relief |
| 6 | 102.6 | 1 | 7 | critical | margin_relief |
| 7 | 115.8 | 1 | 7 | critical | margin_relief |
| 8 | 128.4 | 1 | 7 | critical | margin_relief |
| 9 | 140.4 | 1 | 7 | critical | margin_relief |
| 10 | 151.7 | 1 | 7 | critical | margin_relief |
| 11 | 162.5 | 1 | 7 | critical | margin_relief |
| 12 | 172.7 | 1 | 7 | critical | margin_relief |
| 13 | 182.4 | 1 | 7 | critical | margin_relief |
| 14 | 191.7 | 1 | 7 | critical | margin_relief |
| 15 | 200.5 | 1 | 7 | critical | margin_relief |
| 16 | 208.8 | 1 | 7 | critical | margin_relief |
| 17 | 216.7 | 1 | 7 | critical | margin_relief |
| 18 | 224.3 | 1 | 7 | critical | margin_relief |
| 19 | 231.4 | 1 | 7 | critical | margin_relief |
| 20 | 238.2 | 1 | 7 | critical | margin_relief |
| 21 | 244.6 | 1 | 7 | critical | margin_relief |
| 22 | 250.8 | 1 | 7 | critical | margin_relief |
| 23 | 256.6 | 1 | 7 | critical | margin_relief |
| 24 | 262.1 | 1 | 7 | critical | margin_relief |
| 25 | 267.4 | 1 | 7 | critical | margin_relief |
| 26 | 272.4 | 1 | 7 | critical | margin_relief |
| 27 | 277.1 | 1 | 7 | critical | margin_relief |
| 28 | 281.6 | 1 | 7 | critical | margin_relief |
| 29 | 285.9 | 1 | 7 | critical | margin_relief |
| 30 | 290.0 | 1 | 7 | critical | margin_relief |
| 31 | 293.8 | 1 | 7 | critical | margin_relief |
| 32 | 297.5 | 1 | 7 | critical | margin_relief |
| 33 | 301.0 | 1 | 7 | critical | margin_relief |
| 34 | 304.3 | 1 | 7 | critical | margin_relief |
| 35 | 307.5 | 1 | 7 | critical | margin_relief |
| 36 | 310.4 | 1 | 7 | critical | margin_relief |
| 37 | 313.3 | 1 | 7 | critical | margin_relief |
| 38 | 316.0 | 1 | 7 | critical | margin_relief |
| 39 | 318.6 | 1 | 7 | critical | margin_relief |
| 40 | 321.0 | 1 | 7 | critical | margin_relief |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 321.0
- **承压主体**: industrial_short_001(stressed), speculative_long_001(stressed), speculator_002(stressed)
- **最近稳态**: margin_relief
- **变形链事件**: 3 次变形
- **反馈差异**: 3 个（已解决 3）
