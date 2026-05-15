"""
long_range_evolver.py — 长程演化器

纯演化模式（无训练）：在 HammingLattice 上跑 T=100000 步，
记录完整轨迹用于涌现检测。

关键：
- 不使用模型预测，只用公理约束的随机游走
- 源/汇持续形成通量
- 每 sample_interval 步采样一次状态
- 记录比特翻转历史（用于互信息、返回时间等统计）
"""

import torch
from typing import List, Optional, Dict, Tuple
from layers.hamming_layer import HammingLattice, SourceSinkConfig
from engine.hamming_engine import HammingMeasurement


class TrajectorySnapshot:
    """轨迹快照"""
    def __init__(self, step: int, state: torch.Tensor,
                 flip_position: int, axiom_violations: Dict,
                 flux_stats: Dict):
        self.step = step
        self.state = state.clone()
        self.flip_position = flip_position
        self.axiom_violations = axiom_violations
        self.flux_stats = flux_stats


class LongRangeEvolver:
    """长程演化器

    纯演化模式：公理约束 + 源/汇通量 → 长程轨迹
    """

    def __init__(self, layer: HammingLattice,
                 total_steps: int = 100000,
                 sample_interval: int = 100,
                 device: str = "cpu"):
        self.layer = layer
        self.total_steps = total_steps
        self.sample_interval = sample_interval
        self.device = device

        # 轨迹记录
        self.snapshots: List[TrajectorySnapshot] = []
        self.flip_history: List[int] = []  # 每步翻转的比特位置
        self.axiom_loss_history: List[float] = []
        self.hamming_weight_history: List[int] = []

    def run(self, initial_state: Optional[torch.Tensor] = None,
            verbose: bool = True) -> Dict:
        """运行长程演化

        Args:
            initial_state: 初始状态 (N,)，None 则随机生成
            verbose: 是否打印进度

        Returns:
            演化结果字典
        """
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

        # A8 对称偏好权重
        a8_weights = HammingMeasurement.symmetry_weight_vector(self.layer.N).to(self.device)

        if verbose:
            print(f"[LongRangeEvolver] N={self.layer.N}, T={self.total_steps}, "
                  f"sample_interval={self.sample_interval}")
            print(f"  Source/Sink: {self.layer.ss_config.n_sources} sources, "
                  f"{self.layer.ss_config.n_sinks} sinks")
            print(f"  DAG: {self.layer.dag_enabled}, Strict Axioms: {self.layer.use_strict_axioms}")

        for step in range(self.total_steps):
            w_before = state.sum().long().item()

            # 1. 源注入
            state = self.layer.inject_difference(state)

            # 2. A8 对称偏好调制的单比特翻转
            # 计算每个比特的翻转权重
            flip_weights = self._compute_flip_weights(state, a8_weights)
            state, flip_idx = self.layer.step_hamming(state, flip_weights)

            # 3. 汇吸收
            state = self.layer.absorb_difference(state)

            # 4. 硬投影
            state = self.layer.project_state(state)

            # 5. 记录
            self.flip_history.append(flip_idx)
            w_after = state.sum().long().item()
            self.hamming_weight_history.append(w_after)

            # 6. 采样记录
            if step % self.sample_interval == 0:
                axiom_violations = {}
                if self.layer.axiom_engine:
                    with torch.no_grad():
                        axiom_violations = self.layer.axiom_engine.evaluate(
                            state.unsqueeze(0), state.unsqueeze(0),
                            self.layer, []
                        )

                snapshot = TrajectorySnapshot(
                    step=step,
                    state=state,
                    flip_position=flip_idx,
                    axiom_violations=axiom_violations,
                    flux_stats=self.layer.get_flux_stats(),
                )
                self.snapshots.append(snapshot)

                if verbose and step % (self.sample_interval * 10) == 0:
                    print(f"  Step {step:6d}: w={w_after:3d}, "
                          f"flip={flip_idx:3d}, "
                          f"snapshots={len(self.snapshots)}")

        if verbose:
            print(f"[LongRangeEvolver] Done. {len(self.snapshots)} snapshots recorded.")

        return {
            'total_steps': self.total_steps,
            'n_snapshots': len(self.snapshots),
            'final_state': state,
            'flip_history': self.flip_history,
            'hamming_weight_history': self.hamming_weight_history,
            'snapshots': self.snapshots,
            'flux_stats': self.layer.get_flux_stats(),
        }

    def _compute_flip_weights(self, state: torch.Tensor,
                               a8_weights: torch.Tensor) -> torch.Tensor:
        """计算每个比特的翻转权重

        综合考虑：
        - A8 对称偏好：偏好 w=N/2
        - A6 DAG 方向：不可逆约束
        - 源/汇位置：源附近优先 0→1，汇附近优先 1→0
        """
        N = self.layer.N
        w = state.sum().long().item()

        # 基础权重：均匀
        weights = torch.ones(N, device=self.device)

        # A8 对称偏好调制
        # 如果 w < N/2，偏好 0→1（注入差异）
        # 如果 w > N/2，偏好 1→0（吸收差异）
        if w < N // 2:
            # 增强 0→1 翻转
            weights[state < 0.5] *= 1.5
            weights[state > 0.5] *= 0.8
        elif w > N // 2:
            # 增强 1→0 翻转
            weights[state > 0.5] *= 1.5
            weights[state < 0.5] *= 0.8

        # DAG 方向约束（A6）
        if self.layer.dag_enabled and self.layer.transition.direction is not None:
            direction = self.layer.transition.direction
            # direction=+1 的位只能 0→1，direction=-1 的位只能 1→0
            for i in range(N):
                if direction[i] > 0 and state[i] > 0.5:
                    weights[i] = 0.0  # 禁止 1→0
                elif direction[i] < 0 and state[i] < 0.5:
                    weights[i] = 0.0  # 禁止 0→1

        # 归一化
        weights = weights / weights.sum().clamp(min=1e-8)
        return weights

    def get_trajectory_tensor(self) -> torch.Tensor:
        """获取轨迹张量 (n_snapshots, N)"""
        if not self.snapshots:
            return torch.zeros(0, self.layer.N)
        return torch.stack([s.state for s in self.snapshots], dim=0)

    def get_full_state_history(self) -> torch.Tensor:
        """获取完整状态历史 (T, N)，仅在 record_full=True 时可用"""
        if not hasattr(self, '_full_states') or not self._full_states:
            return torch.zeros(0, self.layer.N)
        return torch.stack(self._full_states, dim=0)

    def get_flip_sequence(self) -> torch.Tensor:
        """获取翻转序列"""
        return torch.tensor(self.flip_history, dtype=torch.long)

    def get_hamming_weight_sequence(self) -> torch.Tensor:
        """获取汉明重量序列"""
        return torch.tensor(self.hamming_weight_history, dtype=torch.long)
