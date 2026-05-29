# Difference World Engine — Project Map

差异论局部世界实验机。

## 一句话定义

在差异论九公理约束下，构造有限离散世界，观察稳定结构能否递归生成高层单元。

## 工程坐标系

| 层 | 说明 | 状态 |
|---|---|---|
| T | Theory，理论来源 | — |
| ACL | Axiomatic Constraint Language，公理约束语言 | in progress |
| L | Layer，层级世界规格 | in progress |
| E | Engine，世界演化引擎 | in progress |
| M | Model，学习模型 | planned |
| V | Validator，验证器 | in progress |
| R | Recursion，稳定结构封装与递归 | in progress |
| P | Physics Modules，物理模块 | future |
| D | Documentation，文档与理论回写 | in progress |

## 核心流程

```
A1(源, +1) → A6(流向) → A3(局域) → A4(最小变易)
    → A7(稳定结构形成)
    → A5(守恒残差检测)
    → A9(升维触发)
    → 粗粒化封装
    → 新层继续运行
```

## 公理分类

| 公理 | 类别 | 角色 |
|------|------|------|
| A1 差异源 | 观测 | 持续 +1 外部注入 |
| A2 离散编码 | 约束 | 状态空间限制 |
| A3 局域性 | 约束 | 模型结构保证 |
| A4 最小变易 | 约束 | 变化代价 |
| A5 守恒 | 约束 | 守恒残差 → 升维压力 |
| A6 流向耦合 | 观测 | 源-汇方向性 |
| A7 稳定闭合 | 约束 | 活/死/噪声三分 |
| A8 差异汇 | 观测 | 持续 -1 外部吸收 |
| A9 升维触发 | 触发 | 层级升级判定 |

## 当前阶段

**Phase 2（象界 → 前主体态）— 进行中**

M4 批次 11 已完成：分层封装、九公理严格化、汉明几何、引力势验证、跨层级引力调制。

### Phase 2 组件状态

| 组件 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 底象检测器 | `xiang_detector.py` | ✅ | Phase 2 P0 #1 |
| 偏置记忆 | `persistent_bias_memory.py` | ✅ | Phase 2 P0 #2 + 保持深度追踪器 |
| 累积筛选器 | `cumulative_selector.py` | ✅ | Phase 2 P0 #3 |
| 回流通道 | `return_flow_channel.py` | ✅ | Phase 2 P0 — 高语义锚定/剥离 |
| 六阈值检测器 | `six_threshold_detector.py` | ✅ | Phase 2 P1 #1 |
| 前主体态收束 | `pre_subjectivity_convergence.py` | ✅ | Phase 2 P1 #2 + 语义防火墙 |
| 解封机制 | `unsealing_mechanism.py` | ✅ | Phase 2 P1 — L1/L2/L3 分级解封 + 界面模式稳定性 |
| 组织密度指数 | `organizational_density_index.py` | ✅ | Phase 2 P1 — 六子指数加权 + 五密度分区 + 十一子区系统 |
| 第七阈值检测器 | `seventh_threshold_detector.py` | ✅ | Phase 2 P1 — 三信号融合 + 子区跃进检测 |
| 协同涌现检测器 | `cooperative_emergence_detector.py` | ✅ | Phase 2 P1 — 五类协同信号 |
| 自维持循环 | `self_sustaining_circulation.py` | ✅ | Phase 2 P2 #1 |
| 功能分化 | `functional_differentiation.py` | ✅ | Phase 2 P2 #2 |
| 复制模式 | `replicate_pattern.py` | ✅ | Phase 2 P2 #3 |
| HierarchicalEvolver 集成 | `hierarchical_evolver.py` | ✅ | ODI + 第七阈值 + 协同涌现已集成到 Phase 2 callback |
| 横向耦合机制 | `lateral_coupling.py` | ✅ | Phase 2 P2 #4 — 同层结构间三种耦合模式 |

### 已完成里程碑

| 阶段 | 日期 | 状态 | 说明 |
|------|------|------|------|
| M0 | 2026-04 | ✅ | 骨架代码、公理接口、层级基础 |
| M1 | 2026-04-29 | ✅ | 差异反应堆 + 公理约束训练 |
| M1.1 | 2026-04-29 | ✅ | 语义修复 + 测试 + 流量平衡 |
| M2 | 2026-05-06 | ✅ | 稳定结构验证器 + 粗粒化映射 + 实验日志 |
| M3 | 2026-05-11 | ✅ | 第一阶段验收 — 全量测试通过 |
| M4 | 2026-05-14~27 | ✅ | Phase 2 核心组件实现（13个新组件，752+测试） |

### 下一步

1. ~~reactor.py 中集成回流通道 step~~ ✅ *（已替代：直接在 `hierarchical_evolver.py` 中集成）*
2. ~~横向耦合机制~~ ✅
3. Phase 3 规划：前主体态 → 现象意识的结构条件
4. ~~LateralCoupler 集成到 HierarchicalEvolver Phase 2 callback~~ ✅

## 第一阶段禁止事项

- 不直接声称模拟现实物理
- 不直接做完整引力/电磁/强弱力/量子
- 不训练大模型
- 不用视觉图案替代验证器
