"""
exp_157 — Phase 13 P3: Multi-subspace Coupling (revised)

科学问题：
  Phase 13 P2 (exp_156) 发现密封后系统处于"有序但无记忆"的冻结态。
  结论：要产生 L2（第二层组织），需要引入新的自由能流。

  之前的 SubspaceAwareEvolver 的耦合机制（修改 binding_strength）无效——
  binding_strength 在动力学中不被读取。

  exp_157 采用新的耦合范式：**单演化器 + 自定义 step_callback 耦合**

核心思想：
  使用单个 SpatialLongRangeEvolver（N=72）。
  密封发生后，通过 step_callback 实现"多子空间效果"：
  1. sealed bits 冻结不动（已是系统行为）
  2. unsealed bits 继续演化
  3. 耦合 = **密封结构调制源注入的空间权重**
     - 靠近 sealed bits 的位置 → 注入权重更低（已被"占据"）
     - 远离 sealed bits 的位置 → 注入权重更高（"空白处"）
  4. 这创造了一种"模板生长"动力学：
     - 密封区域排斥新注入（已被占据）
     - 空白区域吸引新注入（边缘增长）

假设 (H157):
  H157-1 (模板生长): 密封后，新注入的 bits 倾向于分布在密封区域的边缘，
    而非随机分布。→ unsealed active bits 到最近 sealed bit 的距离分布
    呈现边缘峰值（非随机）。

  H157-2 (结构继承): 密封构型的空间结构（密度、聚类）通过模板效应
    传递到后密封动力学。→ 相关函数显示长程关联。

  H157-3 (记忆保存): 不同种子产生不同的密封构型，进而产生不同的
    后密封演化轨迹。→ 与 exp_156 P2 的"无记忆"形成对比。

实验设计：
  1. 运行 SpatialLongRangeEvolver(N=72, steps=2000)
  2. 密封发生后应用 step_callback，实现模板增长
  3. 对比：无模板增长 (callback=空) vs 有模板增长
  4. 每条件：N_RUNS=10 种子

用法：
  python experiments/exp_157_phase13_p3_multi_subspace.py
"""

import sys, os, json, datetime, time
from typing import Optional, Dict, List, Callable
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver


# ============================================================
# 参数
# ============================================================
N = 72                    # 总比特数（密封前不分区）
TOTAL_STEPS = 200          # 密封前（密封在~10步内发生）
POST_SEAL_STEPS = 500     # 密封后
N_RUNS = 10                # 每条件种子数
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================
# 模板增长回调
# ============================================================

