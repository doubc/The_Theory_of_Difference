"""
exp_175_phase16_smallworld.py — Phase 16 Path B3: 小世界网络实验

假设 H16-B3: 小世界网络能使 L1 结构反映 L0 的全局特征。

理论依据:
  差异论当前形式是局部交互 + 串行演化 → 产生"死秩序"（拓扑不变量）。
  Watts-Strogatz 小世界网络介于规则环和随机图之间:
  - 强聚类性（规则环特性）
  - 短平均路径（随机图特性）
  这种"小世界"特性可能使信息在全局网络中快速传播,
  同时保留局部聚类结构→最有利于跨层结构反映。

实验设计:
  采用 Watts-Strogatz 模型重连局部交互拓扑:
  1. 从规则环开始 (每个节点连接 k=2 个最近邻: i-1, i+1)
  2. 对每条边, 以概率 p 重连到随机节点
  3. 通过 step_callback 施加基于小世界邻接的耦合

  配置: p = 0.0 (baseline, 规则环), 0.1, 0.3, 0.5, 0.7, 0.9

  测量:
  - L0 密封率
  - L1 密封率
  - Structure Reflection Score (L1 反映 L0 的聚类结构程度)
  - Structure Entropy (L1 结构有序性)

用法:
    python exp_175_phase16_smallworld.py [--p 0.3] [--n_runs 5] [--all_p]
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
# SmallWorldEvolver — Watts-Strogatz 小世界网络
# ═══════════════════════════════════════════════════════════════════

class SmallWorldEvolver(SpatialLongRangeEvolver):
    """小世界网络演化器 — 在标准 SpatialLongRangeEvolver 上以小世界耦合替代纯局部交互。

    机制:
      1. 从规则环构建起始: 每个节点连接 k=2 个最近邻 (i-1, i+1 mod N)
      2. Watts-Strogatz 重连: 对每条边, 以概率 p 将终点重连到随机节点
         (禁止自环和重复边)
      3. 在 step_callback 中施加小世界耦合:
         每条边 (i,j): 若 state[i] != state[j],
         以概率 alpha = coupling_strength 使状态局部/全局同步

    重连概率 p 的影响:
      p=0.0 → 纯规则环 (强聚类, 长路径) — baseline
      p=0.1 → 弱重连 (仍高聚类, 路径已缩短)
      p=0.3 → 中等小世界 (路径显著缩短, 聚类适度保留)
      p=0.5 → 强重连 (接近随机图)
      p=0.7 → 很强重连
      p=0.9 → 接近纯随机图 (低聚类, 短路径)
    """

    def __init__(self,
                 rewiring_p: float = 0.0,
                 k_neighbors: int = 2,
                 coupling_strength: float = 0.3,
                 **kwargs):
        """
        Args:
            rewiring_p: Watts-Strogatz 重连概率 (0.0~1.0)
            k_neighbors: 初始最近邻数 (默认 2: 连接 i-1, i+1)
            coupling_strength: 小世界耦合强度 (0.0~1.0)
            **kwargs: 传递给 SpatialLongRangeEvolver 的参数
        """
        super().__init__(**kwargs)
        self.rewiring_p = rewiring_p
        self.k_neighbors = min(k_neighbors, self.N - 1)
        self.coupling_strength = coupling_strength

        # 小世界邻接表
        self._sw_edges: List[Tuple[int, int]] = []       # 无向边列表
        self._sw_adj: Dict[int, List[int]] = {}          # 邻接表

        if rewiring_p >= 0.0:
            self._build_smallworld()
            print(f"[SmallWorldEvolver] N={self.N}, k={self.k_neighbors}, "
                  f"p={rewiring_p:.2f}, edges={len(self._sw_edges)}, "
                  f"coupling={coupling_strength:.2f}")

    def _build_ring_lattice(self) -> List[Tuple[int, int]]:
        """构建规则环: 每个节点连接 k 个最近邻 (仅 i < j)。"""
        N = self.N
        k = self.k_neighbors
        edges: Set[Tuple[int, int]] = set()

        half_k = k // 2  # 左右各连 half_k 个
        if half_k < 1 and k > 0:
            half_k = 1

        for i in range(N):
            for d in range(1, half_k + 1):
                j = (i + d) % N
                if i < j:
                    edges.add((i, j))
        return sorted(list(edges))

    def _build_smallworld(self):
        """Watts-Strogatz 小世界网络构建。

        算法:
          1. 从规则环开始 (k 个最近邻)
          2. 遍历每条边 (i, j):
             以概率 p 重连 j 到随机节点 k (k != i, 无重复边)
             (保持节点度不变 ≈ k)
        """
        N = self.N
        ring_edges = self._build_ring_lattice()
        edge_set: Set[Tuple[int, int]] = set(ring_edges)

        if self.rewiring_p > 1e-6:
            # 对每条边遍历重连
            new_edge_set = set()
            for (i, j) in ring_edges:
                if torch.rand(1).item() < self.rewiring_p:
                    # 重连 j 端
                    # 从非 i 节点中随机选一个新 j'
                    candidates = [n for n in range(N)
                                  if n != i
                                  and ((i, n) not in edge_set)
                                  and ((n, i) not in edge_set)
                                  and ((i, n) not in new_edge_set)
                                  and ((n, i) not in new_edge_set)]
                    if candidates:
                        new_j = int(candidates[torch.randint(0, len(candidates), (1,)).item()])
                        new_edge = (min(i, new_j), max(i, new_j))
                        new_edge_set.add(new_edge)
                    else:
                        # 无可用候选: 保留原边
                        new_edge_set.add((i, j))
                else:
                    new_edge_set.add((i, j))

            self._sw_edges = sorted(list(new_edge_set))
        else:
            self._sw_edges = ring_edges

        # 构建邻接表
        self._sw_adj = {i: [] for i in range(N)}
        for (i, j) in self._sw_edges:
            self._sw_adj[i].append(j)
            self._sw_adj[j].append(i)

    def _apply_smallworld_coupling(self, state: torch.Tensor):
        """施加小世界耦合。

        对每条小世界边 (i,j):
          若 state[i] != state[j]:
            以概率 alpha 使 state[i] 向 state[j] 同步

        同步方向: 使用局部多数规则 (基于该节点的小世界邻居)
        这模拟了"小世界网络中的信息传播"。
        """
        if len(self._sw_edges) == 0:
            return

        # 抽样处理 (加速)
        N_edges = len(self._sw_edges)
        n_sample = min(N_edges, max(100, int(N_edges * 0.3)))
        if n_sample < N_edges:
            indices = np.random.choice(N_edges, size=n_sample, replace=False)
            sample_edges = [self._sw_edges[idx] for idx in indices]
        else:
            sample_edges = self._sw_edges

        alpha = self.coupling_strength * 0.02  # 温和耦合

        for (i, j) in sample_edges:
            si = state[i].item()
            sj = state[j].item()
            if abs(si - sj) > 0.5:
                if torch.rand(1).item() < alpha:
                    # 方向: 将其同步到邻居多数
                    neighbors_i = self._sw_adj.get(i, [])
                    n_ones_i = sum(1 for nb in neighbors_i if state[nb].item() > 0.5)
                    majority_i = 1.0 if n_ones_i > len(neighbors_i) / 2 else 0.0
                    state[i] = majority_i

    def run(self,
            initial_state=None,
            verbose=True,
            step_callback=None,
            post_seal_callback=None):
        """运行演化，在每次采样时施加小世界耦合。"""
        if self.rewiring_p < 0.0:
            return super().run(
                initial_state=initial_state,
                verbose=verbose,
                step_callback=step_callback,
                post_seal_callback=post_seal_callback,
            )

        orig_cb = step_callback

        def _sw_callback(step, state, snapshot, constraints):
            self._apply_smallworld_coupling(state)
            if orig_cb is not None:
                orig_cb(step, state, snapshot, constraints)

        return super().run(
            initial_state=initial_state,
            verbose=verbose,
            step_callback=_sw_callback,
            post_seal_callback=post_seal_callback,
        )


# ═══════════════════════════════════════════════════════════════════
# 实验配置
# ═══════════════════════════════════════════════════════════════════

# Watts-Strogatz 重连概率梯度
P_CONFIGS = [
    {'p': 0.0, 'coupling': 0.0, 'label': 'p00_baseline'},    # 规则环 (纯局部)
    {'p': 0.1, 'coupling': 0.3, 'label': 'p01_weak'},        # 弱重连
    {'p': 0.3, 'coupling': 0.3, 'label': 'p03_medium'},      # 中等小世界
    {'p': 0.5, 'coupling': 0.5, 'label': 'p05_strong'},      # 强重连
    {'p': 0.7, 'coupling': 0.5, 'label': 'p07_stronger'},    # 很强重连
    {'p': 0.9, 'coupling': 0.5, 'label': 'p09_random'},      # 接近随机图
]

# 默认参数
N = 48                # 网格大小 (3 的倍数)
L0_STEPS = 3000       # L0 演化步数
L1_STEPS = 2000       # L1 演化步数
SAMPLE_INTERVAL = 25  # 采样间隔
N_RUNS = 5            # 每配置运行次数


# ═══════════════════════════════════════════════════════════════════
# 单次实验运行
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ExperimentResult:
    """单次实验运行的结果。"""
    config_label: str = ''
    rewiring_p: float = 0.0
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
      3. 计算各组内 1 的比例的方差 (方差越小 → 反映越强)
      4. reflection_score = 1.0 - normalized_variance
    """
    l0_clusters = l0_result.get('clusters', [])
    if not l0_clusters or len(l0_clusters) < 2:
        return 0.0

    l1_constraints = l1_result.get('l0_constraints', None)
    if l1_constraints is None:
        return 0.0

    hierarchy_map = l1_constraints.hierarchy_map
    l1_final = l1_result.get('final_state', None)
    if l1_final is None:
        return 0.0

    l1_state = l1_final.cpu().numpy() if torch.is_tensor(l1_final) else l1_final
    if len(l1_state) != len(hierarchy_map):
        return 0.0

    n_clusters = len(l0_clusters)
    group_hws = {cid: [] for cid in range(n_clusters)}
    for i, cid in enumerate(hierarchy_map):
        if cid >= 0 and cid < n_clusters:
            group_hws[cid].append(1.0 if l1_state[i] > 0.5 else 0.0)

    group_ratios = []
    for cid, states in group_hws.items():
        if states:
            ratio = sum(states) / len(states)
            group_ratios.append(ratio)

    if len(group_ratios) < 2:
        return 0.0

    variance = float(np.var(group_ratios))
    return max(0.0, 1.0 - variance / 0.25)


