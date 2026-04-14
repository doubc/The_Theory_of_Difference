# Morse Function Construction on Johnson Graphs

**Status:** Reference Document  
**Last Updated:** 2026-04-14  
**Related Tasks:** [CLEM-TASK-01](../CLEM-TASK-01.md), [CLEM-TASK-02](../CLEM-TASK-02.md)

---

## Overview

Discrete Morse theory provides a powerful tool for simplifying homology computations on simplicial complexes. This document outlines the construction of Morse functions on Johnson graphs $J(N,k)$ and their application to CLEM topology verification.

---

## Theoretical Background

### Discrete Morse Functions

A **discrete Morse function** on a simplicial complex $K$ is a map:

$$f: K \to \mathbb{R}$$

satisfying certain conditions that mimic smooth Morse theory. Specifically, for each simplex $\sigma$:

1. At most one face $\tau < \sigma$ has $f(\tau) \geq f(\sigma)$
2. At most one coface $\rho > \sigma$ has $f(\rho) \leq f(\sigma)$

### Critical Simplices

A simplex $\sigma$ is **critical** if:
- No face $\tau < \sigma$ satisfies $f(\tau) \geq f(\sigma)$
- No coface $\rho > \sigma$ satisfies $f(\rho) \leq f(\sigma)$

**Key Result**: The number of critical $k$-simplices bounds the $k$-th Betti number:

$$b_k \leq \text{number of critical } k\text{-simplices}$$

This is the **Morse inequality**.

### Gradient Vector Fields

From a Morse function, we construct a **gradient vector field** $V$:
- Pair simplices $(\tau, \sigma)$ where $\tau < \sigma$ and $f(\tau) \geq f(\sigma)$
- Unpaired simplices are critical
- Gradient flow follows decreasing $f$ values

---

## Morse Functions on Johnson Graphs

### Natural Candidate: Hamming Weight

For Johnson graph $J(N,k)$, vertices correspond to $k$-element subsets of $\{1, 2, ..., N\}$.

**Simple Morse function**: Use subset "energy" based on element positions:

$$f(\{i_1, i_2, ..., i_k\}) = \sum_{j=1}^k i_j$$

**Properties:**
- Minimum: $f_\min = 1 + 2 + ... + k = k(k+1)/2$ (subset $\{1,2,...,k\}$)
- Maximum: $f_\max = (N-k+1) + ... + N = k(2N-k+1)/2$ (subset $\{N-k+1,...,N\}$)
- Symmetric around midpoint

### Example: J(4,2)

Vertices and their $f$ values:
```
{1,2}: f = 3  (minimum)
{1,3}: f = 4
{1,4}: f = 5
{2,3}: f = 5
{2,4}: f = 6
{3,4}: f = 7  (maximum)
```

**Gradient flow:**
- {1,2} → {1,3} → {1,4} or {2,3} → {2,4} → {3,4}
- Critical points: {1,2} (minimum), {3,4} (maximum)

**Critical simplex count:**
- 0-simplices: 2 critical ({1,2} and {3,4})
- 1-simplices: 0 critical (all paired in gradient flow)
- 2-simplices: 2 critical (top and bottom faces)

**Morse inequalities:**
- $b_0 \leq 2$ ✓ (actual: $b_0 = 1$)
- $b_1 \leq 0$ ✓ (actual: $b_1 = 0$)
- $b_2 \leq 2$ ✓ (actual: $b_2 = 1$)

Inequalities are satisfied but not tight. Better Morse functions may give tighter bounds.

---

## Applications to CLEM

### Simplifying Homology Computation

**Problem**: For large $N$ (e.g., $N=12$), direct homology computation is expensive.

**Solution**: Use discrete Morse theory to collapse complex while preserving homology.

