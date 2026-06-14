#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_experiment.py — 证明九机制咬合的关键实验。

对比两种 A9:
    基线(原项目行为): A9 只向外投影 -> L1 无差异源 -> flux=0 -> 死秩序, 无 L2。
    修复(自指闭环): A9 封装自身 -> L1 获得新差异源 -> flux>0 -> 咬合 -> L2/L3 涌现。
这直接推翻归档结论"Jaccard flux=0.0 / L2 涌现 0%"。
"""
import argparse
import numpy as np
from diffsim import RecursiveWorld
from diffsim.metrics import summarize


def run_condition(self_encap, seeds, **kw):
    depths, fluxes_l1 = [], []
    last_report = None
    for s in seeds:
        w = RecursiveWorld(seed=s, self_encapsulate=self_encap, **kw)
        rep = w.run(max_layers=6)
        last_report = rep
        depths.append(w.emergence_depth())
        l1 = [r for r in rep if r["layer"] == 1]
        fluxes_l1.append(l1[0]["autonomous_flux"] if l1 else 0.0)
    return depths, fluxes_l1, last_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--N0", type=int, default=48)
    args = ap.parse_args()
    seeds = list(range(args.seeds))
    kw = dict(N0=args.N0, n0_active=40, n_colors=6)

    print("=" * 70)
    print("差异论模拟机 v2 — 九机制闭环验证实验")
    print("=" * 70)

    print("\n[基线] A9 只向外投影(原项目行为) — 预期: 死秩序")
    d0, f0, r0 = run_condition(False, seeds, **kw)
    print(summarize(r0))
    print(f"\n  平均涌现深度(密封层数) = {np.mean(d0):.2f}")
    print(f"  L1 平均自主 flux       = {np.mean(f0):.4f}")
    print(f"  L2 涌现率               = {100*np.mean([d>=3 for d in d0]):.0f}%")

    print("\n[修复] A9 封装自身·完成自指 — 预期: 活秩序·咬合")
    d1, f1, r1 = run_condition(True, seeds, **kw)
    print(summarize(r1))
    print(f"\n  平均涌现深度(密封层数) = {np.mean(d1):.2f}")
    print(f"  L1 平均自主 flux       = {np.mean(f1):.4f}")
    print(f"  L2 涌现率               = {100*np.mean([d>=3 for d in d1]):.0f}%")

    print("\n" + "=" * 70)
    print("结论对比")
    print("=" * 70)
    print(f"  {'指标':<22}{'基线(归档)':>14}{'修复(自指闭环)':>18}")
    print(f"  {'L1 自主 flux':<22}{np.mean(f0):>14.4f}{np.mean(f1):>18.4f}")
    print(f"  {'涌现深度':<22}{np.mean(d0):>14.2f}{np.mean(d1):>18.2f}")
    print(f"  {'L2 涌现率':<22}{100*np.mean([d>=3 for d in d0]):>13.0f}%{100*np.mean([d>=3 for d in d1]):>17.0f}%")
    print("=" * 70)


if __name__ == "__main__":
    main()
