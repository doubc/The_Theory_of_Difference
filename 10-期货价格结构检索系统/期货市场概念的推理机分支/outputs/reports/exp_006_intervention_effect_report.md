# Real_World 实验报告：Intervention-Test-World

**实验ID**: exp_006_intervention_effect
**运行步数**: 40
**总破缺事件**: 5

## 一、输入差异

| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |
|---|---|---|---|---|---|---|
| inventory_shortage | inventory | region_A | exchange_delivery | 85.5 | 81.8 | active |
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
| feedback_margin_speculative_long_001_6 | margin | speculative_long_001 | 0.0 | resolved | 反馈: speculative_long_001 承压 4.7，杠杆 2.0x，产生保证金差异 2.8 |

## 五、干预记录

| 时间 | 类型 | 量 | 说明 |
|---|---|---|---|
| 5 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 5 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 5 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(22.6), speculator_002(16.4) |
| 5 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |
| 8 | exchange_intervene | 0.30 | 交易所降低差异生成率 30%，影响: expectation_bullish |
| 8 | intervention_side_effect | 10.50 | 干预副作用: 限仓 → 预期差异 10.5 |
| 8 | exchange_intervene | 0.30 | 交易所释放承接力 30%，影响: speculative_long_001(17.8), speculator_002(11.5) |
| 8 | intervention_side_effect | 12.00 | 干预副作用: 释放承接力 → 流动性差异 12.0 |

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
| 6 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 102.6 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 10 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 100.4 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 14 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 90.2 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 20 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 91.6 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |
| 29 | accumulation_overflow | inventory_shortage | 1.00 | 差异 inventory_shortage 压力 93.5 超过阈值 90.0，触发 accumulation_overflow，严重度 1.00 |

## 八、最近稳态

**最终稳态判定**: unstable

**判定理由**: 近3步有15次破缺，系统不稳定

## 九、状态演变

| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |
|---|---|---|---|---|---|
| 1 | 53.5 | 1 | 7 | medium | margin_relief |
| 2 | 42.3 | 1 | 7 | medium | margin_relief |
| 3 | 58.6 | 1 | 7 | medium | margin_relief |
| 4 | 74.0 | 1 | 7 | high | margin_relief |
| 5 | 98.5 | 3 | 7 | critical | margin_relief |
| 6 | 56.4 | 2 | 7 | medium | margin_relief |
| 7 | 69.6 | 2 | 7 | high | margin_relief |
| 8 | 92.0 | 4 | 7 | critical | unstable |
| 9 | 99.3 | 3 | 7 | critical | unstable |
| 10 | 60.4 | 3 | 7 | high | unstable |
| 11 | 71.2 | 3 | 7 | high | unstable |
| 12 | 81.4 | 3 | 7 | high | unstable |
| 13 | 91.1 | 3 | 7 | critical | unstable |
| 14 | 55.3 | 3 | 7 | medium | unstable |
| 15 | 64.1 | 3 | 7 | high | unstable |
| 16 | 72.4 | 3 | 7 | high | unstable |
| 17 | 80.3 | 3 | 7 | high | unstable |
| 18 | 87.9 | 3 | 7 | high | unstable |
| 19 | 95.0 | 3 | 7 | critical | unstable |
| 20 | 56.0 | 3 | 7 | medium | unstable |
| 21 | 62.5 | 3 | 7 | high | unstable |
| 22 | 68.6 | 3 | 7 | high | unstable |
| 23 | 74.4 | 3 | 7 | high | unstable |
| 24 | 79.9 | 3 | 7 | high | unstable |
| 25 | 85.2 | 3 | 7 | high | unstable |
| 26 | 90.2 | 3 | 7 | critical | unstable |
| 27 | 94.9 | 3 | 7 | critical | unstable |
| 28 | 99.4 | 3 | 7 | critical | unstable |
| 29 | 57.0 | 3 | 7 | medium | unstable |
| 30 | 61.0 | 3 | 7 | high | unstable |
| 31 | 64.9 | 3 | 7 | high | unstable |
| 32 | 68.6 | 3 | 7 | high | unstable |
| 33 | 72.0 | 3 | 7 | high | unstable |
| 34 | 75.4 | 3 | 7 | high | unstable |
| 35 | 78.5 | 3 | 7 | high | unstable |
| 36 | 81.5 | 3 | 7 | high | unstable |
| 37 | 84.3 | 3 | 7 | high | unstable |
| 38 | 87.0 | 3 | 7 | high | unstable |
| 39 | 89.6 | 3 | 7 | high | unstable |
| 40 | 92.0 | 3 | 7 | critical | unstable |

## 十、干预效果分析

### 破缺间隔统计
- **干预前平均破缺间隔**: 4.0 步
- **干预后平均破缺间隔**: 9.0 步
- **延长倍数**: 2.25 倍

### 结论修正
干预措施确实产生了积极效果，破缺间隔从4步延长至9步，表明交易所的干预能够有效延缓系统性压力的积累。然而，需要注意的是：

1. **效果有限性**: 虽然破缺间隔延长了2.25倍，但系统仍然保持不稳定状态
2. **副作用明显**: 每次干预都产生约10.5的压力转移副作用，且释放承接力会转化为流动性差异
3. **可持续性差**: 系统在40步内仍发生5次破缺，说明单次或周期性干预不足以建立稳定的市场结构

**最终结论**: 干预措施在短期内有效延缓了系统性危机的爆发，但不能根本解决结构性问题。需要配合其他机制（如容量扩容、通道优化）才能实现长期稳定。

## 十一、结构判断

> **注意**: 本报告为差异结构分析，不构成任何交易建议。

- **主导差异**: inventory_shortage（inventory），压力 81.8
- **承压主体**: industrial_short_001(stressed), speculative_long_001(stressed)
- **最近稳态**: unstable
- **变形链事件**: 3 次变形
- **反馈差异**: 4 个（已解决 4）
