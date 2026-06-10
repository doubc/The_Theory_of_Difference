"""environment.py — Phase 19: 开放系统(环境交互) v2.

EnvironmentField: 无密封、持续搅动的差异场，提供给主系统外部约束。
EnvironmentCoupling: 双向耦合。

v2 关键改进:
  1. 持久绑定调制 (vs 短寿命 flux_budget, 被 m3 覆盖)
  2. 直接位翻转 (env 直接扰动主系统活跃位)
  3. churn 调制 (persistent, 不被覆盖)
"""
from __future__ import annotations
import numpy as np


class EnvironmentField:
    """环境场。

    与 DifferenceField 的关键区别:
    - 无密封 (no sealed_bits, no seal_step)
    - 持续搅动 (churn_source = all active bits)
    - 内部结构由 structural_entropy 参数控制: 0=白噪声, 1=弱聚簇, 2=强聚簇
    """

    def __init__(self, N=16, structural_entropy=1, cycle_length=5, seed=None):
        self.N = int(N)
        self.rng = np.random.default_rng(seed)
        self.structural_entropy = int(structural_entropy)
        self.cycle_length = int(cycle_length)

        self.step = 0
        self.flux_trace = []

        n_active = max(1, N // 3)
        active = self.rng.choice(N, size=n_active, replace=False).tolist()
        self.state = np.zeros(N, dtype=np.int8)
        self.state[active] = 1

        n_colors = max(1, N // 4)
        self.color = self.rng.integers(0, n_colors, size=N)

        self._init_binding()

    def _init_binding(self):
        """根据 structural_entropy 初始化内部绑定结构。"""
        self.binding = np.zeros((self.N, self.N), dtype=float)
        if self.structural_entropy == 0:
            return
        if self.structural_entropy == 1:
            n_clusters = max(2, self.N // 6)
            for _ in range(n_clusters):
                a = self.rng.integers(0, self.N)
                b = self.rng.integers(0, self.N)
                if a != b:
                    self.binding[a, b] = self.binding[b, a] = 0.3
        else:
            for c in range(max(1, self.N // 4)):
                members = np.where(self.color == c)[0]
                for i in members:
                    for j in members:
                        if i < j:
                            self.binding[i, j] = self.binding[j, i] = 0.8

    def active_set(self):
        return set(np.where(self.state == 1)[0].tolist())

    def n_active(self):
        return int(self.state.sum())

    def step_forward(self):
        """环境场自行演化一步。

        结构熵 0 -> 随机翻转（白噪声）。
        结构熵 >0 -> 用绑定图引导的连续搅动。
        """
        self.step += 1
        prev_active = self.active_set()

        if self.structural_entropy == 0:
            n_flip = max(1, self.N // 5)
            flip = self.rng.choice(self.N, size=n_flip, replace=False).tolist()
            for b in flip:
                self.state[b] = 1 - self.state[b]
        else:
            self._structured_step()

        cur_active = self.active_set()
        if prev_active and cur_active:
            jac = len(prev_active & cur_active) / len(prev_active | cur_active)
            self.flux_trace.append(1.0 - jac)
        else:
            self.flux_trace.append(0.0)

    def _structured_step(self):
        """绑定引导的结构化演化。"""
        active = self.active_set()
        candidates = set(active)
        for b in active:
            connected = np.where(self.binding[b] > 0.2)[0].tolist()
            candidates.update(connected)

        to_activate = candidates - active
        target_active = max(1, self.N // 3)
        n_activate = min(len(to_activate), max(1, target_active - len(active)))
        if n_activate > 0 and to_activate:
            chosen = self.rng.choice(list(to_activate),
                                     size=n_activate, replace=False).tolist()
            for b in chosen:
                self.state[b] = 1

        excess = self.state.sum() - target_active
        if excess > 0:
            current_active = np.where(self.state == 1)[0].tolist()
            n_decay = min(len(current_active), int(excess))
            decay = self.rng.choice(current_active, size=n_decay, replace=False).tolist()
            for b in decay:
                self.state[b] = 0

    def mean_flux(self):
        return float(np.mean(self.flux_trace)) if self.flux_trace else 0.0


class EnvironmentCoupling:
    """环境耦合 (v2)。

    双向设计:
    1. 环境 -> 主系统:
       - 绑定调制 (persistent): env 活跃位对应主系统位之间的绑定增强
       - 直接位翻转: env 活跃位有机会直接翻转主系统对应位
       - 搅动调制: 调节 layer.churn 以影响主系统演化速率

    2. 主系统 -> 环境:
       - 密封组织位在环境对应位置产生抑制
       - 主系统活跃源位在环境对应位置增强活性
    """

    def __init__(self, env: EnvironmentField, coupling_strength=0.2, threshold=0.0,
                 name="default"):
        self.env = env
        self.strength = float(coupling_strength)
        self.threshold = float(threshold)
        self.name = name
        self.coupling_events = []

    def _env_state_slice(self, layer):
        """将环境状态投影到主系统索引空间。"""
        f = layer.field
        n_shared = min(f.N, self.env.N)
        env_active = self.env.active_set()
        return set(b for b in env_active if b < n_shared)

    def apply_to_main(self, layer):
        """v2: 持久绑定调制 + 直接位翻转 + 搅动调制。"""
        f = layer.field
        env_slice = self._env_state_slice(layer)
        if not env_slice or self.strength <= 0:
            return

        # --- 1. 持久绑定调制 (persistent) ---
        # env 活跃位在共享空间中的绑定强度增强
        # 这持续影响 m2_hierarchy 的组织形成
        for i in env_slice:
            for j in env_slice:
                if i < j and i < f.N and j < f.N:
                    inc = self.strength * 0.15
                    f.binding[i, j] = min(5.0, f.binding[i, j] + inc)
                    f.binding[j, i] = f.binding[i, j]

        # --- 2. 直接位翻转 (direct) ---
        # env 活跃位有概率直接翻转主系统对应位
        flip_rate = self.strength * 0.08
        flip_events = 0
        for b in env_slice:
            if b < f.N and b not in f.sealed_bits and f.rng.random() < flip_rate:
                if f.state[b] == 0:
                    f.state[b] = 1
                    flip_events += 1
                elif f.state[b] == 1:
                    f.state[b] = 0
                    flip_events += 1
        if flip_events > 0:
            self.coupling_events.append(("flip", layer.step, flip_events))

        # --- 3. 搅动调制 (persistent) ---
        # env 活跃比例越高 -> 系统搅动越大
        env_ratio = len(env_slice) / max(1, min(f.N, self.env.N))
        churn_bonus = int(self.strength * env_ratio * 3)
        if churn_bonus > 0:
            old = layer.churn
            layer.churn = min(layer.churn + churn_bonus, 8)
            if layer.churn != old:
                self.coupling_events.append(("churn", layer.step, churn_bonus))

    def apply_to_env(self, layer):
        """v2: 主系统废热影响环境。"""
        f = layer.field
        if not f.sealed_bits and not f.state.sum():
            return

        # 主系统密封位抑制环境对应位
        suppressed = 0
        for b in list(self.env.active_set()):
            if b in f.sealed_bits or (b < f.N and f.state[b] == 1 and b in f.a1_source):
                if self.env.rng.random() < self.strength * 0.5:
                    self.env.state[b] = 0
                    suppressed += 1

        # 主系统组织增强环境对应位
        enhanced = 0
        for org in f.organizations.values():
            for b in list(org):
                if b < self.env.N and self.env.rng.random() < self.strength * 0.3:
                    self.env.state[b] = 1
                    enhanced += 1

        if suppressed + enhanced > 0:
            self.coupling_events.append(("env_mod", layer.step, suppressed + enhanced))

    def on_step(self, layer):
        """每一步耦合。"""
        self.apply_to_main(layer)
        self.apply_to_env(layer)

    def summary(self):
        flux_count = sum(1 for e in self.coupling_events if e[0] == "flux_budget" or e[0] == "flip")
        cand_count = sum(1 for e in self.coupling_events if e[0] == "candidates" or e[0] == "churn")
        return {"events": len(self.coupling_events), "direct": flux_count, "indirect": cand_count}