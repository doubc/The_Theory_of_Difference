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
from datetime import datetime

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
# 4. Output Formatting Functions
# ============================================================

def format_matrix_markdown(matrix, name):
    """Format a numpy matrix as a LaTeX-style markdown table."""
    rows, cols = matrix.shape
    lines = []
    lines.append(f"**{name}** (Size ${rows}\\times{cols}$):\n")
    lines.append("$$")

    for i in range(rows):
        row_str = " & ".join(str(int(x)) for x in matrix[i])
        if i < rows - 1:
            lines.append(row_str + " \\\\")
        else:
            lines.append(row_str)

    lines.append("$$\n")
    return "\n".join(lines)


def generate_markdown_report(N, mid_verts, directed_edges, triangles, d1, d2, results):
    """Generate a comprehensive markdown report for the CLEM experiment."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md_lines = []
    md_lines.append(f"# CLEM Numerical Verification Results: N={N}\n")
    md_lines.append(f"*Generated on {timestamp}*\n")
    md_lines.append("---\n")

    # Summary
    md_lines.append("## Summary\n")
    mid_w = N // 2
    md_lines.append(f"- **Mid-section weight:** w = {mid_w}")
    md_lines.append(f"- **Vertices (f₀):** {len(mid_verts)}")
    md_lines.append(f"- **Edges (f₁):** {len(directed_edges)}")
    md_lines.append(f"- **Faces (f₂):** {len(triangles)}")
    md_lines.append(f"- **Euler characteristic:** χ = {results['chi']}")
    md_lines.append(f"- **Betti numbers:** (b₀, b₁, b₂) = {results['betti']}\n")

    # Topological interpretation
    b0, b1, b2 = results['betti']
    md_lines.append("## Topological Interpretation\n")
    md_lines.append(f"- **H₀ = ℤ^{b0}:** {b0} connected component(s)")
    md_lines.append(f"- **H₁ = ℤ^{b1}:** {b1} independent loop(s)")
    md_lines.append(f"- **H₂ = ℤ^{b2}:** {b2} void(s)/sphere(s)\n")

    if b0 == 1 and b1 == 0:
        if b2 == 1:
            md_lines.append("**Conclusion:** The complex is topologically equivalent to a single $S^2$ ✓\n")
        elif b2 > 1:
            md_lines.append(f"**Conclusion:** The complex is homotopy equivalent to a wedge of {b2} spheres ($\\vee^{{{b2}}} S^2$) ✓\n")
        else:
            md_lines.append(f"**Conclusion:** The complex has a different topology.\n")
    else:
        md_lines.append(f"**Conclusion:** The complex has a more complex topology (b₁ ≠ 0 or b₀ ≠ 1).\n")

    # Detailed data
    md_lines.append("---\n")
    md_lines.append("## Detailed Combinatorial Data\n")

    # Vertices
    md_lines.append("### Vertices V\n")
    for i, v in enumerate(mid_verts):
        md_lines.append(f"- $v_{i}$: `{v}`")
    md_lines.append("")

    # Directed Edges
    md_lines.append("### Directed Edges E (A1' + A6)\n")
    for j, e in enumerate(directed_edges):
        md_lines.append(f"- $e_{j}$: `{e[0]}` → `{e[1]}`")
    md_lines.append("")

    # Triangular Faces
    md_lines.append("### Triangular Faces F (A7)\n")
    for k, f in enumerate(triangles):
        md_lines.append(f"- $f_{k}$: `{f}`")
    md_lines.append("")

    # Boundary Matrices
    md_lines.append("---\n")
    md_lines.append("## Boundary Matrices\n")
    md_lines.append(format_matrix_markdown(d1, "Boundary Matrix $\\partial_1$"))
    md_lines.append(format_matrix_markdown(d2, "Boundary Matrix $\\partial_2$"))

    # Verification
    check_matrix = np.dot(d1, d2)
    md_lines.append("### Verification: $\\partial_1 \\circ \\partial_2 = 0$\n")
    if np.all(check_matrix == 0):
        md_lines.append("**Result:** ✓ Confirmed. The chain complex is valid.\n")
    else:
        md_lines.append("**WARNING:** ✗ Failed. Check orientation logic.\n")
        md_lines.append("```\n")
        md_lines.append(str(check_matrix))
        md_lines.append("\n```\n")

    # Computational details
    md_lines.append("---\n")
    md_lines.append("## Computational Details\n")
    r1, r2 = results['ranks']
    md_lines.append(f"- **rank($\\partial_1$):** {r1}")
    md_lines.append(f"- **rank($\\partial_2$):** {r2}")
    md_lines.append(f"- **Euler characteristic (direct):** χ = f₀ - f₁ + f₂ = {results['chi']}")
    md_lines.append(f"- **Euler characteristic (homology):** χ = b₀ - b₁ + b₂ = {results['chi_check']}\n")

    return "\n".join(md_lines)

# ============================================================
# 5. Main Experiment: Mid-section Topology
# ============================================================

def run_clem_midsection_experiment(N=4, output_to_file=True):
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
        return None

    # 4. Compute Homology
    d1, d2 = build_boundary_matrices(mid_verts, directed_edges, triangles)
    results = compute_homology_ranks(d1, d2)

    # 5. Display summary
    b0, b1, b2 = results['betti']
    print(f"\nTopological Results:")
    print(f"  H_0 = Z^{b0} (Connected components)")
    print(f"  H_1 = Z^{b1} (Loops/Circles)")
    print(f"  H_2 = Z^{b2} (Voids/Spheres)")
    print(f"  Euler Characteristic: χ = {results['chi']} (Check: {results['chi_check']})")

    # 6. Conclusion
    print(f"\nCLEM Conclusion:")
    if b0 == 1 and b1 == 0 and b2 == 1:
        print(f"  *** SUCCESS: The mid-section is topologically S^2 ***")
        print(f"  This confirms D_A1' = 2. Combined with D_A1 = 1, we get D_eff = 3.")
    else:
        print(f"  Result differs from S^2. Further analysis required.")

    # 7. Optional: Write detailed report to markdown file
    if output_to_file:
        filename = f"CLEM_N{N}_results.md"
        md_content = generate_markdown_report(N, mid_verts, directed_edges, triangles, d1, d2, results)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"\n✓ Detailed report saved to: {filename}")

    return results


if __name__ == "__main__":
    # Run for N=4 (baseline case)
    print("\n" + "=" * 60)
    print("Running CLEM experiment for N=4...")
    print("=" * 60 + "\n")
    results_N4 = run_clem_midsection_experiment(N=4, output_to_file=True)

    # Run for N=6 (extended case)
    print("\n" + "=" * 60)
    print("Running CLEM experiment for N=6...")
    print("=" * 60 + "\n")
    results_N6 = run_clem_midsection_experiment(N=6, output_to_file=True)

    # Run for N=8 (Reviewer's suggestion for pattern finding)
    print("\n" + "=" * 60)
    print("Running CLEM experiment for N=8...")
    print("=" * 60 + "\n")
    results_N8 = run_clem_midsection_experiment(N=8, output_to_file=True)

    # Summary comparison
    print("\n" + "=" * 60)
    print("SUMMARY COMPARISON")
    print("=" * 60)
    print(f"{'N':<5} {'Vertices':<12} {'Edges':<10} {'Faces':<10} {'(b₀,b₁,b₂)':<20} {'χ':<6} {'Topology'}")
    print("-" * 80)

    def print_summary_line(N, results):
        if results:
            b0, b1, b2 = results['betti']
            all_v = list(product([0, 1], repeat=N))
            mid_verts = [v for v in all_v if sum(v) == N // 2]
            topo = "S²" if (b0==1 and b1==0 and b2==1) else (f"{b2} S²" if (b0==1 and b1==0) else "Complex")
            print(f"{str(N):<5} {str(len(mid_verts)):<12} {'N/A':<10} {'N/A':<10} {str(results['betti']):<20} {str(results['chi']):<6} {topo}")

    print_summary_line(4, results_N4)
    print_summary_line(6, results_N6)
    print_summary_line(8, results_N8)

    print("\nNote: Full combinatorial data saved to CLEM_N*_results.md")