"""
Homology computation for axiom-constrained subcomplexes of {0,1}^4
Goal: Check if Klein bottle structure (Z/2 torsion in H1) emerges
"""

from itertools import combinations

import numpy as np


# ============================================================
# Core homology computation over Z/2Z
# ============================================================

def rank_mod2(M):
    """Compute rank of matrix over Z/2Z using Gaussian elimination."""
    if M.size == 0:
        return 0
    A = M.copy() % 2
    m, n = A.shape
    rank = 0
    for col in range(n):
        pivot = -1
        for row in range(rank, m):
            if A[row, col]:
                pivot = row
                break
        if pivot == -1:
            continue
        A[[rank, pivot]] = A[[pivot, rank]]
        for row in range(m):
            if row != rank and A[row, col]:
                A[row] = (A[row] + A[rank]) % 2
        rank += 1
    return rank


def homology_mod2(n_cells, boundary_fn):
    """
    Compute Betti numbers and detect Z/2 torsion.

    Returns: (betti_dict, torsion_dict)
      betti_dict[i] = dim_{F2} H_i(Z/2Z)
      torsion_dict[i] = True if Z/2 torsion detected in H_i(Z)
    """
    results = {}
    ranks = {}

    for i in sorted(n_cells.keys()):
        n = n_cells[i]
        B = boundary_fn(i)
        if B.size > 0:
            r = rank_mod2(B)
        else:
            r = 0
        ranks[i] = r

        r_prev = ranks.get(i - 1, 0)
        n_prev = n_cells.get(i - 1, 0)

        ker = n - r
        im = r_prev
        beta = ker - im
        results[i] = max(0, beta)

    return results


# ============================================================
# 4-cube complex builder
# ============================================================

class HypercubeComplex:
    """Simplicial complex of the 4-cube {0,1}^4 with axiom constraints."""

    def __init__(self, k=4):
        self.k = k
        self.vertices = [i for i in range(2 ** k)]
        self.v_bits = {}
        for i in range(2 ** k):
            bits = tuple((i >> j) & 1 for j in range(k))
            self.v_bits[i] = bits

        self._build_full()

    def _build_full(self):
        """Build full 4-cube: vertices, edges, faces."""
        k = self.k

        # Edges: pairs at Hamming distance 1
        self.all_edges = []
        edge_set = set()
        for v in range(2 ** k):
            for j in range(k):
                w = v ^ (1 << j)
                e = (min(v, w), max(v, w))
                if e not in edge_set:
                    edge_set.add(e)
                    self.all_edges.append(e)

        # Faces: 4-cycles from pairs of bit positions
        self.all_faces = []
        face_set = set()
        for i, j in combinations(range(k), 2):
            for v in range(2 ** k):
                vi = v ^ (1 << i)
                vj = v ^ (1 << j)
                vij = v ^ (1 << i) ^ (1 << j)
                face = tuple(sorted([v, vi, vij, vj]))
                if face not in face_set:
                    face_set.add(face)
                    self.all_faces.append(face)

        # Face-edge incidence
        self._face_edges = {}
        for fi, face in enumerate(self.all_faces):
            edges = set()
            for a in range(4):
                for b in range(a + 1, 4):
                    e = (min(face[a], face[b]), max(face[a], face[b]))
                    if e in {(min(x, y), max(x, y)) for x, y in self.all_edges}:
                        edges.add(e)
            self._face_edges[fi] = edges

    def subcomplex(self, vertices=None, edges=None, faces=None):
        """Create a subcomplex with specified elements."""
        if vertices is None:
            vertices = set(self.vertices)
        if edges is None:
            edges = set(self.all_edges)
        if faces is None:
            faces = set(range(len(self.all_faces)))

        # Ensure edges only use kept vertices
        edges = {e for e in edges if e[0] in vertices and e[1] in vertices}

        # Ensure faces only use kept edges
        valid_faces = set()
        for fi in faces:
            face_edges = self._face_edges.get(fi, set())
            if face_edges.issubset(edges):
                valid_faces.add(fi)

        return vertices, edges, valid_faces

    def compute_homology(self, vertices, edges, faces):
        """Compute mod-2 homology of the subcomplex."""
        v_list = sorted(vertices)
        e_list = sorted(edges)
        f_list = sorted(faces)

        v_idx = {v: i for i, v in enumerate(v_list)}
        e_idx = {e: i for i, e in enumerate(e_list)}

        nv = len(v_list)
        ne = len(e_list)
        nf = len(f_list)

        # Boundary d1: edges -> vertices (ne x nv)
        if ne > 0 and nv > 0:
            d1 = np.zeros((nv, ne), dtype=int)
            for j, (a, b) in enumerate(e_list):
                d1[v_idx[a], j] = 1
                d1[v_idx[b], j] = 1
        else:
            d1 = np.zeros((nv, ne), dtype=int) if nv > 0 else np.zeros((0, ne), dtype=int)

        # Boundary d2: faces -> edges (nf x ne)
        if nf > 0 and ne > 0:
            d2 = np.zeros((ne, nf), dtype=int)
            for j, fi in enumerate(f_list):
                face = self.all_faces[fi]
                for a in range(4):
                    for b in range(a + 1, 4):
                        e = (min(face[a], face[b]), max(face[a], face[b]))
                        if e in e_idx:
                            d2[e_idx[e], j] = 1
        else:
            d2 = np.zeros((ne, nf), dtype=int) if ne > 0 else np.zeros((0, nf), dtype=int)

        n_cells = {0: nv, 1: ne, 2: nf}

        def boundary(i):
            if i == 1:
                return d1
            elif i == 2:
                return d2
            else:
                n_next = n_cells.get(i, 0)
                n_curr = n_cells.get(i - 1, 0)
                return np.zeros((n_curr, n_next), dtype=int)

        return homology_mod2(n_cells, boundary)


