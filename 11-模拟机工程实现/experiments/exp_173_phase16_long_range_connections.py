"""
exp_173_phase16_long_range_connections.py — Phase 16 Path B1: 长程连接实验

假设 H16-B1: 非局部交互（长程连接）能使 L1 结构反映 L0 的全局特征。

理论依据:
  差异论当前形式是局部交互 + 串行演化 → 产生"死秩序"（拓扑不变量）
  非局部交互可能打破这种刚性，因为远程比特共享全局信息。

实验设计:
  在每个比特上添加 K 个随机远程连接（非局部邻居）。
  通过 step_callback 在每次采样时施加非局部耦合：
    若连接的两个比特状态不同, 以概率 alpha 使状态同步。
  
  配置: K = 0 (baseline), 1, 2, 3, 5, 10
  
  测量:
  - L0 密封率
  - L1 密封率
  - L1 结构是否反映 L0 集群特征 (Structure Reflection Score)
  - L1 HW 轨迹与 L0 的相似性

用法:
    python exp_173_phase16_long_range_connections.py [--K 3] [--n_runs 5] [--all_K]
"""

import sys
import os
import json
import time
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field

import numpy as np
import torch

# ── 项目根目录 ──
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver, SpatialSnapshot
from engine.cross_layer_evolver import CrossLayerMapper, Layer1Evolver, L1Constraints
from acl.axioms_v2 import AxiomConstraints


# ═══════════════════════════════════════════════════════════════════
# NonlocalSpatialEvolver
# ═══════════════════════════════════════════════════════════════════

