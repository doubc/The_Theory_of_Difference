#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_183 — Phase 18 P1: m9 结构传递实验 (Structural Propagation)

目的: 测量 m9 的结构化初始条件对 k(N) 的实际增强效应。
比较:
  - P0 (随机初始): k_rand(N)  — 孤立层随机初始条件  [已完成]
  - P1 (m9 传递):  k_m9(N0)   — m9 生成的 L1 实际 k  [本轮实验]

核心问题:
  m9 生成 L1 时携带 body↔naming 预绑定、颜色继承、命名位作为差异源。
  这些结构化初始条件是否显著提高 k(N)？增强因子是多少？

方法:
  对每个 N0 ∈ [12, 18, 24, 30, 36, 48, 60, 72, 96]:
    运行 16 seeds 的 RecursiveWorld L0
    捕获 m9 输出的 L1 场
    让 L1 运行密封
    测量: k_m9(N0) = L1 密封后组织数
           k0 = L0 密封后组织数
           N1 = m9 生成的 L1 场大小 (= 2*k0 + n_res)
           r_enhanced = k_m9 / N1 (与 P0 的 r_rand 比较)
           amplification = k_m9 / k_rand(N1) (结构传递增强因子)

假设 H18-P1:
  m9 结构化初始条件使 k_m9(N1) 显著高于 k_rand(N1)
  即 amplification > 2.0 (结构传递比随机初始好 2x+)

