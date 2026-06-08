"""
exp_167 — Phase 15 Path B2: Correlated Injection

科学问题：
  Path B1 证明注入方向反转不影响死秩序 — 系统在 0↔1 下完全对称。
  但所有实验至今都注入**随机独立差异**。差异论 §5 区分「差异」(random flips)
  和「信息」(structural patterns)。如果死秩序的抵抗只针对随机差异，
  结构性模式可能在密封结构内部创造自指涉回路。

核心假设：
  H15-B3 (Correlation matters): 只有随机差异被密封结构「吸收」。
    结构性关联差异（成对联动、链式传播）能在密封内部产生新的关联模式，
    这些关联模式可能抵抗密封的均质化效应。
    
  H15-B4 (Spatial coherence): 空间邻近的成对注入比随机配对注入更有效，
    因为空间相关性更可能被 L0 层的横向演化所捕获。

实验设计：
  - 4 种注入模式 × 2 种强度 = 8 条件 + 1 baseline = 9 条件
  - N=48, 总步数 1200
  - 注入发生在每一步（标准注入后，通过 step_callback 追加）

注入模式：
  1. 标准随机单比特 (standard) — 对照组
  2. 空间邻近配对 (adjacent pair) — 两个相邻比特同时翻转
  3. 随机远距配对 (random pair) — 两个随机比特同时翻转
  4. 链式注入 (chain) — 翻转一个比特，下一时间步翻转其邻居

用法：
  cd C:/Users/Administrator/Documents/the_theory_of_difference\11-模拟机工程实现
  python experiments/exp_167_phase15_b2_correlated_injection.py
"""

import sys, os, math, json, datetime, time
import numpy as np
import torch
import contextlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver


# ============================================================
# 参数
# ============================================================
N = 48
TOTAL_STEPS = 1200
SAMPLE_INTERVAL = 50
N_RUNS = 1
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 关联注入条件
# ============================================================
INJECTION_MODES = {
    'standard':        '随机单比特注入（对照组）',
    'adjacent_pair':   '空间邻近配对（两相邻比特同时翻转）',
    'random_pair':     '随机远距配对（两任意比特同时翻转）',
    'chain':           '链式注入（每时间步一个，传播到邻居）',
}
INJECTION_STRENGTHS = [1, 3]  # 每步注入的单元数量

CONDITIONS = []
for mode_name in INJECTION_MODES:
    for strength in INJECTION_STRENGTHS:
        CONDITIONS.append({
            'label': f'{mode_name}_s{strength}',
            'mode': mode_name,
            'strength': strength,
        })

CONDITIONS.insert(0, {
    'label': 'baseline',
    'mode': 'none',
    'strength': 0,
})

print(f"Total conditions: {len(CONDITIONS)} (including baseline)")
print(f"Total runs: {len(CONDITIONS) * N_RUNS}")
print(f"Modes: {list(INJECTION_MODES.keys())}")


