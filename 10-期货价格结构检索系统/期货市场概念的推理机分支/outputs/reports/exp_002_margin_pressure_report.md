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
| 1 | margin_hike | margin_clearing_channel | 9.1 | 经通道 margin_clearing_channel 转移 9.1 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | margin_hike | margin_clearing_channel | 7.5 | 差异变形: margin → liquidity，经通道 margin_clearing_channel，深度 0 |

## 四、反馈差异

| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |
|---|---|---|---|---|---|
| feedback_margin_industrial_long_001_1 | margin | industrial_long_001 | 0.0 | resolved | 反馈: industrial_long_001 承压 21.2，杠杆 1.5x，产生保证金差异 9.6 |
| feedback_margin_speculative_fund_001_1 | margin | speculative_fund_001 | 0.0 | resolved | 反馈: speculative_fund_001 承压 14.2，杠杆 5.0x，产生保证金差异 21.4 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| margin_clearing_channel | margin→liquidity | 10.0 | 182% | 0.02 | 0.018 | open |
| basis_channel | inventory→basis | 15.0 | 0% | 0.00 | 0.000 | open |
| position_reduction_channel | liquidity→liquidity | 25.0 | 0% | 0.00 | 0.000 | open |

## 七、破缺事件

*无破缺事件*

## 八、最近稳态

**最终稳态判定**: margin_relief

**判定理由**: 超过100%主体处于压力状态，等待保证金缓解

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 0.0 | 0 | 3 | low | margin_relief |
| 2 | 0.0 | 0 | 3 | low | margin_relief |
| 3 | 0.0 | 0 | 3 | low | margin_relief |
| 4 | 0.0 | 0 | 3 | low | margin_relief |
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
- **变形链事件**: 1 次变形
- **反馈差异**: 2 个（已解决 2）
