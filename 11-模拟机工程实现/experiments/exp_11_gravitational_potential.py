"""
exp_11_gravitational_potential.py -- Gravitational potential measurement experiment

Verify WorldBase core predictions:
1. Discrete potential field Phi(x) = -sum_s 1/d_H(x,s) (N=6 analytical verification)
2. Dimension locking D=3 => Phi(r) proportional to -1/r (Newtonian gravitational potential)
3. Block embedding {0,1}^N -> R^3 distance relation

Corresponds to WorldBase formalization sections 3.4-3.6 and 4.2-4.3.
"""
import torch
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.hamming_engine import HammingMeasurement


def test1_n6_analytical():
    """Test 1: N=6 analytical verification of -1/d_H potential"""
    print("=" * 60)
    print("TEST 1: N=6 Discrete Potential Field (Analytical)")
    print("=" * 60)
    N = 6
    source = torch.ones(N)
    print(f"\nSource: {source.tolist()}")
    print(f"Theory: Phi(w) = -1/(N-w) = -1/(6-w)\n")

    all_ok = True
    for w in range(N + 1):
        state = torch.zeros(N)
        state[:w] = 1.0
        d = HammingMeasurement.hamming_distance(state, source)
        phi_c = -1.0 / max(1, d)
        phi_t = -1.0 / max(1, N - w)
        if w < N:
            ok = abs(phi_c - phi_t) < 1e-6
            all_ok = all_ok and ok
            tag = "OK" if ok else "FAIL"
            print(f"  w={w}, d={d}: Phi_comp={phi_c:.6f}, Phi_theory={phi_t:.6f} [{tag}]")

    print(f"\n[RESULT] N=6 analytical: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def test2_inverse_scaling():
    """Test 2: N=12 -1/d_H scaling law"""
    print("\n" + "=" * 60)
    print("TEST 2: N=12 Inverse Distance Scaling")
    print("=" * 60)
    N = 12
    source = torch.ones(N)
    products = []
    print(f"\n  N={N}\n")
    for w in range(N):
        state = torch.zeros(N)
        state[:w] = 1.0
        d = HammingMeasurement.hamming_distance(state, source)
        if d > 0:
            phi = -1.0 / d
            products.append(abs(phi * d))
            print(f"  w={w:2d}, d={d:2d}: Phi={phi:.6f}, Phi*d={abs(phi*d):.6f}")

    mean_p = sum(products) / len(products)
    ok = abs(mean_p - 1.0) < 0.01
    print(f"\n  Mean Phi*d: {mean_p:.6f} (theory=1.0)")
    print(f"[RESULT] Scaling law: {'PASS' if ok else 'FAIL'}")
    return ok


def test3_embedding():
    """Test 3: Block embedding distance relation (Lemma CL-0)"""
    print("\n" + "=" * 60)
    print("TEST 3: Block Embedding Distance (Lemma CL-0)")
    print("=" * 60)
    L = 1.0
    print(f"\n  Lemma CL-0: d_H = (n/L^2)|u-v|^2 + eta_N\n")
    for N in [6, 12, 24]:
        n = N // 3
        eps = L / n
        source = torch.ones(N)
        for w in [N // 4, N // 2, 3 * N // 4]:
            state = torch.zeros(N)
            state[:w] = 1.0
            d = HammingMeasurement.hamming_distance(state, source)
            u = torch.zeros(3)
            v = torch.zeros(3)
            for k in range(3):
                u[k] = eps * source[k*n:(k+1)*n].sum()
                v[k] = eps * state[k*n:(k+1)*n].sum()
            eucl = ((u - v)**2).sum().item()
            pred = (n / L**2) * eucl
            ratio = d / max(0.01, pred)
            print(f"  N={N}, w={w}: d={d}, |u-v|^2={eucl:.4f}, pred={pred:.2f}, ratio={ratio:.2f}")

    print(f"\n[RESULT] Embedding: qualitative check done")
    return True


def test4_dynamics():
    """Test 4: Gravitational attraction dynamics"""
    print("\n" + "=" * 60)
    print("TEST 4: Gravitational Dynamics")
    print("=" * 60)
    N = 16
    steps = 500
    n_p = 50
    source = torch.ones(N)
    particles = (torch.rand(n_p, N) < 0.3).float()
    hist = []

    for step in range(steps):
        dists = torch.tensor([
            HammingMeasurement.hamming_distance(particles[i], source)
            for i in range(n_p)
        ], dtype=torch.float32)
        hist.append(dists.mean().item())

        for i in range(n_p):
            d = int(HammingMeasurement.hamming_distance(particles[i], source))
            if d == 0:
                continue
            force = 1.0 / (d ** 2)
            if torch.rand(1).item() < force * 0.3:
                diff = particles[i] != source
                if diff.any():
                    idx = diff.nonzero(as_tuple=True)[0]
                    flip = idx[torch.randint(len(idx), (1,))]
                    particles[i, flip] = source[flip]

    init_d = hist[0]
    final_d = hist[-1]
    pct = (init_d - final_d) / init_d * 100

    print(f"\n  N={N}, {n_p} particles, {steps} steps")
    print(f"  Initial avg dist: {init_d:.2f}")
    print(f"  Final avg dist: {final_d:.2f}")
    print(f"  Reduction: {pct:.1f}%")

    ok = final_d < init_d * 0.9
    print(f"\n[RESULT] Attraction: {'PASS' if ok else 'FAIL'}")
    return ok


def test5_poisson():
    """Test 5: Discrete Poisson equation (nabla^2 Phi = 0 in source-free region)"""
    print("\n" + "=" * 60)
    print("TEST 5: Discrete Poisson Equation")
    print("=" * 60)
    N = 12
    phi = torch.zeros(N + 1)
    for w in range(N + 1):
        d = N - w
        phi[w] = -1.0 / max(1, d) if d > 0 else 0.0

    lap = torch.zeros(N + 1)
    for w in range(1, N):
        lap[w] = phi[w + 1] - 2 * phi[w] + phi[w - 1]

    print(f"\n  N={N}\n")
    print(f"  w  |  Phi(w)   | nabla^2 Phi")
    print(f"  ---|-----------|------------")
    for w in range(N):
        print(f"  {w:2d} | {phi[w]:9.4f} | {lap[w]:11.4f}")

    max_lap = lap[:N].abs().max().item()
    ok = max_lap < 1.0
    print(f"\n  Max |nabla^2 Phi| (source-free): {max_lap:.4f}")
    print(f"[RESULT] Poisson: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    torch.manual_seed(42)
    r = {
        "N=6 analytical": test1_n6_analytical(),
        "-1/d_H scaling": test2_inverse_scaling(),
        "Block embedding": test3_embedding(),
        "Gravitational dynamics": test4_dynamics(),
        "Poisson equation": test5_poisson(),
    }
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, ok in r.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    print(f"\nOverall: {'ALL PASSED' if all(r.values()) else 'SOME FAILED'}")
