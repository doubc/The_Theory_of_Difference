# Real_World 实验报告：Comparison-World

**实验ID**: exp_007b_fast_decay
**运行步数**: 40
**总破缺事件**: 1

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_shortage | inventory | region_A | exchange_delivery | 85.5 | 51.7 | active |
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

| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |
|---|---|---|---|---|
| 12 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 91.1 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |

## 八、最近稳态

**最终稳态判定**: unstable

**判定理由**: 近3步有3次破缺，系统不稳定

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 53.5 | 1 | 7 | medium | margin_relief |
| 2 | 39.7 | 1 | 7 | medium | margin_relief |
| 3 | 51.2 | 1 | 7 | medium | margin_relief |
| 4 | 60.4 | 1 | 7 | high | margin_relief |
| 5 | 67.8 | 1 | 7 | high | margin_relief |
| 6 | 73.7 | 1 | 7 | high | margin_relief |
| 7 | 78.4 | 1 | 7 | high | margin_relief |
| 8 | 82.2 | 1 | 7 | high | margin_relief |
| 9 | 85.2 | 1 | 7 | high | margin_relief |
| 10 | 87.6 | 1 | 7 | high | margin_relief |
| 11 | 89.5 | 1 | 7 | high | margin_relief |
| 12 | 45.5 | 1 | 7 | medium | margin_relief |
| 13 | 46.8 | 1 | 7 | medium | margin_relief |
| 14 | 47.8 | 1 | 7 | medium | unstable |
| 15 | 48.6 | 1 | 7 | medium | unstable |
| 16 | 49.2 | 1 | 7 | medium | unstable |
| 17 | 49.7 | 1 | 7 | medium | unstable |
| 18 | 50.1 | 1 | 7 | medium | unstable |
| 19 | 50.4 | 1 | 7 | medium | unstable |
| 20 | 50.7 | 1 | 7 | medium | unstable |
| 21 | 50.9 | 1 | 7 | medium | unstable |
| 22 | 51.1 | 1 | 7 | medium | unstable |
| 23 | 51.2 | 1 | 7 | medium | unstable |
| 24 | 51.3 | 1 | 7 | medium | unstable |
| 25 | 51.4 | 1 | 7 | medium | unstable |
| 26 | 51.4 | 1 | 7 | medium | unstable |
| 27 | 51.5 | 1 | 7 | medium | unstable |
| 28 | 51.5 | 1 | 7 | medium | unstable |
| 29 | 51.6 | 1 | 7 | medium | unstable |
| 30 | 51.6 | 1 | 7 | medium | unstable |
| 31 | 51.6 | 1 | 7 | medium | unstable |
| 32 | 51.6 | 1 | 7 | medium | unstable |
| 33 | 51.7 | 1 | 7 | medium | unstable |
| 34 | 51.7 | 1 | 7 | medium | unstable |
| 35 | 51.7 | 1 | 7 | medium | unstable |
| 36 | 51.7 | 1 | 7 | medium | unstable |
| 37 | 51.7 | 1 | 7 | medium | unstable |
| 38 | 51.7 | 1 | 7 | medium | unstable |
| 39 | 51.7 | 1 | 7 | medium | unstable |
| 40 | 51.7 | 1 | 7 | medium | unstable |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 51.7
- **承压主体**: industrial_short_001(stressed), speculative_long_001(stressed), speculator_002(stressed)
- **最近稳态**: unstable
- **变形链事件**: 3 次变形
- **反馈差异**: 3 个（已解决 3）
