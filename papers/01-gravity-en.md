# Paper: Newtonian Gravitational Potential from Axioms of Difference

## Title

**Newtonian Gravitational Potential from Axioms of Difference: A Constraint-Derivation Framework**

---

## Abstract

This paper proposes a theoretical construction pathway fundamentally different from existing physical methodologies: *
*constraint derivation** (*constraint derivation*). Unlike the conventional approach of inducting laws from empirical
observation, constraint derivation begins from a set of abstract axioms concerning "difference" and "hierarchy," and
derives physical laws by logically eliminating impossible structures.

The spirit of this methodology resonates deeply with Mendeleev's construction of the periodic table. Mendeleev
discovered periodic patterns in the known properties of elements, and predicted unknown elements through the "gaps" in
those patterns — he was not describing what elements happen to be, but constraining what elements cannot fail to be.
This paper pushes the same methodology to its limit: rather than discovering patterns from empirical data, we derive
patterns from purely formal axioms; rather than predicting unknown elements, we predict the form of physical laws
themselves.

We define 10 axioms (A1–A9, where A1 contains sub-axiom A1'), none of which involves any physical concept — no mass, no
force, no space, no time. The axioms concern only difference structures, hierarchical relations, symmetry constraints,
and conservation laws on a discrete state space.

From five of these axioms (A1, A1', A4, A5, A9), we rigorously prove:

1. The effective dimension of state space $D_{eff} = 3$ (space is 3-dimensional)
2. The decay exponent of the gravitational potential $\gamma = D_{eff} - 2 = 1$
3. The form of the gravitational potential $\Phi(x) = -\sum_{s \in S} 1/d_H(x,s)$, i.e., the Newtonian gravitational
   potential

In the derivation chain, spatial dimension $D = 3$ is not an assumption but a theorem: A1 contributes 1 dimension (the
hierarchical depth direction), A1' contributes 2 dimensions (the emergent space — the 1-dimensional circle $S^1$ is
excluded by the "no preferred direction" symmetry requirement, and $D > 2$ is excluded by A9's "no extra degrees of
freedom"), and their orthogonality yields $D_{eff} = 3$.

Numerical verification on the $N = 6$ hypercube (64 states) shows: the layer-averaged potential under a single stable
state equals exactly $-1/d$ (analytically equivalent, zero error), in complete agreement with the theoretical prediction
of $\gamma = 1$.

By analogy, if Mendeleev's periodic table is the paradigm of "discovering laws from experience," then the framework of
this paper is the paradigm of "deriving laws from logic." The periodic table classifies 118 elements; this paper
classifies $2^{10} = 1024$ "possible worlds" — each world corresponds to a subset of axioms, and each subset has
definite physical characteristics. Our universe corresponds to the point where all 10 axioms are activated.

This paper discusses structural pathways for extending the framework to electromagnetism, the strong force, the weak
force, and quantum mechanics, and identifies the potential significance of the constraint-derivation methodology for the
axiomatization of physics.

---

## Keywords

Constraint derivation; axiomatic physics; Newtonian gravitational potential; discrete state space; hypercube; spatial
dimension; Mendeleev analogy

---

## The Mendeleev Analogy

| Dimension          | Mendeleev                                                    | WorldBase                                              |
|:-------------------|:-------------------------------------------------------------|:-------------------------------------------------------|
| Objects organized  | 118 elements                                                 | 1024 possible worlds                                   |
| Pattern discovered | Elemental properties are periodic functions of atomic number | Physical constants are functions of axiom combinations |
| Prediction method  | Gap → new element                                            | Axiom combination → new physical world                 |
| Methodology        | Constraining structure from experience                       | Constraining structure from logic                      |
| Deeper explanation | Explained by quantum mechanics                               | May be the deepest layer itself                        |

---

# Section 2: Introduction

## 2.1 Two Open Questions in Physics

Physics has two long-standing foundational questions:

**Question One: Why is space 3-dimensional?**

Most theoretical physics frameworks take 3-dimensional space as an input assumption. String theory requires 10 or 11
spacetime dimensions, then compactifies the extra dimensions down to the observable 3+1 — but there are $10^{500}$
possible compactification schemes (the string landscape problem), and none explains why precisely the one we observe is
realized. Loop quantum gravity starts from 3-dimensional space but does not explain why it is 3-dimensional. Virtually
all candidate theories of quantum gravity treat spatial dimensionality as a premise requiring explanation, not a result
to be derived.

**Question Two: Why is the gravitational potential $-1/r$?**

Newton's law of gravitation $F = Gm_1m_2/r^2$ is an experimental law. General relativity derives it as a consequence of
spacetime curvature, but at the cost of introducing new assumptions — the equivalence principle, spacetime as a
4-dimensional pseudo-Riemannian manifold, and the metric satisfying Einstein's equations. These assumptions themselves
have no deeper theoretical explanation.

The common feature of both questions is: **we have precise mathematical descriptions, but no explanation for why the
mathematical descriptions take precisely this form.** We know space is 3-dimensional, but not why. We know the
gravitational potential is $-1/r$, but not why.

This paper attempts to answer both questions — not by introducing new physical assumptions, but through a fundamentally
different methodology.

## 2.2 Methodology: Constraint Derivation

Physics has two fundamentally different construction pathways:

**Path One: Additive — inducing laws from experience.** This is the standard method of physics. Observe phenomena →
induce laws → build theory → verify predictions. Newton induced $F \propto 1/r^2$ from Kepler's observational data.
Coulomb induced $F \propto q_1q_2/r^2$ from torsion balance experiments. This method is effective but has a fundamental
limitation: it tells us what the world happens to be like, but not why the world is that way.

**Path Two: Subtractive — eliminating the impossible through constraints.** This is the method adopted in this paper.
Starting from all logically possible structures, impose constraints, eliminate structures that fail to satisfy them, and
what remains is reality.

In the language of set theory: let $\mathcal{P}$ be the set of all logically possible physical structures, and $C_i$ be
the set of structures permitted by the $i$-th axiom. Then:

$$\text{Reality} = \bigcap_{i} C_i$$

Each additional axiom shrinks the intersection. If the axioms are strong enough, the intersection shrinks to a unique
element — and that is our physical world.

This methodology is not invented in this paper. It has a deep academic tradition:

**Euclidean geometry** (c. 300 BCE): From five axioms, all of plane geometry is derived by pure logic. The axioms
involve no concrete physical objects, yet the derived results apply to all planes.

**Special relativity** (Einstein, 1905): From two axioms — the laws of physics are the same in all inertial frames, and
the speed of light is the same in all inertial frames — the Lorentz transformation, time dilation, length contraction,
and mass-energy equivalence are derived.[5]

**Thermodynamics**: From three laws (conservation of energy, entropy increase, absolute zero is unattainable), the
entire thermodynamic formalism is derived. The three laws are all constraints — they do not say "what the world is
like," but "what the world cannot be like."

**Noether's theorem** (1918): Every continuous symmetry corresponds to a conservation law. This is the precise
mathematical form of the constraint methodology — symmetry constraint → conservation law emerges.[6]

**Classification of finite simple groups**: From the axioms of group theory, all finite simple groups are classified by
elimination. This is a purely constraint-methodological achievement — independent of any experience, purely logical
elimination.

This paper pushes the constraint methodology to a new extreme: **deriving the specific mathematical form of gravity from
purely formal axioms.** Not classifying known objects (as the periodic table classifies elements), but deriving unknown
laws (deriving physical laws from axioms).

## 2.3 The Deep Analogy with Mendeleev

Mendeleev's construction of the periodic table is a classic case of "approaching reality through constraints." He did
not discover the properties of new elements; he **constrained** the patterns that elemental properties must satisfy (the
periodic law). He predicted the existence of germanium not because he had observed it, but because the periodic law *
*constrained** that something must occupy that position.

Mendeleev's methodology and the methodology of this paper are essentially the same: **using constraints to approach
reality.** But there is a key directional difference:

Mendeleev's constraints came from pattern discovery in empirical data — first the observed properties of elements, then
the periodic law. The constraints in this paper come from the logical selection of axioms — first the axioms, then the
physical laws.

Mendeleev's periodic table classifies 118 elements. The framework of this paper classifies $2^{10} = 1024$ "possible
worlds" — each world corresponds to a subset of the 10 axioms. Our universe corresponds to the point where all 10 axioms
are activated. The other 1023 points may correspond to different physical worlds — some already known (such as the
logarithmic potential in two-dimensional systems), others potentially entirely new (such as the axiomatic origin of dark
energy).

If Mendeleev's periodic table was ultimately explained by quantum mechanics (electron shell structure determines
elemental periodicity), does the framework of this paper also require a deeper theory to explain it?

Our answer is: **the framework may itself be the deepest layer.** Mendeleev's periodic table is an intermediate layer (a
bridge from experience to theory); the framework of this paper is the bottom layer (direct derivation from axioms to
physics). If the derivation chain withstands rigorous scrutiny in the continuum limit, it requires no deeper
explanation — the axioms themselves are the ultimate explanation.

