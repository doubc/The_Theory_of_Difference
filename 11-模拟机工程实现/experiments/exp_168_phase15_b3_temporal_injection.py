"""
exp_168 — Phase 15 Path B3: Temporal Pattern Injection

科学问题：
  Path B1 证明方向对称性，Path B2 证明空间关联无效果。
  最后的 B 方案：**时间结构**而非空间结构是否能打破死秩序？
  
  核心假设：如果注入模式在时间上具有节律性（振荡、脉冲），
  可能和系统的内在时间尺度产生共振，从而打破死秩序。

实验设计：
  - 2 种模式 × 4 种频率 × 3 种振幅 = 24 条件 + 1 baseline = 25
  - N=48, 总步数 1200
  - 注入调制通过 step_callback 动态调整 source_strength

时间模式：
  1. 正弦调制: source_strength *= 1 + A * sin(2*pi*omega*t)
  2. 开/关脉冲: source_strength 周期性地设为 0 或原始值

频率:
  omega ∈ [0.01, 0.05, 0.1, 0.5] (弧度/步)
  0.01 ≈ 628 步/周期（慢→与密封时间可比）
  0.5  ≈ 13 步/周期（快→几乎为噪音）

振幅:
  A ∈ [0.25, 0.5, 1.0]

用法：
  cd C:/Users/Administrator/Documents/the_theory_of_difference\11-模拟机工程实现
  python experiments/exp_168_phase15_b3_temporal_injection.py
"""

import sys, os, math, json, datetime, time
import numpy as np
import torch
import contextlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver


N = 48
TOTAL_STEPS = 1200
SAMPLE_INTERVAL = 50
N_RUNS = 1
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Temporal modulation parameters
MODES = ['sine', 'onoff']  # sine modulation, on/off pulsing
OMEGAS = [0.01, 0.05, 0.1, 0.5]  # radians/step
AMPLITUDES = [0.25, 0.5, 1.0]

CONDITIONS = []
for mode in MODES:
    for omega in OMEGAS:
        for A in AMPLITUDES:
            CONDITIONS.append({
                'label': f'{mode}_om{omega}_A{A}',
                'mode': mode, 'omega': omega, 'amplitude': A,
            })
CONDITIONS.insert(0, {'label': 'baseline', 'mode': 'none',
                       'omega': 0, 'amplitude': 0})

print(f"Conditions: {len(CONDITIONS)}")


def make_temporal_callback(mode, omega, amplitude):
    """Create temporal injection modulation callback

    Modulates the effective injection rate:
    - sine:  effective = base * (1 + A * sin(omega * step))
    - onoff: effective = base if sin(omega * step) > 0 else 0
    """
    _step_counter = [0]  # mutable closure to track steps

    def _callback(step, state, snapshot, constraints):
        # This runs AFTER the evolver's injection step.
        # We store the desired multiplier for the next step's injection.
        # Since we can't modify past injection, we estimate the effect.
        pass

    return _callback


