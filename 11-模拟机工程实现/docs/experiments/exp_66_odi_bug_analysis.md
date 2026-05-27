# exp_66: ODI=0 根因调查与修复

**日期**: 2026-05-05-28 05:30 (Asia/Shanghai)
**类型**: Bug 调查 + 修复

---

## 一、问题背景

exp_61-65 的实验报告中，ODI 始终显示为 0.0000。这引发了一个理论疑问：
- **理论解释**: ODI=0 可能是正确的 — 六阈值未全部达标 → 结构未呈象 → ODI=0 符合"存在≠呈象"
- **工程怀疑**: ODI 计算可能有实现缺陷

---

## 二、调查方法

创建 `exp_66_odi_investigation.py`，在 HierarchicalEvolver 运行过程中记录每一步的六个子指数值：
1. threshold_proximity（阈值接近度，权重 0.30）
2. coupling_density（耦合密度，权重 0.20）
3. stability_margin（稳定性裕度，权重 0.20）
4. firewall_purity（防火墙纯度，权重 0.10）
5. temporal_consistency（时间一致性，权重 0.10）
6. cross_mechanism_resonance（跨机制共振，权重 0.10）

---

## 三、关键发现

### 3.1 ODI 并非为零

exp_66 实验揭示：**ODI 实际值为 0.65-0.70**，并非之前报告中显示的 0.0000。

之前的实验从 `result_entry['odi']['value']` 读取 ODI，但该路径在某些情况下返回 0（可能是封口后层切换时的初始值）。ODI 组件内部的历史记录 (`odi._odi_history`) 显示真实值。

### 3.2 真正的 Bug：耦合密度键名不匹配

**根因**: `_compute_coupling_density()` 和 `_compute_resonance()` 使用 `SixThresholdDetector.THRESHOLD_NAMES.keys()` 查找耦合矩阵条目。

`THRESHOLD_NAMES` 的键格式为：
```python
'3.1_interface_regulation', '3.2_self_sustaining', ...
```

但 `hierarchical_evolver.py` 中构建的耦合矩阵使用：
```python
'interface_regulation', 'self_sustaining', ...
```

**结果**: 所有 15 对机制的耦合强度查找都返回 0.0，导致：
- `coupling_density` ≡ 0.0（损失 0.20 权重）
- `cross_mechanism_resonance` 的谱半径分量 ≡ 0.0

### 3.3 修复前后对比

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| coupling_density (mean) | 0.0000 | 0.34-0.61 |
| cross_mechanism_resonance (mean) | 0.59 | 0.78-0.86 |
| ODI max | 0.68 | 0.85-0.91 |
| ODI mean | 0.66 | 0.74-0.82 |
| ODI 分区 | pre_subjective_entry | pre_subjective_deep / dense_entry |

---

## 四、修复内容

### 4.1 `engine/organizational_density_index.py`

添加类常量 `_COUPLING_MECHANISMS`（与 `PreSubjectivityConvergence.MECHANISMS` 和 `hierarchical_evolver` 一致）：

```python
_COUPLING_MECHANISMS = [
    'interface_regulation',       # 3.1
    'self_sustaining',            # 3.2
    'retention',                  # 3.3
    'replication',                # 3.4
    'selection',                  # 3.5
    'functional_differentiation', # 3.6
]
```

更新 `_compute_coupling_density()` 和 `_compute_resonance()` 使用 `_COUPLING_MECHANISMS` 而非 `THRESHOLD_NAMES.keys()`。

### 4.2 `tests/test_organizational_density_index.py`

更新 `_make_full_coupling_matrix()` 辅助函数，使用不带 `3.X_` 前缀的机制名称。

---

## 五、理论意义

### 5.1 ODI 的真实水平

修复后 ODI 达到 0.85-0.91（超致密区入口），说明：
- 六阈值在封口后基本全部达标（threshold_proximity ≈ 0.95）
- 耦合是真正的瓶颈（coupling_density ≈ 0.34-0.61，仍低于其他子指数）
- 这与 exp_63-65 的收敛分析一致

### 5.2 耦合瓶颈的确认

即使修复后，耦合密度仍是六个子指数中最低的：
- Seed 0: coupling_density=0.34（最低），收敛率 0/40
- Seed 1: coupling_density=0.61（较高），收敛率 26/40
- Seed 2: coupling_density=0.61（较高），收敛率 24/40

**结论**: 耦合是收敛的主要瓶颈，与理论分析一致。下一步应继续优化耦合计算（加权耦合、方向场聚类等）。

### 5.3 象界理论验证

修复后的 ODI 值（0.74-0.86 mean）落在"前主体态深层区"到"致密区入口"，说明：
- 系统确实能达到前主体态（ODI > 0.5）
- 但距离超致密区（ODI > 0.85，第七阈值可能涌现）仍有差距
- 这与象界"组织密度连续增长"的理论一致

---

## 六、下一步

1. **exp_67**: 在修复后重新运行 majority coupling 实验，观察收敛率是否提升
2. **加权耦合**: 实现核心机制对加权耦合（符合象界"功能分化"理论）
3. **Phase 3 实验三**: MSI 增长曲线追踪（ODI 现在足够高，Phase 3 组件应该能激活）
4. **ODI 报告修复**: 修复 exp_61-65 中 ODI 读取路径的问题

---

*本文档由 exp_66 心跳调查自动生成*
