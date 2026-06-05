"""
Integration demo: MultiMembershipSeal + AxiomConstraints
"""
import torch
import random
from acl.axioms_v2 import AxiomConstraints
from engine.multi_membership_seal import MultiMembershipSeal

N = 24
constraints = AxiomConstraints(N, n_hierarchy_bits=8)

mms = MultiMembershipSeal(
    N=N,
    binding_strength=constraints.binding_strength,
    org_formation_interval=20,
    org_join_threshold=0.1,
    lock_threshold=0.95,
    max_orgs_per_bit=4,
    min_org_size=2,
    sealing_activation_threshold=int(0.75 * N),
)

random.seed(42)

# Build up binding strength through correlated activity patterns
# Use lateral bits (8-23) for org formation since strengthen_binding requires lateral
# Phase 1 (steps 0-100): cluster A (bits 8-13) co-active
# Phase 2 (steps 100-200): cluster B (bits 12-17) co-active (overlap at 12,13)
# Phase 3 (steps 200-300): cluster C (bits 16-21) co-active (overlap at 16,17)

for step in range(300):
    if step < 100:
        cluster = list(range(8, 14))
    elif step < 200:
        cluster = list(range(12, 18))
    else:
        cluster = list(range(16, 22))
    
    bit = random.choice(cluster)
    mms.record_active(bit, step)
    # Also activate some random bits to build unique active count
    if step % 3 == 0:
        mms.record_active(random.randint(0, N - 1), step)
    
    # Strengthen bindings within the active cluster
    if step % 5 == 0:
        i, j = random.sample(cluster, 2)
        constraints.binding_strength[i][j] += 0.08
        constraints.binding_strength[j][i] += 0.08
    
    # Strengthen bridge bits at cluster transitions
    if step % 12 == 0 and step >= 80:
        if step < 200:
            # Bridge A-B: bits 12,13 (in both clusters)
            for b in [12, 13]:
                for a in range(8, 12):
                    constraints.binding_strength[a][b] += 0.02
                    constraints.binding_strength[b][a] += 0.02
                for c in range(14, 18):
                    constraints.binding_strength[c][b] += 0.02
                    constraints.binding_strength[b][c] += 0.02
        else:
            # Bridge B-C: bits 16,17 (in both clusters)
            for b in [16, 17]:
                for a in range(12, 16):
                    constraints.binding_strength[a][b] += 0.02
                    constraints.binding_strength[b][a] += 0.02
                for c in range(18, 22):
                    constraints.binding_strength[c][b] += 0.02
                    constraints.binding_strength[b][c] += 0.02
    
    if step > 0 and step % mms.org_formation_interval == 0:
        mms.form_organizations(step)

summary = mms.get_summary()

print("=== A9 Multi-Membership Seal Integration Demo (N=24, 200 steps) ===")
print(f"Organizations: {summary['n_organizations']}")
print(f"Multi-member bits: {summary['n_multi_member_bits']}")
print(f"Fully locked: {summary['n_fully_locked']}")
print(f"Partially locked: {summary['n_partially_locked']}")
print(f"Free: {summary['n_free']}")
print(f"Avg lock level: {summary['avg_lock_level']:.3f}")
print(f"Max memberships: {summary['max_memberships']}")
print(f"Avg org size: {summary['avg_org_size']}")
print(f"Overlapping org pairs: {summary['n_overlapping_org_pairs']}")

print("\n=== Multi-Member Bit Details ===")
for bit_idx in range(N):
    memberships = mms.get_org_memberships(bit_idx)
    if len(memberships) > 1:
        ll = mms.compute_lock_level(bit_idx)
        parts = [f"Org{o}(w={w:.2f})" for o, w in memberships]
        orgs_str = ", ".join(parts)
        print(f"  Bit {bit_idx}: L={ll:.2f}, orgs=[{orgs_str}]")

print("\n=== Organization Details ===")
for org_id, org in sorted(mms.organizations.items()):
    members = sorted(org.members)
    print(f"  Org {org_id}: members={members}, binding={org.avg_binding:.3f}, step={org.formation_step}")

print("\n=== Backward Compat Check ===")
sealed = mms.sealed_bits
print(f"sealed_bits (computed): {sorted(sealed)}")
print(f"sealed (computed): {mms.sealed}")

mms.sealed_bits = {0, 1, 2}
print(f"sealed_bits (override): {sorted(mms.sealed_bits)}")
mms.clear_overrides()
print(f"sealed_bits (after clear): {sorted(mms.sealed_bits)}")

print("\nIntegration demo OK!")
