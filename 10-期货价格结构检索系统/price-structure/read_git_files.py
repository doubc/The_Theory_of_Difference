import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')

files = ['全结构检索流程优化.md', '关于模板的改进.md']
for fname in files:
    r = subprocess.run(['git', 'show', f'HEAD:{fname}'], capture_output=True)
    if r.returncode == 0:
        print(f'\n{"="*60}')
        print(f'  {fname}')
        print(f'{"="*60}')
        print(r.stdout.decode('utf-8', errors='replace'))
    else:
        print(f'\nFAILED: {fname}')
        print(r.stderr.decode('utf-8', errors='replace'))