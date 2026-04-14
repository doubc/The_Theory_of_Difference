"""
WorldBase CLEM Topological Verification Script (Full Simplicial Complex)
========================================================================
This script numerically verifies the Continuous Limit Emergence Mechanism (CLEM)
by computing the FULL homology groups of subspaces constrained by WorldBase axioms.

IMPORTANT UPDATE (2026-04-14):
- Previous versions only computed 2-skeleton homology (vertices, edges, triangles).
- Johnson graphs J(N, N/2) for N>=6 contain higher-dimensional cliques (K_4, K_5, etc.),
  forming 3-simplices, 4-simplices, etc.
- This version computes the COMPLETE simplicial complex including all k-cliques.

Core Findings:
1. A8 (Symmetry Preference) isolates the mid-section of the hypercube.
2. A1' (Transverse Emergence) endows the mid-section with sphere-like topology.
3. For N=4: Exact result is S^2 (no higher simplices exist).
4. For N>=6: Full homology may differ from 2-skeleton approximation.

Dependencies: numpy
"""

from itertools import product, combinations
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
# 2. Axiom Constraints & Full Simplicial Complex Construction
# ============================================================

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


def find_all_cliques(directed_edges, vertices, max_dim=None):
    """
    Find all cliques (complete subgraphs) up to specified dimension.
    
    Uses iterative expansion: start from edges, find triangles, then extend to higher dimensions.
    
    Parameters:
    - directed_edges: list of directed edges
    - vertices: list of vertices
    - max_dim: maximum simplex dimension to find (None = find all)
    
    Returns:
    - simplices_by_dim: dict mapping dimension k to list of k-simplices
                        (each simplex is a tuple of vertices in sorted order)
    - max_found_dim: the maximum dimension found
    """
    # Build adjacency structure
    undirected = set(frozenset(e) for e in directed_edges)
    vertex_list = sorted(vertices)
    n = len(vertex_list)
    
    # Create vertex to index mapping for faster lookup
    v_to_idx = {v: i for i, v in enumerate(vertex_list)}
    
    # Build adjacency matrix for quick lookup
    adj_matrix = [[False] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if frozenset([vertex_list[i], vertex_list[j]]) in undirected:
                adj_matrix[i][j] = True
                adj_matrix[j][i] = True
    
    # Initialize simplices dictionary
    simplices_by_dim = {}
    
    # Dimension 0: vertices
    simplices_by_dim[0] = [(v,) for v in vertex_list]
    print(f"  Found {len(simplices_by_dim[0])} vertices")
    
    # Dimension 1: edges
    simplices_by_dim[1] = []
    for i in range(n):
        for j in range(i + 1, n):
            if adj_matrix[i][j]:
                simplices_by_dim[1].append((vertex_list[i], vertex_list[j]))
    print(f"  Found {len(simplices_by_dim[1])} edges")
    
    # For higher dimensions, use iterative clique expansion
    current_max_dim = 1
    
    # Find triangles (dimension 2)
    if max_dim is None or max_dim >= 2:
        simplices_by_dim[2] = []
        
        # Find all triangles using adjacency matrix
        for i in range(n):
            for j in range(i + 1, n):
                if not adj_matrix[i][j]:
                    continue
                for k in range(j + 1, n):
                    if adj_matrix[i][k] and adj_matrix[j][k]:
                        triangle = (vertex_list[i], vertex_list[j], vertex_list[k])
                        simplices_by_dim[2].append(triangle)
        
        print(f"  Found {len(simplices_by_dim[2])} triangles")
        current_max_dim = 2
        
        # For dimensions >= 3, use recursive clique expansion
        while current_max_dim < (max_dim if max_dim else 10):
            next_dim = current_max_dim + 1
            simplices_by_dim[next_dim] = []
            
            # Try to extend each k-simplex to a (k+1)-simplex
            for simplex in simplices_by_dim[current_max_dim]:
                # Get indices of vertices in the simplex
                simplex_indices = [v_to_idx[v] for v in simplex]
                
                # Find vertices that are connected to ALL vertices in the simplex
                common_neighbors = []
                for candidate_idx in range(n):
                    if candidate_idx in simplex_indices:
                        continue
                    if all(adj_matrix[candidate_idx][idx] for idx in simplex_indices):
                        common_neighbors.append(candidate_idx)
                
                # Each common neighbor forms a new (k+1)-simplex
                for neighbor_idx in common_neighbors:
                    new_simplex_vertices = list(simplex) + [vertex_list[neighbor_idx]]
                    new_simplex_vertices.sort()  # Keep canonical ordering
                    new_simplex = tuple(new_simplex_vertices)
                    
                    # Avoid duplicates by checking if already added
                    if new_simplex not in simplices_by_dim[next_dim]:
                        simplices_by_dim[next_dim].append(new_simplex)
            
            if len(simplices_by_dim[next_dim]) == 0:
                print(f"  No simplices found at dimension {next_dim}, stopping.")
                del simplices_by_dim[next_dim]
                break
            else:
                print(f"  Found {len(simplices_by_dim[next_dim])} {next_dim}-simplices")
                current_max_dim = next_dim
    
    max_found_dim = current_max_dim
    
    # Sort simplices within each dimension for consistency
    for dim in simplices_by_dim:
        simplices_by_dim[dim].sort()
    
    return simplices_by_dim, max_found_dim


def build_boundary_operator(dim, simplices_lower, simplices_higher):
    """
    Build boundary operator ∂_k: C_k -> C_{k-1}.
    
    Parameters:
    - dim: dimension k of the boundary operator
    - simplices_lower: list of (k-1)-simplices
    - simplices_higher: list of k-simplices
    
    Returns:
    - boundary_matrix: numpy array of shape (len(simplices_lower), len(simplices_higher))
    """
    # Create index mappings
    lower_idx = {s: i for i, s in enumerate(simplices_lower)}
    n_lower = len(simplices_lower)
    n_higher = len(simplices_higher)
    
    boundary_matrix = np.zeros((n_lower, n_higher), dtype=int)
    
    # For each k-simplex, compute its boundary
    for j, simplex in enumerate(simplices_higher):
        # Boundary of (v_0, v_1, ..., v_k) is sum_{i=0}^{k} (-1)^i (v_0, ..., ^v_i, ..., v_k)
        for i in range(len(simplex)):
            # Remove the i-th vertex
            face = tuple(simplex[m] for m in range(len(simplex)) if m != i)
            
            # Determine sign: (-1)^i
            sign = (-1) ** i
            
            # Add to boundary matrix
            if face in lower_idx:
                boundary_matrix[lower_idx[face], j] += sign
    
    return boundary_matrix


def build_full_chain_complex(simplices_by_dim, max_dim):
    """
    Build the complete chain complex with all boundary operators.
    
    Returns:
    - boundary_operators: dict mapping dimension k to boundary matrix ∂_k
    - f_vector: list [f_0, f_1, ..., f_max_dim] where f_k = number of k-simplices
    """
    boundary_operators = {}
    f_vector = []
    
    for k in range(max_dim + 1):
        if k in simplices_by_dim:
            f_vector.append(len(simplices_by_dim[k]))
        else:
            f_vector.append(0)
    
    # Build boundary operators ∂_k for k = 1, 2, ..., max_dim
    for k in range(1, max_dim + 1):
        if k in simplices_by_dim and (k - 1) in simplices_by_dim:
            boundary_operators[k] = build_boundary_operator(
                k,
                simplices_by_dim[k - 1],
                simplices_by_dim[k]
            )
    
    return boundary_operators, f_vector


# ============================================================
# 3. Homology Computation (Full Chain Complex)
# ============================================================

def compute_full_homology(boundary_operators, f_vector, max_dim):
    """
    Compute Betti numbers for the full simplicial complex.
    
    Uses rank-nullity theorem:
    b_k = dim(ker ∂_k) - dim(im ∂_{k+1})
        = (f_k - rank(∂_k)) - rank(∂_{k+1})
    
    Returns:
    - betti_numbers: dict mapping k to b_k
    - euler_characteristic: χ = Σ(-1)^k f_k
    - ranks: dict mapping k to rank(∂_k)
    """
    betti_numbers = {}
    ranks = {}
    
    # Compute ranks of all boundary operators
    for k in range(1, max_dim + 1):
        if k in boundary_operators:
            ranks[k] = np.linalg.matrix_rank(boundary_operators[k])
        else:
            ranks[k] = 0
    
    # Set boundary conditions: ∂_0 = 0, ∂_{max_dim+1} = 0
    ranks[0] = 0
    ranks[max_dim + 1] = 0
    
    # Compute Betti numbers
    for k in range(max_dim + 1):
        if k < len(f_vector):
            f_k = f_vector[k]
            rank_k = ranks.get(k, 0)
            rank_k_plus_1 = ranks.get(k + 1, 0)
            
            betti_k = (f_k - rank_k) - rank_k_plus_1
            betti_numbers[k] = int(betti_k)
    
    # Compute Euler characteristic
    euler_char = sum((-1) ** k * f_vector[k] for k in range(len(f_vector)))
    euler_check = sum((-1) ** k * betti_numbers.get(k, 0) for k in range(max_dim + 1))
    
    return {
        'betti': betti_numbers,
        'chi': euler_char,
        'chi_check': euler_check,
        'ranks': ranks,
        'f_vector': f_vector
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


def generate_full_markdown_report(N, simplices_by_dim, boundary_operators, results, max_dim):
    """Generate a comprehensive markdown report for the CLEM experiment with full homology."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md_lines = []
    md_lines.append(f"# CLEM Numerical Verification Results: N={N} (Full Simplicial Complex)\n")
    md_lines.append(f"*Generated on {timestamp}*\n")
    md_lines.append("---\n")

    # Summary
    md_lines.append("## Summary\n")
    mid_w = N // 2
    f_vector = results['f_vector']
    md_lines.append(f"- **Mid-section weight:** w = {mid_w}")
    md_lines.append(f"- **Maximum simplex dimension:** {max_dim}")
    md_lines.append(f"- **f-vector:** ({', '.join(f'f_{k}={f_vector[k]}' for k in range(len(f_vector)))})")
    md_lines.append(f"- **Euler characteristic:** χ = {results['chi']}")
    
    betti = results['betti']
    betti_str = ', '.join(f'b_{k}={betti.get(k, 0)}' for k in range(max_dim + 1))
    md_lines.append(f"- **Betti numbers:** ({betti_str})\n")

    # Topological interpretation
    md_lines.append("## Topological Interpretation\n")
    for k in range(max_dim + 1):
        b_k = betti.get(k, 0)
        if k == 0:
            md_lines.append(f"- **H₀ = ℤ^{b_k}:** {b_k} connected component(s)")
        elif k == 1:
            md_lines.append(f"- **H₁ = ℤ^{b_k}:** {b_k} independent loop(s)")
        elif k == 2:
            md_lines.append(f"- **H₂ = ℤ^{b_k}:** {b_k} void(s)/sphere(s)")
        else:
            md_lines.append(f"- **H_{k} = ℤ^{b_k}:** {b_k} {k}-dimensional hole(s)")
    md_lines.append("")

    # Conclusion based on low-dimensional homology
    b0 = betti.get(0, 0)
    b1 = betti.get(1, 0)
    b2 = betti.get(2, 0)
    
    md_lines.append("**Conclusion:**\n")
    if b0 == 1 and b1 == 0:
        if b2 == 1:
            md_lines.append("- The complex is topologically equivalent to a single $S^2$ ✓\n")
        elif b2 > 1:
            md_lines.append(
                f"- The complex is homotopy equivalent to a wedge of {b2} spheres ($\\vee^{{{b2}}} S^2$) ✓\n")
        else:
            md_lines.append(f"- The complex has trivial H₂.\n")
    else:
        md_lines.append(f"- The complex has a more complex topology (b₀≠1 or b₁≠0).\n")
    
    # Note about 2-skeleton vs full complex
    if max_dim >= 3:
        md_lines.append(
            "**Important Note:** This computation includes higher-dimensional simplices (3-simplices and above). ")
        md_lines.append(
            "Previous 2-skeleton-only calculations may have overestimated $b_2$ due to unfilled cavities.\n")

    # Detailed data
    md_lines.append("---\n")
    md_lines.append("## Detailed Combinatorial Data\n")

    # Vertices
    md_lines.append("### Vertices V (0-simplices)\n")
    for i, v in enumerate(simplices_by_dim[0]):
        md_lines.append(f"- $v_{i}$: `{v[0]}`")
    md_lines.append("")

    # Edges
    md_lines.append("### Directed Edges E (1-simplices)\n")
    for j, e in enumerate(simplices_by_dim[1]):
        md_lines.append(f"- $e_{j}$: `{e[0]}` → `{e[1]}`")
    md_lines.append("")

    # Triangles
    if 2 in simplices_by_dim:
        md_lines.append("### Triangular Faces F (2-simplices)\n")
        for k, f in enumerate(simplices_by_dim[2]):
            md_lines.append(f"- $f_{k}$: `{f}`")
        md_lines.append("")

    # Higher simplices
    for dim in range(3, max_dim + 1):
        if dim in simplices_by_dim and len(simplices_by_dim[dim]) > 0:
            md_lines.append(f"### {dim}-Simplices (count: {len(simplices_by_dim[dim])})\n")
            md_lines.append("*Note: Full list omitted for brevity.*\n")
            # Show first few examples
            for i, s in enumerate(simplices_by_dim[dim][:5]):
                md_lines.append(f"- $\\sigma_{i}$: `{s}`")
            if len(simplices_by_dim[dim]) > 5:
                md_lines.append(f"- ... and {len(simplices_by_dim[dim]) - 5} more")
            md_lines.append("")

    # Boundary Matrices
    md_lines.append("---\n")
    md_lines.append("## Boundary Matrices\n")
    for k in range(1, max_dim + 1):
        if k in boundary_operators:
            md_lines.append(format_matrix_markdown(boundary_operators[k], f"Boundary Matrix $\\partial_{k}$"))

    # Verification: ∂_k ∘ ∂_{k+1} = 0
    md_lines.append("### Verification: $\\partial_k \\circ \\partial_{k+1} = 0$\n")
    all_valid = True
    for k in range(1, max_dim):
        if k in boundary_operators and (k + 1) in boundary_operators:
            check = np.dot(boundary_operators[k], boundary_operators[k + 1])
            if np.all(check == 0):
                md_lines.append(f"- **∂_{k} ∘ ∂_{k + 1} = 0:** ✓ Confirmed")
            else:
                md_lines.append(f"- **∂_{k} ∘ ∂_{k + 1} = 0:** ✗ FAILED")
                all_valid = False
    
    if all_valid:
        md_lines.append("\n**Result:** All boundary conditions satisfied. The chain complex is valid.\n")
    else:
        md_lines.append("\n**WARNING:** Some boundary conditions failed. Check orientation logic.\n")

    # Computational details
    md_lines.append("---\n")
    md_lines.append("## Computational Details\n")
    ranks = results['ranks']
    for k in range(1, max_dim + 1):
        if k in ranks:
            md_lines.append(f"- **rank($\\partial_{k}$):** {ranks[k]}")
    md_lines.append(f"- **Euler characteristic (direct):** χ = Σ(-1)^k f_k = {results['chi']}")
    md_lines.append(f"- **Euler characteristic (homology):** χ = Σ(-1)^k b_k = {results['chi_check']}\n")

    return "\n".join(md_lines)


# ============================================================
# 5. Main Experiment: Full Simplicial Complex Homology
# ============================================================

def run_clem_full_homology_experiment(N=4, output_to_file=True, max_simplex_dim=None):
    print(f"{'=' * 70}")
    print(f"CLEM Verification: Full Simplicial Complex Homology (N={N})")
    print(f"{'=' * 70}")

    # 1. Select Mid-section (A8 Constraint)
    all_v = all_vertices(N)
    mid_w = N // 2
    mid_verts = [v for v in all_v if hamming_weight(v) == mid_w]
    print(f"A8 Constraint: Selected {len(mid_verts)} vertices at w={mid_w}")

    # 2. Apply A1' Transverse Edges
    a1p_edges = apply_A1_prime_edges(mid_verts, N)
    directed_edges = orient_edges(a1p_edges, mid_verts)
    print(f"A1' Constraint: Identified {len(directed_edges)} transverse edges")

    # 3. Find ALL cliques (full simplicial complex)
    print(f"\nSearching for all cliques...")
    simplices_by_dim, max_dim = find_all_cliques(directed_edges, mid_verts, max_dim=max_simplex_dim)
    
    print(f"\nFound simplices up to dimension {max_dim}:")
    for dim in sorted(simplices_by_dim.keys()):
        count = len(simplices_by_dim[dim])
        print(f"  Dimension {dim}: {count} simplices")

    # 4. Build full chain complex
    print(f"\nBuilding boundary operators...")
    boundary_operators, f_vector = build_full_chain_complex(simplices_by_dim, max_dim)
    print(f"f-vector: {f_vector}")

    # 5. Compute full homology
    print(f"Computing homology groups...")
    results = compute_full_homology(boundary_operators, f_vector, max_dim)

    # 6. Display summary
    betti = results['betti']
    print(f"\nTopological Results:")
    for k in sorted(betti.keys()):
        print(f"  H_{k} = Z^{betti[k]}")
    print(f"  Euler Characteristic: χ = {results['chi']} (Check: {results['chi_check']})")

    # 7. Comparison with 2-skeleton only
    if max_dim >= 3:
        b2_full = betti.get(2, 0)
        f_2 = f_vector[2] if 2 < len(f_vector) else 0
        print(f"\n⚠️  IMPORTANT: This includes {max_dim}-dimensional simplices.")
        print(f"   The 2-skeleton-only calculation would give different b_2.")
        print(f"   Current b_2 = {b2_full} (with higher simplices filling some cavities)")

    # 8. Conclusion
    print(f"\nCLEM Conclusion:")
    b0 = betti.get(0, 0)
    b1 = betti.get(1, 0)
    b2 = betti.get(2, 0)
    
    if b0 == 1 and b1 == 0 and b2 == 1:
        print(f"  *** SUCCESS: The mid-section is topologically S^2 ***")
        print(f"  This confirms D_A1' = 2. Combined with D_A1 = 1, we get D_eff = 3.")
    elif b0 == 1 and b1 == 0 and b2 > 1:
        print(f"  *** The mid-section is a wedge of {b2} spheres: ∨^{b2} S^2 ***")
        print(f"  This reveals a rich topological structure emerging from discrete axioms.")
    else:
        print(f"  Result differs from simple sphere structure. Further analysis required.")

    # 9. Optional: Write detailed report to markdown file
    if output_to_file:
        filename = f"CLEM_N{N}_FULL_results.md"
        md_content = generate_full_markdown_report(N, simplices_by_dim, boundary_operators, results, max_dim)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"\n✓ Detailed report saved to: {filename}")

    return results


if __name__ == "__main__":
    # Run for N=4 (baseline case - should match previous results exactly)
    print("\n" + "=" * 70)
    print("Running CLEM FULL HOMOTOLOGY experiment for N=4...")
    print("=" * 70 + "\n")
    results_N4 = run_clem_full_homology_experiment(N=4, output_to_file=True)

    # Run for N=6 (extended case with higher simplices)
    print("\n" + "=" * 70)
    print("Running CLEM FULL HOMOTOLOGY experiment for N=6...")
    print("=" * 70 + "\n")
    results_N6 = run_clem_full_homology_experiment(N=6, output_to_file=True)

    # Run for N=8 (Reviewer's suggestion - may take longer due to many cliques)
    print("\n" + "=" * 70)
    print("Running CLEM FULL HOMOTOLOGY experiment for N=8...")
    print("Note: This may take several minutes due to clique enumeration.")
    print("=" * 70 + "\n")
    results_N8 = run_clem_full_homology_experiment(N=8, output_to_file=True)

    # Summary comparison
    print("\n" + "=" * 70)
    print("SUMMARY COMPARISON: Full Simplicial Complex Homology")
    print("=" * 70)
    print(f"{'N':<5} {'Max Dim':<10} {'f-vector':<30} {'Betti Numbers':<40} {'χ':<6}")
    print("-" * 100)

    def print_full_summary_line(N, results):
        if results:
            f_vec = results['f_vector']
            betti = results['betti']
            max_dim = len(f_vec) - 1
            
            # Format f-vector
            f_str = ', '.join(str(f) for f in f_vec)
            if len(f_str) > 28:
                f_str = f_str[:25] + "..."
            
            # Format Betti numbers
            betti_str = ', '.join(f'b_{k}={betti.get(k, 0)}' for k in range(max_dim + 1))
            if len(betti_str) > 38:
                betti_str = betti_str[:35] + "..."
            
            print(f"{str(N):<5} {str(max_dim):<10} {f_str:<30} {betti_str:<40} {str(results['chi']):<6}")

    print_full_summary_line(4, results_N4)
    print_full_summary_line(6, results_N6)
    print_full_summary_line(8, results_N8)

    print("\n" + "=" * 70)
    print("KEY INSIGHTS:")
    print("=" * 70)
    print("1. For N=4: No higher simplices exist (max dim = 2), so result is exact S^2.")
    print("2. For N>=6: Higher simplices (3-simplices, etc.) may fill some 2-cavities.")
    print("3. Compare b_2 values between 2-skeleton-only and full complex calculations.")
    print("4. If b_2 decreases significantly, it means higher simplices are 'filling holes'.")
    print("\nDetailed reports saved to: CLEM_N*_FULL_results.md")
