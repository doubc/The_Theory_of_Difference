# 价格结构形式系统 v3.0 升级计划

> 从 v2.5 到 v3.0：性能、数据、多时间维度的系统性升级。

## 升级总览

| 模块 | v2.5 现状 | v3.0 升级 | 收益 |
|------|----------|----------|------|
| 数据层 | CSV/MySQL，单品种加载 | **Parquet本地化 + DuckDB** | 全市场秒级加载 |
| 数据采集 | 手动单品种 | **批量全市场 + 增量更新** | 65+合约自动同步 |
| 编译器核心 | 纯Python | **C扩展 (pivots/dtw/scan)** | 10-100x加速 |
| 相似度检索 | Python O(n²)扫描 | **NumPy向量化 + C后端** | 检索速度50x提升 |
| 时间维度 | 仅日线 | **5分钟/1小时对比** | 多尺度结构验证 |
| 全市场扫描 | Streamlit单线程 | **并行编译 + 本地缓存** | 分钟级全市场扫描 |
| 对比功能 | 基础跨品种 | **5min对比 + 1h对比 + 跨周期** | 多维度交叉验证 |

## 模块清单

### M1: `src/data/local_store.py` — 本地数据仓库
- Parquet存储引擎
- 批量Sina采集 → Parquet
- 增量更新（只下载新数据）
- DuckDB快速查询接口

### M2: `src/data/batch_fetcher.py` — 全市场批量采集
- 65+合约并发抓取
- 进度追踪 + 断点续传
- 错误重试 + 速率控制

### M3: `src/fast/_pivots.c` — 极值提取C扩展
- 替代 pivots.py 中的热循环
- 自适应窗口 + 分形一致性（C实现）
- NumPy数组直接操作

### M4: `src/fast/_dtw.c` — DTW距离C扩展
- 替代 similarity.py 中的DTW计算
- Sakoe-Chiba带宽约束
- 空间优化 O(m)

### M5: `src/fast/_scan.c` — 全市场扫描C扩展
- 批量编译 + 批量相似度
- SIMD友好的数据布局

### M6: `src/fast/__init__.py` — Python fallback
- 有C扩展用C，没有则fallback到Python
- 自动检测 + 性能报告

### M7: `src/multitimeframe/comparator.py` — 多时间维度对比
- 5分钟结构 vs 日线结构
- 1小时结构 vs 日线结构
- 跨周期一致性评分

### M8: `src/multitimeframe/aligner.py` — 时间对齐器
- 不同频率数据的时间对齐
- 交易时段感知
- 缺失数据插值

### M9: `scripts/batch_compile.py` — 批量编译脚本
- 全市场一键编译
- 结果缓存到本地
- 增量编译（只编译新数据）

### M10: `scripts/multitimeframe_scan.py` — 多时间维度扫描
- 5min + 1h + 1d 三维度扫描
- 一致性报告生成

## 技术决策

1. **C扩展 vs Cython**: 选择纯C扩展 + ctypes/cffi，不引入编译依赖
2. **存储格式**: Parquet（列式压缩，比CSV快10x+）
3. **查询引擎**: DuckDB（嵌入式OLAP，无需服务进程）
4. **向量化**: NumPy数组操作替代Python循环
5. **兼容性**: 所有升级向后兼容，v2.5代码无需修改

## 执行顺序

1. M1 + M2（数据层）→ 先有数据才能测
2. M3 + M4（C扩展核心）→ 性能瓶颈
3. M6（Python fallback）→ 兼容性保障
4. M7 + M8（多时间维度）→ 新功能
5. M5 + M9 + M10（扫描+脚本）→ 集成层
