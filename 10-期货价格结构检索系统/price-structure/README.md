# 价格结构形式系统

> 从期货价格序列中提取结构不变量（Structural Invariant），通过四层相似度检索历史先例，辅助交易决策。

## 这是什么

本系统是一套期货价格结构的研究底座。研究对象是价格序列中反复出现的结构性形态——围绕关键区（Zone）组织的、由速度比/时间比/试探聚集度等度量定义的投影不变量。

核心能力包括：结构编译器（从原始 K 线到完整结构描述的四层流水线）、四层相似度检索（几何/关系/运动/族）、质量分层、跨品种共振检测、多时间维度对比、以及交易信号生成。

技术栈：Python + dataclass + NumPy + Pandas + Plotly + Streamlit，关键路径由 C 扩展加速。

## 快速开始

```bash
cd price-structure
pip install -r requirements.txt

# 编译 C 扩展（可选，无 C 编译器会自动 fallback 到 Python）
python3 setup_fast.py build_ext --inplace

# 编译并查看结果
python3 -c "
from src.data.loader import load_cu0
from src.compiler.pipeline import compile_full, CompilerConfig
loader = load_cu0()
bars = loader.get(start='2025-01-01', end='2026-04-01')
result = compile_full(bars, CompilerConfig(min_amplitude=0.03), symbol='CU000')
for s in result.structures[:3]:
    m = s.motion
    print(f'Zone={s.zone.price_center:.0f}  motion={m.phase_tendency}  flux={m.conservation_flux:+.2f}')
"

# 启动研究工作台
streamlit run src/workbench/app.py
```

## 项目结构

```
price-structure/
├── src/
│   ├── models.py              # 对象模型定义
│   ├── relations.py           # 关系算子 + 运动态 + 投影觉知 + 守恒检查
│   ├── compiler/              # 价格→结构编译器（四层流水线）
│   ├── data/                  # 数据层（CSV/MySQL/Parquet）
│   ├── dsl/                   # 规则引擎
│   ├── retrieval/             # 相似性检索（四层模型）
│   ├── sample/                # 样本库
│   ├── learning/              # 学习模型
│   ├── graph/                 # 知识图谱
│   ├── multitimeframe/        # 多时间维度对比
│   ├── fast/                  # C 扩展（极值提取/DTW/编译器加速）
│   └── workbench/             # 研究工作台（Streamlit 六页布局）
├── scripts/                   # 批量编译、扫描、检索脚本
├── data/                      # 数据文件
├── docs/                      # 文档体系
├── tests/                     # 测试
├── config.yaml                # 配置
└── requirements.txt           # 依赖
```

## 核心概念

系统从原始 K 线数据出发，逐层抽象，形成完整的价格结构描述：

- **极值点（Pivot）**：价格序列中的局部极大/极小值，强制交替出现
- **段（Segment）**：两个相邻极值点之间的连线，携带方向和幅度信息
- **关键区（Zone）**：多个极值点聚集形成的价位区间，有共同的反差（Contrast）驱动
- **循环（Cycle）**：价格围绕 Zone 的一次完整试探过程，携带速度比/时间比等不变量
- **结构（Structure）**：Zone + 多个 Cycle 的组合，携带运动态（MotionState）和投影觉知（ProjectionAwareness）
- **系统态（SystemState）**：结构 × 运动的完整封装，包含差异分层和稳定性判定

详细定义见 [`docs/04_对象模型.md`](docs/04_对象模型.md) 和 [`docs/01_总纲.md`](docs/01_总纲.md)。

## 文档索引

| 文档 | 内容 |
|------|------|
| [`docs/01_总纲.md`](docs/01_总纲.md) | 系统定位、研究目标、核心命题 |
| [`docs/02_术语表.md`](docs/02_术语表.md) | 术语定义和对象词典 |
| [`docs/03_弱公理.md`](docs/03_弱公理.md) | 弱公理体系和可证伪研究假设 |
| [`docs/04_对象模型.md`](docs/04_对象模型.md) | 对象模型定义 |
| [`docs/05_数据字典.md`](docs/05_数据字典.md) | 数据字段定义 |
| [`docs/06_结构DSL规范.md`](docs/06_结构DSL规范.md) | 结构 DSL 规范 |
| [`docs/07_样本库.md`](docs/07_样本库.md) | 样本定义、Schema、标注流程、质量标准 |
| [`docs/08_相似性定义.md`](docs/08_相似性定义.md) | 四层相似度模型 |
| [`docs/09_验证规范.md`](docs/09_验证规范.md) | 验证原则、切分方案、评估指标 |
| [`docs/10_信号设计.md`](docs/10_信号设计.md) | 交易信号设计：Signal 对象、假突破模式、5 维评分 |
| [`docs/11_流程梳理.md`](docs/11_流程梳理.md) | 端到端流程梳理 |
| [`docs/12_检索功能升级设计.md`](docs/12_检索功能升级设计.md) | 检索功能升级设计 |
| [`docs/13_主动匹配.md`](docs/13_主动匹配.md) | 主动匹配：用户主动拉取历史相似案例 |
| [`docs/14_多时间维度.md`](docs/14_多时间维度.md) | 多视角交集分析与信号设计方法论 |
| [`docs/SUMMARY.md`](docs/SUMMARY.md) | 项目摘要 |
| [`CHANGELOG.md`](CHANGELOG.md) | 变更记录 |

## 测试

```bash
python3 -m pytest tests/ -v
```

## 性能

C 扩展加速（`src/fast/`）：

| 模块 | 加速比 | 说明 |
|------|--------|------|
| `_pivots.c` | 24x | 极值提取：自适应窗口 + 分形一致性 + 强制交替 |
| `_dtw.c` | 132x | DTW 距离 + 编辑距离：栈分配 + 工作区复用 |
| `_compiler.c` | 132x | 二分查找 bar 过滤 + 批量相似度 + 批量特征提取 |

无 C 编译器时自动 fallback 到 Python 实现。
