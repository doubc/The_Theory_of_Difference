"""exp_10_physics_validation.py — 物理数学化验证实验

测试当前模拟机在第一阶段（九公理→物理性质可检测）的实际表现。
对比连续版本 vs 严格离散版本的涌现结果。
"""
import torch
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from acl.axiom_base import AxiomEngine
from acl.axioms import (
    A1_DifferenceSource, A2_DiscreteEncoding, A3_Locality,
    A4_MinimalVariation, A5_Conservation, A6_FlowCoupling,
    A7_Stability, A8_SymmetrySink, A9_MinimalSufficient,
)
from layers.L0_binary_lattice import L0BinaryLattice
from layers.hamming_layer import HammingLattice
from models.local_conv_model import LocalConvModel
from engine.world_engine import WorldEngine


def run_continuous_version():
    """运行连续版本（旧）"""
    print("=" * 60)
    print("CONTINUOUS VERSION (L0 Binary Lattice + CNN Reactor)")
    print("=" * 60)

    layer = L0BinaryLattice(shape=(16, 16))
    model = LocalConvModel(channels=1)
    axioms = [
        A1_DifferenceSource(), A2_DiscreteEncoding(), A3_Locality(),
        A4_MinimalVariation(), A5_Conservation(), A6_FlowCoupling(),
        A7_Stability(), A8_SymmetrySink(), A9_MinimalSufficient(),
    ]
    engine = WorldEngine(
        model=model, layer=layer, axiom_engine=AxiomEngine(axioms),
        xiangjie_check_interval=999,  # 跳过象界检测
    )

    result = engine.run(max_steps=64, ascent_check_interval=999)

    # 分析结果
    final = result['final_state']
    structures = result['structures_detected']

    # 物理量测量
    mean_val = final.mean().item()
    std_val = final.std().item()
    unique_vals = len(torch.unique(final.round()))

    # 差异密度
    diff_map = layer.measure_difference(final)
    diff_density = diff_map.mean().item()

    # 守恒量
    invariant = layer.measure_invariant(final).mean().item()

    print(f"Steps: {result['total_steps']}")
    print(f"Structures detected: {structures}")
    print(f"Final state: mean={mean_val:.4f}, std={std_val:.4f}")
    print(f"Unique values: {unique_vals}")
    print(f"Difference density: {diff_density:.4f}")
    print(f"Conservation (total activation): {invariant:.4f}")

    # 检查公理违背
    if result['reports']:
        last_report = result['reports'][-1]
        print(f"\nAxiom violations (last step):")
        for name, report in last_report.axiom_reports.items():
            if hasattr(report, 'raw_violation'):
                print(f"  {name}: {report.raw_violation:.4f}")

    return {
        'mean': mean_val, 'std': std_val, 'unique': unique_vals,
        'diff_density': diff_density, 'invariant': invariant,
        'structures': structures,
    }


def run_strict_version():
    """运行严格离散版本（新）"""
    print("\n" + "=" * 60)
    print("STRICT DISCRETE VERSION (Hamming Lattice + Strict Axioms)")
    print("=" * 60)

    N = 16
    layer = HammingLattice(N=N, stability_window=8, use_strict_axioms=True)

    # 严格版本不需要 CNN 模型（演化是离散翻转）
    # 但为了接口兼容，创建一个 dummy model
    from torch import nn
    dummy_model = nn.Identity()

    # 使用严格化公理引擎
    from acl.axioms_strict import create_strict_axiom_engine
    strict_engine = create_strict_axiom_engine(N=N)

    # 手动运行演化
    state = layer.initial_state(batch_size=1).squeeze(0)  # (N,)
    history = [state.clone()]

    axiom_losses = []
    flip_indices = []

    for step in range(64):
        # A8 对称偏好：计算当前汉明重量，调制翻转方向
        w = state.sum().long().item()
        w = max(0, min(N, w))
        from engine.hamming_engine import HammingMeasurement
        weight_vec = HammingMeasurement.symmetry_weight_vector(N).to(state.device)
        # 当前重量的对称偏好权重
        current_weight = weight_vec[min(w, N)].item()
        # 目标：让重量趋向 N/2
        target_w = N // 2
        if w < target_w:
            # 低于中截面，偏好 0→1（增加重量）
            weights = (1.0 - state) * current_weight  # 只翻转 0→1
        elif w > target_w:
            # 高于中截面，偏好 1→0（减少重量）
            weights = state * current_weight  # 只翻转 1→0
        else:
            # 在中截面附近，均匀翻转
            weights = torch.ones(N, device=state.device) * current_weight

        # 单比特翻转
        new_state, idx = layer.step_hamming(state, weights)
        flip_indices.append(idx)

        # 计算公理损失
        loss = layer.compute_axiom_loss(state, new_state, history)
        axiom_losses.append(loss.item())

        state = new_state
        history.append(state.clone())

    # 分析结果
    final = state
    structures = layer.detect_stable_structures(history)

    mean_val = final.mean().item()
    std_val = final.std().item()
    unique_vals = len(torch.unique(final))

    # 汉明重量
    hamming_w = final.sum().item()

    print(f"Steps: {len(history)-1}")
    print(f"Structures detected: {len(structures)}")
    print(f"Final state: mean={mean_val:.4f}, std={std_val:.4f}")
    print(f"Hamming weight: {hamming_w}/{N}")
    print(f"Symmetry proximity: {HammingMeasurement.mid_surface_proximity(final):.4f}")
    print(f"Avg axiom loss: {sum(axiom_losses)/len(axiom_losses):.4f}")

    # 翻转统计
    flips = [f for f in flip_indices if f >= 0]
    print(f"Total flips: {len(flips)}")
    if flips:
        # 翻转方向分布
        flip_tensor = torch.tensor(flips)
        print(f"Mean flip position: {flip_tensor.float().mean().item():.1f}")

    return {
        'mean': mean_val, 'std': std_val, 'unique': unique_vals,
        'hamming_weight': hamming_w, 'structures': len(structures),
        'avg_axiom_loss': sum(axiom_losses)/len(axiom_losses),
    }


