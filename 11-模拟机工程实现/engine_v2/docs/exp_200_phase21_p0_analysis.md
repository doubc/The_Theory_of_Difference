# exp_200 Phase 21 P0: 能量流基线实验 — 分析报告

## 实验概述

**日期**: 2026-06-12  
**实验脚本**: `experiments/exp_200_phase21_p0_energy_baseline.py`  
**配置**: 4 个 (baseline, with_energy, low_budget, high_decay) × 8 seeds = 32 runs  
**假设**:
- H21-P0a: 能量预算耗尽时系统进入死秩序
- H21-P0b: 有能量注入时活秩序维持更长时间
- H21-P0c: 涌现深度与初始能量预算正相关
- H21-P0d: 熵产生持续 > 0 表示不可逆的叙事演化

## 关键结果

### 1. 涌现深度 (Emergence Depth)

| 配置 | 平均深度 | 标准差 | 范围 |
|------|---------|--------|------|
| baseline | 2.00 | 0.00 | 2-2 |
| with_energy | 2.00 | 0.00 | 2-2 |
| low_budget | 1.00 | 0.00 | 1-1 |
| high_decay | 1.75 | 0.43 | 1-2 |

**发现**:
- ❌ **H21-P0b 失败** — with_energy 与 baseline 深度完全相同 (2.00)
- ⚠️ **H21-P0c 部分确认** — low_budget (30.0) 深度只有 1, high_decay (0.05) 深度 1.75 < 2.00
- ✅ **能量影响深度** — 但 only at extreme values (low_budget, high_decay)

### 2. 能量比率 (Energy Ratio)

| 配置 | 平均能量比率 | 死秩序层数 |
|------|--------------|------------|
| baseline | 0.384 | 1.0 |
| with_energy | 0.384 | 1.0 |
| low_budget | 0.129 | 1.0 |
| high_decay | 0.194 | 1.0 |

**发现**:
- ❌ **H21-P0a 未验证** — 所有配置都有 1.0 死秩序层（通常是 L2）
- with_energy 的能量比率与 baseline 完全相同 — **能量注入没有效果**

### 3. 不可逆性 (Irreversibility)

| 配置 | 不可逆样本数 | 总数 |
|------|--------------|------|
| baseline | 0 | 8 |
| with_energy | 0 | 8 |
| low_budget | 0 | 8 |
| high_decay | 0 | 8 |

**发现**:
- ❌ **H21-P0d 失败** — 所有样本的 `is_irreversible = False`
- 熵产生组件 (`EntropyConfig`) 可能未正确实现或集成

## 根本问题分析

### 问题 1: 能量是"影子跟踪"，不是"驱动机制"

**症状**: `baseline` 和 `with_energy` 结果完全一样

**根因**: `EnergyManager.step()` 计算了能量消耗，但 **没有将能量状态传回给演化机制**。

在 `world.py` 第 88-96 行:
```python
if self.energy:
    costs = self.energy.step(active, total)
    if self.energy.is_dead_order:
        if verbose: print(f"  [ENERGY] L{f.layer} step{self.step}: dead order...")
```

这里只是 **记录和警告**，但没有：
- 根据 `self.energy.budget` 调整机制执行概率
- 在能量不足时跳过某些机制
- 将能量成本与机制输出耦合

**结果**: 无论 `EnergyConfig` 如何设置，九机制都按原样执行 → 结果完全相同。

### 问题 2: 熵产生计算可能错误

**症状**: `cumulative_entropy_production` 为负或零，`is_irreversible` 永远为 False

**可能根因**:
1. `EntropyConfig` 未正确集成到 `RecursiveWorld`
2. 熵产生公式可能符号反了（应该用正号表示产生）
3. `is_irreversible` 判定阈值可能设置错误

## 修复方案

### 方案 A: 能量驱动机制执行 (推荐)

修改 `world.py` 中的九机制调用，根据能量预算调整执行：

```python
# 伪代码
if self.energy:
    # 能量充足时正常执行
    if self.energy.budget > self.energy.config.low_energy_threshold:
        m9_output = self.m9_self_reference(...)
    # 能量不足时降低执行概率或跳过
    else:
        if np.random.random() < 0.5:  # 50% 概率跳过
            m9_output = None
```

**优点**: 能量真正影响动力学  
**缺点**: 需要修改每个机制，改动较大

### 方案 B: 能量作为机制输入参数

修改所有机制函数签名，接受 `energy_budget` 参数：

```python
def m9_self_reference(self, ..., energy_budget: float):
    # 根据能量预算调整输出强度
    strength = energy_budget / self.energy.config.initial_budget
    # ...
```

**优点**: 更精细的控制，能量影响机制输出强度  
**缺点**: 需要修改所有机制签名和调用

### 方案 C: 简化方案 — 能量只影响密封阈值

最小改动：只让能量影响 `should_seal()` 的判断：

```python
def should_seal(self):
    # 原有逻辑...
    if self.energy and self.energy.is_low_energy:
        # 低能量时更容易密封（系统"疲劳"）
        return True
    return # ...原逻辑
```

**优点**: 改动小，快速验证能量是否影响涌现深度  
**缺点**: 不是完整的能量驱动机制

## 建议下一步

1. **立即可做**: 实施方案 C（简化方案），验证能量是否至少能影响涌现深度
2. **短期**: 实施方案 B（能量作为机制输入），实现完整的能量驱动动力学
3. **同期**: 修复熵产生组件 (`EntropyConfig`)，让 `is_irreversible` 能正确判定
4. **重新运行**: exp_200_v2 with 修复后的能量驱动机制

## 理论意义

如果能量驱动机制修复成功，将验证：

1. **自指闭环 (A9) 需要能量预算来维持活秩序** — 能量耗尽 → 死秩序
2. **叙事演化是不可逆的熵产生过程** — 需要正确实现熵产生计算
3. **差异论的「差异源」可以形式化为能量流** — 为差异论与热力学/信息论的连接奠定工程基础

这将使差异论模拟机从「离散密封引擎」升级为「能量-熵流耦合的开放系统」。

---

**文件**: `docs/exp_200_phase21_p0_analysis.md`  
**实验数据**: `results/exp_200_p0_energy_baseline.json`  
**实验脚本**: `experiments/exp_200_phase21_p0_energy_baseline.py`
