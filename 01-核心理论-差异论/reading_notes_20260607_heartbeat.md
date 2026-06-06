# 心跳工作记录 — 2026-06-07 04:44 CST

## 本次执行内容

### 1. 修复 `subspace_evolver.py` UnicodeEncodeError (BUG FIX)

**位置**: `engine/subspace_evolver.py` 第 487 行

**问题**:
`sealed_str` 使用 Unicode 字符 `✓`（U+2713）和 `✗`（U+2717）构建，在 Windows GBK 控制台编码下 `print()` 直接抛出 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2717'`，导致实验脚本静默崩溃（background process 被杀后无错误输出）。

**为什么之前没发现**:
- 之前的实验（exp_148/149/150）可能运行在隔离环境，或 `verbose=False` 未触发该分支
- exp_151 是第一个在 Windows 上以 `verbose=True` 运行的 `SubspaceAwareEvolver` 实验

**修复**:
```python
# Before (crash on Windows GBK):
sealed_str = ", ".join(
    f"{n}: {'✓' if s.is_sealed else '✗'}"
    for n, s in layer_solvers.items()
)

# After (ASCII-safe):
sealed_str = ", ".join(
    f"{n}: {'[Y]' if s.is_sealed else '[N]'}"
    for n, s in layer_solvers.items()
)
```

**影响范围**: 仅 `subspace_evolver.py` 第 487 行，已全文搜索确认无其他 Unicode 符号残留。

---

### 2. exp_151 重启运行

**背景**: exp_151 在 2026-06-07 01:42 首次启动，但因上述 Unicode 错误在第一个 seed 运行完毕后崩溃（print 触发异常，进程退出），导致 48 个 run 只完成了 2 个，结果文件未生成。

**当前状态**: exp_151 已于 04:45 CST 重新启动，输出写入 `experiments/logs/exp_151_run_20260607_0445.log`，预计 ~43 分钟完成（48 runs × ~53s/run）。

**实验设计回顾** (exp_151):
- 非对称耦合：master (40 bits) → slave (20 bits)，单向
- N0*=30.5，master > N0*（形成 L1），slave < N0*（不形成 L1）
- 假设：增强 master→slave 耦合可以 "rescue" slave 的 L1 形成

---

### 3. 理论笔记：非对称耦合与因果箭头

exp_151 的核心物理问题是：**单向耦合能否在非对称子系统之间建立因果箭头？**

这映射到差异论的一个核心议题：
- L1（有序相）对 L0（无序相）有被动约束效应（Phase 8 已验证）
- 子空间版本：大子空间（已过相变）能否"拖拽"小子空间（未过相变）进入有序相？
- 如果可以，这意味着 **差异场的层级结构可以通过耦合传播** —— 高层差异（L1）约束低层差异（L0）

这直接关联到差异论生成式世界的核心机制：
> 差异不是孤立的，差异之间的差异（二阶差异）通过耦合项产生新的生成规则。

exp_151 的 "rescue effect" 如果得到验证，将为"差异的层级生成"提供一个可计算的数值实验基础。

---

## 下次心跳待办

- [ ] 检查 exp_151 结果（预计 05:28 CST 完成）
- [ ] 如果 H151-2（rescue effect）PASS，写 theory_synthesis_v2.md 初稿
- [ ] 如果 H151-2 FAIL，分析原因，设计 exp_152（参数特化）
- [ ] commit bug fix（subspace_evolver.py Unicode 修复）

---

*记录时间: 2026-06-07 04:44 CST | 下次心跳: ~08:00 CST*
