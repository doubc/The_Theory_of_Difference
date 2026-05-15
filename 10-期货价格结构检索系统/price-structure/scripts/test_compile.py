import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['MYSQL_PASSWORD'] = ''

from src.data.loader import MySQLLoader
from src.compiler.pipeline import compile_full, CompilerConfig

loader = MySQLLoader(host='localhost', user='root', password='', db='sina_futures')

# 测试铜
bars = loader.get(symbol='cu0', freq='1d')
print(f'cu0 bars: {len(bars)}')
if bars:
    config = CompilerConfig(min_amplitude=0.02, min_duration=3, zone_bandwidth=0.01)
    result = compile_full(bars, config)
    print(f'structures: {len(result.structures) if result.structures else 0}')
    if result.structures:
        s = result.structures[-1]
        print(f'last structure t_end: {s.t_end}')
        inv = s.invariants or {}
        print(f'invariants: {inv}')
        # 检查结构数据
        print(f'bars[-1]: date={bars[-1].timestamp}, close={bars[-1].close}')sina_futures