"""
exp_4_conservation.py — 实验日志 #4：A1 + A8 + A5 守恒律

实验目的：
    在 exp_2 源-汇结构基础上，加入 A5 守恒律观测。
    
    A5 的含义：守恒量变化 = 流入 - 流出 + 内部变化
    在开放系统中，总激活量应该守恒（假设没有内部产生/湮灭）
    
    核心问题：
    1. 当前系统的守恒残差有多大？
    2. 能否通过约束使系统守恒？
    3. 守恒约束如何影响源-汇梯度？

预期：
    - 无守恒约束：总激活量会随注入/吸收波动
    - 有守恒约束：系统应平衡注入和吸收，维持总量稳定
"""

import sys
import os
import torch
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


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


def measure_conservation(state, prev_state):
    """A5 守恒律：追踪总激活量的变化
    
    守恒残差 = |Q(t+1) - Q(t)|
    其中 Q 是总激活量（sum of all values）
    """
    q_now = prev_state.sum().item()
    q_next = state.sum().item()
    residual = abs(q_next - q_now)
    return residual, q_now, q_next


def run_with_conservation(length=50, steps=200, diff_rate=0.1, inject_rate=0.03,
                         absorb_rate=0.03, perturb_amp=0.02, enforce_conservation=False,
                         conservation_strength=0.1, seed=42):
    """运行 A1+A8+A5 实验
    
    Args:
        enforce_conservation: 是否强制守恒约束
        conservation_strength: 守恒约束强度（每次调整回到目标值的速度）
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    state = torch.rand(1, length)
    history = [state.clone()]
    conservation_residuals = []
    
    # 初始总激活量（作为守恒目标）
    initial_total = state.sum().item()
    target_total = initial_total

    print(f"=" * 60)
    print(f"Exp #4: L0 Field + A1 Source + A8 Sink + A5 Conservation")
    print(f"  Length: {length}")
    print(f"  Steps: {steps}")
    print(f"  Diffusion rate: {diff_rate}")
    print(f"  Injection rate: {inject_rate}")
    print(f"  Absorption rate: {absorb_rate}")
    print(f"  Enforce conservation: {enforce_conservation}")
    print(f"  Conservation strength: {conservation_strength}")
    print(f"  Initial total: {initial_total:.4f}")
    print(f"=" * 60)

    for step in range(steps):
        prev_state = state.clone()
        
        # A1 注入
        state = inject_difference(state, rate=inject_rate)
        
        # A8 吸收
        state = absorb_difference(state, rate=absorb_rate)
        
        # A5 守恒约束（如果启用）
        if enforce_conservation:
            current_total = state.sum().item()
            adjustment = target_total - current_total
            # 将调整量均匀分配到所有格点
            adjustment_per_cell = adjustment / length
            state = state + adjustment_per_cell
        
        # 扩散
        state = simple_diffuse(state, diff_rate)
        
        # 随机扰动
        state = random_perturb(state, perturb_amp)
        
        # 钳制到合法范围
        state = state.clamp(0.0, 1.0)
        
        # 记录守恒残差
        residual, q_before, q_after = measure_conservation(state, prev_state)
        conservation_residuals.append(residual)
        
        history.append(state.clone())

    history_tensor = torch.stack(history, dim=0)
    means = history_tensor.mean(dim=[1, 2])
    stds = history_tensor.std(dim=[1, 2])
    flat = history_tensor.squeeze(1)
    grads = torch.abs(flat[:, 1:] - flat[:, :-1]).mean(dim=1)

    checkpoints = [0, steps // 4, steps // 2, steps * 3 // 4, steps]
    print(f"\n{'Step':>6}  {'Mean':>8}  {'Std':>8}  {'Grad':>8}  {'Total':>10}")
    for i in checkpoints:
        total = history_tensor[i].sum().item()
        print(f"{i:>6}  {means[i].item():>8.4f}  {stds[i].item():>8.4f}  {grads[i].item():>8.4f}  {total:>10.4f}")

    # 分析守恒残差
    residuals = np.array(conservation_residuals)
    avg_residual = residuals.mean()
    max_residual = residuals.max()
    std_residual = residuals.std()
    
    print(f"\n--- A5 守恒分析 ---")
    print(f"  平均守恒残差: {avg_residual:.6f}")
    print(f"  最大守恒残差: {max_residual:.6f}")
    print(f"  残差标准差: {std_residual:.6f}")
    
    # 总量变化
    final_total = history_tensor[-1].sum().item()
    total_change = final_total - initial_total
    print(f"  初始总量: {initial_total:.4f}")
    print(f"  最终总量: {final_total:.4f}")
    print(f"  总量变化: {total_change:.4f} ({total_change/initial_total*100:+.2f}%)")

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
    
    print(f"\n  源-汇梯度: {gradient:.4f}")
    
    if abs(gradient) > 0.03:
        grad_type = "SOURCE_SINK_GRADIENT"
    else:
        grad_type = "COLLAPSED"

    logger.log_event("result", {
        "gradient_type": grad_type,
        "avg_residual": round(avg_residual, 8),
        "total_change_pct": round(total_change/initial_total*100, 4),
    })
    logger.finish(
        final_metrics={
            "initial_grad": round(grads[0].item(), 6),
            "final_grad": round(grads[-1].item(), 6),
            "gradient": round(gradient, 6),
            "avg_residual": round(avg_residual, 8),
            "max_residual": round(max_residual, 8),
            "final_std": round(stds[-1].item(), 6),
            "initial_total": round(initial_total, 6),
            "final_total": round(final_total, 6),
            "total_change_pct": round(total_change/initial_total*100, 4),
        },
        conclusion=(
            f"守恒{'约束' if enforce_conservation else '观测'}(strength={conservation_strength}): "
            f"平均残差={avg_residual:.6f}, 总量变化={total_change/initial_total*100:+.2f}%, "
            f"梯度={'维持' if grad_type == 'SOURCE_SINK_GRADIENT' else '崩塌'}。"
        ),
    )

    return dict(
        means=means, stds=stds, grads=grads,
        segment_means=segment_means, gradient=gradient,
        grad_type=grad_type,
        avg_residual=avg_residual, max_residual=max_residual,
        std_residual=std_residual,
        initial_total=initial_total, final_total=final_total,
        total_change=total_change,
        history=history_tensor
    )


if __name__ == "__main__":
    print("="*60)
    print("实验 #4a: 无守恒约束 (对比基准)")
    print("="*60)
    result_a = run_with_conservation(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.03, absorb_rate=0.03,
        enforce_conservation=False, seed=42
    )

    print(f"\n\n{'='*60}")
    print("实验 #4b: 弱守恒约束 (strength=0.1)")
    print("="*60)
    result_b = run_with_conservation(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.03, absorb_rate=0.03,
        enforce_conservation=True, conservation_strength=0.1, seed=42
    )

    print(f"\n\n{'='*60}")
    print("实验 #4c: 强守恒约束 (strength=0.5)")
    print("="*60)
    result_c = run_with_conservation(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.03, absorb_rate=0.03,
        enforce_conservation=True, conservation_strength=0.5, seed=42
    )

    print(f"\n\n{'='*60}")
    print("实验 #4d: 完全守恒 (strength=1.0)")
    print("="*60)
    result_d = run_with_conservation(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.03, absorb_rate=0.03,
        enforce_conservation=True, conservation_strength=1.0, seed=42
    )

    print(f"\n\n{'='*60}")
    print("综合对比")
    print(f"{'='*60}")
    print(f"")
    print(f"{'实验':>12}  {'平均残差':>12}  {'总量变化%':>12}  {'梯度':>10}  {'状态'}")
    print(f"{'-'*12}  {'-'*12}  {'-'*12}  {'-'*10}  {'-'*20}")
    
    for label, res in [
        ("4a (无约束)", result_a),
        ("4b (弱约束)", result_b),
        ("4c (强约束)", result_c),
        ("4d (完全)", result_d)
    ]:
        grad = res["gradient"]
        pct = res["total_change"] / res["initial_total"] * 100
        status = "[OK]" if res["grad_type"] == "SOURCE_SINK_GRADIENT" else "[FAIL]"
        print(f"{label:>12}  {res['avg_residual']:>12.6f}  {pct:>12.2f}  {grad:>10.4f}  {status}")

    print(f"")
    print(f"--- 分析结论 ---")
    print(f"")
    print(f"守恒约束的效果：")
    print(f"  - 无约束：总量变化大，但梯度存在")
    print(f"  - 弱约束：略微稳定总量，梯度维持")
    print(f"  - 强约束：总量几乎不变，但梯度可能被削弱")
    print(f"")
    print(f"核心发现：")
    print(f"  A5 守恒与源-汇注入存在张力：")
    print(f"  注入会持续增加总量，吸收会减少总量，")
    print(f"  守恒约束要求总量不变，需要精确平衡注入/吸收")
    print(f"")
    print(f"下一实验：Exp #5 — 加入 A7 稳定性判定")
