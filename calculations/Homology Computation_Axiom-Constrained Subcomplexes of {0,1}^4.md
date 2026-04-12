# Homology Computation: Axiom-Constrained Subcomplexes of {0,1}^4

**File**: `homology_corrected.py`
**Date**: 2026-04-12
**Purpose**: Compute mod-2 homology of subcomplexes under axiom constraints, detect Klein bottle (Z/2 torsion),
characterize topological effects of each axiom.

---

## 1. Computational Setup

### 1.1 Complex Construction

The full 4-cube {0,1}^4 is built as a simplicial complex:

| Element  | Definition                          | Count |
|----------|-------------------------------------|-------|
| Vertices | All 16 binary strings of length 4   | 16    |
| Edges    | Pairs at Hamming distance 1         | 32    |
| Faces    | Squares from pairs of bit positions | 24    |

Each face is a 4-cycle: for bits (i,j), vertices {v, v^i, v^j, v^i^j} form a square. There are C(4,2)=6 bit pairs, each
contributing 4 squares (from 2^(4-2)=4 choices of the remaining bits), giving 6×4=24 faces.

### 1.2 Axiom Correspondence

| Axiom                       | Geometric Operation                                          |
|-----------------------------|--------------------------------------------------------------|
| A3 (finite)                 | Work on {0,1}^4, not {0,1}^∞                                 |
| A4 (minimal variation)      | Edges connect Hamming-1 neighbors only                       |
| A6 (irreversibility)        | Not directly modeled (DAG constraint on edges — future work) |
| A7 (cycle closure)          | Faces are closed 4-cycles                                    |
| A8 (mid-section preference) | Weight filter: keep vertices with specific Hamming weight    |

### 1.3 Homology Computation

Mod-2 homology via boundary matrices:

- **d1**: edge → vertex incidence (ne × nv matrix)
- **d2**: face → edge incidence (nf × ne matrix)
- **Betti numbers**: β_i = dim(ker d_i) - dim(im d_{i+1})

Rank computed by Gaussian elimination over F₂.

### 1.4 Subcomplex Filtering

Three independent filters:

- `keep_v`: vertex set (applied first)
- `keep_ei`: edge indices (filtered to those with both endpoints in keep_v)
- `keep_fi`: face indices (filtered to those whose 4 edges are all in the edge set)

---

## 2. Results

### 2.1 Sanity Checks

| Check             | Expected         | Actual   | Status |
|-------------------|------------------|----------|--------|
| Vertex count      | 16               | 16       | ✅      |
| Edge count        | 32               | 32       | ✅      |
| Face count        | 24               | 24       | ✅      |
| Edges per face    | 4                | 4        | ✅      |
| Euler consistency | χ = β₀ - β₁ + β₂ | All pass | ✅      |

### 2.2 Full Results Table

| Subcomplex                    | V  | E  | F  | β₀ | β₁ | β₂ | χ   |
|-------------------------------|----|----|----|----|----|----|-----|
| Full 4-cube                   | 16 | 32 | 24 | 1  | 0  | 7  | 8   |
| No faces                      | 16 | 32 | 0  | 1  | 17 | 0  | -16 |
| Remove bit 0                  | 16 | 24 | 12 | 2  | 0  | 2  | 4   |
| Remove bits (0,1)             | 16 | 16 | 4  | 4  | 0  | 0  | 4   |
| Weight [1,3]                  | 14 | 24 | 12 | 1  | 0  | 1  | 2   |
| Weight [0,2]                  | 11 | 16 | 6  | 1  | 0  | 0  | 1   |
| Weight [1,2]                  | 10 | 12 | 0  | 1  | 3  | 0  | -2  |
| Faces (0,1)                   | 16 | 32 | 4  | 1  | 13 | 0  | -12 |
| Middle slice (w=2)            | 6  | 0  | 0  | 6  | 0  | 0  | 6   |
| Gauge (h1=1)                  | 8  | 12 | 6  | 1  | 0  | 1  | 2   |
| Transverse pair (g3=0,h1=1)   | 4  | 4  | 1  | 1  | 0  | 0  | 1   |
| h1=1, w[2,3]                  | 6  | 6  | 0  | 1  | 1  | 0  | 0   |
| h1=1, w[1,4]                  | 8  | 12 | 6  | 1  | 0  | 1  | 2   |
| 3-bit cube (h1=1, no h1-flip) | 8  | 12 | 6  | 1  | 0  | 1  | 2   |

---

## 3. Key Findings

### Finding 1: A1' Topologically Cuts the Configuration Space

| Configuration     | β₀ (connected components) |
|-------------------|---------------------------|
| Full 4-cube       | 1                         |
| Remove single bit | 2                         |
| Remove bit pair   | 4                         |

Removing edges associated with a single bit position disconnects the hypercube into 2 components. Removing a bit pair
disconnects it into 4 components.

**Physical interpretation**: The transverse structure imposed by A1' acts as a topological cut. Each bit position that
is "removed" (or equivalently, whose dynamics are frozen) fragments the configuration space. The number of fragments is
2^(number of removed bits).

**Mathematical significance**: A1' is not just an algebraic constraint — it has measurable topological consequences (
change in β₀).