class NonlocalSpatialEvolver(SpatialLongRangeEvolver):
    """非局部空间演化器 — 在标准 SpatialLongRangeEvolver 上添加长程连接。

    机制:
      构建 K 个随机远程连接/比特。在 step_callback 中施加非局部耦合:
      若两连接比特状态不同，以概率 alpha 使其同步。
      同步方向: 状态从更多比特的主方向同步（多数决定）。

    效果: 远程比特之间共享全局信息，打破仅靠空间近邻的局部性。
    """

    def __init__(self,
                 K: int = 0,
                 coupling_strength: float = 0.3,
                 **kwargs):
        """
        Args:
            K: 每个比特的长程连接数 (0 = 无长程连接, baseline)
            coupling_strength: 耦合强度 (0.0~1.0)
            **kwargs: 传递给 SpatialLongRangeEvolver 的参数
        """
        super().__init__(**kwargs)
        self.K = K
        self.coupling_strength = coupling_strength
        self._nl_connections: List[Tuple[int, int]] = []     # (i,j) 连接列表
        self._nl_fields: Dict[int, List[int]] = {}           # i -> [j,...] 远程邻居

        if K > 0:
            self._build_nonlocal_connections()
            print(f"[NonlocalSpatialEvolver] K={K}, "
                  f"connections={len(self._nl_connections)}, "
                  f"coupling_strength={coupling_strength}")

    def _build_nonlocal_connections(self):
        """构建 K 个随机远程连接/比特。

        对于每个比特 i, 随机选 K 个 j != i 作为远程连接。
        去重后存入 _nl_connections (undirected)。
        """
        N = self.N
        connection_set: Set[Tuple[int, int]] = set()

        for i in range(N):
            candidates = [j for j in range(N) if j != i]
            if len(candidates) == 0:
                continue
            n_choose = min(self.K, len(candidates))
            chosen = np.random.choice(candidates, size=n_choose, replace=False)
            for j in chosen:
                if i < j:
                    connection_set.add((i, j))

        self._nl_connections = sorted(list(connection_set))

        # 构建邻接查询字典
        self._nl_fields = {i: [] for i in range(N)}
        for (i, j) in self._nl_connections:
            self._nl_fields[i].append(j)
            self._nl_fields[j].append(i)

    def _apply_nonlocal_coupling(self, state: torch.Tensor):
        """在一步耦合中应用非局部同步。

        对每条非局部连接 (i,j):
          若 state[i] != state[j] (差异超过阈值):
            以概率 alpha = coupling_strength / K_avg 翻转一个比特
            使其与远程比特状态一致。

        耦合方向: 远程连接越多、状态越一致的比特"获胜"。
        """
        if self.K == 0 or len(self._nl_connections) == 0:
            return

        N_conn = len(self._nl_connections)
        # 每步只处理部分连接 (抽样加速, 防止 O(N^2))
        # 用随机抽样避免每次都耦合所有连接
        n_sample = min(N_conn, max(100, int(N_conn * 0.2)))
        if n_sample < N_conn:
            indices = np.random.choice(N_conn, size=n_sample, replace=False)
            sample_conns = [self._nl_connections[idx] for idx in indices]
        else:
            sample_conns = self._nl_connections

        alpha = self.coupling_strength * 0.02  # 每次 callback 的温和耦合

        for (i, j) in sample_conns:
            si = state[i].item()
            sj = state[j].item()
            if abs(si - sj) > 0.5:  # 状态不同
                if torch.rand(1).item() < alpha:
                    # 使两者状态一致 (同步)
                    # 偏向多数: 如果该比特的远程邻居多数为 1, 选 1; 反之选 0
                    neighbors = self._nl_fields.get(i, [])
                    n_ones = sum(1 for nb in neighbors if state[nb].item() > 0.5)
                    majority = 1.0 if n_ones > len(neighbors) / 2 else 0.0
                    state[i] = majority

    def run(self,
            initial_state: Optional[torch.Tensor] = None,
            verbose: bool = True,
            step_callback=None,
            post_seal_callback=None):
        """运行演化，在每次采样时施加非局部耦合。"""
        if self.K == 0:
            # 无长程连接: 直接调用父类
            return super().run(
                initial_state=initial_state,
                verbose=verbose,
                step_callback=step_callback,
                post_seal_callback=post_seal_callback,
            )

        # 包装回调: 先施加耦合, 再传原始回调
        orig_cb = step_callback

        def _nl_callback(step, state, snapshot, constraints):
            self._apply_nonlocal_coupling(state)
            if orig_cb is not None:
                orig_cb(step, state, snapshot, constraints)

        return super().run(
            initial_state=initial_state,
            verbose=verbose,
            step_callback=_nl_callback,
            post_seal_callback=post_seal_callback,
        )


# ═══════════════════════════════════════════════════════════════════
# 实验配置
# ═══════════════════════════════════════════════════════════════════

# 长程连接配置梯度
K_CONFIGS = [
    {'K': 0, 'coupling_strength': 0.0, 'label': 'baseline'},       # 无长程连接
    {'K': 1, 'coupling_strength': 0.3, 'label': 'K1_weak'},        # 1 个远程连接/比特
    {'K': 2, 'coupling_strength': 0.3, 'label': 'K2_weak'},        # 2 个远程连接/比特
    {'K': 3, 'coupling_strength': 0.3, 'label': 'K3_medium'},      # 3 个远程连接/比特
    {'K': 5, 'coupling_strength': 0.5, 'label': 'K5_strong'},      # 5 个远程连接/比特
    {'K': 10, 'coupling_strength': 0.5, 'label': 'K10_strong'},    # 10 个远程连接/比特
]

# 默认参数
N = 48                # 网格大小 (3 的倍数)
L0_STEPS = 3000       # L0 演化步数
L1_STEPS = 2000       # L1 演化步数
SAMPLE_INTERVAL = 25  # 采样间隔 (越小耦合越密集)
N_RUNS = 5            # 每配置运行次数


