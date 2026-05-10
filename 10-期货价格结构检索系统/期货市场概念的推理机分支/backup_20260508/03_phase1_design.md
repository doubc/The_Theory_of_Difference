# Phase 1 设计文档：实验扩展 + 引擎修补 + 承接连接

版本：V0.2 | 日期：2026-05-07
作者：QClaw (AI) | 状态：进行中

---

## 一、当前状态（接手快照）

### 已完成
- 文件架构：46 个文件，6 层目录
- 核心对象：World / DifferenceSource / Entity / Channel / State / Trace / Event
- 引擎：transfer / conservation / minimal_change / lock_in / break_event / nearest_stable / runner
- 实验：exp_001（库存差异→基差），跑通 10 步，报告自动生成
- 测试：11 个单元测试全通过

### 已知缺陷
1. **exp_001 太简单**：单差异+通道容量充足，一步转移完，后续无差异运动
2. **通道使用率 247%**：reset_step 只释放 70%，但 transfer 不检查已用>容量
3. **最近稳态 Step 10 缺标签**：state 在 runner._check_stable 之前创建，稳态标签未写入
4. **Entity 未参与承接**：差异转移只走通道，Entity 的承接能力未进入引擎循环
5. **缺少多差异交互**：单差异无法展示「差异叠加→破缺→新稳态」的完整链条

### 文件路径
- 项目根目录：D:\PythonWork\The_Theory_of_Difference\10-期货价格结构检索系统\期货市场概念的推理机分支
- Python：D:\Python312\python.exe
- 依赖：pyyaml>=6.0, pytest>=8.0（已安装）

---

## 二、本阶段目标

| 编号 | 目标 | 完成标准 |
|---|---|---|
| P1-1 | 修复已知缺陷 | 通道使用率不超 100%；稳态标签每步都有；Entity 参与承接 |
| P1-2 | 补充 3 个实验 | exp_002（保证金压力）exp_003（近月逼仓）exp_004（规则调整）均能跑通 |
| P1-3 | 实验结果文档化 | 每个实验有独立的设计→配置→结果→分析文档 |
| P1-4 | 期货领域规则 | futures_rules.py 实现期货专用通道匹配和差异变形规则 |

---

## 三、工程设计

### P1-1 缺陷修复

#### 3.1.1 通道容量保护

**问题**：channel.transfer() 不检查 remaining_capacity，只取 min(amount, remaining)，但 reset_step 释放 70% 后 used_capacity 可能大于 capacity。

**方案**：
- transfer() 中增加硬保护：ctual = min(amount, self.remaining_capacity)（已有）
- reset_step() 改为：self.used_capacity = max(0, self.used_capacity * 0.7 - 0.1 * self.capacity * self.lock_in)
  - 锁定度越高，释放越少（路径依赖占用容量）
- 新增属性方法 capacity_usage 返回 min(1.0, used/capacity)，用于报告

#### 3.1.2 稳态标签写入时序

**问题**：runner._check_stable() 在 snapshot_state() 之后执行，但稳态标签写在前一个 state 上。

**方案**：调整 runner 步骤顺序：
1. 通道恢复
2. 差异转移
3. 守恒检查
4. 破缺检查
5. 锁定更新
6. **状态快照**（移到最后）
7. 稳态判定 → 写入刚创建的 state

#### 3.1.3 Entity 参与承接

**问题**：差异转移只通过通道，Entity 的承接能力完全未使用。

**方案**：在 transfer 流程中增加「承接检查」：
1. 差异选择通道后，查找该通道关联的 Entity
2. Entity 按承接能力排序（available_capacity 最大优先）
3. Entity 承接差异压力，减少 available_capacity
4. Entity 承接不足时，差异积累
5. 破缺时，Entity 可能被 margin_call / forced_out

**实现**：在 World 中增加 channel_entity_map（通道→承接体列表），在 runner._run_transfers 中调用。

### P1-2 实验设计

#### exp_002：保证金压力降低承接力

**差异源**：
- margin_pressure：保证金差异，magnitude=70，persistence=0.9
- inventory_gap：库存差异，magnitude=60

**通道**：
- margin_channel：margin → liquidity，capacity=50（容量不足！）
- basis_channel：inventory → basis

**主体**：
- speculative_fund_001：leverage=5，保证金压力放大
- industrial_long_001：leverage=1.5，影响较小

**预期稳态**：低流动性稳态（投机者承接力被保证金压低）

#### exp_003：近月逼仓

**差异源**：
- delivery_pressure：交割差异，magnitude=90，persistence=0.95
- inventory_shortage：库存差异，magnitude=80

**通道**：
- delivery_channel：delivery → near_month_squeeze，capacity=40（严重不足）
- warehouse_receipt_channel：inventory → delivery，capacity=30

**主体**：
- industrial_short_001：空头，承接力有限
- speculative_long_001：多头，趋势跟随
- exchange_001：交易所（二阶承接位置）

**预期稳态**：近月挤压稳态 → 交易所可能干预

#### exp_004：交易所规则调整

**差异源**：
- rule_change：规则差异，magnitude=60
- margin_pressure：保证金差异，magnitude=50

**通道**：
- exchange_rule_channel：rule → rule_adjusted，capacity=60
- margin_channel：margin → liquidity，capacity=40

**主体**：
- exchange_001：交易所，capacity=200
- speculative_fund_001：leverage=3

**预期稳态**：规则调整后新稳态

### P1-4 期货领域规则

**futures_rules.py** 核心功能：
1. 差异变形规则：inventory → basis → price 的链式变形
2. 通道-差异类型匹配表（哪些差异可以走哪些通道）
3. 近月/远月差异（近月交割压力更大）
4. 交易所二阶承接逻辑（当市场承接不足时，交易所介入）

---

## 四、执行顺序

1. 缺陷修复（P1-1）→ 测试验证
2. futures_rules.py（P1-4）→ 单元测试
3. Entity 承接连接（P1-1.3）→ 测试验证
4. exp_002 配置 + 运行 + 结果文档
5. exp_003 配置 + 运行 + 结果文档
6. exp_004 配置 + 运行 + 结果文档
7. 阶段总结文档

---

## 五、验证清单

- [ ] 通道使用率不超过 100%
- [ ] 每步状态都有稳态标签
- [ ] Entity 参与差异承接（available_capacity 减少）
- [ ] Entity 承接力不足时差异积累
- [ ] exp_002 跑通，稳态为 low_liquidity
- [ ] exp_003 跑通，出现破缺事件（近月逼仓）
- [ ] exp_004 跑通，稳态为 rule_adjusted
- [ ] 所有测试通过
- [ ] 每个实验有独立结果文档