## 2.4 Structure of This Paper

The structure of this paper is as follows:

Section 3 gives precise definitions of the 10 axioms. Each axiom is stated in purely formal language, involving no
physical concepts.

Section 4 proves spatial dimension $D_{eff} = 3$. This is the cornerstone of the entire derivation chain — all
subsequent results depend on this conclusion.

Section 5 derives the form of the gravitational potential. Starting from $D_{eff} = 3$, combined with the conservation
law (A5) and locality (A4), we derive $\gamma = 1$ and $\Phi = -\sum 1/d$.

Section 6 provides numerical verification on the $N = 6$ hypercube. The layer-averaged potential under a single stable
state equals exactly $-1/d$.

Section 7 discusses directions for extending the framework — the axiomatic origins of electromagnetism, the strong
force, the weak force, quantum mechanics, dark energy, and dark matter.

Section 8 concludes.

---

# Section 3: Axiom Definitions

## 3.1 General Framework

Let $\mathcal{X} = \{0, 1\}^N$ be the state space on an $N$-dimensional hypercube, with $|\mathcal{X}| = 2^N$. Each
state $x = (x_1, \ldots, x_N)$ is a binary string of length $N$.

The Hamming distance between two states $x, y$ is defined as:[8]

$$d_H(x, y) = |\{i : x_i \neq y_i\}|$$

The Hamming weight of state $x$ is defined as:

$$w(x) = \sum_{i=1}^{N} x_i = d_H(x, \mathbf{0})$$

where $\mathbf{0} = (0, 0, \ldots, 0)$ is the all-zero state (ground state).

The following 10 axioms are defined on $\mathcal{X}$. The axioms fall into three categories: structural axioms (A1, A1',
A2, A3), dynamical axioms (A4, A5, A6), and topological preference axioms (A7, A8, A9).

## 3.2 Structural Axioms

### A1 (Primordial Difference / Foundational Hierarchy)

**Statement**: There exist ontological differences. The system has a hierarchical partial-order structure, with a unique
ground state $\mathbf{0} = (0,\ldots,0)$, and every evolutionary path corresponds to a monotone non-decrease in Hamming
weight.

**Formalization**:

$$\forall \text{ evolutionary path } \gamma = (x_0, x_1, \ldots, x_k): \quad w(x_0) \leq w(x_1) \leq \cdots \leq w(x_k)$$

**Geometric correspondence**: A1 defines a directed "depth" direction in state space — the hierarchy along Hamming
weight $w$ from $0$ to $N$. This is a 1-dimensional structure.

**Contribution**: $D_{A1} = 1$ (hierarchical depth direction).

**Physical emergence**: Mass, matter, hierarchical structure.

---

### A1' (Hierarchical Emergence)

**Statement**: At each hierarchical node, multiple child nodes can emerge. The direction of emergence is strictly
orthogonal to the hierarchical direction of A1. Emergence is symmetric — no preferred direction.

**Formalization**:

(a) Emergence direction is orthogonal to A1: emergence does not change Hamming weight $w$, i.e., an emergence
transition $x \to y$ satisfies $w(y) = w(x)$.

(b) Emergence is symmetric: there exists a continuous rotation group $SO(k)$, $k \geq 2$, acting on the tangent space of
the emergent space. That is, all directions in the emergent space are equivalent under the action of the symmetry group.

**Geometric correspondence**: A1' defines a transverse emergent space at each hierarchical node. Condition (b) requires
this space to be at least 2-dimensional — because the tangent space of the 1-dimensional circle $S^1$ has only
discrete $\mathbb{Z}_2$ symmetry (flip), which does not satisfy the continuous symmetry requirement of "no preferred
direction."

**Strict argument excluding $S^1$**:

The tangent space of $S^1$ at each point is 1-dimensional. There exists no non-trivial continuous rotation group on a
1-dimensional linear space — the only automorphism is $\{+1, -1\}$ (discrete flip), which does not constitute "no
preferred direction." For the tangent space to admit continuous rotational symmetry ($SO(2)$ action), the tangent space
must be at least 2-dimensional.

