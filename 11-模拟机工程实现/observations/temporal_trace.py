"""
observations/temporal_trace.py — TemporalTrace 观测框架

Phase 12 P0: 高时间分辨率聚簇过程记录与分析。

设计原则:
  1. 不修改现有 engine 代码（只使用已有 step_callback 接口）
  2. 包装器模式：TemporalTrace 创建并包装 SpatialLongRangeEvolver
  3. 每个 step 记录关键状态，用于事后分析 seal_order、cascade、收敛过程
  
使用方式:
    from observations.temporal_trace import TemporalTrace
    
    trace = TemporalTrace(N=40, sample_interval=1)
    result = trace.run(verbose=False)
    
    # 事后分析
    seal_order = trace.get_seal_order()
    cascade_series = trace.get_cascade_series()
    ...

术语:
  - seal: 比特被系统冻结，不再参与演化
  - seal_order: 比特被密封的时间顺序
  - cascade: 一个 step 内多个比特同时密封的"雪崩"事件
  - convergence: 比特权重接近密封阈值的收敛过程
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Set, Tuple
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver
from acl.axioms_v2 import AxiomConstraints


class StepRecord:
    """单个 step 的完整状态快照"""
    
    __slots__ = ('step', 'state', 'w', 'sealed_bits', 'active_bits',
                 'direction', 'flip_idx', 'n_inject', 'n_absorb', 'n_lateral',
                 'total_injected', 'total_absorbed', 'coords_3d')
    
    def __init__(self, step: int, state: torch.Tensor, w: int,
                 sealed_bits: Set[int], active_bits: Dict[int, int],
                 direction: torch.Tensor,
                 flip_idx: int, n_inject: int, n_absorb: int, n_lateral: int,
                 total_injected: int, total_absorbed: int,
                 coords_3d: Optional[np.ndarray] = None):
        self.step = step
        self.state = state.cpu().clone() if isinstance(state, torch.Tensor) else state
        self.w = w
        self.sealed_bits = set(sealed_bits)
        self.active_bits = dict(active_bits)
        self.direction = direction.cpu().clone() if isinstance(direction, torch.Tensor) else direction
        self.flip_idx = flip_idx
        self.n_inject = n_inject
        self.n_absorb = n_absorb
        self.n_lateral = n_lateral
        self.total_injected = total_injected
        self.total_absorbed = total_absorbed
        self.coords_3d = coords_3d.copy() if coords_3d is not None else None


class TemporalTrace:
    """高时间分辨率观测框架
    
    通过 sample_interval=1 和 step_callback 实现每步记录。
    提供 seal_order、cascade 检测、收敛轨迹等分析接口。
    
    Attributes:
        N: 比特数
        history: List[StepRecord] — 完整步进记录
        N0: 初始 1 的个数（源注入的数量）
        sealed: 系统是否已密封
        seal_step: 密封发生的 step 编号（-1 表示未密封）
        _seal_step_per_bit: bit -> step when first observed sealed
    """
    
    def __init__(self, N: int = 36, sample_interval: int = 1,
                 total_steps: int = 5000, device: str = "cpu",
                 n_hierarchy_bits: Optional[int] = None,
                 L: float = 1.0, partial_sealing: bool = False,
                 verbose: bool = False):
        self.N = N
        self.sample_interval = sample_interval
        self.total_steps = total_steps
        self.device = device
        self.n_hierarchy_bits = n_hierarchy_bits
        self.L = L
        self.partial_sealing = partial_sealing
        self._verbose = verbose
        
        # 运行时状态
        self.history: List[StepRecord] = []
        self.sealed = False
        self.seal_step = -1
        self._seal_step_per_bit: Dict[int, int] = {}
        self._prev_sealed_bits: Set[int] = set()
        self._prev_injected: int = 0
        self._prev_absorbed: int = 0
        
    def _make_evolver(self, initial_state: Optional[torch.Tensor] = None) -> SpatialLongRangeEvolver:
        """创建 SpatialLongRangeEvolver 实例"""
        return SpatialLongRangeEvolver(
            N=self.N,
            total_steps=self.total_steps,
            sample_interval=self.sample_interval,
            device=self.device,
            n_hierarchy_bits=self.n_hierarchy_bits,
            L=self.L,
            partial_sealing=self.partial_sealing,
        )
    
    def _callback(self, step: int, state: torch.Tensor,
                  snapshot: object, constraints: AxiomConstraints) -> None:
        """每步回调：记录 StepRecord"""
        sealed_bits = set(constraints.sealed_bits) if hasattr(constraints, 'sealed_bits') else set()
        active_bits = dict(constraints.active_bits) if hasattr(constraints, 'active_bits') else {}
        direction = constraints.direction if hasattr(constraints, 'direction') else torch.zeros(self.N)
        total_inj = getattr(constraints, 'total_injected', 0)
        total_abs = getattr(constraints, 'total_absorbed', 0)
        
        record = StepRecord(
            step=step,
            state=state,
            w=int(state.sum().item()),
            sealed_bits=sealed_bits,
            active_bits=active_bits,
            direction=direction,
            flip_idx=snapshot.flip_idx if hasattr(snapshot, 'flip_idx') else -1,
            n_inject=snapshot.n_inject if hasattr(snapshot, 'n_inject') else 0,
            n_absorb=snapshot.n_absorb if hasattr(snapshot, 'n_absorb') else 0,
            n_lateral=snapshot.n_lateral if hasattr(snapshot, 'n_lateral') else 0,
            total_injected=total_inj,
            total_absorbed=total_abs,
            coords_3d=snapshot.coords_3d if hasattr(snapshot, 'coords_3d') else None,
        )
        self.history.append(record)
        
        # 检测新密封的比特
        if sealed_bits:
            newly_sealed = sealed_bits - self._prev_sealed_bits
            for b in newly_sealed:
                if b not in self._seal_step_per_bit:
                    self._seal_step_per_bit[b] = step
            self._prev_sealed_bits = set(sealed_bits)
            
            if not self.sealed:
                self.sealed = True
                self.seal_step = step
    
    def run(self, initial_state: Optional[torch.Tensor] = None,
            verbose: Optional[bool] = None) -> Dict:
        """运行 TemporalTrace
        
        Args:
            initial_state: 初始状态张量
            verbose: 是否显示 evolver 输出（默认使用 self._verbose）
            
        Returns:
            Dict: evolution result (同 SpatialLongRangeEvolver.run())
        """
        if verbose is None:
            verbose = self._verbose
        
        # 重置
        self.history = []
        self.sealed = False
        self.seal_step = -1
        self._seal_step_per_bit = {}
        self._prev_sealed_bits = set()
        
        evolver = self._make_evolver(initial_state)
        result = evolver.run(
            initial_state=initial_state,
            verbose=verbose,
            step_callback=self._callback,
        )
        
        return result
    
    # ============================================================
    # 分析接口
    # ============================================================
    
    def get_seal_order(self) -> List[int]:
        """返回比特按密封时间顺序排列的列表
        
        Returns:
            List[int]: 密封时间顺序的比特索引（未密封比特不在列表中）
        """
        if not self._seal_step_per_bit:
            return []
        # 按密封 step 排序
        sorted_bits = sorted(self._seal_step_per_bit.items(), key=lambda x: x[1])
        return [b for b, _ in sorted_bits]
    
    def get_seal_step_map(self) -> Dict[int, int]:
        """返回 {bit: seal_step} 映射
        
        Returns:
            Dict[int, int]: 比特索引 -> 密封时的 step 编号
        """
        return dict(self._seal_step_per_bit)
    
    def get_cascade_series(self) -> List[int]:
        """返回每步新增密封比特数的序列
        
        Returns:
            List[int]: history 长度，每个元素是该 step 新增密封数量
        """
        if not self.history:
            return []
        
        cascade = []
        prev_sealed: Set[int] = set()
        for record in self.history:
            new_sealed = record.sealed_bits - prev_sealed
            cascade.append(len(new_sealed))
            prev_sealed = set(record.sealed_bits)
        return cascade
    
    def get_seal_rate_series(self) -> np.ndarray:
        """返回密封率序列（已密封比例随 step 变化）
        
        Returns:
            np.ndarray: shape (len(history),)，每个元素是密封比例
        """
        if not self.history:
            return np.array([])
        return np.array([len(r.sealed_bits) / max(self.N, 1) for r in self.history])
    
    def get_convergence_trace(self) -> np.ndarray:
        """返回收敛轨迹（汉明重量随 step 变化）
        
        Returns:
            np.ndarray: shape (len(history),)，每个元素是汉明重量
        """
        if not self.history:
            return np.array([])
        return np.array([r.w for r in self.history])
    
    def get_flip_frequency(self, window: int = 50) -> np.ndarray:
        """计算每个比特在滑动窗口内的翻转频率
        
        Args:
            window: 滑动窗口大小（step 数）
            
        Returns:
            np.ndarray: shape (N,)，每个比特在窗口内的翻转次数
        """
        if len(self.history) < 2:
            return np.zeros(self.N)
        
        tail = self.history[-window:] if len(self.history) > window else self.history
        flip_count = np.zeros(self.N)
        prev_state = tail[0].state.numpy() if hasattr(tail[0].state, 'numpy') else np.array(tail[0].state)
        
        for record in tail[1:]:
            curr = record.state.numpy() if hasattr(record.state, 'numpy') else np.array(record.state)
            flip_count += (curr != prev_state).astype(int)
            prev_state = curr
        
        return flip_count
    
    def get_pre_seal_activity(self, lookback: int = 50) -> Dict[str, np.ndarray]:
        """分析密封前的比特活动
        
        对每个密封的比特，回溯密封前的活动模式。
        
        Args:
            lookback: 密封前的回溯 step 数
            
        Returns:
            Dict with:
                'pre_seal_weight': shape (n_sealed, lookback) — 密封前权重轨迹
                'pre_seal_flip_rate': shape (n_sealed,) — 密封前的翻转频率
                'sealed_indices': list of bit indices
        """
        if not self._seal_step_per_bit or len(self.history) < 2:
            return {'pre_seal_weight': np.array([]),
                    'pre_seal_flip_rate': np.array([]),
                    'sealed_indices': []}
        
        # 按密封时间排序，取最早密封的比特（有足够的回溯数据）
        sealed_steps = sorted(self._seal_step_per_bit.items(), key=lambda x: x[1])
        
        pre_weights = []
        flip_rates = []
        sealed_indices = []
        
        max_step = max(r.step for r in self.history)
        
        for bit_idx, seal_step in sealed_steps:
            if seal_step < lookback + 1:
                continue  # 回溯数据不足
            
            # 找到 seal_step 以前的 lookback 步
            start_step = max(0, seal_step - lookback)
            relevant = [r for r in self.history if start_step <= r.step < seal_step]
            
            if len(relevant) < 2:
                continue
            
            # 权重轨迹（该比特的状态）
            weight_trace = []
            for r in relevant:
                s = r.state[bit_idx].item() if hasattr(r.state, 'item') else r.state[bit_idx]
                weight_trace.append(float(s))
            
            # 翻转频率
            flips = sum(1 for i in range(1, len(weight_trace))
                       if weight_trace[i] != weight_trace[i-1])
            
            pre_weights.append(weight_trace)
            flip_rates.append(flips / max(len(relevant) - 1, 1))
            sealed_indices.append(bit_idx)
        
        # 对齐到统一长度
        if pre_weights:
            max_len = max(len(w) for w in pre_weights)
            aligned = np.zeros((len(pre_weights), max_len))
            for i, w in enumerate(pre_weights):
                if len(w) < max_len:
                    aligned[i, -len(w):] = w  # 右对齐
                else:
                    aligned[i] = np.array(w[-max_len:])
            
            return {
                'pre_seal_weight': aligned,
                'pre_seal_flip_rate': np.array(flip_rates),
                'sealed_indices': sealed_indices,
            }
        
        return {'pre_seal_weight': np.array([]),
                'pre_seal_flip_rate': np.array([]),
                'sealed_indices': []}
    
    def get_coupling_lag(self) -> Dict[str, float]:
        """分析子空间耦合时序差（在耦合实验中调用）
        
        需要在多子空间环境下运行，比较各子空间的密封时间。
        单空间调用返回空 dict。
        
        Returns:
            Dict with 'subspace_lags' — 各子空间密封时间差
        """
        # 由 MultiTrace 实现
        return {}
    
    def get_summary(self) -> Dict:
        """返回当前运行的统计摘要
        
        Returns:
            Dict with key metrics
        """
        if not self.history:
            return {'status': 'no_data'}
        
        cascade = self.get_cascade_series()
        max_cascade = max(cascade) if cascade else 0
        total_sealed = len(self._seal_step_per_bit)
        
        # 密封持续时间
        step_range = self.get_convergence_trace()
        
        return {
            'status': 'sealed' if self.sealed else 'running',
            'seal_step': self.seal_step,
            'n_total_steps': len(self.history),
            'n_sealed_bits': total_sealed,
            'max_cascade_size': max_cascade,
            'mean_cascade_size': float(np.mean(cascade)) if cascade else 0.0,
            'cascade_events': sum(1 for c in cascade if c > 1),
            'final_weight': int(step_range[-1]) if len(step_range) > 0 else 0,
            'weight_range': [int(step_range.min()), int(step_range.max())] if len(step_range) > 0 else [0, 0],
        }


class SingleTrace(TemporalTrace):
    """单空间 TemporalTrace（Phase 12 P1 专用）
    
    简化接口，支持批量运行和统计。
    """
    
    def run_batch(self, n_runs: int = 50,
                  initial_state: Optional[torch.Tensor] = None,
                  verbose: bool = False) -> List[Dict]:
        """批量运行并返回摘要
        
        Args:
            n_runs: 运行次数
            initial_state: 初始状态（如果为 None，每轮自动生成随机初始状态）
            verbose: 是否打印运行进度
            
        Returns:
            List[Dict]: 每次运行的 summary
        """
        summaries = []
        for i in range(n_runs):
            if verbose and (i + 1) % 10 == 0:
                print(f"  Run {i + 1}/{n_runs}...")
            self.run(initial_state=initial_state, verbose=False)
            summaries.append(self.get_summary())
        return summaries


class MultiTrace:
    """多子空间 TemporalTrace（Phase 12 P2 专用）
    
    包装 SubspaceAwareEvolver 的完整运行。
    由于 SubspaceAwareEvolver 在内部创建 evolvers，需要通过
    设置 sample_interval=1 和 coupling step_callback 来间接记录。
    
    注意：MultiTrace 不直接包装 SubspaceAwareEvolver（因为它内部
    管理 evolvers），而是事后从 SubspaceAwareEvolver 的结果中提取时序数据。
    """
    
    def __init__(self, field: object, coordinator: object,
                 coupling_engine: object, max_layers: int = 3,
                 verbose: bool = False):
        self.field = field
        self.coordinator = coordinator
        self.coupling_engine = coupling_engine
        self.max_layers = max_layers
        self._verbose = verbose
        self.result = None
    
    def run(self, verbose: Optional[bool] = None) -> Dict:
        """运行多子空间演化并记录
        
        Args:
            verbose: 是否显示输出
            
        Returns:
            Dict: SubspaceAwareEvolver.run() 结果
        """
        if verbose is None:
            verbose = self._verbose
        
        from engine.subspace_evolver import SubspaceAwareEvolver
        
        evolver = SubspaceAwareEvolver(
            field=self.field,
            coordinator=self.coordinator,
            coupling_engine=self.coupling_engine,
            max_layers=self.max_layers,
            verbose=verbose,
        )
        
        self.result = evolver.run(verbose=verbose)
        return self.result
    
    def extract_seal_timing(self) -> Dict[str, Dict]:
        """从 SubspaceAwareEvolver 结果中提取密封时序
        
        Returns:
            {subspace_name: {
                'seal_step': int or None,
                'sealed_bits': int,
                'total_bits': int,
                'layer_id': int,
                'hamming_weight': int,
            }}
        """
        if self.result is None:
            return {}
        
        timing = {}
        solvers = self.result.get('solvers', {})
        for name, solver in solvers.items():
            timing[name] = {
                'seal_step': solver.step_count if solver.is_sealed else None,
                'sealed_bits': len(solver.layer_result.get('sealed_bits', set()))
                    if solver.layer_result else 0,
                'total_bits': solver.final_state.numel() if solver.final_state is not None else 0,
                'layer_id': solver.current_layer if hasattr(solver, 'current_layer') else 0,
                'hamming_weight': solver.hamming_weight,
            }
        
        return timing
    
    def get_summary(self) -> Dict:
        """返回多子空间运行摘要"""
        if self.result is None:
            return {'status': 'no_data'}
        
        timing = self.extract_seal_timing()
        layer_summaries = self.result.get('layer_summaries', [])
        
        return {
            'status': 'completed',
            'n_layers': len(layer_summaries),
            'n_subspaces': len(timing),
            'subspace_timing': timing,
            'all_sealed': all(s['seal_step'] is not None for s in timing.values())
                if timing else False,
        }