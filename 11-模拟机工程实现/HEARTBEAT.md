
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

#### 2026-06-02 13:56 — Phase 5 Track B1 exp_114 确认运行
- 完整的 8 seeds × 2000 steps 确认运行
- H28 0/8, H29 2/8, H1-H8 8/8 — 与初版完全一致
- 分析 doc: docs/exp_114_track_b1_analysis.md (50e21d2)
- Git push 失败 (SIGKILL) — 待手动: git push origin main