**Algorithm:**
1. Construct Morse function $f$ on simplicial complex
2. Identify gradient vector field $V$
3. Collapse paired simplices (they don't contribute to homology)
4. Compute homology on reduced complex (only critical simplices)

**Benefit**: Reduced complex is much smaller, making computation feasible.

### Identifying Topological Transitions

As $N$ varies, topology may change. Morse theory helps identify **when** and **how**:

**Method:**
1. Compute Morse function for $J(N,k)$ at different $N$
2. Track critical point births/deaths
3. Critical point changes indicate topological transitions

**Example hypothesis:**
- $N=4$: Simple topology ($S^2$), few critical points
- $N=6$: More complex topology, additional critical points appear
- $N=12$: Chiral structure emerges, critical point asymmetry

### Understanding Essential vs. Redundant Structure

Not all simplices contribute to topology. Morse theory distinguishes:
- **Essential**: Critical simplices (determine homology)
- **Redundant**: Paired simplices (can be collapsed away)

**Physical interpretation:**
- Essential structure → Physical degrees of freedom
- Redundant structure → Gauge redundancy / unphysical modes

---

## Computational Implementation

### Python Pseudocode

```python
import numpy as np
from itertools import combinations

def morse_function_JNK(subset):
    """Simple Morse function on J(N,k) vertex."""
    return sum(subset)

def construct_gradient_field(vertices, edges, faces):
    """Construct gradient vector field from Morse function."""
    # Compute f values
    f_verts = {v: morse_function_JNK(v) for v in vertices}
    f_edges = {e: (f_verts[e[0]] + f_verts[e[1]])/2 for e in edges}
    f_faces = {f: np.mean([f_verts[v] for v in f]) for f in faces}
    
    # Pair simplices
    paired_verts = set()
    paired_edges = set()
    paired_faces = set()
    
    # Process edges: pair with lower vertex
    for edge in edges:
        v0, v1 = edge
        if f_verts[v0] < f_verts[v1]:
            paired_verts.add(v0)
            paired_edges.add(edge)
        else:
            paired_verts.add(v1)
            paired_edges.add(edge)
    
    # Process faces: pair with lower edge
    for face in faces:
        # Find edge with lowest f value
        edges_of_face = get_edges_of_face(face)
        min_edge = min(edges_of_face, key=lambda e: f_edges[e])
        paired_edges.add(min_edge)
        paired_faces.add(face)
    
    # Critical simplices are unpaired
    critical_verts = set(vertices) - paired_verts
    critical_edges = set(edges) - paired_edges
    critical_faces = set(faces) - paired_faces
    
    return {
        'critical_verts': critical_verts,
        'critical_edges': critical_edges,
        'critical_faces': critical_faces
    }

def verify_morse_inequalities(critical_counts, betti_numbers):
    """Check that Morse inequalities hold."""
    for k in range(3):
        if betti_numbers[k] > critical_counts[k]:
            print(f"WARNING: Morse inequality violated for b_{k}!")
            return False
    return True
```

### Integration with Existing Code

Modify `../scripts/Qwen精简Clem_morse.py` to include Morse analysis:

```python
# After computing boundary matrices and Betti numbers
gradient_field = construct_gradient_field(vertices, edges, faces)
critical_counts = {
    0: len(gradient_field['critical_verts']),
    1: len(gradient_field['critical_edges']),
    2: len(gradient_field['critical_faces'])
}

print(f"\nMorse Analysis:")
print(f"Critical 0-simplices: {critical_counts[0]}")
print(f"Critical 1-simplices: {critical_counts[1]}")
print(f"Critical 2-simplices: {critical_counts[2]}")
print(f"Betti numbers: {betti_numbers}")
print(f"Morse inequalities satisfied: {verify_morse_inequalities(critical_counts, betti_numbers)}")
```

---

## Advanced Topics

### Optimal Morse Functions

The simple "sum of elements" function works but may not be optimal. Research directions:

1. **Lexicographic ordering**: Order subsets lexicographically
2. **Distance-based**: Use distance from a reference vertex
3. **Spectral**: Use eigenvectors of graph Laplacian

**Goal**: Minimize number of critical simplices (tighten Morse inequalities).

### Persistent Homology Connection

Morse theory relates to persistent homology:
- Vary Morse function parameter (e.g., threshold)
- Track birth/death of homology classes
- Persistence diagram reveals robust topological features

**Application to CLEM**: Study how topology persists as we vary $N$ or add noise.

### Smooth Limit

As $N \to \infty$, discrete Morse theory should converge to smooth Morse theory on continuous manifolds.

**Question**: What is the smooth limit of Johnson graph Morse functions?

**Conjecture**: For $J(N, N/2)$ as $N \to \infty$, the limit is Morse theory on sphere $S^{N/2-1}$ or related symmetric space.

---

## References

1. Forman, R. (1998). "Morse Theory for Cell Complexes". *Advances in Mathematics* 134(1): 90-145.
2. Kozlov, D. (2008). *Combinatorial Algebraic Topology*. Springer. (Chapter 11: Discrete Morse Theory)
3. Ghrist, R. (2014). *Elementary Applied Topology*. Createspace.
4. Scoville, N. A. (2019). *Discrete Morse Theory*. American Mathematical Society.

---

## Related Files

- **Main CLEM script**: `../scripts/Qwen精简Clem_morse.py`
- **Johnson spectrum**: [johnson_spectrum.md](johnson_spectrum.md)
- **TASK-01 results**: [../CLEM-TASK-01.md](../CLEM-TASK-01.md)

---

**Maintained by:** David Du  
**Contact:** 276857401@qq.com
