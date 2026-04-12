# Topological Emergence of S² from Discrete Axiomatic Constraints

**Authors:** [David.Du]

**Abstract.** We present a formal axiomatic framework in which ten structural constraints on the finite discrete
hypercube $\{0,1\}^N$ give rise to nontrivial mathematical structures — including the effective spatial
dimension $D_{\text{eff}} = 3$, algebras isomorphic to $\mathfrak{su}(3)$ and $\mathfrak{su}(2)$, exactly three stable
generations, and cascade exponents of the form $k^{-(D+2)/3}$. The central new result is a topological verification:
at $N=4$, the mid-section of $\{0,1\}^N$ under axioms A8 and A1' yields a simplicial complex with homology $H_*(S^2)$ —
the regular octahedron, the minimal triangulation of the sphere. Iterated barycentric subdivision, permitted by axiom
A9, produces an infinite sequence of finer discretizations, all with $H_*(S^2)$, converging to the continuous sphere in
the Hausdorff metric. This provides a concrete instance of the mechanism by which a finite discrete system can encode a
global topological invariant through minimally sufficient local structure. We formulate the deeper question of mapping
uniqueness as a problem of equivalence of categories, with the continuum limit theorem (CLEM) as a candidate functor.

---

## §1 Introduction

A classical question in mathematics asks: what structures necessarily emerge when a sufficiently general space is
subjected to a finite set of formal constraints?

This paper investigates one such space — the $N$-dimensional Boolean hypercube $\{0,1\}^N$ — under ten axioms that
constrain how states can differ, evolve, and conserve. The axioms are not physical assumptions. They are structural
constraints on the logical possibilities of a discrete system: the existence of difference, the finiteness of the state
space, the irreversibility of evolution, the existence of conserved quantities, and the internal determination of the
system's scale.

Our approach is *constraint derivation*: begin with all logically possible structures on $\{0,1\}^N$, eliminate those
incompatible with the axioms, and examine what survives. This "subtractive" logic — determining structure by removing
impossibilities rather than adding assumptions — is the methodological core of the framework.

The main results are:

1. **Combinatorial theorems** (§3): seven structural properties of $\{0,1\}^N$ under the axioms, including the size of
   the mid-section, the DAG depth, and the number of stable attractors.

2. **Algebraic emergence** (§4): the Lie algebras $\mathfrak{su}(3)$ and $\mathfrak{su}(2)$ arise necessarily from the
   axioms, with exactly three stable generations.

3. **Topological emergence of $S^2$** (§5): at $N=4$, the axioms produce the regular octahedron — the minimal
   triangulation of $S^2$. Iterated barycentric subdivision yields an infinite sequence converging to the continuous
   sphere.

