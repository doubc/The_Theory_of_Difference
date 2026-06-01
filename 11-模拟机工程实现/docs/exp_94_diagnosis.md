# exp_94 诊断报告 — 2026-06-01

## 执行结果总览

| 指标 | exp_94 | exp_93 | exp_90 (baseline) |
|------|--------|--------|-------------------|
| H1 (GBC n_checks > 0) | ✅ PASS (16) | ❌ FAIL (0) | — |
| H2 (GBC coh > 0.1) | ✅ PASS (0.5671) | ❌ FAIL (0.0000) | — |
| H3 (CIV mean in [3,15]) | ❌ FAIL (2.00) | ❌ FAIL (48.50) | ✅ (5.25) |
| H4 (min CIV >= 3) | ❌ FAIL (min=1) | ✅ PASS (min=4) | ❌ (min=2) |
| H5 (CSC CSCI >= 0.3) | ✅ PASS (0.6668) | ✅ PASS (0.6697) | N/A |
| GBC pass_rate | 1.0000 | 0.0000 | 0.375 |
| CSC narrative coh | 0.8333 | 0.8333 | N/A |

## 核心发现

### GBC 修复成功 ✅
- GBC 现在真正执行了：n_checks=16（每 seed 16 次检查）
- GBC 相干性 mean=0.5671，与 exp_90 的 0.572 非常接近
- GBC pass_rate=1.0（所有检查通过）

### 但约束过强 ❌
- CIV 从 exp_93 的 48.50（爆炸）→ 2.00（坍缩）
- CIV 均值 2.00 甚至低于 exp_90 的 5.25
- min CIV=1（有种子几乎完全丧失文明层级）

### 根因分析

exp_94 使用了**全 +1 方向初始化**（all-ones fallback），导致：
1. `self_sustaining = 1.0`（最大自持值）
2. `boundary_vec = ones.float()`（最大边界约束）
3. GBC 以最大强度约束各层，高层级（CIVILIZATION）几乎无法涌现

这说明 **GBC 的方向初始化策略需要在"全零"（无约束）和"全+1"（最大约束）之间取平衡**。

### CSC 持续稳定 ✅
- CSCI=0.6668（与 exp_93 的 0.6697 几乎相同）
- narrative coherence=0.8333（完全相同）
- 证明 CSC 组件对 GBC 状态不敏感，稳定工作

## 修复方向

当前问题从"约束不足"变为"约束过度"。需要调整方向初始化策略：

**方案 A：随机初始化 direction**
- 以 50/50 概率随机设置 +1/-1
- 预期：self_sustaining ≈ 0.5，约束适中
- 风险：随机性引入方差

**方案 B：基于初始状态的温和阈值**
- 改用 `initial_state > 0.3` 而非 `> 0.5`（更宽松）
- 或：direction = sign(initial_state - mean) 而非 sign(initial_state - 0.5)
- 预期：更自然的约束水平

**方案 C：降低 GBC soft_nudge 强度**
- 从 0.2 降至 0.05-0.1
- 预期：GBC 激活但约束更温和
- 风险：可能不足以防止 CIV 爆炸

**推荐：方案 A（随机初始化）** — 最简单的平衡策略，预期 CIV 回归 exp_90 水平。

## 下一步
1. 实现方向随机初始化（方案 A）
2. 运行 exp_95 验证
3. 如果 CIV 回归正常范围 → 进入全组件联调（AMC + ILP + CSC + GBC）
