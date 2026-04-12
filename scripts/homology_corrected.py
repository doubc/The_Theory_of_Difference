"""
Homology of axiom-constrained subcomplexes of {0,1}^k
Rewritten from scratch with clear separation of concerns.
"""

from itertools import combinations

import numpy as np


def rank_mod2(M):
    """Rank of binary matrix (Gaussian elimination over Z/2)."""
    if M.size == 0:
        return 0
    A = M.copy() % 2
    m, n = A.shape
    pivots = []
    for col in range(n):
        found = False
        for row in range(len(pivots), m):
            if A[row, col]:
                A[[len(pivots), row]] = A[[row, len(pivots)]]
                found = True
                break
        if not found:
            continue
        pr = len(pivots)
        pivots.append(col)
        for row in range(m):
            if row != pr and A[row, col]:
                A[row] = (A[row] + A[pr]) % 2
    return len(pivots)


class HypercubeComplex:
    """Full k-cube with vertices, edges, and square faces."""

    def __init__(self, k):
        self.k = k
        self.n = 2 ** k

        # Vertices as bit-tuples
        self.vbits = [tuple((i >> j) & 1 for j in range(k))
                      for i in range(self.n)]

        # Edges: pairs at Hamming distance 1
        self.edges = []  # list of (a, b) with a < b
        self._eset = set()
        for v in range(self.n):
            for j in range(k):
                w = v ^ (1 << j)
                e = (min(v, w), max(v, w))
                if e not in self._eset:
                    self._eset.add(e)
                    self.edges.append(e)

        # Faces: squares from pairs of bit positions
        # For bits (i,j), vertices {v, v^i, v^j, v^i^j} form a square
        self.faces = []  # list of (v0, v1, v2, v3) sorted
        self._fset = set()
        for i, j in combinations(range(k), 2):
            for v in range(self.n):
                a = v
                b = v ^ (1 << i)
                c = v ^ (1 << i) ^ (1 << j)
                d = v ^ (1 << j)
                f = tuple(sorted([a, b, c, d]))
                if f not in self._fset:
                    self._fset.add(f)
                    self.faces.append(f)

        # Precompute: for each face, which edges does it contain?
        self.face_edges = []
        for face in self.faces:
            fe = set()
            for a in range(4):
                for b in range(a + 1, 4):
                    e = (min(face[a], face[b]), max(face[a], face[b]))
                    if e in self._eset:
                        fe.add(e)
            self.face_edges.append(fe)

        # Precompute: for each edge, which bit does it flip?
        self.edge_bit = {}
        for e in self.edges:
            self.edge_bit[e] = e[0] ^ e[1]  # single bit set

    def subcomplex(self, keep_v=None, keep_ei=None, keep_fi=None):
        """
        Filter to a subcomplex.
        Returns: (vertices, edges, faces) as index sets/lists.
        """
        if keep_v is None:
            keep_v = set(range(self.n))
        if keep_ei is None:
            keep_ei = set(range(len(self.edges)))
        if keep_fi is None:
            keep_fi = set(range(len(self.faces)))

        # Filter edges: must have both endpoints in keep_v
        vei = set()
        for ei in keep_ei:
            a, b = self.edges[ei]
            if a in keep_v and b in keep_v:
                vei.add(ei)

        # Filter faces: all edges must be in vei
        vfi = set()
        for fi in keep_fi:
            if self.face_edges[fi].issubset({self.edges[ei] for ei in vei}):
                vfi.add(fi)

        return keep_v, vei, vfi

    def homology(self, keep_v, keep_ei, keep_fi):
        """
        Compute mod-2 homology of subcomplex.
        Returns: {0: beta0, 1: beta1, 2: beta2}
        """
        vl = sorted(keep_v)
        el = sorted(keep_ei)
        fl = sorted(keep_fi)

        nv, ne, nf = len(vl), len(el), len(fl)

        if nv == 0:
            return {0: 0, 1: 0, 2: 0}

        vi = {v: i for i, v in enumerate(vl)}

        # d1: ne x nv (edge -> vertex boundary)
        d1 = np.zeros((ne, nv), dtype=int)
        for i, ei in enumerate(el):
            a, b = self.edges[ei]
            d1[i, vi[a]] = 1
            d1[i, vi[b]] = 1

        # d2: nf x ne (face -> edge boundary)
        d2 = np.zeros((nf, ne), dtype=int)
        eiset = {self.edges[ei]: i for i, ei in enumerate(el)}
        for i, fi in enumerate(fl):
            for e in self.face_edges[fi]:
                if e in eiset:
                    d2[i, eiset[e]] = 1

        r1 = rank_mod2(d1)
        r2 = rank_mod2(d2)

        b0 = nv - r1
        b1 = (ne - r1) - r2
        b2 = (nf - r2)

        return {0: b0, 1: b1, 2: b2}


