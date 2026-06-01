"""P1-B fix: moderate non-triviality factor in InstitutionalNarrativeStabilizer"""
import os
import re

fp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  'engine', 'narrative_self_emergence.py')

with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the _compute_non_triviality method and replace it entirely
# Match from "def _compute_non_triviality(self):" to the next method or end of class
pattern = r'(    def _compute_non_triviality\(self\) -> float:.*?)(    def |class |\Z)'
match = re.search(pattern, content, re.DOTALL)
if not match:
    print('ERROR: Could not find _compute_non_triviality method')
    sys.exit(1)

old_method = match.group(1)

new_method = '''    def _compute_non_triviality(self) -> float:
        """Calculate non-triviality factor [0, 1]

        Measures the rate of narrative label change in the window.
        - Static convergence: moderate value (~0.6)
        - Changing with coherence: high value (1.0)
        - Fragmented (too much change): moderate value (~0.5)

        Non-triviality = changing but coherent = true stability

        P1-B adjustment (exp_102 feedback):
        - Raised floor from 0.4 to 0.6 to prevent over-penalizing stability
        - exp_102 found: aggressive non-triviality (floor 0.2-0.4) caused stability
          to drop from 0.94 to 0.48, weakening CIVRateLimiter control, leading to
          CIV=194 explosion in seed 742
        """
        if len(self._narrative_history) < 10:
            return 0.7  # neutral-high when insufficient data

        history_list = list(self._narrative_history)
        n = len(history_list)

        change_count = 0
        for i in range(1, n):
            if history_list[i]['narrative'] != history_list[i - 1]['narrative']:
                change_count += 1

        change_rate = change_count / (n - 1)

        # P1-B: gentler non-triviality curve
        # Ideal change rate: 5-25% of steps have label changes
        if change_rate == 0.0:
            return 0.6  # P1-B: was 0.4
        elif 0.05 <= change_rate <= 0.25:  # P1-B: upper bound 0.20 -> 0.25
            return 1.0
        elif change_rate < 0.05:
            return 0.6 + (change_rate / 0.05) * 0.4  # 0.6 -> 1.0
        elif change_rate <= 0.40:  # P1-B: transition zone widened
            return 1.0 - ((change_rate - 0.25) / 0.15) * 0.3  # 1.0 -> 0.7
        else:
            return max(0.5, 0.7 - ((change_rate - 0.40) / 0.60) * 0.2)  # P1-B: floor 0.5

'''

content = content.replace(old_method, new_method)
with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)
print('OK: non-triviality factor moderated for P1-B')
