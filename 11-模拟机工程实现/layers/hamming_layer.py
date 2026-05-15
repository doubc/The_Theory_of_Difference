"""
hamming_layer.py — 汉明格点层（增强版）

增强点：
1. 多源多汇系统（不再是随机翻转）
2. 源/汇位置基于公理约束动态选择
3. 通量路径追踪（用于涌现检测）
4. 纯演化模式（无训练，只看涌现）

对应 WorldBase 形式化 §2.1-2.2 + §3.4 的通量系统。
"""

from typing import List, Optional, Dict, Tuple
import torch
from layers.layer_base import LayerBase
from acl.axiom_base import StableStructure
from acl.axioms_strict import AxiomEngineStrict, create_strict_axiom_engine
from engine.hamming_engine import HammingTransition, HammingMeasurement


class SourceSinkConfig:
    """源/汇配置"""
    def __init__(self,
                 n_sources: int = 2,
                 n_sinks: int = 2,
                 source_strength: int = 2,
                 sink_strength: int = 2,
                 dynamic_position: bool = True,
                 flux_conservation: bool = True):
        self.n_sources = n_sources
        self.n_sinks = n_sinks
        self.source_strength = source_strength  # 每步每个源注入的比特数
        self.sink_strength = sink_strength      # 每步每个汇吸收的比特数
        self.dynamic_position = dynamic_position  # 是否动态选择源/汇位置
        self.flux_conservation = flux_conservation  # 是否保持通量守恒


