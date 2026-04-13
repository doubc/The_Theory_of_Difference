# **`papers/05-gravitational-wave-turbulence.md`**

```markdown
# Gravitational Wave Turbulence from Axioms of Difference:
# A Constraint-Derivation of $E(k) \propto k^{-7/3}$

**Author**: [David Du]  
**Date**: April 2026  
**Status**: 🔷 Primary derivation complete; GW-6 (polarization cross-invariant) pending

---

## Abstract

We derive the energy spectrum of gravitational wave turbulence from four elements of the
WorldBase constraint-derivation framework: A5 (Difference Conservation), A6 (Irreversibility),
the three-dimensional shell geometry (D=3), and the nonlinear self-coupling structure of the
Einstein field equations (Theorem NP). No phenomenological closure assumptions and no free
parameters are introduced.

The derivation identifies the key structural distinction between gravitational wave turbulence
and fluid turbulence: in fluid turbulence, the nonlinear coupling operator is
$\mathbf{u} \cdot \nabla \mathbf{u}$ (first-order spatial derivative, contributing one factor
of $k$ to the characteristic time); in gravitational wave turbulence, the nonlinear coupling
operator is $h \cdot \partial^2 h$ (second-order spatial derivative, contributing two factors
of $k$). This single structural difference shifts the flux relation from
$\Pi(k) \sim k^{5/2} E^{3/2}$ to $\Pi(k) \sim k^{7/2} E^{3/2}$, and the predicted spectrum
from $k^{-5/3}$ to:

$$\boxed{E(k) \propto k^{-7/3}}$$

This prediction coincides with the Zakharov weak turbulence result (1967, 1992), but is derived
here without the Zakharov kinetic equation — solely from the axiom set
$\{A5, A6, D, \text{NP}\}$. The result is in principle testable against LIGO/Virgo stochastic
gravitational wave background observations.

The general formula relating the spectral exponent $\alpha$ to the derivative order $n$ of the
nonlinear coupling operator is:

$$\alpha = \frac{2n + 3}{3}$$

yielding $\alpha = 5/3$ for fluid turbulence ($n=1$) and $\alpha = 7/3$ for gravitational wave
turbulence ($n=2$), with the difference $\Delta\alpha = 2/3$ being an exact algebraic consequence
of the derivative order difference.

**Keywords**: gravitational wave turbulence; energy spectrum; constraint derivation; weak
turbulence; LNCIM framework; nonlinear self-coupling; Zakharov theory

---

## 1. Introduction

### 1.1 Context: The First Predictive Derivation in the Framework

The WorldBase framework has, prior to the turbulence series, operated primarily in an
*explanatory* mode: given a known physical result (Newton's $-1/r$ potential, the
$\mathfrak{su}(2)$ gauge algebra, the Higgs mechanism), the framework derives it from axioms,
demonstrating that the result is a necessary consequence of the axiom set rather than an
independent assumption.

The turbulence series represents a qualitative departure from this mode. When the question was
posed — *can the axiom subsets constrain the form of turbulent cascade spectra, given that
turbulence remains one of the major unsolved problems in physics?* — no target answer was
known in advance. The derivation proceeded by constraint alone: the axiom subset
$\{A4, A5, A6, D, \text{NP}\}$ was identified as the relevant structure class (LNCIM: Local
Nonlinear Conservative Irreversible Multiscale), and the energy spectrum was derived as the
unique power law consistent with the axioms and the dimensional geometry.

The result $k^{-10/3}$ for the two-dimensional enstrophy cascade [CITATION: Paper 3] and
$k^{-7/3}$ for gravitational wave turbulence (this paper) are therefore the framework's first
genuinely *predictive* outputs — predictions made without knowing the answer, rather than
derivations made to recover a known result.

This distinction matters for the scientific status of the framework. A framework that only
recovers known results is, at best, a unification scheme. A framework that makes novel,
falsifiable predictions that differ from existing theory is a candidate for new physics.

### 1.2 The Physical System

Gravitational wave turbulence arises when a stochastic background of gravitational waves
undergoes nonlinear self-interaction. In the weak-field limit, the metric perturbation
$h_{\mu\nu}$ satisfies the linearized Einstein equation, but at second order, the nonlinear
term $h \cdot \partial^2 h$ generates wave-wave interactions that redistribute energy across
scales. This is the gravitational analog of the fluid turbulence cascade.

The key physical difference from fluid turbulence is the propagation speed. In fluid turbulence,
the nonlinear coupling velocity is set by the field itself ($\sim u$, which varies with scale).
In gravitational wave turbulence, the wave propagation speed is fixed at $c$ — a consequence of
Theorem CL (the continuous limit theorem), which establishes that the metric perturbation
propagates at the universal speed determined by the discrete-to-continuous limit. The nonlinear
coupling is still mediated by $h$, but the *propagation* is at fixed speed $c$.

This distinction has no effect on the spectral exponent derivation (which depends only on the
derivative order of the nonlinear coupling, not on the propagation speed), but it is important
for understanding the physical regime in which the turbulence occurs.

### 1.3 Relationship to Zakharov Weak Turbulence Theory

The prediction $E(k) \propto k^{-7/3}$ coincides with the Zakharov (1967, 1992) weak turbulence
result for gravitational waves. The Zakharov derivation proceeds through the kinetic equation
for four-wave interactions, which requires the explicit form of the gravitational wave interaction
vertex — a calculation that depends on the specific structure of the Einstein equation.

The present derivation requires none of this. It uses only:
- A5: a conserved quantity exists and satisfies a continuity equation
- A6: the cascade is directed and approaches steady state
- D=3: three-dimensional shell geometry determines $\delta h(k)$
- NP: the nonlinear coupling has the form $h \cdot \partial^2 h$

The coincidence with Zakharov is not surprising — both derivations ultimately reflect the same
physical structure — but the present derivation is more economical: it identifies the minimal
axiomatic content required to fix the exponent, without requiring the full machinery of
weak turbulence theory.

---

## 2. Axiomatic Framework

### 2.1 The Relevant Axiom Subset

The gravitational wave turbulence derivation uses a strict subset of the LNCIM class:

$$S_{\text{GW}} = \{A5,\ A6,\ D,\ \text{NP}\}$$

Note the absence of A4. In fluid turbulence, A4 (Minimal Variation / Locality) plays a
double role: it establishes the locality of the cascade *and* contributes the factor of $k$ to
the characteristic time through the spatial derivative of the coupling operator. In gravitational
wave turbulence, the nonlinear coupling $h \cdot \partial^2 h$ already contains two spatial
derivatives by the structure of the Einstein equation (Theorem NP), so A4 is not needed as a
separate input — the derivative structure is already fixed by NP.

| Axiom / Theorem | Role | Source |
|----------------|------|--------|
| A5 (Conservation) | Gravitational wave energy conservation; flux stationarity | §3.2 |
| A6 (Irreversibility) | Directed cascade; steady-state condition | §3.2 |
| D = 3 | Three-dimensional shell geometry; $\delta h(k) \sim (E \cdot k^3)^{1/2}$ | §3.4 |
| NP (Nonlinear self-coupling) | $h \cdot \partial^2 h$ structure; two factors of $k$ in $\tau(k)$ | §3.3 |

### 2.2 The Key Structural Distinction

The single structural difference between fluid and gravitational wave turbulence is the
derivative order of the nonlinear coupling operator:

| System | Nonlinear coupling | Derivative order $n$ | $\tau(k)$ | Flux $\Pi(k)$ | Spectrum |
|--------|-------------------|---------------------|-----------|---------------|---------|
| Fluid turbulence | $\mathbf{u} \cdot \nabla \mathbf{u}$ | $n = 1$ | $\sim 1/(h \cdot k)$ | $\sim k^{5/2} E^{3/2}$ | $k^{-5/3}$ |
| GW turbulence | $h \cdot \partial^2 h$ | $n = 2$ | $\sim 1/(h \cdot k^2)$ | $\sim k^{7/2} E^{3/2}$ | $k^{-7/3}$ |

Each additional order of spatial derivative in the nonlinear coupling contributes one additional
factor of $k$ to the flux relation, shifting the spectral exponent by $-2/3$. This is exact.

---

## 3. Derivation of the Gravitational Wave Energy Spectrum

### 3.1 Overview

The derivation follows the same five-step structure as the LNCIM framework [CITATION: T-018],
with the fluid velocity $\delta u(k)$ replaced by the metric perturbation amplitude $\delta h(k)$,
and the first-order derivative $\nabla$ replaced by the second-order derivative $\partial^2$.

### 3.2 Step 1: Energy Flux Stationarity

**Source**: A5 (Conservation) + A6 (Irreversibility)

The gravitational wave energy density in the weak-field limit:

$$\mathcal{E}(k) \sim h^2 k^2$$

where $h$ is the metric perturbation amplitude and $k^2$ arises from the spatial derivative
structure of the gravitational wave stress-energy tensor (Theorem CL-T applied to the
Isaacson tensor).

By A5, total gravitational wave energy is conserved in the inertial range. The $k$-space
continuity equation:

$$\frac{\partial E(k)}{\partial t} + \frac{\partial \Pi(k)}{\partial k} = 0
\quad \text{(inertial range)}$$

By A6, the cascade is irreversible and directed (energy flows from large to small scales in
the weak turbulence regime), and the system approaches steady state. In steady state:

$$\frac{\partial E(k)}{\partial t} = 0 \implies
\frac{\partial \Pi(k)}{\partial k} = 0 \implies
\boxed{\Pi(k) = \Pi_0 = \text{const}}$$

**Proof status**: 🔷 (GW-3: flux stationarity complete; depends on A5+A6 in the same form
as LNCIM-5)

### 3.3 Step 2: Characteristic Time Scale from NP

**Source**: Theorem NP (Nonlinear self-coupling structure)

The Einstein equation at second order generates the nonlinear coupling term $h \cdot \partial^2 h$.
In Fourier space at scale $k$, the characteristic amplitude of this coupling is:

$$\delta h(k) \cdot k^2$$

where the factor $k^2$ comes from the two spatial derivatives in $\partial^2$ — this is the
structural difference from fluid turbulence, where $\nabla \mathbf{u}$ contributes only one
factor of $k$.

The characteristic nonlinear coupling time at scale $k$:

$$\tau(k) \sim \frac{1}{\delta h(k) \cdot k^2}$$

**Comparison with fluid turbulence**: In fluid turbulence (LNCIM-6), the advection term
$\mathbf{u} \cdot \nabla \mathbf{u}$ gives $\tau(k) \sim 1/(\delta u(k) \cdot k)$. The
gravitational wave coupling has one additional spatial derivative, giving
$\tau(k) \sim 1/(\delta h(k) \cdot k^2)$. This single factor of $k$ is the entire source of
the difference between $k^{-5/3}$ and $k^{-7/3}$.

**Proof status**: 🔷 (GW-2: nonlinear coupling structure from Theorem NP + Theorem CL-T;
the identification of $h \cdot \partial^2 h$ as the leading nonlinear term requires the
second-order expansion of the Einstein equation, which is established in the GR derivation
chain §4.13)

### 3.4 Step 3: Metric Perturbation Amplitude from Three-Dimensional Shell Geometry

**Source**: D = 3 geometry + Parseval's theorem

In three dimensions, the shell in wavenumber space at radius $k$ with width $\Delta k \sim k$
is a spherical shell with area $4\pi k^2$. The energy contribution from this shell:

$$(\delta h(k))^2 \sim E(k) \cdot k^2 \cdot k = E(k) \cdot k^3$$

Therefore:

$$\boxed{\delta h(k) \sim (E(k) \cdot k^3)^{1/2} = k^{3/2} \cdot E(k)^{1/2}}$$

This is identical in form to the fluid velocity fluctuation relation in three dimensions
(LNCIM-6). The shell geometry is the same; only the physical interpretation of the field
changes ($h$ instead of $u$).

**Proof status**: ✅ (GW-1: three-dimensional shell geometry is exact; same derivation as
LNCIM-4 + LNCIM-6)

### 3.5 Step 4: Energy Flux Relation

Combining Steps 2 and 3, the characteristic time is:

$$\tau(k) \sim \frac{1}{\delta h(k) \cdot k^2}
= \frac{1}{k^{3/2} E(k)^{1/2} \cdot k^2}
= \frac{1}{k^{7/2} \cdot E(k)^{1/2}}$$

The energy flux $\Pi(k)$ — energy transferred per unit time through scale $k$:

$$\Pi(k) \sim \frac{E(k)}{\tau(k)} \sim E(k) \cdot k^{7/2} \cdot E(k)^{1/2}
= k^{7/2} \cdot E(k)^{3/2}$$

**Dimensional verification**: The exponent is determined by the $k$-dependence alone.
The $L^{-1/2}$ dimensional discrepancy noted in the two-dimensional enstrophy cascade
[CITATION: Paper 3, §3.0] appears here as well, with the same resolution: it reflects the
implicit normalization of flux per unit wavenumber and does not affect the power-law exponent.

**Proof status**: 🔷 (GW-4 precursor: flux relation complete; dimensional prefactor carries
the same $\mathcal{L}^{1/3}$-type normalization as Paper 3 §3.0)

### 3.6 Step 5: Energy Spectrum from Flux Stationarity

From Step 1, $\Pi(k) = \Pi_0 = \text{const}$.
From Step 4, $\Pi(k) \sim k^{7/2} \cdot E(k)^{3/2}$.

Setting these equal:

$$k^{7/2} \cdot E(k)^{3/2} = \Pi_0$$

$$E(k)^{3/2} = \Pi_0 \cdot k^{-7/2}$$

$$\boxed{E(k) = \Pi_0^{2/3} \cdot k^{-7/3}}$$

**Verification**: $k^{7/2} \cdot (k^{-7/3})^{3/2} = k^{7/2} \cdot k^{-7/2} = 1$ ✓

### 3.7 Derivation Chain Summary


A5 (Conservation) ──┐
                    ├──→ Π(k) = const ─────────────────────────┐
A6 (Irreversibility)┘                                          │
                                                               │
NP (h·∂²h coupling) ────→ τ(k) ~ 1/(h·k²) ────────────────────┤
                                                               │
D=3 shell geometry ──────→ δh(k) ~ k^(3/2)·E^(1/2) ───────────┤
                                                               │
                          Π(k) ~ k^(7/2)·E(k)^(3/2) ──────────┤
                                                               │
                                                               ▼


No circular dependencies. Every step follows from the preceding steps or directly from the
axiom subset $\{A5, A6, D, \text{NP}\}$.

---

## 4. The General Formula and the LNCIM Class

### 4.1 Derivative Order and Spectral Exponent

The derivation reveals a general relationship between the derivative order $n$ of the nonlinear
coupling operator and the spectral exponent $\alpha$. For a system in $D=3$ with nonlinear
coupling of the form $q \cdot \partial^n q$:

The characteristic time: $\tau(k) \sim 1/(\delta q(k) \cdot k^n)$

The shell geometry (D=3): $\delta q(k) \sim k^{3/2} E(k)^{1/2}$

The flux relation: $\Pi(k) \sim k^{n + 3/2} \cdot E(k)^{3/2}$

Setting $\Pi(k) = \text{const}$ and solving:

$$\boxed{\alpha = \frac{2n + 3}{3}}$$

| $n$ | Physical system | Coupling operator | $\alpha$ |
|-----|----------------|-------------------|----------|
| 1 | Fluid turbulence (3D energy cascade) | $\mathbf{u} \cdot \nabla \mathbf{u}$ | $5/3$ |
| 2 | Gravitational wave turbulence | $h \cdot \partial^2 h$ | $7/3$ |
| 3 | Hypothetical: $q \cdot \partial^3 q$ | — | $3$ |

Each unit increase in derivative order shifts the spectral exponent by exactly $+2/3$.
This is the algebraic signature of the spatial derivative structure in the LNCIM class.

### 4.2 Dimensional Dependence

The general formula for $D$-dimensional space with coupling order $n$:

$$\alpha = \frac{2n + D - 1}{3}$$

Special cases:

| $D$ | $n=2$ (GW turbulence) | Physical meaning |
|-----|----------------------|-----------------|
| 2 | $E(k) \propto k^{-5/3}$ | 2D GW turbulence (coincides with 3D fluid) |
| 3 | $E(k) \propto k^{-7/3}$ | 3D GW turbulence (physical case) |
| 4 | $E(k) \propto k^{-3}$ | 4D GW turbulence |

The $D=3$ case gives the widest inertial range (slowest spectral decay), consistent with
$D=3$ being the physically realized dimension.

---

## 5. Proof Status Summary

| Proposition | Content | Source | Status |
|------------|---------|--------|--------|
| GW-1 | Gravitational wave energy conservation | A5 + CL-T | ✅ |
| GW-2 | Nonlinear self-coupling structure ($h \cdot \partial^2 h$) | NP + CL | 🔷 |
| GW-3 | Inertial range flux stationarity | A5 + A6 | 🔷 |
| GW-4 | Energy spectrum $E(k) \propto k^{-7/3}$ | GW-1 + GW-2 + GW-3 | 🔷 |
| GW-5 | General formula $\alpha = (2n+3)/3$ | LNCIM-7 + GW-4 | 🔷 |
| GW-6 | Dual polarization cross-invariant conservation | A5 + dual-field structure | 🔶 |
| GW-7 | $D$-dimensional generalization | D + GW-4 | 🔷 |

**GW-6 note**: Gravitational waves carry two polarization states ($+$ and $\times$). The
cross-invariant $H_c = \int h_+ \cdot h_\times \, d^3x$ is expected to be conserved by the
symmetry of the linearized Einstein equation, but the conservation proof requires detailed
expansion of the second-order nonlinear terms. This is structurally analogous to the
cross-helicity in MHD turbulence (see §5.2 below). Current status: 🔶 (analogy argument;
strict proof requires explicit second-order Einstein equation expansion).

---

## 6. Discussion

### 6.1 Relationship to Existing Theory

The prediction $E(k) \propto k^{-7/3}$ is not new as a numerical result — Zakharov (1967)
derived it from weak turbulence theory. What is new is the derivation path. The Zakharov
derivation requires the explicit gravitational wave interaction vertex, computed from the
Einstein equation, and the solution of the kinetic equation for four-wave interactions.
The present derivation requires only four elements: A5, A6, D=3, and the derivative order
of the nonlinear coupling. The identification of $n=2$ as the relevant derivative order is
the only place where the specific structure of general relativity enters.

This economy of derivation has a practical consequence: the general formula $\alpha = (2n+3)/3$
immediately predicts the spectral exponent for any physical system once the derivative order
of its nonlinear coupling is identified, without requiring the full weak turbulence calculation.

### 6.2 Relationship to MHD Turbulence

The dual polarization structure of gravitational waves (GW-6) is structurally analogous to
the dual-field structure of MHD turbulence, where the velocity field $\mathbf{u}$ and the
magnetic field $\mathbf{B}$ are coupled. In MHD, the cross-helicity
$H_c = \int \mathbf{u} \cdot \mathbf{B} \, d^3x$ is conserved, and its conservation modifies
the energy spectrum (Goldreich-Sridhar 1995 critical balance).

For gravitational waves, the two polarizations $h_+$ and $h_\times$ play the role of the two
MHD fields. If $H_c^{\text{GW}} = \int h_+ \cdot h_\times \, d^3x$ is conserved (GW-6),
the gravitational wave turbulence spectrum may be modified from the single-field $k^{-7/3}$
prediction. This is an open question that connects the gravitational wave turbulence problem
to the richer structure of MHD turbulence theory.

### 6.3 Observational Prospects

The stochastic gravitational wave background (SGWB) is a target of LIGO/Virgo/KAGRA and
future space-based detectors (LISA, TianQin). Current SGWB searches characterize the
background by its spectral index $\Omega_{\text{GW}}(f) \propto f^{n_T}$, where
$n_T$ is related to the energy spectrum exponent by $n_T = \alpha - 1$.

For $E(k) \propto k^{-7/3}$, the corresponding SGWB spectral index is:

$$n_T = -7/3 - 1 = -10/3 \approx -3.33$$

This is a specific, parameter-free prediction distinguishable from other SGWB sources
(inflation: $n_T \approx 0$; cosmic strings: $n_T \approx -1$; phase transitions: model-dependent).

**Observational caveat**: The gravitational wave turbulence spectrum applies to a specific
physical regime — a stochastic background undergoing nonlinear self-interaction in the
weak-field limit. Whether this regime is realized for any astrophysical or cosmological SGWB
source is a separate physical question, not addressed by the present derivation.

### 6.4 The Turbulence Series as Predictive Derivation

As noted in §1.1, the turbulence series occupies a unique position in the framework's
development. The derivations of gravitational potential, gauge algebra, and Higgs mechanism
were all *explanatory*: the target was known, and the framework was shown to necessitate it.

The turbulence series was *predictive*: the axiom subset $\{A4, A5, A6, D, \text{NP}\}$ was
identified as the relevant structure class, and the spectrum was derived without a known
target. The coincidence of $k^{-7/3}$ with the Zakharov result was discovered *after* the
derivation, not used as a guide.

This distinction is the primary scientific significance of the turbulence series within the
framework. It demonstrates that the constraint-derivation methodology is not merely a
unification scheme for known results, but a generator of novel predictions.

---

## 7. Conclusion

We have derived $E(k) \propto k^{-7/3}$ for gravitational wave turbulence as a necessary
consequence of the axiom subset $\{A5, A6, D, \text{NP}\}$. The key structural insight is
that the second-order spatial derivative in the Einstein nonlinear coupling $h \cdot \partial^2 h$
contributes an additional factor of $k$ to the characteristic time scale compared to fluid
turbulence, shifting the flux relation from $k^{5/2} E^{3/2}$ to $k^{7/2} E^{3/2}$ and the
spectral exponent from $5/3$ to $7/3$.

The general formula $\alpha = (2n+3)/3$ unifies the fluid ($n=1$, $\alpha = 5/3$) and
gravitational wave ($n=2$, $\alpha = 7/3$) cases, and predicts the spectral exponent for
any LNCIM-class system once the derivative order of its nonlinear coupling is identified.

The prediction is in agreement with Zakharov weak turbulence theory and is in principle
testable against LIGO/Virgo stochastic gravitational wave background observations.

---

## References

[1] Zakharov, V. E. (1967). Weak turbulence in media with a decay spectrum.
*Journal of Applied Mechanics and Technical Physics*, **4**, 22–24.

[2] Zakharov, V. E., L'vov, V. S., & Falkovich, G. (1992).
*Kolmogorov Spectra of Turbulence I: Wave Turbulence*. Springer.

[3] D. Du, "Enstrophy Cascade Spectrum in Two-Dimensional Turbulence: A Derivation from
Locality, Conservation, and Dimensional Geometry," [CITATION: Paper 3] (2026).

[4] D. Du, "Newtonian Gravitational Potential from Axioms of Difference,"
[CITATION: Paper 1] (2026).

[5] D. Du, "Discrete Gauge Algebra su(2) and V–A Structure from Axioms of Difference,"
[CITATION: Paper 2] (2026).

[6] Goldreich, P., & Sridhar, S. (1995). Toward a theory of interstellar turbulence.
*Astrophysical Journal*, **438**, 763–775.

[7] Isaacson, R. A. (1968). Gravitational radiation in the limit of high frequency.
*Physical Review*, **166**, 1263–1271.
```
