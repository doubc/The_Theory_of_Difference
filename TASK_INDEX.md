# 价格结构检索系统 — 任务索引

**目标**：构建5层"结构雷达"全景展示+筛选系统

**分工**：🤖 我（助理）负责打勾和更新状态，💻 mi-mo 负责写代码

---

## 当前进度总览

| 阶段 | 完成度 | 状态 |
|------|--------|------|
| Phase 0 — Bug修复 | ✅ 4/4 | **已完成** |
| Phase 1 — 字段链路打通 | ✅ 5/5 | **已完成** |
| Phase 2 — 展示增强 | ✅ 5/5 | **已完成** |
| Phase 3 — 全景展示 | ✅ 5/5 | **已完成** |
| Phase 4 — 交互升级 | ⬜ 0/4 | 待开始 |
| Phase 5 — 数据层优化 | ⬜ 0/4 | 待开始 |
| Phase 6 — 可视化升级 | ⬜ 0/3 | 待开始 |
| Phase 7 — 性能优化 | ⬜ 0/3 | 待开始 |
| Phase 8 — 代码重构 | ⬜ 0/4 | 待开始 |

---

## Phase 0 — Bug修复（阻断性问题）✅ 已完成

| # | 任务 | 状态 | 验证结果 |
|---|------|------|----------|
| 0-1 | compile_structures 返回值顺序 | ✅ | 当前代码 `sym_result, sym_bars = ...` 正确 |
| 0-2 | 历史日志字段名不一致 (similarity) | ✅ | 当前代码 `c["score"].total` 正确 |
| 0-3 | signal_score placeholder | ✅ | 当前代码 `qa.score` 正确 |
| 0-4 | 运动阶段枚举统一 (breakdown) | ✅ | 当前代码 `motion_map` 映射正确 |

---

## Phase 1 — 字段链路打通（Data → UI）✅ 已完成

**目标**：5个字段全部打通，为后续筛选和排序做准备

| # | 任务 | 状态 | 优先级 | 依赖 | 说明 |
|---|------|------|--------|------|------|
| 1-1 | **session_state 持久化完整结果** | ✅ | 🔴 P0 | - | 已添加 `scan_results_full` 存储完整 `dashboard_data` |
| 1-2 | **price_position_code 字段** | ✅ | 🔴 P0 | - | 已添加 `price_position_code`（H/M/L） |
| 1-3 | **phase_code 字段** | ✅ | 🔴 P0 | - | 已添加 `phase_code`（breakout/confirmation/forming/stable/breakdown） |
| 1-4 | **sector 字段加载** | ✅ | 🔴 P0 | symbol_meta.yaml | 已创建 `get_sector()` 函数，`sector` 字段已加载 |
| 1-5 | **priority_score 字段** | ✅ | 🟡 P1 | 1-2, 1-3, 1-4 | 已实现综合排序分数（0-100）|

### Phase 1 字段说明

**session_state 持久化 (1-1)**
- 当前：`st.session_state["prev_scan_results"] = dashboard_data[:20]`
- 需要：`st.session_state["scan_results_full"] = dashboard_data`

**price_position_code (1-2)**
- 输入：`price_position` 字段（"高位"/"低位"/"中位"）
- 输出：`price_position_code` 字段（"H"/"M"/"L"）
- 用途：筛选器 + 排序

**phase_code (1-3)**
- 输入：`motion` 字段（"破缺"/"确认"/"形成"/"稳态"/"回落"）
- 输出：`phase_code` 字段（"breakout"/"confirmation"/"forming"/"stable"/"breakdown"）
- 用途：筛选器 + priority_score 计算

**sector (1-4)**
- 输入：`symbol`（如 "rb2505"）
- 处理：`symbol_meta.py` 添加 `get_sector(symbol)` 函数，读取 `symbol_meta.yaml`
- 输出：`sector` 字段（"黑色金属"/"有色金属"/"能源化工"/"农产品"/"贵金属"）
- 用途：板块筛选器 + 板块热度图

