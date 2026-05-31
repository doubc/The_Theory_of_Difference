"""experiments/exp_83_narrative_momentum.py

Phase 3 实验十一：叙事动量 — CIVILIZATION 持续激活机制

Purpose:
  exp_82 的关键发现：CIVILIZATION 只在运行早期激活（全部6步在前17%），
  后期完全停止。原因是：系统演化趋于均匀 → 差异信号幅度下降 →
  链长无法达到5 → CIVILIZATION 无法维持。

  本实验引入"叙事动量"机制：
  当 CIVILIZATION 级链形成时，其节点范畴被缓存为"热点"。
  后续步骤中，匹配热点的节点获得连接强度加成，
  使 CIVILIZATION 链更容易被重建和维持。

  理论依据：
  - 差异论 §3.2：差异不是均匀分布的，而是聚集在"热点"上
  - 前主体态的"自催化"特性：一旦形成模式，应倾向于自我维持
  - 类比：相变中的成核效应——晶核形成后，后续原子更容易附着

Design:
  - seed=142（已验证可复现）, N0=72, steps=1600, sample_interval=10
  - 同 exp_82 参数，但使用 NarrativeMomentumConnector（带热点缓存）
  - 对比：exp_82（无动量）vs exp_83（有动量）

Intervention:
  NarrativeMomentumConnector:
  - civ_category_cache: Dict[str, float] — 范畴 → 热度值
  - 当 CIVILIZATION 链检测到时，其节点范畴热度 +1.0
  - 每步热度衰减 0.95（半衰期 ~14 步）
  - 连接强度加成：edge_strength *= (1.0 + 0.3 * cached_heat)
  - 效果：匹配历史 CIVILIZATION 范畴的节点更容易形成长链
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.return_flow_channel import ReturnFlowChannel
from engine.unsealing_mechanism import UnsealingMechanism
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.minimal_self_detector import MinimalSelfDetector
from engine.global_bias_constraint import GlobalBiasConstraint
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from models.narrative_self import (
    NarrativeRecursionOperator, NarrativeLevel, NarrativeConnector,
    NarrativeFilter, NarrativeNamer, NarrativeActionizer, NarrativeVerifier,
    NarrativeNode, CausalChain,
)
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from engine.six_threshold_detector import SixThresholdDetector


class NarrativeMomentumConnector(NarrativeConnector):
    """带叙事动量的连接器 — CIVILIZATION 热点缓存

    在 NarrativeConnector 基础上增加：
    - civ_category_cache: 记录 CIVILIZATION 级链的节点范畴热度
    - 热度随时间衰减，需要持续重建来维持
    - 匹配热点的节点获得连接强度加成
    """

    def __init__(self, strength_threshold: float = 0.3,
                 max_chain_length: int = 10,
                 category_similarity_threshold: float = 0.5,
                 momentum_decay: float = 0.95,
                 momentum_bonus: float = 0.3):
        super().__init__(
            strength_threshold=strength_threshold,
            max_chain_length=max_chain_length,
            category_similarity_threshold=category_similarity_threshold,
        )
        self.momentum_decay = momentum_decay
        self.momentum_bonus = momentum_bonus
        # 范畴热度缓存 {category: heat}
        self.civ_category_cache: Dict[str, float] = {}

    def connect(self, nodes: List[NarrativeNode],
                timestamp: int) -> List[CausalChain]:
        """连接节点，带动量加成"""
        # 每步衰减热度
        for cat in list(self.civ_category_cache.keys()):
            self.civ_category_cache[cat] *= self.momentum_decay
            if self.civ_category_cache[cat] < 0.01:
                del self.civ_category_cache[cat]

        # 调用父类连接
        chains = super().connect(nodes, timestamp)

        # 检测 CIVILIZATION 级链，更新热度缓存
        for chain in chains:
            if len(chain.node_ids) >= 5:
                # 获取链中节点的范畴
                for node_id in chain.node_ids:
                    node = self._node_index.get(node_id)
                    if node:
                        cat = node.category
                        self.civ_category_cache[cat] = (
                            self.civ_category_cache.get(cat, 0.0) + 1.0
                        )

        return chains

    def _compute_edge_strength(self, a: NarrativeNode,
                                b: NarrativeNode) -> float:
        """计算节点间连接强度，带动量加成"""
        base_strength = super()._compute_edge_strength(a, b)

        # 动量加成：如果节点范畴在缓存中
        a_heat = self.civ_category_cache.get(a.category, 0.0)
        b_heat = self.civ_category_cache.get(b.category, 0.0)
        max_heat = max(a_heat, b_heat)

        if max_heat > 0.01:
            # 加成公式：base * (1 + bonus * normalized_heat)
            # heat 范围约 0-5（每次+1，衰减0.95），归一化到 0-1
            normalized_heat = min(max_heat / 5.0, 1.0)
            bonus = 1.0 + self.momentum_bonus * normalized_heat
            base_strength *= bonus

        return base_strength

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        if not self.civ_category_cache:
            return {'n_categories': 0, 'max_heat': 0.0, 'mean_heat': 0.0}
        heats = list(self.civ_category_cache.values())
        return {
            'n_categories': len(heats),
            'max_heat': round(max(heats), 4),
            'mean_heat': round(float(np.mean(heats)), 4),
            'categories': {k: round(v, 3) for k, v in
                          sorted(self.civ_category_cache.items(),
                                 key=lambda x: -x[1])[:5]},
        }


class MomentumNarrativeOperator(NarrativeRecursionOperator):
    """带叙事动量的叙事递归算子"""

    def __init__(self, bias_dimension: int = 128,
                 filter_magnitude_threshold: float = 0.3,
                 connector_strength_threshold: float = 0.3,
                 verifier_consistency_threshold: float = 0.5,
                 narrative_decay_rate: float = 0.9,
                 momentum_decay: float = 0.95,
                 momentum_bonus: float = 0.3):
        # 不调用父类 __init__，手动组装
        self.filter = NarrativeFilter(
            magnitude_threshold=filter_magnitude_threshold)
        self.namer = NarrativeNamer()
        # 使用动量连接器替代普通连接器
        self.connector = NarrativeMomentumConnector(
            strength_threshold=connector_strength_threshold,
            momentum_decay=momentum_decay,
            momentum_bonus=momentum_bonus,
        )
        self.actionizer = NarrativeActionizer(bias_dimension=bias_dimension)
        self.verifier = NarrativeVerifier(
            consistency_threshold=verifier_consistency_threshold)
        self.narrative_decay_rate = narrative_decay_rate
        self._records = []
        self._active_narratives = {}
        self._record_count = 0
        self._total_actions = 0
        self._validated_actions = 0

    def get_momentum_stats(self) -> Dict:
        """获取动量统计"""
        return self.connector.get_cache_stats()


def extract_narrative_level_counts(narrative_summary: Dict) -> Dict:
    level_dist = narrative_summary.get('narrative_level_distribution', {})
    return {
        'MINI': level_dist.get('MINI_NARRATIVE', 0) or level_dist.get('MINI', 0),
        'INSTITUTIONAL': level_dist.get('INSTITUTIONAL', 0),
        'CIVILIZATION': level_dist.get('CIVILIZATION', 0),
    }


def analyze_narrative_activation(step_results: List[Dict]) -> Dict:
    active_count = 0
    correction_count = 0
    msi_at_active = []
    odi_at_active = []
    norms_at_active = []
    civ_activated = False
    civ_steps = []
    civ_msi = []
    civ_odi = []

    prev_civ_count = 0
    for entry in step_results:
        narrative_data = entry.get('narrative_recursion', {})
        msi_data = entry.get('minimal_self', {})
        msi_val = msi_data.get('msi', 0.0) if isinstance(msi_data, dict) else 0.0
        odi_data = entry.get('odi', {})
        odi_val = odi_data.get('value', 0.0) if isinstance(odi_data, dict) else 0.0

        if narrative_data.get('bias_correction_applied', False):
            active_count += 1
            msi_at_active.append(msi_val)
            odi_at_active.append(odi_val)
            norms_at_active.append(float(narrative_data.get('correction_norm', 0.0)))

            level = narrative_data.get('narrative_level', '')
            is_civ_step = (level == 'CIVILIZATION' or narrative_data.get('is_civilization', False))
            level_snap = narrative_data.get('level_distribution_snapshot', {})
            curr_civ_count = level_snap.get('CIVILIZATION', 0)
            if curr_civ_count > prev_civ_count:
                is_civ_step = True
                prev_civ_count = curr_civ_count

            if is_civ_step:
                civ_activated = True
                civ_steps.append(entry.get('step', 0))
                civ_msi.append(msi_val)
                civ_odi.append(odi_val)

        correction = narrative_data.get('correction_norm', 0.0)
        if isinstance(correction, (int, float)) and correction > 0:
            correction_count += 1

    total = max(1, len(step_results))
    return {
        'narrative_active_steps': active_count,
        'narrative_active_ratio': round(active_count / total, 4),
        'narrative_correction_steps': correction_count,
        'msi_at_active_mean': round(float(np.mean(msi_at_active)), 4) if msi_at_active else 0.0,
        'msi_at_active_max': round(float(np.max(msi_at_active)), 4) if msi_at_active else 0.0,
        'odi_at_active_mean': round(float(np.mean(odi_at_active)), 4) if odi_at_active else 0.0,
        'odi_at_active_max': round(float(np.max(odi_at_active)), 4) if odi_at_active else 0.0,
        'mean_correction_norm': round(float(np.mean(norms_at_active)), 6) if norms_at_active else 0.0,
        'max_correction_norm': round(float(np.max(norms_at_active)), 6) if norms_at_active else 0.0,
        'civilization_activated': civ_activated,
        'civilization_steps': civ_steps,
        'civilization_n_steps': len(civ_steps),
        'civilization_msi_mean': round(float(np.mean(civ_msi)), 4) if civ_msi else 0.0,
        'civilization_odi_mean': round(float(np.mean(civ_odi)), 4) if civ_odi else 0.0,
    }


def analyze_growth(values: List[float], label: str) -> Dict:
    arr = np.array(values)
    n = len(arr)
    result = {
        f'{label}_min': round(float(np.min(arr)), 6),
        f'{label}_max': round(float(np.max(arr)), 6),
        f'{label}_final': round(float(arr[-1]), 6),
        f'{label}_mean': round(float(np.mean(arr)), 6),
    }
    if n >= 4:
        q1 = n // 4
        q2 = n // 2
        q3 = 3 * n // 4
        result[f'{label}_q1_mean'] = round(float(np.mean(arr[:q1])), 6)
        result[f'{label}_q2_mean'] = round(float(np.mean(arr[q1:q2])), 6)
        result[f'{label}_q3_mean'] = round(float(np.mean(arr[q2:q3])), 6)
        result[f'{label}_q4_mean'] = round(float(np.mean(arr[q3:])), 6)
    return result


def analyze_civilization_accumulation(step_results: List[Dict]) -> Dict:
    cumulative_civ = []
    civ_count = 0

    for entry in step_results:
        narrative_data = entry.get('narrative_recursion', {})
        level = narrative_data.get('narrative_level', '')
        is_civ = (level == 'CIVILIZATION' or narrative_data.get('is_civilization', False))
        level_snap = narrative_data.get('level_distribution_snapshot', {})
        curr_civ = level_snap.get('CIVILIZATION', 0)

        if is_civ or curr_civ > civ_count:
            civ_count = curr_civ
        cumulative_civ.append(civ_count)

    civ_rate_by_quarter = []
    n = len(cumulative_civ)
    if n >= 4:
        q_size = n // 4
        for i in range(4):
            start = i * q_size
            end = (i + 1) * q_size if i < 3 else n
            civ_start = cumulative_civ[start] if start < n else 0
            civ_end = cumulative_civ[end - 1] if end <= n else cumulative_civ[-1]
            civ_rate_by_quarter.append(civ_end - civ_start)

    return {
        'cumulative_civ_final': cumulative_civ[-1] if cumulative_civ else 0,
        'civ_rate_by_quarter': civ_rate_by_quarter,
        'civ_acceleration': (
            'increasing' if len(civ_rate_by_quarter) == 4
            and civ_rate_by_quarter[3] > civ_rate_by_quarter[0]
            else 'stable_or_decreasing'
        ),
    }


def run_experiment(N0=72, steps=1600, seed=142, sample_interval=10):
    torch.manual_seed(seed)
    np.random.seed(seed)

    return_flow_channel = ReturnFlowChannel(
        anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10,
    )
    unsealing_mechanism = UnsealingMechanism(
        l1_coupling_threshold=0.20, l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40, l2_stability_threshold=0.55,
    )
    pre_subjectivity = PreSubjectivityConvergence(
        coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True,
    )
    odi = OrganizationalDensityIndex(
        temporal_window=10, densification_threshold=0.005, use_refined_zones=True,
    )
    msi_detector = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35, 'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10, 'asymmetry_threshold': 0.15,
        'min_parts': 3, 'history_window': 8, 'history_dependency_threshold': 0.15,
        'min_history_depth': 5, 'self_reference_window': 8,
        'self_reference_threshold': 0.05, 'baseline_correlation_threshold': 0.2,
        'msi_activation_threshold': 0.20, 'msi_emergence_threshold': 0.35,
        'min_active_conditions': 1,
    })
    gbc = GlobalBiasConstraint(
        coherence_threshold=0.5, balance_threshold=0.3,
        min_mechanisms_required=4, geometric_weighting=True,
    )
    # 使用带动量的叙事算子
    narrative = MomentumNarrativeOperator(
        bias_dimension=128, filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1, verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.3,
    )
    anticipatory = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01},
    )
    counterfactual = CounterfactualEngine(config={
        'divergence_threshold': 0.1, 'max_branches': 4,
    })
    six_threshold = SixThresholdDetector()

    evolver = HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        max_layers=1, p1_eval_interval=sample_interval,
        phase2_verbose=False, phase3_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi, six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing_mechanism, return_flow_channel=return_flow_channel,
        pre_subjectivity_convergence=pre_subjectivity, minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory, counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative, global_bias_constraint=gbc,
    )

    print(f"[exp_83] N0={N0}, steps={steps}, seed={seed}, sample_interval={sample_interval}")
    print(f"[exp_83] Purpose: Narrative momentum — CIVILIZATION sustained activation")
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"[exp_83] Completed in {elapsed:.1f}s")

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    odi_values = []
    msi_values = []
    for entry in step_results:
        odi_data = entry.get('odi', {})
        odi_val = odi_data.get('value', 0.0) if isinstance(odi_data, dict) else 0.0
        msi_val = entry.get('minimal_self', {}).get('msi', 0.0) if isinstance(entry.get('minimal_self'), dict) else 0.0
        odi_values.append(float(odi_val))
        msi_values.append(float(msi_val))

    narrative_analysis = analyze_narrative_activation(step_results)
    civ_accumulation = analyze_civilization_accumulation(step_results)

    gbc_coherences = []
    for entry in step_results:
        gbc_data = entry.get('global_bias_constraint', {})
        if isinstance(gbc_data, dict) and gbc_data.get('coherence', 0) > 0:
            gbc_coherences.append(gbc_data['coherence'])

    narrative_summary = narrative.get_summary() if narrative else {}
    momentum_stats = narrative.get_momentum_stats() if hasattr(narrative, 'get_momentum_stats') else {}

    diagnostic = {
        'seed': seed, 'N0': N0, 'steps': steps, 'sample_interval': sample_interval,
        'elapsed_seconds': round(elapsed, 1),
        'n_steps_recorded': len(step_results),
        'odi': analyze_growth(odi_values, 'odi'),
        'msi': analyze_growth(msi_values, 'msi'),
        'narrative': narrative_analysis,
        'civilization_accumulation': civ_accumulation,
        'narrative_operator_summary': narrative_summary,
        'narrative_level_distribution': extract_narrative_level_counts(narrative_summary),
        'momentum_cache_stats': momentum_stats,
        'gbc_coherence_mean': round(float(np.mean(gbc_coherences)), 4) if gbc_coherences else 0.0,
        'gbc_coherence_max': round(float(np.max(gbc_coherences)), 4) if gbc_coherences else 0.0,
    }

    return {'result': result, 'diagnostic': diagnostic}


def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(
        os.path.dirname(__file__),
        f'exp_83_results_{timestamp}.json'
    )

    print(f"{'='*60}")
    print(f"exp_83: Narrative Momentum — CIVILIZATION Sustained Activation")
    print(f"Testing: Does momentum cache help CIVILIZATION persist beyond early phase?")
    print(f"Output: {output_file}")
    print(f"{'='*60}")

    run_data = run_experiment(N0=72, steps=1600, seed=142, sample_interval=10)
    diag = run_data['diagnostic']

    print(f"\n{'='*60}")
    print(f"exp_83 Results (seed={diag['seed']}):")
    print(f"  Steps recorded: {diag['n_steps_recorded']}")
    print(f"  Elapsed: {diag['elapsed_seconds']}s")
    print(f"\n  ODI: min={diag['odi']['odi_min']:.4f} max={diag['odi']['odi_max']:.4f} "
          f"final={diag['odi']['odi_final']:.4f} mean={diag['odi']['odi_mean']:.4f}")
    print(f"\n  MSI: min={diag['msi']['msi_min']:.4f} max={diag['msi']['msi_max']:.4f} "
          f"final={diag['msi']['msi_final']:.4f} mean={diag['msi']['msi_mean']:.4f}")
    print(f"\n  Narrative:")
    print(f"    Active steps: {diag['narrative']['narrative_active_steps']}/{diag['n_steps_recorded']} "
          f"({diag['narrative']['narrative_active_ratio']*100:.1f}%)")
    print(f"    Correction steps: {diag['narrative']['narrative_correction_steps']}")
    print(f"\n  *** CIVILIZATION ***")
    print(f"    Activated: {diag['narrative']['civilization_activated']}")
    print(f"    N steps: {diag['narrative']['civilization_n_steps']}")
    if diag['narrative']['civilization_activated']:
        print(f"    Steps: {diag['narrative']['civilization_steps']}")
    if diag.get('narrative_level_distribution'):
        print(f"    Level dist: {diag['narrative_level_distribution']}")
    if diag.get('civilization_accumulation'):
        ca = diag['civilization_accumulation']
        print(f"    Cumulative CIV final: {ca['cumulative_civ_final']}")
        print(f"    CIV rate by quarter: {ca['civ_rate_by_quarter']}")
        print(f"    CIV acceleration: {ca['civ_acceleration']}")
    if diag.get('momentum_cache_stats'):
        ms = diag['momentum_cache_stats']
        print(f"  Momentum cache: {ms}")
    print(f"\n  GBC: coherence_mean={diag['gbc_coherence_mean']:.4f} "
          f"max={diag['gbc_coherence_max']:.4f}")
    print(f"{'='*60}")

    # Comparison with exp_82
    print(f"\n  Comparison with exp_82 (same seed=142, N0=72, 1600 steps, no momentum):")
    print(f"    exp_82: CIVILIZATION=6, all in early phase (steps 10-170)")
    print(f"    exp_83: CIVILIZATION={diag['narrative']['civilization_n_steps']}, "
          f"ODI max={diag['odi']['odi_max']:.4f}, MSI max={diag['msi']['msi_max']:.4f}")
    if diag['narrative']['civilization_activated']:
        civ = diag['narrative']['civilization_n_steps']
        if civ > 6:
            print(f"    >>> MOMENTUM HELPS: CIVILIZATION increased ({civ} > 6) <<<")
        elif civ == 6:
            print(f"    >>> MOMENTUM NEUTRAL: CIVILIZATION same (6 = 6) <<<")
        else:
            print(f"    >>> MOMENTUM HURTS: CIVILIZATION decreased ({civ} < 6) <<<")
        # Check distribution across quarters
        ca = diag.get('civilization_accumulation', {})
        quarters = ca.get('civ_rate_by_quarter', [])
        if quarters and sum(quarters[2:]) > 0:
            print(f"    >>> LATE-PHASE CIV DETECTED in Q3/Q4: {quarters[2:]} <<<")
        else:
            print(f"    >>> Still no late-phase CIV: Q3+Q4 = 0 <<<")
    else:
        print(f"    >>> CIVILIZATION not activated — momentum insufficient <<<")
    print(f"{'='*60}")

    summary = {
        'experiment': 'exp_83_narrative_momentum',
        'timestamp': timestamp,
        'description': 'Narrative momentum — CIVILIZATION sustained activation via category cache',
        'intervention': {
            'name': 'NarrativeMomentumConnector',
            'mechanism': 'CIVILIZATION chain categories cached as hotspots; matching nodes get connection bonus',
            'parameters': {'momentum_decay': 0.95, 'momentum_bonus': 0.3},
        },
        'hypothesis': 'Momentum cache helps CIVILIZATION persist beyond early phase (Q3/Q4 activation)',
        'comparison_target': 'exp_82 (1600 steps, no momentum, CIVILIZATION=6 all in Q1)',
        'diagnostic': diag,
    }
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults saved to: {output_file}")

    return summary


if __name__ == '__main__':
    main()
