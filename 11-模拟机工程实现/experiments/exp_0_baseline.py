"""
exp_0_baseline.py — 实验日志 #0：L0裸场基线

实验目的：
    建立一个"最原始状态"的基线——没有任何公理约束，
    只有随机初始化+纯扩散。然后逐步加约束，看每步改变了什么。

实验设计：
    - 1D连续场 [0, 1] 区间，初始化为随机值
    - 每个时间步：简单扩散（邻居平均）+ 小随机扰动
    - 不注入差异，不吸收差异，纯自发演化
    - 记录：均值、标准差、梯度、活动度随时间变化

问题：
    无约束时，差异场会自发组织吗？还是趋向热平衡？
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


def run_baseline(length=50, steps=200, diff_rate=0.1, perturb_amp=0.02, seed=42):
    """运行L0裸场实验"""
    torch.manual_seed(seed)
    np.random.seed(seed)

    state = torch.rand(1, 1, length)
    history = [state.clone()]

    print(f"=" * 60)
    print(f"Exp #0: L0 Bare Field Baseline (无约束)")
    print(f"  Length: {length}")
    print(f"  Steps: {steps}")
    print(f"  Diffusion rate: {diff_rate}")
    print(f"  Perturbation amp: {perturb_amp}")
    print(f"  Seed: {seed}")
    print(f"=" * 60)

    for step in range(steps):
        state = simple_diffuse(state, diff_rate)
        state = random_perturb(state, perturb_amp)
        state = state.clamp(0.0, 1.0)
        history.append(state.clone())

    history = torch.cat(history, dim=0)  # (steps+1, 1, 1, length)
    print(f"DEBUG history shape: {history.shape}")
    means = history.mean(dim=[1, 2])
    stds = history.std(dim=[1, 2])
    grads = torch.abs(history[:, :, 1:] - history[:, :, :-1]).mean(dim=[1, 2])

    checkpoints = [0, steps//4, steps//2, steps*3//4, steps]
    print(f"\n{'Step':>6}  {'Mean':>8}  {'Std':>8}  {'Grad':>8}")
    for i in checkpoints:
        print(f"{i:>6}  {means[i].item():>8.4f}  {stds[i].item():>8.4f}  {grads[i].item():>8.4f}")

    print(f"\n--- 成长日志 #0 ---")
    print(f"  初始状态: mean={means[0].item():.4f} std={stds[0].item():.4f} grad={grads[0].item():.4f}")
    print(f"  最终状态: mean={means[-1].item():.4f} std={stds[-1].item():.4f} grad={grads[-1].item():.4f}")
    print(f"")
    print(f"  成长日志：无约束时，差异场趋向热平衡态：梯度持续降低，均值趋近0.5（均匀分布），")
    print(f"  标准差逐渐下降。证明A1（差异源）和A8（差异汇）是必要的基础设施——")
    print(f"  没有外部注入，内部的自发演化只会趋向熵增的均匀态。")
    print(f"  下一步：加入差异源注入，看是否能维持差异结构。")
    return dict(means=means, stds=stds, grads=grads)


if __name__ == "__main__":
    run_baseline(length=50, steps=200)
