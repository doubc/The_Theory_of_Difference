# 集成指南

> 将升级模块整合到 price-structure 项目的步骤。

---

## 一、文件放置

将以下文件复制到项目对应位置：

```
price-structure/
├── src/
│   ├── data/
│   │   ├── local_store.py          ← 本地 Parquet 数据仓库
│   │   └── batch_fetcher.py        ← 全市场批量采集器
│   ├── fast/
│   │   ├── __init__.py             ← C 扩展 Python 包装器
│   │   ├── _pivots.c               ← 极值提取 C 扩展
│   │   ├── _dtw.c                  ← DTW 距离 C 扩展
│   │   └── setup.py                ← C 扩展构建脚本
│   └── multitimeframe/
│       ├── __init__.py             ← 包初始化
│       └── comparator.py           ← 多时间维度对比器
├── scripts/
│   ├── batch_compile.py            ← 批量编译脚本
│   └── multitimeframe_scan.py      ← 多时间维度扫描
└── requirements.txt                ← 更新：新增依赖
```

---

## 二、依赖更新

在 `requirements.txt` 中添加：

```
pyarrow>=12.0.0       # Parquet 读写
duckdb>=0.9.0         # 嵌入式 OLAP 查询（可选）
numpy>=1.24.0         # C 扩展依赖
```

---

## 三、编译 C 扩展

```bash
cd price-structure
pip install numpy pyarrow

# 编译 C 扩展
cd src/fast
python setup.py build_ext --inplace
cd ../..

# 验证
python -c "from src.fast import has_c_extension; print('C ext:', has_c_extension())"
```

如果没有 C 编译器，系统会自动 fallback 到纯 Python 实现（仍然比原来快，因为用了 NumPy 向量化）。

---

## 四、数据迁移

### 4.1 将现有 CSV 数据迁移到 Parquet

```python
from src.data.local_store import LocalStore, LocalStoreConfig
from src.data.loader import CSVLoader

store = LocalStore(LocalStoreConfig())

# 迁移 cu0.csv
loader = CSVLoader("data/cu0.csv", symbol="CU000")
bars = loader.bars
count = store.save_bars("CU000", bars, freq="1d")
print(f"已迁移 CU000: {count} 行")
```

### 4.2 批量采集全市场数据

```bash
# 全市场日线采集
python -m src.data.batch_fetcher --freq 1d --workers 8

# 全市场5分钟线采集
python -m src.data.batch_fetcher --freq 5m --workers 8

# 指定品种
python -m src.data.batch_fetcher --symbols cu0,al0,rb0,i0

# 智能增量更新（只更新过期合约）
python -m src.data.batch_fetcher --smart --max-age 2
```

### 4.3 验证数据

```python
from src.data.local_store import open_store

store = open_store()
print(store.stats())
print(store.list_symbols())
print(store.symbol_info("CU000"))
```

---

## 五、使用新功能

### 5.1 快速极值提取（C 加速）

```python
from src.fast import extract_pivots_fast

# 直接替代 pivots.extract_pivots
pivots = extract_pivots_fast(
    prices,
    min_amplitude=0.03,
    base_window=3,
    adaptive=True,
    fractal_threshold=0.34,
)
```

### 5.2 快速 DTW 相似度

```python
from src.fast import dtw_similarity_fast, dtw_distance_fast

# 替代 similarity.dtw_similarity
score = dtw_similarity_fast(seq1, seq2)
dist = dtw_distance_fast(seq1, seq2)

# 批量
from src.fast import batch_dtw_similarity
scores = batch_dtw_similarity(query_seq, candidate_seqs)
```

### 5.3 全市场批量编译

```bash
# 全市场日线编译
python scripts/batch_compile.py --parallel 4

# 指定品种
python scripts/batch_compile.py --symbols cu0,al0,rb0

# 5分钟线编译
python scripts/batch_compile.py --freq 5m --parallel 2
```

### 5.4 多时间维度对比

```bash
# 全市场扫描
python scripts/multitimeframe_scan.py --top 20

# 单品种详细对比
python scripts/multitimeframe_scan.py --detail cu0

# 指定时间范围
python scripts/multitimeframe_scan.py --start 2026-01-01 --end 2026-04-01
```

```python
from src.multitimeframe.comparator import compare_timeframes
from src.data.local_store import open_store

store = open_store()
report = compare_timeframes("CU0", store, start="2026-01-01")
print(report.summary())
```

---

## 六、兼容性

- **完全向后兼容**：所有旧代码无需修改
- **渐进式升级**：可以只用部分模块
- **C 扩展可选**：没有编译器也能用 Python fallback
- **数据格式兼容**：CSV/MySQL 仍然支持，Parquet 是额外选项

---

*相关文件：`src/fast/__init__.py` · `src/data/local_store.py` · `src/data/batch_fetcher.py` · `src/multitimeframe/comparator.py`*
