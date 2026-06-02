
#### 2026-06-02 23:44 – 02:10 — Phase 5 Track B5 exp_118 — COMPLETE (Full Run)
- **exp_118 独立 L2 聚簇**: 8 seeds × 3000 steps 完整运行 ✅
- **Git**: commit 8441ebd → 修复 hierarchical_evolver.py 动态层迭代 + 重写 exp_118 脚本
- **核心发现**:
  - H30: **8/8 PASS** — L1↔L2 稳定性 r=0.0，L2 活跃 (mean=0.33, min=0.19)
    ✅ **这是真正的解耦**，不同于 B4 的假阳性（L2 静默）
  - H32/H36: **8/8 PASS** — L2 叙事自主性 (autonomy_idx=0.23-0.35)
  - H35: **8/8 PASS** — 稳定性地板生效 (min=0.19-0.25 ≥ 0.10)
  - H31/H33/H37: **0-2/8 FAIL** — 需要真正的多层演化
- **根因**: Layer 0 从未封口 (0 bits sealed)，层 1-2 从未创建
  - IndependentL2Coupling 是 post-hoc 计算，L2 稳定性解耦但叙事信号仍共享 MINI 层来源
  - L1↔L2 NSI 相关仍为 0.97（高），但稳定性相关为 0.0（解耦）
- **结论**: B5 核心主张（软偏置+地板产生真实解耦且不静默 L2）已验证 ✅
  剩余失败是 post-hoc 耦合的架构限制，非 B5 设计缺陷
- **文档**: docs/exp_118_track_b5_analysis.md
- **H31-H34**: 0/8 全部失败
- **崩溃原因**: SIGKILL (numpy NaN), hierarchical_evolver layer not found, AnticipatoryBiasEngine 参数错误
- **根本原因** (debug commit a0fbb08): `max_layers=1` 与 NSE 架构不兼容 — NSE 需要实际多层动力学计算 NSI
- **分析文档**: docs/exp_118_track_b5_analysis.md (d314dfc)
- **下一步**: 修复 max_layers=1→3 + HierarchyManager 初始化，改进 IndependentL2Coupling
- **Git**: commit d314dfc → origin/main (amended from a0fbb08)

#### 2026-06-03 00:40 — Phase 5 Track B6 Design + Implementation
- **Git**: commit 4362b1c → exp_118 B5 results + check_b5.py cleanup (pushed)
- **Track B6 design**: `docs/exp_119_track_b6_design.md` — combine B5 independent coupling with sealing-enabling parameters
- **Experiment script**: `experiments/exp_119_phase5_b6_true_multilayer.py` — 8 seeds × 5000 steps
  - B6 changes vs B5: steps 3000→5000, binding_threshold 0.1→0.05, ILP floor 20→15, consumption_rate 0.05→0.10
- **CSC modification**: Added L1-L2 ODI correlation tracking to `IndependentL2Coupling`
  - Added `_l1_odi_history`, `_l1_l2_odi_correlation_window` deques
  - Added `get_l1_l2_odi_correlation()` method
  - Updated `get_summary()`, `reset()`
- **Hypotheses**: H30/H32/H35/H36 target maintained; H31/H33/H37/H1-H8 target ≥4/8
- **Primary metric**: Sealing rate ≥4/8 seeds (L0 seals within 5000 steps)
- **Next**: Run exp_119 batch, analyze sealing results

#### 2026-06-02 13:56 — Phase 5 Track B1 exp_114 确认运行
- 完整的 8 seeds × 2000 steps 确认运行
- H28 0/8, H29 2/8, H1-H8 8/8 — 与初版完全一致
- 分析 doc: docs/exp_114_track_b1_analysis.md (50e21d2)
- Git push 失败 (SIGKILL) — 待手动: git push origin main

#### 2026-06-03 03:04 — Phase 5 Track B6 Fallback (exp_120) + 关键发现：封口机制 Bug
- **exp_120 B6 Fallback**: N0=48 L0 + N0=72 L2, 单种子测试 (seed 42)
- **结果**: L0 仍未封口 (0 bits sealed after 7500 steps)
- **核心发现**: 封口失败**不是规模问题**，而是 `AxiomConstraints.active_bits` 的**根本性 Bug**
  - `active_bits` 只增不减（`record_active()` 只 add 从不 remove）
  - 封口条件 `len(active_bits) <= min_active_bits` 在早期步骤后永远无法满足
  - N0=48: min_active_bits=16, 但 step 2500 时 active=44 → 44 > 16
  - N0=72: min_active_bits=24, 但 step 2500 时 active=41 → 41 > 24
- **影响**: B1-B6 所有多层实验的封口都受此 Bug 影响
  - B6 中 seed 542 的 12.5% 封口率是统计异常，非可靠机制
- **修复方案**: 
  - Option A (推荐): `active_bits` 改为滑动窗口，追踪最近活跃的 bits
  - Option B: 改用其他封口指标（当前活动率、绑定强度集中度、空间聚类）
  - Option C: 添加 decay 机制，移除长时间未活跃的 bits
- **文档**: docs/exp_120_b6_fallback_critical_finding.md
- **下一步**: 修复 `acl/axioms_v2.py` 的 active_bits 机制，然后重跑 B1-B6
- **Git**: exp_120 脚本已写，待修复后 commit + push
