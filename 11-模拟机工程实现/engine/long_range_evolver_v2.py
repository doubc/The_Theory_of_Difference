"""
long_range_evolver_v2.py — 长程演化器 v2（硬性公理约束版）

核心改变：
- 公理从"损失项"变成"演化图的允许边"
- A1 严格单调（只允许 0→1，汇例外）
- A6 方向累积（不重置）
- A5 严格守恒（每步注入=吸收）
- A1' 横向比特循环
- A7 通量路径循环
"""

import torch
import numpy as np
from typing import List, Optional, Dict, Tuple
from layers.hamming_layer import HammingLattice, SourceSinkConfig
from acl.axioms_v2 import AxiomConstraints
from engine.hamming_engine import HammingMeasurement


class TrajectorySnapshotV2:
    """轨迹快照 v2"""
    def __init__(self, step: int, state: torch.Tensor,
                 flip_idx: int, n_inject: int, n_absorb: int,
                 n_lateral: int, w: int):
        self.step = step
        self.state = state.clone()
        self.flip_idx = flip_idx
        self.n_inject = n_inject
        self.n_absorb = n_absorb
        self.n_lateral = n_lateral
        self.w = w


class LongRangeEvolverV2:
    """长程演化器 v2（硬性公理约束）"""

    def __init__(self, N: int = 24,
                 total_steps: int = 50000,
                 sample_interval: int = 200,
                 device: str = "cpu",
                 n_hierarchy_bits: int = None,
                 coupling_strength: float = 0.3):
        self.N = N
        self.total_steps = total_steps
        self.sample_interval = sample_interval
        self.device = device

        # 公理约束器
        self.constraints = AxiomConstraints(N, n_hierarchy_bits)
        self.coupling_strength = coupling_strength

        # 轨迹记录
        self.snapshots: List[TrajectorySnapshotV2] = []
        self.flip_history: List[int] = []
        self.hamming_weight_history: List[int] = []
        self.inject_history: List[int] = []
        self.absorb_history: List[int] = []
        self.lateral_history: List[int] = []

    def run(self, initial_state: Optional[torch.Tensor] = None,
            verbose: bool = True) -> Dict:
        """运行长程演化"""

        if initial_state is None:
            state = torch.zeros(self.N, device=self.device)
        else:
            state = initial_state.clone().to(self.device)

        self.snapshots = []
        self.flip_history = []
        self.hamming_weight_history = []
        self.inject_history = []
        self.absorb_history = []
        self.lateral_history = []

        if verbose:
            print(f"[LongRangeEvolverV2] N={self.N}, T={self.total_steps}, "
                  f"sample_interval={self.sample_interval}")
            print(f"  Hierarchy bits: {self.constraints.n_hierarchy}, "
                  f"Lateral bits: {self.constraints.n_lateral}")

        for step in range(self.total_steps):
            w_before = state.sum().long().item()

            # ====== 1. 源注入（A1 + A8 调制）======
            source_strength = self.constraints.get_A8_source_strength(state)
            if source_strength > 0:
                # 优先选择层级比特（A1：差异累积）
                h_candidates = [i for i in self.constraints.hierarchy_indices
                                if state[i] < 0.5 and self.constraints.direction[i].item() >= 0]
                # 如果层级比特满了，注入横向比特
                l_candidates = [i for i in self.constraints.lateral_indices
                                if state[i] < 0.5 and self.constraints.direction[i].item() >= 0]
                all_candidates = h_candidates + l_candidates
                if all_candidates:
                    n_inject = min(source_strength, len(all_candidates))
                    ok, _ = self.constraints.check_A5_inject(state, n_inject)
                    if ok:
                        chosen = np.random.choice(all_candidates, n_inject, replace=False)
                        for idx in chosen:
                            state[idx] = 1.0
                            self.constraints.record_inject(1)
                            self.constraints.record_active(idx)
                            self.constraints.direction[idx] = 1
                    else:
                        n_inject = 0
                else:
                    n_inject = 0
            else:
                n_inject = 0

            # ====== 2. 内部演化（A4 + A1 + A6 + A8）======
            allowed = self.constraints.get_allowed_flips(state)
            if allowed:
                # A8 权重采样
                weights = self.constraints.get_A8_weights(state)
                allowed_weights = weights[allowed]
                allowed_weights = allowed_weights / allowed_weights.sum()
                flip_idx = allowed[torch.multinomial(allowed_weights, 1).item()]
                old_val = state[flip_idx].item()
                state[flip_idx] = 1.0 - state[flip_idx]
                new_val = state[flip_idx].item()
                self.constraints.update_A6_direction(flip_idx, old_val, new_val)
                self.constraints.record_active(flip_idx)
            else:
                flip_idx = -1

            # ====== 3. 横向演化（A1' + A5）======
            lateral_pairs = self.constraints.get_A1_prime_candidates(state)
            n_lateral = 0
            for (i, j) in lateral_pairs:
                # i: 1→0, j: 0→1（保持重量不变）
                if state[i] > 0.5 and state[j] < 0.5:
                    state[i] = 0.0
                    state[j] = 1.0
                    self.constraints.update_A6_direction(i, 1.0, 0.0)
                    self.constraints.update_A6_direction(j, 0.0, 1.0)
                    self.constraints.record_active(i)
                    self.constraints.record_active(j)
                    # A1'：增强绑定强度
                    self.constraints.strengthen_binding(i, j, amount=0.1)
                    n_lateral += 1

            # ====== 4. 汇吸收（A8 + A5 平衡）======
            sink_strength = self.constraints.get_A8_sink_strength(state, n_inject)
            if sink_strength > 0:
                # 优先吸收横向比特（保护层级比特）
                allowed_abs = self.constraints.get_allowed_absorbs(state)
                lateral_abs = [i for i in allowed_abs if i in self.constraints.lateral_indices]
                hierarchy_abs = [i for i in allowed_abs if i in self.constraints.hierarchy_indices]

                absorb_targets = lateral_abs + hierarchy_abs
                n_absorb = min(sink_strength, len(absorb_targets))

                if n_absorb > 0:
                    ok, _ = self.constraints.check_A5_absorb(state, n_absorb)
                    if ok:
                        chosen = absorb_targets[:n_absorb]
                        for idx in chosen:
                            state[idx] = 0.0
                            self.constraints.record_absorb(1)
                            # 汇吸收：横向比特可以循环（方向可逆），层级比特冻结
                            if idx in self.constraints.lateral_indices:
                                self.constraints.direction[idx] = 0  # 横向可逆
                            else:
                                self.constraints.direction[idx] = -1  # 层级冻结
                    else:
                        n_absorb = 0
                else:
                    n_absorb = 0
            else:
                n_absorb = 0

            # ====== 5. A7 循环检测 ======
            self.constraints.check_A7(state)

            # ====== 6. 记录 ======
            w_after = state.sum().long().item()
            self.flip_history.append(flip_idx)
            self.hamming_weight_history.append(w_after)
            self.inject_history.append(n_inject)
            self.absorb_history.append(n_absorb)
            self.lateral_history.append(n_lateral)

            # ====== 7. 采样 ======
            if step % self.sample_interval == 0:
                snapshot = TrajectorySnapshotV2(
                    step=step, state=state, flip_idx=flip_idx,
                    n_inject=n_inject, n_absorb=n_absorb,
                    n_lateral=n_lateral, w=w_after
                )
                self.snapshots.append(snapshot)

                if verbose and step % (self.sample_interval * 10) == 0:
                    n_cycles = len(self.constraints.cycle_states)
                    n_active = len(self.constraints.active_bits)
                    print(f"  Step {step:6d}: w={w_after:3d}, "
                          f"inj={n_inject}, abs={n_absorb}, lat={n_lateral}, "
                          f"active={n_active}, cycles={n_cycles}")

        if verbose:
            print(f"[LongRangeEvolverV2] Done. {len(self.snapshots)} snapshots.")
            print(f"  Cycles detected: {len(self.constraints.cycle_states)}")
            print(f"  Active bits: {len(self.constraints.active_bits)}/{self.N}")
            print(f"  Sealed: {self.constraints.sealed} ({len(self.constraints.sealed_bits)} bits, ratio={self.constraints.get_sealed_ratio():.2f})")
            print(f"  Total inject: {self.constraints.total_injected}, "
                  f"absorb: {self.constraints.total_absorbed}")
            clusters = self.constraints.get_clusters()
            print(f"  Clusters: {len(clusters)}")
            for c in clusters:
                print(f"    Cluster: {c}")

        return {
            'total_steps': self.total_steps,
            'n_snapshots': len(self.snapshots),
            'final_state': state,
            'flip_history': self.flip_history,
            'hamming_weight_history': self.hamming_weight_history,
            'inject_history': self.inject_history,
            'absorb_history': self.absorb_history,
            'lateral_history': self.lateral_history,
            'snapshots': self.snapshots,
            'cycle_states': len(self.constraints.cycle_states),
            'active_bits': len(self.constraints.active_bits),
            'direction': self.constraints.direction.clone(),
            'clusters': self.constraints.get_clusters(),
            'binding_strength': self.constraints.binding_strength.clone(),
            'sealed': self.constraints.sealed,
            'sealed_bits': len(self.constraints.sealed_bits),
            'sealed_ratio': self.constraints.get_sealed_ratio(),
            'n_cycles_near': sum(1 for _ in self.constraints.cycle_states),
        }

    def get_trajectory_tensor(self) -> torch.Tensor:
        if not self.snapshots:
            return torch.zeros(0, self.N)
        return torch.stack([s.state for s in self.snapshots], dim=0)

    def get_flip_sequence(self) -> torch.Tensor:
        return torch.tensor(self.flip_history, dtype=torch.long)

    def get_hamming_weight_sequence(self) -> torch.Tensor:
        return torch.tensor(self.hamming_weight_history, dtype=torch.long)
