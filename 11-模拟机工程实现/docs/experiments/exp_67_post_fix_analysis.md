# exp_67: ODI Bug 修复后验证实验 — 分析报告

**日期**: 2026-05-28 06:25 (Asia/Shanghai)
**类型**: 验证实验 + 工程修复

---

## 一、背景

exp_66 发现并修复了 ODI `coupling_density` 计算中的 key mismatch bug：
- `_compute_coupling_density()` 和 `_compute_resonance()` 使用 `THRESHOLD_NAMES.keys()`（带 `3.X_` 前缀）查找耦合矩阵，但矩阵键无前缀
- 导致 `coupling_density ≡ 0.0`（损失 0.20 权重），`cross_mechanism_resonance` 谱分量 ≡ 0.0

exp_67 目标：在 bug 修复后，全面验证收敛率和 ODI 真实水平。

---

## 二、实验设计

| 配置 | 模式 | 阈值 | N0 | 步数 | 运行次数 |
|------|------|------|-----|------|----------|
| A: 基线 | all | 0.30 | 48 | 200 | 4 |
| B: 最佳 | majority | 0.15 | 48 | 200 | 4 |
| C: 深度 | majority | 0.15 | 48 | 500 | 4 |
| D: 高容量 | majority | 0.15 | 72 | 300 | 4 |

新增测量：ODI 六个子指数完整时间序列 + 密度分区分布。

---

## 三、核心结果

### 3.1 收敛率

| 配置 | 收敛率 | 六阈值率 | 耦合率 | 稳定性率 | ODI_max | ODI_mean |
|------|--------|----------|--------|----------|---------|----------|
| A: 基线 (all, 0.30) | **76.2%** | 93.1% | 77.5% | 93.1% | 0.8930 | 0.8302 |
| B: 最佳 (majority, 0.15) | 21.9% | 46.2% | 54.4% | 46.2% | 0.8777 | 0.8034 |
| C: 深度 (majority, 0.15, s500) | 23.5% | 48.5% | 38.8% | 48.5% | 0.8750 | 0.8052 |
| D: 高容量 (majority, 0.15, N72) | 15.0% | 25.4% | 79.6% | 25.4% | 0.8518 | 0.7517 |

### 3.2 ODI 子指数（均值）

| 配置 | TP | CD | SM | FP | TC | CR |
|------|----|----|----|----|----|-----|
| A: 基线 | 0.9326 | 0.6630 | 0.6828 | 1.0000 | 0.9458 | 0.8670 |
| B: 最佳 | 0.9265 | 0.6212 | 0.6042 | 1.0000 | 0.9456 | 0.8583 |
| C: 深度 | 0.9706 | 0.5492 | 0.6112 | 1.0000 | 0.9745 | 0.8449 |
| D: 高容量 | 0.7580 | 0.6184 | 0.6385 | 1.0000 | 0.9655 | 0.7641 |

TP=阈值接近度, CD=耦合密度, SM=稳定性裕度, FP=防火墙纯度, TC=时间一致性, CR=跨机制共振

---

## 四、关键发现

### 4.1 PSC Bug 修复带来巨大提升

基线配置 (all, 0.30, s200) 收敛率：
- exp_63（修复前）：~10.0%
- exp_67（修复后）：**76.2%**

**7.6x 提升**。这是因为 exp_63 中 `PreSubjectivityConvergence` 的内部 `SixThresholdDetector` 从未收到 `replicated_pattern` 和 `original_pattern`，导致阈值 3.4（复制保真度）始终为 0.0，六阈值收束永远无法达成。

### 4.2 多数制耦合不再有优势

exp_65 中多数制（≥12/15）比全对制（15/15）有 ~2.5x 提升。但在 PSC bug 修复后：
- 全对制 (A): 76.2%
- 多数制 (B): 21.9%

**原因**：PSC bug 修复后，六阈值达标率大幅提升（93.1% vs 之前的 ~46%），耦合不再是绝对瓶颈。全对制的严格耦合要求（15/15 > 0.3）现在反而能达成，而多数制的低阈值（0.15）导致六阈值达标率反而更低（46.2%）。

### 4.3 ODI 真实水平确认

修复后 ODI 均值在 0.75-0.83 之间，分区分布主要在 dense_core（0.76-0.85）。这与 exp_66 修复后的单次测量（ODI max 0.85-0.91）一致。

**ODI 子指数排序**（从高到低）：
1. firewall_purity: 1.0000（始终完美，因为字段名检查通过）
2. threshold_proximity: 0.93-0.97（六阈值接近达标）
3. temporal_consistency: 0.94-0.97（时间维度稳定）
4. cross_mechanism_resonance: 0.76-0.87（跨机制协同）
5. stability_margin: 0.56-0.68（稳定性中等）
6. coupling_density: 0.55-0.66（耦合密度仍是最低子指数之一）

### 4.4 耦合仍是结构瓶颈

虽然 PSC bug 修复大幅提升了收敛率，但耦合密度（CD）仍是最低子指数之一：
- 均值 0.55-0.66，远低于 TP (0.93-0.97) 和 TC (0.94-0.97)
- 稳定性裕度 (SM) 也偏低 (0.56-0.68)

这与象界"功能分化"理论一致：机制间的不对称贡献是结构致密化的关键驱动力。

### 4.5 高容量 (N0=72) 表现不佳

D 配置 (N0=72) 收敛率仅 15.0%，低于 B (21.9%)。可能原因：
- 18 个活跃比特 vs 12 个，信号更分散
- 六阈值达标率仅 25.4%（vs B 的 46.2%）
- threshold_proximity 均值 0.758（vs B 的 0.927）

**假设**：更多活跃比特需要更多步数来形成稳定的六阈值结构。300 步可能不够。

---

## 五、工程修复

### 5.1 ODI 子指数追踪

在 `hierarchical_evolver.py` 的 `_make_phase2_callback` 中，ODI result_entry 现在存储全部六个子指数：

```python
result_entry['odi'] = {
    'value': odi_result.odi,
    'zone': odi_result.zone,
    'base_zone': odi_result.base_zone,
    'densification_rate': odi_result.densification_rate,
    'threshold_proximity': odi_result.subindices.threshold_proximity,
    'coupling_density': odi_result.subindices.coupling_density,
    'stability_margin': odi_result.subindices.stability_margin,
    'firewall_purity': odi_result.subindices.firewall_purity,
    'temporal_consistency': odi_result.subindices.temporal_consistency,
    'cross_mechanism_resonance': odi_result.subindices.cross_mechanism_resonance,
}
```

### 5.2 数据提取路径修正

之前实验脚本从 `layer_results[0]['entries']` 提取 ODI 数据，但该路径不存在。正确路径：

```python
for layer in results.get('layer_results', []):
    for step_result in layer.get('phase2_step_results', []):
        odi_data = step_result.get('odi', {})
```

---

## 六、下一步

1. **exp_68**: N0=72 + 更多步数（500-1000），验证高容量配置
2. **exp_69**: 加权耦合原型（核心机制对加权 > 均匀耦合）
3. **Phase 3 实验**: MSI 增长曲线（ODI 现在足够高，Phase 3 门控应能激活）
4. **理论工作**: 稳定性裕度偏低 (0.56-0.68) 的理论解释

---

## 七、Git

- `e1156b9` feat(exp_67): post-bug-fix validation + ODI subindex tracking in evolver
