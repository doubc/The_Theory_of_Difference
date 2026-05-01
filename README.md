# 价格结构形式系统

> 从期货价格序列中提取结构不变量（Structural Invariant），通过四层相似度检索历史先例，辅助交易决策。

## 这是什么

本系统是一套期货价格结构的研究底座。研究对象是价格序列中反复出现的结构性形态——围绕关键区（Zone）组织的、由速度比/时间比/试探聚集度等度量定义的投影不变量。

核心能力：结构编译器（四层流水线）→ 四层相似度检索 → 质量分层 → 跨品种共振 → 信号生成 → 知识图谱

技术栈：`Python` + `NumPy` + `Pandas` + `Plotly` + `Streamlit`，关键路径 `C 扩展` 加速（极值提取 24x，DTW 132x）

---

## 快速开始

```bash
pip install -r requirements.txt

# 编译 C 扩展（可选，无编译器自动 fallback）
python3 setup_fast.py build_ext --inplace

# 启动研究工作台
streamlit run src/workbench/app.py
```

---

## 项目结构

```
src/
├── models.py                  # 对象模型：Point → Segment → Zone → Cycle → Structure → Bundle
├── relations.py               # 关系算子 + 运动态 + 投影觉知 + 守恒检查
├── signals.py                 # 交易信号层（突破/假突破/回踩/结构老化）
├── quality.py                 # 质量分层（5维度 → A/B/C/D 四层）
├── resonance.py               # 跨品种共振检测
├── lifecycle.py               # 生命周期追踪
├── intraday_rhythm.py         # 日内节奏分析
├── narrative.py               # 叙事化输出
├── reflexivity.py             # 反身性追踪（骨架，见下方说明）
├── utils.py                   # 工具函数
├── compiler/                  # 价格→结构编译器（四层流水线）
│   ├── pipeline.py            # 统一入口 compile_full()
│   ├── pivots.py              # 3.1 极值提取
│   ├── segments.py            # 3.2 段生成 + 微段合并
│   ├── zones.py               # 3.3 关键区识别
│   ├── cycles.py              # 3.4 Cycle + Structure 组装
│   └── bundles.py             # 3.5 丛识别
├── data/                      # 数据层
│   ├── loader.py              # Bar / CSVLoader / MySQLLoader
│   ├── symbol_meta.py         # 品种元数据
│   ├── sina_fetcher.py        # 新浪实时数据拉取
│   ├── local_store.py         # Parquet 本地数据仓库
│   ├── batch_fetcher.py       # 批量并发抓取
│   └── price_context.py       # 价格上下文（见下方说明）
├── retrieval/                 # 相似性检索
│   ├── engine.py              # 检索引擎 + 后验统计
│   ├── similarity.py          # 四层相似度（几何/关系/运动/族）
│   ├── active_match.py        # 主动匹配
│   ├── opportunity.py         # 机会评估
│   ├── progress.py            # 检索进度
│   └── transition.py          # 状态转移分析
├── sample/                    # 样本库
│   ├── store.py               # SampleStore（JSONL 持久化）
│   └── outcome.py             # 前向演化结果
├── learning/                  # 学习模型
│   ├── features.py            # 特征提取
│   ├── embedding.py           # 向量嵌入
│   └── classifier.py          # 分类器
├── graph/                     # 知识图谱
│   ├── store.py               # GraphStore（JSONL 持久化）
│   └── product_ingester.py    # 多品种知识导入器
├── multitimeframe/            # 多时间维度
│   ├── comparator.py          # 跨尺度一致性检查
│   └── consistency.py         # MCI 计算
├── fast/                      # C 扩展
│   ├── _pivots.c              # 极值提取（24x）
│   ├── _dtw.c                 # DTW 距离（132x）
│   ├── _compiler.c            # 编译器加速（132x）
│   └── _similarity.c          # 相似度加速
├── dsl/                       # 规则引擎
│   └── rule.py                # 结构 DSL 规则匹配
├── scoring/                   # 评分系统
│   ├── priority.py            # 优先级评分
│   └── adapter.py             # 评分适配器
├── sector/                    # 板块映射
│   └── mapping.py             # 品种→板块
├── validation/                # 验证
│   └── falsification_card.py  # 证伪卡片
└── workbench/                 # Streamlit 研究工作台
    ├── app.py                 # 主入口（12 Tab 路由）
    ├── dashboard.py           # Tab 0: 仪表盘首页
    ├── tab_scan.py            # Tab 1: 全市场扫描
    ├── daily_briefing.py      # Tab 2: 每日简报
    ├── tab_signal.py          # Tab 3: 信号跟踪
    ├── tab_history.py         # Tab 4: 历史对照
    ├── tab_compare.py         # Tab 5: 跨品种对比
    ├── tab_stability.py       # Tab 6: 稳态地图
    ├── tab_journal.py         # Tab 7: 复盘日志
    ├── tab_contract.py        # Tab 8: 合约检索
    ├── tab_multitime.py       # Tab 9: 多时间维度
    ├── tab_quality.py         # Tab 10: 质量与共振
    ├── pages/research_loop.py # Tab 11: 研究闭环
    ├── shared.py              # 共享 CSS / 工具函数
    ├── data_layer.py          # 数据加载 + 编译
    ├── data_flow.py           # 统一数据流管理器
    ├── help_system.py         # 帮助系统
    ├── theme_manager.py       # 主题管理器
    ├── kg_helper.py           # 知识图谱查询助手
    ├── scan_pipeline.py       # 扫描计算管线
    ├── scan_components.py     # 扫描渲染组件
    ├── scan_filters.py        # 扫描筛选逻辑
    ├── scan_models.py         # 扫描数据模型
    ├── ui_formatters.py       # UI 格式化函数
    ├── mini_chart.py          # 缩略图 SVG（见下方说明）
    ├── activity_log.py        # 活动日志
    ├── quality_integration.py # 质量分层集成（见下方说明）
    ├── daily_report.py        # 日报渲染器（见下方说明）
    ├── helpers.py             # 辅助函数（见下方说明）
    └── v3_page.py             # v3.0 独立页面（见下方说明）
```