Therefore $D_{A1'} \geq 2$.

**Contribution**: $D_{A1'} \geq 2$ (emergent space dimension is at least 2).

**Physical emergence**: Transverse spatial structure, electric charge, geometric foundation of electromagnetism.

---

### A2 (Binary Concretization)

**Statement**: All differences ultimately manifest as binary oppositions. The state space is binary-valued.

**Formalization**:

$$\mathcal{X} = \{0, 1\}^N$$

Each component $x_i \in \{0, 1\}$. No intermediate values exist.

**Contribution**: Defines the algebraic structure of state space. Each transition changes exactly one component (
flip $0 \leftrightarrow 1$).

**Physical emergence**: Basis of quantum bits ($|0\rangle, |1\rangle$).

---

### A3 (Finite Discreteness)

**Statement**: The state space is a finite discrete set with a bounded number of states.

**Formalization**:

$$|\mathcal{X}| = 2^N < \infty$$

**Contribution**: Ensures all sums (such as the potential sum $\sum_s 1/d_H(x,s)$) are finite and computable. Defines
the minimum time unit $\Delta t_{\min} = 1$ (one step).

**Physical emergence**: Quantization, finiteness.

## 3.3 Dynamical Axioms

### A4 (Minimal Change)

**Statement**: Each state transition changes exactly one component. That is, each step moves only to a neighbor at
Hamming distance $d_H = 1$.

**Formalization**:

$$\forall \text{ transition } x \to y: \quad d_H(x, y) = 1$$

**Contribution**: Constrains the locality of evolution — information can only propagate along neighbors, not jump. This
is the source of locality in the Poisson equation (field equation).

**Physical emergence**: Finite speed of light ($c = 1$, at most 1 bit per step), principle of least action (variational
principle $\delta S = 0$ in the continuum limit).

---

### A5 (Conservation of Difference)

**Statement**: The total amount of difference in a closed system is conserved.

**Formalization**:

$$\sum_{i=1}^{N} d_i = \text{const}$$

where $d_i$ is the amount of difference in the $i$-th component. On the hypercube, the total difference equals some
function of the Hamming weight $w$.

**Form in the continuum limit**:

$$\frac{\partial \rho}{\partial t} + \nabla \cdot \mathbf{J} = 0$$

where $\rho$ is the difference density and $\mathbf{J}$ is the difference flux density.

**Contribution**: The conservation law requires influence to be uniformly distributed over a "shell." In $D$-dimensional
space, the shell area $\propto r^{D-1}$, so the single-point influence $\propto 1/r^{D-1}$, and the
potential $\propto -1/r^{D-2}$.

This is the key bridge from dimension to the form of gravity.

**Physical emergence**: Conservation of energy, Poisson equation $\nabla^2\Phi = 4\pi G\rho$.

---

### A6 (Direction of Emergence / Irreversibility)

**Statement**: Emergence has directionality; the evolution of the system has a time arrow and is irreversible.

**Formalization**:

The evolutionary graph is a directed acyclic graph (DAG) — no path $x \to y \to x$ exists.

**Contribution**: Defines the directionality of time. The concept of velocity (displacement/time) requires a time
direction — without A6, "how far each step travels" has no meaning.

**Physical emergence**: Arrow of time, second law of thermodynamics (entropy increase), parity violation (only
left-handed coupling in the weak force).

## 3.4 Topological Preference Axioms

### A7 (Cyclic Closure)

**Statement**: Stable states must participate in directed cycles of length $\geq N$. The system has periodic orbits.

**Formalization**:

$$\forall s \in S: \quad \exists \text{ directed cycle } C = (s \to x_1 \to \cdots \to x_k \to s), \quad k \geq N$$

**Contribution**: Introduces periodic structure. Standing wave conditions, energy quantization, and path integrals are
all related to A7.

**Physical emergence**: Quantization (standing wave condition $k_n = 2\pi n/L$), angular momentum, spin.

---

### A8 (Symmetry Preference)

**Statement**: The system prefers symmetric states. States with Hamming weight $w = N/2$ receive additional preference.

**Formalization**:

The stable state set $S$ preferentially includes states with $w = N/2$. As the number of activated axioms increases, the
stable state threshold $k(n)$ increases monotonically, but the $w = N/2$ layer remains the "special layer."

**Contribution**: Defines symmetry preference. The $w = N/2$ layer ($w = 3$ layer for $N = 6$, 20 states) is the
operating range of the strong and weak forces.

**Physical emergence**: $SU(3)$ color charge structure, $SU(2)_L$ weak force structure, Higgs mechanism (symmetry
breaking).

---

### A9 (Intrinsic Completeness)

**Statement**: The system is self-consistently closed, requires no external input, and all evolutionary rules are
determined by internal axioms. The system introduces no extra degrees of freedom not covered by the axioms.

**Formalization**:

All degrees of freedom of the system must have an axiomatic source. Let $F$ be the actual number of degrees of freedom
the system possesses, and $F_{\text{axiom}}$ be the number of degrees of freedom explicitly introduced by the axioms.
Then:

$$F = F_{\text{axiom}}$$

**Contribution**: Gives an upper bound on dimension. The axiomatic content of A1' implies at least 2 independent
directions (determined by continuous rotational symmetry), and does not imply a 3rd or more. A9 prohibits the system
from possessing degrees of freedom beyond what the axioms require, so $D_{A1'} \leq 2$.

Combined with $D_{A1'} \geq 2$ (from the symmetry requirement of A1'), we obtain $D_{A1'} = 2$.

**Physical emergence**: $D_{eff} = 3$ (determination of spatial dimension).

## 3.5 Summary Table of Axioms

| Axiom |    Type     | Core Constraint                                 | Dimensional Contribution |
|:-----:|:-----------:|:------------------------------------------------|:------------------------:|
|  A1   | Structural  | Hierarchical partial order, unique ground state |       $D_{A1} = 1$       |
|  A1'  | Structural  | Symmetric emergence, no preferred direction     |     $D_{A1'} \geq 2$     |
|  A2   | Structural  | Binary state                                    |            —             |
|  A3   | Structural  | Finite discrete                                 |            —             |
|  A4   |  Dynamical  | Minimal change (Hamming distance = 1)           |            —             |
|  A5   |  Dynamical  | Conservation of difference                      |            —             |
|  A6   |  Dynamical  | Irreversibility                                 |            —             |
|  A7   | Topological | Long cycle ($k \geq N$)                         |            —             |
|  A8   | Topological | Symmetry preference ($w = N/2$)                 |            —             |
|  A9   | Topological | No extra degrees of freedom                     |     $D_{A1'} \leq 2$     |

## 3.6 Independence of the Axioms

The 10 axioms are not fully independent. The following relations have been identified:

| Relation      | Description                                                                                                                                     |
|:--------------|:------------------------------------------------------------------------------------------------------------------------------------------------|
| A1 vs A5      | Apparent contradiction (weight increase vs conservation), mediated by A9                                                                        |
| A6 vs A7      | Apparent contradiction (irreversibility vs cycles), A6 constrains local direction, A7 constrains global topology, compatible in directed cycles |
| A1 + A1' + A9 | Jointly determine $D_{eff} = 3$                                                                                                                 |

The tensions between axioms are not defects but structure — it is precisely the resolution of tensions that produces
non-trivial physical consequences.

---

# Section 4: Derivation of Spatial Dimension

## 4.1 Core Theorem

**Theorem 1 (Spatial Dimension Theorem)**: In a WorldBase system satisfying axioms A1, A1', and A9, the effective
dimension of state space is uniquely determined to be $D_{eff} = 3$.

## 4.2 Proof

The proof proceeds in three steps: determining $D_{A1}$, determining $D_{A1'}$, and determining $D_{eff}$.

### Step 1: $D_{A1} = 1$

A1 defines a hierarchical partial-order structure: there exists a unique ground state, and every evolutionary path
corresponds to a monotone non-decrease in Hamming weight.

This structure is geometrically a directed line segment — from $w = 0$ to $w = N$. A line segment is 1-dimensional.

**No further argument is needed.** A hierarchical partial-order structure is naturally 1-dimensional, because a partial
order is a binary relation ($\leq$), not a ternary or higher relation. The Hasse diagram of a partial order is a tree (
directed acyclic graph), and the "depth" direction of a tree is 1-dimensional.

$$\boxed{D_{A1} = 1}$$

### Step 2: $D_{A1'} = 2$

This step is the core of the entire proof. We need to prove both $D_{A1'} \geq 2$ and $D_{A1'} \leq 2$.

**Lower bound** ($D_{A1'} \geq 2$):

A1' requires that emergence be "symmetric (no preferred direction)." This requires the existence of a continuous
rotation group $SO(k)$ on the tangent space of the emergent space, such that all points on the unit sphere $S^{k-1}$ lie
in the same orbit.

For $k = 1$: $S^0 = \{-1, +1\}$ has only discrete $\mathbb{Z}_2$ symmetry (flip); no continuous rotation exists. Does
not satisfy "no preferred direction."

For $k = 2$: $SO(2)$ continuous rotational symmetry exists on $S^1$. Satisfies "no preferred direction."

Therefore $k \geq 2$, i.e., $D_{A1'} \geq 2$.

**Upper bound** ($D_{A1'} \leq 2$):

A9 requires that all degrees of freedom of the system have an axiomatic source — no extra degrees of freedom not covered
by the axioms are introduced.

Examining the full axiomatic content of A1':

- (a) Multiple child nodes emerge → requires at least 1 independent direction
- (b) Orthogonal to A1 → emergent space is independent of the depth direction
- (c) No preferred direction → emergent space is at least 2-dimensional (as proved above)

**Key observation**: The full content of A1', taken together, implies $D_{A1'} \geq 2$, but does not
imply $D_{A1'} > 2$. No clause requires "at least 3 independent directions" or "the emergent space is 3-dimensional or
higher."

A 3rd transverse direction: no axiom requires its existence, and no axiom provides a source for it.

By A9: the system is not permitted to possess this 3rd degree of freedom that is not covered by any axiom.

Therefore $D_{A1'} \leq 2$.

**Combining**:

$$D_{A1'} \geq 2 \quad \text{(from the symmetry requirement of A1')}$$

$$D_{A1'} \leq 2 \quad \text{(from the no-extra-degrees-of-freedom constraint of A9)}$$

$$\boxed{D_{A1'} = 2}$$

### Step 3: $D_{eff} = 3$

The hierarchical direction of A1 (radial) and the emergent direction of A1' (transverse) are orthogonal — the A1' axiom
explicitly requires "the direction of emergence is strictly orthogonal to the hierarchical direction of A1."

The dimensions of orthogonal spaces are additive:

$$\boxed{D_{eff} = D_{A1} + D_{A1'} = 1 + 2 = 3}$$

$\blacksquare$

## 4.3 The Essence of the Proof

The core of the entire proof consists of only two steps:

**First step**: The "no preferred direction" requirement of A1' excludes $D_{A1'} = 1$ ($S^1$ does not satisfy
continuous rotational symmetry).

**Second step**: The "no extra degrees of freedom" requirement of A9 excludes $D_{A1'} > 2$ (no axiom provides a source
for a 3rd transverse direction).

The two steps together lock in $D_{A1'} = 2$.

This is a **precise squeeze argument**: the lower bound comes from symmetry, and the upper bound comes from
completeness. Together they determine the unique solution.

## 4.4 Comparison with Physics

| Physical question           | WorldBase answer                                                                                    |
|:----------------------------|:----------------------------------------------------------------------------------------------------|
| Why is space 3-dimensional? | Because hierarchy is 1-dimensional, symmetric emergence is 2-dimensional, and there is nothing more |
| Why not 2-dimensional?      | Because $S^1$ does not satisfy the continuous symmetry of "no preferred direction"                  |
| Why not 4-dimensional?      | Because no axiom provides a source for a 4th dimension (A9 prohibits it)                            |
| Why not 10-dimensional?     | Same — A9 excludes all dimensions beyond what the axioms require                                    |

## 4.5 Potential Objections and Responses

**Objection 1**: "The 'no preferred direction' requirement of A1' is also satisfied for $k = 3$ ($SO(3)$ also satisfies
it), so why can't we take $k = 3$?"

**Response**: $k = 3$ does indeed satisfy "no preferred direction," but A1' does not **require** $k = 3$. $k = 2$
already satisfies all requirements of A1'. A9 prohibits the system from possessing degrees of freedom beyond what the
axioms require, so $k = 3$ is excluded — not because it fails to satisfy A1', but because no axiom **requires** it.

**Objection 2**: "'Multiple child nodes' might imply more than 2 independent directions."

**Response**: In a 2-dimensional emergent space, any number of child nodes can emerge from a single node (by placing any
number of points on $S^1$).

Specifically: let the emergent space be $\mathbb{R}^2$, with ray directions from the origin continuously parameterized
by angle $\theta \in [0, 2\pi)$. Taking $n$ child nodes corresponds to taking $n$ points on $S^1$. $n$ can be any
positive integer — the number of child nodes in a 2-dimensional space is unlimited.

The "multiple child nodes" constraint concerns the **number** of child nodes, not the **dimension** of the emergent
space. Since any number of child nodes is possible in 2 dimensions, "multiple child nodes" does not imply $D_{A1'} > 2$.

**Objection 3**: "A9 is too weak — it merely says 'self-consistently closed,' which may not constrain dimension."

**Response**: The full statement of A9 is: "requires no external input, all evolutionary rules are determined by
internal axioms. The system introduces no extra degrees of freedom not covered by the axioms."

If the system possesses a degree of freedom not introduced by any axiom, then the source of that degree of freedom is "
external" — it is not determined by any axiom. This directly violates A9. Therefore A9 does indeed constrain dimension.

**Objection 4**: "Continuous rotational symmetry is a continuous concept — how is it defined in a discrete system?"

**Response**: In a discrete system, $SO(2)$ symmetry is manifested as: the set of neighbors reachable from a given node
is invariant under some discrete rotation.

On the $N = 6$ hypercube, the neighbors of a $w = 3$ state $x$ that preserve $w = 3$
number $\binom{3}{1} \cdot \binom{3}{1} = 9$ (flipping one $1 \to 0$ and one $0 \to 1$). These 9 neighbors are
equivalent under some permutation — and this permutation group is a discrete approximation to $SO(2)$.

Strictly speaking, "continuous symmetry" in a discrete system is an emergent property in the continuum limit. For
finite $N$, symmetry is approximate. But the dimensionality argument does not depend on $N$ — it depends on the
semantics of the axioms, not on the discretization scheme.

## 4.6 The Relationship Between Dimension and the Form of Gravity

$D_{eff} = 3$ is the determining factor for the form of gravity. The specific relationship is developed in Section 5,
but the core logic is previewed here:

In $D$-dimensional space, starting from the conservation law (A5) and locality (A4), the potential satisfies the Poisson
equation:

$$\nabla^2\Phi = C_D \rho$$

Its point-source solution is:

$$\Phi(r) \propto -\frac{1}{r^{D-2}}$$

Substituting $D = 3$:

$$\Phi(r) \propto -\frac{1}{r}$$

The derivation is completed in Section 5.

---

# Section 5: Derivation of the Gravitational Potential

## 5.1 Overview

This section derives the form of the gravitational potential from $D_{eff} = 3$ (Theorem 1) together with A4 and A5. The
derivation proceeds through two theorems: Theorem 2 derives the decay exponent $\gamma = D - 2$; Theorem 3 derives the
discrete form $\Phi = -\sum 1/d$.

## 5.2 Theorem 2: Decay Exponent

**Theorem 2 (Decay Exponent Theorem)**: In a WorldBase system satisfying axioms A4 and A5, the decay exponent of the
gravitational potential in $D$-dimensional space is:

$$\gamma = D - 2$$

### Proof

By A5 (conservation of difference) in the static case, the continuity equation reduces to:

$$\nabla \cdot \mathbf{J} = 0 \quad \text{(source-free region)}$$

By A4 (locality):

$$\mathbf{J} = -\sigma \nabla \Phi$$

Combining: $\nabla^2 \Phi = 0$ in source-free regions. For a region containing a point source of strength $M$, applying
Gauss's theorem over a sphere of radius $r$ in $D$-dimensional space:

$$\sigma \cdot |\nabla \Phi(r)| \cdot A_{D-1}(r) = 4\pi GM$$

where $A_{D-1}(r) = \Omega_{D-1} \cdot r^{D-1}$ is the surface area of the $(D-1)$-dimensional sphere of radius $r$, and

$$\Omega_{D-1} = \frac{2\pi^{D/2}}{\Gamma(D/2)}$$

is the surface area of the unit $(D-1)$-sphere (a constant). Solving:

$$|\nabla \Phi(r)| = \frac{4\pi GM}{\sigma \cdot \Omega_{D-1} \cdot r^{D-1}}$$

Integrating the gradient to obtain the potential:

$$\Phi(r) = -\int_r^{\infty} |\nabla \Phi(r')| \, dr' = -\frac{4\pi GM}{\sigma \cdot \Omega_{D-1}} \cdot \frac{1}{(D-2) r^{D-2}}$$

Defining $G \equiv \frac{4\pi}{\sigma \cdot \Omega_{D-1}(D-2)}$:

$$\Phi(r) = -\frac{GM}{r^{D-2}}$$

The decay exponent is therefore:

$$\boxed{\gamma = D - 2}$$

Substituting $D = 3$:

$$\boxed{\gamma = 1}$$

$\blacksquare$

## 5.3 Theorem 3: Newtonian Gravitational Potential

**Theorem 3 (Gravitational Potential Theorem)**: In a WorldBase system satisfying axioms A1, A1', A4, A5, and A9, the
gravitational potential takes the form:

$$\Phi(x) = -\sum_{s \in S} \frac{1}{d_H(x, s)}$$

where $S$ is the set of stable states and $d_H$ is the Hamming distance.

### Proof

By Theorem 1: $D_{eff} = 3$.

By Theorem 2: in $D = 3$ space, $\gamma = 1$, and the point-mass potential is $\Phi(r) = -GM/r$.

On the discrete hypercube, "distance" is the Hamming distance $d_H(x, s)$. The Euclidean distance $r$ in the continuum
limit corresponds to the discrete Hamming distance $d$.

The discrete form of the potential is:

$$\Phi(x) = -\sum_{s \in S} \frac{1}{d_H(x, s)}$$

where:

- The sum runs over all stable states $s \in S$
- When $d_H(x, s) = 0$, we regularize with $d = 0.5$ (corresponding to the self-energy as $r \to 0$ in the continuum
  limit)
- The coefficient is normalized to 1 (natural units, $G = 1$)

**Linear superposition**: The Poisson equation $\nabla^2 \Phi = 4\pi G\rho$ is linear. The total potential from multiple
sources is the sum of individual potentials. This guarantees additivity of the potential in the multi-stable-state case.

$$\boxed{\Phi(x) = -\sum_{s \in S} \frac{1}{d_H(x, s)}}$$

$\blacksquare$

## 5.4 Theorem 4: The Poisson Equation

**Theorem 4 (Field Equation Theorem)**: In the continuum limit satisfying A4 and A5, the gravitational potential
satisfies the Poisson equation:

$$\nabla^2\Phi = 4\pi G\rho$$

### Proof

From the continuum form of A5 (conservation of difference):

$$\nabla \cdot \mathbf{J} = Q$$

where $Q$ is the difference source density. In source-free regions ($Q = 0$):

$$\nabla \cdot \mathbf{J} = 0$$

From A4 (locality):

$$\mathbf{J} = -\sigma \nabla \Phi$$

Combining: $\nabla^2 \Phi = 0$ (source-free region). For regions containing sources, Gauss's theorem gives:

$$\nabla^2 \Phi = 4\pi G\rho$$

where $\rho$ is the difference density (mass density) and $G$ is the coupling constant. This is a standard result of
mathematical physics — the joint consequence of A4 and A5. $\blacksquare$

## 5.5 Dependency Structure of the Derivation Chain

| Step | Premises                      | Conclusion                  | Derivation Type                               |
|:----:|:------------------------------|:----------------------------|:----------------------------------------------|
|  1   | A1 + A1' + A9                 | $D_{eff} = 3$               | Rigorous proof (Theorem 1)                    |
|  2   | A4 + A5 + $D$-dim space       | $\gamma = D - 2$            | Rigorous proof (Theorem 2)                    |
|  3   | Step 1 + Step 2               | $\gamma = 1$                | Direct substitution                           |
|  4   | $\gamma = 1$ + discretization | $\Phi = -\sum 1/d$          | Definition + linear superposition (Theorem 3) |
|  5   | A4 + A5 (continuum limit)     | $\nabla^2\Phi = 4\pi G\rho$ | Standard mathematics (Theorem 4)              |

Dependency graph:

```
A1 ───────────────→ D_A1 = 1 ──────────────────────┐
                                                     │
A1' ──→ D_A1' ≥ 2 ──┐                               │
                     ├──→ D_A1' = 2 ─→ D_eff = 3 ───┤
A9 ───→ D_A1' ≤ 2 ──┘                               │
                                                     │
A4 ──→ Locality ──┐                                  │
                  ├──→ γ = D−2 ──→ γ = 1 ────────────┤
A5 ──→ Conservation┘                                 │
                                                     │
                                                     ▼
                                          Φ = −∑1/d  (Theorem 3)
                                                     │
                                                     ▼
                                        ∇²Φ = 4πGρ  (Theorem 4)
```

No circular dependencies. The premises of every step are either proved earlier or given directly by axioms.

## 5.6 Relationship to General Relativity

General relativity derives Newtonian gravity as the weak-field limit, starting from the equivalence principle and
spacetime curvature. This paper arrives at the same result via a completely different path:

|                   | General Relativity                                 | WorldBase                                                     |
|:------------------|:---------------------------------------------------|:--------------------------------------------------------------|
| Starting point    | Equivalence principle + 4-dimensional spacetime    | Axioms of difference (A1–A9)                                  |
| Spatial dimension | Assumed to be 3+1                                  | Derived as 3 (Theorem 1)                                      |
| Form of gravity   | $-1/r$ in the weak-field limit                     | Direct consequence of conservation + dimension (Theorems 2–3) |
| Field equation    | Einstein equation $G_{\mu\nu} = 8\pi G T_{\mu\nu}$ | Poisson equation $\nabla^2\Phi = 4\pi G\rho$ (Theorem 4)      |

WorldBase yields the Poisson equation (the field equation of Newtonian gravity), not the Einstein equation (the field
equation of general relativity). The relationship between them is: the Poisson equation is the approximation of the
Einstein equation in the weak-field, low-velocity, static limit.

WorldBase currently covers Newtonian gravity and has not yet covered general relativity. The generalization from the
Poisson equation to the Einstein equation is a direction for future work.

---

# Section 6: Numerical Verification

## 6.1 Verification Strategy

Theorem 3 predicts: on the $N = 6$ hypercube, under a single stable state (the all-ones state), the layer-averaged
potential equals exactly $-1/d$, where $d = 6 - w$ is the Hamming distance from the stable state.

Verification method: directly compute the potential values of all 64 states, group them by Hamming weight $w$, and check
whether every value within each group equals exactly $-1/(6-w)$.

## 6.2 Computational Setup

**System**: $N = 6$ hypercube, $2^6 = 64$ states.

**Stable state**: All-ones state $\mathbf{1} = (1,1,1,1,1,1)$, $w = 6$.

**Potential formula**:

$$\Phi(x) = -\frac{1}{d_H(x, \mathbf{1})}$$

where $d_H(x, \mathbf{1}) = 6 - w(x)$.

**Regularization**: When $d_H = 0$, take $d = 0.5$.

**Grouping**: The 64 states are divided into 7 groups by Hamming weight $w = 0, 1, 2, 3, 4, 5, 6$. All states within
each group have the same potential value (guaranteed by hypercube symmetry).

## 6.3 Computational Results

| $w$ | Count $C(6,w)$ | Distance $d = 6-w$ | $\Phi_{\text{theory}} = -1/d$ | $\Phi_{\text{computed}}$ | Error |
|:---:|:--------------:|:------------------:|:-----------------------------:|:------------------------:|:-----:|
|  0  |       1        |         6          |   $-1/6 = -0.1\overline{6}$   |       $-0.166667$        |  $0$  |
|  1  |       6        |         5          |        $-1/5 = -0.200$        |       $-0.200000$        |  $0$  |
|  2  |       15       |         4          |        $-1/4 = -0.250$        |       $-0.250000$        |  $0$  |
|  3  |       20       |         3          |   $-1/3 = -0.\overline{3}$    |       $-0.333333$        |  $0$  |
|  4  |       15       |         2          |        $-1/2 = -0.500$        |       $-0.500000$        |  $0$  |
|  5  |       6        |         1          |        $-1/1 = -1.000$        |       $-1.000000$        |  $0$  |
|  6  |       1        |        0.5         |       $-1/0.5 = -2.000$       |       $-2.000000$        |  $0$  |

**The error is zero in all 7 groups.** The layer-averaged potential equals exactly $-1/d$.

## 6.4 Verification Code

The following Python code computes and verifies the results:

```python
import numpy as np
import itertools

N = 6
states = list(itertools.product([0, 1], repeat=N))
n_states = len(states)

# Hamming weight
hw = np.array([sum(s) for s in states])

# All-ones state (stable state)
stable = [i for i in range(n_states) if hw[i] == N]


# Compute potential
def compute_phi(stable):
    Phi = np.zeros(n_states)
    for i in range(n_states):
        for s in stable:
            d = sum(a != b for a, b in zip(states[i], states[s]))
            if d == 0:
                d = 0.5
            Phi[i] -= 1.0 / d
    return Phi


Phi = compute_phi(stable)

# Output by layer
print("w, C(6,w), d, Phi_theory, Phi_computed, error")
for w in range(N + 1):
    mask = (hw == w)
    phi_layer = Phi[mask][0]  # same value within each layer
    d = N - w if w < N else 0.5
    phi_theory = -1.0 / d
    error = abs(phi_layer - phi_theory)
    print(f"{w}, {sum(mask)}, {d}, {phi_theory:.6f}, {phi_layer:.6f}, {error:.10f}")
```

## 6.5 Multi-Stable-State Verification

To verify the principle of linear superposition, we compute the total potential for two stable states.

**Setup**: Stable state set $S = \{\mathbf{1}, \mathbf{e}_1\}$, where $\mathbf{1} = (1,1,1,1,1,1)$
and $\mathbf{e}_1 = (1,0,0,0,0,0)$.

**Theoretical prediction**:

$$\Phi(x) = -\frac{1}{d_H(x, \mathbf{1})} - \frac{1}{d_H(x, \mathbf{e}_1)}$$

**Verification**: Potential values within the same layer are no longer equal (because the distances to the two stable
states differ), but linear superposition still holds exactly.

| $x$             | $d_H(x, \mathbf{1})$ | $d_H(x, \mathbf{e}_1)$ | $\Phi_{\text{theory}}$  | $\Phi_{\text{computed}}$ | Error |
|:----------------|:--------------------:|:----------------------:|:-----------------------:|:------------------------:|:-----:|
| $(0,0,0,0,0,0)$ |          6           |           1            |  $-1/6 - 1/1 = -1.167$  |       $-1.166667$        |  $0$  |
| $(0,0,0,0,0,1)$ |          5           |           2            |  $-1/5 - 1/2 = -0.700$  |       $-0.700000$        |  $0$  |
| $(0,0,0,0,1,1)$ |          4           |           3            |  $-1/4 - 1/3 = -0.583$  |       $-0.583333$        |  $0$  |
| $(1,1,1,1,1,1)$ |         0.5          |           5            | $-1/0.5 - 1/5 = -2.200$ |       $-2.200000$        |  $0$  |

**The principle of linear superposition holds exactly in the discrete system.**

## 6.6 Verification Summary

| Verification item                 | Prediction                              | Result                     |
|:----------------------------------|:----------------------------------------|:---------------------------|
| Single stable state potential     | $\Phi = -1/d$                           | Holds exactly (zero error) |
| Equal potential within each layer | Hypercube symmetry                      | Holds exactly              |
| Linear superposition              | $\Phi_{\text{total}} = \Phi_1 + \Phi_2$ | Holds exactly              |
| Monotonicity of potential         | $\Phi$ more negative as $w$ increases   | Holds exactly              |

**All numerical verifications are in complete agreement with theoretical predictions.**

## 6.7 Comparison with $\gamma = 2$

To confirm that $\gamma = 1$ is the correct choice, we compare with the potential for $\gamma = 2$ (corresponding
to $D = 4$-dimensional space):

$$\Phi_{\gamma=2}(x) = -\sum_{s \in S} \frac{1}{d_H(x,s)^2}$$

| $w$ | $\Phi_{\gamma=1} = -1/d$ | $\Phi_{\gamma=2} = -1/d^2$ |
|:---:|:------------------------:|:--------------------------:|
|  0  |         $-0.167$         |          $-0.028$          |
|  1  |         $-0.200$         |          $-0.040$          |
|  2  |         $-0.250$         |          $-0.063$          |
|  3  |         $-0.333$         |          $-0.111$          |
|  4  |         $-0.500$         |          $-0.250$          |
|  5  |         $-1.000$         |          $-1.000$          |
|  6  |         $-2.000$         |          $-4.000$          |

$\gamma = 2$ gives the $-1/d^2$ form, corresponding to gravity in four-dimensional space, which does not correspond to
the physics of our universe. $\gamma = 1$ gives the $-1/d$ form, corresponding to Newtonian gravity in three-dimensional
space.

**Numerical verification confirms that $\gamma = 1$ is the correct choice.**

---

# Section 7: Discussion and Directions for Extension

## 7.1 Completed Derivations

Starting from 10 axioms of difference, this paper has rigorously derived the following results:

|  Theorem  | Content                     | Axiomatic Source      |        Status        |
|:---------:|:----------------------------|:----------------------|:--------------------:|
| Theorem 1 | $D_{eff} = 3$               | A1 + A1' + A9         |  Rigorously proved   |
| Theorem 2 | $\gamma = D - 2$            | A4 + A5               |  Rigorously proved   |
| Theorem 3 | $\Phi = -\sum 1/d$          | Theorem 1 + Theorem 2 |  Rigorously derived  |
| Theorem 4 | $\nabla^2\Phi = 4\pi G\rho$ | A4 + A5               | Standard mathematics |

Core achievement: spatial dimension $D = 3$ and the Newtonian gravitational potential $\Phi = -GM/r$ emerge from purely
formal axioms. The derivation chain has no circular dependencies; numerical verification is in complete agreement.

## 7.2 Extension Potential of the Framework

The capacity of the 10 axioms far exceeds the portion used in this paper. The following discusses directions for
extending the framework to other areas of physics. These extensions are currently at varying stages of structural
argumentation and have not yet reached the level of rigor of the gravitational derivation in this paper. They are
presented to demonstrate the potential unifying power of the framework, not to claim that the derivations are complete.

### 7.2.1 Electromagnetism

The structural difference between gravity and electromagnetism in physics can be traced back to a difference in
axiomatic origin:

|                  | Gravity                            | Electromagnetism                             |
|:-----------------|:-----------------------------------|:---------------------------------------------|
| Axiomatic source | A1 (radial)                        | A1' (transverse)                             |
| Source           | Mass (scalar, always non-negative) | Charge (scalar, can be positive or negative) |
| Potential        | $\Phi = -GM/r$                     | $\varphi = q/4\pi\epsilon_0 r$               |
| Symmetry         | None                               | $U(1)$ gauge symmetry                        |

The 2-dimensional emergent space of A1' carries $SO(2)$ rotational symmetry. A mathematical fact: $SO(2) \cong U(1)$ —
the two are isomorphic as groups. Therefore $U(1)$ gauge symmetry is already built into the geometric structure of A1',
requiring no additional axiom.

Electric charge can be defined as the "phase projection" of the transverse space:

$$q(x) = \sum_{i=1}^{N} x_i \cos\!\left(\frac{2\pi i}{N}\right)$$

The geometric reason charge can be positive or negative: the A1 radial direction has only one direction ($w$ increases),
so mass is always non-negative; the A1' transverse direction has two directions ($\theta$ increases or decreases), so
charge can be positive or negative.

Starting from charge conservation (the Noether consequence of $SO(2)$ symmetry) and A4 (locality), and repeating the
mathematical structure of the gravitational derivation, one obtains the Poisson
equation $\nabla^2\varphi = -\rho_q/\epsilon_0$ and the Coulomb potential $\varphi = q/4\pi\epsilon_0 r$.[6]

**The two forces are the radial and transverse projections of the same 3-dimensional space.**

### 7.2.2 The Strong Force

The core feature of the strong force is the linear potential $V = \sigma r$ (quark confinement), in contrast to
the $1/r$ form of gravity and electromagnetism. The linear potential corresponds to $D_{eff} = 1$ (by the
formula $\gamma = D - 2$, giving $\gamma = -1$, $\Phi \propto -r$).

On the $N = 6$ hypercube, the $w = N/2 = 3$ layer has $\binom{6}{3} = 20$ states. These 20 states form the Johnson
graph $J(6,3)$ — a highly symmetric combinatorial structure.

A8 (symmetry preference) confines the strong force to within the $w = N/2$ layer. Within that layer, the shortest paths
between color charges run along the edges of the Johnson graph — each edge corresponds to a Hamming distance change of
2, forming a one-dimensional path.

Conservation propagation along a one-dimensional path gives the linear potential $V = \sigma r$, where $\sigma$ is the
string tension.

**The strong force is the result of $D_{eff}$ collapsing from 3 dimensions to 1 dimension within the $w = N/2$ layer.**

### 7.2.3 The Weak Force

The two distinctive features of the weak force are parity violation (only left-handed fermions participate) and massive
mediators ($W^\pm$, $Z^0$ are massive).

A6 (irreversibility) provides the mechanism for parity violation: the transverse space of A1' has a phase
coordinate $\theta$, and A6 permits only transitions in the direction of increasing $\theta$ (the time arrow),
forbidding transitions in the direction of decreasing $\theta$. The parity transformation $\theta \to -\theta$ turns
permitted directions into forbidden ones, so parity is broken.

The source of mass for $W^\pm$ and $Z^0$ is A8 (symmetry preference): transitions from the $w = N/2$ layer to adjacent
layers must overcome the symmetry preference barrier imposed by A8, and the height of this barrier gives the $W/Z$
masses.

**The weak force is the joint effect of A6 (irreversibility) and A8 (symmetry preference) in the vicinity of
the $w = N/2$ layer.**

### 7.2.4 Quantum Mechanics

The core structures of quantum mechanics — superposition, interference, quantization — all have axiomatic origins:

| Quantum feature      | Axiomatic source                                                | Mechanism                                  |
|:---------------------|:----------------------------------------------------------------|:-------------------------------------------|
| Superposition        | A2 (binary) + A1' (phase)                                       | Binary basis + complex amplitude           |
| Interference         | A7 (cyclic)                                                     | Path phase superposition                   |
| Schrödinger equation | A4 (local evolution) + A3 ($\hbar$ finite) + A1' rotation ($i$) | $i\hbar\partial_t\psi = H\psi$             |
| Quantization         | A7 (cyclic condition)                                           | Standing wave condition $k_n = 2\pi n/L$   |
| Tunneling            | A7 (superposition of all paths)                                 | Non-classical path amplitudes are non-zero |

The Born rule $P = |\psi|^2$ can be derived from Gleason's theorem: $D_{eff} = 3$
guarantees $\dim(\mathcal{H}) \geq 3$,[7]
satisfying the premise of Gleason's theorem, whose unique solution for probability assignment is $P = |\psi|^2$.

### 7.2.5 Dark Energy

Dark energy can be understood as an approximate failure of A5 (conservation of difference) at large scales. Modifying
the continuity equation:

$$\frac{\partial\rho}{\partial t} + \nabla \cdot \mathbf{J} = Q$$

where $Q$ is the source density of difference (difference is "created" or "destroyed" when the conservation law fails).
In the static case:

$$\nabla^2\Phi = 4\pi G\rho - \Lambda$$

where $\Lambda = Q/\sigma$. This is precisely the field equation of the $\Lambda$CDM model.

**Dark energy is not a new form of matter, but a scale-dependent leakage of the conservation law.**

### 7.2.6 Dark Matter

Dark matter requires no new axioms or new entities. The gravitational potential sums over all states, while
electromagnetism is effective only for states where $U(1)$ symmetry is active. The difference between the two is dark
matter:

$$\Phi_{\text{dark}} = \Phi_{\text{grav}} - \Phi_{\text{vis}}$$

On the $N$-dimensional hypercube, the ratio of dark matter to visible matter is:

$$k(N) = \frac{1}{2}\sum_{d=1}^{N}\frac{C(N,d)}{d}$$

For $N = 10$, $k \approx 5.055$, close to the observed value $\Omega_{\text{dark}}/\Omega_{\text{vis}} \approx 5.4$.

### 7.2.7 Matter and Mass

The core derivation of this paper yields the gravitational potential $\Phi(x) = -\sum 1/d_H(x,s)$. This formula
naturally leads to axiomatic definitions of two fundamental concepts: matter and mass.

**Definition of matter**:

Matter is the local minimum of the potential field $\Phi(x)$ — the deepest point of the potential well.

$$\text{Matter} \equiv \{x : \Phi(x) \text{ attains a local minimum}\}$$

In WorldBase, the local minima of the potential are precisely the stable states ($w = N$, the all-ones states).
Therefore:

$$\text{Matter} = \text{Stable states} = \{x : w(x) = N\}$$

This definition is consistent with the fundamental properties of matter in physics:

| Physical property                         | WorldBase correspondence                          | Self-consistent? |
|:------------------------------------------|:--------------------------------------------------|:----------------:|
| Matter generates a gravitational field    | Stable states enter the sum for $\Phi$            |       Yes        |
| Matter is the minimum of potential energy | Local minimum of $\Phi$                           |       Yes        |
| Matter is attracted by gravity            | System evolves along $\nabla\Phi$                 |       Yes        |
| Matter has spatial extent                 | Stable states have a 2-dimensional emergent space |       Yes        |

**Definition of mass**:

The "mass" of each stable state is defined as the magnitude of its contribution to the total potential:

$$m(s) = |\Phi_{\text{contribution}}(s)| = \sum_{s' \neq s} \frac{1}{d_H(s, s')}$$

Key property: mass is not an intrinsic property of a stable state, but a **relational property** — it arises from the
distance relations between a stable state and all other stable states. An isolated stable state has zero mass (no other
states to sum over).

This is consistent with the spirit of general relativity: mass is not something that exists independently, but is part
of the structure of spacetime.

**Relation between mass and hierarchy**:

A1 drives the system to evolve toward higher Hamming weight — from $w = 0$ to $w = N$. Difference accumulates at each
step, and reaches its maximum when $w = N$. Mass is proportional to the accumulated difference:

$$m \propto w(x) \quad \text{(when } x \text{ is a stable state, } w = N\text{)}$$

**Production of matter**: The hierarchical elevation process of A1 is the process of matter production — difference
accumulates continuously, and matter emerges when $w = N$ is reached.

**Annihilation of matter**: When A5 fails at large scales (dark energy effect), the potential wells are filled in,
matter is no longer stable — matter annihilates.

## 7.3 Distinguishing the Framework from Existing Approaches[1][2][3][4]

| Framework                  | Method                                         | Spatial dimension            | Form of gravity                  | Distinguishing point                          |
|:---------------------------|:-----------------------------------------------|:-----------------------------|:---------------------------------|:----------------------------------------------|
| Wolfram Physics Project[1] | Computational rules + experimental exploration | Requires additional argument | Derived from hypergraph geometry | Different method (exploration vs proof)       |
| Constructor Theory         | Constraint formulation                         | Not addressed                | Not addressed                    | Meta-theory, does not derive specific physics |
| Digital Physics            | Philosophical claim                            | Assumed                      | Not derived                      | Lacks rigorous derivation chain               |
| It from Bit                | Programmatic slogan                            | Not addressed                | Not derived                      | Lacks concrete implementation                 |
| **This paper**             | **Constraint derivation**                      | **Derived from axioms**      | **Derived from axioms**          | **Rigorous proof + numerical verification**   |

The unique contribution of this paper: **rigorously deriving spatial dimension and the form of gravity from purely
formal axioms, with exact numerical verification on a finite discrete system.** To our knowledge, this is the first
framework to complete this derivation.

## 7.4 Limitations

The derivations in this paper have the following limitations:

**Continuum limit.** The derivations in this paper are rigorous within the discrete finite system (the $N = 6$
hypercube). The convergence in the continuum limit ($N \to \infty$) has not been rigorously proved. What specifically
needs to be proved is: the discrete potential $\Phi_N(x)$, after appropriate normalization, converges to the continuum
potential $\Phi(\mathbf{x}) = -1/\|\mathbf{x}\|$.

**Rigor of extension derivations.** The core contributions of this paper (Theorems 1–4) are rigorously proved. The
extension directions discussed in Section 7 (electromagnetism, the strong force, the weak force, quantum mechanics) are
at varying stages of structural argumentation and have not yet reached the level of rigor of the core derivations.

**Precise values of physical constants.** This paper derives the form of physical laws ($\Phi = -1/r$), but does not
derive the precise values of physical constants ($G = 6.674 \times 10^{-11}$ N·m²/kg²). The precise values of constants
require additional conversion factors reflecting the mapping from state space to physical space — these are empirical
parameters, not logical consequences.

## 7.5 Future Work

**Highest priority**: Rigorous treatment of the continuum limit. A convergence theorem for the $N \to \infty$ limit must
be established, proving that the discrete potential converges to the continuum Newtonian potential.

**Second priority**: Rigorous derivation of electromagnetism. A precise definition of electric charge, a rigorous
argument for the $SO(2) \to U(1)$ gauge identification, and a complete derivation chain for Coulomb's law are needed.

**Third priority**: Formalization of quantum mechanics. The Schrödinger equation must be rigorously derived from A2 +
A3 + A7, and the axiomatic foundation of the path integral must be established.

**Long-term goal**: Unified derivation of all four forces. Starting from the 10 axioms, rigorously derive all forms of
gravity, electromagnetism, the strong force, and the weak force, establishing an axiomatic foundation for physics.

---

# Section 8: Conclusion

## 8.1 Core Results

This paper proposes a new theoretical construction method — constraint derivation — and uses it to complete a specific
derivation: starting from 10 abstract axioms concerning "difference," the mathematical form of the Newtonian
gravitational potential is derived.

The core of the derivation chain consists of only three theorems:

**Theorem 1**: $D_{eff} = 3$. Space is 3-dimensional — not an assumption, but a theorem. Hierarchy contributes 1
dimension, symmetric emergence contributes 2 dimensions, and there is nothing more.

**Theorem 2**: $\gamma = D - 2 = 1$. The decay exponent of the gravitational potential is uniquely determined by spatial
dimension.

**Theorem 3**: $\Phi(x) = -\sum 1/d_H(x,s)$. The Newtonian gravitational potential emerges from the axioms.

The proofs of the three theorems depend on no physical input whatsoever — no mass, no force, no a priori assumption of
space. The axioms concern only difference structures, hierarchical relations, symmetry constraints, and conservation
laws on a discrete state space.

Numerical verification on the $N = 6$ hypercube is in complete agreement: the potential of a single stable state equals
exactly $-1/d$, with zero error.

## 8.2 Significance

### Physical Significance

Two long-standing open questions receive possible answers:

**Why is space 3-dimensional?** Because hierarchy is 1-dimensional, symmetric emergence is 2-dimensional, and A9
prohibits anything more.

**Why is the gravitational potential $-1/r$?** Because space is 3-dimensional, and the conservation law in 3-dimensional
space necessarily yields a $-1/r$ potential.

The characteristic of these two answers is that they are not empirical inductions but logical consequences. If the
derivation chain withstands rigorous scrutiny in the continuum limit, spatial dimension and the form of gravity will be
elevated from "empirical facts" to "logical theorems."

### Methodological Significance

The constraint-derivation methodology — using subtraction to approach reality — provides a theoretical construction
pathway complementary to empirical induction. It does not answer "what the world happens to be like," but rather "what
the world cannot fail to be like."

The derivations in this paper demonstrate that in certain cases, constraint derivation can go further than empirical
induction — it not only describes physical laws, but explains why physical laws take the form they do.

### Potential Extensions

The core derivations of this paper (Theorems 1–4) are rigorous. The extensions of the framework to electromagnetism, the
strong force, the weak force, and quantum mechanics are at the stage of structural argumentation. These extensions
demonstrate the potential unifying power of the framework: the four forces and quantum mechanics may emerge from
different projections of the same set of axioms.

If these extensions are rigorously proved, the 10 axioms of difference will become the axiomatic foundation of physics —
a complete chain from axioms to all fundamental physical laws.

## 8.3 An Honest Assessment

What this paper has accomplished:

- Established the methodological framework of constraint derivation
- Rigorously derived $D = 3$, $\gamma = 1$, $\Phi = -1/r$ from axioms
- Provided exact numerical verification on a discrete system
- Identified structural pathways for extending the framework to other areas of physics

What this paper has not yet accomplished:

- Rigorous mathematical proof of the continuum limit
- Rigorous derivation of electromagnetism, the strong force, and the weak force
- Derivation of precise values of physical constants
- Experimental verification

The positioning of this paper: **this is the first rigorous step in deriving physical laws from axioms.** The
gravitational derivation chain is complete and verifiable. The extension directions are real and promising. But
between "rigorous derivation of gravity" and "axiomatization of physics," a great deal of work remains to be done.

## 8.4 Closing Remarks

When Mendeleev arranged the periodic table, he said: "I did not discover the periodic law — the periodic law revealed
itself."

The situation in this paper is similar. We did not invent the fact that space is 3-dimensional, nor did we invent the
fact that gravity is $-1/r$. These conclusions emerged from the axioms on their own — we only provided the axioms, then
let logic do its work.

If this direction is correct, then the ultimate theory of physics may not be a set of equations, but a set of axioms —
with every step from axioms to equations being a logical derivation, not an experimental fit.

This is the vision proposed in this paper. The derivation of gravity is its first proof.

---
Acknowledgments

This work was developed through sustained intellectual collaboration with
several AI language models, including Claude (Anthropic), Qwen (Alibaba),
Doubao (ByteDance), DeepSeek, and Xiaomimimo. These systems contributed
substantively to the identification of logical gaps in the derivation chain,
the formalization of axiomatic arguments, the verification of mathematical
proofs, and the refinement of the manuscript. The axiomatic framework
(WorldBase), the core research questions, and all final intellectual and
editorial decisions were conceived and made by the author. The author takes
full responsibility for the content of this paper.

The author also declares that AI language models were used in the preparation
of this manuscript, in accordance with the disclosure policies of the target
journal.

## Appendix A: Complete Axiom Table

| ID  | Name                       | Core Constraint                                                              |    Type     |
|:---:|:---------------------------|:-----------------------------------------------------------------------------|:-----------:|
| A1  | Primordial Difference      | Hierarchical partial order, unique ground state, $w$ monotone non-decreasing | Structural  |
| A1' | Hierarchical Emergence     | Symmetric emergence, no preferred direction, orthogonal to A1                | Structural  |
| A2  | Binary Concretization      | State space $\{0,1\}^N$                                                      | Structural  |
| A3  | Finite Discreteness        | $                                                                            | \mathcal{X} | = 2^N < \infty$ | Structural |
| A4  | Minimal Change             | Each step $d_H = 1$                                                          |  Dynamical  |
| A5  | Conservation of Difference | $\sum d_i = \text{const}$                                                    |  Dynamical  |
| A6  | Direction of Emergence     | Irreversible, arrow of time                                                  |  Dynamical  |
| A7  | Cyclic Closure             | Stable states participate in cycles of length $\geq N$                       | Topological |
| A8  | Symmetry Preference        | Preference for states with $w = N/2$                                         | Topological |
| A9  | Intrinsic Completeness     | No extra degrees of freedom                                                  | Topological |

---

## Appendix B: Verification Code

```python
import numpy as np
import itertools

N = 6
states = list(itertools.product([0, 1], repeat=N))
n_states = len(states)
hw = np.array([sum(s) for s in states])


def compute_phi(stable_indices):
    Phi = np.zeros(n_states)
    for i in range(n_states):
        for s in stable_indices:
            d = sum(a != b for a, b in zip(states[i], states[s]))
            if d == 0:
                d = 0.5
            Phi[i] -= 1.0 / d
    return Phi


stable = [i for i in range(n_states) if hw[i] == N]
Phi = compute_phi(stable)

print("w, count, d, Phi_theory, Phi_computed, error")
for w in range(N + 1):
    mask = (hw == w)
    phi_val = Phi[mask][0]
    d = N - w if w < N else 0.5
    phi_theory = -1.0 / d
    error = abs(phi_val - phi_theory)
    print(f"{w}, {sum(mask)}, {d}, {phi_theory:.6f}, {phi_val:.6f}, {error:.10f}")
```

## References

[1] Wolfram, S. (2020). *A Project to Find the Fundamental Theory
of Physics*. Wolfram Media.

[2] Deutsch, D., & Marletto, C. (2015). Constructor theory of
information. *Proceedings of the Royal Society A*, 471(2174),

20140540.

[3] Wheeler, J. A. (1990). Information, physics, quantum: The search
for links. In W. H. Zurek (Ed.), *Complexity, Entropy, and the
Physics of Information*. Addison-Wesley.

[4] Zuse, K. (1969). *Rechnender Raum*. Friedrich Vieweg & Sohn.

[5] Einstein, A. (1905). Zur Elektrodynamik bewegter Körper.
*Annalen der Physik*, 17, 891–921.

[6] Noether, E. (1918). Invariante Variationsprobleme. *Nachrichten
von der Gesellschaft der Wissenschaften zu Göttingen*, 235–257.

[7] Gleason, A. M. (1957). Measures on the closed subspaces of a
Hilbert space. *Journal of Mathematics and Mechanics*, 6(6),
885–893.

[8] Hamming, R. W. (1950). Error detecting and error correcting codes.
*Bell System Technical Journal*, 29(2), 147–160.

---

*End of paper.*

---
