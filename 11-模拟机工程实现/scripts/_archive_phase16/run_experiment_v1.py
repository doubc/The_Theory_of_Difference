"""
run_experiment.py — 差异论模拟机实验入口

M1：差异反应堆实验
M2：稳定结构验证 + 粗粒化映射
"""

import sys
import os
import argparse

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import torch


def run_1d(args=None):
    """运行 1D 差异反应堆实验"""
    from experiments.exp_1d_reactor import run_1d_experiment
    return run_1d_experiment(
        length=50,
        episodes=30,
        steps_per_episode=100,
        lr=1e-3,
    )


def run_2d(args=None):
    """运行 2D 差异反应堆实验"""
    from experiments.exp_2d_reactor import run_2d_experiment
    grid_size = getattr(args, 'size', 32) if args else 32
    episodes = getattr(args, 'episodes', 20) if args else 20
    return run_2d_experiment(
        grid_size=grid_size,
        episodes=episodes,
        steps_per_episode=150,
        lr=1e-3,
        channels=32,
    )


def run_smoke_test(args=None):
    """冒烟测试：快速验证所有模块可运行"""
    from engine.experiment_logger import ExperimentLogger

    logger = ExperimentLogger(PROJECT_ROOT)
    logger.start("smoke_test", {"type": "smoke"})

    print("=" * 50)
    print("Smoke Test: M1 + M2 Components")
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

    # 8. M2: 检查验证器
    from validators.structure_validator import StructureValidator
    validator = StructureValidator()
    print(f"[OK] StructureValidator: 5 criteria ready")

    # 9. M2: 检查粗粒化
    from layers.L1_abstract_layer import L1AbstractLayer
    from layers.coarse_grain import coarse_grain_state
    l1 = L1AbstractLayer(block_size=4, l1_shape=(2, 2))
    l1_state = l1.initial_state()
    print(f"[OK] L1AbstractLayer: state shape = {l1_state.shape}")

    # 10. M2: 检查实验日志
    from engine.experiment_logger import ExperimentLogger
    print(f"[OK] ExperimentLogger: ready")

    print("\n" + "=" * 50)
    print("All M1 + M2 components ready!")
    print("=" * 50)
    print("\nRun full experiments:")
    print("  python run_experiment.py 1d                  # 1D reactor")
    print("  python run_experiment.py 2d                  # 2D reactor (32x32)")
    print("  python run_experiment.py 2d --size 64        # 2D reactor (64x64)")
    print("  python run_experiment.py validate             # Run structure validator")
    print("  python run_experiment.py coarse-grain         # Test coarse-graining")

    # 记录日志
    logger.log_step(0, eval_result['avg_loss'], {})
    json_path, doc_path = logger.finish(
        total_steps=20,
        final_loss=eval_result['avg_loss'],
        structures_detected=0,
    )
    print(f"\n[LOG] JSON: {json_path}")
    print(f"[LOG] Doc:  {doc_path}")


def run_validate(args=None):
    """运行稳定结构验证器"""
    from engine.experiment_logger import ExperimentLogger
    from layers.L0_binary_lattice import L0BinaryLattice
    from models.local_conv_model import LocalConvModel
    from acl.axioms import create_default_axioms
    from acl.axiom_base import AxiomEngine
    from engine.reactor import DifferenceReactor
    from validators.structure_validator import StructureValidator

    logger = ExperimentLogger(PROJECT_ROOT)
    grid_size = getattr(args, 'size', 32) if args else 32
    steps = getattr(args, 'steps', 200) if args else 200

    logger.start("validate", {
        "grid_size": grid_size,
        "steps": steps,
    })

    print("=" * 50)
    print(f"Structure Validation: {grid_size}x{grid_size}, {steps} steps")
    print("=" * 50)

    # 初始化组件
    layer = L0BinaryLattice(shape=(grid_size, grid_size))
    model = LocalConvModel(channels=32, use_reaction=True)
    axioms = create_default_axioms()
    engine = AxiomEngine(axioms)
    reactor = DifferenceReactor(model, layer, engine)

    # 运行演化，收集历史
    state = layer.initial_state()
    history = [state.clone()]

    print(f"\nRunning {steps} steps...")
    for step in range(steps):
        state, loss, report = reactor.step(state, history)
        history.append(state.clone())
        logger.log_step(step, loss.item(), report)

        if (step + 1) % 50 == 0:
            print(f"  Step {step+1}/{steps}, loss={loss.item():.4f}")

    # 检测稳定结构
    print("\nDetecting stable structures...")
    structures = layer.detect_stable_structures(history)
    print(f"Found {len(structures)} structure(s)")

    # 验证
    validator = StructureValidator()
    if structures:
        report = validator.validate(structures, history)
        print(f"\n{report.summary}")

        validation_result = {
            "total": report.total_structures,
            "passed": report.passed_structures,
            "lifetime": report.lifetime_passed,
            "boundary": report.boundary_passed,
            "closure": report.closure_passed,
            "turnover": report.turnover_passed,
            "interaction": report.interaction_detected,
        }
    else:
        print("\nNo structures to validate.")
        validation_result = {"total": 0, "passed": 0}

    # 记录日志
    final_loss = logger.axiom_trends.get("A2_discreteness", [0])[-1] if logger.axiom_trends.get("A2_discreteness") else 0
    json_path, doc_path = logger.finish(
        total_steps=steps,
        final_loss=final_loss,
        structures_detected=len(structures),
        validation_result=validation_result,
    )
    print(f"\n[LOG] JSON: {json_path}")
    print(f"[LOG] Doc:  {doc_path}")


