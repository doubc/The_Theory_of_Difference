# CLEM Numerical Verification Results: N=4 (Full Simplicial Complex)

*Generated on 2026-04-14 10:01:30*

---

## Summary

- **Mid-section weight:** w = 2
- **Maximum simplex dimension:** 2
- **f-vector:** (f_0=6, f_1=12, f_2=8)
- **Euler characteristic:** χ = 2
- **Betti numbers:** (b_0=1, b_1=0, b_2=1)

## Topological Interpretation

- **H₀ = ℤ^1:** 1 connected component(s)
- **H₁ = ℤ^0:** 0 independent loop(s)
- **H₂ = ℤ^1:** 1 void(s)/sphere(s)

**Conclusion:**

- The complex is topologically equivalent to a single $S^2$ ✓

---

## Detailed Combinatorial Data

### Vertices V (0-simplices)

- $v_0$: `(0, 0, 1, 1)`
- $v_1$: `(0, 1, 0, 1)`
- $v_2$: `(0, 1, 1, 0)`
- $v_3$: `(1, 0, 0, 1)`
- $v_4$: `(1, 0, 1, 0)`
- $v_5$: `(1, 1, 0, 0)`

### Directed Edges E (1-simplices)

- $e_0$: `(0, 0, 1, 1)` → `(0, 1, 0, 1)`
- $e_1$: `(0, 0, 1, 1)` → `(0, 1, 1, 0)`
- $e_2$: `(0, 0, 1, 1)` → `(1, 0, 0, 1)`
- $e_3$: `(0, 0, 1, 1)` → `(1, 0, 1, 0)`
- $e_4$: `(0, 1, 0, 1)` → `(0, 1, 1, 0)`
- $e_5$: `(0, 1, 0, 1)` → `(1, 0, 0, 1)`
- $e_6$: `(0, 1, 0, 1)` → `(1, 1, 0, 0)`
- $e_7$: `(0, 1, 1, 0)` → `(1, 0, 1, 0)`
- $e_8$: `(0, 1, 1, 0)` → `(1, 1, 0, 0)`
- $e_9$: `(1, 0, 0, 1)` → `(1, 0, 1, 0)`
- $e_10$: `(1, 0, 0, 1)` → `(1, 1, 0, 0)`
- $e_11$: `(1, 0, 1, 0)` → `(1, 1, 0, 0)`

### Triangular Faces F (2-simplices)

- $f_0$: `((0, 0, 1, 1), (0, 1, 0, 1), (0, 1, 1, 0))`
- $f_1$: `((0, 0, 1, 1), (0, 1, 0, 1), (1, 0, 0, 1))`
- $f_2$: `((0, 0, 1, 1), (0, 1, 1, 0), (1, 0, 1, 0))`
- $f_3$: `((0, 0, 1, 1), (1, 0, 0, 1), (1, 0, 1, 0))`
- $f_4$: `((0, 1, 0, 1), (0, 1, 1, 0), (1, 1, 0, 0))`
- $f_5$: `((0, 1, 0, 1), (1, 0, 0, 1), (1, 1, 0, 0))`
- $f_6$: `((0, 1, 1, 0), (1, 0, 1, 0), (1, 1, 0, 0))`
- $f_7$: `((1, 0, 0, 1), (1, 0, 1, 0), (1, 1, 0, 0))`

---

## Boundary Matrices

**Boundary Matrix $\partial_1$** (Size $6\times12$):

$$
-1 & -1 & -1 & -1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
1 & 0 & 0 & 0 & -1 & -1 & -1 & 0 & 0 & 0 & 0 & 0 \\
0 & 1 & 0 & 0 & 1 & 0 & 0 & -1 & -1 & 0 & 0 & 0 \\
0 & 0 & 1 & 0 & 0 & 1 & 0 & 0 & 0 & -1 & -1 & 0 \\
0 & 0 & 0 & 1 & 0 & 0 & 0 & 1 & 0 & 1 & 0 & -1 \\
0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 & 1 & 0 & 1 & 1
$$

**Boundary Matrix $\partial_2$** (Size $12\times8$):

$$
1 & 1 & 0 & 0 & 0 & 0 & 0 & 0 \\
-1 & 0 & 1 & 0 & 0 & 0 & 0 & 0 \\
0 & -1 & 0 & 1 & 0 & 0 & 0 & 0 \\
0 & 0 & -1 & -1 & 0 & 0 & 0 & 0 \\
1 & 0 & 0 & 0 & 1 & 0 & 0 & 0 \\
0 & 1 & 0 & 0 & 0 & 1 & 0 & 0 \\
0 & 0 & 0 & 0 & -1 & -1 & 0 & 0 \\
0 & 0 & 1 & 0 & 0 & 0 & 1 & 0 \\
0 & 0 & 0 & 0 & 1 & 0 & -1 & 0 \\
0 & 0 & 0 & 1 & 0 & 0 & 0 & 1 \\
0 & 0 & 0 & 0 & 0 & 1 & 0 & -1 \\
0 & 0 & 0 & 0 & 0 & 0 & 1 & 1
$$

### Verification: $\partial_k \circ \partial_{k+1} = 0$

- **∂_1 ∘ ∂_2 = 0:** ✓ Confirmed

**Result:** All boundary conditions satisfied. The chain complex is valid.

---

## Computational Details

- **rank($\partial_1$):** 5
- **rank($\partial_2$):** 7
- **Euler characteristic (direct):** χ = Σ(-1)^k f_k = 2
- **Euler characteristic (homology):** χ = Σ(-1)^k b_k = 2
