import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.compiler.pipeline import compile_full, CompilerConfig
from src.data.loader import MySQLLoader
from src.relations import compute_motion

password = os.getenv('MYSQL_PASSWORD', '')
loader = MySQLLoader(host="localhost", user="root", password=password, db="sina_futures")
config = CompilerConfig(min_amplitude=0.02, min_duration=3, zone_bandwidth=0.01)

for sym in ['hc0', 'ni0', 'ag0', 'sn0', 'rm0']:
    bars = loader.get(symbol=sym, freq="1d")
    result = compile_full(bars, config)
    if not result.structures:
        continue
    st = result.structures[-1]
    # 强制覆盖motion
    st.motion = compute_motion(st)
    m = st.motion
    print(f"{sym:6s}  movement_type={m.movement_type.value:15s}  tendency={m.phase_tendency:15s}  flux={m.conservation_flux:+.2f}")