---

## 模块状态说明

### ✅ 核心模块（活跃）

| 模块 | 用途 | 调用链 |
|------|------|--------|
| `compiler/pipeline.py` | 编译统一入口 | app.py → data_layer → compile_full |
| `models.py` | 全部对象模型 | 全局依赖 |
| `relations.py` | 运动态 / 投影觉知 / 守恒 | pipeline → relations |
| `signals.py` | 信号生成 | tab_scan → signals |
| `quality.py` | 质量分层 | tab_quality / tab_scan → quality |
| `retrieval/engine.py` | 检索引擎 | tab_history → engine |
| `retrieval/similarity.py` | 四层相似度 | engine → similarity |
| `data/loader.py` | 数据加载 | 全局依赖 |
| `data/sina_fetcher.py` | 新浪实时数据 | tab_contract / tab_quality |
| `graph/store.py` | 知识图谱存储 | pipeline → graph |
| `workbench/app.py` | 工作台主入口 | — |
| `workbench/tab_*.py` | 12 个功能 Tab | app.py 路由 |
| `workbench/data_flow.py` | 数据流管理 | tab_signal / tab_scan |
| `fast/_*.c` | C 加速扩展 | fast/__init__.py 自动检测 |

### 🔶 骨架/预留模块（未完成）

| 模块 | 状态 | 说明 |
|------|------|------|
| `reflexivity.py` | 骨架 | 反身性追踪。理论框架已定义（V1.6 Ch14 命题 14.4），当前仅 dataclass + 接口预留。完整实现需要大量样本积累 + 长期运行数据。 |
| `data/price_context.py` | 骨架 | 价格上下文（顺时序分位数 + 价格体制判定）。模块已实现，但未接入编译器流水线。可作为反差推断的增强信号。 |
| `learning/` | 骨架 | 特征提取 + 向量嵌入 + 分类器。框架已搭建，需要真实样本数据训练。 |

### 🔷 工具/辅助模块（间接使用或参考实现）