# ============================================================
# 关联注入回调
# ============================================================
class CorrelatedInjector:
    """管理关联注入的状态和操作"""

    def __init__(self, mode: str, strength: int, seed: int):
        self.mode = mode
        self.strength = strength
        self.rng = np.random.RandomState(seed)
        self.chain_target = None  # For chain mode: target to propagate to
        self.total_injected = 0

    def _find_standard_candidates(self, state, constraints):
        """Find bits at 0 with direction >= 0 (standard injection)"""
        return [i for i in range(state.numel())
                if state[i].item() < 0.5
                and constraints.direction[i].item() >= 0]

    def _find_chain_source(self, state, constraints):
        """For chain mode: find a 0-bit with direction >= 0 near chain_target"""
        if self.chain_target is not None:
            # Propagate from chain_target to its neighbors (cyclic)
            N_state = state.numel()
            neighbors = [(self.chain_target - 1) % N_state,
                         (self.chain_target + 1) % N_state]
            for n in neighbors:
                if state[n].item() < 0.5 and constraints.direction[n].item() >= 0:
                    self.chain_target = n
                    return [n]
        # If no valid neighbor, start new chain randomly
        candidates = self._find_standard_candidates(state, constraints)
        if candidates:
            self.chain_target = int(self.rng.choice(candidates))
            return [self.chain_target]
        return []

    def inject(self, step: int, state: torch.Tensor, constraints) -> int:
        """执行一次关联注入，返回注入的比特数"""
        if constraints.sealed:
            return 0

        actual_injected = 0
        N_state = state.numel()

        if self.mode == 'standard':
            # 单比特随机注入（对照组）
            candidates = self._find_standard_candidates(state, constraints)
            if candidates:
                n_choose = min(self.strength, len(candidates))
                chosen = self.rng.choice(candidates, size=n_choose, replace=False)
                for idx in chosen:
                    state[idx] = 1.0
                    constraints.direction[idx] = 1
                    self.total_injected += 1
                    actual_injected += 1

        elif self.mode in ('adjacent_pair', 'random_pair'):
            # 成对注入（同时翻转两个比特）
            candidates = self._find_standard_candidates(state, constraints)
            if len(candidates) < 2:
                return 0

            n_pairs = min(self.strength, len(candidates) // 2)
            used = set()

            for _ in range(n_pairs):
                remaining = [c for c in candidates if c not in used]
                if len(remaining) < 2:
                    break

                # 选择第一个比特
                first = int(self.rng.choice(remaining))
                used.add(first)

                # 选择第二个比特
                if self.mode == 'adjacent_pair':
                    # 空间邻近：距离为 1
                    neighbors = [(first - 1) % N_state, (first + 1) % N_state]
                    second_candidates = [n for n in neighbors
                                         if n in candidates and n not in used]
                else:
                    # 随机远距
                    remaining2 = [c for c in candidates if c not in used]
                    if not remaining2:
                        break
                    second_candidates = [int(self.rng.choice(remaining2))]

                if not second_candidates:
                    used.discard(first)
                    continue

                second = second_candidates[0]
                used.add(second)

                # 同时注入
                state[first] = 1.0
                state[second] = 1.0
                constraints.direction[first] = 1
                constraints.direction[second] = 1
                self.total_injected += 2
                actual_injected += 2

        elif self.mode == 'chain':
            # 链式注入：每一步传播到相邻位置
            for _ in range(self.strength):
                targets = self._find_chain_source(state, constraints)
                for idx in targets:
                    state[idx] = 1.0
                    constraints.direction[idx] = 1
                    self.total_injected += 1
                    actual_injected += 1

        return actual_injected


def make_correlated_callback(mode: str, strength: int, seed: int):
    """创建关联注入回调"""
    injector = CorrelatedInjector(mode, strength, seed)

    def _callback(step: int, state: torch.Tensor,
                  snapshot: object, constraints: object) -> None:
        injector.inject(step, state, constraints)

    # Attach injector for stats
    _callback.injector = injector
    return _callback


# ============================================================
# 单次运行
# ============================================================
def run_single(condition: dict, run_id: int) -> dict:
    label = condition['label']
    mode = condition['mode']
    strength = condition['strength']

    seed = run_id * 31337 + 167 + hash(label) % 100000
    rng = np.random.RandomState(seed % (2**31))
    torch.manual_seed(seed % (2**31))

    # 初始状态：~6 个 1
    initial = torch.zeros(N)
    n_ones = rng.randint(4, min(10, N // 2))
    indices = rng.choice(N, size=n_ones, replace=False)
    initial[indices] = 1.0

    # 创建回调
    if mode != 'none':
        callback = make_correlated_callback(mode, strength, seed + 999)
    else:
        callback = None

    evolver = SpatialLongRangeEvolver(
        N=N,
        total_steps=TOTAL_STEPS,
        sample_interval=SAMPLE_INTERVAL,
        partial_sealing=False,
    )

    t0 = time.time()
    with contextlib.redirect_stdout(open(os.devnull, 'w')):
        result = evolver.run(initial_state=initial, verbose=False,
                             step_callback=callback)
    elapsed = time.time() - t0

    # Stats
    hw_traj = np.array(evolver.hamming_weight_history)
    seal_step = evolver.seal_step if evolver.seal_step >= 0 else len(hw_traj) // 2
    sealed_bits = evolver.constraints.sealed_bits
    n_sealed = len(sealed_bits)

    seal_snap_idx = None
    for idx, snap in enumerate(evolver.snapshots):
        if snap.step >= seal_step:
            seal_snap_idx = idx
            break
    if seal_snap_idx is None:
        seal_snap_idx = len(evolver.snapshots) // 2

    post_hw = hw_traj[seal_snap_idx:] if seal_snap_idx < len(hw_traj) else hw_traj[-50:]
    post_hw_mean = float(post_hw.mean()) if len(post_hw) > 0 else 0.0
    post_hw_var = float(post_hw.var()) if len(post_hw) > 1 else 0.0

    post_seal_flip_positions = []
    for i in range(seal_snap_idx, len(evolver.snapshots) - 1):
        s1 = evolver.snapshots[i].state
        s2 = evolver.snapshots[i + 1].state
        diff = (s2 - s1).abs()
        flipped = torch.where(diff > 0.5)[0].tolist()
        post_seal_flip_positions.extend(flipped)

    if n_sealed > 0 and len(post_seal_flip_positions) > 0:
        sealed_array = np.array(sorted(sealed_bits))
        dists = []
        for fp in post_seal_flip_positions:
            if fp not in sealed_bits:
                dist = min(abs(fp - s) for s in sealed_array)
                dists.append(dist)
        dists = np.array(dists)
        mean_flip_dist = float(dists.mean()) if len(dists) > 0 else N
        n_boundary = int(np.sum(dists <= 3)) if len(dists) > 0 else 0
        n_non_boundary = int(np.sum(dists > 3)) if len(dists) > 0 else 0
    else:
        mean_flip_dist = N
        n_boundary = 0
        n_non_boundary = 0

    n_post_flips = len(post_seal_flip_positions)

    direction_arr = evolver.constraints.direction.cpu().numpy()
    n_dir_pos = int(np.sum(direction_arr > 0))
    n_dir_neg = int(np.sum(direction_arr < 0))
    total_dir = n_dir_pos + n_dir_neg
    dir_balance = abs(n_dir_pos - n_dir_neg) / max(total_dir, 1) if total_dir > 0 else 0.0

    if n_sealed > 0:
        sealed_dir_pos = sum(1 for i in sealed_bits if direction_arr[i] > 0)
        sealed_dir_neg = sum(1 for i in sealed_bits if direction_arr[i] < 0)
        sealed_dir_balance = abs(sealed_dir_pos - sealed_dir_neg) / max(n_sealed, 1)
    else:
        sealed_dir_balance = 0.0

    sealed_ratio = n_sealed / N
    is_over_sealed = sealed_ratio > 0.45

    # Find extra injected count
    extra_injected = getattr(callback, 'injector', None).total_injected if callback else 0
    total_injected = evolver.constraints.total_injected + extra_injected

    return {
        'condition_label': label,
        'mode': mode,
        'strength': strength,
        'run_id': run_id,
        'seed': seed,
        'extra_injected': extra_injected,
        'total_injected': total_injected,
        'sealed': evolver.constraints.sealed,
        'n_sealed': n_sealed,
        'sealed_ratio': sealed_ratio,
        'is_over_sealed': is_over_sealed,
        'seal_step': seal_step,
        'post_seal_steps': len(hw_traj) - seal_step,
        'post_hw_mean': post_hw_mean,
        'post_hw_var': post_hw_var,
        'n_post_flips': n_post_flips,
        'post_flip_rate': n_post_flips / max(len(hw_traj) - seal_step, 1),
        'mean_flip_dist_to_sealed': mean_flip_dist,
        'n_boundary_flips': n_boundary,
        'n_non_boundary_flips': n_non_boundary,
        'boundary_flip_ratio': n_boundary / max(n_post_flips, 1),
        'n_dir_pos': n_dir_pos,
        'n_dir_neg': n_dir_neg,
        'dir_balance': float(dir_balance),
        'sealed_dir_balance': sealed_dir_balance,
        'correlation_length': int(np.argmax(np.correlate(
            post_hw - post_hw.mean(),
            post_hw - post_hw.mean(),
            mode='full'
        )[len(post_hw)//2:] / max(
            np.var(post_hw) * len(post_hw), 1e-10) < 1/math.e
        )) if len(post_hw) > 10 and np.var(post_hw) > 1e-10 else 0,
        'elapsed_sec': round(elapsed, 2),
    }


# ============================================================
# 分析 + 打印
# ============================================================
def analyze_results(all_metrics: list) -> dict:
    by_cond = {}
    for m in all_metrics:
        label = m['condition_label']
        if label not in by_cond:
            by_cond[label] = []
        by_cond[label].append(m)

    analysis = {'by_condition': {}}
    for label in sorted(by_cond.keys()):
        group = by_cond[label]
        n_total = len(group)
        c = {}
        for key in ['sealed', 'is_over_sealed']:
            c[key] = float(np.mean([m[key] for m in group]))
        for key in ['post_flip_rate', 'boundary_flip_ratio',
                     'post_hw_var', 'dir_balance', 'mean_flip_dist_to_sealed']:
            vals = [m[key] for m in group]
            c[f'{key}_mean'] = float(np.mean(vals))
            if len(vals) > 1:
                c[f'{key}_std'] = float(np.std(vals))
            else:
                c[f'{key}_std'] = 0.0
        c['total_injected_mean'] = float(np.mean([m['total_injected'] for m in group]))
        c['n_runs'] = n_total
        c['over_sealed_rate'] = c['is_over_sealed']
        analysis['by_condition'][label] = c

    ranked = sorted(analysis['by_condition'].items(),
                    key=lambda x: x[1]['post_flip_rate_mean'], reverse=True)
    analysis['ranked_by_activity'] = [
        {'label': l, 'post_flip_rate': c['post_flip_rate_mean'],
         'boundary_ratio': c['boundary_flip_ratio_mean'],
         'over_sealed_rate': c['over_sealed_rate'],
         'hw_var': c['post_hw_var_mean']}
        for l, c in ranked]

    return analysis


def print_results(analysis: dict):
    print(f"\n{'=' * 110}")
    print("Phase 15 Path B2: Correlated Injection — Results (exp_167)")
    print("=" * 110)

    by_cond = analysis['by_condition']
    ranked = analysis['ranked_by_activity']

    header = (f"{'Condition':24s} {'Seal':>6s} {'FlipRate':>8s} {'Bound%':>7s} "
              f"{'Dist':>5s} {'HWvar':>7s} {'OverS':>6s} {'Injected':>8s}")
    print(f"\n{header}")
    print("-" * 110)

    for item in ranked:
        label = item['label']
        cs = by_cond[label]
        se = f"{cs.get('sealed',0)*100:4.0f}%"
        fr = f"{cs['post_flip_rate_mean']:.4f}"
        br = f"{cs['boundary_flip_ratio_mean']*100:5.1f}%"
        dd = f"{cs['mean_flip_dist_to_sealed_mean']:.1f}"
        hv = f"{cs['post_hw_var_mean']:.3f}"
        os_ = f"{cs['over_sealed_rate']*100:4.0f}%"
        ti = f"{cs['total_injected_mean']:.0f}"
        print(f"  {label:24s} {se:>6s} {fr:>8s} {br:>7s} {dd:>5s} {hv:>7s} {os_:>6s} {ti:>8s}")

    print(f"\n{'=' * 110}")

    # By mode
    print("\n  --- By Injection Mode ---")
    for mode_name in INJECTION_MODES:
        mode_conds = [(l, c) for l, c in by_cond.items()
                      if l.startswith(f'{mode_name}_')]
        if not mode_conds:
            continue
        avg_flip = np.mean([c['post_flip_rate_mean'] for _, c in mode_conds])
        avg_bound = np.mean([c['boundary_flip_ratio_mean'] for _, c in mode_conds])
        avg_over = np.mean([c['over_sealed_rate'] for _, c in mode_conds])
        print(f"    {mode_name:16s}: flip_rate={avg_flip:.4f}, "
              f"boundary%={avg_bound*100:.1f}%, over_sealed%={avg_over*100:.0f}%")

    # Verdict
    print(f"\n  {'=' * 60}")
    print(f"  Hypothesis Verdict")
    print(f"  {'=' * 60}")

    max_over = max(c['over_sealed_rate'] for c in by_cond.values())
    if max_over > 0.2:
        print(f"  [STRONG] H15-B3 (Correlation): OVER-SEALED — "
              f"max_over_sealed={max_over*100:.0f}%")
    else:
        print(f"  [NO] H15-B3 (Correlation): No secondary sealing — "
              f"max_over_sealed={max_over*100:.0f}%")

    # Check if spatial modes differ from random
    if max_over <= 0.2:
        print(f"\n  === FINAL: Path B2 REJECTED — Correlated injection fails ===")
    else:
        print(f"\n  === FINAL: Path B2 SHOWS SIGNAL ===")

    print(f"\n  {sum(c['n_runs'] for c in by_cond.values())} runs, "
          f"{len(by_cond)} conditions")


def run_experiment():
    print("=" * 110)
    print("Phase 15 Path B2: Correlated Injection (exp_167)")
    print("=" * 110)
    print(f"  N={N}, steps={TOTAL_STEPS}, sample_interval={SAMPLE_INTERVAL}")
    print(f"  Conditions: {len(CONDITIONS)}")
    print(f"  Modes: {list(INJECTION_MODES.keys())}")
    print(f"  Strengths: {INJECTION_STRENGTHS}")
    print("=" * 110)

    all_metrics = []
    t_start = time.time()
    run_count = 0
    total_runs = len(CONDITIONS)

    baseline_cond = [c for c in CONDITIONS if c['mode'] == 'none']
    other_conds = [c for c in CONDITIONS if c['mode'] != 'none']

    for cond in baseline_cond + other_conds:
        label = cond['label']
        print(f"\n--- {label} ---")
        for run_id in range(N_RUNS):
            metrics = run_single(cond, run_id)
            all_metrics.append(metrics)
            run_count += 1

        elapsed_so_far = time.time() - t_start
        rate = run_count / max(1, elapsed_so_far)
        eta = (total_runs - run_count) / max(rate, 0.001)
        nf_val = metrics.get('n_post_flips', 0)
        print(f"    total {run_count}/{total_runs} | flips={nf_val} | "
              f"{elapsed_so_far:.0f}s elapsed, ~{eta:.0f}s remaining")

    t_total = time.time() - t_start
    print(f"\nTotal time: {t_total:.0f}s")

    analysis = analyze_results(all_metrics)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR,
                               f"exp167_phase15_b2_correlated_{timestamp}.json")

    save_metrics = [{k: (int(v) if isinstance(v, (np.integer,)) else
                         float(v) if isinstance(v, (np.floating,)) else
                         v.tolist() if isinstance(v, np.ndarray) else v)
                     for k, v in m.items()} for m in all_metrics]

    save_data = {
        'params': {'N': N, 'total_steps': TOTAL_STEPS, 'n_runs': N_RUNS,
                   'n_conditions': len(CONDITIONS),
                   'timestamp': timestamp, 'experiment': 'exp_167'},
        'analysis': {'by_condition': {k: dict(v) for k, v in analysis['by_condition'].items()},
                     'ranked_by_activity': analysis['ranked_by_activity']},
        'metrics': save_metrics,
    }

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f"\n=== Saved: {result_file}")

    print_results(analysis)


if __name__ == '__main__':
    run_experiment()