# ═══════════════════════════════════════════════════════════════════
# 单次实验运行
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ExperimentResult:
    """单次实验运行的结果。"""
    config_label: str = ''
    K: int = 0
    trial: int = 0

    # L0
    l0_sealed: bool = False
    l0_seal_step: int = -1
    l0_hw_final: int = 0
    l0_hw_history: List[int] = field(default_factory=list)
    l0_n_clusters: int = 0
    l0_cluster_sizes: List[int] = field(default_factory=list)

    # L1
    l1_sealed: bool = False
    l1_seal_step: int = -1
    l1_hw_final: int = 0
    l1_hw_history: List[int] = field(default_factory=list)

    # Structure reflection
    reflection_score: float = 0.0
    l1_structure_entropy: float = 0.0

    # Timing
    elapsed_sec: float = 0.0

    # Error
    error: Optional[str] = None


def compute_structure_reflection(l0_result: Dict, l1_result: Dict) -> float:
    """计算 L1 结构对 L0 的反映度。

    方法:
      1. 获取 L0 聚类标签
      2. 将 L1 比特按 hierarchy_map 分组
      3. 计算 L1 各组内 HW 的方差 (方差越小 → 结构越一致 → 反映度越高)
      4. reflection_score = 1.0 - normalized_variance

    Returns:
        0.0 ~ 1.0 的反映度分数
    """
    l0_clusters = l0_result.get('clusters', [])
    if not l0_clusters or len(l0_clusters) < 2:
        return 0.0

    # 获取 L1 约束信息 (如果有)
    l1_constraints = l1_result.get('l0_constraints', None)
    if l1_constraints is None:
        return 0.0

    hierarchy_map = l1_constraints.hierarchy_map
    l1_hw = l1_result.get('hw_history', [])

    if not l1_hw:
        return 0.0

    # 计算每组的 HW 方差
    n_clusters = len(l0_clusters)
    group_hws = {cid: [] for cid in range(n_clusters)}

    # 注意: l1_hw 是标量序列, 不是每个比特的 HW
    # 改用 L1 final state 检查每个比特的状态
    l1_final = l1_result.get('final_state', None)
    if l1_final is None:
        return 0.0

    # 将每个 L1 比特按 cluster 分组, 统计组内 1 的比例
    l1_state = l1_final.cpu().numpy() if torch.is_tensor(l1_final) else l1_final
    if len(l1_state) != len(hierarchy_map):
        return 0.0

    for i, cid in enumerate(hierarchy_map):
        if cid >= 0 and cid < n_clusters:
            group_hws[cid].append(1.0 if l1_state[i] > 0.5 else 0.0)

    # 计算每组内 1 的比例的方差
    group_ratios = []
    for cid, states in group_hws.items():
        if states:
            ratio = sum(states) / len(states)
            group_ratios.append(ratio)

    if len(group_ratios) < 2:
        return 0.0

    # 方差: 越小 → 每组内状态越一致 → 结构反映越强
    variance = float(np.var(group_ratios))
    # 归一化: 最大方差 = 0.25 (二项分布, p=0.5)
    max_variance = 0.25
    reflection_score = max(0.0, 1.0 - variance / max_variance)

    return reflection_score


