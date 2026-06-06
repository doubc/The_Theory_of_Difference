# Difference World Engine — Project Map

差异论局部世界实验机。

## 一句话定义

在差异论九公理约束下，构造有限离散世界，观察稳定结构能否递归生成高层单元。

## 工程坐标系（Phase 10 最终状态）

| 层 | 说明 | 状态 |
|---|---|---|
| T | Theory，理论来源 | ✅ COMPLETE (`docs/theory_synthesis_v1.md`) |
| ACL | Axiomatic Constraint Language，公理约束语言 | ✅ COMPLETE (`acl/axioms_v2.py`，九公理严格化) |
| L | Layer，层级世界规格 | ✅ COMPLETE (L0-L3 四层工程验证完毕) |
| E | Engine，世界演化引擎 | ✅ COMPLETE (CSC + NSE + NRC + Booster 全螺旋) |
| M | Model，学习模型 | ✅ COMPLETE (NarrativeRecursionOperator, DifferenceSignal) |
| V | Validator，验证器 | ✅ COMPLETE (996 tests, 46 test files) |
| R | Recursion，稳定结构封装与递归 | ✅ COMPLETE (NRC 事件驱动闭环, R→P 改写真实) |
| P | Physics Modules，物理模块 | ⏸️ 已完成理论映射（引力势验证、维度锁定V2），未做子空间分解 |
| D | Documentation，文档与理论回写 | ✅ COMPLETE (phase summaries 覆盖 1-9 + 理论综合 v1 + 架构参考 v1) |

## 核心流程（四层递进）

```
A1(源, +1) → A6(流向) → A3(局域) → A4(最小变易)
    → A7(稳定结构形成)
    → A5(守恒残差检测)
    → A9(升维触发)
    → 粗粒化封装
    → 新层继续运行
```

### 工程实现的等价路径

```
P(状态空间) → E(演化) → M(度量) → S(结构涌现) → R(递归) → P'(重写空间)
     ↑                                                        |
     └──────────────────────── R→P 反馈 ──────────────────────┘
```

## 公理分类

| 公理 | 类别 | 角色 | 工程验证 |
|------|------|------|---------|
| A1 差异源 | 观测 | 持续 +1 外部注入 | ✅ 所有实验活跃 |
| A2 离散编码 | 约束 | 状态空间限制 | ✅ 恒有效 |
| A3 局域性 | 约束 | 模型结构保证 | ✅ 恒有效 |
| A4 最小变易 | 约束 | 变化代价 | ✅ 恒有效 |
| A5 守恒 | 约束 | 守恒残差 → 升维压力 | ✅ 恒有效 |
| A6 流向耦合 | 观测 | 源-汇方向性 | ⚠️ DAG 约束可绕过（已知限制） |
| A7 稳定闭合 | 约束 | 活/死/噪声三分 | ✅ 恒有效，事后检测 |
| A8 差异汇 | 观测 | 持续 -1 外部吸收 | ✅ 恒有效 |
| A9 升维触发 | 触发 | 层级升级判定 | ✅ 多隶属封口已集成（Phase 10 P1） |

## 当前阶段

**Phase 10（理论综合与架构归约）— 已全部完成 ✅**

所有 9 个实验阶段完成，引擎功能完整，理论回写完毕。

### 组件状态（按 Phase 顺序）

#### Phase 1：基础演化器
| 组件 | 文件 | 状态 |
|------|------|------|
| 长程演化器（旧版） | `engine/long_range_evolver_v2.py` | ✅ |
| 空间演化器 | `engine/spatial_evolver_v2.py` | ✅ |

#### Phase 2：象界 → 前主体态（13+ 组件）
| 组件 | 文件 | 状态 |
|------|------|------|
| 层级管理 | `engine/hierarchy_manager.py` | ✅ |
| 封装引擎 | `engine/encapsulation_engine.py` | ✅ |
| 跨层级引力调节 | `engine/cross_layer_gravity.py` | ✅ |
| 底象检测器 | `engine/xiang_detector.py` | ✅ |
| 偏置记忆 | `engine/persistent_bias_memory.py` | ✅ |
| 累积筛选器 | `engine/cumulative_selector.py` | ✅ |
| 回流通道 | `engine/return_flow_channel.py` | ✅ |
| 六阈值检测器 | `engine/six_threshold_detector.py` | ✅ |
| 第七阈值检测器 | `engine/seventh_threshold_detector.py` | ✅ |
| 前主体态收束 | `engine/pre_subjectivity_convergence.py` | ✅ |
| 解封机制 | `engine/unsealing_mechanism.py` | ✅ |
| 组织密度指数 (ODI) | `engine/organizational_density_index.py` | ✅ |
| 自维持循环 | `engine/self_sustaining_circulation.py` | ✅ |
| 功能分化 | `engine/functional_differentiation.py` | ✅ |
| 复制模式 | `engine/replicate_pattern.py` | ✅ |
| 协同涌现检测器 | `engine/cooperative_emergence_detector.py` | ✅ |
| 横向耦合器 | `engine/lateral_coupling.py` | ✅ |
| 功能信号耦合 | `engine/functional_signal_coupling.py` | ✅ |

