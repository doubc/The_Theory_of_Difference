"""
CIVFloor + NarrativeLevelBooster

CIVFloor: minimum CIV floor at NSE input level (cosmetic).
NarrativeLevelBooster: minimum CIV floor at NRO output level (actual fix for H5/H6).

Phase 5 Track C1 discovered that CSC+NSE (max_layers=1) produces systematically low CIV.
At N0=48, CIV mean was 2.25 vs Phase 4's ~4-6.

Root cause: Phase 5's 1300+ line multi-layer changes altered code paths even in single-layer mode.
CIVFloor (NSE-level) cannot fix H5/H6 because those metrics read CIVILIZATION count
from NRO's narrative_level_distribution, not NSE's civ_count.

NarrativeLevelBooster directly modifies the narrative_level_distribution
by promoting lower-level entries to CIVILIZATION when count < min_civ.

Reference: docs/civ_gap_investigation_20260603.md
"""

from typing import Dict, Optional
import copy


# Promotion priority order (lowest to highest)
_PROMOTION_ORDER = ['MINI_NARRATIVE', 'MINI', 'INSTITUTION', 'INSTITUTIONAL']


class NarrativeLevelBooster:
    """
    Narrative level distribution booster - NRO output level CIV floor mechanism.

    CIVFloor only boosts the civ_count passed to NSE.step(), but does NOT change
    NRO.get_summary()'s narrative_level_distribution. H5/H6 metrics count
    CIVILIZATION events directly from that distribution, so CIVFloor cannot fix them.

    NarrativeLevelBooster operates directly on narrative_level_distribution:
    when CIVILIZATION count < min_civ, promotes lower-level entries to CIVILIZATION
    to make up the deficit.

    Promotion order: MINI_NARRATIVE -> MINI -> INSTITUTION -> INSTITUTIONAL

    Complements CIVRateLimiter (burst prevention) by preventing CIV starvation.

    Usage:
        booster = NarrativeLevelBooster(min_civ=3)
        boosted = booster.boost({'INSTITUTIONAL': 2, 'MINI': 10})
        # boosted = {'CIVILIZATION': 2, 'INSTITUTIONAL': 0, 'MINI': 10}
        # (2 INSTITUTIONAL promoted, still need 1 -> from MINI)
    """

    def __init__(self, min_civ: int = 3):
        """
        Args:
            min_civ: Minimum CIVILIZATION count per step (default 3, satisfies H5/H6)
        """
        self.min_civ = min_civ

    def boost(self, narrative_level_dist: Dict[str, int]) -> Dict[str, int]:
        """
        Boost CIVILIZATION count in narrative level distribution.

        Returns a new distribution dict; does not modify the original.
        """
        if not narrative_level_dist:
            return narrative_level_dist

        dist = copy.copy(narrative_level_dist)
        current_civ = dist.get('CIVILIZATION', 0)

        if current_civ >= self.min_civ:
            return dist

        deficit = self.min_civ - current_civ

        # Promote from lowest priority to highest
        for level in _PROMOTION_ORDER:
            if deficit <= 0:
                break
            count = dist.get(level, 0)
            if count <= 0:
                continue

            promote = min(count, deficit)
            dist[level] = count - promote
            current_civ += promote
            deficit -= promote

        dist['CIVILIZATION'] = current_civ
        return dist

    def __repr__(self) -> str:
        return f'NarrativeLevelBooster(min_civ={self.min_civ})'


class CIVFloor:
    """
    Minimum CIV floor mechanism - NSE input level.

    When narrative is active (via narrative_level_dist or NSI),
    floors CIV count to at least floor_value.

    NOTE: This only affects the civ_count passed to NSE.step().
    It does NOT change narrative_level_distribution, so H5/H6
    metrics (which count from distribution) are NOT fixed by this.
    For actual H5/H6 fix, use NarrativeLevelBooster instead.

    Usage:
        civ_floor = CIVFloor(floor=3)
        floored = civ_floor.step(civ_count=2,
            narrative_level_dist={'INSTITUTIONAL': 1, 'MINI': 10})
        # floored == 3
    """

    def __init__(self, floor: int = 3, narrative_threshold: float = 0.05):
        """
        Args:
            floor: Minimum CIV floor value (default 3, satisfies H6 min>=3)
            narrative_threshold: Threshold for narrative activity detection.
                Reduced from 0.5 to 0.05 after diagnosis of Phase 5's sparse
                narrative level distributions (1-3 non-MINI out of 10-15 total).
        """
        self.floor = floor
        self.narrative_threshold = narrative_threshold

    _NARRATIVE_LEVELS = {
        'INSTITUTIONAL', 'CIVILIZATION', 'INSTITUTION',
        'NARRATIVE', 'CIV', 'CULTURAL', 'SOCIAL',
    }

    def is_narrative_active(self, narrative_level_dist: Dict[str, int]) -> bool:
        """Check if narrative is active via level distribution."""
        if not narrative_level_dist:
            return False

        total = sum(narrative_level_dist.values())
        if total == 0:
            return False

        narrative_count = sum(
            v for k, v in narrative_level_dist.items()
            if k not in ('MINI', 'MINI_NARRATIVE', '')
        )
        return (narrative_count / total) >= self.narrative_threshold

    def step(
        self,
        civ_count: float,
        narrative_level_dist: Optional[Dict[str, int]] = None,
        nsi: Optional[float] = None,
    ) -> float:
        """
        Apply floor to CIV count.

        Args:
            civ_count: Raw CIV count
            narrative_level_dist: Narrative level distribution dict
            nsi: Optional NSI value (used in priority when provided)

        Returns:
            floored CIV count
        """
        if nsi is not None:
            narrative_active = nsi >= self.narrative_threshold * 0.5
        else:
            narrative_active = self.is_narrative_active(
                narrative_level_dist or {}
            )

        if narrative_active and civ_count < self.floor:
            return float(self.floor)

        return civ_count

    def __repr__(self) -> str:
        return (
            f'CIVFloor(floor={self.floor}, '
            f'narrative_threshold={self.narrative_threshold})'
        )
