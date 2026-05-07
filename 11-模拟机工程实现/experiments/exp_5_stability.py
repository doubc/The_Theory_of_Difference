"""
exp_5_stability.py — 实验日志 #5：A7 稳定性判定

实验目的：
    在源-汇结构基础上，观测 A7 稳定性指标。
    
    A7 的核心定义：
    - 稳定 = 模式持续（pattern persistence），而非状态不变
    - 活结构：模式持续 + 物质更换（漩涡型）→ 好
    - 死结构：模式持续 + 物质不换（冻结型）→ 惩罚
    - 噪声：模式不持续 → 失败
    
    四个子指标：
    - pattern_persistence：差异场的时间相关性（余弦相似度）
    - boundary_integrity：梯度场的时间稳定性
    - material_turnover：状态值的平均变化量
    - frozenness：pattern 高 + turnover 低 → 冻结惩罚

核心问题：
1. 源-汇结构能否形成稳定模式？
2. 稳定区域在哪里？（源端？汇端？中间？）
3. 是活结构还是死结构？

实验设计：
    - 运行足够长的步数（400步），让模式有机会稳定
    - 用时间窗口（16步）计算稳定性指标
    - 对比不同区域的稳定性
"""

import sys
import os
import torch
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def simple_diffuse(state, diffusion_rate=0.1):
    """纯扩散"""
    left = torch.roll(state, -1, dims=-1)
    right = torch.roll(state, 1, dims=-1)
    neighbor_avg = (left + right) / 2
    return state * (1 - diffusion_rate) + neighbor_avg * diffusion_rate


def random_perturb(state, amplitude=0.02):
    """随机扰动"""
    return state + torch.randn_like(state) * amplitude


def inject_difference(state, rate=0.03):
    """A1 差异源注入"""
    noise = torch.rand_like(state)
    mask = torch.zeros_like(state)
    mask[..., 0] = 1.0
    return state + rate * noise * mask


def absorb_difference(state, rate=0.03):
    """A8 差异汇吸收"""
    mask = torch.zeros_like(state)
    mask[..., -1] = 1.0
    noise = torch.rand_like(state)
    return state * (1.0 - mask * rate * 0.3) + mask * noise * rate * 0.5


def compute_pattern_persistence(history_window):
    """计算模式持续性：时间窗口内相邻时刻的余弦相似度
    
    history_window: list of states, each shape (1, length)
    """
    if len(history_window) < 2:
        return 0.0
    
    states = torch.stack(history_window, dim=0)  # (T, 1, L)
    states = states.squeeze(1)  # (T, L)
    
    # 计算相邻时刻的余弦相似度
    similarities = []
    for t in range(len(states) - 1):
        s1 = states[t].flatten()
        s2 = states[t+1].flatten()
        
        # 余弦相似度
        dot = (s1 * s2).sum()
        norm1 = s1.norm()
        norm2 = s2.norm()
        
        if norm1 > 1e-6 and norm2 > 1e-6:
            sim = dot / (norm1 * norm2)
            similarities.append(sim.item())
    
    if not similarities:
        return 0.0
    
    return np.mean(similarities)


def compute_material_turnover(history_window):
    """计算物质周转率：状态值的平均变化量
    
    高周转 = 物质在换（活结构）
    低周转 = 物质不换（死结构）
    """
    if len(history_window) < 2:
        return 0.0
    
    states = torch.stack(history_window, dim=0)
    states = states.squeeze(1)
    
    # 计算相邻时刻的变化量
    changes = (states[1:] - states[:-1]).abs().mean(dim=1)
    return changes.mean().item()


def compute_boundary_integrity(history_window):
    """计算边界完整性：梯度场的时间稳定性
    
    梯度场 = 相邻格点的差异
    """
    if len(history_window) < 2:
        return 0.0
    
    states = torch.stack(history_window, dim=0)
    states = states.squeeze(1)  # (T, L)
    
    # 计算梯度场
    grads = states[:, 1:] - states[:, :-1]  # (T, L-1)
    
    # 梯度场的时间变化
    grad_changes = (grads[1:] - grads[:-1]).abs().mean(dim=1)
    return grad_changes.mean().item()


def classify_structure(pattern_persistence, material_turnover, 
                      pattern_threshold=0.9, turnover_threshold=0.01):
    """分类结构类型
    
    返回：'alive', 'dead', 'noise'
    """
    if pattern_persistence < pattern_threshold:
        return 'noise'
    
    if material_turnover < turnover_threshold:
        return 'dead'
    
    return 'alive'