class HammingLattice(LayerBase):
    """汉明格点层（增强版）

    状态空间：{0,1}^N 超立方体
    演化：单比特翻转（A4 严格）+ DAG 方向约束（A6 严格）
    公理：严格化九公理引擎
    通量：多源多汇 + 动态位置 + 通量追踪
    """

    name = "hamming_lattice"

    def __init__(self, N: int = 16, device: str = "cpu",
                 stability_window: int = 16,
                 use_strict_axioms: bool = True,
                 dag_enabled: bool = True,
                 source_sink_config: Optional[SourceSinkConfig] = None):
        self.N = N
        self.device = device
        self.stability_window = stability_window
        self.use_strict_axioms = use_strict_axioms
        self.dag_enabled = dag_enabled

        # 源/汇配置
        self.ss_config = source_sink_config or SourceSinkConfig()

        # 汉明跃迁算子
        self.transition = HammingTransition(N=N, dag_enabled=dag_enabled)

        # 严格化公理引擎
        if use_strict_axioms:
            self.axiom_engine = create_strict_axiom_engine(N=N)
        else:
            self.axiom_engine = None

        # 结构追踪
        self._struct_registry: Dict[int, dict] = {}
        self._next_struct_id = 0

        # 公理权重（兼容旧接口）
        self._axiom_weights = {
            "A2_discrete_encoding": 1.0,
            "A3_locality": 1.0,
            "A4_minimal_variation": 0.8,
            "A5_conservation": 1.0,
            "A7_stability": 0.8,
        }

        # 通量追踪
        self._flux_log: List[Dict] = []

    # --- 状态空间 ---

    def initial_state(self, batch_size: int = 1) -> torch.Tensor:
        """生成初始状态：随机二值向量（低密度）"""
        return (torch.rand(batch_size, self.N, device=self.device) < 0.3).float()

    def project_state(self, raw_state: torch.Tensor,
                      mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """投影到合法状态空间 {0,1}^N"""
        binary = (raw_state > 0.5).float()
        if mask is not None:
            binary = binary * mask
        return binary

    def valid_state(self, state: torch.Tensor) -> bool:
        return state.shape[-1] == self.N

    # --- 差异度量 ---

    def measure_difference(self, state: torch.Tensor) -> torch.Tensor:
        """差异分布：每个比特与均值的偏离"""
        mean = state.mean(dim=-1, keepdim=True)
        return (state - mean).abs()

    def measure_invariant(self, state: torch.Tensor) -> torch.Tensor:
        """守恒量：汉明重量（总激活量）"""
        return state.sum(dim=-1, keepdim=True)

    def transition_cost(self, state: torch.Tensor,
                        next_state: torch.Tensor) -> torch.Tensor:
        """过渡成本：汉明距离"""
        hard_state = (state > 0.5).float()
        hard_next = (next_state > 0.5).float()
        return (hard_next - hard_state).abs().sum().float()

    def discreteness_violation(self, state: torch.Tensor) -> torch.Tensor:
        return (state * (1.0 - state)).mean()

    def locality_violation(self, state: torch.Tensor,
                           next_state: torch.Tensor) -> torch.Tensor:
        return torch.tensor(0.0, device=state.device)

    # --- 增强源/汇系统 ---

    def _select_source_positions(self, state: torch.Tensor) -> torch.Tensor:
        """动态选择源位置（A1：差异注入点）

        策略：
        - 优先选择当前为 0 的比特（注入差异 = 0→1）
        - 基于 A8 对称偏好：如果当前 w < N/2，增强注入
        - 基于 A5 守恒量：如果当前总通量不足，增强注入
        - 多源：选择多个位置形成空间分布

        Returns:
            source_positions: (n_sources,) 源位置索引
        """
        flat = state.flatten()
        zero_mask = flat < 0.5
        zero_indices = zero_mask.nonzero(as_tuple=True)[0]

        if zero_indices.numel() == 0:
            return torch.tensor([], dtype=torch.long, device=self.device)

        n = min(self.ss_config.n_sources, zero_indices.numel())

        if self.ss_config.dynamic_position:
            # 动态选择：基于 A8 对称偏好权重
            w = flat.sum().item()
            N = self.N

            # 如果 w < N/2，更倾向于注入（帮助达到中截面）
            inject_bias = 1.0
            if w < N / 2:
                inject_bias = 1.5  # 增强注入
            elif w > N / 2:
                inject_bias = 0.5  # 减弱注入

            # 随机选择，但偏向低密度区域
            probs = torch.ones(zero_indices.numel(), device=self.device) * inject_bias
            # 额外偏向：选择与其他已激活比特距离较远的位置（扩散）
            if w > 0:
                one_indices = (flat > 0.5).nonzero(as_tuple=True)[0]
                for idx in range(zero_indices.numel()):
                    pos = zero_indices[idx].item()
                    # 计算到最近已激活比特的距离
                    if one_indices.numel() > 0:
                        min_dist = min(abs(pos - int(o)) for o in one_indices[:50])
                        probs[idx] *= (1.0 + min_dist / N)  # 越远越优先

            probs = probs / probs.sum()
            selected = torch.multinomial(probs, n, replacement=False)
            return zero_indices[selected]
        else:
            # 静态随机选择
            perm = torch.randperm(zero_indices.numel(), device=self.device)[:n]
            return zero_indices[perm]

    def _select_sink_positions(self, state: torch.Tensor) -> torch.Tensor:
        """动态选择汇位置（A8：差异吸收点）

        策略：
        - 优先选择当前为 1 的比特（吸收差异 = 1→0）
        - 基于 A8 对称偏好：如果当前 w > N/2，增强吸收
        - 基于 A5 守恒量：如果当前总通量过剩，增强吸收
        - 多汇：选择多个位置形成空间分布

        Returns:
            sink_positions: (n_sinks,) 汇位置索引
        """
        flat = state.flatten()
        one_mask = flat > 0.5
        one_indices = one_mask.nonzero(as_tuple=True)[0]

        if one_indices.numel() == 0:
            return torch.tensor([], dtype=torch.long, device=self.device)

        n = min(self.ss_config.n_sinks, one_indices.numel())

        if self.ss_config.dynamic_position:
            w = flat.sum().item()
            N = self.N

            absorb_bias = 1.0
            if w > N / 2:
                absorb_bias = 1.5  # 增强吸收
            elif w < N / 2:
                absorb_bias = 0.5  # 减弱吸收

            probs = torch.ones(one_indices.numel(), device=self.device) * absorb_bias
            probs = probs / probs.sum()
            selected = torch.multinomial(probs, n, replacement=False)
            return one_indices[selected]
        else:
            perm = torch.randperm(one_indices.numel(), device=self.device)[:n]
            return one_indices[perm]

    def inject_difference(self, state: torch.Tensor,
                          source_strength: Optional[int] = None) -> torch.Tensor:
        """A1：在源端注入差异（增强版）

        多源 + 动态位置选择 + 通量追踪
        """
        if source_strength is None:
            source_strength = self.ss_config.source_strength
        source_strength = int(source_strength)

        result = state.clone()
        flat = result.flatten()

        source_positions = self._select_source_positions(state)
        n_inject = min(int(source_strength * self.ss_config.n_sources), source_positions.numel())

        if n_inject > 0:
            injected_positions = source_positions[:n_inject]
            flat[injected_positions] = 1.0

            # 记录通量
            self._flux_log.append({
                'type': 'inject',
                'positions': injected_positions.tolist(),
                'n_bits': n_inject,
                'w_before': flat.sum().item() - n_inject,
                'w_after': flat.sum().item(),
            })

        return result

    def absorb_difference(self, state: torch.Tensor,
                          sink_strength: Optional[int] = None) -> torch.Tensor:
        """A8：在汇端吸收差异（增强版）

        多汇 + 动态位置选择 + 通量追踪
        """
        if sink_strength is None:
            sink_strength = self.ss_config.sink_strength
        sink_strength = int(sink_strength)

        result = state.clone()
        flat = result.flatten()

        sink_positions = self._select_sink_positions(state)
        n_absorb = min(int(sink_strength * self.ss_config.n_sinks), sink_positions.numel())

        if n_absorb > 0:
            absorbed_positions = sink_positions[:n_absorb]
            flat[absorbed_positions] = 0.0

            self._flux_log.append({
                'type': 'absorb',
                'positions': absorbed_positions.tolist(),
                'n_bits': n_absorb,
                'w_before': flat.sum().item() + n_absorb,
                'w_after': flat.sum().item(),
            })

        return result

    def apply_boundary_flow(self, state: torch.Tensor,
                            source_strength: Optional[int] = None,
                            sink_strength: Optional[int] = None):
        """应用源/汇边界条件，返回流量信息（增强版）"""
        q_before = self.measure_invariant(state)
        after_source = self.inject_difference(state, source_strength)
        after_sink = self.absorb_difference(after_source, sink_strength)
        q_after = self.measure_invariant(after_sink)

        injected = (self.measure_invariant(after_source) - q_before).clamp(min=0.0)
        absorbed = (q_before + injected - q_after).clamp(min=0.0)

        return after_sink, injected, absorbed

    def get_flux_stats(self) -> Dict:
        """获取通量统计"""
        if not self._flux_log:
            return {'total_inject': 0, 'total_absorb': 0, 'net_flux': 0}

        total_inject = sum(e['n_bits'] for e in self._flux_log if e['type'] == 'inject')
        total_absorb = sum(e['n_bits'] for e in self._flux_log if e['type'] == 'absorb')
        return {
            'total_inject': total_inject,
            'total_absorb': total_absorb,
            'net_flux': total_inject - total_absorb,
            'n_events': len(self._flux_log),
        }

    def clear_flux_log(self):
        """清除通量记录"""
        self._flux_log = []

    # --- 稳定性 ---

    def stability_violation(self, window: List[torch.Tensor]) -> torch.Tensor:
        if len(window) < 2:
            return torch.tensor(0.0, device=window[0].device)
        states = torch.stack(window, dim=0)
        temporal_std = states.std(dim=0).mean()
        activity = states.mean()
        collapse = torch.relu(torch.tensor(0.05, device=states.device) - activity)
        explosion = torch.relu(activity - torch.tensor(0.95, device=states.device))
        return temporal_std + collapse + explosion

    def detect_stable_structures(self, history: List[torch.Tensor]) -> List[StableStructure]:
        if len(history) < self.stability_window:
            return []
        window = history[-self.stability_window:]
        states = torch.stack(window, dim=0)
        temporal_std = states.std(dim=0)
        temporal_mean = states.mean(dim=0)
        active = (temporal_mean > 0.0) & (temporal_mean < 1.0)
        all_stable = (temporal_std < 0.1).all()
        stable = (temporal_std < 0.1) & (active | all_stable)
        stable_mask = stable

        if not stable_mask.any():
            return []

        stable_bits = stable_mask.float()
        n_stable = int(stable_mask.sum().item())
        n_total = self.N

        if states.shape[0] > 1:
            diffs = (states[1:] - states[:-1]).abs()
            turnover = diffs.mean().item()
        else:
            turnover = 0.0

        struct = StableStructure(
            mask=stable_mask,
            lifetime=self.stability_window,
            pattern_signature=temporal_mean.mean().unsqueeze(0),
            boundary_map=stable_bits,
            material_turnover=turnover,
            source_layer=self.name,
            connectivity_ratio=n_stable / max(1, n_total),
            boundary_closure_score=1.0 - (n_stable / max(1, n_total)),
            source_trace=[{"n_stable_bits": n_stable, "n_total": n_total}],
        )
        return [struct]

    # --- 粗粒化与升维 ---

    def coarse_grain(self, structures: List) -> Optional['LayerBase']:
        if not structures:
            return None
        new_N = max(4, self.N // 2)
        return HammingLattice(N=new_N, device=self.device,
                              stability_window=self.stability_window,
                              use_strict_axioms=self.use_strict_axioms,
                              dag_enabled=self.dag_enabled,
                              source_sink_config=self.ss_config)

    def measure_ascent_pressure(self, history: List[torch.Tensor],
                                 structures: List) -> float:
        if len(history) < 2 or not structures:
            return 0.0
        q1 = self.measure_invariant(history[-2])
        q2 = self.measure_invariant(history[-1])
        residual = ((q2 - q1) ** 2).mean().item()
        total_bits = self.N
        stable_bits = sum(s.mask.sum().item() for s in structures)
        density = stable_bits / max(1, total_bits)
        return residual * density

    # --- 配置 ---

    def get_axiom_weight(self, axiom_name: str) -> float:
        return self._axiom_weights.get(axiom_name, 0.0)

    # --- 严格化公理引擎接口 ---

    def evaluate_axioms(self, state: torch.Tensor, next_state: torch.Tensor,
                        history: List[torch.Tensor],
                        boundary_info: Optional[Dict] = None) -> Dict:
        if self.axiom_engine is None:
            return {}
        return self.axiom_engine.evaluate(
            state, next_state, self, history,
            boundary_info=boundary_info
        )

    def compute_axiom_loss(self, state: torch.Tensor, next_state: torch.Tensor,
                           history: List[torch.Tensor],
                           boundary_info: Optional[Dict] = None) -> torch.Tensor:
        if self.axiom_engine is None:
            return torch.tensor(0.0, device=state.device)
        return self.axiom_engine.total_loss(
            state, next_state, self, history,
            boundary_info=boundary_info
        )

    def step_hamming(self, state: torch.Tensor,
                     weights: Optional[torch.Tensor] = None) -> tuple:
        """执行一步汉明演化（单比特翻转）"""
        if state.dim() == 1:
            new_state, idx = self.transition.random_flip(state, weights)
            return new_state, idx
        else:
            B = state.shape[0]
            new_states = state.clone()
            indices = torch.full((B,), -1, dtype=torch.long, device=self.device)
            for b in range(B):
                w = weights[b] if weights is not None and weights.dim() > 1 else weights
                new_states[b], indices[b] = self.transition.random_flip(state[b], w)
            return new_states, indices

    def reset(self):
        """重置有状态的公理（新 episode 时调用）"""
        if self.axiom_engine:
            self.axiom_engine.reset()
        self._struct_registry = {}
        self._next_struct_id = 0
        self._flux_log = []
