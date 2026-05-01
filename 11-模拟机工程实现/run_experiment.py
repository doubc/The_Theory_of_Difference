"""
run_experiment.py — 差异论模拟机实验入口

M1：差异反应堆实验
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import torch


def run_1d():
    """运行 1D 差异反应堆实验"""
    from experiments.exp_1d_reactor import run_1d_experiment
    return run_1d_experiment(
        length=50,
        episodes=30,
        steps_per_episode=100,
        lr=1e-3,
    )


def run_2d():
    """运行 2D 差异反应堆实验"""
    from experiments.exp_2d_reactor import run_2d_experiment
    return run_2d_experiment(
        grid_size=32,
        episodes=20,
        steps_per_episode=150,
        lr=1e-3,
        channels=32,
    )


def run_smoke_test():
    """冒烟测试：快速验证所有模块可运行"""
    print("=" * 50)
    print("Smoke Test: M1 Components")
    print("=" * 50)

    # 1. 检查 PyTorch
    print(f"\nPyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    # 2. 检查模型
    from models.local_conv_model import LocalConvModel
    model = LocalConvModel(channels=16, use_reaction=True)
    params = sum(p.numel() for p in model.parameters())
    print(f"\n[OK] LocalConvModel: {params} parameters")

    # 3. 检查 L0 层
    from layers.L0_binary_lattice import L0BinaryLattice
    layer = L0BinaryLattice(shape=(8, 8))
    state = layer.initial_state()
    print(f"[OK] L0BinaryLattice: state shape = {state.shape}")

    # 4. 检查公理引擎
    from acl.axioms import create_default_axioms
    from acl.axiom_base import AxiomEngine
    axioms = create_default_axioms()
    engine = AxiomEngine(axioms)
    print(f"[OK] AxiomEngine: {len(axioms)} axioms")

    # 5. 检查反应堆
    from engine.reactor import DifferenceReactor
    reactor = DifferenceReactor(model, layer, engine)
    next_state, loss, report = reactor.step(state)
    print(f"[OK] DifferenceReactor: loss = {loss.item():.4f}")

    # 6. 检查训练器
    from engine.trainer import AxiomTrainer
    trainer = AxiomTrainer(reactor, lr=1e-3)
    result = trainer.train_step(state)
    print(f"[OK] AxiomTrainer: loss = {result['loss']:.4f}")

    # 7. 检查 WorldEngine
    from engine.world_engine import WorldEngine
    world = WorldEngine(model, layer, engine, lr=1e-3)
    eval_result = world.evaluate(steps=20)
    print(f"[OK] WorldEngine: eval loss = {eval_result['avg_loss']:.4f}")

    print("\n" + "=" * 50)
    print("All M1 components ready!")
    print("=" * 50)
    print("\nRun full experiments:")
    print("  python run_experiment.py 1d    # 1D reactor")
    print("  python run_experiment.py 2d    # 2D reactor")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run_experiment.py test   # Smoke test")
        print("  python run_experiment.py 1d     # 1D experiment")
        print("  python run_experiment.py 2d     # 2D experiment")
        print("\nRunning smoke test by default...\n")
        run_smoke_test()
        return

    mode = sys.argv[1].lower()

    if mode == "test":
        run_smoke_test()
    elif mode == "1d":
        run_1d()
    elif mode == "2d":
        run_2d()
    else:
        print(f"Unknown mode: {mode}")
        print("Use: test, 1d, or 2d")


if __name__ == '__main__':
    main()