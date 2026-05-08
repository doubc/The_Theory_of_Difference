# Real_World 实验报告：Near-Month-Squeeze-World

**实验ID**: exp_003_near_month_squeeze
**运行步数**: 25
**总破缺事件**: 1

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| delivery_pressure | delivery | near_month | exchange | 81.2 | 0.0 | resolved |
| inventory_shortage | inventory | region_A | exchange_delivery | 61.2 | 63.4 | active |
| expectation_bullish | expectation | market | price | 35.7 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | delivery_pressure | delivery_channel | 2.7 | 经通道 delivery_channel 转移 2.7 压力 |
| 1 | inventory_shortage | warehouse_receipt_channel | 30.0 | 经通道 warehouse_receipt_channel 转移 30.0 压力 |
| 2 | inventory_shortage | warehouse_receipt_channel | 21.0 | 经通道 warehouse_receipt_channel 转移 21.0 压力 |
| 3 | inventory_shortage | warehouse_receipt_channel | 21.0 | 经通道 warehouse_receipt_channel 转移 21.0 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | delivery_pressure | delivery_channel | 2.5 | 差异变形: delivery → basis，经通道 delivery_channel，深度 0 |
| 1 | inventory_shortage | warehouse_receipt_channel | 9.0 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |
| 2 | inventory_shortage | warehouse_receipt_channel | 6.3 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |
| 3 | inventory_shortage | warehouse_receipt_channel | 6.3 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_short_001_1 | margin | industrial_short_001 | 3.8 | active | 反馈: industrial_short_001 承压 10.0，杠杆 2.0x，产生保证金差异 6.0 |
| feedback_margin_industrial_short_001_2 | margin | industrial_short_001 | 1.9 | active | 反馈: industrial_short_001 承压 5.0，杠杆 2.0x，产生保证金差异 3.0 |
| feedback_margin_industrial_short_001_3 | margin | industrial_short_001 | 0.9 | active | 反馈: industrial_short_001 承压 2.5，杠杆 2.0x，产生保证金差异 1.5 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| delivery_channel | delivery→basis | 20.0 | 54% | 0.01 | 0.005 | open |
| warehouse_receipt_channel | inventory→delivery | 15.0 | 1440% | 0.14 | 0.144 | open |
| futures_contract_channel | expectation→price | 10.0 | 0% | 0.00 | 0.000 | open |
| exchange_rule_channel | delivery→rule | 50.0 | 0% | 0.00 | 0.000 | open |

## 七、破缺事件

| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |
|---|---|---|---|---|
| 11 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 72.4 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |

## 八、最近稳态

**最终稳态判定**: unstable

**判定理由**: 近3步有3次破缺，系统不稳定

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 52.5 | 4 | 4 | medium | basis_widening |
| 2 | 39.8 | 5 | 4 | medium | basis_widening |
| 3 | 29.6 | 6 | 4 | low | basis_widening |
| 4 | 40.5 | 6 | 4 | medium | basis_widening |
| 5 | 50.1 | 6 | 4 | medium | basis_widening |
| 6 | 58.6 | 6 | 4 | medium | basis_widening |
| 7 | 66.0 | 6 | 4 | high | basis_widening |
| 8 | 72.5 | 6 | 4 | high | basis_widening |
| 9 | 78.3 | 6 | 4 | high | basis_widening |
| 10 | 83.4 | 6 | 4 | high | basis_widening |
| 11 | 51.6 | 6 | 4 | medium | basis_widening |
| 12 | 55.6 | 6 | 4 | medium | basis_widening |
| 13 | 59.0 | 6 | 4 | medium | unstable |
| 14 | 62.0 | 6 | 4 | high | unstable |
| 15 | 64.7 | 6 | 4 | high | unstable |
| 16 | 67.1 | 6 | 4 | high | unstable |
| 17 | 69.1 | 6 | 4 | high | unstable |
| 18 | 71.0 | 6 | 4 | high | unstable |
| 19 | 72.6 | 6 | 4 | high | unstable |
| 20 | 74.0 | 6 | 4 | high | unstable |
| 21 | 75.2 | 6 | 4 | high | unstable |
| 22 | 76.3 | 6 | 4 | high | unstable |
| 23 | 77.3 | 6 | 4 | high | unstable |
| 24 | 78.1 | 6 | 4 | high | unstable |
| 25 | 78.9 | 6 | 4 | high | unstable |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 63.4
- **承压主体**: industrial_short_001(stressed)
- **最近稳态**: unstable
- **变形链事件**: 4 次变形
- **反馈差异**: 3 个（已解决 0）
