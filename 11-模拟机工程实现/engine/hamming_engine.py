"""
hamming_engine.py — 汉明几何引擎

核心：从欧氏几何转向汉明几何
- 状态空间：{0,1}^N 超立方体
- 距离：汉明距离 d_H(x,y) = |{i: x_i ≠ y_i}|
- 重量：w(x) = Σx_i（差异密度）
- 中截面：w = N/2（最大差异层，物理活跃层）

对应 WorldBase 形式化 §2.1-2.2 的状态空间定义。
"""

import torch
import torch.nn.functional as F
from typing import List, Optional, Tuple


class HammingState:
    """汉明状态空间管理

    将连续状态 tensor 映射到离散汉明空间，
    同时维护连续近似（用于梯度回传）。
    """

    def __init__(self, binary_mask: torch.Tensor, temperature: float = 0.1):
        """
        Args:
            binary_mask: (N,) 或 (B, C, H, W) 的二值掩码
            temperature: Gumbel-Softmax 温度（越低越接近硬二值）
        """
        self.binary = binary_mask.float()
        self.temperature = temperature
        self.shape = binary_mask.shape
        self.N = binary_mask.numel() if binary_mask.dim() == 1 else binary_mask.shape[-1]

    @classmethod
    def from_continuous(cls, continuous_state: torch.Tensor,
                        threshold: float = 0.5) -> "HammingState":
        """从连续状态创建汉明状态"""
        binary = (continuous_state > threshold).float()
        return cls(binary)

    @property
    def hamming_weight(self) -> torch.Tensor:
        """汉明重量 w(x) = Σx_i"""
        return self.binary.sum(dim=-1)

    @property
    def hamming_weight_normalized(self) -> torch.Tensor:
        """归一化汉明重量 w(x)/N ∈ [0,1]"""
        return self.hamming_weight / max(1, self.N)

    @property
    def mid_surface_ratio(self) -> float:
        """中截面比率：w(x)/N 接近 0.5 的程度"""
        w_norm = self.hamming_weight_normalized.float().mean()
        return 1.0 - 2.0 * abs(w_norm - 0.5)

    def gumbel_softmax_sample(self) -> torch.Tensor:
        """Gumbel-Softmax 采样（可微分的硬二值近似）"""
        logits = torch.stack([1.0 - self.binary, self.binary], dim=-1)
        # 添加 Gumbel 噪声
        gumbel = -torch.log(-torch.log(torch.rand_like(logits).clamp(min=1e-8)))
        y = logits + gumbel
        return F.softmax(y / self.temperature, dim=-1)[..., 1]

    def hard_project(self) -> torch.Tensor:
        """硬投影到 {0,1}"""
        return (self.binary > 0.5).float()


