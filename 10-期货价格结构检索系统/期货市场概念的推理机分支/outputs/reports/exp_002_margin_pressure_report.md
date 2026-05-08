# Real_World 实验报告：Margin-Pressure-World

**实验ID**: exp_002_margin_pressure
**运行步数**: 20
**总破缺事件**: 0

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| margin_hike | margin | exchange | market | 64.1 | 0.0 | resolved |
| inventory_gap | inventory | region_A | region_B | 28.0 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | margin_hike | margin_clearing_channel | 50.0 | 经通道 margin_clearing_channel 转移 50.0 压力 |
| 1 | inventory_gap | basis_channel | 35.5 | 经通道 basis_channel 转移 35.5 压力 |
| 1 | transform_margin_to_liquidity_0_margin_hike | position_reduction_channel | 15.0 | 经通道 position_reduction_channel 转移 15.0 压力 |
| 2 | margin_hike | margin_clearing_channel | 35.0 | 经通道 margin_clearing_channel 转移 35.0 压力 |
| 2 | transform_margin_to_liquidity_0_margin_hike | position_reduction_channel | 10.5 | 经通道 position_reduction_channel 转移 10.5 压力 |
| 3 | margin_hike | margin_clearing_channel | 35.0 | 经通道 margin_clearing_channel 转移 35.0 压力 |
| 3 | transform_margin_to_liquidity_0_margin_hike | position_reduction_channel | 10.5 | 经通道 position_reduction_channel 转移 10.5 压力 |
| 4 | margin_hike | margin_clearing_channel | 27.6 | 经通道 margin_clearing_channel 转移 27.6 压力 |
| 4 | feedback_margin_industrial_long_001_1 | margin_clearing_channel | 6.0 | 经通道 margin_clearing_channel 转移 6.0 压力 |
| 4 | feedback_margin_speculative_fund_001_1 | margin_clearing_channel | 1.4 | 经通道 margin_clearing_channel 转移 1.4 压力 |
| 4 | transform_margin_to_liquidity_0_feedback_margin_industrial_long_001_1 | position_reduction_channel | 1.8 | 经通道 position_reduction_channel 转移 1.8 压力 |
| 4 | transform_margin_to_liquidity_0_feedback_margin_speculative_fund_001_1 | position_reduction_channel | 0.4 | 经通道 position_reduction_channel 转移 0.4 压力 |
| 5 | feedback_margin_industrial_long_001_2 | margin_clearing_channel | 3.0 | 经通道 margin_clearing_channel 转移 3.0 压力 |
| 5 | feedback_margin_speculative_fund_001_2 | margin_clearing_channel | 2.5 | 经通道 margin_clearing_channel 转移 2.5 压力 |
| 5 | feedback_margin_industrial_long_001_3 | margin_clearing_channel | 1.5 | 经通道 margin_clearing_channel 转移 1.5 压力 |
| 5 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.2 | 经通道 margin_clearing_channel 转移 0.2 压力 |
| 5 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.2 | 经通道 margin_clearing_channel 转移 0.2 压力 |
| 5 | transform_margin_to_liquidity_0_feedback_margin_industrial_long_001_4 | position_reduction_channel | 0.1 | 经通道 position_reduction_channel 转移 0.1 压力 |
| 5 | transform_margin_to_liquidity_0_feedback_margin_speculative_fund_001_4 | position_reduction_channel | 0.1 | 经通道 position_reduction_channel 转移 0.1 压力 |
| 5 | feedback_margin_industrial_long_001_5 | margin_clearing_channel | 0.1 | 经通道 margin_clearing_channel 转移 0.1 压力 |
| 5 | feedback_margin_industrial_long_001_5 | margin_clearing_channel | 0.0 | 经通道 margin_clearing_channel 转移 0.0 压力 |
| 5 | feedback_margin_industrial_long_001_5 | margin_clearing_channel | 0.0 | 经通道 margin_clearing_channel 转移 0.0 压力 |
| 5 | feedback_margin_industrial_long_001_5 | margin_clearing_channel | 0.0 | 经通道 margin_clearing_channel 转移 0.0 压力 |
| 5 | feedback_margin_speculative_fund_001_5 | margin_clearing_channel | 0.0 | 经通道 margin_clearing_channel 转移 0.0 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | margin_hike | margin_clearing_channel | 15.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 1 | inventory_gap | basis_channel | 19.7 | 差异变形: inventory → basis，经通道 basis_channel，深度 0 |
| 2 | margin_hike | margin_clearing_channel | 10.5 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 3 | margin_hike | margin_clearing_channel | 10.5 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 4 | margin_hike | margin_clearing_channel | 8.3 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 4 | feedback_margin_industrial_long_001_1 | margin_clearing_channel | 1.8 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 4 | feedback_margin_speculative_fund_001_1 | margin_clearing_channel | 0.4 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 5 | feedback_margin_industrial_long_001_2 | margin_clearing_channel | 1.9 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 5 | feedback_margin_speculative_fund_001_2 | margin_clearing_channel | 1.4 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 5 | feedback_margin_industrial_long_001_3 | margin_clearing_channel | 0.8 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 5 | feedback_margin_industrial_long_001_4 | margin_clearing_channel | 0.1 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 5 | feedback_margin_speculative_fund_001_4 | margin_clearing_channel | 0.1 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |
| 5 | feedback_margin_industrial_long_001_5 | margin_clearing_channel | 0.1 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 1 |
| 5 | feedback_margin_industrial_long_001_5 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 1 |
| 5 | feedback_margin_industrial_long_001_5 | margin_clearing_channel | 0.0 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 1 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_long_001_1 | margin | industrial_long_001 | 0.0 | resolved | 反馈: industrial_long_001 承压 21.2，杠杆 1.5x，产生保证金差异 9.6 |
| feedback_margin_speculative_fund_001_1 | margin | speculative_fund_001 | 8.4 | active | 反馈: speculative_fund_001 承压 10.4，杠杆 5.0x，产生保证金差异 15.6 |
| feedback_margin_industrial_long_001_2 | margin | industrial_long_001 | 0.0 | resolved | 反馈: industrial_long_001 承压 10.6，杠杆 1.5x，产生保证金差异 4.8 |
| feedback_margin_speculative_fund_001_2 | margin | speculative_fund_001 | 0.0 | resolved | 反馈: speculative_fund_001 承压 2.6，杠杆 5.0x，产生保证金差异 3.9 |
| feedback_margin_industrial_long_001_3 | margin | industrial_long_001 | 0.0 | resolved | 反馈: industrial_long_001 承压 5.3，杠杆 1.5x，产生保证金差异 2.4 |
| feedback_margin_speculative_fund_001_3 | margin | speculative_fund_001 | 1.2 | active | 反馈: speculative_fund_001 承压 1.3，杠杆 5.0x，产生保证金差异 1.9 |
| feedback_margin_industrial_long_001_4 | margin | industrial_long_001 | 0.0 | resolved | 反馈: industrial_long_001 承压 0.7，杠杆 1.5x，产生保证金差异 0.3 |
| feedback_margin_speculative_fund_001_4 | margin | speculative_fund_001 | 0.0 | resolved | 反馈: speculative_fund_001 承压 0.2，杠杆 5.0x，产生保证金差异 0.2 |
| feedback_margin_industrial_long_001_5 | margin | industrial_long_001 | 0.0 | resolved | 反馈: industrial_long_001 承压 0.0，杠杆 1.5x，产生保证金差异 0.0 |
| feedback_margin_speculative_fund_001_5 | margin | speculative_fund_001 | 0.0 | resolved | 反馈: speculative_fund_001 承压 0.0，杠杆 5.0x，产生保证金差异 0.0 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| margin_clearing_channel | margin→liquidity | 10.0 | 3250% | 0.32 | 0.325 | open |
| basis_channel | inventory→basis | 15.0 | 710% | 0.07 | 0.071 | open |
| position_reduction_channel | liquidity→liquidity | 25.0 | 768% | 0.08 | 0.077 | open |

