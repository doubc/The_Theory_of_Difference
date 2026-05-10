# Real_World — 差异结构推理机

## 项目定位

基于差异论的可运行推理系统。输入差异源，输出差异运动轨迹与稳态判断。

系统回答：**当前主要差异源 → 经哪些通道转移 → 通道是否拥堵 → 谁在承接 → 谁可能退出 → 最可能滑向哪个稳态 → 参数变动后的轨迹变化。
**

## 第一阶段

- 落脚点：商品期货（单品种玩具模型）
- 虚构品种 RW-Copper / ToyMetal
- YAML 输入，输出轨迹/状态/Markdown 报告

## 核心机制

差异 → 转移 → 守恒 → 最小变易 → 最近稳态 → 锁定

## 快速开始

```bash
pip install -r requirements.txt
python -m Real_world.engine.runner experiments/futures/exp_001_inventory_basis.yaml
```

## 项目结构

```text
real_world/
  core/        核心对象（World, Difference, Entity, Channel, State, Trace）
  engine/      推理引擎（转移、守恒、最小变易、稳态、锁定、破缺）
  domains/     领域模型（futures/商品期货, social/社会系统接口）
  io/          输入输出（YAML/JSON 加载, 结果写出）
  reporting/   报告生成（Markdown, 解释说明）
  visualization/ 可视化（Mermaid, Graph）
experiments/   实验配置
outputs/       输出目录
tests/         测试
```

## 铁律

- 不改第一性定义
- 不改写为价格预测/交易信号系统
- 不引入真实下单
- 不把差异清零
- 不只给结论必给路径
- 不把最近稳态解释为最优
- 不把模拟解释为现实预测