def compute_structure_entropy(l0_result: Dict, l1_result: Dict) -> float:
    """计算 L1 结构熵 (衡量 L1 结构随机性的程度)。

    如果熵高 → L1 结构随机, 未能反映 L0 特征
    如果熵低 → L1 结构有序, 反映了 L0 特征
    """
    l1_constraints = l1_result.get('l0_constraints', None)
    if l1_constraints is None:
        return 1.0

    hierarchy_map = l1_constraints.hierarchy_map
    l1_final = l1_result.get('final_state', None)
    if l1_final is None:
        return 1.0

    l1_state = l1_final.cpu().numpy() if torch.is_tensor(l1_final) else l1_final
    if len(l1_state) != len(hierarchy_map):
        return 1.0

    # 按 cluster 分组, 计算组内 1 的比例
    l0_clusters = l0_result.get('clusters', [])
    n_clusters = len(l0_clusters) if l0_clusters else 1
    group_ratios = []

    for cid in range(n_clusters):
        states = []
        for i, hcid in enumerate(hierarchy_map):
            if hcid == cid:
                states.append(1.0 if l1_state[i] > 0.5 else 0.0)
        if states:
            ratio = sum(states) / len(states)
            group_ratios.append(ratio)

    if len(group_ratios) < 2:
        return 1.0

    # 熵: 对比例分布计算
    # 如果所有比例相同 → 熵最小 (0) → 结构有序
    # 如果比例均匀分布 → 熵最大
    ratios = np.array(group_ratios)
    ratios = np.clip(ratios, 0.001, 0.999)  # 避免 log(0)
    entropy = -np.mean(ratios * np.log(ratios) + (1 - ratios) * np.log(1 - ratios))
    max_entropy = -0.5 * np.log(0.5) - 0.5 * np.log(0.5)  # p=0.5 时的熵
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 1.0

    return float(normalized_entropy)


def run_single_trial(K: int, coupling_strength: float,
                     trial_idx: int = 0,
                     label: str = '') -> ExperimentResult:
    """运行单次实验 (L0→L1 cross-layer + 非局部耦合)。

    Args:
        K: 长程连接数/比特
        coupling_strength: 耦合强度
        trial_idx: 运行序号
        label: 配置标签

    Returns:
        ExperimentResult
    """
    result = ExperimentResult(
        config_label=label,
        K=K,
        trial=trial_idx,
    )
    t0 = time.time()

    try:
        # ── Phase 1: L0 演化 (带长程连接) ──
        l0_evolver = NonlocalSpatialEvolver(
            N=N,
            total_steps=L0_STEPS,
            sample_interval=SAMPLE_INTERVAL,
            device='cpu',
            K=K,
            coupling_strength=coupling_strength,
        )

        l0_result = l0_evolver.run(verbose=False)

        result.l0_sealed = l0_result.get('sealed', False)
        result.l0_seal_step = l0_evolver.seal_step

        hw_hist = l0_result.get('hamming_weight_history', [])
        result.l0_hw_history = hw_hist
        if hw_hist:
            result.l0_hw_final = hw_hist[-1]

        clusters_raw = l0_result.get('clusters', [])
        if clusters_raw:
            result.l0_n_clusters = len(clusters_raw)
            result.l0_cluster_sizes = [len(c) for c in clusters_raw]

        if not result.l0_sealed:
            result.error = 'L0 did not seal'
            result.elapsed_sec = time.time() - t0
            return result

        # ── Phase 2: L0 → L1 约束映射 ──
        mapper = CrossLayerMapper(N0=N, N1=N, device='cpu')
        l1_constraints = mapper.map_from_l0_result(
            l0_evolver=l0_evolver,
            l0_result=l0_result,
        )

        # ── Phase 3: L1 演化 ──
        l1_evolver = Layer1Evolver(
            N1=N,
            total_steps=L1_STEPS,
            sample_interval=SAMPLE_INTERVAL,
            device='cpu',
            l0_constraints=l1_constraints,
            feedback_from_l0=False,
        )
        l1_evolver._install_constraint_callback()
        l1_result = l1_evolver.run()

        result.l1_sealed = l1_result.get('sealed', False)
        result.l1_seal_step = l1_result.get('seal_step', -1)

        l1_hw = l1_result.get('hw_history', [])
        result.l1_hw_history = l1_hw
        if l1_hw:
            result.l1_hw_final = l1_hw[-1]

        # Inject l0_constraints into l1_result for structure analysis
        l1_result['l0_constraints'] = l1_constraints
        l1_result['clusters'] = clusters_raw

        # ── Phase 4: 结构分析 ──
        result.reflection_score = compute_structure_reflection(l0_result, l1_result)
        result.structure_entropy = compute_structure_entropy(l0_result, l1_result)

        result.elapsed_sec = time.time() - t0

    except Exception as e:
        import traceback
        result.error = f"{type(e).__name__}: {e}"
        result.elapsed_sec = time.time() - t0
        print(f"    ERROR in trial {trial_idx}: {e}")
        traceback.print_exc()

    return result