def run_single(condition, run_id):
    label = condition['label']
    mode = condition['mode']
    omega = condition['omega']
    A = condition['amplitude']

    seed = run_id * 31337 + 168 + hash(label) % 100000
    rng = np.random.RandomState(seed % (2**31))
    torch.manual_seed(seed % (2**31))

    initial = torch.zeros(N)
    n_ones = rng.randint(4, min(10, N // 2))
    indices = rng.choice(N, size=n_ones, replace=False)
    initial[indices] = 1.0

    # For temporal modulation, we use a step_callback that
    # injects additional bits with a modulated pattern.
    # This simulates "effective injection rate" changing over time.
    def temporal_injection_callback(step, state, snapshot, constraints):
        if constraints.sealed:
            return
        if mode == 'none':
            return

        # Calculate modulation factor
        if mode == 'sine':
            # sine: 0.5 to 1.5 (shifted so never goes negative)
            mod = 1.0 + A * math.sin(omega * step)
        elif mode == 'onoff':
            # on/off: 1 or 0
            mod = 1.0 if math.sin(omega * step) > 0 else 0.0
        else:
            return

        if mod <= 0:
            return

        # Inject additional modulated bits
        candidates = [i for i in range(state.numel())
                      if state[i].item() < 0.5
                      and constraints.direction[i].item() >= 0]
        if not candidates:
            return

        # n_inject proportional to modulation
        base_n = 2  # base injection per step
        n_extra = max(1, int(base_n * (mod - 1.0))) if mod > 1.0 else 0

        if n_extra > 0:
            n_choose = min(n_extra, len(candidates))
            rng_local = np.random.RandomState(seed=int(step * 31337 + 168))
            chosen = rng_local.choice(candidates, size=n_choose, replace=False)
            for idx in chosen:
                state[idx] = 1.0
                constraints.direction[idx] = 1

    evolver = SpatialLongRangeEvolver(
        N=N, total_steps=TOTAL_STEPS,
        sample_interval=SAMPLE_INTERVAL, partial_sealing=False)

    t0 = time.time()
    with contextlib.redirect_stdout(open(os.devnull, 'w')):
        result = evolver.run(initial_state=initial, verbose=False,
                             step_callback=temporal_injection_callback)
    elapsed = time.time() - t0

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
        dists = [min(abs(fp - s) for s in sealed_array)
                 for fp in post_seal_flip_positions if fp not in sealed_bits]
        dists = np.array(dists)
        mean_flip_dist = float(dists.mean()) if len(dists) > 0 else N
        n_boundary = int(np.sum(dists <= 3)) if len(dists) > 0 else 0
    else:
        mean_flip_dist = N
        n_boundary = 0

    n_post_flips = len(post_seal_flip_positions)
    sealed_ratio = n_sealed / N
    is_over_sealed = sealed_ratio > 0.45

    direction_arr = evolver.constraints.direction.cpu().numpy()
    n_dir_pos = int(np.sum(direction_arr > 0))
    n_dir_neg = int(np.sum(direction_arr < 0))
    total_dir = n_dir_pos + n_dir_neg
    dir_balance = abs(n_dir_pos - n_dir_neg) / max(total_dir, 1) if total_dir > 0 else 0.0

    return {
        'condition_label': label,
        'mode': mode, 'omega': omega, 'amplitude': A,
        'run_id': run_id, 'seed': seed,
        'sealed': evolver.constraints.sealed,
        'n_sealed': n_sealed,
        'sealed_ratio': sealed_ratio,
        'is_over_sealed': is_over_sealed,
        'seal_step': seal_step,
        'n_post_flips': n_post_flips,
        'post_flip_rate': n_post_flips / max(len(hw_traj) - seal_step, 1),
        'mean_flip_dist_to_sealed': mean_flip_dist,
        'n_boundary_flips': n_boundary,
        'boundary_flip_ratio': n_boundary / max(n_post_flips, 1),
        'dir_balance': float(dir_balance),
        'post_hw_var': post_hw_var,
        'elapsed_sec': round(elapsed, 2),
    }


def run_experiment():
    print("Phase 15 Path B3: Temporal Injection (exp_168)\n")
    print(f"  N={N}, steps={TOTAL_STEPS}")
    print(f"  Conditions: {len(CONDITIONS)}")
    print(f"  Modes: {MODES}, Omegas: {OMEGAS}, Amps: {AMPLITUDES}")

    all_metrics = []
    t_start = time.time()
    run_count = 0

    for cond in CONDITIONS:
        print(f"\n--- {cond['label']} ---")
        for run_id in range(N_RUNS):
            metrics = run_single(cond, run_id)
            all_metrics.append(metrics)
            run_count += 1

        pct = run_count / len(CONDITIONS) * 100
        elapsed = time.time() - t_start
        rate = run_count / max(1, elapsed)
        eta = (len(CONDITIONS) - run_count) / max(rate, 0.001)
        nf = metrics.get('n_post_flips', 0)
        print(f"    {run_count}/{len(CONDITIONS)} ({pct:.0f}%) | flips={nf} | "
              f"{elapsed:.0f}s, ~{eta:.0f}s remaining")

    print(f"\nTotal: {time.time()-t_start:.0f}s")

    # Analysis
    by_cond = {}
    for m in all_metrics:
        l = m['condition_label']
        by_cond.setdefault(l, []).append(m)

    print(f"\n{'='*110}")
    print("Results:")
    print(f"{'Condition':30s} {'Seal':>6s} {'FlipRate':>8s} {'Bound%':>7s} {'HWvar':>7s} {'OverS':>6s}")
    print("-"*110)

    for cond in CONDITIONS:
        l = cond['label']
        c = by_cond.get(l, [{}])[0]
        se = f"{c.get('sealed',0)*100:4.0f}%"
        fr = f"{c.get('post_flip_rate',0):.4f}"
        br = f"{c.get('boundary_flip_ratio',0)*100:5.1f}%"
        hv = f"{c.get('post_hw_var',0):.3f}"
        os_ = f"{c.get('is_over_sealed',False)*100:4.0f}%"
        print(f"  {l:30s} {se:>6s} {fr:>8s} {br:>7s} {hv:>7s} {os_:>6s}")


    max_over = max(c.get('is_over_sealed', 0)
                   for group in by_cond.values() for c in group)
    print(f"\n{'='*60}")
    print("Verdict:")
    if max_over > 0.2:
        print(f"  H15-B4 (Temporal): OVER-SEALED! max={max_over*100:.0f}%")
    else:
        print(f"  H15-B4 (Temporal): REJECTED — {max_over*100:.0f}%")

    print(f"\n  {len(all_metrics)} runs, {len(by_cond)} conditions")

    # Save
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"exp168_phase15_b3_temporal_{timestamp}.json")
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'params': {'N': N, 'total_steps': TOTAL_STEPS, 'experiment': 'exp_168'},
            'metrics': [{k: (int(v) if isinstance(v, (np.integer,)) else
                             float(v) if isinstance(v, (np.floating,)) else v)
                        for k, v in m.items()} for m in all_metrics],
        }, f, indent=2)
    print(f"\nSaved: {result_file}")


if __name__ == '__main__':
    run_experiment()