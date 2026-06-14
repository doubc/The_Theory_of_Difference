"""
exp_214_p3_depth_real.py - Phase 23 P3 涌现深度突破验证（真实模拟器版）

替代简化解析模型，使用 world_v2.py 中的 RecursiveWorld 真实模拟器。

假设 H23-3: 在开放系统（持续能量注入）+ 自指闭环环境下，
涌现深度能够突破 Phase 18 的极限 log_3(N0/3) ≈ 4-5 层。

实验设计 (2×2 因子):
- G1: 封闭系统 + 无自指 (死秩序基线)
- G2: 开放系统 + 无自指 (能量效应)
- G3: 封闭系统 + 自指闭环 (自指效应)
- G4: 开放系统 + 自指闭环 (两者协同)

日期: 2026-06-15 00:44
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import json
import numpy as np
from datetime import datetime
from pathlib import Path
import datetime as dt

from diffsim.world_v2 import RecursiveWorld, Params
from diffsim.energy_v2 import EnergyConfig, EnergyManager
from diffsim.entropy import EntropyConfig

# =============================================================================
# 实验参数
# =============================================================================
N_SEEDS = 5          # 每组随机种子数
N0_LIST = [100, 300] # 初始规模
MAX_LAYERS = 12      # 最大涌现层数
MAX_STEPS = 400      # 每层最大步数

# 能量配置
ENERGY_BUDGET = 500  # 每层能量预算
M9_COST = 2.0       # m9 自指成本

# =============================================================================
# 实验组定义
# =============================================================================
def make_energy_cfg():
    """创建能量配置。"""
    return EnergyConfig(
        initial_budget=ENERGY_BUDGET,
        m1_cost=0.1, m3_cost=0.1, m6_cost=0.1, m9_cost=M9_COST,
    )


def run_group(group_id, N0, seed, energy_injection, self_reference):
    """运行单个实验组。"""
    energy_cfg = make_energy_cfg() if energy_injection else None

    try:
        world = RecursiveWorld(
            N0=N0,
            params=Params(max_steps=MAX_STEPS),
            energy_cfg=energy_cfg,
            seed=seed,
            self_encapsulate=self_reference,
        )

        result = world.run(max_layers=MAX_LAYERS, verbose=False)

        # 提取关键指标
        depth = result['depth']
        n_layers = result['n_layers']
        layer_infos = result['layers']

        # 计算 Phase 18 极限
        phase18_limit = np.log(N0 / 3) / np.log(3)

        # 深度是否突破极限
        breakthrough = depth > phase18_limit

        # 计算平均通量
        fluxes = [li['flux'] for li in layer_infos if 'flux' in li]
        avg_flux = float(np.mean(fluxes)) if fluxes else 0.0
        max_flux = float(np.max(fluxes)) if fluxes else 0.0

        # L1 特殊指标（自指主要效应层）
        l1_flux = layer_infos[1]['flux'] if n_layers > 1 else 0.0

        return {
            'group_id': group_id,
            'N0': N0,
            'seed': seed,
            'energy_injection': energy_injection,
            'self_reference': self_reference,
            'depth': depth,
            'n_layers': n_layers,
            'phase18_limit': float(phase18_limit),
            'breakthrough': breakthrough,
            'avg_flux': avg_flux,
            'max_flux': max_flux,
            'l1_flux': float(l1_flux),
            'layers': layer_infos,
            'success': True,
        }

    except Exception as e:
        return {
            'group_id': group_id,
            'N0': N0,
            'seed': seed,
            'energy_injection': energy_injection,
            'self_reference': self_reference,
            'depth': 0,
            'n_layers': 0,
            'phase18_limit': float(np.log(N0 / 3) / np.log(3)),
            'breakthrough': False,
            'avg_flux': 0.0,
            'max_flux': 0.0,
            'l1_flux': 0.0,
            'layers': [],
            'success': False,
            'error': str(e),
        }


def run_experiment():
    """运行完整实验。"""
    print("=" * 70)
    print("Phase 23 P3: 涌现深度突破验证 (exp_214 真实模拟器版)")
    print("=" * 70)
    print()

    groups = [
        ("G1", False, False, "封闭/无自指(死秩序基线)"),
        ("G2", True,  False, "开放/无自指(能量效应)"),
        ("G3", False, True,  "封闭/有自指(自指效应)"),
        ("G4", True,  True,  "开放/有自指(协同效应)"),
    ]

    all_results = []
    summary_data = {}

    for group_id, energy, self_ref, desc in groups:
        print(f"\n### {group_id}: {desc}")
        print("-" * 70)

        group_depths = []
        group_fluxes = []
        group_l1_fluxes = []
        group_breakthrough = []

        for N0 in N0_LIST:
            phase18_limit = np.log(N0 / 3) / np.log(3)
            n_subgroup = 0
            subgroup_depths = []
            subgroup_breakthrough = []

            for seed in range(N_SEEDS):
                result = run_group(group_id, N0, seed, energy, self_ref)
                all_results.append(result)

                if result['success']:
                    group_depths.append(result['depth'])
                    group_fluxes.append(result['avg_flux'])
                    group_l1_fluxes.append(result['l1_flux'])
                    group_breakthrough.append(result['breakthrough'])
                    subgroup_depths.append(result['depth'])
                    subgroup_breakthrough.append(result['breakthrough'])
                    n_subgroup += 1

                    print(f"  N0={N0}, seed={seed}: "
                          f"depth={result['depth']}, "
                          f"L1_flux={result['l1_flux']:.4f}, "
                          f"breakthrough={result['breakthrough']}")

            # 子组汇总
            if subgroup_depths:
                avg_depth = np.mean(subgroup_depths)
                std_depth = np.std(subgroup_depths)
                breakthrough_rate = sum(subgroup_breakthrough) / len(subgroup_breakthrough)

                print(f"  [{group_id}] N0={N0}: "
                      f"avg_depth={avg_depth:.2f}±{std_depth:.2f}, "
                      f"突破率={breakthrough_rate*100:.0f}%")

        # 组汇总
        if group_depths:
            summary_data[group_id] = {
                'desc': desc,
                'avg_depth': float(np.mean(group_depths)),
                'std_depth': float(np.std(group_depths)),
                'avg_flux': float(np.mean(group_fluxes)),
                'avg_l1_flux': float(np.mean(group_l1_fluxes)),
                'breakthrough_rate': sum(group_breakthrough) / len(group_breakthrough),
            }

    # =======================================================================
    # H23-3 假设验证
    # =======================================================================
    print("\n" + "=" * 70)
    print("假设验证: H23-3 涌现深度突破")
    print("=" * 70)

    for N0 in N0_LIST:
        phase18_limit = np.log(N0 / 3) / np.log(3)
        print(f"\nN0={N0} (Phase 18 极限: {phase18_limit:.2f} 层):")

        for group_id, _, _, desc in groups:
            depths_N0 = [r['depth'] for r in all_results
                        if r['group_id'] == group_id and r['N0'] == N0 and r['success']]
            if depths_N0:
                avg = np.mean(depths_N0)
                breakthrough = any(r['breakthrough'] for r in all_results
                                  if r['group_id'] == group_id and r['N0'] == N0 and r['success'])
                status = "[PASS]" if breakthrough else "[FAIL]"
                print(f"  {group_id}: avg_depth={avg:.2f} {status}")

    # 跨规模比较
    print("\n跨规模比较:")
    G1_depths = [r['depth'] for r in all_results if r['group_id'] == 'G1' and r['success']]
    G4_depths = [r['depth'] for r in all_results if r['group_id'] == 'G4' and r['success']]

    avg_G1 = np.mean(G1_depths) if G1_depths else 0.0
    avg_G4 = np.mean(G4_depths) if G4_depths else 0.0
    depth_ratio = avg_G4 / avg_G1 if avg_G1 > 0 else 0.0

    print(f"  G1 (基线) 平均深度: {avg_G1:.2f}")
    print(f"  G4 (开放+自指) 平均深度: {avg_G4:.2f}")
    print(f"  深度比值: {depth_ratio:.2f}x")

    # H23-3 判定: G4 深度显著超过 G1
    H23_3_pass = depth_ratio >= 1.2

    if H23_3_pass:
        print(f"\n[PASS] H23-3 PASS: G4 深度是 G1 的 {depth_ratio:.2f}x (≥1.2x 阈值)")
    else:
        print(f"\n[FAIL] H23-3 FAIL: 深度比值 {depth_ratio:.2f}x < 1.2x 阈值")

    # 额外: 自指效应分析
    print("\n自指效应分析:")
    G3_depths = [r['depth'] for r in all_results if r['group_id'] == 'G3' and r['success']]
    G1_self_depths = [r['depth'] for r in all_results if r['group_id'] == 'G1' and r['success']]
    if G3_depths and G1_self_depths:
        selfref_ratio = np.mean(G3_depths) / np.mean(G1_self_depths)
        print(f"  G3(自指)/G1(基线) = {selfref_ratio:.2f}x")

    # =======================================================================
    # 保存结果
    # =======================================================================
    script_dir = Path(__file__).parent
    output_path = script_dir / ".." / "results" / "exp_214_p3_depth_real.json"
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "experiment": "exp_214_p3_depth_real",
        "timestamp": datetime.now().isoformat(),
        "description": "Phase 23 P3 涌现深度突破验证（真实模拟器）",
        "parameters": {
            "N_SEEDS": N_SEEDS,
            "N0_LIST": N0_LIST,
            "MAX_LAYERS": MAX_LAYERS,
            "MAX_STEPS": MAX_STEPS,
            "ENERGY_BUDGET": ENERGY_BUDGET,
            "M9_COST": M9_COST,
        },
        "phase18_limits": {str(N0): float(np.log(N0 / 3) / np.log(3)) for N0 in N0_LIST},
        "summary": summary_data,
        "h23_3_verdict": "PASS" if H23_3_pass else "FAIL",
        "depth_ratio": float(depth_ratio),
        "avg_G1_depth": float(avg_G1),
        "avg_G4_depth": float(avg_G4),
        "results": all_results,
    }

    def _np_default(o):
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, (np.float32, np.float64, np.float_)):
            return float(o)
        if isinstance(o, (np.int8, np.int16, np.int32, np.int64, np.int_, np.uint8, np.uint16)):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if hasattr(o, '__dict__'):
            return o.__dict__
        if isinstance(o, set):
            return sorted(list(o))
        return None
    with open(output_path, "w", encoding="utf-8") as f:
        try:
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=_np_default)
        except Exception as e:
            # Strip numpy objects that still fail
            def safe_default(obj):
                if hasattr(obj, 'tolist'):
                    return obj.tolist()
                if hasattr(obj, '__dict__'):
                    return {k: safe_default(v) for k, v in obj.__dict__.items()}
                return str(obj)
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=safe_default)
        print(f"结果已保存: {output_path}")

    print(f"\n结果已保存: {output_path}")
    print("=" * 70)

    return all_results, H23_3_pass, summary_data


if __name__ == "__main__":
    results, h23_3_pass, summary = run_experiment()