# ═══════════════════════════════════════════════════════════════════
# 汇总与分析
# ═══════════════════════════════════════════════════════════════════

def run_experiment_for_K(K: int, coupling_strength: float,
                         label: str, n_runs: int = N_RUNS) -> List[ExperimentResult]:
    """对给定 K 配置运行多次实验。"""
    print(f"\n{'─' * 60}")
    print(f"Config: {label} (K={K}, coupling={coupling_strength})")
    print(f"  Running {n_runs} trials...")

    results = []
    for trial in range(n_runs):
        print(f"  Trial {trial + 1}/{n_runs}...", end=' ', flush=True)
        r = run_single_trial(K, coupling_strength, trial, label)
        results.append(r)
        print(f"L0_seal={r.l0_sealed}, L1_seal={r.l1_sealed}, "
              f"reflection={r.reflection_score:.3f} "
              f"({r.elapsed_sec:.1f}s)")
        if r.error:
            print(f"    ⚠ {r.error}")

    return results


def analyze_results(all_results: Dict[str, List[ExperimentResult]]):
    """分析并打印所有配置的统计结果。"""
    print(f"\n{'=' * 70}")
    print("EXP_173 STATISTICAL SUMMARY")
    print(f"{'=' * 70}")

    for label, results in all_results.items():
        n = len(results)
        valid = [r for r in results if not r.error]
        n_valid = len(valid)

        print(f"\n{'─' * 50}")
        print(f"{label} (K={results[0].K if results else '?'}, N={n} trials, "
              f"{n_valid} valid):")

        if n_valid == 0:
            print("  ⚠ No valid trials")
            continue

        # L0 seal
        l0_sealed = [r for r in valid if r.l0_sealed]
        l0_rate = len(l0_sealed) / n_valid * 100
        print(f"  L0 seal rate: {len(l0_sealed)}/{n_valid} = {l0_rate:.1f}%")

        if l0_sealed:
            steps = [r.l0_seal_step for r in l0_sealed]
            print(f"  L0 seal step: mean={np.mean(steps):.1f}±{np.std(steps):.1f}")

            hw = [r.l0_hw_final for r in l0_sealed]
            print(f"  L0 HW final: mean={np.mean(hw):.1f}±{np.std(hw):.1f}")

            nc = [r.l0_n_clusters for r in l0_sealed]
            print(f"  L0 clusters: mean={np.mean(nc):.1f}±{np.std(nc):.1f}")

        # L1 seal
        l1_sealed = [r for r in valid if r.l1_sealed]
        l1_rate = len(l1_sealed) / n_valid * 100
        print(f"  L1 seal rate: {len(l1_sealed)}/{n_valid} = {l1_rate:.1f}%")

        if l1_sealed:
            steps = [r.l1_seal_step for r in l1_sealed]
            print(f"  L1 seal step: mean={np.mean(steps):.1f}±{np.std(steps):.1f}")

            hw = [r.l1_hw_final for r in l1_sealed]
            print(f"  L1 HW final: mean={np.mean(hw):.1f}±{np.std(hw):.1f}")

        # Reflection score
        scores = [r.reflection_score for r in valid if r.l1_sealed]
        if scores:
            print(f"  Reflection score (sealed only): "
                  f"mean={np.mean(scores):.3f}±{np.std(scores):.3f}")

        # Entropy
        entropies = [r.structure_entropy for r in valid if r.l1_sealed]
        if entropies:
            print(f"  Structure entropy (sealed only): "
                  f"mean={np.mean(entropies):.3f}±{np.std(entropies):.3f}")

        # K=0 比较
        if results[0].K == 0:
            print(f"  [BASELINE] K=0 reference")


