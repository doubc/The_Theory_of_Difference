"""P1-B fix: improve CIV stability computation in hierarchical_evolver.py"""
import os
import re

fp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  'engine', 'hierarchical_evolver.py')

with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Replace CIV stability computation (interval-only -> combined interval + density)
# Find the block by matching unique code patterns
old_civ = re.search(
    r'(                # P1: Track CIV layer stability.*?else:\n                    self\._civ_step_history = \[\])',
    content, re.DOTALL
)
if not old_civ:
    print('ERROR: Could not find CIV stability block')
    exit(1)

new_civ_text = '''                # P1-B: CIV layer stability = combined interval CV + event density
                civ_stability = 0.0
                if not hasattr(self, '_civ_step_history'):
                    self._civ_step_history = []
                if len(self._civ_step_history) >= 1:
                    recent = self._civ_step_history[-20:]
                    # Interval stability: CV-based
                    interval_stability = 0.0
                    if len(recent) >= 3:
                        intervals = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
                        mean_int = sum(intervals) / len(intervals)
                        if mean_int > 0:
                            std_int = (sum((x - mean_int)**2 for x in intervals) / len(intervals)) ** 0.5
                            cv = std_int / mean_int
                            interval_stability = max(0.0, min(1.0, 1.0 - cv))
                        else:
                            interval_stability = 1.0
                    elif len(recent) >= 1:
                        interval_stability = 0.3
                    # Density stability: event count-based (20+ events -> full)
                    density_stability = min(1.0, len(recent) / 20.0)
                    # Combined: 60% interval + 40% density
                    civ_stability = 0.6 * interval_stability + 0.4 * density_stability'''

content = content[:old_civ.start()] + new_civ_text + content[old_civ.end():]

# Fix 2: Add ILP fallback for INSTITUTIONAL stability
old_inst_pattern = re.search(
    r"(                        # P1: Use CIV event-based stability for CIVILIZATION layer\n                        if hl == 'CIVILIZATION' and civ_stability > 0:\n                            stab = max\(stab, civ_stability\))",
    content
)
if not old_inst_pattern:
    print('ERROR: Could not find INSTITUTIONAL stability block')
    exit(1)

new_inst_text = """                        # P1: Use CIV event-based stability for CIVILIZATION layer
                        if hl == 'CIVILIZATION' and civ_stability > 0:
                            stab = max(stab, civ_stability)
                        # P1-B: For INSTITUTIONAL, use ILP's internal stability as fallback
                        if hl == 'INSTITUTIONAL' and stab < 0.1 and self.institutional_layer_protector is not None:
                            try:
                                ilp_summary = self.institutional_layer_protector.get_summary()
                                ilp_stab = ilp_summary.get('stability_score', 0.0)
                                if ilp_stab > stab:
                                    stab = ilp_stab
                            except Exception:
                                pass"""

content = content[:old_inst_pattern.start()] + new_inst_text + content[old_inst_pattern.end():]

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)
print('OK: CIV stability computation improved for P1-B')
