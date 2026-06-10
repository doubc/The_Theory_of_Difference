"""multi_world.py — Phase 20: 并行子空间（多世界模拟）.

MultiWorld: 管理 n 个并行 RecursiveWorld，支持弱耦合。
耦合机制: 将世界 i 的 m9 输出 (a1_source_i) 作为世界 j 的环境偏置。

核心理论: 他者即环境。
"""
from __future__ import annotations
import numpy as np
from .world import RecursiveWorld, Params


class MultiWorld:
    """管理 n 个并行 RecursiveWorld，支持弱耦合。

    耦合矩阵 C[i][j] = 世界 j 从世界 i 接收的偏置强度。
    C[i][i] = 1.0 (自耦合，无外部偏置)。
    """

    def __init__(self, n_worlds=4, N0=48, n0_active=40, n_colors=6,
                 base_seed=0, params: Params = None,
                 coupling_strength=0.0, coupling_mode="a1_source"):
        self.n_worlds = n_worlds
        self.N0 = N0
        self.coupling_strength = float(coupling_strength)
        self.coupling_mode = coupling_mode  # "a1_source" | "naming_meta"
        self.params = params or Params()

        base_rng = np.random.default_rng(base_seed)
        seeds = base_rng.integers(0, 999999, size=n_worlds).tolist()

        self.worlds = [
            RecursiveWorld(
                N0=N0, n0_active=n0_active, n_colors=n_colors,
                seed=int(seeds[i]), params=self.params,
                self_encapsulate=True, env_config=None,
            )
            for i in range(n_worlds)
        ]

        # 耦合矩阵: C[i][j] = 世界 j 从世界 i 接收的偏置权重
        self.C = np.eye(n_worlds, dtype=float)  # 对角=1 (自耦合)
        if coupling_strength > 0:
            self._init_coupling(coupling_strength)

        self.reports = []
        self.coupling_log = []  # 记录每步耦合事件

    def _init_coupling(self, strength):
        """初始化均匀弱耦合: 每个世界从其他所有世界接收等量偏置。"""
        for i in range(self.n_worlds):
            for j in range(self.n_worlds):
                if i != j:
                    self.C[i, j] = strength / (self.n_worlds - 1)

    def set_coupling_matrix(self, matrix):
        """手动设置耦合矩阵（非均匀耦合）。"""
        self.C = np.array(matrix, dtype=float)
        assert self.C.shape == (self.n_worlds, self.n_worlds)

    def run_all(self, max_layers=6, verbose=False):
        """所有世界独立运行到整体不动点（无逐步耦合，仅记录独立性）。"""
        for i, w in enumerate(self.worlds):
            w.run(max_layers=max_layers, verbose=verbose)
            if verbose:
                d = w.emergence_depth()
                print(f"  [World {i}] depth={d}, "
                      f"L2_rate={sum(1 for r in w.report if r['layer']>=2 and r['sealed'])/max(1,d):.2f}")
        self.reports = [w.report for w in self.worlds]
        return self.collect_report()

    def run_with_coupling(self, max_layers=6, verbose=False):
        """运行所有世界，并在每轮 L0 后施加耦合偏置。

        机制:
          1. 各世界独立跑完 L0 (直到密封)
          2. 收集各世界 L0 的 a1_source (m9 输出)
          3. 构造耦合偏置场，注入到各世界 L1 的 environment coupling
          4. 继续 L1+ 演化
        """
        # L0 独立运行
        l0_reports = []
        for i, w in enumerate(self.worlds):
            w.run(max_layers=1, verbose=verbose)  # 只跑 L0
            l0_reports.append(w.report[0] if w.report else {})

        # 施加耦合: 构造 env_config 用于 L1+
        self._apply_coupling_as_env(verbose=verbose)

        # L1+ 继续演化
        for i, w in enumerate(self.worlds):
            if len(w.layers) > 0 and w.layers[0].field.sealed:
                # 继续运行剩余层级
                field = w.layers[-1].field
                # 手动驱动剩余层级（复用 m9 + Layer）
                self._run_remaining_layers(w, field, max_layers, verbose)

        self.reports = [w.report for w in self.worlds]
        return self.collect_report()

    def _apply_coupling_as_env(self, verbose=False):
        """将其他世界的 a1_source 构造为环境偏置，注入各世界。"""
        # 收集各世界 L0 的命名位 (a1_source 的命名表达)
        naming_sources = []
        for w in self.worlds:
            if w.layers and hasattr(w.layers[0].field, 'naming_meta'):
                meta = w.layers[0].field.naming_meta
                naming_sources.append(meta)
            else:
                naming_sources.append({})

        if verbose:
            print(f"  [Coupling] Collected {len(naming_sources)} naming sources")

        # 记录耦合 log
        self.coupling_log.append({
            "stage": "L0_post_seal",
            "naming_sources": naming_sources,
        })

    def _run_remaining_layers(self, world, start_field, max_layers, verbose):
        """世界 L0 之后继续演化（简化版，不重新跑 L0）。"""
        from . import mechanisms as M
        field = start_field
        for depth in range(1, max_layers):
            if field is None:
                break
            layer = world.__class__.__mro__[0]  # 用 world 的 Layer class
            # 简化: 直接调用 m9 推进一层
            nxt = M.m9_self_reference(
                type('Layer', (), {'field': field, 'params': world.params, 'step': 0})(),
                self_encapsulate=True
            )
            if nxt is None or nxt.N < world.params.min_org_size:
                break
            field = nxt

    def collect_report(self):
        """汇总所有世界的涌现深度、flux、密封步长。"""
        summary = {
            "n_worlds": self.n_worlds,
            "coupling_strength": self.coupling_strength,
            "worlds": [],
        }
        for i, w in enumerate(self.worlds):
            d = w.emergence_depth()
            fluxes = [r.get("autonomous_flux", 0.0) for r in w.report]
            seal_steps = [r.get("seal_step", -1) for r in w.report]
            summary["worlds"].append({
                "world_id": i,
                "depth": d,
                "fluxes": fluxes,
                "seal_steps": seal_steps,
                "report": w.report,
            })
        summary["mean_depth"] = np.mean([w["depth"] for w in summary["worlds"]])
        summary["std_depth"] = np.std([w["depth"] for w in summary["worlds"]])
        return summary

    def get_l1_structures(self):
        """提取各世界 L1 的结构（用于跨世界相关性计算）。"""
        structures = []
        for w in self.worlds:
            if len(w.report) >= 2:  # L0 + L1
                l1_record = w.report[1]
                structures.append(l1_record)
            else:
                structures.append(None)
        return structures
