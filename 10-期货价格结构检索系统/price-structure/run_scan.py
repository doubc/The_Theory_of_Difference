"""Daily scan wrapper"""
import subprocess, sys, os
os.chdir(r'C:\Users\Administrator\Documents\the_theory_of_difference\10-期货价格结构检索系统\price-structure')
result = subprocess.run([sys.executable, 'scripts/daily_scan.py'], capture_output=True, text=True)
print(result.stdout[-6000:] if len(result.stdout) > 6000 else result.stdout)
print(result.stderr[-2000:] if result.stderr else '')
print('Exit code:', result.returncode)