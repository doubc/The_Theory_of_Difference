"""
experiments/exp_phase2_e2e.py — Phase 2 端到端集成实验

验证从底象检测到前主体态收束、解封、回流锚定的完整生成链：
  底象 → 界面调节 → 自维持 → 记忆(保持) → 复制 → 筛选 → 功能分化
  → 六阈值同步 → 前主体态收束 → 分级解封 → 高语义回流锚定

这是 Phase 2 的综合验证实验，在 HierarchicalEvolver 的完整演化过程中
实时追踪所有 Phase 2 组件的状态变化，并生成端到端分析报告。

实验配置：
  Config A: N=48, steps=2000, max_layers=2, functional coupling (主实验)
  Config B: N=32, steps=3000, max_layers=3, functional coupling (深层级)
  Config C: N=48, steps=2000, max_layers=2, weighted coupling (对照)

输出：
  - JSON 结果文件 (experiments/exp_phase2_e2e_results_<timestamp>.json)
  - Markdown 分析报告 (experiments/exp_phase2_e2e_report_<timestamp>.md)
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.xiang_detector import XiàngDetector
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.unsealing_mechanism import UnsealingMechanism
from engine.return_flow_channel import ReturnFlowChannel, HighSemanticPayload
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.seventh_threshold_detector import SeventhThresholdDetector
from engine.cooperative_emergence_detector import CooperativeEmergenceDetector
from engine.functional_signal_coupling import FunctionalSignalSet


# ─── 实验配置 ───

CONFIGS = {
    "A_N48_L2_func": {
        "N0": 48,
        "steps_per_layer": 2000,
        "max_layers": 2,
        "sample_interval": 100,
        "p1_eval_interval": 5,
        "coupling_mode": "functional",
        "coupling_threshold": 0.30,
        "auto_encapsulate": True,
        "phase2_verbose": True,
        "description": "N=48, 2 layers, functional coupling (primary)",
    },

    "C_N48_L2_weighted": {
        "N0": 48,
        "steps_per_layer": 2000,
        "max_layers": 2,
        "sample_interval": 100,
        "p1_eval_interval": 5,
        "coupling_mode": "weighted",
        "coupling_threshold": 0.30,
        "auto_encapsulate": True,
        "phase2_verbose": True,
        "description": "N=48, 2 layers, weighted coupling (control)",
    },
}


# ─── 辅助函数 ───

def build_phase2_components(cfg: Dict, coupling_threshold_override: float = None):
    """构建所有 Phase 2 组件"""
    ct = coupling_threshold_override if coupling_threshold_override is not None else cfg["coupling_threshold"]

    xiang = XiàngDetector(rho_threshold=0.25, tau_threshold=0.4)
    bias_mem = PersistentBiasMemory(max_history_depth=100, decay_rate=0.97)
    selector = CumulativeSelector(window_size=10, trend_threshold=0.55)
    six_det = SixThresholdDetector()
    conv = PreSubjectivityConvergence(
        coupling_threshold=ct,
        stability_threshold=0.35,
        n_perturbation_tests=5,
        perturbation_scale=0.03,
        coupling_mode=cfg["coupling_mode"],
    )
    unsealing = UnsealingMechanism(
        l1_coupling_threshold=0.25,
        l1_stability_threshold=0.40,
        l2_coupling_threshold=0.45,
        l2_stability_threshold=0.60,
        l3_coupling_threshold=0.65,
        l3_stability_threshold=0.80,
    )
    return_flow = ReturnFlowChannel(
        anchor_threshold=0.20,
        decay_rate=0.03,
        min_retention_steps=5,
    )
    odi = OrganizationalDensityIndex()
    seventh = SeventhThresholdDetector()
    coop = CooperativeEmergenceDetector()

    return {
        "xiang_detector": xiang,
        "persistent_bias_memory": bias_mem,
        "cumulative_selector": selector,
        "six_threshold_detector": six_det,
        "pre_subjectivity_convergence": conv,
        "unsealing_mechanism": unsealing,
        "return_flow_channel": return_flow,
        "organizational_density_index": odi,
        "seventh_threshold_detector": seventh,
        "cooperative_emergence_detector": coop,
    }


def inject_return_flow_at_convergence(
    evolver: HierarchicalEvolver,
    convergence_step: int,
    layer_id: int,
) -> Optional[Dict]:
    """在前主体态收束后注入高语义回流载荷"""
    if evolver.return_flow_channel is None:
        return None

    payloads = [
        HighSemanticPayload(
            payload_id=f"meaning_L{layer_id}_s{convergence_step}",
            content_type="meaning",
            content_vector=torch.randn(6),
            created_at=convergence_step,
        ),
        HighSemanticPayload(
            payload_id=f"institution_L{layer_id}_s{convergence_step}",
            content_type="institution",
            content_vector=torch.randn(6),
            created_at=convergence_step,
        ),
        HighSemanticPayload(
            payload_id=f"narrative_L{layer_id}_s{convergence_step}",
            content_type="narrative",
            content_vector=torch.randn(6),
            created_at=convergence_step,
        ),
    ]

    results = []
    for payload in payloads:
        # 构造低语义结构代理（从演化器当前状态提取）
        layer = evolver.hierarchy.get_layer(layer_id)
        state = layer.state
        if state is None:
            continue

        n = len(state)
        structures = [
            {
                "structure_id": layer_id,
                "mechanisms": {
                    "boundary": float(state.float().mean().item()),
                    "self_sustaining": float(state.float().mean().item() * 0.8),
                    "retention": min(1.0, evolver.persistent_bias_memory.n_entries / 20.0)
                        if evolver.persistent_bias_memory else 0.0,
                    "replication": float(1.0 - state.float().std().item()),
                    "selection": float(state.float().mean().item() * 0.6),
                    "function": float(state.float().mean().item() * 0.7),
                },
            },
            {
                "structure_id": layer_id + 100,
                "mechanisms": {
                    "boundary": float(state.float().mean().item() * 0.5),
                    "self_sustaining": float(state.float().mean().item() * 0.4),
                    "retention": min(1.0, evolver.persistent_bias_memory.n_entries / 30.0)
                        if evolver.persistent_bias_memory else 0.0,
                    "replication": float(1.0 - state.float().std().item() * 0.5),
                    "selection": float(state.float().mean().item() * 0.3),
                    "function": float(state.float().mean().item() * 0.9),
                },
            },
        ]

        event = evolver.return_flow_channel.attempt_anchor(
            payload, structures, timestamp=convergence_step
        )
        evolver._return_flow_events.append(event)
        results.append({
            "payload_id": payload.payload_id,
            "content_type": payload.content_type,
            "success": event.success,
            "reason": event.reason,
            "anchor_structure": event.anchor.structure_id if event.anchor else None,
            "anchor_mechanism": event.anchor.mechanism if event.anchor else None,
            "residual_strength": event.residual_strength,
        })

    return results


def analyze_xiang_formation(step_results: List[Dict]) -> Dict:
    """分析底象形成动态"""
    xiang_data = [r for r in step_results if "xiang" in r]
    if not xiang_data:
        return {"n_checks": 0}

    densities = [r["xiang"]["density"] for r in xiang_data]
    traces = [r["xiang"]["trace"] for r in xiang_data]
    continuities = [r["xiang"]["continuity"] for r in xiang_data]
    formed = [r for r in xiang_data if r["xiang"]["formed"]]

    return {
        "n_checks": len(xiang_data),
        "n_formed": len(formed),
        "formation_rate": len(formed) / len(xiang_data),
        "first_formed_step": formed[0]["step"] if formed else None,
        "max_density": max(densities),
        "mean_density": float(np.mean(densities)),
        "max_trace": max(traces),
        "max_continuity": max(continuities),
        "density_trend": densities,
        "trace_trend": traces,
    }


def analyze_convergence_dynamics(step_results: List[Dict]) -> Dict:
    """分析收束动态"""
    conv_data = [r for r in step_results if "convergence" in r]
    if not conv_data:
        return {"n_evals": 0}

    converged = [r for r in conv_data if r["convergence"]["converged"]]
    thresholds_met = [r for r in conv_data if r["convergence"]["thresholds_met"]]
    coupling_met = [r for r in conv_data if r["convergence"]["coupling_met"]]
    stability_met = [r for r in conv_data if r["convergence"]["stability_met"]]
    firewall_passed = [r for r in conv_data if r["convergence"]["firewall_passed"]]

    stability_scores = [r["convergence"]["stability_score"] for r in conv_data]
    n_coupled_pairs = [r["convergence"]["n_coupled_pairs"] for r in conv_data]

    return {
        "n_evals": len(conv_data),
        "n_converged": len(converged),
        "first_converged_step": converged[0]["step"] if converged else None,
        "convergence_rate": len(converged) / len(conv_data),
        "thresholds_met_rate": len(thresholds_met) / len(conv_data),
        "coupling_met_rate": len(coupling_met) / len(conv_data),
        "stability_met_rate": len(stability_met) / len(conv_data),
        "firewall_pass_rate": len(firewall_passed) / len(conv_data),
        "max_stability_score": max(stability_scores) if stability_scores else 0.0,
        "mean_stability_score": float(np.mean(stability_scores)) if stability_scores else 0.0,
        "max_n_coupled_pairs": max(n_coupled_pairs) if n_coupled_pairs else 0,
    }


def analyze_unsealing_dynamics(step_results: List[Dict]) -> Dict:
    """分析解封动态"""
    unseal_data = [r for r in step_results if "unsealing" in r]
    if not unseal_data:
        return {"n_records": 0, "n_events": 0, "max_level": 0, "final_level": 0, "level_progression": [], "events": []}

    events = [r for r in unseal_data if r["unsealing"].get("changed", True)]
    levels = [r["unsealing"]["level"] for r in unseal_data]

    return {
        "n_records": len(unseal_data),
        "n_events": len(events),
        "max_level": max(levels) if levels else 0,
        "final_level": levels[-1] if levels else 0,
        "level_progression": levels,
        "events": [
            {
                "step": r["step"],
                "level": r["unsealing"]["level"],
                "reason": r["unsealing"].get("reason", ""),
                "capacity": r["unsealing"].get("capacity", 0.0),
            }
            for r in events
        ],
    }


def analyze_return_flow(step_results: List[Dict]) -> Dict:
    """分析回流动态"""
    rf_data = [r for r in step_results if "return_flow" in r]
    if not rf_data:
        return {"n_records": 0, "max_anchored": 0, "total_detach_events": 0, "final_anchored": 0}

    anchored_counts = [r["return_flow"]["anchored_count"] for r in rf_data]
    detach_counts = [r["return_flow"].get("detach_events_this_step", 0) for r in rf_data]

    return {
        "n_records": len(rf_data),
        "max_anchored": max(anchored_counts),
        "total_detach_events": sum(detach_counts),
        "final_anchored": anchored_counts[-1] if anchored_counts else 0,
    }


def analyze_six_threshold(step_results: List[Dict]) -> Dict:
    """分析六阈值达标动态"""
    st_data = [r for r in step_results if "six_threshold" in r]
    if not st_data:
        return {"n_evals": 0}

    all_met = [r for r in st_data if r["six_threshold"]["all_met"]]
    n_met_vals = [r["six_threshold"]["n_met"] for r in st_data]
    bottlenecks = [r["six_threshold"]["bottleneck"] for r in st_data if r["six_threshold"]["bottleneck"]]

    return {
        "n_evals": len(st_data),
        "n_all_met": len(all_met),
        "first_all_met_step": all_met[0]["step"] if all_met else None,
        "max_n_met": max(n_met_vals),
        "mean_n_met": float(np.mean(n_met_vals)),
        "bottleneck_frequency": {
            b: bottlenecks.count(b) for b in set(bottlenecks)
        } if bottlenecks else {},
    }


def analyze_odi(step_results: List[Dict]) -> Dict:
    """分析组织密度指数动态"""
    odi_data = [r for r in step_results if "odi" in r]
    if not odi_data:
        return {"n_evals": 0}

    values = [r["odi"]["value"] for r in odi_data]
    zones = [r["odi"]["zone"] for r in odi_data]
    zone_counts = {z: zones.count(z) for z in set(zones)}

    return {
        "n_evals": len(odi_data),
        "max_odi": max(values),
        "mean_odi": float(np.mean(values)),
        "final_odi": values[-1] if values else 0.0,
        "zone_distribution": zone_counts,
        "value_trend": values,
    }


def analyze_bias_memory(step_results: List[Dict]) -> Dict:
    """分析偏置记忆动态"""
    bm_data = [r for r in step_results if "bias_memory" in r]
    if not bm_data:
        return {"n_records": 0}

    entries = [r["bias_memory"]["entries"] for r in bm_data]
    strengths = [r["bias_memory"]["strength"] for r in bm_data]

    return {
        "n_records": len(bm_data),
        "max_entries": max(entries),
        "mean_strength": float(np.mean(strengths)),
        "final_entries": entries[-1] if entries else 0,
    }


def analyze_functional_signals(step_results: List[Dict]) -> Dict:
    """分析功能信号动态"""
    fs_data = [r for r in step_results if "functional_signals" in r]
    if not fs_data:
        return {"n_records": 0}

    result = {"n_records": len(fs_data)}
    for mechanism in FunctionalSignalSet.mechanism_names():
        vals = [r["functional_signals"].get(mechanism, 0.0) for r in fs_data]
        result[mechanism] = {
            "final": vals[-1] if vals else 0.0,
            "mean": float(np.mean(vals)) if vals else 0.0,
            "max": max(vals) if vals else 0.0,
        }
    return result


def compute_generation_chain_score(analysis: Dict) -> Dict:
    """计算完整生成链的达标分数"""
    scores = {}

    # 1. 底象形成 (0-1)
    xiang = analysis.get("xiang", {})
    scores["xiang_formation"] = xiang.get("formation_rate", 0.0)

    # 2. 六阈值达标 (0-1)
    six = analysis.get("six_threshold", {})
    scores["six_threshold"] = six.get("n_all_met", 0) / max(six.get("n_evals", 1), 1)

    # 3. 前主体态收束 (0-1)
    conv = analysis.get("convergence", {})
    scores["convergence"] = conv.get("convergence_rate", 0.0)

    # 4. 解封等级 (0-1, normalized from 0-3)
    unseal = analysis.get("unsealing", {})
    scores["unsealing"] = (unseal.get("max_level", 0) / 3.0) if unseal.get("n_records", 0) > 0 else 0.0

    # 5. 回流锚定 (0-1)
    rf = analysis.get("return_flow", {})
    scores["return_flow"] = min(1.0, rf.get("max_anchored", 0) / 3.0)

    # 6. 语义防火墙 (0-1)
    scores["firewall"] = conv.get("firewall_pass_rate", 1.0)

    # 综合分数 (加权平均)
    weights = {
        "xiang_formation": 0.15,
        "six_threshold": 0.20,
        "convergence": 0.20,
        "unsealing": 0.15,
        "return_flow": 0.15,
        "firewall": 0.15,
    }
    scores["overall"] = sum(scores[k] * w for k, w in weights.items())

    return scores


# ─── 主实验函数 ───

def run_config(name: str, cfg: Dict, seed: int = 42) -> Dict:
    """运行单个配置"""
    print(f"\n{'=' * 70}")
    print(f"[{name}] {cfg['description']}")
    print(f"{'=' * 70}")

    torch.manual_seed(seed)
    np.random.seed(seed)

    components = build_phase2_components(cfg)

    evolver = HierarchicalEvolver(
        N0=cfg["N0"],
        steps_per_layer=cfg["steps_per_layer"],
        sample_interval=cfg["sample_interval"],
        max_layers=cfg["max_layers"],
        auto_encapsulate=cfg["auto_encapsulate"],
        p1_eval_interval=cfg["p1_eval_interval"],
        phase2_verbose=cfg["phase2_verbose"],
        **components,
    )

    t0 = time.time()
    results = evolver.run(verbose=True)
    elapsed = time.time() - t0

    print(f"\n  Evolution completed in {elapsed:.1f}s")

    # ── 在收束成功后注入回流载荷 ──
    return_flow_injections = []
    for lr in results["layer_results"]:
        layer_id = lr["layer"]
        step_results = lr.get("phase2_step_results", [])
        conv_data = [r for r in step_results if r.get("convergence", {}).get("converged")]
        if conv_data:
            conv_step = conv_data[0]["step"]
            injection_result = inject_return_flow_at_convergence(
                evolver, conv_step + 10, layer_id
            )
            if injection_result:
                return_flow_injections.extend(injection_result)

    # ── 分析每层结果 ──
    layer_analyses = {}
    for lr in results["layer_results"]:
        layer_id = lr["layer"]
        step_results = lr.get("phase2_step_results", [])

        analysis = {
            "layer": layer_id,
            "N": lr["N"],
            "sealed": lr["sealed"],
            "steps": lr["steps"],
            "cycles": lr["cycles"],
            "n_clusters": len(lr["clusters"]),
            "xiang": analyze_xiang_formation(step_results),
            "bias_memory": analyze_bias_memory(step_results),
            "six_threshold": analyze_six_threshold(step_results),
            "convergence": analyze_convergence_dynamics(step_results),
            "unsealing": analyze_unsealing_dynamics(step_results),
            "return_flow": analyze_return_flow(step_results),
            "odi": analyze_odi(step_results),
            "functional_signals": analyze_functional_signals(step_results),
        }
        analysis["chain_score"] = compute_generation_chain_score(analysis)
        layer_analyses[f"L{layer_id}"] = analysis

    # ── 汇总 ──
    p2_summary = results.get("phase2_summary", {})

    summary = {
        "config": name,
        "config_details": cfg,
        "elapsed_seconds": round(elapsed, 1),
        "n_layers": results["n_layers"],
        "n_encapsulation_events": len(results["encapsulation_events"]),
        "layer_analyses": layer_analyses,
        "return_flow_injections": return_flow_injections,
        "final_unsealing_status": evolver.get_unsealing_status(),
        "final_return_flow_status": evolver.get_return_flow_status(),
        "phase2_summary": {
            k: v for k, v in p2_summary.items()
            if not isinstance(v, (list, dict)) or k in [
                "unsealing_summary",
            ]
        },
    }

    # ── 打印摘要 ──
    print(f"\n{'─' * 60}")
    print(f"[{name}] 实验摘要")
    print(f"{'─' * 60}")
    print(f"  运行时间: {elapsed:.1f}s")
    print(f"  层数: {results['n_layers']}")
    print(f"  封装事件: {len(results['encapsulation_events'])}")

    for layer_key, la in layer_analyses.items():
        score = la["chain_score"]
        print(f"\n  {layer_key}: N={la['N']}, sealed={la['sealed']}")
        print(f"    底象形成率: {score['xiang_formation']:.2f}")
        print(f"    六阈值达标率: {score['six_threshold']:.2f}")
        print(f"    收束率: {score['convergence']:.2f}")
        print(f"    解封等级: {score['unsealing']:.2f} ({la['unsealing'].get('max_level', 0)}/3)")
        print(f"    回流锚定: {score['return_flow']:.2f}")
        print(f"    语义防火墙: {score['firewall']:.2f}")
        print(f"    → 综合分数: {score['overall']:.3f}")

    return summary


def generate_report(all_results: Dict, timestamp: str) -> str:
    """生成 Markdown 分析报告"""
    lines = []
    lines.append(f"# Phase 2 端到端集成实验报告")
    lines.append(f"")
    lines.append(f"**时间**: {datetime.now().isoformat()}")
    lines.append(f"**实验数**: {len(all_results)}")
    lines.append(f"")

    # ── 总览表 ──
    lines.append(f"## 总览")
    lines.append(f"")
    lines.append(f"| 配置 | 层数 | 运行时间 | 封装事件 | 平均综合分数 |")
    lines.append(f"|------|------|---------|---------|------------|")
    for name, result in all_results.items():
        if "error" in result:
            lines.append(f"| {name} | ERROR | - | - | - |")
            continue
        avg_score = np.mean([
            la["chain_score"]["overall"]
            for la in result["layer_analyses"].values()
        ]) if result.get("layer_analyses") else 0.0
        n_layers = result.get('n_layers', '-')
        elapsed = result.get('elapsed_seconds', '-')
        n_encap = result.get('n_encapsulation_events', '-')
        lines.append(
            f"| {name} | {n_layers} | {elapsed}s | "
            f"{n_encap} | {avg_score:.3f} |"
        )
    lines.append(f"")

    # ── 每层详细分析 ──
    for name, result in all_results.items():
        if "error" in result:
            lines.append(f"## {name}: [ERROR] {result['error']}")
            lines.append(f"")
            continue
        lines.append(f"## {name}: {result['config_details']['description']}")
        lines.append(f"")

        for layer_key, la in result["layer_analyses"].items():
            lines.append(f"### {layer_key} (N={la['N']}, sealed={la['sealed']})")
            lines.append(f"")

            # 生成链分数
            score = la["chain_score"]
            lines.append(f"#### 生成链分数")
            lines.append(f"")
            lines.append(f"| 维度 | 分数 | 说明 |")
            lines.append(f"|------|------|------|")
            lines.append(f"| 底象形成 | {score['xiang_formation']:.3f} | 差异组织化程度 |")
            lines.append(f"| 六阈值达标 | {score['six_threshold']:.3f} | 六机制同步达标率 |")
            lines.append(f"| 前主体态收束 | {score['convergence']:.3f} | 耦合收束率 |")
            lines.append(f"| 分级解封 | {score['unsealing']:.3f} | 最大解封等级/3 |")
            lines.append(f"| 回流锚定 | {score['return_flow']:.3f} | 高语义载荷锚定率 |")
            lines.append(f"| 语义防火墙 | {score['firewall']:.3f} | 低语义纯度 |")
            lines.append(f"| **综合** | **{score['overall']:.3f}** | **加权平均** |")
            lines.append(f"")

            # 底象
            xiang = la["xiang"]
            lines.append(f"#### 底象检测")
            lines.append(f"- 检测次数: {xiang.get('n_checks', 0)}")
            lines.append(f"- 形成次数: {xiang.get('n_formed', 0)}")
            lines.append(f"- 首次形成步: {xiang.get('first_formed_step', 'N/A')}")
            lines.append(f"- 最大密度: {xiang.get('max_density', 0):.4f}")
            lines.append(f"- 最大可追溯性: {xiang.get('max_trace', 0):.4f}")
            lines.append(f"")

            # 六阈值
            six = la["six_threshold"]
            lines.append(f"#### 六阈值检测")
            lines.append(f"- 评估次数: {six.get('n_evals', 0)}")
            lines.append(f"- 全部达标次数: {six.get('n_all_met', 0)}")
            lines.append(f"- 首次全达标步: {six.get('first_all_met_step', 'N/A')}")
            lines.append(f"- 平均达标数: {six.get('mean_n_met', 0):.2f}/6")
            if six.get("bottleneck_frequency"):
                lines.append(f"- 瓶颈频率: {six['bottleneck_frequency']}")
            lines.append(f"")

            # 收束
            conv = la["convergence"]
            lines.append(f"#### 前主体态收束")
            lines.append(f"- 评估次数: {conv.get('n_evals', 0)}")
            lines.append(f"- 收束次数: {conv.get('n_converged', 0)}")
            lines.append(f"- 首次收束步: {conv.get('first_converged_step', 'N/A')}")
            lines.append(f"- 最大稳定性分数: {conv.get('max_stability_score', 0):.4f}")
            lines.append(f"- 最大耦合对数: {conv.get('max_n_coupled_pairs', 0)}")
            lines.append(f"")

            # 解封
            unseal = la["unsealing"]
            lines.append(f"#### 分级解封")
            lines.append(f"- 解封事件数: {unseal.get('n_events', 0)}")
            lines.append(f"- 最大解封等级: {unseal.get('max_level', 0)}/3")
            if unseal.get("events"):
                lines.append(f"- 解封事件:")
                for evt in unseal["events"][:5]:
                    lines.append(f"  - Step {evt['step']}: Level {evt['level']} — {evt['reason']}")
            lines.append(f"")

            # 回流
            rf = la["return_flow"]
            lines.append(f"#### 回流通道")
            lines.append(f"- 最大锚定数: {rf.get('max_anchored', 0)}")
            lines.append(f"- 总剥离事件: {rf.get('total_detach_events', 0)}")
            lines.append(f"")

            # ODI
            odi = la["odi"]
            lines.append(f"#### 组织密度指数")
            lines.append(f"- 评估次数: {odi.get('n_evals', 0)}")
            lines.append(f"- 最大ODI: {odi.get('max_odi', 0):.4f}")
            lines.append(f"- 平均ODI: {odi.get('mean_odi', 0):.4f}")
            if odi.get("zone_distribution"):
                lines.append(f"- 区域分布: {odi['zone_distribution']}")
            lines.append(f"")

        # 回流注入结果
        if result.get("return_flow_injections"):
            lines.append(f"#### 高语义回流注入 (收束后)")
            lines.append(f"")
            lines.append(f"| 载荷ID | 类型 | 成功 | 锚定结构 | 锚定机制 | 原因 |")
            lines.append(f"|--------|------|------|---------|---------|------|")
            for inj in result["return_flow_injections"]:
                lines.append(
                    f"| {inj['payload_id']} | {inj['content_type']} | "
                    f"{'✓' if inj['success'] else '✗'} | "
                    f"{inj.get('anchor_structure', 'N/A')} | "
                    f"{inj.get('anchor_mechanism', 'N/A')} | "
                    f"{inj['reason']} |"
                )
            lines.append(f"")

    # ── 结论 ──
    lines.append(f"## 结论")
    lines.append(f"")

    best_config = max(
        all_results.items(),
        key=lambda x: np.mean([
            la["chain_score"]["overall"]
            for la in x[1]["layer_analyses"].values()
        ]) if x[1]["layer_analyses"] else 0.0,
    )
    lines.append(f"- **最佳配置**: {best_config[0]}")

    all_converged = all(
        any(la["chain_score"]["convergence"] > 0 for la in r["layer_analyses"].values())
        for r in all_results.values()
        if r["layer_analyses"]
    )
    lines.append(f"- **全部配置收束**: {'是' if all_converged else '否'}")

    all_firewall = all(
        all(la["chain_score"]["firewall"] == 1.0 for la in r["layer_analyses"].values())
        for r in all_results.values()
        if r["layer_analyses"]
    )
    lines.append(f"- **语义防火墙全部通过**: {'是' if all_firewall else '否'}")

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*由 exp_phase2_e2e.py 自动生成*")

    return "\n".join(lines)


# ─── 主入口 ───

def main():
    print("=" * 70)
    print("Phase 2 端到端集成实验")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 70)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_results = {}

    # 运行所有配置
    for name, cfg in CONFIGS.items():
        try:
            result = run_config(name, cfg)
            all_results[name] = result
        except Exception as e:
            print(f"\n  [ERROR] {name} 运行失败: {e}")
            import traceback
            traceback.print_exc()
            all_results[name] = {"config": name, "error": str(e)}

    # ── 保存 JSON ──
    json_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"exp_phase2_e2e_results_{timestamp}.json",
    )
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n\nJSON 结果已保存: {json_path}")

    # ── 生成并保存报告 ──
    report = generate_report(all_results, timestamp)
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"exp_phase2_e2e_report_{timestamp}.md",
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Markdown 报告已保存: {report_path}")

    # ── 最终摘要 ──
    print("\n" + "=" * 70)
    print("实验完成")
    print("=" * 70)
    for name, result in all_results.items():
        if "error" in result:
            print(f"  {name}: [ERROR] {result['error']}")
        else:
            avg_score = np.mean([
                la["chain_score"]["overall"]
                for la in result["layer_analyses"].values()
            ]) if result["layer_analyses"] else 0.0
            print(f"  {name}: 综合分数={avg_score:.3f}, "
                  f"层数={result['n_layers']}, "
                  f"耗时={result['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
