# Real_World 实验报告：Feedback-Constraint-Test

**实验ID**: exp_008_feedback_constraint
**运行步数**: 15
**总破缺事件**: 0

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_pressure | inventory | region_A | exchange_delivery | 144.0 | 0.0 | resolved |
| margin_stress | margin | clearing | market | 47.6 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_pressure | warehouse_receipt_channel | 80.0 | 经通道 warehouse_receipt_channel 转移 80.0 压力 |
| 1 | margin_stress | margin_channel | 55.6 | 经通道 margin_channel 转移 55.6 压力 |
| 2 | feedback_margin_normal_speculator_2 | margin_channel | 3.3 | 经通道 margin_channel 转移 3.3 压力 |
| 2 | feedback_margin_high_leverage_speculator_2 | margin_channel | 3.1 | 经通道 margin_channel 转移 3.1 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_pressure | warehouse_receipt_channel | 24.0 | 差异变形: inventory → basis，经通道 warehouse_receipt_channel，深度 0，损耗=56.00 |
| 1 | margin_stress | margin_channel | 24.7 | 差异变形: margin → liquidity，经通道 margin_channel，深度 0，损耗=30.91 |
| 2 | feedback_margin_normal_speculator_2 | margin_channel | 2.6 | 差异变形: margin → liquidity，经通道 margin_channel，深度 1，损耗=0.66 |
| 2 | feedback_margin_high_leverage_speculator_2 | margin_channel | 2.4 | 差异变形: margin → liquidity，经通道 margin_channel，深度 1，损耗=0.71 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_normal_speculator_2 | margin | normal_speculator | 0.0 | resolved | 反馈: normal_speculator 承压 17.5，杠杆 2.0x，衰减后产生保证金差异 5.2 |
| feedback_margin_high_leverage_speculator_2 | margin | high_leverage_speculator | 0.0 | resolved | 反馈: high_leverage_speculator 承压 6.5，杠杆 5.0x，衰减后产生保证金差异 4.9 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| warehouse_receipt_channel | inventory→delivery | 15.0 | 1600% | 0.16 | 0.160 | open |
| margin_channel | margin→liquidity | 10.0 | 1240% | 0.12 | 0.124 | open |

## 七、破缺事件

*无破缺事件*

## 八、最近稳态

**最终稳态判定**: unstable

**判定理由**: 总压力53.7，无明显稳定路径，需继续观察

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 62.7 | 3 | 2 | high | unstable |
| 2 | 53.7 | 4 | 2 | medium | unstable |
| 3 | 53.7 | 4 | 2 | medium | unstable |
| 4 | 53.7 | 4 | 2 | medium | unstable |
| 5 | 53.7 | 4 | 2 | medium | unstable |
| 6 | 53.7 | 4 | 2 | medium | unstable |
| 7 | 53.7 | 4 | 2 | medium | unstable |
| 8 | 53.7 | 4 | 2 | medium | unstable |
| 9 | 53.7 | 4 | 2 | medium | unstable |
| 10 | 53.7 | 4 | 2 | medium | unstable |
| 11 | 53.7 | 4 | 2 | medium | unstable |
| 12 | 53.7 | 4 | 2 | medium | unstable |
| 13 | 53.7 | 4 | 2 | medium | unstable |
| 14 | 53.7 | 4 | 2 | medium | unstable |
| 15 | 53.7 | 4 | 2 | medium | unstable |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: transform_margin_to_liquidity_0_margin_stress（liquidity），压力 24.7
- **承压主体**: high_leverage_speculator(stressed)
- **最近稳态**: unstable
- **变形链事件**: 4 次变形
- **反馈差异**: 2 个（已解决 2）
