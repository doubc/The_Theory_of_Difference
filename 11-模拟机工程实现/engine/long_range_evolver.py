"""
long_range_evolver.py — 长程演化器（增强版）

增强点：
1. 比特间耦合翻转（coupling_strength 控制）
2. 增强源/汇通量
3. DAG方向持续性追踪

演化流程（每步）：
  1. 源注入差异（多源，动态位置）
  2. 主翻转：A8对称偏好调制的单比特翻转
  3. 耦合翻转：以概率 coupling_strength 触发关联比特翻转
  4. 汇吸收差异（多汇，动态位置）
  5. DAG方向更新（A6不可逆性）
  6. 记录轨迹
"""

import torch
from typing import List, Optional, Dict, Tuple
from layers.hamming_layer import HammingLattice, SourceSinkConfig
from engine.hamming_engine import HammingMeasurement


class TrajectorySnapshot:
    """轨迹快照"""
    def __init__(self, step: int, state: torch.Tensor,
                 flip_position: int, axiom_violations: Dict,
                 flux_stats: Dict, n_coupled: int = 0):
        self.step = step
        self.state = state.clone()
        self.flip_position = flip_position
        self.axiom_violations = axiom_violations
        self.flux_stats = flux_stats
        self.n_coupled = n_coupled


class LongRangeEvolver:
    """长程演化器（增强版）"""

    def __init__(self, layer: HammingLattice,
                 total_steps: int = 100000,
                 sample_interval: int = 100,
                 device: str = "cpu",
                 coupling_strength: float = 0.3):
        self.layer = layer
        self.total_steps = total_steps
        self.sample_interval = sample_interval
        self.device = device
        self.coupling_strength = coupling_strength

        # 轨迹记录
        self.snapshots: List[TrajectorySnapshot] = []
        self.flip_history: List[int] = []
        self.axiom_loss_history: List[float] = []
        self.hamming_weight_history: List[int] = []
        self.coupled_flips: List[Tuple[int, int]] = []

    def run(self, initial_state: Optional[torch.Tensor] = None,
            verbose: bool = True) -> Dict:
        """运行长程演化"""
        if initial_state is None:
            state = self.layer.initial_state(batch_size=1).squeeze(0)
        else:
            state = initial_state.clone()

        state = state.to(self.device)
        self.layer.reset()
        self.snapshots = []
        self.flip_history = []
        self.axiom_loss_history = []
        self.hamming_weight_history = []
        self.coupled_flips = []

        a8_weights = HammingMeasurement.symmetry_weight_vector(self.layer.N).to(self.device)

        if verbose:
            ss = self.layer.ss_config
            print(f"[LongRangeEvolver] N={self.layer.N}, T={self.total_steps}, "
                  f"sample_interval={self.sample_interval}, coupling={self.coupling_strength}")
            print(f"  Source/Sink: {ss.n_sources}s/{ss.n_sinks}k, "
                  f"strength={ss.source_strength}/{ss.sink_strength}, "
                  f"dynamic={ss.dynamic_position}")
            print(f"  DAG: {self.layer.dag_enabled}, Strict Axioms: {self.layer.use_strict_axioms}")

        for step in range(self.total_steps):
            w_before = state.sum().long().item()

            # 1. 源注入
            state = self.layer.inject_difference(state)

            # 2. 主翻转（A8调制）
            flip_weights = self._compute_flip_weights(state, a8_weights)
            state, flip_idx = self.layer.step_hamming(state, flip_weights)

            # 3. 耦合翻转（比特间相互作用）
            n_coupled = 0
            if flip_idx >= 0 and self.coupling_strength > 0:
                state, n_coupled = self._coupled_flip(state, flip_idx)

            # 4. 汇吸收
            state = self.layer.absorb_difference(state)

            # 5. 硬投影
            state = self.layer.project_state(state)

            # 6. 记录
            self.flip_history.append(flip_idx)
            w_after = state.sum().long().item()
            self.hamming_weight_history.append(w_after)

            # 7. 采样记录
            if step % self.sample_interval == 0:
                snapshot = TrajectorySnapshot(
                    step=step, state=state, flip_position=flip_idx,
                    axiom_violations={}, flux_stats=self.layer.get_flux_stats(),
                    n_coupled=n_coupled,
                )
                self.snapshots.append(snapshot)

                if verbose and step % (self.sample_interval * 10) == 0:
                    print(f"  Step {step:6d}: w={w_after:3d}, "
                          f"flip={flip_idx:3d}, coupled={n_coupled}, "
                          f"snapshots={len(self.snapshots)}")

        if verbose:
            print(f"[LongRangeEvolver] Done. {len(self.snapshots)} snapshots, "
                  f"{len(self.coupled_flips)} coupled flips.")

        return {
            'total_steps': self.total_steps,
            'n_snapshots': len(self.snapshots),
            'final_state': state,
            'flip_history': self.flip_history,
            'hamming_weight_history': self.hamming_weight_history,
            'snapshots': self.snapshots,
            'flux_stats': self.layer.get_flux_stats(),
            'coupled_flips': self.coupled_flips,
        }

    def _coupled_flip(self, state: torch.Tensor,
                      primary_idx: int) -> Tuple[torch.Tensor, int]:
        """耦合翻转（向量化版本）"""
        if torch.rand(1).item() > self.coupling_strength:
            return state, 0

        N = self.layer.N
        flat = state.clone()

        # 向量化计算距离权重
        all_indices = torch.arange(N, device=self.device)
        distances = torch.min(
            torch.abs(all_indices - primary_idx),
            N - torch.abs(all_indices - primary_idx)
        ).float()
        weights = 1.0 / (1.0 + distances)
        weights[primary_idx] = 0.0  # 排除自身

        # DAG 约束
        if self.layer.dag_enabled and self.layer.transition.direction is not None:
            direction = self.layer.transition.direction
            dag_mask = torch.ones(N, dtype=torch.bool, device=self.device)
            dag_mask &= ~((direction > 0) & (flat > 0.5))
            dag_mask &= ~((direction < 0) & (flat < 0.5))
            weights = weights * dag_mask.float()

        if weights.sum() < 1e-8:
            return state, 0

        weights = weights / weights.sum()
        coupled_idx = torch.multinomial(weights, 1).item()

        flat[coupled_idx] = 1.0 - flat[coupled_idx]
        self.coupled_flips.append((primary_idx, coupled_idx))
        return flat, 1

    def _compute_flip_weights(self, state: torch.Tensor,
                               a8_weights: torch.Tensor) -> torch.Tensor:
        """计算每个比特的翻转权重"""
        N = self.layer.N
        w = state.sum().long().item()

        weights = torch.ones(N, device=self.device)

        # A8 对称偏好
        if w < N // 2:
            weights[state < 0.5] *= 1.5
            weights[state > 0.5] *= 0.8
        elif w > N // 2:
            weights[state > 0.5] *= 1.5
            weights[state < 0.5] *= 0.8

        # DAG 方向约束（A6）
        if self.layer.dag_enabled and self.layer.transition.direction is not None:
            direction = self.layer.transition.direction
            for i in range(N):
                if direction[i] > 0 and state[i] > 0.5:
                    weights[i] = 0.0
                elif direction[i] < 0 and state[i] < 0.5:
                    weights[i] = 0.0

        weights = weights / weights.sum().clamp(min=1e-8)
        return weights

    def get_trajectory_tensor(self) -> torch.Tensor:
        if not self.snapshots:
            return torch.zeros(0, self.layer.N)
        return torch.stack([s.state for s in self.snapshots], dim=0)

    def get_flip_sequence(self) -> torch.Tensor:
        return torch.tensor(self.flip_history, dtype=torch.long)

    def get_hamming_weight_sequence(self) -> torch.Tensor:
        return torch.tensor(self.hamming_weight_history, dtype=torch.long)
