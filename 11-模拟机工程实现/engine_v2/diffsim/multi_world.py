"""multi_world.py — Phase 20: 并行子空间（多世界模拟）.

MultiWorld: 管理 n 个并行 RecursiveWorld，支持多种耦合机制。

耦合模式:
  1. "none"        — 无耦合，各世界独立运行
  2. "env_coupling" — 将其他世界的命名位作为环境偏置注入（非破坏性）
  3. "bit_swap_soft" — 在 L0 运行期间逐步注入微弱偏置（不破坏密封）

核心理论: 他者即环境。多个自指链耦合 -> 可能产生单链无法达到的复杂度。
"""
from __future__ import annotations
import numpy as np
from typing import List, Dict, Any, Optional

from .world import RecursiveWorld, Params, Layer
from .core import DifferenceField
from .environment import EnvironmentField, EnvironmentCoupling
from . import mechanisms as M


class MultiWorld:
    """管理 n 个并行 RecursiveWorld，支持弱耦合。"""

    def __init__(
        self,
        n_worlds: int = 4,
        N0: int = 48,
        n0_active: int = 40,
        n_colors: int = 6,
        base_seed: int = 0,
        params: Optional[Params] = None,
        coupling_strength: float = 0.0,
        coupling_mode: str = "none",
        bit_swap_rate: float = 0.1,
    ):
        self.n_worlds = n_worlds
        self.N0 = N0
        self.coupling_strength = float(coupling_strength)
        self.coupling_mode = coupling_mode
        self.bit_swap_rate = bit_swap_rate
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

        # 环境场: 每个世界一个
        self.envs: List[Optional[EnvironmentField]] = [None] * n_worlds
        self.env_couplings: List[Optional[EnvironmentCoupling]] = [None] * n_worlds

        self.reports: List[Dict] = []
        self.coupling_log: List[Dict] = []
        self.cross_layer_snapshots: List[Dict] = []

    # ------------------------------------------------------------------
    # 运行模式 1: 独立运行（无耦合）
    # ------------------------------------------------------------------
    def run_all(self, max_layers: int = 6, verbose: bool = False) -> Dict:
        """所有世界独立运行到整体不动点（无耦合）。"""
        for i, w in enumerate(self.worlds):
            w.run(max_layers=max_layers, verbose=verbose)
            if verbose:
                d = w.emergence_depth()
                print(f"  [World {i}] depth={d}")
        self.reports = [w.report for w in self.worlds]
        return self.collect_report()

    # ------------------------------------------------------------------
    # 运行模式 2: 逐层运行 + 环境耦合（非破坏性）
    # ------------------------------------------------------------------
    def run_with_coupling(
        self,
        max_layers: int = 6,
        max_steps_per_layer: int = 400,
        verbose: bool = False,
    ) -> Dict:
        """所有世界逐层同步运行，每层密封后通过环境施加耦合。

        耦合通过环境偏置实现（不破坏密封后的 field.state）：
        - 收集其他世界的命名位（a1_source）
        - 构造为 EnvironmentField
        - 注入到本世界的 L1+ 演化中
        """
        if self.coupling_mode in ("env_coupling", "a1_source"):
            return self._run_env_coupling_mode(max_layers, verbose)
        elif self.coupling_mode == "bit_swap_soft":
            return self._run_bit_swap_soft_mode(max_layers, max_steps_per_layer, verbose)
        else:
            return self.run_all(max_layers, verbose)

    def _run_env_coupling_mode(
        self,
        max_layers: int,
        verbose: bool,
    ) -> Dict:
        """环境耦合模式: L0 密封后，将其他世界的命名位注入为环境偏置。"""
        # L0 独立运行
        for i, w in enumerate(self.worlds):
            w.run(max_layers=1, verbose=verbose)

        # 收集各世界 L0 的命名位
        naming_sources = []
        for w in self.worlds:
            if w.layers and hasattr(w.layers[0].field, 'naming_meta'):
                naming_sources.append(w.layers[0].field.naming_meta)
            else:
                naming_sources.append({})

        if verbose:
            print(f"  [env_coupling] Collected {len(naming_sources)} naming sources")

        # 为每个世界创建环境（基于其他世界的命名位）
        self._create_coupled_envs(naming_sources, verbose)

        # L1+ 继续演化（带环境耦合）
        for i, w in enumerate(self.worlds):
            if len(w.layers) > 0 and w.layers[0].field.sealed:
                self._run_remaining_with_env(w, i, max_layers, verbose)

        self.reports = [w.report for w in self.worlds]
        return self.collect_report()

    def _create_coupled_envs(self, naming_sources: List[Dict], verbose: bool):
        """为每个世界创建耦合环境（来自其他世界的命名位）。"""
        for i in range(self.n_worlds):
            # 收集其他世界的命名位
            other_naming = {}
            for j in range(self.n_worlds):
                if j != i and naming_sources[j]:
                    other_naming.update(naming_sources[j])

            if not other_naming:
                continue

            # 构造环境场
            env_N = max(4, min(16, self.N0 // 4))
            env_seed = int(hash(str(other_naming)) % 999999)
            env = EnvironmentField(
                N=env_N,
                structural_entropy=1,  # 低熵 = 有结构
                cycle_length=5,
                seed=env_seed,
            )
            coupling = EnvironmentCoupling(
                env,
                coupling_strength=self.coupling_strength,
                threshold=0.3,
            )
            self.envs[i] = env
            self.env_couplings[i] = coupling

            if verbose:
                print(f"  [env] World {i} env created: N={env_N}, strength={self.coupling_strength}")

    def _run_remaining_with_env(self, world, world_idx: int, max_layers: int, verbose: bool):
        """带环境耦合的 L1+ 演化。"""
        if self.envs[world_idx] is None or self.env_couplings[world_idx] is None:
            # 无环境 -> 正常演化
            world.run(max_layers=max_layers, verbose=verbose)
            return

        env = self.envs[world_idx]
        coupling = self.env_couplings[world_idx]

        field = world.layers[-1].field
        for depth in range(1, max_layers):
            if field is None:
                break

            # 创建 Layer 并运行（带环境回调）
            layer = Layer(field, world.params)

            def make_cb(env_ref, coup_ref):
                def cb(lyr):
                    env_ref.step_forward()
                    coup_ref.on_step(lyr)
                return cb

            cb = make_cb(env, coupling)
            sealed = layer.run_until_seal(verbose=False, step_callback=cb)

            world.layers.append(layer)
            flux = layer.autonomous_flux()
            k = len([o for o in field.organizations.values()
                      if len(o) >= world.params.min_org_size])
            rec = {
                "layer": field.layer,
                "N": field.N,
                "sealed": sealed,
                "seal_step": field.seal_step,
                "n_orgs": k,
                "autonomous_flux": round(flux, 4),
                "mode": field.naming_meta.get("mode", "seed"),
                "env_coupled": True,
            }
            world.report.append(rec)

            if not sealed:
                break

            nxt = M.m9_self_reference(layer, self_encapsulate=True)
            if nxt is None or nxt.N < world.params.min_org_size:
                world.report[-1]["closure"] = "整体不动点(自指闭合)"
                break
            field = nxt

    def _run_bit_swap_soft_mode(
        self,
        max_layers: int,
        max_steps_per_layer: int,
        verbose: bool,
    ) -> Dict:
        """软位交换模式: 在 L0 运行期间注入微弱偏置（通过环境，不破坏密封）。"""
        # 类似 _run_env_coupling_mode 但耦合在 L0 就开始
        for i, w in enumerate(self.worlds):
            # L0 带环境耦合运行
            if self.envs[i] is not None:
                w.env = self.envs[i]
                w.env_coupling = self.env_couplings[i]
                w.env_start_step = 0  # 从 step 0 开始耦合
            w.run(max_layers=1, verbose=verbose)

        # L1+ 继续
        for i, w in enumerate(self.worlds):
            if len(w.layers) > 0 and w.layers[0].field.sealed:
                self._run_remaining_with_env(w, i, max_layers, verbose)

        self.reports = [w.report for w in self.worlds]
        return self.collect_report()

    # ------------------------------------------------------------------
    # 分析和报告
    # ------------------------------------------------------------------
    def collect_report(self) -> Dict:
        """汇总所有世界的涌现深度、flux、密封步长。"""
        summary: Dict = {
            "n_worlds": self.n_worlds,
            "coupling_strength": self.coupling_strength,
            "coupling_mode": self.coupling_mode,
            "worlds": [],
        }
        depths = []
        for i, w in enumerate(self.worlds):
            d = w.emergence_depth()
            depths.append(d)
            fluxes = [r.get("autonomous_flux", 0.0) for r in w.report]
            seal_steps = [r.get("seal_step", -1) for r in w.report]
            summary["worlds"].append({
                "world_id": i,
                "depth": d,
                "fluxes": fluxes,
                "seal_steps": seal_steps,
                "report": w.report,
            })
        if depths:
            summary["mean_depth"] = float(np.mean(depths))
            summary["std_depth"] = float(np.std(depths))
        else:
            summary["mean_depth"] = 0.0
            summary["std_depth"] = 0.0
        return summary

    def compute_cross_world_correlation(self) -> Dict:
        """计算跨世界涌现深度相关性（H20-P0a）。"""
        depths = [w.emergence_depth() for w in self.worlds]
        if len(depths) < 2:
            return {"correlation": None, "n_pairs": 0}

        import itertools
        pairs = list(itertools.combinations(range(len(depths)), 2))
        if not pairs:
            return {"correlation": None, "n_pairs": 0}

        corrs = []
        for i, j in pairs:
            f_i = [r.get("autonomous_flux", 0.0) for r in self.worlds[i].report]
            f_j = [r.get("autonomous_flux", 0.0) for r in self.worlds[j].report]
            min_len = min(len(f_i), len(f_j))
            if min_len >= 2:
                corr = np.corrcoef(f_i[:min_len], f_j[:min_len])[0, 1]
                if not np.isnan(corr):
                    corrs.append(corr)

        return {
            "correlation": round(float(np.mean(corrs)), 4) if corrs else None,
            "all_correlations": [round(float(c), 4) for c in corrs],
            "n_pairs": len(corrs),
            "depths": depths,
        }
