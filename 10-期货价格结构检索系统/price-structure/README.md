# 价格结构形式系统

> 基于《差异论 V1.6》的期货价格结构研究底座
> 第一年目标：做出一个能稳定描述、识别、比较价格结构的研究底座。

## 理论基础

价格是现实差异的低维压缩投影（影子）。本系统从影子中提取**投影不变量**——
围绕关键区组织的、由速度比/时间比/试探聚集度等度量定义的结构性关系。

核心命题：
- **系统 = 结构 × 运动**：没有运动的结构是死骨架
- **差异守恒**：不能被无代价清零，沿低阻通道转移
- **最近稳态**：系统先滑向最近能稳住的安排，不是最优解

## 快速开始

```bash
cd price-structure
pip install -r requirements.txt

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
│   ├── models.py              # 对象模型: Point→Segment→Zone→Cycle→Structure
│   ├── relations.py           # 关系算子 + 运动态计算 + 投影觉知 + 守恒检查
│   ├── compiler/              # 价格→结构编译器（四层流水线）
│   │   ├── pivots.py          #   极值提取（强制交替）
│   │   ├── segments.py        #   段生成
│   │   ├── zones.py           #   关键区识别（含共同反差推断）
│   │   ├── cycles.py          #   Cycle组装（含最近稳态检测）
│   │   └── pipeline.py        #   统一入口：编译+运动+投影+守恒
│   ├── dsl/                   # 规则引擎
│   ├── retrieval/             # 相似性检索（四层：几何+关系+运动+族）
│   ├── sample/                # 样本库
│   ├── learning/              # 学习模型
│   └── workbench/             # 研究工作台
│       ├── app.py             #   主界面（五页布局）
│       ├── daily_report.py    #   HTML报告渲染
│       └── mini_chart.py      #   图表生成
├── data/                      # 数据
├── docs/                      # 文档体系
├── tests/                     # 测试（73个）
├── config.yaml                # 配置
└── requirements.txt           # 依赖
```

## 研究工作台（五页布局）

运行 `streamlit run src/workbench/app.py`

### 📡 1. 系统总览

全市场结构态一览——每个结构同时显示**是什么（结构）× 在怎么动（运动）× 可信度（投影）**。

- K 线图 + Zone 标注 + 稳态标注
- 结构卡片矩阵：Zone、运动标签、守恒通量条、稳态距离、投影压缩度
- 高压缩结构标 ⚠️ 警告

### 🔬 2. 结构深潜

单个结构的完整解剖，三栏并排：

| 🦴 结构（骨架） | 🌊 运动（趋势） | 👁️ 投影（觉知） |
|---|---|---|
| Zone 价位/带宽 | 阶段趋势 →breakdown | 压缩度 40% |
| 来源/反差类型 | 守恒通量 +0.50 | 可信度 88% |
| Cycles/Phases | 稳态距离/趋近速度 | 盲区通道 |
| 标签/叙事 | 系统时间 | 观测说明 |

附加：Cycle 详情表 + 守恒警告 + K 线图（含稳态标注）

### 🎯 3. 主动匹配

选一个当前结构，系统检索历史相似：

- 四层相似性对比（几何/关系/**运动**/族）
- 样本库检索 + 后验分布（5d/10d/20d 收益）
- 最近稳态验证建议

### 🗺️ 4. 稳态地图

最近稳态的全局视图：

- 所有 Cycle 的稳态价位/到达天数/阻力评分表
- 稳态价位分布直方图
- 阻力评分统计 + 低阻力假稳态警告

### 📝 5. 研究日志

自动生成编译上下文摘要，手动记录研究笔记。

## 对象模型

```
Point → Segment → Zone → Cycle → Structure → Bundle
                                         ↓
                                   MotionState（运动态）
                                   ProjectionAwareness（投影觉知）
```

每个 Structure 携带三重态：
- **结构态**：Zone、Cycles、Phases、invariants
- **运动态**：阶段趋势、守恒通量、稳态趋近、转移路径
- **投影觉知**：压缩度、盲区通道、可信度

## 弱公理

```
A0  价格是影子：价格 = Π(现实差异)，Π 有损、不可逆
A1  价格路径 = 时间有序离散状态序列
A2  结构由点间关系生成，不由单点定义
A3  结构在容差下保持同一性
A4  结构围绕关键区组织，关键区有共同反差驱动
A5  结构通过阶段转换生成、确认、破坏、反演
A6  随机扰动为残差，不参与结构定义
A7  量纲守恒与归一化原则
A8  差异守恒：不能被无代价清零，沿低阻通道转移
A9  最近稳态：系统先滑向最近能稳住的安排，不是最优解
A10 系统 = 结构 × 运动
```

## 文档

- [项目设计书 v2.0](../项目设计书.md)
- [V1.6 形式化定义层](docs/10_V1.6形式化定义.md)
- [弱公理与研究假设](docs/03_弱公理与研究假设.md)
- [理论-代码偏差追踪](docs/theory_code_deviation.md)
- [流程梳理](docs/11_流程梳理.md)

## 测试

```bash
python3 -m pytest tests/ -v
# 73 passed
```

## 技术栈

Python · dataclass · Pandas · Plotly · Streamlit · YAML
