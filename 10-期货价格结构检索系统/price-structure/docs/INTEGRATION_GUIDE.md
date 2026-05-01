# 集成指南 — 已完成

> 本文档记录的集成步骤已全部完成。保留作为历史参考。

## 已集成模块

### 数据层
- `src/data/local_store.py`：Parquet 本地数据仓库
- `src/data/batch_fetcher.py`：全市场批量采集器
- `src/data/sina_fetcher.py`：新浪数据源（国内期货/外盘/外汇）

### C 扩展
- `src/fast/_pivots.c`：极值提取（24x 加速）
- `src/fast/_dtw.c`：DTW 距离（132x 加速）
- `src/fast/_compiler.c`：编译器加速（132x 加速）

### 多时间维度
- `src/multitimeframe/comparator.py`：跨尺度一致性检查

### 知识图谱
- `src/graph/store.py`：GraphStore 持久化
- `src/graph/__init__.py`：StructureGraph
- `src/graph/narrative_tracker.py`：叙事递归追踪
- `src/graph/reflexivity.py`：反身性闭环检测
- `src/graph/transfer_network.py`：跨品种传导网络
- `src/graph/product_ingester.py`：多品种知识导入器

### 知识层
- `src/knowledge/engine.py`：KnowledgeEngine
- `src/knowledge/result.py`：KnowledgeResult

### 配置
- `config/products/`：7品种知识配置
- `knowledge/`：L1/L2/L3 YAML 规则库

---

*集成日期：2026-04-24 ~ 2026-05-01*
