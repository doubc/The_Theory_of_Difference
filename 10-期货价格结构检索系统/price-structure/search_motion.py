import re

with open('src/relations.py', encoding='utf-8') as f:
    lines = f.readlines()

keywords = ['movement_type', 'NearestStableState', 'compute_motion', 'stable_transition', 'MarketMovementType']
for i, l in enumerate(lines):
    if any(k in l for k in keywords):
        print(f'{i+1}: {l.rstrip()}')

matches = [l for l in lines if any(k in l for k in keywords)]
print(f'\nTotal: {len(matches)} matches')

# Also search in models.py for compute_motion
with open('src/models.py', encoding='utf-8') as f:
    model_lines = f.readlines()
for i, l in enumerate(model_lines):
    if any(k in l for k in keywords):
        print(f'models.py:{i+1}: {l.rstrip()}')