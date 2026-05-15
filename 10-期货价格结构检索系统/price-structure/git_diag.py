import subprocess, sys, os, glob
sys.stdout.reconfigure(encoding='utf-8')

REPO = r'C:\Users\Administrator\Documents\the_theory_of_difference\10-期货价格结构检索系统\price-structure'
os.chdir(REPO)

# Check git state
r = subprocess.run(['git', 'log', '--oneline', '-5'], capture_output=True, text=True)
print("=== LOG ===")
print(r.stdout)
r = subprocess.run(['git', 'branch', '-a'], capture_output=True, text=True)
print("=== BRANCHES ===")
print(r.stdout)
r = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True)
print("=== STATUS ===")
print(r.stdout)

# List all files in HEAD
r = subprocess.run(['git', 'ls-tree', '-r', '--name-only', 'HEAD'], capture_output=True, text=True)
print("=== ALL FILES IN HEAD ===")
print(r.stdout)

# Try to find the .md files with Chinese chars
for line in r.stdout.splitlines():
    if line.endswith('.md') and any(ord(c) > 127 for c in line):
        fname = os.path.basename(line)
        r2 = subprocess.run(['git', 'show', f'HEAD:{line}'], capture_output=True)
        if r2.returncode == 0:
            print(f"\n=== {fname} ===")
            print(r2.stdout.decode('utf-8', errors='replace'))
            # Write to local file
            local_name = f"from_git_{line.replace('/', '_').replace('\\', '_')}"
            with open(local_name, 'w', encoding='utf-8', errors='replace') as f:
                f.write(r2.stdout.decode('utf-8', errors='replace'))
            print(f"  (saved to {local_name})")
        else:
            print(f"FAILED: {line} -> {r2.stderr.decode('utf-8', errors='replace')}")