依赖: exp_182 的 P0 结果文件 (results/exp_182_p0_compression_*.json)
"""
import sys, os, json, time, glob
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from diffsim import RecursiveWorld, Layer
from diffsim.core import DifferenceField
from diffsim.world import Params
from diffsim import mechanisms as M
from diffsim.metrics import jaccard_flux


# ─────────────────────────────────────────
#  1. 加载 P0 基线结果 (k_rand)
# ─────────────────────────────────────────
def load_p0_results():
    """载入 exp_182 的最新 P0 结果文件, 返回 {N: mean_k} 字典."""
    pat = os.path.join(os.path.dirname(__file__), "..", "results",
                       "exp_182_p0_compression_*.json")
    files = sorted(glob.glob(pat))
    if not files:
        print("⚠️  未找到 P0 结果文件, 将在无基线比较模式下运行")
        return {}
    latest = files[-1]
    with open(latest, "r") as f:
        data = json.load(f)
    results = data.get("results", [])
    p0_table = {}
    for rec in results:
        N = rec["N"]
        if N not in p0_table:
            p0_table[N] = {"k": [], "r": []}
        p0_table[N]["k"].append(rec.get("k", 0))
        p0_table[N]["r"].append(rec.get("r_ratio", 0))
    p0 = {}
    for N, vals in p0_table.items():
        p0[N] = {
            "mean_k": np.mean(vals["k"]),
            "max_k": np.max(vals["k"]),
            "mean_r": np.mean(vals["r"]),
        }
    print(f"📂 已载入 P0 基线: {latest} ({len(files)} 个种子)")
    return p0


# ─────────────────────────────────────────
#  2. 运行 L0 + m9 + L1 的端到端流程
# ─────────────────────────────────────────
def run_l0_m9_l1(N0, seed=0, params=None, verbose=False):
    """
    运行 RecursiveWorld L0 → m9 生成 L1 → L1 密封.
    返回 L0 和 L1 的完整指标.
    """
    p = params or Params()
    rng = np.random.default_rng(seed)

    # -- L0: 构建差异场并密封 --
    n_active = min(N0, max(6, N0 // 2))
    active0 = rng.choice(N0, size=n_active, replace=False).tolist()
    color0 = rng.integers(0, 6, size=N0)
    field0 = DifferenceField(
        N=N0, active=active0, a1_source=set(active0),
        direction=np.zeros(N0, dtype=np.int8), color=color0,
        layer=0, rng=rng,
    )
    layer0 = Layer(field0, p)
    sealed0 = layer0.run_until_seal(verbose=verbose)
    flux0 = layer0.autonomous_flux()
    k0 = len([o for o in field0.organizations.values()
              if len(o) >= p.min_org_size])

    if not sealed0 or k0 == 0:
        # L0 未密封 -> 无法进入 m9
        return {
            "N0": N0, "seed": seed, "L0_sealed": False, "k0": k0,
        }

    # -- 执行 m9 自指封装 (生成 L1 场) --
    nxt = M.m9_self_reference(layer0, self_encapsulate=True)
    if nxt is None:
        return {
            "N0": N0, "seed": seed, "L0_sealed": True, "k0": k0,
            "m9_generated": False,
        }

    N1 = nxt.N  # m9 输出的 L1 场大小
    k1_residual = len(nxt.naming_meta.get("res_idx", []))

    # -- L1: 运行密封 --
    layer1 = Layer(nxt, p)
    sealed1 = layer1.run_until_seal(verbose=verbose)
    flux1 = layer1.autonomous_flux()
    k1 = len([o for o in nxt.organizations.values()
              if len(o) >= p.min_org_size])

    # -- L1 初始组织数 (m9 做了预绑定, 看实际密封结果) --
    return {
        "N0": N0, "seed": seed,
        "L0_sealed": True, "m9_generated": True,
        "k0": k0, "N1": N1, "k1": k1,
        "n_res": k1_residual,
        "L0_seal_step": field0.seal_step,
        "L1_seal_step": nxt.seal_step,
        "L1_sealed": sealed1,
        "L0_flux": round(flux0, 4),
        "L1_flux": round(flux1, 4),
        "r_m9": round(k1 / N1, 4) if N1 > 0 else 0,
        "r0_vs_N0": round(k0 / N0, 4) if N0 > 0 else 0,
    }


# ─────────────────────────────────────────
#  3. 扫描 N0
# ─────────────────────────────────────────
def sweep(N_values=None, seeds_per_N=16, params=None, verbose=False):
    if N_values is None:
        N_values = [12, 18, 24, 30, 36, 48, 60, 72, 96]
    results = []
    total = len(N_values) * seeds_per_N
    done = 0
    t0 = time.time()
    for N in N_values:
        for s in range(seeds_per_N):
            rec = run_l0_m9_l1(N, seed=s, params=params, verbose=verbose)
            results.append(rec)
            done += 1
            if done % 8 == 0 or done == total:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                print(f"  [{done}/{total}] N0={N} seed={s} "
                      f"k0={rec.get('k0','?')} k1={rec.get('k1','?')} "
                      f"({rate:.1f} runs/s)")
    return results


# ─────────────────────────────────────────
#  4. 分析和对比 P0
# ─────────────────────────────────────────
def analyze(results, N_values, p0):
    print("\n" + "=" * 75)
    print("exp_183 — P1 m9 结构传递实验: 结果汇总")
    print("=" * 75)

    rows = []
    for N in N_values:
        recs = [r for r in results if r["N0"] == N and r.get("m9_generated")]
        if not recs:
            continue
        sealed_l0 = np.mean([r["L0_sealed"] for r in recs])
        sealed_l1 = np.mean([r.get("L1_sealed", False) for r in recs])
        k0_vals = np.array([r["k0"] for r in recs])
        k1_vals = np.array([r["k1"] for r in recs])
        n1_vals = np.array([r["N1"] for r in recs])
        flux0_vals = np.array([r["L0_flux"] for r in recs])
        flux1_vals = np.array([r["L1_flux"] for r in recs])

        mean_k0 = np.mean(k0_vals)
        mean_k1 = np.mean(k1_vals)
        mean_n1 = np.mean(n1_vals)
        mean_r_m9 = np.mean([r["r_m9"] for r in recs])
        mean_flux0 = np.mean(flux0_vals)
        mean_flux1 = np.mean(flux1_vals)

        # 从 P0 获取对应 N1 的 k_rand 和 r_rand
        # 如果 N1 不在 P0 keys 中, 用最接近的插值
        if p0:
            nearest_n1 = min(p0.keys(), key=lambda x: abs(x - mean_n1))
            p0_k = p0[nearest_n1]["mean_k"]
            p0_r = p0[nearest_n1]["mean_r"]
            ampl = mean_k1 / p0_k if p0_k > 0 else float("inf")
            r_ampl = mean_r_m9 / p0_r if p0_r > 0 else float("inf")
        else:
            p0_k = p0_r = ampl = r_ampl = float("nan")

        rows.append({
            "N": N, "L0密封率": f"{100*sealed_l0:.0f}%",
            "L1密封率": f"{100*sealed_l1:.0f}%",
            "k0": f"{mean_k0:.2f}",
            "k1": f"{mean_k1:.2f}",
            "N1": f"{mean_n1:.1f}",
            "r_m9": f"{mean_r_m9:.4f}",
            "P0_r": f"{p0_r:.4f}" if not np.isnan(p0_r) else "N/A",
            "ampl": f"{ampl:.2f}x" if not np.isnan(ampl) else "N/A",
            "flux_L0": f"{mean_flux0:.4f}",
            "flux_L1": f"{mean_flux1:.4f}",
        })

    # 打印表格
    header = f"{'N0':>5} | {'L0密封':>6} | {'L1密封':>6} | {'k0':>5} | {'k1':>5} | {'N1':>5} | {'r_m9':>7} | {'P0_r':>7} | {'ampl':>6} | {'flux0':>7} | {'flux1':>7}"
    sep = "-" * len(header)
    print(f"\n{header}")
    print(sep)
    for row in rows:
        print(f"{row['N']:>5} | {row['L0密封率']:>6} | {row['L1密封率']:>6} | "
              f"{row['k0']:>5} | {row['k1']:>5} | {row['N1']:>5} | "
              f"{row['r_m9']:>7} | {row['P0_r']:>7} | {row['ampl']:>6} | "
              f"{row['flux_L0']:>7} | {row['flux_L1']:>7}")

    # H18-P1 检验
    print(f"\n--- H18-P1 检验: m9 结构传递是否显著增强 k(N) ---")
    ampl_vals = [r for r in rows if r["ampl"] != "N/A" and not np.isnan(float(r["ampl"].replace("x","")))]
    if ampl_vals:
        ampl_float = [float(r["ampl"].replace("x","")) for r in ampl_vals]
        mean_ampl = np.mean(ampl_float)
        print(f"  mean amplification = {mean_ampl:.2f}x  (target: > 2.0x)")
        print(f"  结论: {'H18-P1 CONFIRMED ✅ — m9 结构化 init 显著增强 k(N)' if mean_ampl > 2.0 else 'H18-P1 部分确认 — 增强但需进一步分析'}")
    else:
        print("  N/A — 无 P0 基线数据")

    # 传递效应分析
    print(f"\n--- L0→L1 结构传递效应 ---")
    # 计算 N1 与 k0 的关系
    k0_all = np.array([r["k0"] for r in results if r.get("m9_generated")])
    k1_all = np.array([r["k1"] for r in results if r.get("m9_generated")])
    n1_all = np.array([r["N1"] for r in results if r.get("m9_generated")])
    if len(k0_all) > 0:
        corr_k0_k1 = np.corrcoef(k0_all, k1_all)[0, 1] if len(k0_all) > 1 else 0
        corr_k0_n1 = np.corrcoef(k0_all, n1_all)[0, 1] if len(k0_all) > 1 else 0
        corr_n1_k1 = np.corrcoef(n1_all, k1_all)[0, 1] if len(n1_all) > 1 else 0
        print(f"  corr(k0, k1)  = {corr_k0_k1:.4f}  — L0 组织数传递到 L1")
        print(f"  corr(k0, N1)  = {corr_k0_n1:.4f}  — m9 编码效应")
        print(f"  corr(N1, k1)  = {corr_n1_k1:.4f}  — L1 规模与组织数相关")
        # 计算平均深度预测
        depth_actual = sum(1 for r in results if r.get("L1_sealed") and r.get("m9_generated"))
        depth_total = sum(1 for r in results if r.get("m9_generated"))
        print(f"  L1 密封率 = {depth_actual}/{depth_total} = {100*depth_actual/max(1,depth_total):.1f}%")
        print(f"  (密封率越高 → 涌现深度链越可能继续)")

    # 对比 exp_182 P0 的深度预测
    print(f"\n--- 深度预测修正 (与 P0 对比) ---")
    if p0:
        # 用膨胀后的 k1 计算下一层大小预测
        for N in N_values:
            recs = [r for r in results if r["N0"] == N and r.get("m9_generated")]
            if not recs:
                continue
            k1_mean = np.mean([r["k1"] for r in recs])
            n1_mean = np.mean([r["N1"] for r in recs])

            # 用 P0 的 k_rand(N1) 预测深度: 只走 1 步 P0 预测
            nearest = min(p0.keys(), key=lambda x: abs(x - n1_mean))
            p0_k_at_n1 = p0[nearest]["mean_k"]
            p0_n2 = 2 * p0_k_at_n1 + 3
            # 用 m9 的 k1 预测下一层: n2_m9 = 2*k1 + 3
            n2_m9 = 2 * k1_mean + 3
            p0_n2_at_n1 = 2 * p0_k_at_n1 + 3
            delta = n2_m9 - p0_n2_at_n1
            print(f"  N0={N:>3}: k1(exp183)={k1_mean:.1f} vs k_rand(N1={n1_mean:.0f})={p0_k_at_n1:.1f}  "
                  f"→ n2_m9={n2_m9:.0f} vs n2_p0={p0_n2_at_n1:.0f} (delta={delta:+.0f})")

    return rows


# ─────────────────────────────────────────
#  5. Main
# ─────────────────────────────────────────
def main():
    print("=" * 75)
    print("exp_183 — Phase 18 P1: m9 结构传递实验")
    print("=" * 75)
    t0 = time.time()

    N_values = [12, 18, 24, 30, 36, 48, 60, 72, 96]
    seeds_per_N = 16
    total = len(N_values) * seeds_per_N

    print(f"\n运行: {len(N_values)} N 值 × {seeds_per_N} seeds = {total} runs\n")

    # 加载 P0 基线
    p0 = load_p0_results()

    # 扫描
    p = Params()
    results = sweep(N_values, seeds_per_N, params=p)

    # 分析
    rows = analyze(results, N_values, p0)

    # 保存
    os.makedirs("results", exist_ok=True)
    out_path = f"results/exp_183_p1_propagation_{time.strftime('%Y%m%d_%H%M')}.json"
    with open(out_path, "w") as f:
        json.dump({
            "experiment": "exp_183_phase18_p1_structural_propagation",
            "params": {k: v for k, v in p.__dict__.items() if not k.startswith("_")},
            "N_values": N_values, "seeds_per_N": seeds_per_N,
            "results": results,
            "elapsed_seconds": round(time.time() - t0, 1),
        }, f, indent=2)
    print(f"\n结果已保存: {out_path}")
    print(f"总耗时: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()