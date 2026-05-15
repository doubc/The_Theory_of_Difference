import subprocess, sys, os
sys.stdout.reconfigure(encoding='utf-8')

paths_to_try = [
    r'C:\Users\Administrator\Documents\the_theory_of_difference',
    r'C:\Users\Administrator\Documents\the_theory_of_difference\The_Theory_of_Difference',
]

repo_root = None
for p in paths_to_try:
    if os.path.exists(os.path.join(p, '.git')):
        repo_root = p
        break

print(f'Repo root: {repo_root}')
if not repo_root:
    sys.exit(1)

# Get log
r = subprocess.run(['git', 'log', '--oneline', '-5'], cwd=repo_root, capture_output=True)
print('LOG:', r.stdout.decode('utf-8', errors='replace'))

# Find files with Chinese chars
r = subprocess.run(['git', 'ls-tree', '-r', '--name-only', 'HEAD'], cwd=repo_root, capture_output=True)
for line in r.stdout.decode('utf-8', errors='replace').splitlines():
    if '.md' in line and any(ord(c) > 127 for c in line):
        print(f'Found: {repr(line)}')
        r2 = subprocess.run(['git', 'show', f'HEAD:{line}'], cwd=repo_root, capture_output=True)
        if r2.returncode == 0:
            content = r2.stdout.decode('utf-8', errors='replace')
            print(f'\n{"="*60}')
            print(f'  {line}')
            print(f'{"="*60}')
            print(content)
            # Save locally
            fname = 'from_git_' + line.replace('/', '_').replace('\\', '_')
            with open(fname, 'w', encoding='utf-8', errors='replace') as f:
                f.write(content)
            print(f'[Saved to {fname}]')
        else:
            print(f'  FAILED: {r2.stderr.decode("utf-8", errors="replace")[:200]}')