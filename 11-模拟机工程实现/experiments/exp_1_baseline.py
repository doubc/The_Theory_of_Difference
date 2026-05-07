"""
exp_1_baseline.py — 实验日志 #1：加入差异源注入

实验目的：
    在基线（exp_0）基础上加入 A1 差异源注入，看差异场是否能维持非平衡态。
    对比 exp_0：无注入 → 趋向热平衡；有注入 → ？

实验设计（对比 exp_0）：
    - 完全相同的 1D 格点、相同随机种子、相同扩散率
    - 唯一区别：每个时间步在左端注入差异（source model）
    - 记录：均值、标准差、梯度、活动度随时间变化

核心问题：
    注入的差异能否形成梯度并维持结构？还是也被扩散抹平？
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


def inject_difference(state, rate=0.03, source_mode="left"):
    """A1 差异源注入：模拟"太阳"持续发光
    
    source_mode:
        "left"      — 左端（index 0）注入，模拟从左向右的差异流
        "random"    — 随机位置注入
        "gradient"   — 在特定位置形成梯度注入
    """
    if source_mode == "left":
        # 左端点 +1 注入
        noise = torch.rand_like(state)
        mask = torch.zeros_like(state)
        mask[..., 0] = 1.0
        return state + rate * noise * mask
    elif source_mode == "random":
        noise = torch.rand_like(state)
        prob = torch.rand_like(state)
        mask = (prob < rate).float()
        return state + noise * mask
    else:
        return state


def run_with_injection(length=50, steps=200, diff_rate=0.1, inject_rate=0.03,
                       perturb_amp=0.02, seed=42, source_mode="left"):
    """运行 A1 差异源实验"""
    torch.manual_seed(seed)
    np.random.seed(seed)

    state = torch.rand(1, 1, length)
    history = [state.clone()]

    print(f"=" * 60)
    print(f"Exp #1: L0 Field + A1 Difference Injection")
    print(f"  Length: {length}")
    print(f"  Steps: {steps}")
    print(f"  Diffusion rate: {diff_rate}")
    print(f"  Injection rate: {inject_rate}")
    print(f"  Injection mode: {source_mode}")
    print(f"  Perturbation amp: {perturb_amp}")
    print(f"  Seed: {seed}")
    print(f"=" * 60)

    for step in range(steps):
        state = inject_difference(state, rate=inject_rate, source_mode=source_mode)
        state = simple_diffuse(state, diff_rate)
        state = random_perturb(state, perturb_amp)
        state = state.clamp(0.0, 1.0)
        history.append(state.clone())

    history_tensor = torch.cat(history, dim=0)  # (steps+1, 1, 1, length)
    means = history_tensor.mean(dim=[1, 2])
    stds = history_tensor.std(dim=[1, 2])
    grads = torch.abs(history_tensor[:, :, 1:] - history_tensor[:, :, :-1]).mean(dim=[1, 2])

    checkpoints = [0, steps // 4, steps // 2, steps * 3 // 4, steps]
    print(f"\n{'Step':>6}  {'Mean':>8}  {'Std':>8}  {'Grad':>8}")
    for i in checkpoints:
        print(f"{i:>6}  {means[i].item():>8.4f}  {stds[i].item():>8.4f}  {grads[i].item():>8.4f}")

    print(f"\n--- 成长日志 #1 ---")
    print(f"  初始状态: mean={means[0].item():.4f} std={stds[0].item():.4f} grad={grads[0].item():.4f}")
    print(f"  最终状态: mean={means[-1].item():.4f} std={stds[-1].item():.4f} grad={grads[-1].item():.4f}")
    print(f"")

    # 对比 exp_0 的结论
    print(f"  与 exp_0（无注入）对比：")
    # exp_0 基线数据（已知）
    exp0_grad_initial = 0.38
    exp0_grad_final = 0.05
    grad_change = grads[-1].item() - grads[0].item()
    if grad_change > 0.0:
        print(f"  梯度变化: {grad_change:.4f} (上升，与 exp_0 下降相反)")
    else:
        print(f"  梯度变化: {grad_change:.4f} (下降，但幅度小于 exp_0)")
    
    std_change = stds[-1].item() - stds[0].item()
    if std_change < 0:
        print(f"  标准差变化: {std_change:.4f} (下降)")
    else:
        print(f"  标准差变化: {std_change:.4f} (上升)")

    # 计算源端 vs 汇端的差异分布
    last_state = history_tensor[-1, 0, :]  # (length,)
    left_mean = last_state[:5].mean().item()
    right_mean = last_state[-5:].mean().item()
    print(f"")
    print(f"  空间分布（最终时刻）：")
    print(f"    源端均值（左5点）: {left_mean:.4f}")
    print(f"    汇端均值（右5点）: {right_mean:.4f}")
    print(f"    梯度: {left_mean - right_mean:.4f}")
    if abs(left_mean - right_mean) > 0.05:
        print(f"    结论：注入形成了稳定梯度场（A1 差异源有效）")
    else:
        print(f"    结论：注入无法维持梯度，仍被扩散抹平")

    print(f"")
    print(f"  下一步：加入 A8 差异汇（吸收端），看能否形成稳定的源-汇梯度结构")

    return dict(means=means, stds=stds, grads=grads,
                left_mean=left_mean, right_mean=right_mean,
                history=history_tensor)


if __name__ == "__main__":
    # 基础实验
    run_with_injection(length=50, steps=200, inject_rate=0.03, seed=42)
    
    print(f"\n\n{'='*60}")
    print(f"补充实验：不同注入速率")
    print(f"{'='*60}\n")

    for rate in [0.01, 0.05, 0.10]:
        print(f"--- Injection rate = {rate} ---")
        run_with_injection(length=50, steps=200, inject_rate=rate, seed=42)
        print()