**priority_score (1-5)**
```
priority_score = departure_score×0.30 + quality_score×0.20 + phase_score×0.20 + position_score×0.15 + volume_score×0.15
```
- `phase_score` 映射：breakout=1.0, confirmation=0.8, forming=0.5, stable=0.3, breakdown=0.2
- `position_score` 映射：H=1.0, M=0.6, L=0.8
- `quality_score` = `score.total` / 100
- `volume_score` = 标准化成交量

---

## Phase 2 — 展示增强（筛选器 + 排序 + 分页）✅ 已完成

**目标**：增加5个筛选器，重构分页逻辑，让筛选器从 session_state 读取数据。

| # | 任务 | 状态 | 优先级 | 依赖 | 说明 |
|---|------|------|--------|------|------|
| 2-1 | **priority_score 综合排序** | ✅ | 🔴 P0 | 1-5 | 默认排序改为 priority_score 降序 |
| 2-2 | **价格位置筛选器** | ✅ | 🔴 P0 | 1-2 | 下拉框：全部/高位/中位/低位（用 price_position_code） |
| 2-3 | **运动阶段筛选器** | ✅ | 🔴 P0 | 1-3 | 改用 phase_code 字段筛选（breakout/confirmation/forming/stable/breakdown） |
| 2-4 | **sector 板块筛选器** | ✅ | 🟡 P1 | 1-4 | 下拉框：全部/黑色金属/有色金属/能源化工/农产品/贵金属 |
| 2-5 | **分页增强** | ✅ | 🟡 P1 | 1-1 | 重构：筛选面板外移，从 session_state["scan_results_full"] 读取 |

---

## Phase 3 — 全景展示 ✅ 已完成

**目标**：5层结构雷达——板块热度图 → 机会队列 → 合约详情 → 观察池 → 自选提醒

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 3-1 | **板块热度图** | ✅ | 按 sector 分组，展示情绪（偏多/偏空/分歧）+ top 合约 |
| 3-2 | **机会队列** | ✅ | 按板块分组展示 top3 优先级合约 |
| 3-3 | **合约详情面板增强** | ✅ | 3列布局 + priority_score + sector + 观察池按钮 |
| 3-4 | **观察池** | ✅ | session_state 持久化，支持添加/删除/清空 |
| 3-5 | **自选提醒** | ✅ | 阶段变化提醒 + 价格远离稳态提醒 |

---

## Phase 4-8

（详见原设计文档，当前聚焦 Phase 1-3）

---

## 设计参考

### sector 映射（symbol_meta.yaml）
```yaml
黑色金属: rb, hc, j, i, jm
有色金属: cu, al, zn, ni, sn
能源化工: sc, bu, ta, ma, pf
农产品: m, y, p, cs, a
贵金属: au, ag
```

### priority_score 公式
```
priority_score = departure_score×0.30 + quality_score×0.20 + phase_score×0.20 + position_score×0.15 + volume_score×0.15
```

---

## 执行记录

**2026-04-29 22:15** 
- ✅ Phase 1 完成：5/5 字段链路任务全部实现
- 修改文件：`src/data/symbol_meta.py`（添加 get_sector）、`src/workbench/tab_scan.py`（添加5个字段+session_state持久化）
- 📋 任务分工确认：我（助理）负责打勾，亲自实现代码
- 🔄 准备进入 Phase 2（展示增强）

**2026-04-29 22:37**
- ✅ Phase 2 + Phase 3 一次性完成：10/10 任务全部实现
- 修改文件：`src/workbench/tab_scan.py`（新增 248 行：板块热度图 + 机会队列 + 合约详情增强 + 观察池 + 自选提醒 + 新筛选器）
- 🗺️ 3-1: 板块热度图——按 sector 分组，情绪卡片（偏多/偏空/分歧）
- 🎯 3-2: 机会队列——按板块分组 top3 优先级合约
- 📋 3-3: 合约详情增强——3列布局 + priority_score 构成分解 + 观察池按钮
- ⭐ 3-4 + 3-5: 观察池 + 自选提醒（阶段变化 + 价格远离稳态）
- 🔄 准备进入 Phase 4（交互升级）
