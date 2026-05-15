import os, re

def grep_files(root, pattern, files=None):
    results = []
    for f in files or []:
        if not f.endswith('.py'): continue
        path = os.path.join(root, f)
        try:
            with open(path, encoding='utf-8') as fh:
                for i, l in enumerate(fh):
                    if pattern in l:
                        results.append(f'{f}:{i+1}: {l.rstrip()}')
        except:
            pass
    return results

root = 'scripts'
print('=== scripts/*.py ===')
for f in os.listdir(root):
    r = grep_files(root, 'build_system_state', [f])
    for x in r: print(x)
for f in os.listdir(root):
    r = grep_files(root, 'compute_motion', [f])
    for x in r: print(x)

print('=== src/*.py ===')
for f in os.listdir('src'):
    r = grep_files('src', 'build_system_state', [f])
    for x in r: print(x)
for f in os.listdir('src'):
    r = grep_files('src', 'compute_motion', [f])
    for x in r: print(x)