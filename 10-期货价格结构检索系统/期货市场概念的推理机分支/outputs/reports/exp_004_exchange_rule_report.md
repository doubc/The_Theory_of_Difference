# Real_World 实验报告：Exchange-Rule-World

**实验ID**: exp_004_exchange_rule
**运行步数**: 20
**总破缺事件**: 0

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| rule_change | rule | exchange | market | 34.2 | 0.0 | resolved |
| margin_pressure | margin | exchange | market | 42.1 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | rule_change | exchange_rule_channel | 34.2 | 经通道 exchange_rule_channel 转移 34.2 压力 |
| 1 | margin_pressure | margin_clearing_channel | 40.0 | 经通道 margin_clearing_channel 转移 40.0 压力 |
| 1 | transform_margin_to_liquidity_0_margin_pressure | position_reduction_channel | 12.0 | 经通道 position_reduction_channel 转移 12.0 压力 |
| 2 | margin_pressure | margin_clearing_channel | 28.0 | 经通道 margin_clearing_channel 转移 28.0 压力 |
| 2 | transform_margin_to_liquidity_0_margin_pressure | position_reduction_channel | 8.4 | 经通道 position_reduction_channel 转移 8.4 压力 |
| 3 | margin_pressure | margin_clearing_channel | 12.5 | 经通道 margin_clearing_channel 转移 12.5 压力 |
| 3 | feedback_margin_speculative_fund_001_2 | margin_clearing_channel | 5.6 | 经通道 margin_clearing_channel 转移 5.6 压力 |
| 3 | feedback_margin_industrial_long_001_2 | margin_clearing_channel | 2.1 | 经通道 margin_clearing_channel 转移 2.1 压力 |
| 3 | transform_margin_to_liquidity_0_margin_pressure | position_reduction_channel | 4.8 | 经通道 position_reduction_channel 转移 4.8 压力 |
| 3 | transform_margin_to_liquidity_0_feedback_margin_speculative_fund_001_2 | position_reduction_channel | 1.7 | 经通道 position_reduction_channel 转移 1.7 压力 |
| 3 | transform_margin_to_liquidity_0_feedback_margin_industrial_long_001_2 | position_reduction_channel | 0.6 | 经通道 position_reduction_channel 转移 0.6 压力 |
| 3 | feedback_margin_industrial_long_001_3 | margin_clearing_channel | 3.5 | 经通道 margin_clearing_channel 转移 3.5 压力 |
| 3 | feedback_margin_industrial_long_001_3 | margin_clearing_channel | 1.6 | 经通道 margin_clearing_channel 转移 1.6 压力 |
| 3 | feedback_margin_industrial_long_001_3 | margin_clearing_channel | 0.6 | 经通道 margin_clearing_channel 转移 0.6 压力 |
| 3 | transform_margin_to_liquidity_1_feedback_margin_industrial_long_001_3 | position_reduction_channel | 1.1 | 经通道 position_reduction_channel 转移 1.1 压力 |
| 3 | transform_margin_to_liquidity_1_feedback_margin_industrial_long_001_3 | position_reduction_channel | 0.5 | 经通道 position_reduction_channel 转移 0.5 压力 |
| 3 | transform_margin_to_liquidity_1_feedback_margin_industrial_long_001_3 | position_reduction_channel | 0.2 | 经通道 position_reduction_channel 转移 0.2 压力 |
| 3 | feedback_margin_speculative_fund_001_3 | margin_clearing_channel | 2.1 | 经通道 margin_clearing_channel 转移 2.1 压力 |
| 3 | transform_margin_to_liquidity_2_feedback_margin_speculative_fund_001_3 | position_reduction_channel | 0.6 | 经通道 position_reduction_channel 转移 0.6 压力 |
| 4 | feedback_margin_industrial_long_001_3 | margin_clearing_channel | 0.9 | 经通道 margin_clearing_channel 转移 0.9 压力 |
| 4 | feedback_margin_speculative_fund_001_3 | margin_clearing_channel | 0.4 | 经通道 margin_clearing_channel 转移 0.4 压力 |
| 4 | transform_margin_to_liquidity_0_feedback_margin_industrial_long_001_3 | position_reduction_channel | 0.6 | 经通道 position_reduction_channel 转移 0.6 压力 |
| 4 | transform_margin_to_liquidity_0_feedback_margin_speculative_fund_001_3 | position_reduction_channel | 0.3 | 经通道 position_reduction_channel 转移 0.3 压力 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.3 | 经通道 margin_clearing_channel 转移 0.3 压力 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.3 | 经通道 margin_clearing_channel 转移 0.3 压力 |
| 4 | transform_margin_to_liquidity_1_feedback_margin_industrial_long_001_4 | position_reduction_channel | 0.2 | 经通道 position_reduction_channel 转移 0.2 压力 |
| 4 | transform_margin_to_liquidity_1_feedback_margin_speculative_fund_001_4 | position_reduction_channel | 0.2 | 经通道 position_reduction_channel 转移 0.2 压力 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.4 | 经通道 margin_clearing_channel 转移 0.4 压力 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.2 | 经通道 margin_clearing_channel 转移 0.2 压力 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.1 | 经通道 margin_clearing_channel 转移 0.1 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | margin_pressure | margin_clearing_channel | 12.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 2 | margin_pressure | margin_clearing_channel | 8.4 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 3 | margin_pressure | margin_clearing_channel | 4.8 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 3 | feedback_margin_speculative_fund_001_2 | margin_clearing_channel | 1.7 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 3 | feedback_margin_industrial_long_001_2 | margin_clearing_channel | 0.6 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 3 | feedback_margin_industrial_long_001_3 | margin_clearing_channel | 1.1 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 1 |
| 3 | feedback_margin_industrial_long_001_3 | margin_clearing_channel | 0.5 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 1 |
| 3 | feedback_margin_industrial_long_001_3 | margin_clearing_channel | 0.2 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 1 |
| 3 | feedback_margin_speculative_fund_001_3 | margin_clearing_channel | 0.6 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 2 |
| 4 | feedback_margin_industrial_long_001_3 | margin_clearing_channel | 0.6 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 4 | feedback_margin_speculative_fund_001_3 | margin_clearing_channel | 0.3 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.2 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 1 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.2 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 1 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.3 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 2 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.1 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 2 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 2 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 2 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.1 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 3 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.1 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 3 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.1 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 3 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.1 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 3 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 3 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 3 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.1 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 4 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 4 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 4 |
| 4 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 4 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 4 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 4 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 4 |
| 4 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 4 |
| 5 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 5 | feedback_margin_speculative_fund_001_5 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 1 |
| 5 | feedback_margin_speculative_fund_001_5 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 1 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_speculative_fund_001_2 | margin | speculative_fund_001 | 0.0 | resolved | 反馈: speculative_fund_001 承压 8.4，杠杆 3.5x，产生保证金差异 8.8 |
| feedback_margin_industrial_long_001_2 | margin | industrial_long_001 | 0.0 | resolved | 反馈: industrial_long_001 承压 7.5，杠杆 1.5x，产生保证金差异 3.4 |
| feedback_margin_industrial_long_001_3 | margin | industrial_long_001 | 0.0 | resolved | 反馈: industrial_long_001 承压 3.2，杠杆 1.5x，产生保证金差异 1.4 |
| feedback_margin_speculative_fund_001_3 | margin | speculative_fund_001 | 0.0 | resolved | 反馈: speculative_fund_001 承压 0.6，杠杆 3.5x，产生保证金差异 0.7 |
| feedback_margin_industrial_long_001_4 | margin | industrial_long_001 | 0.0 | resolved | 反馈: industrial_long_001 承压 0.0，杠杆 1.5x，产生保证金差异 0.0 |
| feedback_margin_speculative_fund_001_4 | margin | speculative_fund_001 | 0.0 | resolved | 反馈: speculative_fund_001 承压 0.0，杠杆 3.5x，产生保证金差异 0.0 |
| feedback_margin_industrial_long_001_5 | margin | industrial_long_001 | 0.0 | resolved | 反馈: industrial_long_001 承压 0.0，杠杆 1.5x，产生保证金差异 0.0 |
| feedback_margin_speculative_fund_001_5 | margin | speculative_fund_001 | 0.0 | resolved | 反馈: speculative_fund_001 承压 0.0，杠杆 3.5x，产生保证金差异 0.0 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| exchange_rule_channel | rule→rule | 30.0 | 684% | 0.07 | 0.068 | open |
| margin_clearing_channel | margin→liquidity | 10.0 | 1993% | 0.20 | 0.199 | open |
| position_reduction_channel | liquidity→liquidity | 20.0 | 640% | 0.06 | 0.064 | open |