def make_template_growth_callback(
    spatial_layer: object,
    strength: float = 1.0,
) -> Callable:
    """创建模板增长回调函数。

    工作方式：
      每步（密封后）检查是否有密封比特。
      如果有，计算未密封位置到最近密封位置的空间距离。
      将距离归一化为注入偏好权重：
        - 靠近密封比特 → 低权重（不注入）
        - 远离密封比特 → 高权重（优先注入）
    
      strength: 调制强度 (0.0 = 无耦合, 1.0 = 标准, >1.0 = 强耦合)
    """
    def callback(step: int, state: torch.Tensor, evolver: object) -> None:
        """密封后的模板增长回调。

        参数由 SpatialLongRangeEvolver.run() 的 step_callback 约定:
        callback(step, state, snapshot, constraints) → None
        但对于 post_seal_callback，调用为 callback(step, state, evolver)。
        """
        # 获取约束和空间层
        constraints = evolver.constraints
        N = evolver.N
        n = N // 3
        
        # 检查是否有密封比特
        sealed_indices = list(getattr(constraints, 'sealed_bits', set()))
        if not sealed_indices:
            return  # 尚未密封，不做操作
        
        # 计算3D坐标
        coords = np.zeros((N, 3))
        for i in range(N):
            group = i // n
            idx_in = i % n
            coords[i, group] = evolver.spatial_layer.epsilon * (idx_in + 0.5)
        
        sealed_coords = coords[sealed_indices]
        
        # 对每个0值比特，计算到最近密封比特的距离
        state_np = state.cpu().numpy()
        zeros = np.where(state_np < 0.5)[0]
        
        if len(zeros) < 5 or len(sealed_coords) < 2:
            return  # 太少零点或密封点
        
        # 计算距离权重
        distances = []
        valid_zeros = []
        for idx in zeros:
            coord = coords[idx]
            dists = np.linalg.norm(sealed_coords - coord, axis=1)
            min_dist = dists.min()
            if min_dist > 0.001:  # 避免除以零
                distances.append(min_dist)
                valid_zeros.append(idx)
        
        if not valid_zeros:
            return
        
        distances = np.array(distances)
        
        # 归一化距离到 [0, 1]
        d_min, d_max = distances.min(), distances.max()
        if d_max - d_min < 0.001:
            return  # 所有距离相同
        
        weights = (distances - d_min) / (d_max - d_min)  # [0, 1], 越远越大
        
        # 应用强度调制：strength=0 → 均匀权重, strength=1 → 完全由距离决定
        if strength < 1.0:
            # 在均匀分布和距离加权之间插值
            weights = (1.0 - strength) * 0.5 + strength * weights
        elif strength > 1.0:
            # 非线性增强：远离密封比特的权重被指数放大
            weights = weights ** strength
        
        # 归一化
        weights = weights / weights.sum()
        
        # 选择注入位置：少数几个 (与原始 source_strength 成正比)
        source_strength = constraints.get_A8_source_strength(state)
        n_inject = min(source_strength, len(valid_zeros))
        
        if n_inject < 1:
            return
        
        # 尝试注入：从权重分布中采样
        try:
            chosen_indices = np.random.choice(
                len(valid_zeros), 
                size=min(n_inject, len(valid_zeros)),
                replace=False,
                p=weights
            )
        except ValueError:
            return
        
        # 执行注入
        for ci in chosen_indices:
            idx = valid_zeros[ci]
            # 直接翻转（绕过 A8 源注入，但这是模板增长的"外部耦合"）
            a9_ok, _ = constraints.check_A9(idx, partial_sealing=getattr(evolver, 'partial_sealing', False))
            if a9_ok:
                state[idx] = 1.0
                constraints.record_active(idx)
                constraints.direction[idx] = 1
    
    return callback


# ============================================================
# 分析函数
# ============================================================

def compute_edge_clustering(
    state: torch.Tensor,
    sealed_bits: set,
    spatial_layer: object,
    N: int,
) -> Dict:
    """计算边缘聚类指标。

    对每个活跃未密封比特，计算到最近密封比特的距离。
    如果模板增长有效，距离分布应呈现：
      - 均值 < 随机基线（活跃比特靠近密封区域边缘）
      - 直方图在短距离处有峰值

    返回距离统计量。
    """
    if not sealed_bits:
        return {"mean_dist": -1, "std_dist": -1, "n_active_unsealed": 0}

    n = N // 3
    coords = np.zeros((N, 3))
    for i in range(N):
        group = i // n
        idx_in = i % n
        coords[i, group] = spatial_layer.epsilon * (idx_in + 0.5)

    sealed_indices = list(sealed_bits)
    sealed_coords = coords[sealed_indices]

    state_np = state.cpu().numpy()
    # Active unsealed bits: value=1 but not in sealed_bits
    active_mask = state_np > 0.5
    unsealed_active = [i for i in range(N) if active_mask[i] and i not in sealed_bits]

    if len(unsealed_active) < 3:
        return {"mean_dist": -1, "std_dist": -1, "n_active_unsealed": len(unsealed_active)}

    distances = []
    for idx in unsealed_active:
        coord = coords[idx]
        dists = np.linalg.norm(sealed_coords - coord, axis=1)
        distances.append(dists.min())

    return {
        "mean_dist": float(np.mean(distances)),
        "std_dist": float(np.std(distances)),
        "min_dist": float(np.min(distances)),
        "max_dist": float(np.max(distances)),
        "n_active_unsealed": len(unsealed_active),
        "n_sealed": len(sealed_indices),
    }


