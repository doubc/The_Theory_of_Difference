# M1 完成 - 差异反应堆

## 日期
2026-04-29

## 状态
M1 阶段完成 (差异反应堆 + 公理约束训练)

## 已实现模块

| 模块 | 文件 | 状态 |
|------|------|------|
| 增强 CNN 模型 | models/local_conv_model.py | 残差连接 + 反应分支 |
| 差异反应堆 | engine/reactor.py | 反应-扩散动力学 |
| 公理训练器 | engine/trainer.py | 公理约束训练循环 |
| 1D 实验 | experiments/exp_1d_reactor.py | 可运行 |
| 2D 实验 | experiments/exp_2d_reactor.py | 可运行 |
| 世界引擎 | engine/world_engine.py | 集成 reactor + trainer |

## 核心改进

### 1. LocalConvModel 增强
- 残差连接：output = sigmoid(conv(x) + x)
- 反应分支：1x1 卷积 + tanh 非线性
- 可学习反应强度参数

### 2. 差异反应堆 (DifferenceReactor)
- 模型预测 + 公理损失可微分
- 源/汇边界条件（开放系统）
- NaN 保护

### 3. 公理损失函数
- A2: 离散性（惩罚中间值）
- A4: 最小变易（惩罚大变化）
- A5: 守恒（相对残差）
- A7: 稳定性（模式持续性）
- 空间多样性（梯度 + 值分布）

### 4. 空间多样性损失
- 梯度多样性：鼓励空间梯度非零
- 值多样性：鼓励 0 和 1 共存
- 打破均匀化（热寂）

## 测试结果

### 1D 实验 (50 cells, 30 episodes)
```
Loss reduction: 92.1%
A2 (discreteness): 0.01
A5 (conservation): 0.0006
std: 0.39
unique values: 2
stable structures: 1
```

### 2D 实验 (32x32, 20 episodes)
```
Loss reduction: 79.4%
A2 (discreteness): 0.004
A5 (conservation): 0.000024
std: 0.46
active ratio: 0.31
max gradient: 1.0
stable structures: 1
```

## 关键发现

1. **公理约束训练有效**：模型通过最小化公理违背度学会产生离散、守恒的状态
2. **空间多样性是关键**：单纯扩散导致均匀化，需要显式鼓励空间结构
3. **值多样性比梯度多样性更有效**：直接奖励 0 和 1 共存比鼓励梯度更稳定
4. **2D 比 1D 更容易产生结构**：更多空间自由度 → 更丰富的模式

## 运行方式

```bash
cd "D:\python work\The_Theory_of_Difference\11-模拟机工程实现"

# 冒烟测试
python run_experiment.py test

# 1D 实验
python run_experiment.py 1d

# 2D 实验
python run_experiment.py 2d
```

## 下一步 (M2)

1. **放大规模**：64x64, 128x128
2. **更长训练**：100+ episodes
3. **结构检测升级**：连通区域分析
4. **粗粒化映射**：L0 → L1 升维
5. **可视化**：状态演化动画

## Git
doubc/The_Theory_of_Difference/11-模拟机工程实现
