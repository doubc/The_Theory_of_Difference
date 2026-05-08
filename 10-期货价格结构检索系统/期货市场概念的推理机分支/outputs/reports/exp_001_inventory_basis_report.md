# Real_World 实验报告：RW-Copper-World

**实验ID**: exp_001_inventory_basis
**运行步数**: 15
**总破缺事件**: 0

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_gap_A_B | inventory | region_A | region_B | 61.2 | 0.0 | resolved |

## 二、主要转移路径

| 时间 | 差异ID | 通道ID | 转移量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_gap_A_B | basis_channel | 61.2 | 经通道 basis_channel 转移 61.2 压力 |
| 1 | transform_inventory_to_basis_0_inventory_gap_A_B | basis_to_price_channel | 23.7 | 经通道 basis_to_price_channel 转移 23.7 压力 |

## 三、变形链

| 时间 | 源差异 | 通道 | 变形量 | 说明 |
|---|---|---|---|---|
| 1 | inventory_gap_A_B | basis_channel | 23.7 | 差异变形: inventory → basis，经通道 basis_channel，深度 0 |
| 1 | transform_inventory_to_basis_0_inventory_gap_A_B | basis_to_price_channel | 16.7 | 差异变形: basis → price，经通道 basis_to_price_channel，深度 1 |

## 六、通道状态

| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |
|---|---|---|---|---|---|---|
| basis_channel | inventory→basis | 15.0 | 1224% | 0.12 | 0.122 | open |
| futures_contract_channel | inventory→price | 25.0 | 0% | 0.00 | 0.000 | open |
| basis_to_price_channel | basis→price | 12.0 | 475% | 0.05 | 0.047 | open |
| storage_channel | inventory→inventory | 30.0 | 0% | 0.00 | 0.000 | open |

## 七、破缺事件

*无破缺事件*

## 八、最近稳态

**最终稳态判定**: liquidity_recovery

**判定理由**: 总压力16.7<30.0，活跃差异1≤2，流动性恢复稳态

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 2 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 3 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 4 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 5 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 6 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 7 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 8 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 9 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 10 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 11 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 12 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 13 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 14 | 16.7 | 1 | 4 | low | liquidity_recovery |
| 15 | 16.7 | 1 | 4 | low | liquidity_recovery |

## 十、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: transform_basis_to_price_1_transform_inventory_to_basis_0_inventory_gap_A_B（price），压力 16.7
- **最近稳态**: liquidity_recovery
- **变形链事件**: 2 次变形
