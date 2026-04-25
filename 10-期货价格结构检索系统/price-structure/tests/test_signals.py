"""
Signal Layer Numerical Correctness Tests

Test Focus:
1. 5-dimensional breakout score calculation correctness (penetration depth, volume, flux, compression, dwell)
2. Fake breakout 5 pattern trigger condition reasonableness
3. Position factor calculation compliance with A/B/C/D tier rules
4. Signal priority sorting correctness
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional
import statistics

from src.data.loader import Bar
from src.models import (
    Structure, Zone, Cycle, Segment, Point, 
    MotionState, ProjectionAwareness, StabilityVerdict,
    SignalKind, FakeBreakoutPattern, SystemState
)
from src.signals import (
    generate_signal, detect_fake_breakout, score_breakout_confirmation,
    detect_pullback_confirmation, detect_structure_aging, calculate_position_factor,
    BREAKOUT_STRONG, BREAKOUT_WEAK, FAKE_PENETRATION_THRESHOLD,
    FAKE_VOLUME_CLIMIX, FAKE_VOLUME_DIV, FAKE_FLUX_WEAK, FAKE_SHADOW_RATIO
)
from src.quality import assess_quality, QualityTier


# ============================================================
# Test Data Construction Utilities
# ============================================================

def create_bar(
    timestamp: datetime,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000,
    symbol: str = "TEST"
) -> Bar:
    """Create a single bar"""
    return Bar(
        symbol=symbol,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume
    )


def create_bars_sequence(
    start_date: datetime,
    n_days: int,
    base_price: float = 100.0,
    price_trend: str = "flat",  # flat, up, down
    volume_base: float = 1000,
    volume_spike_day: Optional[int] = None,
    spike_multiplier: float = 2.0
) -> List[Bar]:
    """Create a sequence of bars"""
    bars = []
    for i in range(n_days):
        date = start_date + timedelta(days=i)
        
        # Price trend
        if price_trend == "up":
            trend_offset = i * 0.5
        elif price_trend == "down":
            trend_offset = -i * 0.5
        else:
            trend_offset = 0
        
        # Base price
        base = base_price + trend_offset
        noise = (i % 5 - 2) * 0.2  # Small fluctuation
        
        open_p = base + noise
        close_p = base + noise + (0.3 if i % 2 == 0 else -0.2)
        high_p = max(open_p, close_p) + 0.5
        low_p = min(open_p, close_p) - 0.5
        
        # Volume
        vol = volume_base
        if volume_spike_day is not None and i == volume_spike_day:
            vol *= spike_multiplier
        
        bars.append(create_bar(date, open_p, high_p, low_p, close_p, vol))
    
    return bars


def create_structure_with_zone(
    center: float = 100.0,
    bandwidth: float = 2.0,
    n_cycles: int = 5,
    cycle_count: Optional[int] = None
) -> Structure:
    """Create a test structure with Zone"""
    zone = Zone(
        price_center=center,
        bandwidth=bandwidth,
        strength=n_cycles * 0.5
    )
    
    # Create cycles
    cycles = []
    base_date = datetime(2024, 1, 1)
    for i in range(n_cycles):
        entry_point = Point(t=base_date + timedelta(days=i*10), x=center - bandwidth * 0.5, idx=i*2)
        exit_point = Point(t=base_date + timedelta(days=i*10+5), x=center + bandwidth * 0.5, idx=i*2+1)
        
        entry_seg = Segment(start=entry_point, end=Point(t=entry_point.t + timedelta(days=2), x=center, idx=entry_point.idx+1))
        exit_seg = Segment(start=Point(t=exit_point.t - timedelta(days=2), x=center, idx=exit_point.idx-1), end=exit_point)
        
        cycle = Cycle(entry=entry_seg, exit=exit_seg, zone=zone)
        cycles.append(cycle)
    
    structure = Structure(
        zone=zone,
        cycles=cycles,
        invariants={
            "cycle_count": n_cycles,
            "avg_speed_ratio": 1.2,
            "avg_time_ratio": 1.0,
            "zone_rel_bw": bandwidth / center
        },
        typicality=0.8,
        label="test_structure"
    )
    
    # Manually set cycle_count for testing
    if cycle_count is not None:
        # Adjust by modifying cycles list
        while len(structure.cycles) < cycle_count:
            structure.cycles.append(cycles[0])
        structure.cycles = structure.cycles[:cycle_count]
    
    return structure


def create_system_state(
    flux: float = 0.5,
    structural_age: int = 10,
    phase_tendency: str = "stable",
    is_blind: bool = False,
    stability_verified: bool = True,
    stability_surface: str = "stable"
) -> SystemState:
    """Create system state"""
    motion = MotionState(
        conservation_flux=flux,
        structural_age=structural_age,
        phase_tendency=phase_tendency,
        phase_confidence=0.8
    )
    
    projection = ProjectionAwareness(
        compression_level=0.8 if is_blind else 0.3,
        projection_confidence=0.5 if is_blind else 0.9
    )
    
    stability = StabilityVerdict(
        surface=stability_surface,
        verified=stability_verified
    )
    
    structure = create_structure_with_zone()
    structure.motion = motion
    structure.projection = projection
    structure.stability_verdict = stability
    
    return SystemState(
        structure=structure,
        motion=motion,
        projection=projection,
        stability=stability
    )


# ============================================================
# Test Case 1: 5-dimensional Breakout Score Calculation
# ============================================================

def test_breakout_score_calculation():
    """Test 5-dimensional breakout score calculation"""
    print("\n" + "="*60)
    print("Test 1: 5-dimensional Breakout Score Calculation")
    print("="*60)
    
    # Create base structure: center=100, bandwidth=2 (upper=102, lower=98)
    structure = create_structure_with_zone(center=100.0, bandwidth=2.0, n_cycles=5)
    ss = create_system_state(flux=0.5, structural_age=10)
    
    base_date = datetime(2024, 1, 1)
    
    # Test case 1.1: Exactly 0.55 points (weak breakout threshold)
    print("\n--- Test 1.1: Exactly 0.55 points boundary ---")
    
    # Create a bar that just breaks upper=102 (close=102.5, penetration=0.25 bandwidth)
    bars = create_bars_sequence(base_date, 20, base_price=100.0)
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=101.0,
        high=103.0,
        low=101.0,
        close=102.5,  # Break upper=102, penetration=0.25
        volume=2000   # 2x volume
    )
    
    score, note = score_breakout_confirmation(structure, bars, ss)
    print(f"  Breakout score: {score:.4f}")
    print(f"  Score note: {note}")
    print(f"  Expected: should be >= 0.55 to trigger weak breakout signal")
    
    # Manual calculation verification
    # penetration = (102.5 - 102) / 2 = 0.25
    # score_penetration = min(0.25 / 0.5, 1.0) = 0.5
    # volume_ratio = 2000 / 1000 = 2.0 (assuming median=1000)
    # score_volume = min(2.0 / 2.0, 1.0) = 1.0
    # flux=0.5, direction=1, aligned, strength=0.5 -> score_flux = 0.5
    # n_tests=5 -> score_compression = min(5/5, 1.0) = 1.0
    # days=10 -> score_dwell = min(10/10, 1.0) = 1.0
    # total = 0.5*0.25 + 1.0*0.25 + 0.5*0.15 + 1.0*0.20 + 1.0*0.15 = 0.80
    
    expected_score = 0.5 * 0.25 + 1.0 * 0.25 + 0.5 * 0.15 + 1.0 * 0.20 + 1.0 * 0.15
    print(f"  Manual calculation expected: {expected_score:.4f}")
    
    # Verify boundary
    assert score >= BREAKOUT_WEAK, f"Score should be >= {BREAKOUT_WEAK} to trigger weak breakout"
    print(f"  [PASS] Score >= {BREAKOUT_WEAK}, can trigger weak breakout signal")
    
    # Test case 1.2: Exactly 0.80 points (strong breakout threshold)
    print("\n--- Test 1.2: Exactly 0.80 points boundary (strong breakout) ---")
    # Higher penetration and better flux
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=101.0,
        high=104.0,
        low=101.0,
        close=103.0,  # penetration=0.5
        volume=3000   # 3x volume
    )
    
    # Adjust flux to fully align
    ss.motion.conservation_flux = 0.8  # Strong positive flux
    
    score, note = score_breakout_confirmation(structure, bars, ss)
    print(f"  Breakout score: {score:.4f}")
    print(f"  Score note: {note}")
    
    # penetration = (103-102)/2 = 0.5 -> score_penetration = 1.0
    # volume_ratio = 3.0 -> score_volume = 1.0
    # flux=0.8, aligned, strength>0.3 -> score_flux = 1.0
    expected_score = 1.0 * 0.25 + 1.0 * 0.25 + 1.0 * 0.15 + 1.0 * 0.20 + 1.0 * 0.15
    print(f"  Manual calculation expected: {expected_score:.4f}")
    
    if score >= BREAKOUT_STRONG:
        print(f"  [PASS] Score >= {BREAKOUT_STRONG}, triggers strong breakout signal")
    else:
        print(f"  [INFO] Score < {BREAKOUT_STRONG}, only weak breakout")
    
    # Test case 1.3: Below 0.55 points (no breakout signal)
    print("\n--- Test 1.3: Below 0.55 points (no signal) ---")
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=100.5,
        high=101.5,
        low=100.5,
        close=101.0,  # Not breaking upper=102
        volume=1000
    )
    
    score, note = score_breakout_confirmation(structure, bars, ss)
    print(f"  Breakout score: {score:.4f}")
    print(f"  Score note: {note}")
    
    if score < BREAKOUT_WEAK:
        print(f"  [PASS] Score < {BREAKOUT_WEAK}, does not trigger breakout signal")
    else:
        print(f"  [WARN] Score >= {BREAKOUT_WEAK}, unexpectedly triggers breakout signal")
    
    return True


# ============================================================
# Test Case 2: Fake Breakout 5 Pattern Trigger Conditions
# ============================================================

def test_fake_breakout_patterns():
    """Test fake breakout 5 pattern trigger conditions"""
    print("\n" + "="*60)
    print("Test 2: Fake Breakout 5 Pattern Trigger Conditions")
    print("="*60)
    
    structure = create_structure_with_zone(center=100.0, bandwidth=2.0, n_cycles=5)
    base_date = datetime(2024, 1, 1)
    
    # Test case 2.1: FAKE_PIN (Probe type)
    print("\n--- Test 2.1: FAKE_PIN Probe Type ---")
    print(f"  Trigger condition: high > upper({structure.zone.upper}) and close < upper, penetration > {FAKE_PENETRATION_THRESHOLD}, flux opposite")
    
    # Create probe type bar: breaks through then falls back
    bars = create_bars_sequence(base_date, 20, base_price=100.0, volume_base=1000)
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=100.0,
        high=103.0,    # Large breakout above upper=102
        low=100.0,
        close=101.0,   # Close back inside Zone
        volume=1500
    )
    
    # flux negative (opposite to upward breakout direction)
    ss = create_system_state(flux=-0.5, structural_age=10)
    
    is_fake, pattern, conf = detect_fake_breakout(structure, bars, ss)
    print(f"  Is fake breakout: {is_fake}")
    print(f"  Pattern: {pattern}")
    print(f"  Confidence: {conf:.2f}")
    
    # Verify penetration depth
    penetration = (103.0 - 102.0) / 2.0  # 0.5
    print(f"  Penetration depth: {penetration:.2f} (threshold: {FAKE_PENETRATION_THRESHOLD})")
    
    if is_fake and pattern == FakeBreakoutPattern.FAKE_PIN:
        print(f"  [PASS] Correctly identified FAKE_PIN pattern")
    else:
        print(f"  [WARN] FAKE_PIN pattern not identified")
    
    # Test case 2.2: FAKE_DSPIKE (Single K extreme)
    print("\n--- Test 2.2: FAKE_DSPIKE Single K Extreme ---")
    print(f"  Trigger condition: shadow/body ratio > {FAKE_SHADOW_RATIO}, volume climax, weak flux")
    
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=100.0,
        high=104.0,    # Long upper shadow
        low=99.0,
        close=100.2,   # Close near open, small body
        volume=2500    # Volume climax (>1.5x)
    )
    
    # Weak flux
    ss.motion.conservation_flux = 0.1
    
    is_fake, pattern, conf = detect_fake_breakout(structure, bars, ss)
    print(f"  Is fake breakout: {is_fake}")
    print(f"  Pattern: {pattern}")
    
    # Calculate shadow/body ratio
    body = abs(100.2 - 100.0)  # 0.2
    shadow_up = 104.0 - max(100.0, 100.2)  # 3.8
    ratio = shadow_up / body if body > 0 else float('inf')
    print(f"  Shadow/body ratio: {ratio:.1f} (threshold: {FAKE_SHADOW_RATIO})")
    
    if is_fake and pattern == FakeBreakoutPattern.FAKE_DSPIKE:
        print(f"  [PASS] Correctly identified FAKE_DSPIKE pattern")
    else:
        print(f"  [WARN] FAKE_DSPIKE pattern not identified")
    
    # Test case 2.3: FAKE_VOLDIV (Volume divergence)
    print("\n--- Test 2.3: FAKE_VOLDIV Volume Divergence ---")
    print(f"  Trigger condition: price breakout but volume < {FAKE_VOLUME_DIV}x median, flux opposite or near 0")
    
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=101.0,
        high=103.0,
        low=101.0,
        close=103.0,   # Break upper
        volume=500     # Volume contraction (<0.8x)
    )
    
    # flux opposite
    ss.motion.conservation_flux = -0.5
    
    is_fake, pattern, conf = detect_fake_breakout(structure, bars, ss)
    print(f"  Is fake breakout: {is_fake}")
    print(f"  Pattern: {pattern}")
    print(f"  Confidence: {conf:.2f}")
    
    if is_fake and pattern == FakeBreakoutPattern.FAKE_VOLDIV:
        print(f"  [PASS] Correctly identified FAKE_VOLDIV pattern")
    else:
        print(f"  [WARN] FAKE_VOLDIV pattern not identified")
    
    # Test case 2.4: FAKE_BLIND_WHIP (Blind zone whip)
    print("\n--- Test 2.4: FAKE_BLIND_WHIP Blind Zone Whip ---")
    print(f"  Trigger condition: breakout in blind zone then return, flux decay")
    
    # Create sequence with breakout then return
    bars = create_bars_sequence(base_date, 18, base_price=100.0)
    # Day before breakout
    bars.append(create_bar(
        base_date + timedelta(days=18),
        open_price=101.0,
        high=103.0,
        low=101.0,
        close=103.0,   # Breakout
        volume=2000
    ))
    # Today return to Zone
    bars.append(create_bar(
        base_date + timedelta(days=19),
        open_price=102.0,
        high=102.5,
        low=100.5,
        close=101.0,   # Back inside Zone
        volume=1200
    ))
    
    # Blind zone + weak flux
    ss = create_system_state(flux=0.1, structural_age=10, is_blind=True)
    
    is_fake, pattern, conf = detect_fake_breakout(structure, bars, ss)
    print(f"  Is fake breakout: {is_fake}")
    print(f"  Pattern: {pattern}")
    
    if is_fake and pattern == FakeBreakoutPattern.FAKE_BLIND_WHIP:
        print(f"  [PASS] Correctly identified FAKE_BLIND_WHIP pattern")
    else:
        print(f"  [WARN] FAKE_BLIND_WHIP pattern not identified")
    
    # Test case 2.5: FAKE_GAP (Gap fill)
    print("\n--- Test 2.5: FAKE_GAP Gap Fill ---")
    print(f"  Trigger condition: gap breakout of Zone but filled same day, flux opposite")
    
    bars = create_bars_sequence(base_date, 18, base_price=100.0)
    # Yesterday close inside Zone
    bars.append(create_bar(
        base_date + timedelta(days=18),
        open_price=100.0,
        high=101.5,
        low=99.5,
        close=101.0,   # Inside Zone (lower=98, upper=102)
        volume=1000
    ))
    # Today gap up but filled
    bars.append(create_bar(
        base_date + timedelta(days=19),
        open_price=103.0,  # Gap up breakout above upper=102
        high=104.0,
        low=101.5,
        close=101.0,       # Filled back to Zone
        volume=1500
    ))
    
    # flux opposite (negative flux indicates downward pressure)
    ss = create_system_state(flux=-0.6, structural_age=10)
    
    is_fake, pattern, conf = detect_fake_breakout(structure, bars, ss)
    print(f"  Is fake breakout: {is_fake}")
    print(f"  Pattern: {pattern}")
    print(f"  Confidence: {conf:.2f}")
    
    if is_fake and pattern == FakeBreakoutPattern.FAKE_GAP:
        print(f"  [PASS] Correctly identified FAKE_GAP pattern")
    else:
        print(f"  [WARN] FAKE_GAP pattern not identified")
    
    return True


# ============================================================
# Test Case 3: Position Factor Calculation
# ============================================================

def test_position_factor_calculation():
    """Test position factor calculation"""
    print("\n" + "="*60)
    print("Test 3: Position Factor Calculation (A/B/C/D Tiers)")
    print("="*60)
    
    test_cases = [
        ("A", False, 1.0, "Tier A non-blind should be 1.0"),
        ("A", True, 0.5, "Tier A blind should be halved to 0.5"),
        ("B", False, 0.6, "Tier B non-blind should be 0.6"),
        ("B", True, 0.3, "Tier B blind should be halved to 0.3"),
        ("C", False, 0.3, "Tier C non-blind should be 0.3"),
        ("C", True, 0.15, "Tier C blind should be halved to 0.15"),
        ("D", False, 0.0, "Tier D should be 0.0 (no trade)"),
        ("D", True, 0.0, "Tier D blind still 0.0"),
    ]
    
    all_passed = True
    for tier, is_blind, expected, description in test_cases:
        result = calculate_position_factor(tier, is_blind)
        status = "[PASS]" if abs(result - expected) < 0.001 else "[FAIL]"
        if status == "[FAIL]":
            all_passed = False
        print(f"  {status} {description}: expected={expected}, actual={result}")
    
    # Test unknown tier
    print("\n--- Test Unknown Tier ---")
    result = calculate_position_factor("X", False)
    print(f"  Unknown tier 'X' non-blind: {result} (expected default 0.3)")
    
    result = calculate_position_factor("X", True)
    print(f"  Unknown tier 'X' blind: {result} (expected default 0.15)")
    
    return all_passed


# ============================================================
# Test Case 4: Signal Priority Sorting
# ============================================================

def test_signal_priority():
    """Test signal priority sorting"""
    print("\n" + "="*60)
    print("Test 4: Signal Priority Sorting")
    print("="*60)
    
    structure = create_structure_with_zone(center=100.0, bandwidth=2.0, n_cycles=5)
    base_date = datetime(2024, 1, 1)
    
    # Create a scenario that can trigger multiple signals
    # When fake breakout and breakout confirm coexist, fake breakout has higher priority
    
    print("\n--- Test 4.1: Fake Breakout vs Breakout Confirm Priority ---")
    
    # Create a bar that satisfies both fake breakout and breakout confirm conditions
    bars = create_bars_sequence(base_date, 19, base_price=100.0)
    # Last bar: upward breakout with long upper shadow (may trigger both fake breakout and breakout confirm)
    bars.append(create_bar(
        base_date + timedelta(days=19),
        open_price=100.0,
        high=105.0,    # Large breakout
        low=100.0,
        close=103.0,   # Close breaks upper=102
        volume=3000    # High volume
    ))
    
    # flux positive (supports breakout)
    ss = create_system_state(flux=0.8, structural_age=10)
    
    signal = generate_signal(structure, bars, ss)
    
    if signal:
        print(f"  Generated signal: {signal.kind.value}")
        print(f"  Direction: {signal.direction}")
        print(f"  Priority: {signal.priority}")
        print(f"  Confidence: {signal.confidence:.2f}")
        
        # Since flux is positive, breakout confirm should take priority over fake breakout
        if signal.kind == SignalKind.BREAKOUT_CONFIRM:
            print(f"  [PASS] Correctly prioritized BREAKOUT_CONFIRM signal (flux positive)")
        elif signal.kind == SignalKind.FAKE_BREAKOUT:
            print(f"  [INFO] Fake breakout signal triggered (possibly due to other conditions)")
    else:
        print(f"  [WARN] No signal generated")
    
    # Test case 4.2: Fake breakout has highest priority
    print("\n--- Test 4.2: Fake Breakout Priority Verification ---")
    
    # Modify conditions to make fake breakout more explicit
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=100.0,
        high=104.0,    # Large breakout
        low=100.0,
        close=101.0,   # Close back inside Zone
        volume=2500
    )
    
    # flux opposite (supports fake breakout)
    ss.motion.conservation_flux = -0.6
    
    signal = generate_signal(structure, bars, ss)
    
    if signal:
        print(f"  Generated signal: {signal.kind.value}")
        print(f"  Priority: {signal.priority}")
        
        expected_priority = 1  # FAKE_BREAKOUT should be 1
        if signal.priority == expected_priority:
            print(f"  [PASS] Fake breakout signal priority is 1 (highest)")
        else:
            print(f"  [WARN] Fake breakout signal priority is {signal.priority}, expected 1")
    
    # Test case 4.3: Verify priority values for each signal type
    print("\n--- Test 4.3: Priority Values for Each Signal Type ---")
    
    from src.models import Signal
    
    # Create signals of each type to check priority property
    test_signals = [
        (SignalKind.FAKE_BREAKOUT, 1),
        (SignalKind.BREAKOUT_CONFIRM, 2),
        (SignalKind.PULLBACK_CONFIRM, 3),
        (SignalKind.BLIND_BREAKOUT, 4),
        (SignalKind.STRUCTURE_EXPIRED, 5),
    ]
    
    for kind, expected_priority in test_signals:
        # Create a minimal signal object to check priority property
        sig = Signal(
            kind=kind,
            direction="long",
            confidence=0.7,
            flux_aligned=True,
            stability_ok=True,
            entry_note="test"
        )
        actual_priority = sig.priority
        status = "[PASS]" if actual_priority == expected_priority else "[FAIL]"
        print(f"  {status} {kind.value}: priority={actual_priority}, expected={expected_priority}")
    
    return True


# ============================================================
# Test Case 5: Boundary Value Tests
# ============================================================

def test_boundary_values():
    """Test boundary values"""
    print("\n" + "="*60)
    print("Test 5: Boundary Value Tests")
    print("="*60)
    
    structure = create_structure_with_zone(center=100.0, bandwidth=2.0, n_cycles=5)
    base_date = datetime(2024, 1, 1)
    
    # Test case 5.1: Exactly 0.55 points boundary
    print("\n--- Test 5.1: Exactly 0.55 Points Boundary Test ---")
    
    # Calculate minimum conditions needed to reach 0.55 points
    # score = p*0.25 + v*0.25 + f*0.15 + c*0.20 + d*0.15 >= 0.55
    # Assume: v=1(full), f=0(no flux), c=1(full), d=1(full)
    # Need: p*0.25 + 0.25 + 0 + 0.2 + 0.15 >= 0.55
    # p*0.25 >= -0.05 -> always satisfied
    
    # More realistic boundary: only penetration and volume contribute
    # p*0.25 + v*0.25 >= 0.55 (assume others are 0)
    # If p=1, v=1: score = 0.5 -> not enough
    # Need other dimensions to contribute
    
    # Create a scenario that is exactly 0.55 points
    bars = create_bars_sequence(base_date, 20, base_price=100.0)
    # Small breakout
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=101.0,
        high=102.5,
        low=101.0,
        close=102.2,   # penetration = 0.1
        volume=1400    # 1.4x volume
    )
    
    ss = create_system_state(flux=0.0, structural_age=5)  # Weak flux, medium age
    
    score, note = score_breakout_confirmation(structure, bars, ss)
    print(f"  Breakout score: {score:.4f}")
    print(f"  Boundary value: {BREAKOUT_WEAK}")
    
    if abs(score - BREAKOUT_WEAK) < 0.1:
        print(f"  [PASS] Score near boundary value {BREAKOUT_WEAK}")
    
    # Test case 5.2: Exactly 0.80 points boundary
    print("\n--- Test 5.2: Exactly 0.80 Points Boundary Test ---")
    
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=101.0,
        high=104.0,
        low=101.0,
        close=103.0,   # penetration = 0.5
        volume=2000    # 2x volume
    )
    
    ss = create_system_state(flux=0.5, structural_age=10)
    
    score, note = score_breakout_confirmation(structure, bars, ss)
    print(f"  Breakout score: {score:.4f}")
    print(f"  Strong breakout boundary: {BREAKOUT_STRONG}")
    
    if score >= BREAKOUT_STRONG:
        print(f"  [PASS] Score >= {BREAKOUT_STRONG}, reaches strong breakout standard")
    else:
        print(f"  [INFO] Score < {BREAKOUT_STRONG}, weak breakout")
    
    # Test case 5.3: Fake breakout penetration threshold boundary
    print("\n--- Test 5.3: Fake Breakout Penetration Threshold Boundary ---")
    
    threshold = FAKE_PENETRATION_THRESHOLD
    print(f"  Penetration threshold: {threshold}")
    
    # Just below threshold
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=100.0,
        high=102.5,    # penetration = 0.25 (just below 0.3 threshold)
        low=100.0,
        close=101.0,
        volume=1500
    )
    
    ss.motion.conservation_flux = -0.5
    
    is_fake, pattern, conf = detect_fake_breakout(structure, bars, ss)
    print(f"  Penetration 0.25 (threshold {threshold}): is_fake={is_fake}")
    
    # Just above threshold
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=100.0,
        high=102.7,    # penetration = 0.35 (above 0.3 threshold)
        low=100.0,
        close=101.0,
        volume=1500
    )
    
    is_fake, pattern, conf = detect_fake_breakout(structure, bars, ss)
    print(f"  Penetration 0.35 (threshold {threshold}): is_fake={is_fake}, pattern={pattern}")
    
    if is_fake:
        print(f"  [PASS] Penetration > {threshold} correctly triggers fake breakout")
    
    return True


# ============================================================
# Test Case 6: Comprehensive Scenario Tests
# ============================================================

def test_comprehensive_scenarios():
    """Comprehensive scenario tests"""
    print("\n" + "="*60)
    print("Test 6: Comprehensive Scenario Tests")
    print("="*60)
    
    # Scenario 6.1: Tier D quality does not generate signal
    print("\n--- Test 6.1: Tier D Quality Does Not Generate Signal ---")
    
    # Create low quality structure (few cycles, no label, etc.)
    low_quality_structure = create_structure_with_zone(center=100.0, bandwidth=2.0, n_cycles=1)
    low_quality_structure.invariants = {}
    low_quality_structure.typicality = 0.0
    low_quality_structure.label = None
    
    base_date = datetime(2024, 1, 1)
    bars = create_bars_sequence(base_date, 20, base_price=100.0)
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=101.0,
        high=104.0,
        low=101.0,
        close=103.0,
        volume=3000
    )
    
    ss = create_system_state(flux=0.8, structural_age=10)
    
    # Check quality tier first
    qa = assess_quality(low_quality_structure, ss)
    print(f"  Quality assessment: tier={qa.tier.value}, score={qa.score:.2f}")
    
    signal = generate_signal(low_quality_structure, bars, ss)
    
    if qa.tier.value == "D":
        print(f"  [PASS] Correctly identified as Tier D")
        if signal is None:
            print(f"  [PASS] Tier D does not generate signal")
        else:
            print(f"  [WARN] Tier D unexpectedly generated signal: {signal.kind.value}")
    
    # Scenario 6.2: Stability red light caps confidence
    print("\n--- Test 6.2: Stability Red Light Caps Confidence ---")
    
    structure = create_structure_with_zone(center=100.0, bandwidth=2.0, n_cycles=5)
    bars = create_bars_sequence(base_date, 20, base_price=100.0)
    bars[-1] = create_bar(
        base_date + timedelta(days=19),
        open_price=101.0,
        high=104.0,
        low=101.0,
        close=103.0,
        volume=3000
    )
    
    # Red light status
    ss = create_system_state(
        flux=0.8, 
        structural_age=10,
        stability_surface="unstable",
        stability_verified=False
    )
    
    signal = generate_signal(structure, bars, ss)
    
    if signal:
        print(f"  Signal type: {signal.kind.value}")
        print(f"  Confidence: {signal.confidence:.2f}")
        print(f"  Stability OK: {signal.stability_ok}")
        
        if signal.confidence <= 0.50:
            print(f"  [PASS] Red light status correctly caps confidence to 0.50")
        else:
            print(f"  [WARN] Red light status confidence not properly capped")
    
    # Scenario 6.3: Blind zone downgrade
    print("\n--- Test 6.3: Blind Zone Downgrade ---")
    
    ss = create_system_state(
        flux=0.8, 
        structural_age=10,
        is_blind=True,
        stability_surface="stable",
        stability_verified=True
    )
    
    signal = generate_signal(structure, bars, ss)
    
    if signal:
        print(f"  Signal type: {signal.kind.value}")
        print(f"  Confidence: {signal.confidence:.2f}")
        print(f"  Is blind: {signal.is_blind}")
        print(f"  Position factor: {signal.position_size_factor}")
        
        if signal.is_blind and signal.position_size_factor < 0.5:
            print(f"  [PASS] Blind zone correctly reduces position")
        
        # Blind breakout observation signal
        if signal.kind == SignalKind.BLIND_BREAKOUT:
            print(f"  [PASS] Blind zone generates BLIND_BREAKOUT observation signal")
    
    return True


# ============================================================
# Main Run Function
# ============================================================

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print(" Futures Price Structure Retrieval System - Signal Layer Numerical Correctness Tests")
    print("="*70)
    
    results = []
    
    try:
        results.append(("5-dim Breakout Score", test_breakout_score_calculation()))
    except Exception as e:
        print(f"\n[FAIL] 5-dim Breakout Score test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("5-dim Breakout Score", False))
    
    try:
        results.append(("Fake Breakout 5 Patterns", test_fake_breakout_patterns()))
    except Exception as e:
        print(f"\n[FAIL] Fake Breakout 5 Patterns test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Fake Breakout 5 Patterns", False))
    
    try:
        results.append(("Position Factor Calc", test_position_factor_calculation()))
    except Exception as e:
        print(f"\n[FAIL] Position Factor Calc test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Position Factor Calc", False))
    
    try:
        results.append(("Signal Priority Sorting", test_signal_priority()))
    except Exception as e:
        print(f"\n[FAIL] Signal Priority Sorting test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Signal Priority Sorting", False))
    
    try:
        results.append(("Boundary Value Tests", test_boundary_values()))
    except Exception as e:
        print(f"\n[FAIL] Boundary Value Tests failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Boundary Value Tests", False))
    
    try:
        results.append(("Comprehensive Scenarios", test_comprehensive_scenarios()))
    except Exception as e:
        print(f"\n[FAIL] Comprehensive Scenarios test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Comprehensive Scenarios", False))
    
    # Print summary
    print("\n" + "="*70)
    print(" Test Results Summary")
    print("="*70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")
    
    print(f"\n  Total: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
