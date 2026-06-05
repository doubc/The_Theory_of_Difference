# 模拟机工程 — 代码审阅修改纲要

> 基准：2026-05-11 第三方代码审阅（code_review_2026-05-11.md）
> 状态：纲要阶段 → 逐条落地

## 可执行性分析

审阅中提到的以下文件**不在本地工程树中**（可能仅存在于 GitHub 或审阅者的本地版本）：
- `validators/structure_validator.py` — 不存在（本地 validators/ 仅有 __init__.py）
- `engine/experiment_logger.py` — 不存在
- `layers/coarse_grain.py` — 不存在
- `tests/test_structure_validator.py` — 不存在

这些文件的修改需求将在纲要中以"文档规格"记录，待文件出现时执行。

以下文件**存在且可修改**：
- `layers/L0_binary_lattice.py`, `layers/layer_base.py`
- `engine/world_engine.py`, `engine/reactor.py`, `engine/trainer.py`
- `acl/axiom_base.py`, `acl/axioms.py`
- `engine/axiom_adapter.py` (legacy)
- `run_experiment.py`
- `tests/test_l0_binary_lattice.py`, `tests/test_reactor_step.py`

---

## A 级：关键正确性修复（审阅 #1-4）

### A-1 🔴 修复 inject_difference() shape 生成逻辑
- **文件**: `layers/L0_binary_lattice.py` 第 132-139 行
- **问题**: `mask = torch.rand(state.shape[0], 1, self.shape[0], width, ...)` 中 `self.shape[0]` 应基于 `state` 而非对象初始化参数
- **方案**: 改用 `b, c, h, w = state.shape` → `mask = torch.rand(b, c, h, width, ...)`，同时 `width = min(3, max(1, w // 4))`

### A-2 🔴 修复 WorldEngine 升维后状态续接
- **文件**: `engine/world_engine.py` 第 115-120 行 + `layers/layer_base.py` + `layers/L0_binary_lattice.py`
- **问题**: `new_layer.initial_state()` 丢弃旧层状态，破坏层级递归连续性
- **方案**:
  1. `LayerBase` 新增抽象方法 `project_to_next_layer(source_layer, source_state) → Tensor`
  2. `L0BinaryLattice` 实现它（当前 coarse_grain 返回 None 所以暂用简单插值）
  3. `WorldEngine.run()` 改用 `if hasattr(new_layer, 'project_to_next_layer'): ... else: initial_state()`

### A-3 🔴 统合 DifferenceReactor 损失与 AxiomEngine
- **文件**: `engine/reactor.py` + `acl/axiom_base.py` + `acl/axioms.py`
- **问题**: reactor._compute_axiom_loss() 绕过 axiom_engine.evaluate()，自写 A2/A4/A5/A7
- **方案**:
  1. 扩展 `AxiomEngine.evaluate()` 接口接受 `**kwargs`，透传给各公理
  2. 更新 `A5_Conservation.violation()` 支持 boundary_info 做开放系统流量平衡
  3. `reactor._compute_axiom_loss()` 改为先调 `axiom_engine.evaluate()` 再追加 `spatial_diversity`
  4. A7 统一：reactor 中的稳定性损失回收进 A7.violation()

### A-4 🔴 统一 measure_difference() 输出语义（同型）
- **文件**: `layers/L0_binary_lattice.py` 第 80-103 行
- **问题**: 1D 返回 `dx (..., ..., w-1)`，2D 对齐裁切后平均，形状不一致
- **方案**: 末尾 F.pad 回原尺寸，使返回值始终与输入同 shape
- **影响**: 测试 `test_measure_difference_1d` 需要更新断言

---

## B 级：结构性改进（审阅 #5-6, #10）

### B-5 🟡 Legacy 代码隔离
- **文件**: `engine/axiom_adapter.py`
- **方案**: 移至 `legacy/axiom_adapter.py`，更新 PROJECT_MAP（如存在）

### B-6 🟢 实验配置 dataclass 化
- **文件**: 新建 `run_config.py`，修改 `run_experiment.py`
- **方案**: 定义 `ExperimentConfig` dataclass，实验注册表 `EXPERIMENT_REGISTRY`

---

## C 级：文档规格（对应审阅但文件不存在）

### C-7 — closure 术语拆分（待 structure_validator.py 出现）
- 检测器 closure (perimeter/area) → `boundary_closure_score`
- 验证器 closure (max_component/total) → `connectivity_ratio`
- StableStructure.source_trace 需同时记录二者

### C-8 — 验证器 boundary 重算（待 structure_validator.py 出现）
- 增加 `recompute_boundary=True` 参数
- 用 struct.mask 重推边界，与 struct.boundary_map 做一致性检查

### C-9 — ExperimentLogger 元信息（待 experiment_logger.py 出现）
- 记录 seed、commit sha、torch version、device、shape/channels/lr 等

### C-10 — 性质测试（待进一步规划）
- 守恒性质：ΔQ ≈ injected - absorbed
- 最小变易：step_scale↓ → transition_cost↓
- 粗粒化一致性：coarse_grain 前后守恒量容差关系

---

## 执行顺序

1. ✅ 写纲要文档（当前文件）
2. 🔧 A-1: inject_difference shape 修复
3. 🔧 A-4: measure_difference 同型化
4. 🔧 A-3: reactor-AxiomEngine 损失统合
5. 🔧 A-2: WorldEngine 升维状态续接
6. 🔧 B-5: Legacy 隔离
7. 🔧 B-6: 实验配置 dataclass
8. ✅ 运行测试验证
9. ✅ 写任务总结