def compute_structure_entropy(l0_result: Dict, l1_result: Dict) -> float:
    """计算 L1 结构熵 (衡量 L1 结构随机性)。"""
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

    ratios = np.array(group_ratios)
    ratios = np.clip(ratios, 0.001, 0.999)
    entropy = -np.mean(ratios * np.log(ratios) + (1 - ratios) * np.log(1 - ratios))
    max_entropy = -0.5 * np.log(0.5) - 0.5 * np.log(0.5)
    return float(entropy / max_entropy) if max_entropy > 0 else 1.0


def run_single_trial(rewiring_p: float, coupling_strength: float,
                     trial_idx: int = 0, label: str = '') -> ExperimentResult:
    """运行单次实验 (L0→L1 cross-layer + 小世界网络)。"""
    result = ExperimentResult(config_label=label, rewiring_p=rewiring_p,
                              trial=trial_idx)
    t0 = time.time()

    try:
        # ── Phase 1: L0 演化 (小世界网络) ──
        l0_evolver = SmallWorldEvolver(
            N=N,
            total_steps=L0_STEPS,
            sample_interval=SAMPLE_INTERVAL,
            device='cpu',
            rewiring_p=rewiring_p,
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
            l0_evolver=l0_evolver, l0_result=l0_result,
        )

        # ── Phase 3: L1 演化 ──
        l1_evolver = Layer1Evolver(
            N1=N, total_steps=L1_STEPS, sample_interval=SAMPLE_INTERVAL,
            device='cpu', l0_constraints=l1_constraints, feedback_from_l0=False,
        )
        l1_evolver._install_constraint_callback()
        l1_result = l1_evolver.run()

        result.l1_sealed = l1_result.get('sealed', False)
        result.l1_seal_step = l1_result.get('seal_step', -1)
        l1_hw = l1_result.get('hw_history', [])
        result.l1_hw_history = l1_hw
        if l1_hw:
            result.l1_hw_final = l1_hw[-1]

        # Inject for structure analysis
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
        print(f"    ERROR trial {trial_idx}: {e}")
        traceback.print_exc()

    return result


