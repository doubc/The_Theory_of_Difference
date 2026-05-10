"""
exp_3_minimal_variation.py — 实验日志 #3：A1 + A8 + A4 最小变易约束

实验目的：
    在 exp_2 源-汇结构基础上，加入 A4 最小变易约束。
    
    A4 的含义：变化有代价，系统偏好代价最小的演化路径。
    在物理类比中，这类似于最小作用量原理或惰性。
    
    核心问题：
    1. A4 会不会锁死系统？（过度惩罚变化）
    2. A4 能否帮助维持源-汇梯度？（抵抗扩散的抹平倾向）
    3. A4 与源-汇注入的平衡点在哪里？

预期：
    - A4 权重太低：无效果，系统行为同 exp_2
    - A4 权重适中：减缓扩散抹平，帮助维持梯度
    - A4 权重太高：系统冻结，无法响应源-汇注入

实验设计：
    对比三种 A4 权重：0.0（无约束）、0.3（弱约束）、1.0（强约束）
"""

import sys
import os
import torch
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from experiments.logger import ExperimentLogger


def simple_diffuse(state, diffusion_rate=0.1):
    """纯扩散：每个格点向邻居靠拢"""
    left = torch.roll(state, -1, dims=-1)
    right = torch.roll(state, 1, dims=-1)
    neighbor_avg = (left + right) / 2
    return state * (1 - diffusion_rate) + neighbor_avg * diffusion_rate


def random_perturb(state, amplitude=0.02):
    """随机扰动"""
    return state + torch.randn_like(state) * amplitude


def inject_difference(state, rate=0.03):
    """A1 差异源注入：左端持续注入"""
    noise = torch.rand_like(state)
    mask = torch.zeros_like(state)
    mask[..., 0] = 1.0
    return state + rate * noise * mask


def absorb_difference(state, rate=0.03):
    """A8 差异汇吸收：右端持续吸收"""
    mask = torch.zeros_like(state)
    mask[..., -1] = 1.0
    noise = torch.rand_like(state)
    return state * (1.0 - mask * rate * 0.3) + mask * noise * rate * 0.5


def apply_a4_constraint(state, prev_state, a4_weight=0.3):
    """A4 最小变易约束：惩罚过大的状态变化
    
    实现：将状态向 prev_state 拉回一部分，模拟"惯性"
    """
    if a4_weight <= 0:
        return state
    
    # A4 约束：状态倾向于保持不变
    # 将当前状态向上一时刻的状态拉回
    # 拉回强度由 a4_weight 控制
    pulled_back = state * (1 - a4_weight) + prev_state * a4_weight
    return pulled_back


def compute_transition_cost(state, next_state):
    """计算 A4 违背度：状态变化的平方均值"""
    delta = next_state - state
    return (delta ** 2).mean().item()