def run_test(cx, name, keep_v=None, keep_ei=None, keep_fi=None):
    """Run one test and return results."""
    V, E, F = cx.subcomplex(keep_v, keep_ei, keep_fi)
    b = cx.homology(V, E, F)
    chi = len(V) - len(E) + len(F)
    return name, b, len(V), len(E), len(F), chi


def main():
    K = 4
    cx = HypercubeComplex(K)

    print("=" * 72)
    print(f"Homology of Axiom-Constrained Subcomplexes of {{0,1}}^{K}")
    print("=" * 72)
    print(f"\nFull complex: {cx.n} vertices, "
          f"{len(cx.edges)} edges, {len(cx.faces)} faces")
    print(f"Expected: 16 verts, 32 edges, 24 faces")

    # Verify basic properties
    print(f"\n--- Sanity checks ---")
    print(f"Vertices: {cx.n} (expected 16)")
    print(f"Edges: {len(cx.edges)} (expected 32)")
    print(f"Faces: {len(cx.faces)} (expected 24)")
    print(f"Each face has {len(cx.face_edges[0])} edges (expected 4)")

    results = []

    # 1. Full complex
    r = run_test(cx, "Full 4-cube")
    print(f"\n1. Full 4-cube: |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
          f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
    results.append(r)

    # 2. No faces
    r = run_test(cx, "No faces", keep_fi=set())
    print(f"2. No faces: |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
          f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
    results.append(r)

    # 3. Remove single bit edges
    print(f"\n3. Remove single bit edges:")
    for bit in range(K):
        mask = 1 << bit
        keep = {i for i in range(len(cx.edges))
                if not (cx.edges[i][0] ^ cx.edges[i][1]) & mask}
        r = run_test(cx, f"  -bit{bit}", keep_ei=keep)
        print(f"   bit {bit}: |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
              f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
        results.append(r)

    # 4. Remove bit pair edges
    print(f"\n4. Remove bit pair edges:")
    for i, j in combinations(range(K), 2):
        mask = (1 << i) | (1 << j)
        keep = {ei for ei in range(len(cx.edges))
                if not (cx.edges[ei][0] ^ cx.edges[ei][1]) & mask}
        r = run_test(cx, f"  -bits({i},{j})", keep_ei=keep)
        print(f"   ({i},{j}): |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
              f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
        results.append(r)

    # 5. Weight filter
    print(f"\n5. Weight filter:")
    for lo, hi in [(1, 3), (0, 2), (2, 4), (1, 2), (0, 3), (1, 4)]:
        kv = {v for v in range(cx.n) if lo <= sum(cx.vbits[v]) <= hi}
        r = run_test(cx, f"  w[{lo},{hi}]", keep_v=kv)
        print(f"   w[{lo},{hi}]: |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
              f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
        results.append(r)

    # 6. Faces on specific bit pairs
    print(f"\n6. Faces on specific bit pair only:")
    for i, j in combinations(range(K), 2):
        kf = set()
        for fi in range(len(cx.faces)):
            face = cx.faces[fi]
            base = cx.vbits[face[0]]
            varies = set()
            for v in face:
                for k in range(K):
                    if cx.vbits[v][k] != base[k]:
                        varies.add(k)
            if varies == {i, j}:
                kf.add(fi)
        r = run_test(cx, f"  faces({i},{j})", keep_fi=kf)
        print(f"   ({i},{j}): |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
              f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
        results.append(r)

    # 7. Middle slice (weight=2)
    print(f"\n7. Middle slice (weight=2):")
    kv = {v for v in range(cx.n) if sum(cx.vbits[v]) == 2}
    r = run_test(cx, "  mid slice", keep_v=kv)
    bits = sorted([cx.vbits[v] for v in sorted(kv)])
    print(f"   |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
          f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
    print(f"   Vertices: {bits}")
    results.append(r)

    # 8. Gauge subspace (h1=1)
    print(f"\n8. Gauge subspace (h1=1):")
    kv = {v for v in range(cx.n) if cx.vbits[v][3] == 1}
    r = run_test(cx, "  gauge", keep_v=kv)
    print(f"   |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
          f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
    results.append(r)

    # 9. Transverse pair (g3=0, h1=1) — this is a SQUARE
    print(f"\n9. Transverse pair (g3=0, h1=1):")
    kv = {v for v in range(cx.n) if cx.vbits[v][2] == 0 and cx.vbits[v][3] == 1}
    r = run_test(cx, "  trans pair", keep_v=kv)
    bits = sorted([cx.vbits[v] for v in sorted(kv)])
    print(f"   |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
          f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
    print(f"   Vertices: {bits}")
    results.append(r)

    # 10. h1=1 with weight filters
    print(f"\n10. h1=1 + weight filter:")
    for lo, hi in [(1, 2), (1, 3), (2, 3), (0, 3), (1, 4)]:
        kv = {v for v in range(cx.n)
              if cx.vbits[v][3] == 1 and lo <= sum(cx.vbits[v]) <= hi}
        r = run_test(cx, f"  h1=1,w[{lo},{hi}]", keep_v=kv)
        print(f"   w[{lo},{hi}]: |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
              f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
        results.append(r)

    # 11. Both transverse pairs (Klein bottle candidate)
    print(f"\n11. Both transverse pairs (fix h1=1, vary g1,g2,g3):")
    kv = {v for v in range(cx.n) if cx.vbits[v][3] == 1}
    # Also remove edges that flip h1 (bit 3)
    ke = {ei for ei in range(len(cx.edges))
          if not (cx.edges[ei][0] ^ cx.edges[ei][1]) & (1 << 3)}
    r = run_test(cx, "  3-bit cube (no h1-flip)", keep_v=kv, keep_ei=ke)
    print(f"   |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
          f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
    results.append(r)

    # 12. Single square face
    print(f"\n12. Single square face:")
    kv = {0, 1, 3, 2}  # face from bits (0,1), v=0
    ke = set()
    for ei in range(len(cx.edges)):
        a, b = cx.edges[ei]
        if a in kv and b in kv:
            ke.add(ei)
    kf = set()
    for fi in range(len(cx.faces)):
        if set(cx.faces[fi]) == kv:
            kf.add(fi)
    r = run_test(cx, "  square (0,1,3,2)", keep_v=kv, keep_ei=ke, keep_fi=kf)
    print(f"   |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
          f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
    results.append(r)

    # 13. Two adjacent squares (cylinder/Möbius candidate)
    print(f"\n13. Two adjacent squares:")
    kv = {0, 1, 3, 2, 4, 5, 7, 6}  # two faces sharing no edge
    ke = set()
    for ei in range(len(cx.edges)):
        a, b = cx.edges[ei]
        if a in kv and b in kv:
            ke.add(ei)
    kf = set()
    for fi in range(len(cx.faces)):
        if set(cx.faces[fi]).issubset(kv):
            kf.add(fi)
    r = run_test(cx, "  two squares", keep_v=kv, keep_ei=ke, keep_fi=kf)
    print(f"   |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
          f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
    results.append(r)

    # 14. All faces from specific bit pair (strip of squares)
    print(f"\n14. All faces from bit pair (0,1) — strip of 4 squares:")
    kf = set()
    for fi in range(len(cx.faces)):
        face = cx.faces[fi]
        base = cx.vbits[face[0]]
        varies = set()
        for v in face:
            for k in range(K):
                if cx.vbits[v][k] != base[k]:
                    varies.add(k)
        if varies == {0, 1}:
            kf.add(fi)
    r = run_test(cx, "  strip (0,1)", keep_fi=kf)
    print(f"   |V|={r[2]}, |E|={r[3]}, |F|={r[4]}  "
          f"b=[{r[1][0]},{r[1][1]},{r[1][2]}] chi={r[5]}")
    results.append(r)

    # ============================================================
    # Summary
    # ============================================================
    print(f"\n{'=' * 72}")
    print("SUMMARY")
    print(f"{'=' * 72}")
    print(f"\n{'Subcomplex':<35} {'V':>3} {'E':>3} {'F':>3}  "
          f"{'b0':>3} {'b1':>3} {'b2':>3}  {'chi':>4}")
    print("-" * 72)
    for name, b, nv, ne, nf, chi in results:
        print(f"{name:<35} {nv:>3} {ne:>3} {nf:>3}  "
              f"{b[0]:>3} {b[1]:>3} {b[2]:>3}  {chi:>4}")

    # Klein bottle detection
    print(f"\n{'=' * 72}")
    print("KLEIN BOTTLE DETECTION")
    print(f"{'=' * 72}")
    print("""
Klein bottle:  H0=Z,  H1=Z⊕Z/2,  H2=0
Torus:         H0=Z,  H1=Z⊕Z,    H2=Z
Sphere:        H0=Z,  H1=0,       H2=Z
Disk:          H0=Z,  H1=0,       H2=0
Cylinder:      H0=Z,  H1=Z,       H2=0

Detection: compare mod-2 H1 with integer H1.
If mod-2 H1 > integer H1: Z/2 torsion present.

For now, look for subcomplexes where:
  - beta0 = 1 (connected)
  - beta1 > 0 (has loops)
  - chi matches known surfaces
""")
    for name, b, nv, ne, nf, chi in results:
        if b[0] == 1 and b[1] > 0:
            print(f"  {name}: b1={b[1]}, chi={chi}")

    # Euler characteristic check
    print(f"\nEuler check:")
    ok = True
    for name, b, nv, ne, nf, chi in results:
        chi_b = b[0] - b[1] + b[2]
        if chi != chi_b:
            print(f"  MISMATCH: {name}: chi={chi}, betti-chi={chi_b}")
            ok = False
    if ok:
        print("  All Euler characteristics consistent.")


if __name__ == "__main__":
    main()