def run_stability_experiment(length=50, steps=400, window_size=16,
                             diff_rate=0.1, inject_rate=0.03,
                             absorb_rate=0.03, perturb_amp=0.02, seed=42):
    """运行稳定性观测实验"""
    torch.manual_seed(seed)
    np.random.seed(seed)
    
    state = torch.rand(1, length)
    history = [state.clone()]
    
    print(f"=" * 60)
    print(f"Exp #5: L0 Field + A1 Source + A8 Sink + A7 Stability")
    print(f"  Length: {length}")
    print(f"  Steps: {steps}")
    print(f"  Window size: {window_size}")
    print(f"  Diffusion rate: {diff_rate}")
    print(f"  Injection rate: {inject_rate}")
    print(f"  Absorption rate: {absorb_rate}")
    print(f"=" * 60)
    
    for step in range(steps):
        state = inject_difference(state, rate=inject_rate)
        state = absorb_difference(state, rate=absorb_rate)
        state = simple_diffuse(state, diff_rate)
        state = random_perturb(state, perturb_amp)
        state = state.clamp(0.0, 1.0)
        history.append(state.clone())
    
    # 计算全局稳定性指标
    print(f"\n--- A7 稳定性指标 ---")
    
    # 用最后 window_size 步计算
    final_window = history[-window_size:]
    
    pattern_persist = compute_pattern_persistence(final_window)
    turnover = compute_material_turnover(final_window)
    boundary_integrity = compute_boundary_integrity(final_window)
    
    print(f"  模式持续性: {pattern_persist:.4f}")
    print(f"  物质周转率: {turnover:.4f}")
    print(f"  边界完整性: {boundary_integrity:.4f}")
    
    # 分类结构
    structure_type = classify_structure(pattern_persist, turnover)
    frozenness = max(0, pattern_persist - turnover) if structure_type == 'dead' else 0.0
    
    print(f"  结构类型: {structure_type.upper()}")
    print(f"  冻结度: {frozenness:.4f}")
    
    # 分区域分析
    print(f"\n--- 分区域稳定性 ---")
    segments = 5
    seg_len = length // segments
    
    last_state = history[-1].squeeze(0)
    
    for i in range(segments):
        start = i * seg_len
        end = (i + 1) * seg_len if i < segments - 1 else length
        
        # 提取该区域的历史
        region_history = [h[:, start:end] for h in final_window]
        
        region_pattern = compute_pattern_persistence(region_history)
        region_turnover = compute_material_turnover(region_history)
        region_type = classify_structure(region_pattern, region_turnover)
        region_mean = last_state[start:end].mean().item()
        
        print(f"  [{start:2d}-{end:2d}]: pattern={region_pattern:.3f}, turnover={region_turnover:.4f}, type={region_type}, mean={region_mean:.3f}")
    
    # 时间演化：稳定性如何随时间变化
    print(f"\n--- 稳定性时间演化 ---")
    checkpoints = [window_size, steps // 4, steps // 2, steps * 3 // 4, steps]
    
    for step in checkpoints:
        if step < window_size:
            continue
        window = history[step-window_size:step]
        p = compute_pattern_persistence(window)
        t = compute_material_turnover(window)
        s = classify_structure(p, t)
        print(f"  Step {step:3d}: pattern={p:.3f}, turnover={t:.4f}, type={s}")
    
    # 基本统计
    history_tensor = torch.stack(history, dim=0)
    means = history_tensor.mean(dim=[1, 2])
    stds = history_tensor.std(dim=[1, 2])
    flat = history_tensor.squeeze(1)
    grads = torch.abs(flat[:, 1:] - flat[:, :-1]).mean(dim=1)
    
    print(f"\n--- 基本统计 ---")
    print(f"  初始: mean={means[0].item():.4f}, std={stds[0].item():.4f}, grad={grads[0].item():.4f}")
    print(f"  最终: mean={means[-1].item():.4f}, std={stds[-1].item():.4f}, grad={grads[-1].item():.4f}")
    
    return dict(
        pattern_persistence=pattern_persist,
        material_turnover=turnover,
        boundary_integrity=boundary_integrity,
        structure_type=structure_type,
        frozenness=frozenness,
        final_mean=means[-1].item(),
        final_std=stds[-1].item(),
        final_grad=grads[-1].item()
    )


if __name__ == "__main__":
    print(f"="*60)
    print(f"实验 #5：A7 稳定性判定")
    print(f"="*60)
    
    result = run_stability_experiment(
        length=50, steps=400, window_size=16,
        diff_rate=0.1, inject_rate=0.03,
        absorb_rate=0.03, seed=42
    )
    
    print(f"\n\n{'='*60}")
    print(f"结论")
    print(f"{'='*60}")
    print(f"")
    print(f"结构类型: {result['structure_type'].upper()}")
    print(f"模式持续性: {result['pattern_persistence']:.4f}")
    print(f"物质周转率: {result['material_turnover']:.4f}")
    print(f"边界完整性: {result['boundary_integrity']:.4f}")
    print(f"冻结度: {result['frozenness']:.4f}")
    print(f"最终梯度: {result['final_grad']:.4f}")
    print(f"")
    
    if result['structure_type'] == 'alive':
        print(f"结论：源-汇结构形成了活结构（模式持续 + 物质更换）")
        print(f"      这符合差异论的预期：结构是差异被组织起来的形态")
    elif result['structure_type'] == 'dead':
        print(f"结论：源-汇结构形成了死结构（模式持续 + 物质冻结）")
        print(f"      需要增加扰动或注入，让物质流动起来")
    else:
        print(f"结论：源-汇结构未形成稳定模式（噪声）")
        print(f"      需要调整参数，让结构有机会稳定")
    
    print(f"\n下一实验：Exp #6 — A9 升维触发 + 粗粒化映射")
