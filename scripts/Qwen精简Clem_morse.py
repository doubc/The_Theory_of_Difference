"""
WorldBase CLEM Topological Verification Script
==============================================
This script numerically verifies the Continuous Limit Emergence Mechanism (CLEM)
by computing the homology groups of subspaces constrained by WorldBase axioms.

Core Findings:
1. A8 (Symmetry Preference) isolates the mid-section of the hypercube.
2. A1' (Transverse Emergence) endows the mid-section with S^2 topology.
3. D_eff = dim(S^2) + dim(R_A1) = 2 + 1 = 3.

Dependencies: numpy
"""

from itertools import product

import numpy as np


# ============================================================
# 1. State Space Construction ({0,1}^N)
# ============================================================

def all_vertices(N=4):
    """Generate all vertices of an N-dimensional hypercube."""
    return list(product([0, 1], repeat=N))


def hamming_distance(a, b):
    return sum(x != y for x, y in zip(a, b))


def hamming_weight(v):
    return sum(v)


# ============================================================
# 2. Axiom Constraints & Boundary Operators
# ============================================================

def apply_A4_edges(vertices):
    """A4 (Minimal Change): Edges with Hamming distance = 1."""
    edges = set()
    n = len(vertices)
    for i in range(n):
        for j in range(i + 1, n):
            if hamming_distance(vertices[i], vertices[j]) == 1:
                edges.add(frozenset([vertices[i], vertices[j]]))
    return list(edges)


def apply_A1_prime_edges(vertices, N):
    """A1' (Transverse Emergence): Edges with d_H=2 and same weight."""
    edges = set()
    n = len(vertices)
    for i in range(n):
        for j in range(i + 1, n):
            v, u = vertices[i], vertices[j]
            if hamming_weight(v) == hamming_weight(u) and hamming_distance(v, u) == 2:
                edges.add(frozenset([v, u]))
    return list(edges)


def orient_edges(edges, vertices):
    """A6 (Irreversibility): Orient edges from lower to higher weight/lexicographic."""
    directed = []
    for e in edges:
        v_list = list(e)
        w0, w1 = hamming_weight(v_list[0]), hamming_weight(v_list[1])
        if w0 < w1 or (w0 == w1 and v_list[0] < v_list[1]):
            directed.append((v_list[0], v_list[1]))
        else:
            directed.append((v_list[1], v_list[0]))
    return directed


def find_triangles(directed_edges, vertices):
    """A7 (Cycle Closure): Identify triangular faces in the complex."""
    undirected = set(frozenset(e) for e in directed_edges)
    triangles = []
    vl = sorted(vertices)
    n = len(vl)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                vi, vj, vk = vl[i], vl[j], vl[k]
                if (frozenset([vi, vj]) in undirected and
                        frozenset([vj, vk]) in undirected and
                        frozenset([vi, vk]) in undirected):
                    triangles.append((vi, vj, vk))
    return triangles


def build_boundary_matrices(vertices, directed_edges, faces):
    """Construct boundary operators d1 (edge->vertex) and d2 (face->edge)."""
    v_idx = {v: i for i, v in enumerate(vertices)}
    e_idx = {e: i for i, e in enumerate(directed_edges)}

    n0, n1, n2 = len(vertices), len(directed_edges), len(faces)
    d1 = np.zeros((n0, n1), dtype=int)
    d2 = np.zeros((n1, n2), dtype=int)

    # d1: boundary of edge (src, tgt) is tgt - src
    for j, (src, tgt) in enumerate(directed_edges):
        d1[v_idx[tgt], j] += 1
        d1[v_idx[src], j] -= 1

    # d2: boundary of triangle (v0, v1, v2) is (v0->v1) - (v0->v2) + (v1->v2)
    for k, (v0, v1, v2) in enumerate(faces):
        edges_signed = [((v0, v1), 1), ((v0, v2), -1), ((v1, v2), 1)]
        for (src, tgt), sign in edges_signed:
            if (src, tgt) in e_idx:
                d2[e_idx[(src, tgt)], k] += sign
            elif (tgt, src) in e_idx:
                d2[e_idx[(tgt, src)], k] -= sign

    return d1, d2


# ============================================================
# 3. Homology Computation (Rank-based)
# ============================================================

