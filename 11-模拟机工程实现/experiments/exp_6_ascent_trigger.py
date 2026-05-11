"""
exp_6_ascent_trigger.py - 实验日志 #6: A9 升维触发 + 粗粒化映射

实验目的:
    在 L0 场 + A1 源 + A8 汇 + A7 稳定结构的基础上,
    验证 A9 升维触发条件是否可被可靠触发,
    并尝试粗粒化映射将 L0 稳定结构封装为 L1 token.

    A9 不是约束, 是触发器:
    - 不参与 loss 计算
    - check_ascent() 独立判定是否应该升维
    - 升维压力 = 守恒残差 x 结构密度 (当前实现)
    
    三条升维条件(理论):
    1. A5 检测到守恒残差 - 当前层的守恒量不再被完美保持
    2. A9 检测到不可约残差 - 稳定结构无法被当前层的原语完全表达
    3. 稳定结构存在 - A7 已确认有活结构

核心问题:
1. 在什么参数条件下, 升维压力超过阈值?
2. 升维压力随时间的演化曲线是什么样的?
3. 粗粒化映射能否将 L0 的稳定区域压缩为 L1 token?
4. 粗粒化后的 L1 与 L0 之间有什么信息保留/丢失?

实验设计:
    Phase 1: 基础运行 - 复现 Exp#5 的稳定结构, 确认 baseline
    Phase 2: 渐进注入 - 逐步增大注入制造守恒残差
    Phase 3: 参数扫描 - 不同注入强度下的升维压力
    Phase 4: 粗粒化映射 - 对稳定区域执行 2x1 block 压缩, 生成 L1

对照:
    - 之前的 Exp#5: 源-汇平衡, 升维压力应接近 0
    - 增大注入: 守恒量增加, 残差增大, 应触发升维
"""

import sys
import os
import torch
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from experiments.logger import ExperimentLogger


# ============================================================
# 基本场操作 (与 Exp#5 一致)
# ============================================================

def simple_diffuse(state, diffusion_rate=0.1):
    left = torch.roll(state, -1, dims=-1)
    right = torch.roll(state, 1, dims=-1)
    neighbor_avg = (left + right) / 2
    return state * (1 - diffusion_rate) + neighbor_avg * diffusion_rate


def random_perturb(state, amplitude=0.02):
    return state + torch.randn_like(state) * amplitude


