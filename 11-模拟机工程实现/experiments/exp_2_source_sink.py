"""
exp_2_source_sink.py — 实验日志 #2：A1 + A8 源-汇联合结构

实验目的：
    在 exp_1 基础上加入 A8 差异汇（吸收端），形成完整的源-汇梯度结构。
    对比：
        exp_0：无注入无吸收 → 趋向热平衡（梯度崩溃）
        exp_1：只有注入 → 梯度仍崩溃（扩散双向抹平）
        exp_2（本实验）：注入 + 吸收 → 能否形成稳定梯度？

核心假设：
    差异从源端注入，被扩散推向整个空间，同时在汇端被吸收。
    如果源注入速率 > 汇吸收速率，应该能维持从源到汇的梯度。
    如果两者平衡，应该形成稳定的梯度带（差异的中间态）。
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
    """A1 差异源注入：左端持续 +1"""
    noise = torch.rand_like(state)
    mask = torch.zeros_like(state)
    mask[..., 0] = 1.0
    return state + rate * noise * mask


def absorb_difference(state, rate=0.03):
    """A8 差异汇吸收：右端持续 -1（驱向 0）"""
    mask = torch.zeros_like(state)
    mask[..., -1] = 1.0
    # 吸收：把右端值拉向 0（通过乘以小于1的因子）
    absorb_factor = 1.0 - rate * 0.5
    # 更简单：直接把右端加点扰动推向任意方向
    noise = torch.rand_like(state)
    return state * (1.0 - mask * rate * 0.3) + mask * noise * rate * 0.5


def run_source_sink(length=50, steps=200, diff_rate=0.1, inject_rate=0.03,
                    absorb_rate=0.03, perturb_amp=0.02, seed=42):
    """运行 A1+A8 源-汇实验"""
    torch.manual_seed(seed)
    np.random.seed(seed)

    state = torch.rand(1, length)
    history = [state.clone()]

    logger = ExperimentLogger(f"exp_2_src{inject_rate:.2f}_snk{absorb_rate:.2f}")
    logger.start(
        params=dict(length=length, steps=steps, diff_rate=diff_rate,
                    inject_rate=inject_rate, absorb_rate=absorb_rate,
                    perturb_amp=perturb_amp, seed=seed),
        description="A1+A8 源-汇联合结构：验证扩散能否形成稳定梯度",
    )

    print(f"=" * 60)
    print(f"Exp #2: L0 Field + A1 Source + A8 Sink")
    print(f"  Length: {length}")
    print(f"  Steps: {steps}")
    print(f"  Diffusion rate: {diff_rate}")
    print(f"  Injection rate: {inject_rate}")
    print(f"  Absorption rate: {absorb_rate}")
    print(f"  Perturbation amp: {perturb_amp}")
    print(f"=" * 60)

    for step in range(steps):
        state = inject_difference(state, rate=inject_rate)
        state = absorb_difference(state, rate=absorb_rate)
        state = simple_diffuse(state, diff_rate)
        state = random_perturb(state, perturb_amp)
        state = state.clamp(0.0, 1.0)
        history.append(state.clone())

        if step % 16 == 0:
            logger.log_step(step, {
                "mean": round(state.mean().item(), 6),
                "std": round(state.std().item(), 6),
            })

    history_tensor = torch.stack(history, dim=0)  # (steps+1, 1, length)
    means = history_tensor.mean(dim=[1, 2])  # (steps+1,)
    stds = history_tensor.std(dim=[1, 2])  # (steps+1,)
    # 梯度：先 squeeze batch dim，再做邻居差分
    flat = history_tensor.squeeze(1)  # (steps+1, length)
    grads = torch.abs(flat[:, 1:] - flat[:, :-1]).mean(dim=1)  # (steps+1,)

    checkpoints = [0, steps // 4, steps // 2, steps * 3 // 4, steps]
    print(f"\n{'Step':>6}  {'Mean':>8}  {'Std':>8}  {'Grad':>8}")
    for i in checkpoints:
        print(f"{i:>6}  {means[i].item():>8.4f}  {stds[i].item():>8.4f}  {grads[i].item():>8.4f}")

    print(f"\n--- 成长日志 #2 ---")
    print(f"  初始状态: mean={means[0].item():.4f} std={stds[0].item():.4f} grad={grads[0].item():.4f}")
    print(f"  最终状态: mean={means[-1].item():.4f} std={stds[-1].item():.4f} grad={grads[-1].item():.4f}")
    print(f"")

    # 空间分布
    last_state = history_tensor[-1, 0, :]
    segments = 5
    seg_len = length // segments
    print(f"  空间分布（最终时刻，分{segments}段）：")
    segment_means = []
    for i in range(segments):
        start = i * seg_len
        end = (i + 1) * seg_len if i < segments - 1 else length
        m = last_state[start:end].mean().item()
        segment_means.append(m)
        print(f"    [{start:2d}-{end:2d}]: {m:.4f}")
    
    # 梯度方向
    left_seg = segment_means[0]
    right_seg = segment_means[-1]
    gradient = left_seg - right_seg
    print(f"")
    print(f"  源-汇梯度: {gradient:.4f}")
    
    if abs(gradient) > 0.03:
        print(f"  结论：A1+A8 形成了稳定的空间梯度（A1 差异源 + A8 差异汇有效）")
        grad_type = "SOURCE_SINK_GRADIENT"
    else:
        print(f"  结论：源-汇注入无法建立稳定梯度，仍被扩散抹平")
        grad_type = "COLLAPSED"

    # 时间演化：梯度是否持续
    print(f"")
    print(f"  梯度时间演化：")
    for i in checkpoints:
        g = grads[i].item()
        print(f"    Step {i}: grad={g:.4f}")

    logger.log_event("result", {
        "gradient_type": grad_type,
        "source_to_sink_gradient": round(gradient, 6),
    })
    logger.finish(
        final_metrics={
            "initial_grad": round(grads[0].item(), 6),
            "final_grad": round(grads[-1].item(), 6),
            "gradient": round(gradient, 6),
            "final_std": round(stds[-1].item(), 6),
            "segment_means": [round(m, 6) for m in segment_means],
        },
        conclusion=(
            f"注入{inject_rate:.2f}/吸收{absorb_rate:.2f}时，形成"
            f"{'稳定' if grad_type == 'SOURCE_SINK_GRADIENT' else '崩塌'}梯度({gradient:.4f})。"
            f"源-汇需要速率差才能维持梯度场。"
        ),
    )

    return dict(
        means=means, stds=stds, grads=grads,
        segment_means=segment_means, gradient=gradient,
        grad_type=grad_type, history=history_tensor
    )


if __name__ == "__main__":
    print(f"="*60)
    print(f"实验 #2a：注入速率 = 吸收速率（平衡）")
    print(f"="*60)
    result_a = run_source_sink(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.03, absorb_rate=0.03, seed=42
    )

    print(f"\n\n{'='*60}")
    print(f"实验 #2b：注入速率 > 吸收速率（源强）")
    print(f"="*60)
    result_b = run_source_sink(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.05, absorb_rate=0.02, seed=42
    )

    print(f"\n\n{'='*60}")
    print(f"实验 #2c：注入速率 < 吸收速率（汇强）")
    print(f"="*60)
    result_c = run_source_sink(
        length=50, steps=200, diff_rate=0.1,
        inject_rate=0.02, absorb_rate=0.05, seed=42
    )

    print(f"\n\n{'='*60}")
    print(f"综合对比")
    print(f"{'='*60}")
    print(f"")
    print(f"{'实验':>10}  {'最终梯度':>12}  {'最终标准差':>14}  {'结论'}")
    print(f"{'-'*10}  {'-'*12}  {'-'*14}  {'-'*20}")
    for label, res in [("2a (平衡)", result_a), ("2b (源强)", result_b), ("2c (汇强)", result_c)]:
        grad = res["grads"][-1].item()
        std = res["stds"][-1].item()
        print(f"{label:>10}  {res['gradient']:>12.4f}  {std:>14.4f}  {'[OK]' if res['grad_type'] == 'SOURCE_SINK_GRADIENT' else '[FAIL]'} {res['grad_type']}")

    print(f"")
    print(f"下一实验：Exp #3 — 加入 A4 最小变易约束，看模型能否学会维持梯度结构")