def analyze_physics(results_continuous, results_strict):
    """分析物理数学化程度"""
    print("\n" + "=" * 60)
    print("PHYSICS ANALYSIS")
    print("=" * 60)

    print("\n--- 维度锁定 ---")
    print(f"  Continuous: state space = R^(16x16) (continuous)")
    print(f"  Strict:     state space = {{0,1}}^16 (discrete hypercube)")
    print(f"  WorldBase target: D_eff = 3 (from A1+A1'+A9)")

    print("\n--- 引力势 ---")
    print(f"  Continuous: difference density = {results_continuous['diff_density']:.4f}")
    print(f"  Strict:     hamming weight = {results_strict['hamming_weight']}/16")
    print(f"  WorldBase target: Φ ∝ -1/r (from D=3 + A5 conservation)")

    print("\n--- 规范结构 ---")
    print(f"  Continuous: unique values = {results_continuous['unique']}")
    print(f"  Strict:     unique patterns = {results_strict['unique']}")
    print(f"  WorldBase target: su(3), su(2), U(1) gauge groups")

    print("\n--- 稳定性 ---")
    print(f"  Continuous: structures = {results_continuous['structures']}")
    print(f"  Strict:     structures = {results_strict['structures']}")
    print(f"  WorldBase target: stable structures from A7 cycle closure")

    print("\n--- 公理损失 ---")
    print(f"  Strict version avg axiom loss: {results_strict['avg_axiom_loss']:.4f}")
    print(f"  (lower = better satisfaction of all 9 axioms)")

    print("\n" + "=" * 60)
    print("WHAT'S EMERGED vs WHAT'S MISSING")
    print("=" * 60)

    print("\n[OK] EMERGED:")
    print("  - Discrete state space {0,1}^N (strict A2)")
    print("  - Single-bit flip evolution (strict A4)")
    print("  - DAG direction constraint (strict A6)")
    print("  - Symmetry preference weight (strict A8)")
    print("  - Cycle closure detection (strict A7)")
    print("  - Stable structure detection")

    print("\n[MISSING] NOT YET EMERGED:")
    print("  - Dimension locking (D=3): needs spatial embedding")
    print("  - Gravitational potential (Φ ∝ -1/r): needs distance metric")
    print("  - Gauge group structure (su(3), su(2), U(1)): needs field theory")
    print("  - Fermion/boson statistics: needs quantum sector")
    print("  - Parameter closure: needs all interactions coupled")

    print("\n[WARNING] CRITICAL GAPS:")
    print("  - Current state: 1D bit string, no spatial geometry")
    print("  - Needed: 3D spatial embedding from A1+A1'+A9")
    print("  - Current: single species, no particle types")
    print("  - Needed: multi-species from sub-space decomposition")


if __name__ == "__main__":
    torch.manual_seed(42)
    results_c = run_continuous_version()
    results_s = run_strict_version()
    analyze_physics(results_c, results_s)