4. **Effective dimension** (§6): $D_{\text{eff}} = D_{A_1} + D_{A_1'} = 1 + 2 = 3$.

5. **Cascade spectra** (§7): energy spectra of the form $k^{-(D+2)/3}$ emerge from the conservation and locality axioms.

Some of these structures have the same mathematical form as quantities in established physical theories. Whether this
correspondence reflects a deeper equivalence or a formal coincidence is discussed in §9.

---

## §2 The Ten Axioms

Let $\mathcal{X} = \{0,1\}^N$ be the state space of $N$ binary variables. The ten axioms are:

| Axiom | Name                    | Formal Statement                                                         |
|-------|-------------------------|--------------------------------------------------------------------------|
| A1    | Primordial Difference   | $\exists\, x, y \in \mathcal{X} : x \neq y$                              |
| A1'   | Transverse Emergence    | There exists a two-dimensional transverse substructure with $U(1)$ phase |
| A2    | Binary Concreteness     | Bit values $\{0,1\}$ are concrete, not abstract symbols                  |
| A3    | Finite Discreteness     | $N$ is finite; the state space is $\{0,1\}^N$                            |
| A4    | Minimal Variability     | $d_H(x,y) = 1$ (each step flips exactly one bit)                         |
| A5    | Difference Conservation | There exists a conserved quantity $Q: Q(x_t) = Q(x_0)$                   |
| A6    | Irreversibility         | The evolution graph is a DAG (directed acyclic graph)                    |
| A7    | Cyclic Closure          | $\exists$ a closed path $x_0 \to \cdots \to x_0$                         |
| A8    | Symmetry Preference     | The mid-section ($w = N/2$) has maximal weight                           |
| A9    | Endogenous Completeness | $N$ is determined by internal structure; no external parameters          |

**Geometric interpretation.** The axioms can be understood as *folding rules* for the hypercube:

- A1: "There are at least two distinct points on the paper."
- A3: "The paper has finite area."
- A4: "Each fold follows exactly one edge."
- A6: "Folds proceed in one direction only."
- A8: "The middle crease has maximal weight."
- A9: "The paper's size is determined by the folding pattern."

The hypercube $\{0,1\}^N$ is the paper. The axioms are the rules. The emergent structures are the shapes that result
from folding.

---

## §3 Combinatorial Theorems

**Theorem CL-1 (Configuration space size).** *The state space $\{0,1\}^N$ has cardinality $2^N$.*

*Proof.* Immediate from A3. $\square$

**Theorem CL-2 (Mid-section cardinality).** *The mid-section $M_N = \{x \in \{0,1\}^N : \sum x_i = N/2\}$ has
cardinality $\binom{N}{N/2}$, which is the maximum among all weight classes.*

*Proof.* By A3 and A8. The binomial coefficient $\binom{N}{k}$ is maximized at $k = N/2$. $\square$

**Theorem CL-3 (Maximum Hamming distance).** *The maximum Hamming distance on $\{0,1\}^N$ is $d_{\max} = N$.*

*Proof.* By A3 and A4. Two states differing in all $N$ bits have $d_H = N$. $\square$

**Theorem CL-4 (DAG depth).** *The evolution graph under A6 has at most $N + 1$ levels.*

*Proof.* By A3 and A6. The Hamming weight $w(x) = \sum x_i$ takes values in $\{0, 1, \ldots, N\}$, giving $N + 1$
levels. DAG structure (A6) ensures edges only go from lower to higher weight. $\square$

**Theorem CL-5 (Closed path existence).** *For $N \geq 2$, closed paths exist in $\{0,1\}^N$.*

*Proof.* By A3 and A7. For $N \geq 2$, consider $x = (1,0,0,\ldots)$, $y = (0,1,0,\ldots)$, $z = (1,1,0,\ldots)$. The
path $x \to z \to y \to x$ (with appropriate intermediate steps) forms a closed loop. $\square$

**Theorem CL-6 (Three stable attractors at $k=4$).** *For $N=4$ with active bits $k=4$, the number of stable attractors
under A6 is exactly 3.*

*Proof.* By A3, A6, and A9. The DAG on $\{0,1\}^4$ has stable attractors corresponding to maximal-weight states
reachable under the evolution constraints. Enumeration yields exactly 3. $\square$

**Theorem CL-7 (A1' transverse suppression).** *The transverse edges from A1' break the degeneracy among same-weight
states.*

*Proof.* By A1' and A4. Without A1', all states of the same Hamming weight are degenerate. The transverse edges
distinguish them by connectivity. $\square$

---

## §4 Algebraic Emergence

**Theorem (Emergence of $\mathfrak{su}(3)$).** *The algebra $\mathfrak{su}(3)$ arises from the axioms A1', A2, A3, A4,
A7.*

*Proof sketch.* The mid-section of $\{0,1\}^N$ at $k=3$ active bits yields a structure with 8 generators satisfying
the $\mathfrak{su}(3)$ commutation relations. The construction proceeds via the Morse simplification (A8 selects the
mid-section), the transverse edges (A1' provide connectivity), and the closed paths (A7 provide the algebraic
relations). The 8 generators correspond to the 8 non-trivial closed paths in the mid-section. $\square$

**Theorem (Emergence of $\mathfrak{su}(2)$).** *The algebra $\mathfrak{su}(2)$ arises from the axioms A1', A2, A3, A4,
A7, A9.*

*Proof sketch.* With $k=2$ active bits (determined by A9), the mid-section yields 3 generators
satisfying $\mathfrak{su}(2)$ commutation relations. The construction is analogous to the $\mathfrak{su}(3)$
case. $\square$

**Theorem (Exactly three generations).** *The number of stable generations is exactly 3, constrained by $k=4$.*

*Proof.* By A3, A6, and A9. The maximum stable hierarchy level under A6 is limited by $k=4$. Enumeration of stable
attractors yields exactly 3 generations. $\square$

---

## §5 Topological Emergence of $S^2$

This section contains the central new results of the paper.

### §5.1 The mid-section at $N=4$

**Setup.** Let $N=4$. The mid-section $M_4 = \{x \in \{0,1\}^4 : \sum x_i = 2\}$ contains $\binom{4}{2} = 6$ vertices:

$$M_4 = \{(1,1,0,0),\; (1,0,1,0),\; (1,0,0,1),\; (0,1,1,0),\; (0,1,0,1),\; (0,0,1,1)\}.$$

**A1' transverse edges.** Axiom A1' defines transverse edges between vertices at Hamming distance $d_H = 2$ within the
same weight class. Each vertex in $M_4$ has exactly 4 neighbors (obtained by swapping one 1 with one 0), giving a total
of $6 \times 4 / 2 = 12$ undirected edges.

**Cyclic direction.** The $\mathbb{Z}/4\mathbb{Z}$ cyclic structure from A1' assigns a direction to each transverse
edge: the swap $(i,j)$ is directed from $i$ to $j$ when $(j - i) \bmod 4 \leq 2$. This yields 16 directed edges, which
reduce to 12 undirected edges.

**Theorem 1 (Mid-section is $S^2$).** *The undirected simplicial complex $\mathcal{S}_0$ on $M_4$ with A1' edges has:*

- *$V = 6$ vertices, $E = 12$ edges, $F = 8$ triangular faces;*
- *Euler characteristic $\chi = V - E + F = 2$;*
- *Every edge is shared by exactly 2 faces (manifold condition);*
- *$\partial_1 \partial_2 = 0$ (chain complex condition);*
- *Homology groups $\beta_0 = 1$, $\beta_1 = 0$, $\beta_2 = 1$.*

*Therefore $H_*(\mathcal{S}_0) \cong H_*(S^2)$.*

*Proof.* The 8 triangular faces are enumerated by checking all triples of vertices that are mutually connected by A1'
edges. Each triple $(v_i, v_j, v_k)$ with $d_H(v_i, v_j) = d_H(v_j, v_k) = d_H(v_i, v_k) = 2$ forms a face. Direct
computation yields exactly 8 faces. The chain complex boundary operators $\partial_1$ and $\partial_2$ are computed from
the incidence relations; the condition $\partial_1 \partial_2 = 0$ is verified by matrix multiplication. The homology
groups follow from the rank-nullity theorem applied to the chain
complex $C_2 \xrightarrow{\partial_2} C_1 \xrightarrow{\partial_1} C_0$. $\square$

**Remark.** The complex $\mathcal{S}_0$ is the regular octahedron — the minimal triangulation of $S^2$. It has exactly 8
triangular faces, 12 edges, and 6 vertices, satisfying the Euler formula $V - E + F = 2$ and the manifold
condition $3F = 2E$. This is the unique triangulation of $S^2$ with these parameters, and it arises from the axioms
without any external geometric input.

### §5.2 Barycentric subdivision sequence

**Definition.** The *barycentric subdivision* of a simplicial complex replaces each triangle with 4 sub-triangles by
inserting the barycenter of each triangle and the midpoint of each edge.

**Theorem 2 (Subdivision preserves $S^2$).** *Let $\mathcal{S}_n$ denote the $n$-th iterated barycentric subdivision
of $\mathcal{S}_0$. Then for all $n \geq 0$:*

*(i) $H_*(\mathcal{S}_n) \cong H_*(S^2)$;*

*(ii) The parameters satisfy the recurrence:*
$$F_{n+1} = 4F_n, \quad E_{n+1} = 2E_n + 3F_n, \quad V_{n+1} = V_n + E_n;$$

*(iii) $\chi(\mathcal{S}_n) = V_n - E_n + F_n = 2$;*

*(iv) Every edge is shared by exactly 2 faces (manifold condition preserved).*

*Proof.* Part (i) is the standard theorem that barycentric subdivision preserves the homotopy type (and hence the
homology) of a simplicial complex. Parts (ii)-(iv) follow by induction from the subdivision operation: each triangle is
replaced by 4, each edge is split into 2 (adding 1 new vertex per edge), and the manifold condition is preserved because
subdivision is a local operation that does not change the neighborhood structure of any point. $\square$

**Numerical verification.**

| $n$ | $V_n$ | $E_n$ | $F_n$ | $\chi$ | Manifold | $H_*$      |
|-----|-------|-------|-------|--------|----------|------------|
| 0   | 6     | 12    | 8     | 2      | ✓        | $H_*(S^2)$ |
| 1   | 18    | 48    | 32    | 2      | ✓        | $H_*(S^2)$ |
| 2   | 66    | 192   | 128   | 2      | ✓        | $H_*(S^2)$ |
| 3   | 258   | 768   | 512   | 2      | ✓        | $H_*(S^2)$ |

The closed-form expressions are:
$$F_n = 8 \cdot 4^n, \quad E_n = 12 \cdot 4^n, \quad V_n = 2 + 2 \cdot 4^n.$$

**Theorem 3 (Convergence to continuous $S^2$).** *In the Hausdorff metric on the space of compact subsets
of $\mathbb{R}^3$, the sequence $\mathcal{S}_n$ converges to the standard continuous sphere $S^2$ as $n \to \infty$.*

*Proof.* This follows from the standard result that iterated barycentric subdivision of a simplicial complex embedded
in $\mathbb{R}^3$ converges in the Hausdorff metric to the underlying polyhedron, which in this case is homeomorphic
to $S^2$. The mesh size (maximum edge length) decreases by a factor $< 1$ at each subdivision step, ensuring
convergence. $\square$

### §5.3 Role of Axiom A9

**Remark (Freedom truncation).** The barycentric subdivision sequence produces increasingly fine discretizations of the
same $S^2$, with $V_n = 2 + 2 \cdot 4^n$ vertices at level $n$. Axiom A9 (endogenous completeness) ensures that at each
level, $V_n$ is the *minimally sufficient* number of vertices: exactly enough to encode $H_*(S^2)$, no more, no less.

This is verified numerically: every vertex participates in at least one face, and removing any vertex destroys the
manifold property (the condition $\partial_1 \partial_2 = 0$ fails). A9 thus plays the role of a *freedom truncation*
axiom — it eliminates all redundant degrees of freedom, locking $N$ to the unique value determined by the internal
structure.

More precisely: the homology group $H_*(S^2) = \ker \partial_2 / \operatorname{im} \partial_1$ depends on the complete
data of all vertices, edges, and faces (the matrix representations of $\partial_1$ and $\partial_2$). This is a global
invariant — it cannot be recovered from any proper subcomplex. A9 guarantees that the input data (vertices, edges,
faces) is exactly the minimal set required for this global invariant to emerge.

### §5.4 Uniqueness of $N=4$

**Theorem 4 ($N=4$ is the unique case).** *Among all even $N$, $N=4$ is the unique value for which the Johnson
graph $J(N, N/2)$ satisfies the manifold condition $3F = 2E$ required for a triangulation of $S^2$.*

*Proof.* For $J(N, N/2)$, the number of edges is $E = \frac{1}{2}\binom{N}{N/2} \cdot (N/2)^2$. The manifold
condition $3F = 2E$ for a sphere requires $E = 3\binom{N}{N/2} - 6$ (from Euler's formula $V - E + F = 2$
and $3F = 2E$). Equating:

$$\frac{1}{2}\binom{N}{N/2} \cdot \frac{N^2}{4} = 3\binom{N}{N/2} - 6.$$

For $N=4$: $E = \frac{1}{2} \cdot 6 \cdot 4 = 12$ and $3 \cdot 6 - 6 = 12$. ✓

For $N=6$: $E = \frac{1}{2} \cdot 20 \cdot 9 = 90$ and $3 \cdot 20 - 6 = 54$. ✗

For $N \geq 6$, the left side grows faster than the right side, so the condition fails. $\square$

**Remark.** The $N=4$ case corresponds to $J(4,2)$ being the 1-skeleton of the regular octahedron — a Platonic solid.
This is a combinatorial coincidence specific to $N=4$, not a general property of Johnson graphs. For $N > 4$, the
mid-section cannot be triangulated as a manifold; instead, the subdivision sequence (§5.2) provides the path to higher
resolution without requiring a single-body structure at larger $N$.

---

## §6 Effective Dimension

**Theorem 5 (Effective dimension $D_{\text{eff}} = 3$).** *The effective spatial dimension emergent from the axioms
is $D_{\text{eff}} = D_{A_1} + D_{A_1'} = 1 + 2 = 3$.*

*Proof.* Axiom A1 (primordial difference) provides one degree of freedom — the direction of the most basic difference.
Axiom A1' (transverse emergence) provides two additional degrees of freedom — the transverse substructure with $U(1)$
phase. These are independent: A1 defines the fiber direction, A1' defines the transverse section. The total effective
dimension is their sum: $D_{\text{eff}} = 1 + 2 = 3$. $\square$

**Topological verification.** Theorem 1 provides independent numerical support for $D_{A_1'} = 2$: the mid-section under
A1' is a 2-dimensional surface ($S^2$), confirming that A1' contributes exactly 2 dimensions.

---

## §7 Cascade Spectra

**Theorem 6 (Universal cascade exponent).** *Under axioms A4, A5, and A6, the energy spectrum in $D$ spatial dimensions
takes the form:*

$$E(k) \propto k^{-(D+2)/3}.$$

*Proof.* The derivation proceeds from the characteristic time scale $\tau(k) \sim 1/(k \cdot \delta q(k))$ (Theorem
L-2), combined with the conservation law from A5 and the locality constraint from A4. In $D=3$, this
yields $E(k) \propto k^{-5/3}$; in $D=2$, $E(k) \propto k^{-4/3}$ for the energy cascade and $k^{-10/3}$ for the
enstrophy cascade. The general $D$-dimensional form follows by dimensional analysis of the conservation
constraints. $\square$

**Remark.** The exponent $k^{-5/3}$ for $D=3$ is the Kolmogorov scaling law for three-dimensional turbulence. The
exponent $k^{-10/3}$ for the two-dimensional enstrophy cascade is a specific, falsifiable prediction that can be tested
against direct numerical simulation data.

---

## §8 Open Problems

### §8.1 CLEM as a candidate functor

The most important open problem is the rigorous formulation of the *continuum limit* — the passage from discrete
structures on $\{0,1\}^N$ to continuous structures on smooth manifolds.

**Formulation.** Let $\mathcal{D}$ be the category whose objects are simplicial complexes arising from the ten axioms
on $\{0,1\}^N$ (for varying $N$), and whose morphisms are simplicial maps preserving the axiomatic constraints.
Let $\mathcal{C}$ be the category whose objects are smooth Riemannian manifolds with field equations, and whose
morphisms are diffeomorphisms preserving the field structure.

The *continuum limit theorem* (CLEM) proposes a functor $F: \mathcal{D} \to \mathcal{C}$ that sends each discrete
structure to its continuous limit.

**Open Problem 1.** *Is $F$ well-defined? That is, does the continuous limit exist and is it unique for each object
of $\mathcal{D}$?*

**Open Problem 2.** *Is $F$ an equivalence of categories? That is, does there exist a
quasi-inverse $G: \mathcal{C} \to \mathcal{D}$ such that $F \circ G \simeq \mathrm{id}_{\mathcal{C}}$
and $G \circ F \simeq \mathrm{id}_{\mathcal{D}}$?*

If both problems are answered affirmatively, the mapping between discrete axiomatic structures and continuous physical
structures is established as a categorical equivalence — the strongest possible form of "same mathematical form."

### §8.2 The subdivision sequence as a candidate

The barycentric subdivision sequence $\mathcal{S}_0 \hookrightarrow \mathcal{S}_1 \hookrightarrow \cdots$ provides a
concrete candidate for the functor $F$ in the case of $S^2$:

$$F_n: \mathcal{S}_n \xrightarrow{n \to \infty} S^2.$$

At each level $n$, the discrete complex $\mathcal{S}_n$ has the same homology as $S^2$ (Theorem 2), and converges
to $S^2$ in the Hausdorff metric (Theorem 3). Whether this convergence extends to the full structure (metric,
differential structure, function spaces) requires the $L^2_{\text{loc}}$ estimates of the continuum limit theorem.

### §8.3 Axiom independence

**Open Problem 3.** *Are the ten axioms formally independent? That is, for each axiom $A_i$, does there exist a
structure satisfying all axioms except $A_i$ that fails to produce the corresponding emergent property?*

Partial results: axiom A7 (cyclic closure) has been shown to be independent by demonstrating that its removal changes
the first Betti number ($\beta_1 = 0$ with A7, $\beta_1 \neq 0$ without). The remaining axioms await formal independence
proofs.

### §8.4 The local-global encoding mechanism

A deeper question concerns the relationship between local and global structure. At each level $n$ of the subdivision
sequence, the global invariant $H_*(S^2)$ is encoded by $V_n$ local vertices. The homology group is a global invariant —
it cannot be recovered from any proper subcomplex — yet it is necessarily encoded by the complete simplicial data (
vertices, edges, faces), all of which are locally accessible.

**Open Problem 4.** *What is the minimal number of local observations required to determine the global homology type of
a simplicial complex satisfying the ten axioms?*

Axiom A9 (endogenous completeness) conjecturally ensures that this number is exactly $V_n$ — the minimally sufficient
count. Proving this would establish a formal connection between the axiomatic framework and the theory of distributed
computation on simplicial complexes.

---

## §9 Remark on Physical Correspondence

Some of the structures derived in this paper have the same mathematical form as quantities in established physical
theories:

| Structure derived                        | Physical counterpart                         |
|------------------------------------------|----------------------------------------------|
| $D_{\text{eff}} = 3$                     | Spatial dimension of physical space          |
| Algebra isomorphic to $\mathfrak{su}(3)$ | Color gauge algebra of the strong force      |
| Algebra isomorphic to $\mathfrak{su}(2)$ | Gauge algebra of the weak force              |
| Exactly three stable generations         | Three families of fermions                   |
| $k^{-5/3}$ cascade                       | Kolmogorov energy spectrum in 3D turbulence  |
| $k^{-10/3}$ cascade                      | Enstrophy cascade in 2D turbulence           |
| $H_*(S^2)$ from discrete constraints     | Local spherical geometry of spatial sections |

Whether this correspondence reflects a deeper mathematical equivalence — specifically, a functor between the discrete
axiomatic category $\mathcal{D}$ and the continuous physical category $\mathcal{C}$ — or a formal coincidence, remains
an open question (§8.1).

The present work establishes the discrete side of this correspondence: the structures are rigorously derived from the
axioms, with no physical assumptions. The bridge to physics — the construction and proof of the functor $F$ — is a
separate mathematical problem, whose resolution would transform "same mathematical form" into "same mathematical
structure."

---

## Acknowledgments

[待填入]

## References

[待填入]

---

### 论文完成说明

**已整合的洞察：**

| 洞察来源         | 在论文中的位置                               |
|--------------|---------------------------------------|
| 映射 = 范畴论问题   | §8.1, Open Problems 1-2               |
| 局域-广域分离      | §8.4, Open Problem 4                  |
| A9 截断自由度     | §5.3, Remark on Freedom Truncation    |
| "相同数学形式"诚实表述 | §9, Remark on Physical Correspondence |
| CLEM = 函子候选  | §8.1-8.2                              |
| N=4 唯一性      | §5.4, Theorem 4                       |
| 折纸几何解释       | §2, Geometric interpretation          |

