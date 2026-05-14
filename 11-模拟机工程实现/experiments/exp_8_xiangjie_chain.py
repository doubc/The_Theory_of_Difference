"""
exp_8_xiangjie_chain.py — 象界显现链集成实验

验证《象界》八章生成链在模拟机中的可检测性。
实验设计：
1. 运行世界引擎，生成稳定结构
2. 在运行过程中周期性评估象界显现链
3. 观察：稳定结构能否通过象界门槛？最高到达哪一阶段？
"""

import sys
import os
import torch
import numpy as np
from typing import Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from acl.axiom_base import AxiomEngine, StableStructure
from acl.axioms import (
    A1_DifferenceSource, A2_DiscreteEncoding, A3_Locality,
    A4_MinimalVariation, A5_Conservation, A6_FlowCoupling,
    A7_Stability, A8_SymmetrySink, A9_MinimalSufficient,
)
from layers.L0_binary_lattice import L0BinaryLattice
from models.local_conv_model import LocalConvModel
from engine.world_engine import WorldEngine
from xiangjie.chain import XiangjieChain, XiangjieReport


def create_engine(grid_size: int = 32, lr: float = 1e-3) -> WorldEngine:
    """创建配置好的世界引擎"""
    layer = L0BinaryLattice(shape=(grid_size, grid_size))
    model = LocalConvModel(channels=1)

    axioms = [
        A1_DifferenceSource(),
        A2_DiscreteEncoding(),
        A3_Locality(),
        A4_MinimalVariation(),
        A5_Conservation(),
        A6_FlowCoupling(),
        A7_Stability(),
        A8_SymmetrySink(),
        A9_MinimalSufficient(),
    ]
    axiom_engine = AxiomEngine(axioms)

    engine = WorldEngine(
        model=model, layer=layer, axiom_engine=axiom_engine,
        lr=lr, device="cpu",
        xiangjie_check_interval=64,
    )
    return engine


def run_xiangjie_experiment(
    grid_size: int = 32,
    max_steps: int = 512,
    lr: float = 1e-3,
) -> Dict:
    """运行象界显现链实验"""
    print("=" * 60)
    print("象界显现链集成实验 (exp_8)")
    print("=" * 60)
    print(f"  网格: {grid_size}x{grid_size}")
    print(f"  步数: {max_steps}")
    print(f"  学习率: {lr}")

    engine = create_engine(grid_size, lr)

    # 运行世界引擎（禁用升维以避免 L1 shape 属性缺失问题）
    print("\n--- 运行世界引擎 ---")
    result = engine.run(
        max_steps=max_steps,
        ascent_check_interval=max_steps + 1,  # 不触发升维
        train=True,
    )

    print(f"\n总步数: {result['total_steps']}")
    print(f"检测到结构: {result['structures_detected']}")
    print(f"升维次数: {len(result['ascents'])}")

    # 输出象界报告
    xj_reports = result.get("xiangjie_reports", [])
    if xj_reports:
        print(f"\n象界评估次数: {len(xj_reports)}")
        for i, report in enumerate(xj_reports):
            print(f"\n--- 象界评估 #{i+1} ---")
            print(report)
    else:
        print("\n无象界报告（稳定结构不足或检查间隔未到）")

        # 手动检测：尝试在历史中找稳定结构并评估
        print("\n--- 手动象界评估 ---")
        layer = engine.layer
        # 需要从 trainer 获取历史
        state = layer.initial_state()
        history = [state.detach()]
        for _ in range(128):
            next_state, _, _ = engine.reactor.step(state, history)
            state = next_state.detach()
            history.append(state)

        structures = layer.detect_stable_structures(history)
        print(f"手动检测到 {len(structures)} 个稳定结构")

        if structures:
            chain = XiangjieChain()
            report = chain.evaluate(structures, history, layer, state)
            print(report)

    # 最终状态统计
    final = result["final_state"]
    print(f"\n最终状态: mean={final.mean():.4f}, std={final.std():.4f}")
    unique = len(torch.unique(final.round()))
    print(f"离散值数: {unique}")

    return result


if __name__ == "__main__":
    result = run_xiangjie_experiment(
        grid_size=32,
        max_steps=512,
        lr=1e-3,
    )