# ═══════════════════════════════════════════════════════════════════
# 汇总与分析
# ═══════════════════════════════════════════════════════════════════

def run_experiment_for_p(rewiring_p: float, coupling_strength: float,
                         label: str, n_runs: int = N_RUNS) -> List[ExperimentResult]:
    """对给定 p 配置运行多次实验。"""
    print(f"\n{'─' * 60}")
    print(f"Config: {label} (p={rewiring_p:.2f}, coupling={coupling_strength:.2f})")
    print(f"  Running {n_runs} trials...")

    results = []
    for trial in range(n_runs):
        print(f"  Trial {trial + 1}/{n_runs}...", end=' ', flush=True)
        r = run_single_trial(rewiring_p, coupling_strength, trial, label)
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
    print("EXP_175 STATISTICAL SUMMARY — Small-World Network")
    print(f"{'=' * 70}")

    for label, results in all_results.items():
        valid = [r for r in results if not r.error]
        n_valid = len(valid)
        p = results[0].rewiring_p if results else 0.0

        print(f"\n{'─' * 50}")
        print(f"{label} (p={p:.1f}, N={len(results)} trials, {n_valid} valid):")

        if n_valid == 0:
            print("  ⚠ No valid trials")
            continue

        # L0 seal
        l0_sealed = [r for r in valid if r.l0_sealed]
        l0_rate = len(l0_sealed) / n_valid * 100
        print(f"  L0 seal rate: {len(l0_sealed)}/{n_valid} = {l0_rate:.1f}%")

        if l0_sealed:
            steps = [r.l0_seal_step for r in l0_sealed]
            hw = [r.l0_hw_final for r in l0_sealed]
            nc = [r.l0_n_clusters for r in l0_sealed]
            print(f"  L0 seal step: {np.mean(steps):.1f}±{np.std(steps):.1f}")
            print(f"  L0 HW final:  {np.mean(hw):.1f}±{np.std(hw):.1f}")
            print(f"  L0 clusters:  {np.mean(nc):.1f}±{np.std(nc):.1f}")

        # L1 seal
        l1_sealed = [r for r in valid if r.l1_sealed]
        l1_rate = len(l1_sealed) / n_valid * 100
        print(f"  L1 seal rate: {len(l1_sealed)}/{n_valid} = {l1_rate:.1f}%")

        if l1_sealed:
            steps = [r.l1_seal_step for r in l1_sealed]
            hw = [r.l1_hw_final for r in l1_sealed]
            print(f"  L1 seal step: {np.mean(steps):.1f}±{np.std(steps):.1f}")
            print(f"  L1 HW final:  {np.mean(hw):.1f}±{np.std(hw):.1f}")

        # Reflection
        scores = [r.reflection_score for r in l1_sealed]
        if scores:
            print(f"  Reflection:   {np.mean(scores):.3f}±{np.std(scores):.3f}")

        # Entropy
        ents = [r.structure_entropy for r in l1_sealed]
        if ents:
            print(f"  Structure entropy: {np.mean(ents):.3f}±{np.std(ents):.3f}")


