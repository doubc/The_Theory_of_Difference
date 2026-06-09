"""world.py — 单层引擎(Layer) 与 递归闭环世界(RecursiveWorld)。

Layer 运行一层的九机制齿轮直到密封。
RecursiveWorld 把一层的自指(A9)输出作为下一层的差异源, 递归咬合成闭环。
"""
from __future__ import annotations
from dataclasses import dataclass, field as dfield
import numpy as np

from .core import DifferenceField
from . import mechanisms as M
from .metrics import jaccard_flux


@dataclass
class Params:
    bind_inc: float = 0.18
    bind_cap: float = 5.0
    bind_threshold: float = 1.0
    cascade_density: float = 0.9
    min_org_size: int = 3
    seal_fraction: float = 0.6
    lock_inc: float = 0.12
    lock_threshold: float = 0.6
    cycle_persistence: int = 3
    target_active: int = 0          # 0 => 初始活跃数
    max_flip: int = 6
    churn: int = 2
    n_meta_colors: int = 4
    max_residual: int = 6
    max_steps: int = 400


class Layer:
    """驱动一个 DifferenceField 跑完九机制齿轮直到密封。"""

    def __init__(self, field: DifferenceField, params: Params):
        self.field = field
        self.p = params
        if self.p.target_active == 0:
            self.p = Params(**{**params.__dict__, "target_active": max(1, field.n_active())})
        self.step = 0
        self.churn = self.p.churn
        self.tentative_orgs = []
        self.newly_broken = []
        self.is_cyclic = False
        self.moves_this_step = 0
        self.flux_trace = []

    def run_until_seal(self, verbose=False):
        f = self.field
        f.record()
        while not f.sealed and self.step < self.p.max_steps:
            self.step += 1
            prev = f.active_set()
            M.m1_clustering(self)
            M.m2_hierarchy(self)
            M.m3_conservation(self)
            M.m4_innate_completeness(self)
            M.m5_minimal_variation(self)
            M.m6_breaking(self)
            f.record()
            M.m7_cycle(self)
            M.m8_locking(self)
            cur = f.active_set()
            self.flux_trace.append(jaccard_flux(prev, cur))
            if verbose and self.step % 25 == 0:
                print(f"  L{f.layer} step{self.step} active={f.n_active()} "
                      f"orgs={len(f.organizations)} sealed_bits={len(f.sealed_bits)}")
        return f.sealed

    def autonomous_flux(self):
        """该层自主演化的平均 Jaccard flux。flux=0 <=> 死秩序。"""
        return float(np.mean(self.flux_trace)) if self.flux_trace else 0.0


class RecursiveWorld:
    """九机制闭环: L0 -> (自指) -> L1 -> (自指) -> L2 -> ... 直到自指不动点(整体)。"""

    def __init__(self, N0=48, n0_active=40, n_colors=6, seed=0,
                 params: Params = None, self_encapsulate=True):
        self.rng = np.random.default_rng(seed)
        self.params = params or Params()
        self.self_encapsulate = self_encapsulate
        active0 = self.rng.choice(N0, size=min(n0_active, N0), replace=False).tolist()
        color0 = self.rng.integers(0, n_colors, size=N0)
        self.field0 = DifferenceField(
            N=N0, active=active0, a1_source=set(active0),
            direction=np.zeros(N0, dtype=np.int8), color=color0,
            layer=0, rng=self.rng,
        )
        self.layers = []
        self.report = []

    def run(self, max_layers=6, verbose=False):
        field = self.field0
        for depth in range(max_layers):
            layer = Layer(field, self.params)
            sealed = layer.run_until_seal(verbose=verbose)
            self.layers.append(layer)
            flux = layer.autonomous_flux()
            k = len([o for o in field.organizations.values()
                     if len(o) >= self.params.min_org_size])
            rec = {
                "layer": field.layer, "N": field.N, "sealed": sealed,
                "seal_step": field.seal_step, "n_orgs": k,
                "autonomous_flux": round(flux, 4),
                "mode": field.naming_meta.get("mode", "seed"),
            }
            self.report.append(rec)
            if verbose:
                print(f"[L{field.layer}] sealed={sealed} orgs={k} "
                      f"flux={flux:.4f} mode={rec['mode']}")
            if not sealed:
                break
            nxt = M.m9_self_reference(layer, self_encapsulate=self.self_encapsulate)
            if nxt is None or nxt.N < self.params.min_org_size:
                # 自指不动点: 结构把自身纳入自身, 整体(whole)被定义 -> 闭环完成。
                rec["closure"] = "整体不动点(自指闭合)"
                break
            # 下一层的聚簇以上一层自指生成的新差异源重新启动 -> 咬合。
            field = nxt
        return self.report

    def emergence_depth(self):
        return sum(1 for r in self.report if r["sealed"])
