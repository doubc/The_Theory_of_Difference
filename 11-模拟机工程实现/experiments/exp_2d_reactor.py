"""
exp_2d_reactor.py — 2D 差异反应堆实验

Phase 2 实验：
- 32x32 或 64x64 网格
- 源端（左）注入差异，汇端（右）吸收差异
- 公理约束训练
- 目标：涌现空间上连通的稳定结构
"""

import sys
import os
import torch
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from layers.L0_binary_lattice import L0BinaryLattice
from acl.axioms import create_default_axioms
from acl.axiom_base import AxiomEngine
from models.local_conv_model import LocalConvModel
from engine.reactor import DifferenceReactor
from engine.trainer import AxiomTrainer


def run_2d_experiment(
    grid_size: int = 32,
    episodes: int = 30,
    steps_per_episode: int = 200,
    lr: float = 1e-3,
    channels: int = 32,
    device: str = "cpu",
    verbose: bool = True,
):
    """运行 2D 差异反应堆实验。

    Args:
        grid_size: 网格边长
        episodes: 训练 episode 数
        steps_per_episode: 每 episode 步数
        lr: 学习率
        channels: CNN 通道数
        device: 设备 (cpu/cuda)
        verbose: 是否打印详细日志

    Returns:
        训练日志列表
    """
    print("=" * 60)
    print(f"2D Difference Reactor Experiment")
    print(f"  Grid: {grid_size}x{grid_size}")
    print(f"  Episodes: {episodes}")
    print(f"  Steps/episode: {steps_per_episode}")
    print(f"  Learning rate: {lr}")
    print(f"  Channels: {channels}")
    print(f"  Device: {device}")
    print("=" * 60)

    # 1. 创建 L0 层
    layer = L0BinaryLattice(
        shape=(grid_size, grid_size),
        device=device,
        source_side="left",
        sink_side="right",
    )

    # 2. 创建公理引擎
    axioms = create_default_axioms(ascent_threshold=0.5)
    axiom_engine = AxiomEngine(axioms)

    # 3. 创建模型
    model = LocalConvModel(channels=channels, use_reaction=True).to(device)
    param_count = sum(p.numel() for p in model.parameters())
    print(f"\nModel parameters: {param_count}")

    # 4. 创建反应堆和训练器
    reactor = DifferenceReactor(model, layer, axiom_engine, device)
    trainer = AxiomTrainer(reactor, lr=lr, device=device)

    # 5. 训练
    print("\n--- Training ---")
    start_time = time.time()
    logs = trainer.train(
        episodes=episodes,
        steps_per_episode=steps_per_episode,
        log_interval=steps_per_episode // 4,
    )
    elapsed = time.time() - start_time
    print(f"\nTraining completed in {elapsed:.1f}s")

    # 6. 评估
    print("\n--- Evaluation ---")
    eval_state = layer.initial_state()
    eval_result = trainer.evaluate(eval_state, steps=300)
    print(f"  Final state mean: {eval_result['final_state_mean']:.4f}")
    print(f"  Final state std: {eval_result['final_state_std']:.4f}")
    print(f"  Unique values: {eval_result['unique_values']}")
    print(f"  Stable structures: {eval_result['stable_structures']}")
    print(f"  Avg loss: {eval_result['avg_loss']:.4f}")

    print("\n  Axiom violations:")
    for k, v in eval_result["axiom_summary"].items():
        print(f"    {k}: {v:.6f}")

    # 7. 训练趋势
    if len(logs) >= 2:
        print("\n--- Training Trend ---")
        first_loss = logs[0].avg_loss
        last_loss = logs[-1].avg_loss
        print(f"  First episode avg loss: {first_loss:.4f}")
        print(f"  Last episode avg loss: {last_loss:.4f}")
        print(f"  Loss reduction: {(1 - last_loss/max(first_loss, 1e-8))*100:.1f}%")

        first_structures = logs[0].stable_structures
        last_structures = logs[-1].stable_structures
        print(f"  First episode structures: {first_structures}")
        print(f"  Last episode structures: {last_structures}")

    # 8. 空间结构分析
    print("\n--- Spatial Analysis ---")
    final = eval_result["history"][-1].squeeze()
    diff = layer.measure_difference(eval_result["history"][-1]).squeeze()
    print(f"  Final state shape: {final.shape}")
    print(f"  Mean difference field: {diff.mean():.4f}")
    print(f"  Max difference field: {diff.max():.4f}")

    # 检测空间连通区域
    binary = (final > 0.5).float()
    active_ratio = binary.mean().item()
    print(f"  Active cell ratio: {active_ratio:.4f}")

    return logs, eval_result


if __name__ == "__main__":
    logs, result = run_2d_experiment(
        grid_size=32,
        episodes=20,
        steps_per_episode=150,
        lr=1e-3,
        channels=32,
    )
