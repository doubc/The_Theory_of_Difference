# 🔍 开发者审查报告

**审查日期**: 2026-05-01  
**审查范围**: The_Theory_of_Difference 全项目  
**审查视角**: 全栈 Python 开发者接手维护

---

## 1. 代码可维护性

### 模块划分：⭐⭐⭐⭐ (4/5)

**做得好的：**
- `src/` 目录结构清晰：`compiler/`, `data/`, `retrieval/`, `workbench/`, `learning/`, `fast/` 各司其职
- 编译器流水线设计合理：`pivots → segments → zones → cycles → structures → bundles`
- 配置统一在 `src/config/__init__.py`，信号阈值不再散落各处

### 🔴 P0: 项目存在两套几乎完全相同的代码

```
src/                              ← 根目录的 src（v4.0）
10-期货价格结构检索系统/price-structure/src/  ← 子目录的 src（v3.1，旧版）
```

`diff` 验证：核心文件（signals.py, models.py, relations.py, quality.py）**完全相同**，但子目录缺少 6 个新文件（`daily_briefing.py`, `data_flow.py`, `help_system.py`, `kg_helper.py`, `tab_signal.py`, `theme_manager.py`）。

**风险**：改了一个 src 忘了改另一个，两个版本会悄悄分裂。

**修复**：删除子目录副本，保留根目录 v4.0 作为唯一源。

### 🟡 P1: "上帝函数"存在

| 函数 | 行数 | 位置 |
|------|------|------|
| `generate_signal()` | ~120 行 | `src/signals.py` |
| `compute_motion()` | ~150 行 | `src/relations.py` |
| `check_conservation()` | ~130 行 | `src/relations.py` |
| `build_dashboard_data()` | ~200 行 | `src/workbench/scan_pipeline.py` |
| `tab_scan` 全文 | **1296 行** | `src/workbench/tab_scan.py` |

`tab_scan.py` 1296 行是最严重的——单文件承担了全市场扫描 UI + 计算 + 展示，应该拆分。

### 🟡 P1: 命名不一致

- **中英混用**：`克莱因瓶涌现实现.py`、`素数相位码.py` 与 `batch_compile.py` 共存
- **函数别名污染**：`relations.py` 定义 `safe_cv` 后又 `_safe_cv = safe_cv`，`utils.py` 也有 `safe_cv`
- **重复定义**：`_departure_score` 在 `tab_scan.py` 和 `scan_pipeline.py` 各定义了一次

---

## 2. 依赖健康度

### 🔴 P0: `xgboost` 作为核心依赖

```toml
dependencies = [
    ...
    "xgboost>=2.0",  # ~200MB ML 库，只在 learning/classifier.py 用到
]
```

`xgboost` 只在 `src/learning/classifier.py` 里用，且有 `try/except ImportError` 保护。应改为 optional。

### 🟡 P1: `streamlit` 作为核心依赖

`streamlit>=1.30` 只在 `src/workbench/` 下使用。如果只跑 `scripts/batch_compile.py`，也得装 streamlit。应拆为 `pip install price-structure[ui]`。

### 同步问题

`pyproject.toml` 和 `requirements.txt` 内容一致，但 `requirements.txt` 把 MySQL 依赖写成了非 optional。

---

## 3. 测试覆盖度

### 143 个测试分布

| 测试文件 | 测试数 | 覆盖模块 |
|---------|--------|---------|
| `test_signals.py` | 11 | 信号生成、假突破模式、ATR止损 |
| `test_scan_modules.py` | 41 | 扫描组件（formatter、评分、价格位置） |
| `test_models.py` | 22 | 数据模型序列化/反序列化 |
| `test_retrieval.py` | 13 | 检索引擎 |
| `test_compiler.py` | 12 | 编译器流水线 |
| `test_quality.py` | 12 | 质量分层 |
| `test_dsl.py` | 12 | DSL 规则引擎 |
| `test_learning.py` | 9 | 特征提取 |
| `test_new_modules.py` | 6 | 新模块（反射性、共振、叙事） |
| `test_sample.py` | 5 | 样本库 |

