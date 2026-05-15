import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.compiler.pipeline import compile_full, CompilerConfig
from src.data.loader import MySQLLoader
from src.retrieval.opportunity import aggregate_opportunity
from src.relations import compute_motion

password = os.getenv('MYSQL_PASSWORD', '')
loader = MySQLLoader(host="localhost", user="root", password=password, db="sina_futures")
config = CompilerConfig(min_amplitude=0.02, min_duration=3, zone_bandwidth=0.01)

bars = loader.get(symbol="hc0", freq="1d")
result = compile_full(bars, config)
st = result.structures[-1]
st.motion = compute_motion(st)

print("Structure motion movement_type:", st.motion.movement_type.value)

# Simulate what daily_scan does
from src.retrieval.opportunity import TemplateMatch

bars2 = loader.get(symbol="hc0", freq="1d")
current_price = bars2[-1].close
confirmed_at = str(bars2[-1].timestamp)
current_inv = st.invariants or {}

evidence = {"config_hash": "test", "data_cutoff": "2026-04-25",
            "template_pool_size": 237, "scan_window_years": 3, "top_k": 5}
tmpl = TemplateMatch(symbol="test", symbol_name="test", end_date="2026-04-20",
    outcome_start="2026-04-21", direction="up", up_move=0.05, down_move=-0.03,
    days_to_peak=10, days_to_trough=5, bundle_id="b1", diff_detail={},
    distance=0.5, similarity=0.67)

opp = aggregate_opportunity("hc0", "热卷连续", round(current_price, 2),
    str(confirmed_at), current_inv, [tmpl], evidence)

print("Opportunity fields:", [f for f in dir(opp) if not f.startswith('_')])
print("movement_type attr:", getattr(opp, 'movement_type', 'MISSING'))
print("to_dict keys:", list(opp.to_dict().keys()))
d = opp.to_dict()
print("movement_type in dict:", d.get('movement_type', 'MISSING'))