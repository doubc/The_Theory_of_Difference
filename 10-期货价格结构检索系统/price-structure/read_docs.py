import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')

REPO = r'C:\Users\Administrator\Documents\the_theory_of_difference\10-期货价格结构检索系统\price-structure'

files = [
    f'{REPO}/docs/全结构检索流程优化.md',
    f'{REPO}/docs/关于模板的改进.md',
]

for fpath in files:
    r = subprocess.run(['git', 'show', f'HEAD:{fpath.replace(REPO, "").lstrip("/").lstrip("\\\\")}'], capture_output=True)
    if r.returncode == 0:
        content = r.stdout.decode('utf-8', errors='replace')
        print(f'\n{"="*70}')
        print(f'  {fpath.split("/")[-1]}')
        print(f'{"="*70}')
        print(content)
    else:
        print(f'FAILED: {fpath}')

# Alternative: list docs dir to see what files are there
r = subprocess.run(['git', 'ls-tree', '-r', '--name-only', 'HEAD', 'docs/'], capture_output=True, text=True)
print('\n=== FILES IN docs/ ===')
for line in r.stdout.splitlines():
    if any(ord(c) > 127 for c in line):
        print(repr(line))