### Finding 2: A8 Creates Isolated Energy Layers

| Configuration                   | β₀ | β₁ |
|---------------------------------|----|----|
| Full 4-cube                     | 1  | 0  |
| Middle slice (w=2)              | 6  | 0  |
| Weight [1,3] (remove extremes)  | 1  | 0  |
| Weight [0,2] (remove top layer) | 1  | 0  |

The middle slice (weight=2) consists of 6 vertices with **zero edges** between them. Every single-bit flip from a
weight-2 vertex changes the weight to 1 or 3, leaving the middle slice.

**Physical interpretation**: The mid-section is an isolated potential minimum. Vertices are trapped in potential wells;
a bit-flip (energy cost) is required to leave. This is the geometric meaning of A8's "mid-section preference" — the
mid-section is not a connected basin but a set of isolated minima separated by barriers.

**Mathematical significance**: A8 is not a smooth optimization — it creates a discrete landscape with isolated minima,
analogous to a spin glass.

### Finding 3: Gauge Subspace Has Non-Trivial H₂

| Configuration                 | β₀ | β₁ | β₂ |
|-------------------------------|----|----|----|
| Gauge (h1=1)                  | 1  | 0  | 1  |
| 3-bit cube (h1=1, no h1-flip) | 1  | 0  | 1  |

The 3-cube (gauge subspace with h1 fixed) has β₂=1. This means there is one independent 2-cycle — a "hollow" structure.

**Physical interpretation**: The 2-cycle in the gauge subspace corresponds to the magnetic flux structure of the gauge
field. The 6 faces of the 3-cube form a closed 2-surface (a topological sphere), giving β₂=1.

### Finding 4: Weight Filter Reveals Layered Structure

| Filter                          | β₀ | β₁ | χ  |
|---------------------------------|----|----|----|
| Full (no filter)                | 1  | 0  | 8  |
| w[1,3] (remove extremes)        | 1  | 0  | 2  |
| w[0,2] (remove top)             | 1  | 0  | 1  |
| w[1,2] (middle bands, no faces) | 1  | 3  | -2 |
| w[0,3] (remove top only)        | 1  | 0  | 5  |

The Euler characteristic decreases as more extreme-weight vertices are removed, confirming that extreme-weight vertices
contribute disproportionately to the "volume" (β₂) of the complex.

### Finding 5: No Klein Bottle Detected

Klein bottle requires: H₀=Z, H₁=Z⊕Z/2, H₂=0. Over Z/2: β₀=1, β₁=2, β₂=0.

No subcomplex in {0,1}^4 satisfies this. The reasons:

1. **Faces are too strong**: every square face directly eliminates the loop it bounds (β₁ drops to 0 whenever faces are
   present).
2. **2-skeleton is insufficient**: the abab⁻¹ gluing pattern of Klein bottle requires identification of edges in a way
   that the standard cube faces don't provide.
3. **{0,1}^4 is too small**: the minimum triangulation of a Klein bottle requires more simplices than the 4-cube's
   2-skeleton contains.

**Conclusion**: Klein bottle does not emerge in the 2-skeleton of {0,1}^4 under current axiom constraints. Detection
would require either:

- Higher-dimensional cubes (k≥5)
- 3-skeleton (tetrahedra, not just squares)
- Modified face construction (non-standard identification)

---

## 4. Methodology Notes

### 4.1 Mod-2 vs Integer Homology

All computations use F₂ coefficients. This means:

- Z/2 torsion is invisible (it looks like a free generator over F₂)
- β₁ over F₂ can be larger than the free rank of H₁(Z)
- To detect Klein bottle (which has Z/2 torsion), one must compare mod-2 and integer homology

The current script computes mod-2 only. Integer homology computation (via Smith normal form) would be needed for full
torsion detection.

### 4.2 Limitations

| Limitation              | Impact                                                   |
|-------------------------|----------------------------------------------------------|
| Only mod-2 coefficients | Cannot distinguish free rank from torsion                |
| Only 2-skeleton         | No 3-cycles or higher                                    |
| No DAG constraint (A6)  | Irreversibility not modeled                              |
| No A1' phase structure  | U(1) phases not included                                 |
| k=4 only                | Small system, may miss structures requiring larger cubes |

### 4.3 Future Work

1. **Integer homology** via Smith normal form — detect Z/2 torsion
2. **A6 DAG constraint** — remove edges with "wrong" orientation, recompute
3. **Higher k** — {0,1}^5 or {0,1}^6 may reveal Klein bottle
4. **3-skeleton** — add tetrahedra, compute β₃
5. **A1' phase structure** — assign U(1) weights to edges, compute twisted homology

---

## 5. Summary

The homology computation confirms that axiom constraints have measurable topological effects on {0,1}^4:

- **A1'** cuts the configuration space into disconnected components
- **A8** creates isolated potential minima (not a connected basin)
- **A7** provides face structure that eliminates 1-cycles
- **Gauge subspace** has non-trivial H₂ (magnetic flux topology)

Klein bottle was not detected in the 2-skeleton of {0,1}^4. Further investigation with higher k, 3-skeleton, or integer
homology is needed.
