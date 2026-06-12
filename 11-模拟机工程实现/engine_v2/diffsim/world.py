"""world.py — 单层引擎(Layer) 与 递归闭环世界(RecursiveWorld)。

Layer 运行一层的九机制齿轮直到密封。
RecursiveWorld 把一层的自指(A9)输出作为下一层的差异源, 递归咬合成闭环。
"""
from __future__ import annotations
from dataclasses import dataclass, field as dfield
from typing import Optional
import numpy as np

from .core import DifferenceField
from . import mechanisms as M
from .metrics import jaccard_flux
from .environment import EnvironmentField, EnvironmentCoupling
from .energy import EnergyManager, EnergyConfig
from .entropy import EntropyTracker, EntropyConfig


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

    def __init__(self, field: DifferenceField, params: Params,
                 energy_cfg: Optional[EnergyConfig] = None,
                 entropy_cfg: Optional[EntropyConfig] = None):
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
        # Phase 21: 能量 + 熵追踪
        if energy_cfg is not None:
            self.energy = EnergyManager(energy_cfg)
        else:
            self.energy = None
        if entropy_cfg is not None:
            self.entropy = EntropyTracker(entropy_cfg)
        else:
            self.entropy = None
        self._energy_cfg = energy_cfg
        self._entropy_cfg = entropy_cfg

    def run_until_seal(self, verbose=False, step_callback=None):
        f = self.field
        f.record()
        while not f.sealed and self.step < self.p.max_steps:
            self.step += 1
            prev = f.active_set()

            # 计算节流因子 (如果能量系统存在)
            throttle = 1.0
            if self.energy:
                throttle = self.energy.throttle_factor()

            # 传递节流因子到机制 (m1, m5, m6 接受调制)
            M.m1_clustering(self, throttle)
            M.m2_hierarchy(self)
            M.m3_conservation(self)
            M.m4_innate_completeness(self)
            M.m5_minimal_variation(self, throttle)
            M.m6_breaking(self, throttle)
            f.record()
            M.m7_cycle(self)
            M.m8_locking(self)

            cur = f.active_set()
            self.flux_trace.append(jaccard_flux(prev, cur))

            # Phase 21: 能量衰减 + 注入 + 熵计算
            if self.energy:
                active = f.n_active()
                total = f.N
                costs = self.energy.step(active, total)
                if self.energy.is_dead_order:
                    if verbose: print(f"  [ENERGY] L{f.layer} step{self.step}: dead order (budget={self.energy.budget:.1f})")
                    break
                if self.energy.is_low_energy and verbose:
                    print(f"  [ENERGY] L{f.layer} step{self.step}: low energy warning (budget={self.energy.budget:.1f})")

            if self.entropy:
                ent_metrics = self.entropy.step(
                    f.state.copy(),
                    {oid: list(org) for oid, org in f.organizations.items()},
                    self.energy.budget if self.energy else 0.0
                )

            if step_callback:
                step_callback(self)
            if verbose and self.step % 25 == 0:
                e_info = f" energy={self.energy.budget:.1f}" if self.energy else ""
                s_info = f" neg={self.entropy.history.negentropy[-1]:.3f}" if self.entropy and self.entropy.history.negentropy else ""
                print(f"  L{f.layer} step{self.step} active={f.n_active()} "
                      f"orgs={len(f.organizations)} sealed_bits={len(f.sealed_bits)}"
                      f"{e_info}{s_info}")
        return f.sealed

    def autonomous_flux(self):
        """该层自主演化的平均 Jaccard flux。flux=0 <=> 死秩序。"""
        return float(np.mean(self.flux_trace)) if self.flux_trace else 0.0