#### Phase 3：前主体 → 最小自我
| 组件 | 文件 | 状态 |
|------|------|------|
| 最小自我检测器 (MSI) | `engine/minimal_self_detector.py` | ✅ |
| 预期偏置引擎 | `engine/anticipatory_bias_engine.py` | ✅ |
| 反事实推理引擎 | `engine/counterfactual_engine.py` | ✅ |
| 全局偏置约束 (GBC) | `engine/global_bias_constraint.py` | ✅ |

#### Phase 4：叙事自我与跨尺度耦合
| 组件 | 文件 | 状态 |
|------|------|------|
| 跨尺度耦合 (CSCI) | `engine/cross_scale_coupling.py` | ✅ |
| 叙事自我涌现 (NSE) | `engine/narrative_self_emergence.py` | ✅ |

#### Phase 5：系统鲁棒性与资源约束
| 组件 | 文件 | 状态 |
|------|------|------|
| CIV 下限 (CIVFloor) | `engine/civ_floor.py` | ✅ |
| 分层指标收集器 | `engine/per_layer_metrics.py` | ✅ |
| 自适应动量控制 | `engine/adaptive_momentum_controller.py` | ✅ |
| 制度层保护器 | `engine/institutional_layer_protector.py` | ✅ |

#### Phase 6：叙事递归闭合 (NRC)
| 组件 | 文件 | 状态 |
|------|------|------|
| 叙事递归闭合 | `engine/narrative_recursive_closure.py` | ✅ |

#### Phase 8：L1 循环检测
| 组件 | 文件 | 状态 |
|------|------|------|
| L1 循环检测器 | `engine/l1_cycle_detector.py` | ✅ |

#### Phase 9：多隶属封口 (A9 渐进式)
| 组件 | 文件 | 状态 |
|------|------|------|
| 多隶属封口 | `engine/multi_membership_seal.py` | ✅ |
| 差异密度追踪 | `engine/difference_density_tracker.py` | ✅ |
| 维度锁定 V2 | `engine/detectors/dimension_locking_v2.py` | ✅ |

## 已完成实验阶段

