# 模拟机工程项目代码审阅

> 审阅时间：2026-05-11
> 审阅范围：`11-模拟机工程实现` 目录核心文件
> 审阅方式：基于 GitHub 仓库代码级阅读

---

## 总体判断

这套工程不是"乱写能跑"的原型，而是已经有清晰意图的第一阶段研究型代码。

**优点**：理论映射意识强、模块边界初步存在、测试意识存在、日志和验证器已经进入主流程。

**典型一阶段问题**：接口语义还没有完全收束、部分实现和抽象层有偏差、一些 shape/广播/统计逻辑存在隐性 bug 风险、验证器与结构检测之间存在"名义一致但数学口径未完全统一"。

---

## 一、Layer 抽象与实现的语义偏差

`LayerBase` 设计得很好——层级对象统一为状态空间、差异度量、源/汇、稳定性、粗粒化、升维压力、公理权重。但 L0/L1 实现还没有做到严格语义一致。

**关键问题**：`L0BinaryLattice.measure_difference()` 在 1D、2D、双方向时的 tensor 形状不一致。1D 直接返回 `dx`，2D 做裁剪后平均。

**建议**：`measure_difference()` 改成同型输出——内部仍按边计算，末尾 pad 回原尺寸。

---

## 二、L0BinaryLattice 实质性 bug 风险

### 1. `inject_difference()` 维度可能写错

```python
mask = torch.rand(state.shape[0], 1, self.shape[0], width, device=self.device) < 0.08
```

用 `self.shape[0]` 而非 `state.shape[-2]`。batch、channel、shape 解耦后会出问题。

**建议**：
```python
b, c, h, w = state.shape
mask = torch.rand(b, c, h, width, device=state.device) < p
```

同时 `width = min(3, max(1, w // 4))` 比 `self.shape[-1] // 4` 更稳。

### 2. WorldEngine 升维后状态续接逻辑失配

`WorldEngine.run()` 升维后检查 `hasattr(self.layer, 'coarse_grain_state')`，但 L0BinaryLattice 没有实例方法 `coarse_grain_state`——只有 `layers/coarse_grain.py` 里的模块函数。于是大概率走 `else`，升维后重新随机初始化。

**建议**：在 `LayerBase` 加 `project_to_next_layer()` 抽象方法，L0 实现它显式调用 `coarse_grain_state()`，WorldEngine 不猜测方法存在性。

### 3. AxiomEngine.evaluate() 和 DifferenceReactor._compute_axiom_loss() 是两套系统

公理抽象存在，但主训练回路不依赖它——reactor 自己手写了 A2/A4/A5/A7 + spatial_diversity。

**建议**：把可抽象项回收进 AxiomEngine，损失定义只在一处维护。reactor 只负责模型前向、边界条件、调用 axiom engine、返回 loss/report。

---

## 三、稳定结构检测与验证未完全闭合

检测器 `L0BinaryLattice.detect_stable_structures()` 已引入：时间稳定性、连通分量分离、边界闭合、物质更替率、结构间交互、跨窗口生命周期追踪——接近"活结构/死结构/噪声"区分的工程原型。

但验证器和检测器的术语口径不一致：

| 概念 | 检测器定义 | 验证器定义 | 问题 |
|------|-----------|-----------|------|
| closure | perimeter/area 归一化（边界紧致度） | 最大连通域/总稳定区域（连通完整度） | 同名异义 |
| interaction | 共存次数统计（时间共现） | 中心距离<阈值（空间接近） | 同名异义 |

**建议**：
- 拆分为 `connectivity_ratio`（最大连通域占比）和 `boundary_closure_score`（边界闭合度）
- 拆分为 `spatial_interaction` 和 `temporal_coexistence`
- `StableStructure.source_trace` 中同时记录二者

---

## 四、验证器需要两个修正

### 1. `validate_single()` 过度信任传入的 boundary_map

如果 boundary_map 是错的，验证器不会发现。**建议**：增加可选重算逻辑 `recompute_boundary=True`，默认用 struct.mask 重推边界并与 boundary_map 做一致性检查。

### 2. 交互检测只看质心距离，过于粗糙

**建议**：当前 interaction 标注为"几何近邻代理指标，不等于严格作用关系"。未来加入边界最短距离、历史反相关/同步波动、source/sink 流线因果邻接。

---

## 五、ExperimentLogger 缺三项元信息

1. **随机种子**：无 seed 则实验不可复现
2. **代码版本**：至少 commit sha 或 version tag
3. **核心环境**：torch version、device、shape/channels/lr/stability_window/ascent_threshold

建议统一写入 `runtime_info`，使日志从"实验结果记录"升级为"实验法证档案"。

---

## 六、run_experiment.py 可工程化改进

1. **实验注册表抽出**：command→function 映射从 main() 中移出为 `EXPERIMENT_REGISTRY`
2. **实验配置对象显式化**：用 dataclass 定义配置（size、steps 等），统一 CLI 解析、日志写入、文档生成

---

## 七、测试从"存在性测试"升级到"性质测试"

现有测试偏 shape 检查、不报错、返回值存在。建议增加：

1. **守恒性质测试**：验证 `ΔQ ≈ injected - absorbed`
2. **最小变易性质测试**：step_scale 调小后 transition_cost 系统性下降
3. **粗粒化一致性测试**：粗粒化前后守恒量在允许误差内一致

---

## 八、legacy 代码隔离

`engine/axiom_adapter.py` 已标 LEGACY 但仍在工程树中。建议移到 `legacy/` 或 `archive/`，文件名前缀 `legacy_`，主 README/PROJECT_MAP 明确"不参与当前主干运行"。

---

## 九、优先级排序（Top 10）

| # | 修改项 | 优先级 |
|---|--------|--------|
| 1 | 修 `inject_difference()` shape 生成逻辑 | 🔴 最高 |
| 2 | 修 WorldEngine 升维后状态续接（不退回随机初始） | 🔴 最高 |
| 3 | 把 reactor 损失定义统一回 AxiomEngine 体系 | 🔴 最高 |
| 4 | 统一 `measure_difference()` 输出语义（同型） | 🔴 最高 |
| 5 | 拆分 closure → connectivity_ratio + boundary_closure_score | 🟡 |
| 6 | 验证器增加 boundary 重算与一致性检查 | 🟡 |
| 7 | 日志增加 seed / commit / runtime_info | 🟡 |
| 8 | 实验配置 dataclass 化 | 🟢 |
| 9 | 增加守恒/最小变易/粗粒化一致性性质测试 | 🟢 |
| 10 | legacy 模块移出主干 | 🟢 |

**只改前 4 条，工程稳定性就会明显提升。**

---

## 十、审稿式结论

> 这套代码的优点不在算法华丽，而在于它已经形成了理论对象、层级对象、公理对象、演化对象、验证对象、实验对象之间的对应关系。对于一个独立项目，这是很难得的。
>
> 它的主要问题也不是"写得乱"，而是第一阶段原型常见的接口收束不足：抽象层与实现层尚未完全同构，检测器与验证器的指标体系尚未完全统一，部分主循环逻辑仍带有"能跑先跑"的临时性。
>
> 它现在的状态不是需要重构成另一套系统，而是需要进入一次语义清洗 + 接口固化 + 验证口径统一的阶段。
>
> 这是一种很好的问题。因为这说明核心方向已经立住了，接下来是工程收束，而不是世界观重写。