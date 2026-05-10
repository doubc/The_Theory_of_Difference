# Real_World 实验报告：Near-Month-Squeeze-World

**实验ID**: exp_003_near_month_squeeze
**运行步数**: 20
**总破缺事件**: 34

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| delivery_pressure | delivery | near_month | exchange | 280.8 | 282.2 | active |
| inventory_shortage | inventory | region_A | exchange_delivery | 292.6 | 236.8 | active |
| expectation_bullish | expectation | market | price | 35.7 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | delivery_pressure | delivery_channel | 40.0 | 经通道 delivery_channel 转移 40.0 压力 |
| 1 | inventory_shortage | warehouse_receipt_channel | 30.0 | 经通道 warehouse_receipt_channel 转移 30.0 压力 |
| 1 | expectation_bullish | futures_contract_channel | 41.7 | 经通道 futures_contract_channel 转移 41.7 压力 |
| 2 | delivery_pressure | delivery_channel | 28.0 | 经通道 delivery_channel 转移 28.0 压力 |
| 3 | delivery_pressure | delivery_channel | 28.0 | 经通道 delivery_channel 转移 28.0 压力 |
| 4 | delivery_pressure | delivery_channel | 28.0 | 经通道 delivery_channel 转移 28.0 压力 |
| 5 | delivery_pressure | delivery_channel | 28.0 | 经通道 delivery_channel 转移 28.0 压力 |
| 6 | delivery_pressure | delivery_channel | 27.8 | 经通道 delivery_channel 转移 27.8 压力 |

## 三、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| delivery_channel | delivery→basis | 20.0 | 3597% | 0.36 | 0.360 | open |
| warehouse_receipt_channel | inventory→delivery | 15.0 | 600% | 0.06 | 0.060 | open |
| futures_contract_channel | expectation→price | 10.0 | 834% | 0.08 | 0.083 | open |
| exchange_rule_channel | delivery→rule | 50.0 | 0% | 0.00 | 0.000 | open |

## 四、破缺事件

| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |
|---|---|---|---|---|
| 1 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 72.7 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 2 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 122.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 3 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 149.2 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 4 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 174.8 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 5 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 199.3 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 6 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 223.0 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 7 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 78.2 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 7 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 245.9 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 8 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 114.9 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 8 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 268.1 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 9 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 150.7 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 9 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 289.6 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 10 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 186.1 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 10 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 310.3 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 11 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 221.6 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 11 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 330.2 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 12 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 257.3 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 12 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 349.4 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 13 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 293.4 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 13 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 367.8 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 14 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 330.1 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 14 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 385.4 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 15 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 367.5 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 15 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 402.1 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 16 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 405.6 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 16 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 418.1 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 17 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 444.4 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 17 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 433.2 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 18 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 483.8 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 18 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 447.4 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 19 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 523.9 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 19 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 460.9 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |
| 20 | delivery_failure | delivery_pressure | 1.00 | 差异 delivery_pressure 压力 564.5 超过阈值 50.0，触发 delivery_failure，严重度 1.00 |
| 20 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 473.5 超过阈值 70.0，触发 accumulation_overflow，严重度 1.00 |

## 五、最近稳态

**最终稳态判定**: unstable

**判定理由**: 近3步有96次破缺，系统不稳定

## 六、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 83.6 | 2 | 4 | high | unstable |
| 2 | 98.6 | 2 | 4 | critical | unstable |
| 3 | 110.6 | 2 | 4 | critical | unstable |
| 4 | 119.9 | 2 | 4 | critical | unstable |
| 5 | 126.7 | 2 | 4 | critical | unstable |
| 6 | 131.5 | 2 | 4 | critical | unstable |
| 7 | 162.1 | 2 | 4 | critical | unstable |
| 8 | 191.5 | 2 | 4 | critical | unstable |
| 9 | 220.1 | 2 | 4 | critical | unstable |
| 10 | 248.2 | 2 | 4 | critical | unstable |
| 11 | 275.9 | 2 | 4 | critical | unstable |
| 12 | 303.3 | 2 | 4 | critical | unstable |
| 13 | 330.6 | 2 | 4 | critical | unstable |
| 14 | 357.8 | 2 | 4 | critical | unstable |
| 15 | 384.8 | 2 | 4 | critical | unstable |
| 16 | 411.8 | 2 | 4 | critical | unstable |
| 17 | 438.8 | 2 | 4 | critical | unstable |
| 18 | 465.6 | 2 | 4 | critical | unstable |
| 19 | 492.4 | 2 | 4 | critical | unstable |
| 20 | 519.0 | 2 | 4 | critical | unstable |

## 七、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: delivery_pressure（delivery），压力 282.2
- **最近稳态**: unstable
