# 价格结构形式系统

研究价格路径中的关系不变量——结构本体、编译、检索、学习。

## 快速开始

```bash
cd price-structure
pip install -r requirements.txt
```

## 项目结构

```
price-structure/
├── docs/              # 文档体系
│   ├── 01_总纲.md
│   ├── 02_术语与对象词典.md
│   ├── 03_弱公理与研究假设.md
│   └── 04_数据字典.md
├── src/
│   ├── __init__.py
│   ├── models.py      # 对象模型（Point/Segment/Zone/Cycle/Structure）
│   ├── data/          # 数据层
│   │   ├── loader.py  # MySQL → 统一接口
│   │   └── schema.py  # 数据 Schema 定义
│   ├── compiler/      # 结构编译器
│   ├── dsl/           # 规则引擎
│   ├── sample/        # 样本库
│   ├── retrieval/     # 相似性检索
│   ├── learning/      # 学习模型
│   └── workbench/     # 研究界面
├── tests/             # 测试
├── scripts/           # 脚本
├── data/              # 本地数据
└── config.yaml        # 项目配置
```

## 当前阶段

**阶段 0: 立项** — 文档固化中
**阶段 1: 数据基础** — 等待样本数据
