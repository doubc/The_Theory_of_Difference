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
| 2 | margin_pressure | margin_clearing_channel | 28.0 | 经通道 margin_clearing_channel 转移 28.0 压力 |
| 3 | margin_pressure | margin_clearing_channel | 12.5 | 经通道 margin_clearing_channel 转移 12.5 压力 |

## 三、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| exchange_rule_channel | rule→rule | 30.0 | 684% | 0.07 | 0.068 | open |
| margin_clearing_channel | margin→liquidity | 10.0 | 1610% | 0.16 | 0.161 | open |
| position_reduction_channel | liquidity→liquidity | 20.0 | 0% | 0.00 | 0.000 | open |

## 四、破缺事件

*无破缺事件*

## 五、最近稳态

**最终稳态判定**: liquidity_recovery

**判定理由**: 总压力0.0<30.0，活跃差异0≤2，流动性恢复稳态

## 六、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 15.8 | 1 | 3 | low | liquidity_recovery |
| 2 | 0.6 | 1 | 3 | low | liquidity_recovery |
| 3 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 4 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 5 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 6 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 7 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 8 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 9 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 10 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 11 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 12 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 13 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 14 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 15 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 16 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 17 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 18 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 19 | 0.0 | 0 | 3 | low | liquidity_recovery |
| 20 | 0.0 | 0 | 3 | low | liquidity_recovery |

## 七、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: 无活跃差异
- **最近稳态**: liquidity_recovery
