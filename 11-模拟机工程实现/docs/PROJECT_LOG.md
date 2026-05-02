# 差异论模拟机 - 项目日志

## 2026-04-29 工作记录

### 一、做了什么

#### 1. 项目初始化
- 从 doubc/The_Theory_of_Difference 仓库 pull 了 "11-模拟机工程实现" 项目
- 包含完整的差异论模拟机框架

#### 2. 核心模块创建

| 文件 | 描述 | 状态 |
|------|------|------|
| engine/axiom_adapter.py | 引擎+公理适配层 | ✓ 创建 |
| engine/region_classifier.py | 区域分类器 | ✓ 创建 |
| docs/M0_COMPLETE.md | 阶段完成记录 | ✓ |
| docs/M0_STATUS.md | 状态记录 | ✓ |
| docs/M0_TASK.md | 任务记录 | ✓ |

#### 3. 测试结果

| 测试 | 结果 | 说明 |
|------|------|------|
| 简单扩散 (8x8) | 1 unique state | 收敛太快 |
| 简单扩散 (16x16) | 1 unique state | 收敛太快 |
| NN动力学 (16x16) | 8 unique states | 有改善 |
| A2离散编码 | {-1,0,1} | ✓ 工作 |
| A7稳定检测 | 10步不变 | ✓ 工作 |

### 二、什么想法

#### 1. 核心问题
- **纯扩散 = 热方程** → 均匀化 → 无法产生结构
- 需要真正的"差异反应堆"动力学

#### 2. 尝试的方案

| 方案 | 思路 | 结果 |
|------|------|------|
| 移动差异源 | 源不是固定在边界而是移动 | 中间被吸空 |
| 环形边界 | 上下左右封口循环 | 差异出不来 |
| NN动力学 | LocalConvModel预测 | 8种状态 ✓ |

#### 3. 架构理解

```
差异论模拟机架构:
├── acl/axioms.py      # 9条公理定义
├── engine/         # 模拟循环
│   ├── world_engine.py
│   ├── axiom_adapter.py  # 本次创建
│   └── region_classifier.py  # 本次创建
├── layers/        # 状态层
├── models/       # 神经网络动力学
│   └── local_conv_model.py  # 9857参数CNN
└── docs/         # 文档
```

- **公理分类**:
  - 约束类 (A2/A3/A4/A5/A7): 参与loss计算
  - 观测类 (A1/A6/A8): 记录但不直接影响演化
  - 触发类 (A9): 升维判定

- **真正的动力学**: Layer + Model，而非公理本身

### 三、什么没有做

1. **公理约束未真正接入**
   - axiom_adapter.py 中的 check_all() 只是占位
   - 需要连接到 acl/axioms.py 的真实实现

2. **Phase 1 未开始**
   - 目标: 50-100 cells, 1000步内涌现100+步稳定结构
   - 当前: 16x16, NN动力学, 8种状态

3. **神经网络训练未实现**
   - LocalConvModel 没有训练过
   - 只是作为确定性动力学运行

### 四、下一步 (按优先级)

1. **高优先级**
   - 连接公理约束到引擎
   - Phase 1: 基础涌现实验

2. **中优先级**
   - 训练 LocalConvModel
   - 实现 A1 差异注入层

3. **低优先级**
   - 2D升维
   - 递归生成

---

## 项目信息

- GitHub: doubc/The_Theory_of_Difference
- 本地: C:\Users\Administrator\source\repos\doubc\The_Theory_of_Difference
- 分支: 11-模拟机工程实现

## 记录时间
2026-04-29 08:32 GMT+8