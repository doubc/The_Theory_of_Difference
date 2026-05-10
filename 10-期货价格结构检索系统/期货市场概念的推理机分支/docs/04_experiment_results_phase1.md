# Phase 1 实验结果与分析

日期：2026-05-07
版本：V0.2（含 recurrent 机制）

---

## 一、缺陷修复验证

| 缺陷 | 修复 | 验证 |
|---|---|---|
| 通道使用率>100% | reset_step 改为锁定感知释放+硬保护 | ✅ capacity_usage 属性已加，硬保护已加。但报告中仍有 3597%，原因是 used_capacity 累积（通道每步转移量大），需进一步修复 |
| 稳态标签缺失 | 调整 runner 步骤顺序：快照→稳态判定 | ✅ 每步都有稳态标签 |
| Entity 未参与承接 | runner._run_transfers 增加 Entity 承接检查 | ✅ Entity 参与，报告中有 entity_absorb 事件 |

**未完全修复**：通道使用率显示问题。根因是 capacity_usage 使用 used/capacity，而 used 在多步转移中累积远超 capacity。这不是 bug——通道容量在每步部分恢复，但转移量可能很大。需要区分「瞬时使用率」和「累计通过量」。

---

## 二、实验结果

### exp_002：保证金压力降低承接力

**配置**：
- 差异：margin_hike（recurrent, rate=0.3, decay=0.95）+ inventory_gap（recurrent, rate=0.15, decay=0.9）
- 通道：margin_clearing（capacity=50）+ basis（capacity=80）+ position_reduction（capacity=40）
- 主体：speculative_fund（leverage=5）+ industrial_long（leverage=1.5）

**结果**：
- 4步内差异全部转移完毕
- 稳态：margin_relief（主体受压后等待保证金缓解）
- 无破缺事件
- 问题：recurrent_rate 产生的压力不够，通道容量仍然充足

**分析**：
- 保证金差异每步生成 75×0.3=22.5 压力，衰减 5%/步
- margin_clearing_channel capacity=50，足够吸收每步生成量
- 需要降低通道容量或提高 recurrent_rate 才能产生积累和破缺

### exp_003：近月逼仓 ✅ 核心实验

**配置**：
- 差异：delivery_pressure（recurrent, rate=0.35, decay=0.92）+ inventory_shortage（recurrent, rate=0.2, decay=0.88）+ expectation_bullish
- 通道：delivery（capacity=40）+ warehouse_receipt（capacity=30）+ futures_contract（capacity=100）+ exchange_rule（capacity=80）
- 主体：industrial_short + speculative_long + exchange

**结果**：
- **34次破缺事件**：delivery_failure + accumulation_overflow 交替出现
- 差异压力持续积累：delivery 280→565，inventory 293→474
- 稳态：unstable（近3步96次破缺）
- 通道锁定度 0.36（路径依赖形成中）

**分析**：
- 交割通道 capacity=40，但差异每步生成 90×0.35=31.5，加上积累，通道严重不足
- 破缺后仅释放 50% 压力，但 recurrent 机制继续生成新压力
- **这正是差异论所描述的「差异积累→破缺→新差异继续生成」的循环**
- 缺少交易所干预机制——当市场持续破缺时，交易所应介入

### exp_004：交易所规则调整

**配置**：
- 差异：rule_change + margin_pressure（recurrent, rate=0.25, decay=0.93）
- 通道：exchange_rule（capacity=60）+ margin_clearing（capacity=40）+ position_reduction（capacity=50）
- 主体：exchange + speculative_fund + industrial_long

**结果**：
- 3步内差异全部转移完毕
- 稳态：liquidity_recovery
- 无破缺事件

**分析**：
- 交易所作为高容量承接体（capacity=200），直接吸收了规则差异
- margin_pressure 的 recurrent 生成量 55×0.25=13.75/步，通道 capacity=40 足够
- 需要更强的 recurrent 压力或更低的通道容量

---

## 三、关键发现

1. **recurrent 机制有效**：差异持续生成是让玩具世界产生动态行为的必要条件。没有 recurrent，差异2-3步内就被通道完全吸收。

2. **通道容量是关键瓶颈**：当 recurrent_rate 高、通道容量低时（exp_003），差异会持续积累并触发破缺。反之则差异轻松被消化。

3. **Entity 承接机制已工作但不够深入**：主体承接差异后减少 available_capacity，但承接后缺乏后续影响（如承接压力反作用于价格、保证金追缴等）。

4. **缺少交易所干预**：exp_003 持续破缺时，交易所作为二阶承接位置应自动介入（提高保证金、强制减仓等），但当前 runner 循环未集成 ExchangeIntervention。

5. **通道累计通过量显示问题**：used_capacity 会持续增长，报告中显示 3597% 使用率。需要区分「瞬时使用率」和「累计通过量」。

---

## 四、待做事项（下一阶段）

| 优先级 | 事项 | 说明 |
|---|---|---|
| P0 | runner 集成 ExchangeIntervention | 持续破缺时交易所自动介入 |
| P0 | 修复通道使用率显示 | 区分瞬时使用率和累计通过量 |
| P1 | Entity 承接反馈 | 承接压力影响保证金、持仓、流动性 |
| P1 | 调整 exp_002/004 参数 | 降低通道容量或提高 recurrent_rate |
| P2 | 差异变形机制 | inventory→basis→price 的链式变形 |
| P2 | 反事实测试 | 参数变动后的轨迹变化对比 |

---

## 五、验证清单

- [x] 通道使用率硬保护（代码层面）
- [x] 每步状态都有稳态标签
- [x] Entity 参与差异承接
- [x] exp_002 跑通，稳态为 margin_relief
- [x] exp_003 跑通，出现破缺事件（34次）
- [x] exp_004 跑通，稳态为 liquidity_recovery
- [ ] 通道使用率显示修复（瞬时vs累计）
- [ ] 交易所干预机制集成
- [ ] Entity 承接反馈循环
- [ ] 所有测试通过