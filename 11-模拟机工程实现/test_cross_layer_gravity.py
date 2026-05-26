"""
test_cross_layer_gravity.py -- Cross-Layer Gravity Modulation Tests
"""

import torch
import sys
sys.path.insert(0, '.')

from engine.cross_layer_gravity import GravityField, CrossLayerGravityModulator
from engine.encapsulation_engine import EncapsulationEngine, EncapsulatedBit


def test_gravity_field_creation():
    state = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    frozen = {0, 1, 2, 3}
    active = {0, 1, 2, 3, 4, 5, 6, 7}

    modulator = CrossLayerGravityModulator()
    field = modulator.compute_gravity_field(
        layer_id=0, state=state, frozen_bits=frozen,
        active_bits=active, step=0
    )

    assert field.layer_id == 0
    assert field.total_mass == 2
    assert field.potential.shape == (8,)
    assert field.potential.abs().max() <= 1.0
    print(f"[PASS] GravityField: L0, mass={field.total_mass}, phi_max={field.potential.max().item():.4f}")


def test_gravity_field_with_binding():
    state = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    frozen = {0, 1, 2, 3}
    active = set(range(8))
    binding = torch.zeros(8, 8)
    binding[0, 1] = 0.8
    binding[1, 0] = 0.8
    binding[2, 3] = 0.2
    binding[3, 2] = 0.2

    modulator = CrossLayerGravityModulator()
    field = modulator.compute_gravity_field(
        layer_id=0, state=state, frozen_bits=frozen,
        active_bits=active, binding_strength=binding, step=0
    )

    assert field.total_mass == 2
    print(f"[PASS] GravityField with binding: phi_mean={field.potential.mean().item():.4f}")


def test_gravity_projection_up():
    state_low = torch.tensor([1.0, 1.0, 0.0, 0.0])
    frozen = {0, 1}
    active = {0, 1, 2, 3}

    modulator = CrossLayerGravityModulator()
    field = modulator.compute_gravity_field(
        layer_id=0, state=state_low, frozen_bits=frozen,
        active_bits=active, step=0
    )

    projected = modulator.project_gravity_up(
        source_layer_id=0, source_field=field,
        target_N=4, encap_engine=None, source_layer=0
    )

    assert projected.shape == (4,)
    assert projected.abs().max() <= 1.0
    print(f"[PASS] Gravity projection: low N=4 -> high N=4, max={projected.max().item():.4f}")


def test_gravity_projection_with_encapsulation():
    state = torch.tensor([1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    frozen = {0, 1, 2}
    active = {3, 4, 5, 6, 7, 8}
    binding = torch.ones(9, 9) * 0.5

    encap = EncapsulationEngine(binding_threshold=0.3, min_group_size=2)
    new_state, enc_bits, mapping = encap.encapsulate(
        state=state, frozen_bits=frozen, binding_strength=binding,
        active_bits=active, layer=0
    )

    assert len(enc_bits) == 1
    assert len(new_state) == 7

    modulator = CrossLayerGravityModulator()
    field = modulator.compute_gravity_field(
        layer_id=0, state=state, frozen_bits=frozen,
        active_bits=active, binding_strength=binding, step=0
    )

    projected = modulator.project_gravity_up(
        source_layer_id=0, source_field=field,
        target_N=len(new_state), encap_engine=encap, source_layer=0
    )

    assert projected.shape == (7,)
    print(f"[PASS] Gravity with encapsulation: L0 N=9 -> L1 N=7, enc_bits={len(enc_bits)}, phi_max={projected.max().item():.4f}")


def test_modulation_computation():
    modulator = CrossLayerGravityModulator(
        gravity_decay=0.5,
        modulation_strength=0.1,
        distance_exponent=2.0
    )

    field_l0 = GravityField(
        layer_id=0,
        potential=torch.tensor([0.8, 0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6]),
        mass_sources=[0, 1],
        generation_step=0
    )
    field_l2 = GravityField(
        layer_id=2,
        potential=torch.tensor([0.5, 0.3, 0.1, -0.1, -0.3, -0.5]),
        mass_sources=[0],
        generation_step=0
    )

    target_state = torch.zeros(8)

    result = modulator.compute_modulation(
        layer_id=1,
        lower_fields=[field_l0],
        upper_fields=[field_l2],
        target_state=target_state
    )

    assert 'modulation_vector' in result
    assert result['modulation_vector'].shape == (8,)
    assert result['n_lower_fields'] == 1
    assert result['n_upper_fields'] == 1
    print(f"[PASS] Modulation: L1 receives from L0(up) and L2(down), strength={result['modulation_strength']}")


def test_gravity_projection_down():
    """测试高层引力向下投影到低层"""
    modulator = CrossLayerGravityModulator(gravity_decay=0.5)

    # 高层 N=4 -> 低层 N=8
    field_high = GravityField(
        layer_id=2,
        potential=torch.tensor([0.8, 0.4, -0.4, -0.8]),
        mass_sources=[0],
        generation_step=0
    )

    projected = modulator.project_gravity_down(
        source_field=field_high, target_N=8, decay_factor=0.5
    )

    assert projected.shape == (8,)
    assert projected.abs().max() <= 0.5  # 衰减后不超过 0.5
    print(f"[PASS] Gravity projection down: L2 N=4 -> L0 N=8, max={projected.max().item():.4f}")


def test_injection_modulation_scores():
    modulator = CrossLayerGravityModulator(modulation_strength=0.1)

    field_l0 = GravityField(
        layer_id=0,
        potential=torch.tensor([0.9, 0.7, 0.5, 0.3, 0.1, -0.1, -0.3, -0.5]),
        mass_sources=[0, 1],
        generation_step=0
    )

    all_fields = {0: [field_l0]}
    candidates = [0, 1, 2, 3, 4]

    scores = modulator.get_modulation_for_injection(
        layer_id=1, candidates=candidates, all_fields=all_fields
    )

    assert scores[0] > scores[4], f"Expected scores[0]={scores[0]} > scores[4]={scores[4]}"
    print(f"[PASS] Injection modulation: scores={scores}")


def run_all_tests():
    print("=" * 60)
    print("Cross-Layer Gravity Modulation Tests")
    print("=" * 60)

    test_gravity_field_creation()
    test_gravity_field_with_binding()
    test_gravity_projection_up()
    test_gravity_projection_down()
    test_gravity_projection_with_encapsulation()
    test_modulation_computation()
    test_injection_modulation_scores()

    print("=" * 60)
    print("All 7 tests passed [OK]")
    print("=" * 60)


if __name__ == '__main__':
    run_all_tests()
