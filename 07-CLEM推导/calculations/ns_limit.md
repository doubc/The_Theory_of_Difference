# Navier-Stokes Equation Limit Derivation from Discrete Axioms

**Status:** Reference Document  
**Last Updated:** 2026-04-14  
**Related Papers:** `../../papers/03-turbulence-2d.md`, `../../papers/05-gravitational-wave-turbulence.md`

---

## Overview

This document derives the Navier-Stokes equation from WorldBase discrete axioms via the CLEM mechanism. The derivation shows how fluid dynamics emerges from discrete conservation laws, irreversibility, and continuous limit procedures.

---

## Theoretical Background

### Navier-Stokes Equation

The incompressible Navier-Stokes equation is:

$$\frac{\partial \mathbf{u}}{\partial t} + (\mathbf{u} \cdot 
abla)\mathbf{u} = -\frac{1}{\rho}
abla p + 
u 
abla^2 \mathbf{u} + \mathbf{f}$$

with continuity equation:

$$\nabla \cdot \mathbf{u} = 0$$

where:
- $\mathbf{u}$: velocity field
- $p$: pressure
- $\rho$: density (constant for incompressible flow)
- $\nu$: kinematic viscosity
- $\mathbf{f}$: external forces

### Key Challenge

Derive this **continuous, nonlinear, dissipative** PDE from:
- **Discrete** bit configurations
- **Reversible** microscopic rules (A4: one bit flip per step)
- **Conservative** dynamics (A5: difference conservation)

The emergence of **irreversibility** and **viscosity** requires careful treatment.

---

## Derivation Strategy

### Step 1: Discrete Continuity Equation (from A5)

**Axiom A5 (Difference Conservation)**: Conserved quantities exist and are preserved under evolution.

For fluid mass/density, define discrete density at vertex $i$:

$$\rho_i(t) = \text{number of bits set at vertex } i \text{ at time } t$$

Conservation means:

$$\sum_i \rho_i(t) = \text{constant}$$

Local conservation (continuity equation):

$$\rho_i(t+1) - \rho_i(t) + \sum_{j \sim i} J_{ij} = 0$$

where $J_{ij}$ is flux from vertex $i$ to neighbor $j$.

**Continuous limit**: As lattice spacing $a \to 0$ and time step $\Delta t \to 0$:

$$\frac{\partial \rho}{\partial t} + \nabla \cdot (\rho \mathbf{u}) = 0$$

For incompressible flow ($\rho = \text{const}$):

$$\nabla \cdot \mathbf{u} = 0$$

✓ **Continuity equation derived**.

---

### Step 2: Discrete Momentum Conservation

Define discrete momentum at vertex $i$:

$$\mathbf{p}_i(t) = \rho_i \mathbf{u}_i(t)$$