def run_with_a4(length=50, steps=200, diff_rate=0.1, inject_rate=0.03,
                absorb_rate=0.03, perturb_amp=0.02, a4_weight=0.3, seed=42):
    """运行 A1+A8+A4 实验"""
    torch.manual_seed(seed)
    np.random.seed(seed)

    state = torch.rand(1, length)
    prev_state = state.clone()
    history = [state.clone()]
    transition_costs = []

    logger = ExperimentLogger(f"exp_3_a4{a4_weight:.2f}")
    logger.start(
        params=dict(length=length, steps=steps, diff_rate=diff_rate,
                    inject_rate=inject_rate, absorb_rate=absorb_rate,
                    perturb_amp=perturb_amp, a4_weight=a4_weight, seed=seed),
        description="A1+A8+A4 最小变易约束：验证惰性是否帮助/阻碍梯度维持",
    )

    print(f"=" * 60)
    print(f"Exp #3: L0 Field + A1 Source + A8 Sink + A4 Minimal Variation")
    print(f"  Length: {length}")
    print(f"  Steps: {steps}")
    print(f"  Diffusion rate: {diff_rate}")
    print(f"  Injection rate: {inject_rate}")
    print(f"  Absorption rate: {absorb_rate}")
    print(f"  Perturbation amp: {perturb_amp}")
    print(f"  A4 weight: {a4_weight}")
    print(f"=" * 60)

    for step in range(steps):
        # 保存当前状态用于 A4 约束
        state_before_a4 = state.clone()
        
        # 标准演化流程（同 exp_2）
        state = inject_difference(state, rate=inject_rate)
        state = absorb_difference(state, rate=absorb_rate)
        state = simple_diffuse(state, diff_rate)
        state = random_perturb(state, perturb_amp)
        
        # 应用 A4 约束
        state = apply_a4_constraint(state, prev_state, a4_weight)
        
        state = state.clamp(0.0, 1.0)
        
        # 计算实际变化成本
        cost = compute_transition_cost(state_before_a4, state)
        transition_costs.append(cost)
        
        prev_state = state.clone()
        history.append(state.clone())

        if step % 16 == 0:
            logger.log_step(step, {
                "mean": round(state.mean().item(), 6),
                "std": round(state.std().item(), 6),
                "transition_cost": round(cost, 8),
            })

    history_tensor = torch.stack(history, dim=0)
    means = history_tensor.mean(dim=[1, 2])
    stds = history_tensor.std(dim=[1, 2])
    flat = history_tensor.squeeze(1)
    grads = torch.abs(flat[:, 1:] - flat[:, :-1]).mean(dim=1)

    checkpoints = [0, steps // 4, steps // 2, steps * 3 // 4, steps]
    print(f"\n{'Step':>6}  {'Mean':>8}  {'Std':>8}  {'Grad':>8}  {'TransCost':>10}")
    
    cost_idx = 0
    for i in checkpoints:
        if i > 0:
            cost_idx = min(i - 1, len(transition_costs) - 1)
        cost_val = transition_costs[cost_idx] if i > 0 else 0.0
        print(f"{i:>6}  {means[i].item():>8.4f}  {stds[i].item():>8.4f}  {grads[i].item():>8.4f}  {cost_val:>10.6f}")

    # 空间分布
    last_state = history_tensor[-1, 0, :]
    segments = 5
    seg_len = length // segments
    print(f"\n  空间分布（最终时刻，分{segments}段）：")
    segment_means = []
    for i in range(segments):
        start = i * seg_len
        end = (i + 1) * seg_len if i < segments - 1 else length
        m = last_state[start:end].mean().item()
        segment_means.append(m)
        print(f"    [{start:2d}-{end:2d}]: {m:.4f}")

    left_seg = segment_means[0]
    right_seg = segment_means[-1]
    gradient = left_seg - right_seg
    
    # 平均变化成本
    avg_cost = np.mean(transition_costs)
    
    print(f"\n--- 成长日志 #3 ---")
    print(f"  源-汇梯度: {gradient:.4f}")
    print(f"  平均变化成本: {avg_cost:.6f}")
    print(f"  最终标准差: {stds[-1].item():.4f}")
    
    if abs(gradient) > 0.03:
        print(f"  结论：A4 约束下仍能维持源-汇梯度")
        grad_type = "GRADIENT_MAINTAINED"
    else:
        print(f"  结论：A4 约束导致梯度崩溃或系统冻结")
        grad_type = "COLLAPSED_OR_FROZEN"

    logger.log_event("result", {
        "gradient_type": grad_type,
        "avg_transition_cost": round(avg_cost, 8),
        "gradient": round(gradient, 6),
    })
    logger.finish(
        final_metrics={
            "initial_grad": round(grads[0].item(), 6),
            "final_grad": round(grads[-1].item(), 6),
            "gradient": round(gradient, 6),
            "avg_cost": round(avg_cost, 8),
            "final_std": round(stds[-1].item(), 6),
        },
        conclusion=(
            f"A4={a4_weight:.2f}: 梯度={gradient:.4f}, 平均变化成本={avg_cost:.6f}。"
            f"{'A4帮助维持了梯度。' if grad_type == 'GRADIENT_MAINTAINED' else 'A4过强导致系统冻结或梯度崩塌。'}"
        ),
    )

    return dict(
        means=means, stds=stds, grads=grads,
        segment_means=segment_means, gradient=gradient,
        grad_type=grad_type, history=history_tensor,
        transition_costs=transition_costs, avg_cost=avg_cost
    )


if __name__ == "__main__":
    print(f"="*60)
    print(f"实验 #3a：A4 = 0.0（无约束，对照 exp_2）")
    print(f"="*60)
    result_a = run_with_a4(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.03, absorb_rate=0.03,
        a4_weight=0.0, seed=42
    )

    print(f"\n\n{'='*60}")
    print(f"实验 #3b：A4 = 0.3（弱约束）")
    print(f"="*60)
    result_b = run_with_a4(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.03, absorb_rate=0.03,
        a4_weight=0.3, seed=42
    )

    print(f"\n\n{'='*60}")
    print(f"实验 #3c：A4 = 0.7（强约束）")
    print(f"="*60)
    result_c = run_with_a4(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.03, absorb_rate=0.03,
        a4_weight=0.7, seed=42
    )

    print(f"\n\n{'='*60}")
    print(f"实验 #3d：A4 = 0.95（极强约束，接近冻结）")
    print(f"="*60)
    result_d = run_with_a4(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.03, absorb_rate=0.03,
        a4_weight=0.95, seed=42
    )

    print(f"\n\n{'='*60}")
    print(f"综合对比")
    print(f"{'='*60}")
    print(f"")
    print(f"{'实验':>12}  {'最终梯度':>10}  {'平均变化成本':>14}  {'最终标准差':>12}  {'结论'}")
    print(f"{'-'*12}  {'-'*10}  {'-'*14}  {'-'*12}  {'-'*20}")
    for label, res in [
        ("3a (A4=0.0)", result_a),
        ("3b (A4=0.3)", result_b),
        ("3c (A4=0.7)", result_c),
        ("3d (A4=0.95)", result_d)
    ]:
        grad = res["gradient"]
        cost = res["avg_cost"]
        std = res["stds"][-1].item()
        status = "OK" if res["grad_type"] == "GRADIENT_MAINTAINED" else "FAIL"
        print(f"{label:>12}  {grad:>10.4f}  {cost:>14.6f}  {std:>12.4f}  {status}")

    print(f"\n--- 核心发现 ---")
    print(f"")
    
    # 分析 A4 的效果
    grad_no_a4 = result_a["gradient"]
    grad_weak_a4 = result_b["gradient"]
    grad_strong_a4 = result_c["gradient"]
    grad_frozen = result_d["gradient"]
    
    cost_no_a4 = result_a["avg_cost"]
    cost_weak_a4 = result_b["avg_cost"]
    cost_strong_a4 = result_c["avg_cost"]
    cost_frozen = result_d["avg_cost"]
    
    print(f"变化成本随 A4 权重变化：")
    print(f"  A4=0.0:  {cost_no_a4:.6f}")
    print(f"  A4=0.3:  {cost_weak_a4:.6f}")
    print(f"  A4=0.7:  {cost_strong_a4:.6f}")
    print(f"  A4=0.95: {cost_frozen:.6f}")
    
    print(f"\n梯度随 A4 权重变化：")
    print(f"  A4=0.0:  {grad_no_a4:.4f}")
    print(f"  A4=0.3:  {grad_weak_a4:.4f}")
    print(f"  A4=0.7:  {grad_strong_a4:.4f}")
    print(f"  A4=0.95: {grad_frozen:.4f}")
    
    # 判断最佳 A4 权重
    gradients = [grad_no_a4, grad_weak_a4, grad_strong_a4, grad_frozen]
    best_idx = np.argmax([abs(g) for g in gradients])
    best_weights = [0.0, 0.3, 0.7, 0.95]
    
    print(f"\n最佳 A4 权重（梯度最大）：{best_weights[best_idx]}")
    
    print(f"\n下一实验：Exp #4 — 加入 A5 守恒律，追踪开放系统的流量平衡")