class RecursiveWorld:
    """九机制闭环: L0 -> (自指) -> L1 -> (自指) -> L2 -> ... 直到自指不动点(整体)。"""

    def __init__(self, N0=48, n0_active=40, n_colors=6, seed=0,
                 params: Params = None, self_encapsulate=True,
                 env_config=None, env_coupling_strength=0.2,
                 env_start_step=None,
                 energy_config: Optional[EnergyConfig] = None,
                 entropy_config: Optional[EntropyConfig] = None):
        self.rng = np.random.default_rng(seed)
        self.params = params or Params()
        self.self_encapsulate = self_encapsulate
        self.env_config = env_config
        self.env_coupling_strength = float(env_coupling_strength)
        self.env_start_step = env_start_step  # None=after L0 seal, int=at L0 step
        self.env = None
        self.env_coupling = None
        active0 = self.rng.choice(N0, size=min(n0_active, N0), replace=False).tolist()
        color0 = self.rng.integers(0, n_colors, size=N0)
        self.field0 = DifferenceField(
            N=N0, active=active0, a1_source=set(active0),
            direction=np.zeros(N0, dtype=np.int8), color=color0,
            layer=0, rng=self.rng,
        )
        self.layers = []
        self.report = []
        self.energy_config = energy_config
        self.entropy_config = entropy_config

    def _make_env_callback(self, coupling, env):
        def callback(layer):
            env.step_forward()
            coupling.on_step(layer)
        return callback

    def _l0_step_callback(self, layer):
        """L0 步回调: 按 env_start_step 创建环境并施加耦合。"""
        if self.env_start_step is not None and self.env is None:
            if layer.step >= self.env_start_step:
                self._create_env(layer.field)
        if self.env is not None:
            self.env.step_forward()
            self.env_coupling.on_step(layer)

    def _create_env(self, field):
        """创建环境场和耦合器。"""
        if self.env_config is None or self.env is not None:
            return
        env_seed = field.rng.integers(0, 999999) if hasattr(field, 'rng') else 0
        self.env = EnvironmentField(
            N=self.env_config.get("N", 16),
            structural_entropy=self.env_config.get("structural_entropy", 1),
            cycle_length=self.env_config.get("cycle_length", 5),
            seed=int(env_seed),
        )
        self.env_coupling = EnvironmentCoupling(
            self.env,
            coupling_strength=self.env_coupling_strength,
            threshold=self.env_config.get("threshold", 0.0),
        )

    def run(self, max_layers=6, verbose=False):
        field = self.field0
        for depth in range(max_layers):
            layer = Layer(field, self.params,
                           energy_cfg=self.energy_config,
                           entropy_cfg=self.entropy_config)

            # L0: 如果 env_start_step 已设置, 用步回调创建环境并施加耦合
            if depth == 0 and self.env_start_step is not None:
                sealed = layer.run_until_seal(
                    verbose=verbose,
                    step_callback=self._l0_step_callback
                )
            elif depth == 0 or self.env is None:
                sealed = layer.run_until_seal(verbose=verbose)
            else:
                # L1+ 且有环境: 每步施加环境耦合
                cb = self._make_env_callback(self.env_coupling, self.env)
                sealed = layer.run_until_seal(verbose=verbose, step_callback=cb)

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

            # Phase 21: 能量 + 熵信息记录
            if layer.energy:
                rec["energy_final"] = round(layer.energy.budget, 2)
                rec["energy_ratio"] = round(layer.energy.budget_ratio(), 4)
                rec["energy_low"] = layer.energy.is_low_energy
            if layer.entropy:
                s = layer.entropy.summary()
                rec["negentropy_final"] = round(s.get("final_negentropy", 0.0), 4)
                rec["mean_free_energy"] = round(s.get("mean_free_energy", 0.0), 4)
                rec["is_irreversible"] = s.get("is_irreversible", False)

            # Phase 19: 环境耦合信息记录
            if self.env is not None:
                rec["env_N"] = self.env.N
                rec["env_entropy"] = self.env.structural_entropy
                rec["env_flux"] = round(self.env.mean_flux(), 4)
                rec["coupling_strength"] = self.env_coupling_strength
                rec["coupling_events"] = self.env_coupling.summary()

            self.report.append(rec)
            if verbose:
                print(f"[L{field.layer}] sealed={sealed} orgs={k} "
                      f"flux={flux:.4f} mode={rec['mode']}")
            if not sealed:
                break

            nxt = M.m9_self_reference(layer, self_encapsulate=self.self_encapsulate)
            if nxt is None or nxt.N < self.params.min_org_size:
                rec["closure"] = "整体不动点(自指闭合)"
                break
            field = nxt

            # Phase 19: L0 密封后创建环境（如果还没创建）
            if depth == 0 and self.env_config is not None and self.env is None:
                # 如果 env_start_step > L0 seal_step（环境从未被创建），降级为固定创建
                self._create_env(field)
                if verbose:
                    print(f"[ENV] Created env N={self.env.N} "
                          f"entropy={self.env.structural_entropy} "
                          f"strength={self.env_coupling_strength}")

        return self.report

    def emergence_depth(self):
        return sum(1 for r in self.report if r["sealed"])
