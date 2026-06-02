# exp_116 Track B3: L1→L2 信息通道重构 — 噪声注入 + 层内自生动力学

**Date:** 2026-06-02  
**Parent:** exp_115 (Track B2: Serial CSC Coupling)  
**Status:** Design

---

## B2 失败总结

| 指标 | 目标 | B2 结果 | 差距 |
|---|---|---|---|
| H30: L1↔L2 相关性 | r < 0.7 | r = 0.86 ± 0.10 | 仅 1/8 通过 |
| H31: L0→L1 延迟 | 检测到 | 0/8 检测到 | 完全未激活 |
| H8: TopDown | 8/8 激活 | 0/8 | 完全未激活 |

**根因：**
1. B2 的 serial coupling 中，L2 从 L1 派生，但噪声注入 (0.05) 太弱，衰减 (0.7) 不够
2. L1 自身稳定性太高 (~0.61)，即使衰减后 L2 仍与 L1 高度相关
3. L1 不由 L0 驱动，而由自身制度自稳驱动 → L0→L1 信号被淹没
4. L2 完全被动派生，没有独立动力学

---

## B3 设计：三层改进

### 改进 1: 增强 L1→L2 噪声注入 (Noise Injection)

**当前：** `serial_l1_to_l2_noise = 0.05`（对结构向量的绝对噪声）

**问题：** 噪声幅度远小于 L1 信号强度（L1 稳定性 ~0.61），噪声被淹没

**B3 方案：**
- 将噪声从绝对噪声改为 **相对噪声**（相对于 L1 信号强度）
- `serial_l1_to_l2_noise_rel = 0.3`（L1 信号强度的 30%）
- 同时保留绝对噪声 `serial_l1_to_l2_noise_abs = 0.1` 作为基底噪声
- 综合噪声 = `relative_noise * l1_signal + absolute_noise`

**理论依据：** 差异论 §2.2 — 层级间的差异不是简单的信息衰减，而是**差异的重新组织**。噪声代表"层间差异的不可约部分"，即 L1 的制度输出在传导到 L2 时必然丢失/扭曲的信息。

### 改进 2: 降低 L1→L2 衰减 (Attenuation)

**当前：** `serial_l1_to_l2_attenuation = 0.7`

**问题：** 0.7 的衰减意味着 L2 仍保留 L1 70% 的信息，相关性依然过高

**B3 方案：**
- `serial_l1_to_l2_attenuation = 0.3`（L2 只保留 L1 30% 的信息）
- 额外 ODI 衰减因子 `serial_l1_to_l2_odi_factor = 0.5`（ODI 额外减半）

**理论依据：** "信息每经过一个层级就发生一次不可逆的耗散" — 制度信息传导到文明层级时，大部分具体细节被抽象化/丢失，只保留宏观结构。

### 改进 3: 添加 L2 层内自生动力学 (Intrinsic L2 Dynamics)

**当前：** L2 完全被动派生自 L1，无任何独立动力学

**问题：** 即使噪声和衰减调整，L2 仍然是 L1 的函数，无法真正独立

**B3 方案：**
- 为 L2 添加 **自生噪声扰动**（intrinsic noise perturbation）
- 每步以概率 `serial_l2_intrinsic_perturbation_rate = 0.02` 对 L2 结构向量施加随机扰动
- 扰动幅度 `serial_l2_intrinsic_perturbation_magnitude = 0.15`
- L2 的稳定性有一个**基础衰减**：每步自动衰减 `serial_l2_autonomous_decay = 0.98`（模拟文明层级的自然耗散）

**理论依据：** 差异论 — 每个层级都有自身的"差异场"，文明层级不是制度的简单投影，而是制度差异在更大尺度上的**重新凝聚**。自生扰动模拟这种重新凝聚过程中的随机性。

### 改进 4: L0→L1 传导增强

**当前：** L1 不由 L0 驱动，导致 L0→L1 延迟无法检测

**B3 方案：**
- 在 serial coupling 中，L1 仍然从 L0 接收输入（这是 B2 已有的）
- 但需要确保 L1 的**制度自稳**不会完全压制 L0 信号
- 添加 `serial_l0_to_l1_signal_weight = 0.4`（L0 信号在 L1 中的权重）
- 当 L1 稳定性过高时，自动降低自稳权重，让 L0 信号有更多空间

---

## 配置参数汇总

| 参数 | B2 值 | B3 值 | 变化 |
|---|---|---|---|
| `coupling_mode` | serial | serial | 不变 |
| `serial_l1_to_l2_delay` | 15 | 15 | 不变 |
| `serial_l1_to_l2_attenuation` | 0.7 | **0.3** | ↓ 57% |
| `serial_l1_to_l2_noise` | 0.05 | **0.1 (abs) + 0.3 (rel)** | ↑ 6x |
| `serial_l1_to_l2_odi_factor` | 0.8 | **0.5** | ↓ 37.5% |
| `serial_l2_intrinsic_perturbation_rate` | — | **0.02** | 新增 |
| `serial_l2_intrinsic_perturbation_magnitude` | — | **0.15** | 新增 |
| `serial_l2_autonomous_decay` | — | **0.98** | 新增 |
| `serial_l0_to_l1_signal_weight` | — | **0.4** | 新增 |

---

## 假设更新

### H30 (层间解耦): L1↔L2 相关性 r < 0.7
- **B2 结果:** 1/8 (12.5%), mean r = 0.86
- **B3 预期:** ≥ 5/8 (62.5%)
- **理论依据:** 更强的噪声 + 更低的衰减 + L2 自生动力学 → L2 不再镜像 L1

### H31 (层级延迟): L0→L1 + L1→L2 延迟检测
- **B2 结果:** 0/8 检测到 L0→L1 延迟
- **B3 预期:** ≥ 4/8 检测到 L0→L1 延迟
- **理论依据:** L0 信号权重提升 + L1 自稳压制减弱 → L0→L1 信号可检测

### H32 (新增): L2 自主性指数
- **定义:** L2 叙事与 L1 叙事的不一致性（1 - 叙事标签相似度）
- **目标:** L2 自主性指数 > 0.3（即 L2 叙事与 L1 至少有 30% 不同）
- **预期:** ≥ 5/8 种子通过

---

## 实验配置

- **脚本:** `experiments/exp_116_phase5_b3_l1_l2_channel_redesign.py`
- **种子:** 8 seeds (与 B1/B2 一致，便于对比)
- **步数:** 2000 steps
- **N0:** 72 (B2 最优规模)
- **架构:** CSC(serial, B3 config)+NSE+LNT

---

## 对比基线

| 实验 | 耦合模式 | L1↔L2 r | L0→L1 延迟 | TopDown |
|---|---|---|---|---|
| B1 (Parallel) | parallel | 0.976 | N/A | 0/8 |
| B2 (Serial) | serial | 0.861 | 0/8 | 0/8 |
| **B3 (Redesign)** | serial+B3 | **目标 < 0.7** | **目标 ≥ 4/8** | **目标 ≥ 4/8** |