## 七、破缺事件

*无破缺事件*

## 八、最近稳态

**最终稳态判定**: margin_relief

**判定理由**: 超过100%主体处于压力状态，等待保证金缓解

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 72.2 | 4 | 3 | high | unstable |
| 2 | 64.0 | 6 | 3 | high | margin_relief |
| 3 | 52.1 | 8 | 3 | medium | margin_relief |
| 4 | 45.0 | 9 | 3 | medium | margin_relief |
| 5 | 41.8 | 8 | 3 | medium | margin_relief |
| 6 | 41.8 | 8 | 3 | medium | margin_relief |
| 7 | 41.8 | 8 | 3 | medium | margin_relief |
| 8 | 41.8 | 8 | 3 | medium | margin_relief |
| 9 | 41.8 | 8 | 3 | medium | margin_relief |
| 10 | 41.8 | 8 | 3 | medium | margin_relief |
| 11 | 41.8 | 8 | 3 | medium | margin_relief |
| 12 | 41.8 | 8 | 3 | medium | margin_relief |
| 13 | 41.8 | 8 | 3 | medium | margin_relief |
| 14 | 41.8 | 8 | 3 | medium | margin_relief |
| 15 | 41.8 | 8 | 3 | medium | margin_relief |
| 16 | 41.8 | 8 | 3 | medium | margin_relief |
| 17 | 41.8 | 8 | 3 | medium | margin_relief |
| 18 | 41.8 | 8 | 3 | medium | margin_relief |
| 19 | 41.8 | 8 | 3 | medium | margin_relief |
| 20 | 41.8 | 8 | 3 | medium | margin_relief |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: transform_inventory_to_basis_0_inventory_gap（basis），压力 19.7
- **承压主体**: speculative_fund_001(stressed), industrial_long_001(stressed)
- **最近稳态**: margin_relief
- **变形链事件**: 15 次变形
- **反馈差异**: 10 个（已解决 8）