class HammingTransition:
    """汉明跃迁算子

    严格实现 A4（单比特翻转）和 A6（DAG 方向约束）。
    每步恰好翻转一个比特，翻转方向由 DAG 约束决定。
    """

    def __init__(self, N: int, dag_enabled: bool = True):
        """
        Args:
            N: 比特数
            dag_enabled: 是否启用 DAG 方向约束（A6 不可逆性）
        """
        self.N = N
        self.dag_enabled = dag_enabled
        # DAG 方向矩阵：direction[i] = +1 表示只能从 0→1，-1 表示只能从 1→0
        self.direction = torch.zeros(N)  # 0 = 双向允许

    def set_dag_direction(self, direction: torch.Tensor):
        """设置 DAG 方向约束（A6）"""
        self.direction = direction.clone()

    def get_allowed_flips(self, state: torch.Tensor) -> torch.Tensor:
        """获取当前状态下允许翻转的比特位置

        Returns:
            allowed: (N,) bool tensor，True 表示该位置允许翻转
        """
        allowed = torch.ones(self.N, dtype=torch.bool, device=state.device)

        if self.dag_enabled:
            # DAG 约束：direction=+1 的位只能 0→1（当前为 1 则不允许翻转）
            #           direction=-1 的位只能 1→0（当前为 0 则不允许翻转）
            for i in range(self.N):
                if self.direction[i] > 0 and state.flatten()[i] > 0.5:
                    allowed[i] = False
                elif self.direction[i] < 0 and state.flatten()[i] < 0.5:
                    allowed[i] = False

        return allowed

    def single_bit_flip(self, state: torch.Tensor,
                        flip_idx: int) -> torch.Tensor:
        """单比特翻转（A4 严格实现）

        Args:
            state: 当前状态 (N,) 或 (..., N)
            flip_idx: 要翻转的比特索引

        Returns:
            翻转后的状态
        """
        result = state.clone()
        flat = result.view(-1, self.N) if result.dim() > 1 else result.unsqueeze(0)
        flat[0, flip_idx] = 1.0 - flat[0, flip_idx]
        return result

    def random_flip(self, state: torch.Tensor,
                    weights: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, int]:
        """随机单比特翻转（受 DAG 约束和权重调制）

        Args:
            state: 当前状态
            weights: (N,) 翻转权重（由 A8 对称偏好调制）

        Returns:
            (新状态, 翻转的比特索引)
        """
        allowed = self.get_allowed_flips(state)
        if not allowed.any():
            return state.clone(), -1

        if weights is None:
            weights = torch.ones(self.N, device=state.device)

        # 只从允许的位置采样
        flip_probs = weights * allowed.float()
        flip_probs = flip_probs / flip_probs.sum().clamp(min=1e-8)
        flip_idx = torch.multinomial(flip_probs, 1).item()

        new_state = self.single_bit_flip(state, flip_idx)
        return new_state, flip_idx

    def batch_flip(self, state: torch.Tensor,
                   flip_indices: torch.Tensor) -> torch.Tensor:
        """批量单比特翻转（用于并行模拟多个世界）

        Args:
            state: (B, N) 批量状态
            flip_indices: (B,) 每个样本要翻转的比特索引

        Returns:
            (B, N) 翻转后的批量状态
        """
        result = state.clone()
        B = state.shape[0]
        for b in range(B):
            if flip_indices[b] >= 0:
                result[b, flip_indices[b]] = 1.0 - result[b, flip_indices[b]]
        return result


class HammingMeasurement:
    """汉明几何测量

    对应 WorldBase 中从汉明距离推导物理量的测量方法。
    """

    @staticmethod
    def hamming_distance(state_a: torch.Tensor,
                         state_b: torch.Tensor) -> int:
        """汉明距离 d_H(a,b) = |{i: a_i ≠ b_i}|"""
        return (state_a != state_b).sum().item()

    @staticmethod
    def hamming_weight(state: torch.Tensor) -> int:
        """汉明重量 w(x) = Σx_i"""
        return state.sum().item()

    @staticmethod
    def normalized_hamming_weight(state: torch.Tensor) -> float:
        """归一化汉明重量 w(x)/N"""
        return state.sum().item() / max(1, state.numel())

    @staticmethod
    def surface_distance(state: torch.Tensor,
                         reference: torch.Tensor) -> float:
        """到参考态的汉明距离（用于引力势近似）

        对应 WorldBase §3.4：Φ_N(x) = -Σ_s 1/d_H(x,s)
        """
        d = HammingMeasurement.hamming_distance(state, reference)
        return 1.0 / max(1, d)

    @staticmethod
    def symmetry_weight(w: int, N: int) -> float:
        """A8 对称偏好权重 ρ(w) = C(N,w) / C(N,N/2)

        偏好 w=N/2 态，随 |w-N/2| 单调递减。
        """
        if N == 0:
            return 1.0
        from math import comb
        return comb(N, w) / comb(N, N // 2)

    @staticmethod
    def symmetry_weight_vector(N: int) -> torch.Tensor:
        """预计算所有重量的对称偏好权重向量

        Returns:
            weights: (N+1,) 权重向量
        """
        weights = torch.tensor(
            [HammingMeasurement.symmetry_weight(w, N) for w in range(N + 1)],
            dtype=torch.float32
        )
        return weights

    @staticmethod
    def mid_surface_proximity(state: torch.Tensor) -> float:
        """到中截面（w=N/2）的接近程度

        返回值 ∈ [0,1]，1=恰在中截面，0=在最底层或最顶层
        """
        w = state.sum().item()
        N = state.numel()
        if N == 0:
            return 0.0
        return 1.0 - 2.0 * abs(w / N - 0.5)

    @staticmethod
    def level_depth(state: torch.Tensor) -> int:
        """层级深度 = 汉明重量（A1）"""
        return state.sum().item()

    @staticmethod
    def is_ascending(state_from: torch.Tensor,
                     state_to: torch.Tensor) -> bool:
        """检查是否沿层级深度上升（A1 单调累积）"""
        return state_to.sum().item() >= state_from.sum().item()