def compute_hw_variance(state_history: List[float], pre_seal: int) -> Dict:
    """计算密封前后 HW 方差。"""
    if len(state_history) < 10:
        return {"pre_var": -1, "post_var": -1}

    pre = state_history[:pre_seal]
    post = state_history[pre_seal:]

    return {
        "pre_var": float(np.var(pre)) if len(pre) > 5 else -1,
        "post_var": float(np.var(post)) if len(post) > 5 else -1,
    }


def compute_correlation_length(
    state: torch.Tensor,
    sealed_bits: set,
    spatial_layer: object,
    N: int,
) -> Dict:
    """计算空间相关长度（简化版）。

    对密封区域外，计算 C(r) = <s_i * s_j> - <s_i><s_j>
    其中 s_i 是比特 i 的状态 (0/1)，r 是空间距离。
    """
    if not sealed_bits or len(sealed_bits) < 3:
        return {"xi": -1, "c0": -1}

    n = N // 3
    coords = np.zeros((N, 3))
    for i in range(N):
        group = i // n
        idx_in = i % n
        coords[i, group] = spatial_layer.epsilon * (idx_in + 0.5)

    state_np = state.cpu().numpy()
    sealed_set = set(sealed_bits)
    
    # 仅分析非密封比特
    unsealed = [i for i in range(N) if i not in sealed_set]
    if len(unsealed) < 5:
        return {"xi": -1, "c0": -1}

    # 计算相关性
    pairs = []
    for i in range(len(unsealed)):
        for j in range(i+1, len(unsealed)):
            a, b = unsealed[i], unsealed[j]
            si, sj = state_np[a], state_np[b]
            r = np.linalg.norm(coords[a] - coords[b])
            pairs.append((r, si * sj))

    if len(pairs) < 10:
        return {"xi": -1, "c0": -1}

    # 按距离分箱
    rs = np.array([p[0] for p in pairs])
    cs = np.array([p[1] for p in pairs])
    
    # 简单拟合：特征相关长度 = 自关联距离
    # 如果存在长程相关，C(r) 在较大 r 处仍为正
    r_max = rs.max()
    r_bins = np.linspace(0, r_max, 10)
    bin_means = []
    for k in range(len(r_bins) - 1):
        mask = (rs >= r_bins[k]) & (rs < r_bins[k+1])
        if mask.sum() > 0:
            bin_means.append(float(cs[mask].mean()))
        else:
            bin_means.append(0.0)

    # 简单度量：相关长度 ≈ 相关函数降到 1/e 的距离
    if bin_means and bin_means[0] > 0.01:
        half_idx = 0
        for k in range(1, len(bin_means)):
            if bin_means[k] < bin_means[0] / np.e:
                half_idx = k
                break
        xi = r_bins[half_idx] if half_idx > 0 else r_max
    else:
        xi = 0

    return {
        "xi": float(xi),
        "c0": float(bin_means[0]) if bin_means else 0,
        "bin_means": [float(b) for b in bin_means],
    }


# ============================================================
# 单次运行
# ============================================================