def save_results(all_results: Dict[str, List[ExperimentResult]], timestamp: str):
    """保存结果到 JSON。"""
    results_dir = PROJECT_ROOT / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)

    serializable = {}
    for label, results in all_results.items():
        serializable[label] = []
        for r in results:
            serializable[label].append({
                'config_label': r.config_label,
                'rewiring_p': r.rewiring_p,
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
            })

    result_file = results_dir / f'exp_175_results_{timestamp}.json'
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
        description='exp_175: 小世界网络实验 (Phase 16 Path B3)')
    parser.add_argument('--p', type=float, default=None,
                        help='重连概率 (不指定则运行所有配置)')
    parser.add_argument('--n_runs', type=int, default=N_RUNS,
                        help=f'每配置运行次数 (默认 {N_RUNS})')
    parser.add_argument('--all_p', action='store_true',
                        help='运行所有重连概率配置')
    parser.add_argument('--fast', action='store_true',
                        help='快速模式 (n_runs=2, 仅验证)')
    args = parser.parse_args()

    n_runs = 2 if args.fast else args.n_runs

    if args.all_p:
        configs_to_run = P_CONFIGS
    elif args.p is not None:
        matching = [c for c in P_CONFIGS if abs(c['p'] - args.p) < 1e-6]
        if not matching:
            print(f"Unknown p={args.p}. Options: {[c['p'] for c in P_CONFIGS]}")
            return
        configs_to_run = matching
    else:
        configs_to_run = P_CONFIGS

    # ─── Print header ───
    print("=" * 70)
    print("exp_175 — Phase 16 Path B3: 小世界网络实验 (Watts-Strogatz)")
    print("=" * 70)
    print(f"  N={N}, L0_steps={L0_STEPS}, L1_steps={L1_STEPS}")
    print(f"  sample_interval={SAMPLE_INTERVAL}")
    print(f"  n_runs={n_runs}")
    print(f"  Configs: {[c['label'] for c in configs_to_run]}")
    print(f"  p values: {[c['p'] for c in configs_to_run]}")
    print(f"  Total experiments: {len(configs_to_run) * n_runs}")
    print("=" * 70)

    t_start = time.time()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    all_results: Dict[str, List[ExperimentResult]] = {}

    for cfg in configs_to_run:
        results = run_experiment_for_p(
            rewiring_p=cfg['p'],
            coupling_strength=cfg['coupling'],
            label=cfg['label'],
            n_runs=n_runs,
        )
        all_results[cfg['label']] = results

    total_elapsed = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"Total elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print(f"{'=' * 70}")

    analyze_results(all_results)
    save_results(all_results, timestamp)


if __name__ == '__main__':
    main()