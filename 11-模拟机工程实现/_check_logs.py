import os, sys

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

d = r'C:\Users\Administrator\source\repos\doubc\The_Theory_of_Difference\11-模拟机工程实现\experiments'
for f in sorted(os.listdir(d)):
    if f.startswith('exp_') and f.endswith('.py'):
        try:
            with open(os.path.join(d, f), encoding='utf-8') as fh:
                content = fh.read()
            if 'ExperimentLogger' in content:
                print(f'{f}: LOGGED')
            else:
                print(f'{f}: NO_LOG')
        except Exception as e:
            print(f'{f}: ERROR - {e}')