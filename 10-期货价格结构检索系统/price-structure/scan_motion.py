with open('src/retrieval/active_match.py', encoding='utf-8') as f:
    lines = f.readlines()
for i, l in enumerate(lines):
    if 'compute_motion' in l or 'movement_type' in l:
        print(f'{i+1}: {l.rstrip()}')

print('---')
# Also check the scan pipeline
with open('scripts/daily_scan.py', encoding='utf-8') as f:
    scan_lines = f.readlines()
for i, l in enumerate(scan_lines):
    if 'movement_type' in l or 'compute_motion' in l:
        print(f'daily_scan.py:{i+1}: {l.rstrip()}')