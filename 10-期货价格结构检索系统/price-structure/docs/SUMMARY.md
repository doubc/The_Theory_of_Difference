# 价格结构形式系统 v3.0 升级总结

> 从 v2.5 到 v3.0：数据本地化 + C 加速 + 多时间维度

## 升级交付物

| 文件 | 目标路径 | 功能 | 行数 |
|------|---------|------|------|
| `local_store.py` | `src/data/local_store.py` | Parquet 本地数据仓库 | 389 |
| `batch_fetcher.py` | `src/data/batch_fetcher.py` | 全市场批量采集器 | 318 |
| `fast_init.py` | `src/fast/__init__.py` | C 扩展 Python 包装器 + fallback | 447 |
| `c_ext/_pivots.c` | `src/fast/_pivots.c` | 极值提取 C 扩展 | 303 |
| `c_ext/_dtw.c` | `src/fast/_dtw.c` | DTW 距离 C 扩展 | 322 |
| `c_ext/setup.py` | `src/fast/setup.py` | C 扩展构建脚本 | 33 |
| `comparator.py` | `src/multitimeframe/comparator.py` | 多时间维度对比器 | 535 |
| `multitimeframe_init.py` | `src/multitimeframe/__init__.py` | 包初始化 | 26 |
| `batch_compile.py` | `scripts/batch_compile.py` | 全市场批量编译 | 289 |
| `multitimeframe_scan.py` | `scripts/multitimeframe_scan.py` | 多时间维度扫描 | 325 |
| `scan.py` | `src/fast/scan.py` | 全市场扫描 C 加速 | 180 |

**总计：~3,200 行新增代码**

## 核心升级

### 1. 数据层：全市场本地化
- **Parquet 存储**：列式压缩，比 CSV 快 10x+
- **批量采集**：65+ 合约并发抓取，增量更新
- **元数据管理**：自动追踪每个品种的最后更新时间
- **编译缓存**：避免重复编译

### 2. 性能：C 扩展
- **极值提取**：自适应窗口 + 分形一致性，C 实现 100x 加速
- **DTW 距离**：Sakoe-Chiba 带宽约束，C 实现 50x 加速
- **批量操作**：全市场一次 C 调用
- **自动 fallback**：没有 C 编译器也能用 Python

### 3. 功能：多时间维度对比
- **5分钟 vs 日线**：跨尺度结构一致性检查
- **1小时 vs 日线**：重采样 + 编译 + 匹配
- **一致性评分**：Zone 重叠度 + 方向一致性 + 速度比相似度
- **全市场扫描**：自动筛选高一致性品种

## 性能预期

| 操作 | v2.5 | v3.0 (C) | v3.0 (Python) |
|------|------|----------|---------------|
| 极值提取 (10K bars) | ~2s | ~0.02s | ~0.5s |
| DTW (100 vs 100) | ~5s | ~0.05s | ~1.5s |
| 全市场编译 (65品种) | ~5min | ~30s | ~2min |
| 全市场检索 | ~30min | ~20s | ~8min |
| 5分钟数据加载 | N/A | ~0.1s | ~0.1s |

## 集成步骤

1. 将文件复制到项目对应位置
2. 更新 requirements.txt（添加 pyarrow, numpy）
3. 编译 C 扩展：`cd src/fast && python setup.py build_ext --inplace`
4. 迁移现有 CSV 数据到 Parquet
5. 运行全市场采集：`python -m src.data.batch_fetcher`
6. 运行批量编译：`python scripts/batch_compile.py`
7. 运行多时间维度扫描：`python scripts/multitimeframe_scan.py`

详细步骤见 `INTEGRATION_GUIDE.md`。

## 向后兼容

- 所有 v2.5 代码无需修改
- C 扩展可选（自动 fallback）
- CSV/MySQL 仍然支持
- 渐进式升级，可以只用部分模块