def run_single(
    seed: int,
    template_strength: float = 0.0,
    verbose: bool = False,
) -> Dict:
    """带模板增长耦合的单次运行。

    template_strength=0.0 → 对照组（无耦合）
    template_strength>0 → 有模板增长
    """
    torch.manual_seed(seed * 137 + 53)
    np.random.seed(seed * 137 + 53)

    # 初始状态：随机少量 1
    initial = torch.zeros(N)
    n_ones = max(3, int(np.random.randint(4, min(12, N // 2) + 1)))
    indices = torch.randperm(N)[:n_ones]
    initial[indices] = 1.0

    # 创建演化器
    evolver = SpatialLongRangeEvolver(
        N=N,
        total_steps=TOTAL_STEPS,
        post_seal_steps=POST_SEAL_STEPS,
        sample_interval=50,
        device="cpu",
        L=1.0,
        partial_sealing=False,
    )

    # 创建模板增长回调（仅 template_strength > 0）
    post_callback = None
    if template_strength > 0:
        post_callback = make_template_growth_callback(
            evolver.spatial_layer,
            strength=template_strength,
        )

    # 运行
    result = evolver.run(
        initial_state=initial,
        verbose=verbose,
        step_callback=None,
        post_seal_callback=post_callback,
    )

    sealed = result.get("sealed", False)
    seal_step = result.get("seal_step", -1)
    final_state = result.get("final_state", None)
    hw_history = result.get("hamming_weight_history", [])
    total_steps_actual = result.get("total_steps", TOTAL_STEPS)

    # 获取密封比特集
    sealed_bits = set()
    if hasattr(evolver, 'constraints') and evolver.constraints is not None:
        sb = getattr(evolver.constraints, 'sealed_bits', set())
        if sb:
            sealed_bits = set(sb)

    # 分析
    edge_stats = {"mean_dist": -1}
    corr_stats = {"xi": -1}

    if final_state is not None and sealed:
        edge_stats = compute_edge_clustering(
            final_state, sealed_bits, evolver.spatial_layer, evolver.N
        )
        corr_stats = compute_correlation_length(
            final_state, sealed_bits, evolver.spatial_layer, evolver.N
        )

    hw_var = compute_hw_variance(hw_history, seal_step if seal_step > 0 else TOTAL_STEPS)

    # 最终 HW
    final_hw = float(final_state.sum().item()) if final_state is not None else 0.0

    return {
        "seed": seed,
        "sealed": bool(sealed),
        "seal_step": int(seal_step),
        "final_hw": final_hw,
        "n_sealed_bits": len(sealed_bits),
        "edge_mean_dist": edge_stats.get("mean_dist", -1),
        "edge_n_active": edge_stats.get("n_active_unsealed", 0),
        "corr_length": corr_stats.get("xi", -1),
        "hw_pre_var": hw_var.get("pre_var", -1),
        "hw_post_var": hw_var.get("post_var", -1),
        "total_steps": int(total_steps_actual),
    }


# ============================================================
# 主运行
# ============================================================

def main():
    # 条件：模板增长强度扫描
    TEMPLATE_STRENGTHS = [0.0, 1.0, 5.0]

    print("=" * 70)
    print("Phase 13 P3: 多子空间耦合实验 (exp_157, 修订版)")
    print(f"  N={N}, 每个条件 {N_RUNS} 种子")
    print(f"  模板增长强度: {TEMPLATE_STRENGTHS}")
    print("=" * 70)

    all_results = {}

    for s in TEMPLATE_STRENGTHS:
        print(f"\n--- 模板强度={s:.1f} ---")
        cond_results = []
        for seed in range(N_RUNS):
            r = run_single(seed, template_strength=s, verbose=False)
            cond_results.append(r)
            sealed = "Y" if r["sealed"] else "N"
            edge = f"d={r['edge_mean_dist']:.3f}" if r["edge_mean_dist"] > 0 else "N/A"
            print(f"  Seed {seed:2d}: 密封={sealed} "
                  f"HW={r['final_hw']:.0f} "
                  f"sealed_bits={r['n_sealed_bits']} "
                  f"边缘距离={edge} "
                  f"ξ={r['corr_length']:.3f}")

        all_results[str(s)] = cond_results

        # 汇总
        sealed_rates = [r["sealed"] for r in cond_results]
        seal_rates_f = sum(sealed_rates) / len(sealed_rates)

        edge_dists = [r["edge_mean_dist"] for r in cond_results if r["edge_mean_dist"] > 0]
        corr_lengths = [r["corr_length"] for r in cond_results if r["corr_length"] > 0]

        print(f"\n  密封率: {seal_rates_f:.2f} ({int(seal_rates_f * N_RUNS)}/{N_RUNS})")
        if edge_dists:
            print(f"  边缘距离: {np.mean(edge_dists):.4f} ± {np.std(edge_dists):.4f}")
        if corr_lengths:
            print(f"  相关长度 ξ: {np.mean(corr_lengths):.3f} ± {np.std(corr_lengths):.3f}")

    # ── 假设检验 ──
    print("\n" + "=" * 70)
    print("假设检验")
    print("=" * 70)

    base = all_results["0.0"]
    strong = all_results["10.0"]

    base_edge = [r["edge_mean_dist"] for r in base if r["edge_mean_dist"] > 0]
    strong_edge = [r["edge_mean_dist"] for r in strong if r["edge_mean_dist"] > 0]

    h157_1 = bool(strong_edge and base_edge and np.mean(strong_edge) < np.mean(base_edge) * 0.9)
    print(f"H157-1 (模板生长, 边缘距离减小): {'PASS ✅' if h157_1 else 'REJECT ❌'}")
    if base_edge:
        print(f"  对照组(0.0): {np.mean(base_edge):.4f} ± {np.std(base_edge):.4f}")
    if strong_edge:
        print(f"  强耦合(10.0): {np.mean(strong_edge):.4f} ± {np.std(strong_edge):.4f}")
    if base_edge and strong_edge:
        print(f"  差异: {np.mean(base_edge) - np.mean(strong_edge):+.4f} "
              f"({(np.mean(base_edge) - np.mean(strong_edge)) / np.mean(base_edge) * 100:+.1f}%)")

    base_xi = [r["corr_length"] for r in base if r["corr_length"] > 0]
    strong_xi = [r["corr_length"] for r in strong if r["corr_length"] > 0]
    h157_2 = bool(strong_xi and base_xi and np.mean(strong_xi) > np.mean(base_xi) * 1.1)
    print(f"\nH157-2 (结构继承, 相关长度增加): {'PASS ✅' if h157_2 else 'REJECT ❌'}")
    if base_xi:
        print(f"  对照组(0.0): ξ={np.mean(base_xi):.3f} ± {np.std(base_xi):.3f}")
    if strong_xi:
        print(f"  强耦合(10.0): ξ={np.mean(strong_xi):.3f} ± {np.std(strong_xi):.3f}")

    # H157-3: 记忆痕迹 — 强耦合下种子间 HW 方差 vs 对照组
    base_hw_var = float(np.var([r["final_hw"] for r in base if r["sealed"]])) if any(r["sealed"] for r in base) else 0
    strong_hw_var = float(np.var([r["final_hw"] for r in strong if r["sealed"]])) if any(r["sealed"] for r in strong) else 0
    # 期望方差 ≈ HW_mean * (1 - HW_mean/N)
    base_hw_mean = float(np.mean([r["final_hw"] for r in base if r["sealed"]])) if any(r["sealed"] for r in base) else 0
    strong_hw_mean = float(np.mean([r["final_hw"] for r in strong if r["sealed"]])) if any(r["sealed"] for r in strong) else 0
    base_expected_var = base_hw_mean * (1 - base_hw_mean / N) if base_hw_mean > 0 else 0
    strong_expected_var = strong_hw_mean * (1 - strong_hw_mean / N) if strong_hw_mean > 0 else 0
    h157_3 = strong_hw_var > strong_expected_var * 1.5 if strong_expected_var > 0 else False
    print(f"\nH157-3 (记忆保存): {'PASS ✅' if h157_3 else 'REJECT ❌'}")
    print(f"  对照组: HW_var={base_hw_var:.1f}, 期望={base_expected_var:.1f}")
    print(f"  强耦合: HW_var={strong_hw_var:.1f}, 期望={strong_expected_var:.1f}")

    # 跨强度对比表
    print("\n" + "-" * 60)
    print("跨强度对比")
    print("-" * 60)
    print(f"{'强度':>6} | {'密封率':>7} | {'HW':>6} | {'边缘距离':>8} | {'ξ':>6} | {'HW后方差':>8}")
    print("-" * 60)
    for s in TEMPLATE_STRENGTHS:
        r = all_results[str(s)]
        rate = sum(rr["sealed"] for rr in r) / len(r)
        hw = float(np.mean([rr["final_hw"] for rr in r if rr["sealed"]])) if any(rr["sealed"] for rr in r) else 0
        edge = [rr["edge_mean_dist"] for rr in r if rr["edge_mean_dist"] > 0]
        xi = [rr["corr_length"] for rr in r if rr["corr_length"] > 0]
        post_var = [rr["hw_post_var"] for rr in r if rr["hw_post_var"] > 0]
        edge_s = f"{np.mean(edge):.4f}" if edge else "N/A"
        xi_s = f"{np.mean(xi):.3f}" if xi else "N/A"
        pv_s = f"{np.mean(post_var):.1f}" if post_var else "N/A"
        print(f"{s:>6.1f} | {rate:>7.2f} | {hw:>6.0f} | {edge_s:>8} | {xi_s:>6} | {pv_s:>8}")

    # 保存
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_filename = os.path.join(RESULTS_DIR, f"exp157_phase13_p3_multi_subspace_{timestamp}.json")

    save_data = {
        "experiment": "exp_157",
        "phase": "13_p3",
        "version": "revised",
        "description": "Template growth via post-seal step_callback — sealed bits bias injection locations",
        "timestamp": timestamp,
        "params": {
            "N": N,
            "total_steps": TOTAL_STEPS,
            "post_seal_steps": POST_SEAL_STEPS,
            "n_runs": N_RUNS,
            "template_strengths": TEMPLATE_STRENGTHS,
        },
        "results": {
            str(s): {
                "seal_rate": float(np.mean([rr["sealed"] for rr in r])),
                "hw_mean": float(np.mean([rr["final_hw"] for rr in r if rr["sealed"]])),
                "edge_mean": float(np.mean([rr["edge_mean_dist"] for rr in r if rr["edge_mean_dist"] > 0])),
                "edge_std": float(np.std([rr["edge_mean_dist"] for rr in r if rr["edge_mean_dist"] > 0])),
                "xi_mean": float(np.mean([rr["corr_length"] for rr in r if rr["corr_length"] > 0])),
                "xi_std": float(np.std([rr["corr_length"] for rr in r if rr["corr_length"] > 0])),
                "hw_post_var_mean": float(np.mean([rr["hw_post_var"] for rr in r if rr["hw_post_var"] > 0])),
                "per_seed": [
                    {"seed": rr["seed"], "sealed": rr["sealed"], "hw": rr["final_hw"],
                     "edge": rr["edge_mean_dist"], "xi": rr["corr_length"]}
                    for rr in r
                ],
            }
            for s, r in all_results.items()
        },
        "hypotheses": {
            "H157-1_template_growth": h157_1,
            "H157-2_structural_inheritance": h157_2,
            "H157-3_memory": h157_3,
        },
    }

    with open(result_filename, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    print(f"\n结果保存至: {result_filename}")

    # 写入结果 MD
    md_path = os.path.join(RESULTS_DIR, f"exp157_result_{timestamp}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"""# exp_157 执行结果 — Phase 13 P3 多子空间耦合（修订版）

## 实验参数
- N={N}
- 模板增长强度扫描: {TEMPLATE_STRENGTHS}
- 每条件: {N_RUNS} 种子

## 跨强度对比

| 强度 | 密封率 | HW | 边缘距离 | ξ | HW后方差 |
|------|--------|-----|----------|-----|---------|
""")
        for s in TEMPLATE_STRENGTHS:
            r = all_results[str(s)]
            rate = sum(rr["sealed"] for rr in r) / len(r)
            hw = float(np.mean([rr["final_hw"] for rr in r if rr["sealed"]])) if any(rr["sealed"] for rr in r) else 0
            edge = [rr["edge_mean_dist"] for rr in r if rr["edge_mean_dist"] > 0]
            xi = [rr["corr_length"] for rr in r if rr["corr_length"] > 0]
            pv = [rr["hw_post_var"] for rr in r if rr["hw_post_var"] > 0]
            edge_s = f"{np.mean(edge):.4f}" if edge else "N/A"
            xi_s = f"{np.mean(xi):.3f}" if xi else "N/A"
            pv_s = f"{np.mean(pv):.1f}" if pv else "N/A"
            f.write(f"| {s:.1f} | {rate:.2f} | {hw:.0f} | {edge_s} | {xi_s} | {pv_s} |\n")

        f.write(f"""
## 假设检验
- H157-1 (模板生长): **{'确认' if h157_1 else '拒绝'}**
- H157-2 (结构继承): **{'确认' if h157_2 else '拒绝'}**
- H157-3 (记忆保存): **{'确认' if h157_3 else '拒绝'}**

## 科学意义
（运行后分析）
""")

    print(f"结果 MD: {md_path}")


if __name__ == "__main__":
    main()