def save_results(all_results: Dict[str, List[ExperimentResult]], timestamp: str):
    """保存结果到 JSON。"""
    results_dir = PROJECT_ROOT / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)

    # 转为可序列化
    serializable = {}
    for label, results in all_results.items():
        serializable[label] = []
        for r in results:
            d = {
                'config_label': r.config_label,
                'K': r.K,
                'trial': r.trial,
                'l0_sealed': r.l0_sealed,
                'l0_seal_step': r.l0_seal_step,
                'l0_hw_final': r.l0_hw_final,
                'l0_n_clusters': r.l0_n_clusters,
                'l1_sealed': r.l1_sealed,
                'l1_seal_step': r.l1_seal_step,
                'l1_hw_final': r.l1_hw_final,
                'reflection_score': r.reflection_score,
                'structure_entropy': r.l1_structure_entropy,
                'elapsed_sec': r.elapsed_sec,
                'error': r.error,
            }
            serializable[label].append(d)

    result_file = results_dir / f'exp_173_results_{timestamp}.json'
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {result_file}")
    return result_file


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='exp_173: 长程连接实验 (Phase 16 Path B1)')
    parser.add_argument('--K', type=int, default=None,
                        help='长程连接数/比特 (不指定则运行所有配置)')
    parser.add_argument('--coupling', type=float, default=None,
                        help='耦合强度 (不指定则使用默认)')
    parser.add_argument('--n_runs', type=int, default=N_RUNS,
                        help=f'每配置运行次数 (默认 {N_RUNS})')
    parser.add_argument('--all_K', action='store_true',
                        help='运行所有 K 配置')
    parser.add_argument('--fast', action='store_true',
                        help='快速模式 (n_runs=2, 仅验证)')
    args = parser.parse_args()

    # 决定运行的配置
    if args.fast:
        n_runs = 2
    else:
        n_runs = args.n_runs

    if args.all_K:
        configs_to_run = K_CONFIGS
    elif args.K is not None:
        # 查找匹配的配置
        matching = [c for c in K_CONFIGS if c['K'] == args.K]
        if not matching:
            print(f"Unknown K={args.K}. Available: {[c['K'] for c in K_CONFIGS]}")
            return
        cfg = matching[0]
        if args.coupling is not None:
            cfg['coupling_strength'] = args.coupling
        configs_to_run = [cfg]
    else:
        # 默认: 只运行 baseline (K=0) 和 K=3 (medium)
        configs_to_run = [c for c in K_CONFIGS if c['K'] in (0, 3)]

    # ─── Print header ───
    print("=" * 70)
    print("exp_173 — Phase 16 Path B1: 长程连接实验 (Non-local Connections)")
    print("=" * 70)
    print(f"  N={N}, L0_steps={L0_STEPS}, L1_steps={L1_STEPS}")
    print(f"  sample_interval={SAMPLE_INTERVAL}")
    print(f"  n_runs={n_runs}")
    print(f"  Configs: {[c['label'] for c in configs_to_run]}")
    print(f"  K values: {[c['K'] for c in configs_to_run]}")
    print(f"  Total experiments: {len(configs_to_run) * n_runs}")
    print("=" * 70)

    t_start = time.time()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # ─── 运行所有配置 ───
    all_results: Dict[str, List[ExperimentResult]] = {}

    for cfg in configs_to_run:
        results = run_experiment_for_K(
            K=cfg['K'],
            coupling_strength=cfg['coupling_strength'],
            label=cfg['label'],
            n_runs=n_runs,
        )
        all_results[cfg['label']] = results

    total_elapsed = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"Total elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print(f"{'=' * 70}")

    # ─── 分析 ───
    analyze_results(all_results)

    # ─── 保存 ───
    save_results(all_results, timestamp)


if __name__ == '__main__':
    main()