## 七、破缺事件

*无破缺事件*

## 八、最近稳态

**最终稳态判定**: margin_relief

**判定理由**: 超过67%主体处于压力状态，等待保证金缓解

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 15.8 | 1 | 3 | low | liquidity_recovery |
| 2 | 8.3 | 3 | 3 | low | unstable |
| 3 | 1.3 | 2 | 3 | low | margin_relief |
| 4 | 0.1 | 4 | 3 | low | margin_relief |
| 5 | 0.0 | 0 | 3 | low | margin_relief |
| 6 | 0.0 | 0 | 3 | low | margin_relief |
| 7 | 0.0 | 0 | 3 | low | margin_relief |
| 8 | 0.0 | 0 | 3 | low | margin_relief |
| 9 | 0.0 | 0 | 3 | low | margin_relief |
| 10 | 0.0 | 0 | 3 | low | margin_relief |
| 11 | 0.0 | 0 | 3 | low | margin_relief |
| 12 | 0.0 | 0 | 3 | low | margin_relief |
| 13 | 0.0 | 0 | 3 | low | margin_relief |
| 14 | 0.0 | 0 | 3 | low | margin_relief |
| 15 | 0.0 | 0 | 3 | low | margin_relief |
| 16 | 0.0 | 0 | 3 | low | margin_relief |
| 17 | 0.0 | 0 | 3 | low | margin_relief |
| 18 | 0.0 | 0 | 3 | low | margin_relief |
| 19 | 0.0 | 0 | 3 | low | margin_relief |
| 20 | 0.0 | 0 | 3 | low | margin_relief |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: 无活跃差异
- **承压主体**: speculative_fund_001(stressed), industrial_long_001(stressed)
- **最近稳态**: margin_relief
- **变形链事件**: 34 次变形
- **反馈差异**: 8 个（已解决 8）