def compute_homology_ranks(d1, d2):
    """Compute Betti numbers using matrix ranks."""
    n0, n1, n2 = d1.shape[0], d1.shape[1], d2.shape[1]
    r1 = np.linalg.matrix_rank(d1)
    r2 = np.linalg.matrix_rank(d2)

    b0 = n0 - r1
    b1 = (n1 - r1) - r2
    b2 = n2 - r2

    chi = n0 - n1 + n2
    chi_check = b0 - b1 + b2

    return {
        'betti': (b0, b1, b2),
        'chi': chi,
        'chi_check': chi_check,
        'ranks': (r1, r2)
    }


# ============================================================
# 4. Main Experiment: Mid-section S^2 Emergence
# ============================================================

def run_clem_midsection_experiment(N=4):
    print(f"{'=' * 60}")
    print(f"CLEM Verification: Mid-section Topology (N={N})")
    print(f"{'=' * 60}")

    # 1. Select Mid-section (A8 Constraint)
    all_v = all_vertices(N)
    mid_w = N // 2
    mid_verts = [v for v in all_v if hamming_weight(v) == mid_w]
    print(f"A8 Constraint: Selected {len(mid_verts)} vertices at w={mid_w}")

    # 2. Apply A1' Transverse Edges
    a1p_edges = apply_A1_prime_edges(mid_verts, N)
    directed_edges = orient_edges(a1p_edges, mid_verts)
    print(f"A1' Constraint: Identified {len(directed_edges)} transverse edges")

    # 3. Apply A7 Cycle Closure (Triangles)
    triangles = find_triangles(directed_edges, mid_verts)
    print(f"A7 Constraint: Identified {len(triangles)} triangular faces")

    if not directed_edges:
        print("No edges found. Cannot compute homology.")
        return

    # 4. Compute Homology
    d1, d2 = build_boundary_matrices(mid_verts, directed_edges, triangles)

    # --- [新增代码开始：用于论文附录的显式输出] ---
    print(f"\n--- Appendix Data for Paper ---")

    # 1. 显式列出顶点 (V)
    print(f"Vertices V (Johnson Graph J(4,2) nodes):")
    for i, v in enumerate(mid_verts):
        print(f"  v_{i}: {v}")

    # 2. 显式列出有向边 (E) - 对应 A1' + A6 约束
    print(f"\nDirected Edges E (d_H=2, oriented by A6):")
    for j, e in enumerate(directed_edges):
        print(f"  e_{j}: {e[0]} -> {e[1]}")

    # 3. 显式列出三角面 (F) - 对应 A7 约束
    print(f"\nTriangular Faces F (A7 Cycle Closure):")
    for k, f in enumerate(triangles):
        print(f"  f_{k}: {f}")

    # 4. 打印边界矩阵 (关键审阅材料)
    print(f"\nBoundary Matrix d1 (Size {d1.shape[0]}x{d1.shape[1]}):")
    print(d1)

    print(f"\nBoundary Matrix d2 (Size {d2.shape[0]}x{d2.shape[1]}):")
    print(d2)

    # 5. 验证 d1 * d2 = 0 (同调群定义的核心)
    check_matrix = np.dot(d1, d2)
    print(f"\nVerification: d1 . d2 = \n{check_matrix}")
    if np.all(check_matrix == 0):
        print("Result: d1.d2 = 0 confirmed. The complex is valid.")
    else:
        print("WARNING: d1.d2 != 0. Check orientation logic.")
    # --- [新增代码结束] ---

    results = compute_homology_ranks(d1, d2)

    b0, b1, b2 = results['betti']
    print(f"\nTopological Results:")
    print(f"  H_0 = Z^{b0} (Connected components)")
    print(f"  H_1 = Z^{b1} (Loops/Circles)")
    print(f"  H_2 = Z^{b2} (Voids/Spheres)")
    print(f"  Euler Characteristic: χ = {results['chi']} (Check: {results['chi_check']})")

    # 5. Conclusion
    print(f"\nCLEM Conclusion:")
    if b0 == 1 and b1 == 0 and b2 == 1:
        print(f"  *** SUCCESS: The mid-section is topologically S^2 ***")
        print(f"  This confirms D_A1' = 2. Combined with D_A1 = 1, we get D_eff = 3.")
    else:
        print(f"  Result differs from S^2. Further analysis required.")


if __name__ == "__main__":
    run_clem_midsection_experiment(N=4)
    # You can also try N=6 for a more complex mid-section
    # run_clem_midsection_experiment(N=6)