| 模块 | 状态 | 说明 |
|------|------|------|
| `workbench/mini_chart.py` | 已实现，未接入 | 紧凑缩略图 SVG 渲染（K线/折线/柱状图 + Zone标注）。可嵌入扫描卡片，当前未集成到 Tab。 |
| `workbench/daily_report.py` | 已实现，未接入 | 面向研究决策的日报渲染器（三段式布局）。依赖 `Opportunity` 对象，当前 Tab 2 用 `daily_briefing.py` 替代。 |
| `workbench/quality_integration.py` | 参考实现 | 质量分层集成补丁。功能已内嵌到 `tab_quality.py`，此文件保留为工具函数参考。 |
| `workbench/helpers.py` | 参考实现 | 辅助函数。`_build_current_structure_dict` 已在 `app.py` 中内联实现。 |
| `workbench/v3_page.py` | 独立页面 | v3.0 统一集成页。功能已合并到 `app.py` Tab 10，此文件保留为独立运行入口。 |
| `workbench/activity_log.py` | 活跃 | 活动日志（JSONL）。被 `tab_scan`、`tab_history`、`tab_compare`、`tab_journal` 调用。 |
| `workbench/scan_pipeline.py` | 活跃 | 扫描计算管线。被 `tab_scan` 调用。 |
| `workbench/scan_components.py` | 活跃 | 扫描渲染组件。被 `tab_scan` 调用。 |
| `workbench/scan_filters.py` | 活跃 | 扫描筛选逻辑。被 `tab_scan` 调用。 |
| `workbench/scan_models.py` | 活跃 | 扫描数据模型。被 `tab_scan` 调用。 |
| `workbench/ui_formatters.py` | 活跃 | UI 格式化。被 `tab_scan`、`tab_compare` 调用。 |
| `workbench/kg_helper.py` | 活跃 | 知识图谱查询。被 `tab_journal`、`research_loop` 调用。 |
| `workbench/theme_manager.py` | 已实现 | 主题管理器（暗色/亮色切换）。已集成到 app.py。 |
| `workbench/help_system.py` | 活跃 | 帮助系统。被 `app.py` 调用。 |

---

## 核心概念

```
原始 K 线 → 极值点(Pivot) → 段(Segment) → 关键区(Zone)
    → 循环(Cycle) → 结构(Structure) → 系统态(SystemState)
```

| 概念 | 定义 |
|------|------|
| **极值点** | 价格序列中的局部极大/极小值，强制交替 |
| **关键区** | 多个极值点聚集的价位区间，有共同反差驱动 |
| **循环** | 价格围绕 Zone 的一次完整试探，携带速度比/时间比不变量 |
| **结构** | Zone + Cycles 的组合，携带运动态和投影觉知 |
| **系统态** | 结构 × 运动的完整封装，含差异分层和稳定性判定 |

详细定义 → [`docs/04_对象模型.md`](docs/04_对象模型.md)

---

## 金融知识图谱

内置多品种知识图谱，增强检索排序和叙事生成。

| 品种 | 实体 | 关系 | 传导链 | 定价模型 |
|------|------|------|--------|----------|
| _shared（跨品种） | 211 | 228 | 39 | — |
| copper（铜） | 35 | 23 | 7 | 5 |
| lithium_carbonate（碳酸锂） | 5 | 0 | 0 | — |
| lead / platinum / ferrosilicon / methanol / pta / soybean_meal / cotton / glass / soda_ash / industrial_silicon | 各 4-6 | 各 5 | 各 1-2 | 各 1 |

配置说明 → [`config/README.md`](config/README.md)

---

## 文档索引

| 文档 | 内容 |
|------|------|
| `docs/01_总纲.md` | 系统定位、研究目标、核心命题 |
| `docs/02_术语表.md` | 术语定义和对象词典 |
| `docs/03_弱公理.md` | 弱公理体系和可证伪研究假设 |
| `docs/04_对象模型.md` | 对象模型定义 |
| `docs/06_编译器.md` | 编译器四层流水线 |
| `docs/09_相似性定义.md` | 四层相似度模型 |
| `docs/11_信号设计.md` | 交易信号设计 |
| `docs/16_知识注入系统.md` | 知识注入架构（L1/L2/L3） |

---

## 测试

```bash
python3 -m pytest tests/ -v                    # 单元测试（143 用例）
python3 scripts/smoke_test_finance_graph.py     # 金融图谱冒烟测试
```

---

## 性能

| 模块 | 加速比 | 说明 |
|------|--------|------|
| `_pivots.c` | **24x** | 极值提取：自适应窗口 + 分形一致性 |
| `_dtw.c` | **132x** | DTW 距离：栈分配 + 工作区复用 |
| `_compiler.c` | **132x** | 批量编译：二分查找 + 批量特征提取 |

---

## 许可证

MIT License

---

> *差异是世界的本质，结构是认知的桥梁。*
