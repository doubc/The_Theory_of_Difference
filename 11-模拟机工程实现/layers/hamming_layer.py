"""
hamming_layer.py — 汉明格点层

基于汉明几何的格点层，使用严格化九公理。
与 L0_binary_lattice 的关键区别：
- 状态空间：{0,1}^N 超立方体（严格二值）
- 距离：汉明距离（替代欧氏距离）
- 演化：单比特翻转（替代连续卷积）
- 公理：严格化九公理（替代连续近似）

对应 WorldBase 形式化 §2.1 的状态空间定义。
"""

from typing import List, Optional, Dict
import torch
from layers.layer_base import LayerBase
from acl.axiom_base import StableStructure
from acl.axioms_strict import AxiomEngineStrict, create_strict_axiom_engine
from engine.hamming_engine import HammingTransition, HammingMeasurement


class HammingLattice(LayerBase):
    """汉明格点层

    状态空间：{0,1}^N 超立方体
    演化：单比特翻转（A4 严格）+ DAG 方向约束（A6 严格）
    公理：严格化九公理引擎
    """

    name = "hamming_lattice"

    def __init__(self, N: int = 16, device: str = "cpu",
                 stability_window: int = 16,
                 use_strict_axioms: bool = True,
                 dag_enabled: bool = True):
        """
        Args:
            N: 比特数（状态空间维度）
            device: 计算设备
            stability_window: 稳定性检测窗口
            use_strict_axioms: 是否使用严格化公理引擎
            dag_enabled: 是否启用 DAG 方向约束
        """
        self.N = N
        self.device = device
        self.stability_window = stability_window
        self.use_strict_axioms = use_strict_axioms
        self.dag_enabled = dag_enabled

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

    # --- 状态空间 ---

    def initial_state(self, batch_size: int = 1) -> torch.Tensor:
        """生成初始状态：随机二值向量"""
        return (torch.rand(batch_size, self.N, device=self.device) < 0.3).float()

    def project_state(self, raw_state: torch.Tensor,
                      mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """投影到合法状态空间 {0,1}^N"""
        binary = (raw_state > 0.5).float()
        if mask is not None:
            binary = binary * mask
        return binary

    def valid_state(self, state: torch.Tensor) -> bool:
        """检查状态是否合法"""
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
        """离散性违背：距离 0/1 的偏离"""
        return (state * (1.0 - state)).mean()

    def locality_violation(self, state: torch.Tensor,
                           next_state: torch.Tensor) -> torch.Tensor:
        """局域性违背：在汉明几何中=0（单比特翻转天然局域）"""
        return torch.tensor(0.0, device=state.device)

    # --- 差异源与汇 ---

    def inject_difference(self, state: torch.Tensor,
                          source_strength: float = 1.0) -> torch.Tensor:
        """A1：在源端注入差异（翻转 source_strength 个 0→1 比特）"""
        result = state.clone()
        flat = result.view(-1, self.N)
        # 找到当前为 0 的比特
        zero_mask = flat < 0.5
        n_zeros = zero_mask.sum().item()
        n_inject = min(int(source_strength), int(n_zeros))
        if n_inject > 0:
            # 随机选择 n_inject 个 0 翻转为 1
            zero_indices = zero_mask.nonzero(as_tuple=True)
            perm = torch.randperm(n_zeros, device=self.device)[:n_inject]
            flat[zero_indices[0][perm], zero_indices[1][perm]] = 1.0
        return result

    def absorb_difference(self, state: torch.Tensor,
                          sink_strength: float = 1.0) -> torch.Tensor:
        """A8：在汇端吸收差异（翻转 sink_strength 个 1→0 比特）"""
        result = state.clone()
        flat = result.view(-1, self.N)
        one_mask = flat > 0.5
        n_ones = one_mask.sum().item()
        n_absorb = min(int(sink_strength), int(n_ones))
        if n_absorb > 0:
            one_indices = one_mask.nonzero(as_tuple=True)
            perm = torch.randperm(n_ones, device=self.device)[:n_absorb]
            flat[one_indices[0][perm], one_indices[1][perm]] = 0.0
        return result

    def apply_boundary_flow(self, state: torch.Tensor,
                            source_strength: float = 1.0,
                            sink_strength: float = 1.0):
        """应用源/汇边界条件，返回流量信息"""
        q_before = self.measure_invariant(state)
        after_source = self.inject_difference(state, source_strength)
        after_sink = self.absorb_difference(after_source, sink_strength)
        q_after = self.measure_invariant(after_sink)
        injected = (self.measure_invariant(after_source) - q_before).clamp(min=0.0)
        absorbed = (q_before + injected - q_after).clamp(min=0.0)
        return after_sink, injected, absorbed

    # --- 稳定性 ---

    def stability_violation(self, window: List[torch.Tensor]) -> torch.Tensor:
        """A7：稳定性违背"""
        if len(window) < 2:
            return torch.tensor(0.0, device=window[0].device)
        states = torch.stack(window, dim=0)
        # 时间波动
        temporal_std = states.std(dim=0).mean()
        # 活动度
        activity = states.mean()
        collapse = torch.relu(torch.tensor(0.05, device=states.device) - activity)
        explosion = torch.relu(activity - torch.tensor(0.95, device=states.device))
        return temporal_std + collapse + explosion

    def detect_stable_structures(self,
                                 history: List[torch.Tensor]) -> List[StableStructure]:
        """从演化历史中检测稳定结构"""
        if len(history) < self.stability_window:
            return []

        window = history[-self.stability_window:]
        states = torch.stack(window, dim=0)

        # 时间稳定性
        temporal_std = states.std(dim=0)
        temporal_mean = states.mean(dim=0)
        # 活跃：既非全0也非全1的区域（有变化的余地）
        active = (temporal_mean > 0.0) & (temporal_mean < 1.0)
        # 或者：所有比特都稳定（包括全0和全1）
        all_stable = (temporal_std < 0.1).all()
        stable = (temporal_std < 0.1) & (active | all_stable)
        stable_mask = stable

        if not stable_mask.any():
            return []

        # 稳定比特构成一个结构
        stable_bits = stable_mask.float()
        n_stable = int(stable_mask.sum().item())
        n_total = self.N

        # 物质更替率
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
        """粗粒化：将稳定结构封装为更高层"""
        if not structures:
            return None
        # 简化：返回一个 N/2 的汉明层
        new_N = max(4, self.N // 2)
        return HammingLattice(N=new_N, device=self.device,
                              stability_window=self.stability_window,
                              use_strict_axioms=self.use_strict_axioms,
                              dag_enabled=self.dag_enabled)

    def measure_ascent_pressure(self, history: List[torch.Tensor],
                                 structures: List) -> float:
        """A5+A9：升维压力"""
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
        """使用严格化公理引擎评估"""
        if self.axiom_engine is None:
            return {}
        return self.axiom_engine.evaluate(
            state, next_state, self, history,
            boundary_info=boundary_info
        )

    def compute_axiom_loss(self, state: torch.Tensor, next_state: torch.Tensor,
                           history: List[torch.Tensor],
                           boundary_info: Optional[Dict] = None) -> torch.Tensor:
        """计算严格化公理总损失"""
        if self.axiom_engine is None:
            return torch.tensor(0.0, device=state.device)
        return self.axiom_engine.total_loss(
            state, next_state, self, history,
            boundary_info=boundary_info
        )

    def step_hamming(self, state: torch.Tensor,
                     weights: Optional[torch.Tensor] = None) -> tuple:
        """执行一步汉明演化（单比特翻转）

        Args:
            state: 当前状态 (B, N) 或 (N,)
            weights: 翻转权重 (B, N) 或 (N,)，由 A8 对称偏好调制

        Returns:
            (新状态, 翻转的比特索引)
        """
        if state.dim() == 1:
            new_state, idx = self.transition.random_flip(state, weights)
            return new_state, idx
        else:
            # 批量处理
            B = state.shape[0]
            new_states = state.clone()
            indices = torch.full((B,), -1, dtype=torch.long, device=state.device)
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