def inject_difference(state, rate=0.03, width=3):
    noise = torch.rand_like(state)
    mask = torch.zeros_like(state)
    w = min(width, state.shape[-1] // 4)
    mask[..., :w] = 1.0
    return state + rate * noise * mask


def absorb_difference(state, rate=0.03, width=3):
    mask = torch.zeros_like(state)
    w = min(width, state.shape[-1] // 4)
    mask[..., -w:] = 1.0
    return state * (1.0 - mask * rate * 0.3)


# ============================================================
# A9 升维压力计算
# ============================================================

def compute_conservation_residual(history):
    """A5 守恒残差: 总量变化率的均方
    
    如果总量恒定, 残差 = 0 (封闭系统)
    如果总量在变, 残差 > 0 (开放系统, 注入/吸收不平衡)
    """
    if len(history) < 2:
        return 0.0
    
    states = torch.stack(history, dim=0)  # (T, batch, L)
    # Sum over spatial dims
    quantities = states.sum(dim=(-1,))  # (T, batch)
    if quantities.dim() > 1:
        quantities = quantities.sum(dim=-1)  # (T,)
    
    changes = (quantities[1:] - quantities[:-1]) ** 2
    return changes.mean().item()


def compute_structure_density(history, threshold_std=0.1, 
                               threshold_mean_low=0.1, threshold_mean_high=0.9):
    """结构密度: 稳定区域占总空间的比例
    
    稳定 = 时间标准差小 + 不全0/全1
    """
    if len(history) < 2:
        return 0.0
    
    states = torch.stack(history, dim=0)  # (T, batch, L)
    temporal_std = states.std(dim=0)      # (batch, L)
    temporal_mean = states.mean(dim=0)    # (batch, L)
    
    stable_mask = (temporal_std < threshold_std) & \
                  (temporal_mean > threshold_mean_low) & \
                  (temporal_mean < threshold_mean_high)
    
    return stable_mask.float().mean().item()


def compute_ascent_pressure(conservation_residual, structure_density):
    """升维压力 = 守恒残差 x 结构密度
    
    这是当前 L0.measure_ascent_pressure() 的实现逻辑
    """
    return conservation_residual * structure_density


def compute_irreducibility_score(history, structures_mask=None):
    """不可约性得分: 检查稳定结构内部是否存在无法被均值+方差表达的残留模式
    
    思路: 如果一个区域的时间演化可以用 (均值 + 噪声) 充分近似,
    那它是可约的; 如果存在残差模式(如周期性/趋势), 则不可约.
    
    当前简化实现: 用一阶自回归拟合, 残差越大越不可约
    """
    if len(history) < 4:
        return 0.0
    
    states = torch.stack(history, dim=0)  # (T, batch, L)
    
    # 一阶自回归: s[t] = a * s[t-1] + b + noise
    s_prev = states[:-1].flatten()
    s_curr = states[1:].flatten()
    
    n = s_prev.numel()
    if n < 2:
        return 0.0
    
    sum_x = s_prev.sum()
    sum_y = s_curr.sum()
    sum_xx = (s_prev * s_prev).sum()
    sum_xy = (s_prev * s_curr).sum()
    
    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-10:
        return 0.0
    
    a = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - a * sum_x) / n
    
    predicted = a * s_prev + b
    residual = ((s_curr - predicted) ** 2).mean().item()
    
    var = s_curr.var().item()
    if var < 1e-10:
        return 0.0
    
    return min(residual / var, 1.0)


# ============================================================
# 粗粒化映射
# ============================================================

def coarse_grain_2x1(state, length):
    """2x1 block 平均粗粒化
    
    将相邻两个格点合并为一个 L1 token.
    如果 length 为奇数, 丢弃最后一个格点.
    
    Returns:
        l1_state: (1, length//2) 的粗粒化状态
        block_map: 映射关系, l1[i] = mean(l0[2i], l0[2i+1])
    """
    s = state.squeeze(0)  # (L,)
    n_blocks = length // 2
    
    l1_values = []
    block_map = []
    
    for i in range(n_blocks):
        block_start = 2 * i
        block_end = 2 * i + 2
        block_mean = s[block_start:block_end].mean().item()
        l1_values.append(block_mean)
        block_map.append((block_start, block_end))
    
    l1_state = torch.tensor([l1_values], dtype=torch.float32)
    return l1_state, block_map


def compute_coarse_graining_error(state, l1_state, block_map):
    """粗粒化误差: L0 原始状态与 L1 重建状态之间的偏差
    
    重建: 每个格点用其所属 block 的均值替代
    误差 = MSE(original, reconstructed)
    """
    s = state.squeeze(0)
    reconstructed = torch.zeros_like(s)
    
    for i, (start, end) in enumerate(block_map):
        reconstructed[start:end] = l1_state[0, i]
    
    mse = ((s - reconstructed) ** 2).mean().item()
    return mse


def analyze_l1_layer(l1_state, l1_history=None):
    """分析 L1 层的基本统计"""
    s = l1_state.squeeze(0)
    n = s.numel()
    
    result = {
        'length': n,
        'mean': s.mean().item(),
        'std': s.std().item(),
    }
    
    if n > 1:
        diff = (s[1:] - s[:-1]).abs()
        result['gradient_mean'] = diff.mean().item()
        result['gradient_max'] = diff.max().item()
    
    if l1_history is not None and len(l1_history) >= 2:
        totals = [h.sum().item() for h in l1_history]
        total_changes = [abs(totals[i+1] - totals[i]) for i in range(len(totals)-1)]
        result['conservation_residual'] = np.mean([c**2 for c in total_changes])
        result['total_change_pct'] = abs(totals[-1] - totals[0]) / max(abs(totals[0]), 1e-6) * 100
    
    return result


# ============================================================
# A7 稳定性检测 (与 Exp#5 一致)
# ============================================================

def compute_pattern_persistence(history_window):
    if len(history_window) < 2:
        return 0.0
    states = torch.stack(history_window, dim=0).squeeze(1)
    similarities = []
    for t in range(len(states) - 1):
        s1 = states[t].flatten()
        s2 = states[t+1].flatten()
        dot = (s1 * s2).sum()
        norm1 = s1.norm()
        norm2 = s2.norm()
        if norm1 > 1e-6 and norm2 > 1e-6:
            sim = dot / (norm1 * norm2)
            similarities.append(sim.item())
    return np.mean(similarities) if similarities else 0.0


def compute_material_turnover(history_window):
    if len(history_window) < 2:
        return 0.0
    states = torch.stack(history_window, dim=0).squeeze(1)
    changes = (states[1:] - states[:-1]).abs().mean(dim=1)
    return changes.mean().item()


def classify_structure(pattern_persistence, material_turnover,
                      pattern_threshold=0.9, turnover_threshold=0.01):
    if pattern_persistence < pattern_threshold:
        return 'noise'
    if material_turnover < turnover_threshold:
        return 'dead'
    return 'alive'


# ============================================================
# 主实验
# ============================================================

def run_ascent_experiment(length=50, steps=500, window_size=16,
                          diff_rate=0.1, inject_rate=0.03,
                          absorb_rate=0.03, perturb_amp=0.02,
                          ascent_threshold=0.5, seed=42,
                          inject_schedule=None):
    """运行升维触发实验
    
    inject_schedule: 可选, dict of {step: inject_rate}
                     用于在运行中改变注入强度, 制造守恒残差
    """
    torch.manual_seed(seed)
    np.random.seed(seed)
    
    logger = ExperimentLogger(f"exp_6_inj{inject_rate:.2f}")
    logger.start(
        params=dict(length=length, steps=steps, window_size=window_size,
                    diff_rate=diff_rate, inject_rate=inject_rate,
                    absorb_rate=absorb_rate, perturb_amp=perturb_amp,
                    ascent_threshold=ascent_threshold, seed=seed,
                    inject_schedule=str(inject_schedule)),
        description="A9升维触发+粗粒化映射（旧公式 residual x density）",
    )

    state = torch.rand(1, length)
    history = [state.clone()]
    
    ascent_pressures = []
    conservation_residuals = []
    structure_densities = []
    irreducibility_scores = []
    totals = [state.sum().item()]
    
    current_inject = inject_rate
    
    print("=" * 60)
    print("Exp #6: A9 Ascent Trigger + Coarse-Graining")
    print(f"  Length: {length}")
    print(f"  Steps: {steps}")
    print(f"  Window size: {window_size}")
    print(f"  Diffusion rate: {diff_rate}")
    print(f"  Inject rate: {inject_rate}")
    print(f"  Absorb rate: {absorb_rate}")
    print(f"  Ascent threshold: {ascent_threshold}")
    print("=" * 60)
    
    ascent_triggered_at = None
    
    for step in range(steps):
        if inject_schedule and step in inject_schedule:
            current_inject = inject_schedule[step]
            print(f"  >> Step {step}: inject_rate changed to {current_inject}")
        
        state = inject_difference(state, rate=current_inject)
        state = absorb_difference(state, rate=absorb_rate)
        state = simple_diffuse(state, diff_rate)
        state = random_perturb(state, perturb_amp)
        state = state.clamp(0.0, 1.0)
        history.append(state.clone())
        totals.append(state.sum().item())
        
        if (step + 1) % window_size == 0 and step >= window_size:
            window = history[-window_size:]
            
            c_residual = compute_conservation_residual(window)
            s_density = compute_structure_density(window)
            pressure = compute_ascent_pressure(c_residual, s_density)
            irred = compute_irreducibility_score(window)
            
            conservation_residuals.append(c_residual)
            structure_densities.append(s_density)
            ascent_pressures.append(pressure)
            irreducibility_scores.append(irred)
            
            logger.log_step(step, {
                "pressure": round(pressure, 6),
                "residual": round(c_residual, 6),
                "density": round(s_density, 4),
                "irreducibility": round(irred, 4),
            })

            if pressure > ascent_threshold and ascent_triggered_at is None:
                logger.log_event("ascent_triggered", {
                    "step": step, "pressure": pressure,
                    "residual": c_residual, "density": s_density,
                    "threshold": ascent_threshold,
                })
                ascent_triggered_at = step
                print(f"  ** A9 ASCENT TRIGGERED at step {step} **")
                print(f"     pressure={pressure:.4f} > threshold={ascent_threshold}")
                print(f"     residual={c_residual:.4f}, density={s_density:.4f}")
    
    # ---- Final analysis ----
    
    print("\n--- Evolution complete ---")
    
    total_start = totals[0]
    total_end = totals[-1]
    total_change_pct = (total_end - total_start) / max(abs(total_start), 1e-6) * 100
    print(f"  Total quantity: {total_start:.2f} -> {total_end:.2f} ({total_change_pct:+.2f}%)")
    
    if ascent_pressures:
        print("\n--- A9 Ascent Pressure Stats ---")
        print(f"  Max pressure:  {max(ascent_pressures):.6f}")
        print(f"  Mean pressure: {np.mean(ascent_pressures):.6f}")
        print(f"  Min pressure:  {min(ascent_pressures):.6f}")
        print(f"  Mean residual: {np.mean(conservation_residuals):.6f}")
        print(f"  Mean density:  {np.mean(structure_densities):.4f}")
        print(f"  Mean irreducibility: {np.mean(irreducibility_scores):.4f}")
        
        print("\n  Pressure time series:")
        n_points = len(ascent_pressures)
        sample_indices = list(range(0, n_points, max(1, n_points // 10)))
        if sample_indices[-1] != n_points - 1:
            sample_indices.append(n_points - 1)
        for i in sample_indices:
            step_num = (i + 1) * window_size
            triggered = " ** ASCENT" if ascent_pressures[i] > ascent_threshold else ""
            print(f"    Step {step_num:3d}: pressure={ascent_pressures[i]:.6f}, "
                  f"residual={conservation_residuals[i]:.6f}, "
                  f"density={structure_densities[i]:.4f}, "
                  f"irred={irreducibility_scores[i]:.4f}{triggered}")
    
    # A7 stability check
    final_window = history[-window_size:]
    pattern_persist = compute_pattern_persistence(final_window)
    turnover = compute_material_turnover(final_window)
    structure_type = classify_structure(pattern_persist, turnover)
    print("\n--- A7 Stability Check ---")
    print(f"  Pattern persistence: {pattern_persist:.4f}")
    print(f"  Material turnover:   {turnover:.4f}")
    print(f"  Structure type:      {structure_type.upper()}")
    
    # ---- Coarse-graining ----
    
    print("\n--- Coarse-Graining (2x1 block) ---")
    
    l1_state, block_map = coarse_grain_2x1(state, length)
    l1_analysis = analyze_l1_layer(l1_state)
    
    print(f"  L0: length={length}, mean={state.mean().item():.4f}, std={state.std().item():.4f}")
    print(f"  L1: length={l1_analysis['length']}, mean={l1_analysis['mean']:.4f}, std={l1_analysis['std']:.4f}")
    if 'gradient_mean' in l1_analysis:
        print(f"  L1 gradient: mean={l1_analysis['gradient_mean']:.4f}, max={l1_analysis['gradient_max']:.4f}")
    
    cg_error = compute_coarse_graining_error(state, l1_state, block_map)
    print(f"  Coarse-graining MSE: {cg_error:.6f}")
    
    # L1 conservation over time
    l1_history = []
    for h in history[-window_size:]:
        l1_h, _ = coarse_grain_2x1(h, length)
        l1_history.append(l1_h)
    l1_full = analyze_l1_layer(l1_state, l1_history)
    if 'conservation_residual' in l1_full:
        print(f"  L1 conservation residual: {l1_full['conservation_residual']:.6f}")
        print(f"  L1 total change: {l1_full.get('total_change_pct', 0):.4f}%")
    
    # Per-block analysis
    print("\n  Per-block analysis:")
    s = state.squeeze(0)
    block_errors = []
    for i, (start, end) in enumerate(block_map):
        block = s[start:end]
        block_std = block.std().item()
        block_range = (block.max() - block.min()).item()
        block_mean = block.mean().item()
        error = ((block - block_mean) ** 2).mean().item()
        block_errors.append(error)
        if i < 5 or i >= len(block_map) - 3:
            print(f"    Block {i:2d} [{start:2d}-{end:2d}]: mean={block_mean:.3f}, "
                  f"std={block_std:.3f}, range={block_range:.3f}, mse={error:.6f}")
        elif i == 5:
            print(f"    ... ({len(block_map) - 7} more blocks) ...")
    
    print(f"  Mean block MSE: {np.mean(block_errors):.6f}")
    print(f"  Max block MSE:  {max(block_errors):.6f}")
    
    # ---- Summary ----
    
    print(f"\n{'=' * 60}")
    print("Conclusion")
    print(f"{'=' * 60}")
    
    if ascent_triggered_at is not None:
        print(f"A9 Ascent: YES (step {ascent_triggered_at})")
        print(f"  Trigger: residual x density > {ascent_threshold}")
    else:
        max_p = max(ascent_pressures) if ascent_pressures else 0
        print(f"A9 Ascent: NO (max pressure={max_p:.6f}, threshold={ascent_threshold})")
        if max_p < ascent_threshold * 0.1:
            print(f"  Reason: both residual and density are low, system at equilibrium")
        elif max_p < ascent_threshold:
            ratio = max_p / ascent_threshold
            print(f"  Reason: pressure reached {ratio:.1%} of threshold, need more injection-absorption imbalance")
    
    print("\nCoarse-graining assessment:")
    if cg_error < 0.01:
        print(f"  Low CG error ({cg_error:.6f}): L0 nearly uniform, 2x1 compression loses little")
    elif cg_error < 0.05:
        print(f"  Medium CG error ({cg_error:.6f}): L0 has local gradients, some info lost")
    else:
        print(f"  High CG error ({cg_error:.6f}): L0 has large differences, simple mean loses too much")
    
    logger.log_event("result", {
        "ascent_triggered": ascent_triggered_at is not None,
        "cg_error": round(cg_error, 6),
        "structure_type": structure_type,
    })
    logger.finish(
        final_metrics={
            "max_pressure": round(max(ascent_pressures) if ascent_pressures else 0, 6),
            "mean_pressure": round(np.mean(ascent_pressures) if ascent_pressures else 0, 6),
            "mean_residual": round(np.mean(conservation_residuals) if conservation_residuals else 0, 6),
            "mean_density": round(np.mean(structure_densities) if structure_densities else 0, 4),
            "structure_type": structure_type,
            "pattern_persistence": round(pattern_persist, 4),
            "material_turnover": round(turnover, 4),
            "cg_error": round(cg_error, 6),
            "l1_length": l1_analysis['length'],
            "total_change_pct": round(total_change_pct, 2),
        },
        conclusion=(
            f"A9升维{'触发' if ascent_triggered_at else '未触发'} "
            f"(max_p={max(ascent_pressures) if ascent_pressures else 0:.4f}), "
            f"粗粒化MSE={cg_error:.6f}, 结构={structure_type}"
        ),
    )

    return dict(
        ascent_triggered_at=ascent_triggered_at,
        max_pressure=max(ascent_pressures) if ascent_pressures else 0,
        mean_pressure=np.mean(ascent_pressures) if ascent_pressures else 0,
        mean_residual=np.mean(conservation_residuals) if conservation_residuals else 0,
        mean_density=np.mean(structure_densities) if structure_densities else 0,
        mean_irreducibility=np.mean(irreducibility_scores) if irreducibility_scores else 0,
        structure_type=structure_type,
        pattern_persistence=pattern_persist,
        material_turnover=turnover,
        cg_error=cg_error,
        l1_length=l1_analysis['length'],
        total_change_pct=total_change_pct,
    )


def run_parameter_sweep():
    """Parameter sweep: injection rate vs ascent pressure"""
    
    print(f"\n{'=' * 60}")
    print("Parameter Sweep: inject_rate vs ascent pressure")
    print(f"{'=' * 60}")
    
    inject_rates = [0.01, 0.03, 0.05, 0.10, 0.15, 0.20, 0.30]
    results = []
    
    for ir in inject_rates:
        print(f"\n--- inject_rate = {ir} ---")
        r = run_ascent_experiment(
            length=50, steps=500, window_size=16,
            diff_rate=0.1, inject_rate=ir,
            absorb_rate=0.03,
            perturb_amp=0.02, seed=42
        )
        results.append((ir, r))
    
    # Summary table
    print(f"\n\n{'=' * 60}")
    print("Parameter Sweep Summary")
    print(f"{'=' * 60}")
    print(f"{'inject':>8s} {'max_p':>10s} {'mean_p':>10s} {'residual':>10s} {'density':>8s} {'irred':>8s} {'type':>6s} {'cg_err':>8s} {'ascent':>8s}")
    print(f"{'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*6} {'-'*8} {'-'*8}")
    
    for ir, r in results:
        asc = "YES" if r['ascent_triggered_at'] is not None else "no"
        print(f"{ir:8.2f} {r['max_pressure']:10.6f} {r['mean_pressure']:10.6f} "
              f"{r['mean_residual']:10.6f} {r['mean_density']:8.4f} "
              f"{r['mean_irreducibility']:8.4f} {r['structure_type']:>6s} "
              f"{r['cg_error']:8.6f} {asc:>8s}")
    
    triggered = [ir for ir, r in results if r['ascent_triggered_at'] is not None]
    if triggered:
        print(f"\nMinimum injection rate to trigger ascent: {min(triggered):.2f}")
    else:
        print(f"\nNo ascent triggered in current parameter range")
        print(f"Suggestion: increase inject-absorb gap, or lower ascent_threshold")


if __name__ == "__main__":
    print("=" * 60)
    print("Experiment #6: A9 Ascent Trigger + Coarse-Graining")
    print("=" * 60)
    
    # Part 1: Baseline (same params as Exp#5)
    print(f"\n\n{'#' * 60}")
    print("Part 1: Baseline (same params as Exp#5)")
    print(f"{'#' * 60}")
    
    r1 = run_ascent_experiment(
        length=50, steps=500, window_size=16,
        diff_rate=0.1, inject_rate=0.03,
        absorb_rate=0.03, perturb_amp=0.02,
        ascent_threshold=0.5, seed=42
    )
    
    # Part 2: Progressive injection ramp
    print(f"\n\n{'#' * 60}")
    print("Part 2: Progressive Injection (ramping up)")
    print(f"{'#' * 60}")
    
    r2 = run_ascent_experiment(
        length=50, steps=500, window_size=16,
        diff_rate=0.1, inject_rate=0.03,
        absorb_rate=0.03, perturb_amp=0.02,
        ascent_threshold=0.5, seed=42,
        inject_schedule={
            200: 0.06,
            300: 0.12,
            400: 0.25,
        }
    )
    
    # Part 3: Parameter sweep
    print(f"\n\n{'#' * 60}")
    print("Part 3: Parameter Sweep")
    print(f"{'#' * 60}")
    
    run_parameter_sweep()
    
    print(f"\nNext: Exp #7 - Multi-layer nesting and inter-layer feedback")