def run_coarse_grain(args=None):
    """测试粗粒化映射"""
    from engine.experiment_logger import ExperimentLogger
    from layers.L0_binary_lattice import L0BinaryLattice
    from layers.coarse_grain import coarse_grain_state
    from models.local_conv_model import LocalConvModel
    from acl.axioms import create_default_axioms
    from acl.axiom_base import AxiomEngine
    from engine.reactor import DifferenceReactor

    logger = ExperimentLogger(PROJECT_ROOT)
    grid_size = getattr(args, 'size', 32) if args else 32
    steps = getattr(args, 'steps', 300) if args else 300

    logger.start("coarse_grain", {
        "grid_size": grid_size,
        "steps": steps,
        "block_size": 4,
    })

    print("=" * 50)
    print(f"Coarse-Graining Test: {grid_size}x{grid_size}, {steps} steps")
    print("=" * 50)

    # 初始化组件
    layer = L0BinaryLattice(shape=(grid_size, grid_size))
    model = LocalConvModel(channels=32, use_reaction=True)
    axioms = create_default_axioms()
    engine = AxiomEngine(axioms)
    reactor = DifferenceReactor(model, layer, engine)

    # 运行演化
    state = layer.initial_state()
    history = [state.clone()]

    print(f"\nRunning {steps} steps to build stable structures...")
    for step in range(steps):
        state, loss, report = reactor.step(state, history)
        history.append(state.clone())
        logger.log_step(step, loss.item(), report)

        if (step + 1) % 100 == 0:
            print(f"  Step {step+1}/{steps}, loss={loss.item():.4f}")

    # 检测稳定结构
    print("\nDetecting stable structures...")
    structures = layer.detect_stable_structures(history)
    print(f"Found {len(structures)} structure(s)")

    if structures:
        # 测试粗粒化
        struct = structures[0]
        print(f"\nCoarse-graining structure (mask sum={struct.mask.sum().item():.0f})...")

        l1_state, l1_mask = coarse_grain_state(state, struct.mask, block_size=4)
        print(f"L0 state shape: {state.shape}")
        print(f"L1 state shape: {l1_state.shape}")
        print(f"L1 mask shape:  {l1_mask.shape}")
        print(f"L1 state range: [{l1_state.min().item():.4f}, {l1_state.max().item():.4f}]")
        print(f"L1 active blocks: {l1_mask.sum().item():.0f}")

        # 测试 L0.coarse_grain()
        l1_layer = layer.coarse_grain(structures)
        if l1_layer is not None:
            print(f"\n[OK] L0.coarse_grain() returned: {l1_layer.name}")
            print(f"     L1 initial state shape: {l1_layer.initial_state().shape}")

            # 测试 L1 的基本操作
            l1_s = l1_layer.initial_state()
            diff = l1_layer.measure_difference(l1_s)
            inv = l1_layer.measure_invariant(l1_s)
            print(f"     L1 measure_difference shape: {diff.shape}")
            print(f"     L1 measure_invariant shape: {inv.shape}")
        else:
            print("\n[WARN] L0.coarse_grain() returned None")

        validation_result = {
            "l0_state_shape": list(state.shape),
            "l1_state_shape": list(l1_state.shape),
            "l1_active_blocks": int(l1_mask.sum().item()),
            "coarse_grain_success": l1_layer is not None,
        }
    else:
        print("\nNo structures detected. Try more steps or different parameters.")
        validation_result = {"coarse_grain_success": False}

    # 记录日志
    final_loss = logger.axiom_trends.get("A2_discreteness", [0])[-1] if logger.axiom_trends.get("A2_discreteness") else 0
    json_path, doc_path = logger.finish(
        total_steps=steps,
        final_loss=final_loss,
        structures_detected=len(structures),
        validation_result=validation_result,
    )
    print(f"\n[LOG] JSON: {json_path}")
    print(f"[LOG] Doc:  {doc_path}")


def main():
    parser = argparse.ArgumentParser(description="差异论模拟机实验入口")
    subparsers = parser.add_subparsers(dest="command", help="实验命令")

    # test
    subparsers.add_parser("test", help="冒烟测试")

    # 1d
    subparsers.add_parser("1d", help="1D 差异反应堆实验")

    # 2d
    parser_2d = subparsers.add_parser("2d", help="2D 差异反应堆实验")
    parser_2d.add_argument("--size", type=int, default=32, help="网格大小 (default: 32)")
    parser_2d.add_argument("--episodes", type=int, default=20, help="训练轮数 (default: 20)")

    # validate
    parser_val = subparsers.add_parser("validate", help="运行稳定结构验证器")
    parser_val.add_argument("--size", type=int, default=32, help="网格大小 (default: 32)")
    parser_val.add_argument("--steps", type=int, default=200, help="演化步数 (default: 200)")

    # coarse-grain
    parser_cg = subparsers.add_parser("coarse-grain", help="测试粗粒化映射")
    parser_cg.add_argument("--size", type=int, default=32, help="网格大小 (default: 32)")
    parser_cg.add_argument("--steps", type=int, default=300, help="演化步数 (default: 300)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        print("\nRunning smoke test by default...\n")
        run_smoke_test()
        return

    commands = {
        "test": run_smoke_test,
        "1d": run_1d,
        "2d": run_2d,
        "validate": run_validate,
        "coarse-grain": run_coarse_grain,
    }

    func = commands.get(args.command)
    if func:
        func(args)
    else:
        print(f"Unknown command: {args.command}")


if __name__ == '__main__':
    main()