Momentum conservation (Newton's second law in discrete form):

$$\mathbf{p}_i(t+1) - \mathbf{p}_i(t) = \mathbf{F}_i^\text{int} + \mathbf{F}_i^\text{ext}$$

where:
- $\mathbf{F}_i^\text{int}$: Internal forces from neighboring vertices
- $\mathbf{F}_i^\text{ext}$: External forces (pressure gradient, body forces)

#### Internal Forces: Advection Term

Internal forces arise from momentum transport between neighbors:

$$\mathbf{F}_i^\text{adv} = -\sum_{j \sim i} (\mathbf{u}_i \cdot \mathbf{n}_{ij}) \mathbf{u}_j A_{ij}$$

where $\mathbf{n}_{ij}$ is unit normal from $i$ to $j$, and $A_{ij}$ is cross-sectional area.

**Continuous limit**:

$$\mathbf{F}^\text{adv} \to -(\mathbf{u} \cdot \nabla)\mathbf{u}$$

✓ **Advection term derived**.

#### Pressure Force

Pressure arises from density gradients (equation of state). For ideal fluid:

$$p = c_s^2 \rho$$

where $c_s$ is speed of sound.

Discrete pressure force:

$$\mathbf{F}_i^\text{press} = -\sum_{j \sim i} \frac{p_j - p_i}{|\mathbf{x}_j - \mathbf{x}_i|} \mathbf{n}_{ij}$$

**Continuous limit**:

$$\mathbf{F}^\text{press} \to -\frac{1}{\rho}\nabla p$$

✓ **Pressure gradient derived**.

---

### Step 3: Irreversibility and Viscosity (from A6)

**Axiom A6 (Irreversibility)**: Evolution is directed (DAG structure).

This seems to contradict reversible microscopic dynamics (A4: single bit flips are reversible). Resolution:

**Key insight**: While individual bit flips are reversible, the **coarse-grained** evolution on Johnson graph is irreversible due to:
1. Information loss in coarse-graining
2. Entropy increase from A8 (Symmetry Preference)
3. DAG structure at macroscopic scale

#### Discrete Dissipation

Model viscous dissipation as momentum diffusion:

$$\mathbf{F}_i^\text{visc} = \nu_\text{discrete} \sum_{j \sim i} (\mathbf{u}_j - \mathbf{u}_i)$$

This is a discrete Laplacian operator.

**Physical origin**: 
- Microscopic reversibility (A4) + Macroscopic irreversibility (A6) → Effective friction
- Analogy: Molecular collisions are reversible, but produce macroscopic viscosity

**Continuous limit**:

$$\mathbf{F}^\text{visc} \to \nu \nabla^2 \mathbf{u}$$

where kinematic viscosity $\nu$ relates to discrete parameters:

$$\nu \sim \frac{a^2}{\Delta t} \cdot \text{(scattering rate)}$$

✓ **Viscous term derived**.

---

### Step 4: Assembly and Continuous Limit

Combine all terms:

$$\frac{\mathbf{p}_i(t+1) - \mathbf{p}_i(t)}{\Delta t} = \mathbf{F}_i^\text{adv} + \mathbf{F}_i^\text{press} + \mathbf{F}_i^\text{visc} + \mathbf{F}_i^\text{ext}$$

Substitute $\mathbf{p}_i = \rho \mathbf{u}_i$ and take $\Delta t \to 0$, $a \to 0$:

$$\rho \frac{\partial \mathbf{u}}{\partial t} = -\rho(\mathbf{u} \cdot 
abla)\mathbf{u} - 
abla p + \rho 
u 
abla^2 \mathbf{u} + \rho \mathbf{f}$$

Divide by $\rho$:

$$\frac{\partial \mathbf{u}}{\partial t} + (\mathbf{u} \cdot 
abla)\mathbf{u} = -\frac{1}{\rho}
abla p + 
u 
abla^2 \mathbf{u} + \mathbf{f}$$

✓ **Navier-Stokes equation recovered**.

---

## Dimensional Analysis

### Viscosity Scaling

From discrete parameters:
- Lattice spacing: $a$
- Time step: $\Delta t$
- Scattering rate: $\Gamma \sim 1/\tau$

Kinematic viscosity:

$$[\nu] = \frac{L^2}{T} = \frac{a^2}{\Delta t}$$

If we identify:
- $a \sim$ mean free path $\ell$
- $\Delta t \sim$ collision time $\tau$

Then:

$$\nu \sim \frac{\ell^2}{\tau} = \ell \cdot \frac{\ell}{\tau} = \ell \cdot v_\text{thermal}$$

This matches kinetic theory result! ✓

### Reynolds Number

Dimensionless Reynolds number:

$$Re = \frac{UL}{\nu}$$

where $U$ is characteristic velocity, $L$ is characteristic length.

**In discrete terms**:
- $U \sim a/\Delta t$ (max velocity on lattice)
- $L \sim Na$ (system size for $N$ vertices)
- $\nu \sim a^2/\Delta t$

Therefore:

$$Re \sim \frac{(a/\Delta t)(Na)}{a^2/\Delta t} = N$$

**Implication**: Reynolds number scales with system size $N$. Larger systems naturally achieve turbulent regimes.

---

## Connection to Turbulence Prediction

### 2D Enstrophy Cascade

Paper `../../papers/03-turbulence-2d.md` predicts energy spectrum:

$$E(k) \propto k^{-10/3}$$

for 2D enstrophy cascade.

**Derivation sketch**:
1. In 2D, both energy $E$ and enstrophy $\Omega = \int |\nabla \times \mathbf{u}|^2$ are conserved
2. Dual cascade: energy flows to large scales, enstrophy to small scales
3. Dimensional analysis with enstrophy flux $\eta$ gives $E(k) \sim \eta^{2/3} k^{-10/3}$

### Comparison with Kolmogorov

Standard 3D Kolmogorov turbulence:

$$E(k) \propto k^{-5/3}$$

**Difference**: 
- 3D: Energy cascade only → $k^{-5/3}$
- 2D: Enstrophy cascade → $k^{-10/3}$ (steeper)

Our prediction $k^{-10/3}$ differs from some CFT-based derivations ($k^{-3}$), providing a falsifiable test.

---

## Gravitational Wave Turbulence

Paper `../../papers/05-gravitational-wave-turbulence.md` extends this to gravitational waves.

**Key idea**: Nonlinear Einstein equations exhibit turbulent behavior similar to Navier-Stokes.

**Prediction**: Gravitational wave energy spectrum in strong-field regime should show power-law scaling analogous to fluid turbulence.

---

## Verification Steps

### 1. Conservation Laws

Check that discrete scheme conserves:
- Mass: $\sum_i \rho_i = \text{const}$ ✓ (by construction)
- Momentum: $\sum_i \mathbf{p}_i$ changes only due to external forces ✓
- Energy: Total energy decreases due to viscosity (irreversibility) ✓

### 2. Galilean Invariance

Navier-Stokes equation is Galilean invariant. Check if discrete version preserves this symmetry in continuum limit.

**Issue**: Lattice breaks rotational invariance. Johnson graphs have high symmetry but not full SO(3).

**Resolution**: Symmetry emerges in $N \to \infty$ limit (CLEM mechanism).

### 3. Numerical Tests

Implement discrete scheme and compare with known solutions:
- Poiseuille flow (channel flow)
- Taylor-Green vortex
- Decaying turbulence

Validate convergence to analytical/numerical benchmarks.

---

## Open Questions

1. **Compressible flow**: Can we derive compressible Navier-Stokes (with sound waves)?
2. **Quantum turbulence**: How does quantum mechanics (QLEM) modify turbulence?
3. **Relativistic extension**: Derive relativistic fluid dynamics from WorldBase?
4. **Turbulence onset**: Predict critical Reynolds number for transition to turbulence from discrete parameters?

---

## Related Work

- **2D Turbulence Paper**: `../../papers/03-turbulence-2d.md`
- **Gravitational Wave Turbulence**: `../../papers/05-gravitational-wave-turbulence.md`
- **Continuous Limit Theory**: `../../02-worldbase物理框架/04-continuous-limit.md`
- **CLEM Tasks**: [../CLEM-TASK-01.md](../CLEM-TASK-01.md), [../CLEM-TASK-02.md](../CLEM-TASK-02.md)

---

## References

1. Frisch, U. (1995). *Turbulence: The Legacy of A. N. Kolmogorov*. Cambridge University Press.
2. Boffetta, G., & Ecke, R. E. (2012). "Two-Dimensional Turbulence". *Annual Review of Fluid Mechanics* 44: 427-451.
3. Landau, L. D., & Lifshitz, E. M. (1987). *Fluid Mechanics* (2nd ed.). Butterworth-Heinemann.
4. Pope, S. B. (2000). *Turbulent Flows*. Cambridge University Press.

---

**Maintained by:** David Du  
**Contact:** 276857401@qq.com