### 🔴 核心路径缺失测试

1. **`relations.py` — 0 个直接测试**：`compute_motion()`, `check_conservation()`, `compute_projection()`, `detect_stability_illusion()` 无独立单元测试
2. **`lifecycle.py` — 0 个测试**
3. **`src/fast/__init__.py` — 0 个测试**：C 扩展 fallback 路径未测，且有 `Path` 未导入 bug
4. **错误路径测试缺失**：所有测试都是 happy path
5. **`build_system_state()` 副作用未测试**

---

## 4. 错误处理

### 🔴 静默失败泛滥

| 位置 | 问题 | 影响 |
|------|------|------|
| `scan_pipeline.py:222` | `generate_signal()` 失败被 `pass` | 用户不知道是"没信号"还是"计算出错" |
| `app.py:293-481` | `_safe_float/int/str` 吞异常 | 数据展示静默降级为 0 |
| `data_flow.py` (8处) | JSONL 读取失败静默跳过 | 历史数据丢失无告警 |
| `sina_fetcher.py:93,124` | 网络请求失败静默 | 数据获取失败无告警 |

### 做得好的

- `CompilerConfig.__post_init__()` 有参数校验
- `batch_compile.py` 有错误收集和报告机制

---

## 5. 性能瓶颈

### 全市场扫描

`build_dashboard_data()` 对每个品种做完整编译 + 信号生成。50 品种 × 3-5 结构 = 150-250 次编译。

### 已有优化

- `batch_compile.py` 多进程并行
- `src/fast/` C 扩展加速
- `binary_filter_bars()` 二分查找 O(log n)

### 🔴 待优化

1. **无结果缓存**：每次全量重算，应加 TTL 缓存
2. **重复计算 `statistics.median(volumes)`**：`detect_fake_breakout()` 和 `score_breakout_confirmation()` 各算一次
3. **`_detect_fake_wick_cluster` O(n²)**：内层循环重复遍历
4. **`check_conservation()` 与 `compute_motion()` 重复逻辑**

---

## 6. 可扩展性

### 加新品种：⭐⭐⭐⭐⭐ (0 个代码文件)

只需 `config/products/<name>/` + `registry.yaml`，完全数据驱动。

### 加新 Tab：⭐⭐⭐⭐ (2-3 个文件)

新建 `tab_<name>.py` + `app.py` 注册。

### 加新信号类型：⭐⭐⭐ (3-5 个文件)

需改 `models.py` + `signals.py` + `config/__init__.py` + 测试 + 展示。`generate_signal()` 已很长，应重构为策略模式。

---

## 修复计划

| 优先级 | 问题 | 状态 |
|--------|------|------|
| 🔴 P0 | `10-期货价格结构检索系统/` 重复目录 | ⬜ 保留，需手动同步 |
| 🔴 P0 | `fast/__init__.py` 的 `Path` 未导入 bug | ✅ fa206b1 |
| 🔴 P0 | `xgboost`/`streamlit` 移到 optional dependencies | ✅ fa206b1 |
| 🟡 P1 | 信号生成静默失败 → logged warning | ✅ a926c3a |
| 🟡 P1 | 知识图谱加载静默失败 → logged debug | ✅ a926c3a |
| 🟡 P1 | `build_dashboard_data()` 加缓存 | ⬜ |
| 🟡 P1 | `generate_signal()` 重构为策略模式 | ⬜ |
| 🟡 P1 | `tab_scan.py` 拆分计算/展示 | ⬜ |
| 🟢 P2 | 补充 relations/lifecycle/fast 测试 | ⬜ |
| 🟢 P2 | `requirements.txt` 拆分依赖 | ✅ fa206b1 |
| 🟢 P2 | 统一命名规范 | ⬜ |