| 阶段 | 核心问题 | 实验数 | 状态 | 关键结论 |
|------|---------|--------|------|---------|
| Phase 1 | 基础涌现：离散差异空间中的稳定结构 | 3+ | ✅ | 公理约束 + NN 动力学可在 16×16 空间产生 8 种状态 |
| Phase 2 | 象界 → 前主体（生成链八章门槛） | ~15 | ✅ | 13 组件实现全部生成链门槛 |
| Phase 3 | 前主体 → 现象意识的结构条件 | 3 | ✅ | 最小自我 + 预期 + 反事实 + 全局偏置 |
| Phase 4 | 跨尺度双向因果与叙事自我 | 3 | ✅ | CSC TopDown/BottomUp + NSI 涌现 |
| Phase 5 | 多层级动力学、资源约束、长期演化 | 14 (B1-B10, C1-C2, D1) | ✅ | L1 被动约束确认 (Jaccard flux=0.0)；L2 自主动力学；N0*=30 临界 |
| Phase 6 | 叙事递归闭合 (NRC) | 7 (P1-P6) | ✅ | 张力触发 R2 突破；NRC 事件驱动非周期 |
| Phase 7 | 全螺旋集成 (P→E→M→S→R→P') | 1 | ✅ | R→P 改写真实（delta 0.09-0.15） |
| Phase 8 | 跨尺度螺旋耦合 | 5 (P0-P4) | ✅ | L1 = 被动约束提供者，非自主主体 |
| Phase 9 | 鲁棒性测绘 | 6 (P0-P3) | ✅ | 一阶相变 N0≈30.5；N0=24-288 核心涌现零降级 |
| **Phase 10** | **理论综合与架构归约** | **0（无实验）** | **✅** | 理论综合 v1 + 架构最终 v1 + A9 多隶属集成 + Bug 验证 |

## 实验 → 理论核心发现

| # | 发现 | 阶段 | 确定性 |
|---|------|------|-------|
| 1 | **L1 是被动约束投影**，非自主主体（Jaccard flux=0.0） | P5.B8 | ✅ 决定性（10000 步验证） |
| 2 | **层级解耦需要独立差异空间**，不能通过"削弱耦合"实现 | P5.B5 | ✅ 决定性（r=0.032） |
| 3 | **级联耦合递增**：L0→L1 r~0.50, L1→L2 r~0.75, L2→L3 r~0.87, L4+ 无意义 | P5.B10 | ✅ 决定性 |
| 4 | **NRC 是事件驱动**，非周期性振荡器（循环集中在前 500 步） | P6 | ✅ 决定性 |
| 5 | **R2 触发需用累积张力**而非瞬时 NSI（NSI 峰值后衰减，触发永假） | P6.P4 | ✅ 决定性（23/24 种子） |
| 6 | **R→P 改写真实**（level_transition_weights delta 0.09-0.15） | P7 | ✅ 决定性（8/8） |
| 7 | **一阶不连续相变** N0≈30.5：L1 形成率 0→0.438→1.0，绑定强度骤降 50% | P9.P3 | ✅ 决定性（144 次运行，9 N0 值） |
| 8 | **核心涌现不可摧毁**：H1-H8 在 N0=24-288、500-10000 步、12 参数配置下接近完美通过 | P9 | ✅ 决定性 |
| 9 | **NSI 反缩放**：更大 N0 扩散叙事活动，降低峰值 NSI | P9.P0 | ✅ 决定性 |
| 10 | **九机制模拟并行 ≠ 逻辑串行**：所有公理同时作用于每步翻转，理论并行性自动涌现 | P7 回写 | ✅ 决定性 |

## 关键文档索引

| 文档 | 位置 | 说明 |
|------|------|------|
| 理论综合 v1 | `docs/theory_synthesis_v1.md` | 从公理→模拟→验证→理论回写的完整叙事 |
| 最终架构参考 v1 | `docs/arch_final_v1.md` | 模块依赖图 + 数据流 + 参数范围 + 测试覆盖 + 已知限制 |
| Phase 5-9 阶段总结 | `docs/PHASE_SUMMARY_PHASE5to9.md` | 35+ 实验的详细分析 |
| Phase 1-5 阶段总结 | `docs/PHASE_SUMMARY_2026-06-02.md` | 早期阶段总结 |
| Phase 10 规划 | `docs/phase10_planning.md` | Phase 10 设计文档（已全部完成） |
| A9 多隶属设计 | `docs/a9_multi_membership_design.md` | A9 升维触发渐进式封口设计 |
| 九机制并行性 | `docs/theory_nine_mechanisms_parallel_and_phase_transition.md` | 九机制并行性理论回写 |
| 维度锁定方法论 | `docs/dimension_locking_methodology_analysis.md` | D_eff=18.5 测量方法论修复 |

## 已修复 Bug 汇总

| Bug | 发现阶段 | 根因 | 修复结果 |
|-----|---------|------|---------|
| 封口双峰问题 | P5.B6 | 全有/全无封口 | 部分封口机制 ✅ |
| `get_state()` 空 sealed_bits | P5.B9 | 只查 sealed_bits 不查 lateral_sealed_bits | 合并冻结集合 ✅ |
| `active_window` 错位 | P5.C1 | 正确时间戳使窗口过紧 | 规模检查与冻结解耦 ✅ |
| R2 NSI 触发永假 | P6.P1-P4 | NSI 峰值后衰减 | 改用累积张力触发 ✅ |
| GBC 张量尺寸不匹配 | P9.P3 | N 对齐 3 倍但索引未同步 | 自动裁剪/填充 ✅ |
| NarrativeFilter 维度不匹配 | P9.P3 | NRO 跨不同 N0 复用 | 每种子新鲜 NRO ✅ |
| 维度锁定 V1 伪方差 | P9 回写 | 测量方法论问题 | V2 关联维数法 ✅ |

## 工程稳定性统计

| 指标 | 值 |
|------|-----|
| 总实验数 | ~150（Phase 1-9） |
| 总独立运行次数 | ~1000+ |
| 总测试文件数 | 46 |
| 测试通过 | ~995 |
| 测试跳过 | 23 |
| 测试失败 | 0 |
| 引擎组件数 | 35+ |
| 公理引擎 | 9 公理（全部严格实现） |
| 最终参数范围 | N0 ∈ [30, 288], steps ∈ [500, 10000] |
| 一阶相变临界点 | N0* ≈ 30.5 |

## 开放问题与未来方向

| 问题 | 说明 | 方向建议 |
|------|------|---------|
| A6 DAG 约束可绕过 | 演化方向性不完整 | 在 `axioms_v2.py` 中强化 `block_reverse` 逻辑 |
| L0/L1 无自然反馈闭环 | 跨尺度循环不自然涌现 | 理论问题：制度记忆是否需要反馈？ |
| 封口度量提取 Bug | 某些 seed 报告 seal_step=0 | 已于 `test_sealing_fix.py` 确认修复，待整合到标准报告 |
| 子空间未分解 | 引力/弱力/强力/电磁在同一网格演化 | 独立的 Phase 11 方向 |
| 无种群演化 | 单世界演化，无多世界竞争 | 独立扩展方向 |
| 无并行演化 | 九机制在引擎中串行执行 | 理论并行性已证明；工程串行是自然约束 |

## 第一阶段禁止事项（仍适用）

- 不直接声称模拟现实物理
- 不直接做完整引力/电磁/强弱力/量子
- 不训练大模型
- 不用视觉图案替代验证器

---

*最后更新: 2026-06-06 12:48 CST*
*基于: Phase 1-10 全部完成 + theory_synthesis_v1.md + arch_final_v1.md + PHASE_SUMMARY_PHASE5to9.md*