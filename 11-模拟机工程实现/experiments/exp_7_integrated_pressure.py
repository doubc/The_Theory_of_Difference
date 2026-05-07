"""
exp_7_integrated_pressure.py - 验证累积积分版 A9 升维压力

背景：
- exp_6 发现升维压力始终未触发（max≈0.03 << threshold 0.5）
- 原因：旧公式 `pressure = residual × density` 只用瞬时值
- 改进：新公式 `pressure = ∫|residual| dt × density`（累积积分）

目的：
验证累积积分版升维压力能否触发升维。

核心问题：
累积积分会放大小残差的长时间累积效应吗？
"""

import sys
import os
import torch
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from layers.L0_binary_lattice import L0BinaryLattice


def run_integrated_pressure_test(
    length=50,
    steps=300,
    diff_rate=0.1,
    inject_rate=0.03,
    absorb_rate=0.03,
    perturb_amp=0.02,
    ascent_threshold=0.5,
    seed=42
):
    """用 L0 层的累积积分版 measure_ascent_pressure 测试"""
    torch.manual_seed(seed)
    np.random.seed(seed)
    
    layer = L0BinaryLattice(shape=(1, length))
    state = layer.initial_state(batch_size=1)
    
    history = [state.clone()]
    pressures = []
    residuals = []
    structures_counts = []
    
    print("=" * 60)
    print("Exp #7: Integrated Ascent Pressure Test")
    print(f"  Length: {length}")
    print(f"  Steps: {steps}")
    print(f"  Inject rate: {inject_rate}")
    print(f"  Absorb rate: {absorb_rate}")
    print(f"  Ascent threshold: {ascent_threshold}")
    print("=" * 60)
    
    ascent_triggered_at = None
    
    for step in range(steps):
        # 演化
        state = layer.inject_difference(state, source_strength=inject_rate * 10)
        state = layer.absorb_difference(state, sink_strength=absorb_rate * 10)
        
        # 简单扩散
        left = torch.roll(state, -1, dims=-1)
        right = torch.roll(state, 1, dims=-1)
        neighbor_avg = (left + right) / 2
        state = state * (1 - diff_rate) + neighbor_avg * diff_rate
        
        # 扰动
        state = state + torch.randn_like(state) * perturb_amp
        state = state.clamp(0.0, 1.0)
        
        history.append(state.clone())
        
        # 每16步检测一次
        if step >= 16 and step % 16 == 0:
            structures = layer.detect_stable_structures(history)
            pressure = layer.measure_ascent_pressure(history, structures)
            
            # 计算瞬时残差
            q1 = layer.measure_invariant(history[-2])
            q2 = layer.measure_invariant(history[-1])
            residual = ((q2 - q1) ** 2).mean().item()
            
            pressures.append(pressure)
            residuals.append(residual)
            structures_counts.append(len(structures))
            
            if pressure > ascent_threshold and ascent_triggered_at is None:
                ascent_triggered_at = step
                print(f"\n  ** A9 ASCENT TRIGGERED at step {step} **")
                print(f"     pressure={pressure:.6f} > threshold={ascent_threshold}")
    
    # 最终分析
    print("\n--- Results ---")
    if pressures:
        print(f"  Max pressure: {max(pressures):.6f}")
        print(f"  Mean pressure: {np.mean(pressures):.6f}")
        print(f"  Min pressure: {min(pressures):.6f}")
        print(f"  Max residual: {max(residuals):.6f}")
        print(f"  Mean structures: {np.mean(structures_counts):.1f}")
        
        # 对比瞬时残差和累积压力
        print("\n  Time series (sampled):")
        indices = list(range(0, len(pressures), max(1, len(pressures) // 10)))
        for i in indices:
            print(f"    Window {i}: pressure={pressures[i]:.6f}, residual={residuals[i]:.6f}")
    
    # A7 稳定性检查
    if len(history) >= 16:
        window = history[-16:]
        states = torch.stack(window, dim=0)
        pattern_sim = torch.cosine_similarity(
            states[-1].flatten().unsqueeze(0),
            states[-2].flatten().unsqueeze(0)
        ).item()
        turnover = (states[-1] - states[-2]).abs().mean().item()
        print(f"\n  Stability: pattern_sim={pattern_sim:.4f}, turnover={turnover:.4f}")
    
    # 结论
    print(f"\n{'=' * 60}")
    if ascent_triggered_at is not None:
        print(f"A9 Ascent: YES (step {ascent_triggered_at})")
    else:
        max_p = max(pressures) if pressures else 0
        print(f"A9 Ascent: NO (max={max_p:.6f}, threshold={ascent_threshold})")
        ratio = max_p / ascent_threshold if max_p > 0 else 0
        print(f"  Pressure reached {ratio:.1%} of threshold")
    
    return {
        'ascent_triggered': ascent_triggered_at is not None,
        'max_pressure': max(pressures) if pressures else 0,
        'mean_pressure': np.mean(pressures) if pressures else 0,
    }


def parameter_sweep():
    """参数扫描：注入率 vs 升维压力"""
    print("\n\n" + "#" * 60)
    print("Parameter Sweep: inject_rate vs integrated pressure")
    print("#" * 60)
    
    inject_rates = [0.01, 0.03, 0.05, 0.10, 0.15, 0.20]
    results = []
    
    for ir in inject_rates:
        print(f"\n--- inject_rate = {ir} ---")
        r = run_integrated_pressure_test(
            length=50, steps=300,
            inject_rate=ir, absorb_rate=0.03,
            ascent_threshold=0.5
        )
        results.append((ir, r))
    
    # 汇总表
    print("\n\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"{'inject':>8} {'max_p':>10} {'mean_p':>10} {'ascent':>8}")
    print("-" * 40)
    for ir, r in results:
        asc = "YES" if r['ascent_triggered'] else "no"
        print(f"{ir:8.2f} {r['max_pressure']:10.6f} {r['mean_pressure']:10.6f} {asc:>8}")
    
    triggered = [ir for ir, r in results if r['ascent_triggered']]
    if triggered:
        print(f"\nMinimum inject_rate to trigger: {min(triggered):.2f}")
    else:
        max_all = max(r['max_pressure'] for ir, r in results)
        print(f"\nMax pressure across all params: {max_all:.6f}")
        print(f"Suggestion: increase inject-absorb gap further")


if __name__ == "__main__":
    print("=" * 60)
    print("Experiment #7: Integrated Ascent Pressure")
    print("=" * 60)
    
    # Part 1: 基础测试
    print("\n\n" + "#" * 60)
    print("Part 1: Baseline")
    print("#" * 60)
    
    r1 = run_integrated_pressure_test(
        length=50, steps=300,
        inject_rate=0.03, absorb_rate=0.03,
        ascent_threshold=0.5
    )
    
    # Part 2: 参数扫描
    parameter_sweep()
    
    print("\n\nConclusion:")
    print("累积积分版公式是否有效？需要对比 exp_6 的结果。")