# ============================================================
# Main analysis
# ============================================================

def format_betti(betti):
    parts = []
    for i in sorted(betti.keys()):
        b = betti[i]
        if b > 0:
            parts.append(f"H{i}=(Z/2)^{b}" if b > 1 else f"H{i}=Z/2")
        else:
            parts.append(f"H{i}=0")
    return ", ".join(parts)


def main():
    print("=" * 65)
    print("Homology of Axiom-Constrained Subcomplexes of {0,1}^4")
    print("Goal: Detect Klein bottle (Z/2 torsion in H1)")
    print("=" * 65)

    cx = HypercubeComplex(k=4)

    print(f"\nComplex: {len(cx.vertices)} vertices, "
          f"{len(cx.all_edges)} edges, "
          f"{len(cx.all_faces)} faces")

    all_results = []

    # ---- Test 1: Full 4-cube ----
    print("\n" + "-" * 65)
    print("1. Full 4-cube (no constraints)")
    V, E, F = cx.subcomplex()
    betti = cx.compute_homology(V, E, F)
    print(f"   |V|={len(V)}, |E|={len(E)}, |F|={len(F)}")
    print(f"   H*(Z/2): {format_betti(betti)}")
    all_results.append(("Full 4-cube", betti, len(V), len(E), len(F)))

    # ---- Test 2: 1-skeleton only ----
    print("\n" + "-" * 65)
    print("2. 1-skeleton only (no faces)")
    V, E, F = cx.subcomplex(faces=set())
    betti = cx.compute_homology(V, E, F)
    print(f"   |V|={len(V)}, |E|={len(E)}, |F|={len(F)}")
    print(f"   H*(Z/2): {format_betti(betti)}")
    all_results.append(("1-skeleton", betti, len(V), len(E), len(F)))

    # ---- Test 3: Remove edges by bit position ----
    print("\n" + "-" * 65)
    print("3. Remove edges by bit position (A1' structure test)")
    for bit in range(4):
        kept = {(a, b) for a, b in cx.all_edges
                if not ((a ^ b) & (1 << bit))}
        V, E, F = cx.subcomplex(edges=kept)
        betti = cx.compute_homology(V, E, F)
        print(f"   Remove bit {bit}: |V|={len(V)}, |E|={len(E)}, "
              f"|F|={len(F)}")
        print(f"     H*(Z/2): {format_betti(betti)}")
        all_results.append((f"Remove bit {bit}", betti,
                            len(V), len(E), len(F)))

    # ---- Test 4: Remove edges for bit pairs ----
    print("\n" + "-" * 65)
    print("4. Remove edges for bit pairs (A1' transverse test)")
    for i, j in combinations(range(4), 2):
        kept = {(a, b) for a, b in cx.all_edges
                if not ((a ^ b) & ((1 << i) | (1 << j)))}
        V, E, F = cx.subcomplex(edges=kept)
        betti = cx.compute_homology(V, E, F)
        print(f"   Remove bits ({i},{j}): |V|={len(V)}, "
              f"|E|={len(E)}, |F|={len(F)}")
        print(f"     H*(Z/2): {format_betti(betti)}")
        all_results.append((f"Remove bits ({i},{j})", betti,
                            len(V), len(E), len(F)))

    # ---- Test 5: Vertex weight filter (A3+A8 test) ----
    print("\n" + "-" * 65)
    print("5. Vertex weight filter (A3+A8 test)")
    for min_w, max_w in [(1, 3), (0, 2), (2, 4), (1, 2)]:
        kept_v = {v for v in cx.vertices
                  if min_w <= sum(cx.v_bits[v]) <= max_w}
        V, E, F = cx.subcomplex(vertices=kept_v)
        betti = cx.compute_homology(V, E, F)
        weights = sorted(set(sum(cx.v_bits[v]) for v in kept_v))
        print(f"   Weight [{min_w},{max_w}] "
              f"(weights={weights}): |V|={len(V)}, "
              f"|E|={len(E)}, |F|={len(F)}")
        print(f"     H*(Z/2): {format_betti(betti)}")
        all_results.append((f"Weight [{min_w},{max_w}]", betti,
                            len(V), len(E), len(F)))

    # ---- Test 6: Face filter by bit pairs ----
    print("\n" + "-" * 65)
    print("6. Face filter by bit pair (A7 transverse test)")
    for i, j in combinations(range(4), 2):
        kept_f = {fi for fi in range(len(cx.all_faces))
                  if set(cx.all_faces[fi]) ==
                  {v for v in cx.vertices
                   if all(cx.v_bits[v][k] == cx.v_bits[min(cx.all_faces[fi])][k]
                          for k in range(4) if k not in (i, j))}
                  or True}  # Keep faces on (i,j) plane
        # More precise: keep only faces on the (i,j) bit plane
        kept_f = set()
        for fi in range(len(cx.all_faces)):
            face = cx.all_faces[fi]
            # Check if face varies only in bits i and j
            base = cx.v_bits[face[0]]
            varies = set()
            for v in face:
                for k in range(4):
                    if cx.v_bits[v][k] != base[k]:
                        varies.add(k)
            if varies == {i, j}:
                kept_f.add(fi)

        V, E, F = cx.subcomplex(faces=kept_f)
        betti = cx.compute_homology(V, E, F)
        print(f"   Faces on ({i},{j}): |V|={len(V)}, "
              f"|E|={len(E)}, |F|={len(F)}")
        print(f"     H*(Z/2): {format_betti(betti)}")
        all_results.append((f"Faces ({i},{j})", betti,
                            len(V), len(E), len(F)))

    # ---- Test 7: Middle slice (A8 specific) ----
    print("\n" + "-" * 65)
    print("7. Middle slice (weight=2, A8 test)")
    kept_v = {v for v in cx.vertices if sum(cx.v_bits[v]) == 2}
    V, E, F = cx.subcomplex(vertices=kept_v)
    betti = cx.compute_homology(V, E, F)
    print(f"   |V|={len(V)}, |E|={len(E)}, |F|={len(F)}")
    print(f"   Vertices: {sorted([cx.v_bits[v] for v in V])}")
    print(f"   H*(Z/2): {format_betti(betti)}")
    all_results.append(("Middle slice (w=2)", betti,
                        len(V), len(E), len(F)))

    # ---- Test 8: Gauge subspace (3 bits) ----
    print("\n" + "-" * 65)
    print("8. Gauge subspace (fix h1=1, 3 gauge bits)")
    kept_v = {v for v in cx.vertices if cx.v_bits[v][3] == 1}
    V, E, F = cx.subcomplex(vertices=kept_v)
    betti = cx.compute_homology(V, E, F)
    print(f"   |V|={len(V)}, |E|={len(E)}, |F|={len(F)}")
    print(f"   H*(Z/2): {format_betti(betti)}")
    all_results.append(("Gauge subspace (h1=1)", betti,
                        len(V), len(E), len(F)))

    # ---- Test 9: Transverse pair subspace (2 bits) ----
    print("\n" + "-" * 65)
    print("9. Transverse pair subspace (fix g3=0, h1=1)")
    kept_v = {v for v in cx.vertices
              if cx.v_bits[v][2] == 0 and cx.v_bits[v][3] == 1}
    V, E, F = cx.subcomplex(vertices=kept_v)
    betti = cx.compute_homology(V, E, F)
    print(f"   |V|={len(V)}, |E|={len(E)}, |F|={len(F)}")
    print(f"   Vertices: {sorted([cx.v_bits[v] for v in V])}")
    print(f"   H*(Z/2): {format_betti(betti)}")
    all_results.append(("Transverse pair (g3=0,h1=1)", betti,
                        len(V), len(E), len(F)))

    # ---- Test 10: Remove ALL faces ----
    print("\n" + "-" * 65)
    print("10. All vertices + edges, no faces")
    V, E, F = cx.subcomplex(faces=set())
    betti = cx.compute_homology(V, E, F)
    print(f"   |V|={len(V)}, |E|={len(E)}, |F|={len(F)}")
    print(f"   H*(Z/2): {format_betti(betti)}")
    all_results.append(("No faces", betti, len(V), len(E), len(F)))

    # ---- Test 11: Only faces, no loose edges ----
    print("\n" + "-" * 65)
    print("11. All faces (keep only edges in faces)")
    face_edges = set()
    for fi in range(len(cx.all_faces)):
        face = cx.all_faces[fi]
        for a in range(4):
            for b in range(a + 1, 4):
                e = (min(face[a], face[b]), max(face[a], face[b]))
                face_edges.add(e)
    V, E, F = cx.subcomplex(edges=face_edges)
    betti = cx.compute_homology(V, E, F)
    print(f"   |V|={len(V)}, |E|={len(E)}, |F|={len(F)}")
    print(f"   H*(Z/2): {format_betti(betti)}")
    all_results.append(("All faces", betti, len(V), len(E), len(F)))

    # ---- Test 12: Combined constraint ----
    print("\n" + "-" * 65)
    print("12. Combined: gauge subspace + weight filter")
    for min_w, max_w in [(1, 2), (1, 3), (2, 3)]:
        kept_v = {v for v in cx.vertices
                  if cx.v_bits[v][3] == 1 and
                  min_w <= sum(cx.v_bits[v]) <= max_w}
        V, E, F = cx.subcomplex(vertices=kept_v)
        betti = cx.compute_homology(V, E, F)
        print(f"   h1=1, weight [{min_w},{max_w}]: "
              f"|V|={len(V)}, |E|={len(E)}, |F|={len(F)}")
        print(f"     H*(Z/2): {format_betti(betti)}")
        all_results.append((f"h1=1, w[{min_w},{max_w}]", betti,
                            len(V), len(E), len(F)))

    # ============================================================
    # Summary
    # ============================================================
    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"\n{'Subcomplex':<35} {'|V|':>4} {'|E|':>4} "
          f"{'|F|':>4} {'H0':>4} {'H1':>4} {'H2':>4}")
    print("-" * 65)
    for name, betti, nv, ne, nf in all_results:
        h0 = betti.get(0, 0)
        h1 = betti.get(1, 0)
        h2 = betti.get(2, 0)
        marker = " ***" if h1 > 0 else ""
        print(f"{name:<35} {nv:>4} {ne:>4} {nf:>4} "
              f"{h0:>4} {h1:>4} {h2:>4}{marker}")

    # Klein bottle detection
    print("\n" + "=" * 65)
    print("KLEIN BOTTLE CHECK")
    print("=" * 65)
    print("\nKlein bottle: H1(Z) = Z ⊕ Z/2")
    print("Over Z/2: H1 = (Z/2)^2")
    print("Over Z:   H1 = Z (free rank 1)")
    print("\nIf mod-2 H1 > free rank H1: Z/2 torsion present")
    print("\nNote: This script computes mod-2 homology.")
    print("For full torsion detection, compare with Z homology.")
    print("If any subcomplex has H1 > 0, investigate further.\n")

    interesting = [(name, betti) for name, betti, _, _, _
                   in all_results if betti.get(1, 0) > 0]
    if interesting:
        print("Subcomplexes with non-trivial H1:")
        for name, betti in interesting:
            print(f"  {name}: H1 = (Z/2)^{betti[1]}")
    else:
        print("No subcomplex has non-trivial H1 over Z/2.")
        print("This means no Z/2 torsion detected in any subcomplex.")


if __name__ == "__main__":
    main()
