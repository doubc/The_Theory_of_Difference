# exp_103 P1-B Analysis: CIV Stability & TopDown Activation

> **日期**: 2026-06-01 23:29
> **实验**: exp_103_p1b_fixes
> **阶段**: Phase 4 P1-B
> **结果**: 5/8 pass (H5, H6, H8 fail)

---

## 一、实验目的

修复 exp_102 的两个失败假设：
- **H5**: CIV mean=32.125（种子 742 的 CIV=194 爆炸）
- **H8**: TopDown 激活种子数=0

---

## 二、P1-B 修复内容

1. **非平凡性因子温和化**: 下限 0.4→0.6，避免稳定性过度惩罚
2. **CIVRateLimiterV2 收紧**: max_rate 0.1→0.05, cooldown 10→5
3. **CIV 稳定性组合度量**: 60% 间隔 CV + 40% 事件密度
4. **TopDown 阈值降低**: 0.3→0.15
5. **INSTITUTIONAL 稳定性 ILP 回退**: 当层级状态缺失时使用 ILP 内部分数

---

## 三、结果对比

| 指标 | exp_101 | exp_102 | exp_103 | 变化方向 |
|------|---------|---------|---------|---------|
| stability_mean | 0.938 | 0.480 | 0.633 | ↑ 恢复 |
| CIV_mean | 5.25 | 32.125 | 2.5 | ↓ 过度抑制 |
| CIV_min | 3 | 5 | 1 | ↓ 低于 H6 阈值 |
| CIV_max | 7 | 194 | 7 | ↓ 742 爆炸修复 |
| CSCI_std | 0.001 | 0.027 | 0.021 | ✅ 保持非伪相干 |
| TopDown_active | 0 | 0 | 0 | ❌ 未改善 |
| NSI_max | 0.801 | 0.765 | 0.769 | ≈ 持平 |
| history_depth | 0.122 | 0.215 | 0.161 | ↓ 回落 |

---

## 四、H5/H6 失败分析

**根因**: CIVRateLimiter 收紧过度。

exp_103 的 limiter 配置 (max_rate=0.05, cooldown=5) 比 exp_102 (0.1, 10) 严格一倍。
加上非平凡性温和化后稳定性恢复，叙事递归产生的 CIV 事件更规律，
limiter 的窗口内事件密度更容易触发阈值。

**数据证据**:
- 种子 742: limiter_seen=6, limiter_down=6 (100% 降级率)
- 种子 342: limiter_seen=3, limiter_down=15 (500% 降级率 — cooldown 累积)
- 种子 642: limiter_seen=3, limiter_down=10 (333% 降级率)

**结论**: max_rate=0.05 太严格。需要回调到 0.07-0.08。

---

## 五、H8 失败分析

**根因**: CIV 层稳定性仍然太低，无法达到 TopDown 阈值 (0.15)。

即使使用了组合度量 (60% 间隔 CV + 40% 密度)，
CIV 事件太少 (1-4 个/种子/1600 步)，导致：
- 密度稳定性 = min(1.0, 4/20) = 0.2
- 间隔稳定性 = 数据不足，默认 0.3
- 组合 = 0.6×0.3 + 0.4×0.2 = 0.26

但这是理论上限。实际上，大多数种子的 CIV 事件间隔 CV 很高（事件分布不均匀），
导致 interval_stability 接近 0。

**根本问题**: CIV 层是"稀有事件"层，用事件间隔/密度来度量稳定性本质上有噪声。

**新策略 (P1-C)**:
1. **用 INSTITUTIONAL 层稳定性作为 TopDown 主要驱动**
   - INSTITUTIONAL 层有更多活动，稳定性信号更强
   - TopDown 约束的来源应该是 INSTITUTIONAL（有活动）而非 CIV（太稀疏）
2. **CIV 层稳定性仅作为辅助信号**
   - 当 CIV 事件足够多时（>10），才计入稳定性
3. **进一步降低 TopDown 阈值**: 0.15 → 0.10

---

## 六、P1-C 行动计划

1. **回调 CIVRateLimiter**: max_rate 0.05→0.08, cooldown 5→8
2. **TopDown 主驱动改为 INSTITUTIONAL**: 当 INSTITUTIONAL 稳定性 > 0.1 时激活
3. **TopDown 阈值**: 0.15→0.10
4. **CIV 稳定性**: 仅当事件数 > 10 时计入，否则使用默认值 0.3

---

## 七、结论

P1-B 部分成功：
- ✅ 修复了 CIV 爆炸（742: 194→4）
- ✅ 稳定性恢复（0.48→0.63）
- ❌ CIV 过度抑制（mean 2.5 < 3）
- ❌ TopDown 仍未激活

核心教训：
1. CIVRateLimiter 的 max_rate 和 cooldown 需要精细平衡
2. CIV 层作为"稀有事件"层，不适合用事件密度驱动 TopDown
3. TopDown 应该由 INSTITUTIONAL 层（中间层级，有足够活动）驱动
