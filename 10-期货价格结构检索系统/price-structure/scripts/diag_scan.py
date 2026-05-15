"""诊断扫描，找出为何结构识别为 0"""
import os, sys, math, json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['MYSQL_PASSWORD'] = ''

from src.data.loader import MySQLLoader
from src.data.symbol_meta import symbol_name
from src.compiler.pipeline import compile_full, CompilerConfig
from src.retrieval.opportunity import TemplateMatch, aggregate_opportunity, FEATURE_SCALES, FEATURES
from sqlalchemy import create_engine, inspect

MAX_DIST_THRESHOLD = 1.5
TOP_K = 5
SCAN_WINDOW_YEARS = 3

def _distance(inv1, inv2):
    diff, sq = {}, 0.0
    for f in FEATURES:
        scale = FEATURE_SCALES[f]
        v1 = (inv1.get(f) or 0) / scale
        v2 = (inv2.get(f) or 0) / scale
        d = abs(v1 - v2)
        diff[f] = round(d, 3)
        sq += d ** 2
    return math.sqrt(sq), diff

def _is_active(bars, min_atr_pct=0.005):
    if len(bars) < 20:
        return False, 0
    recent = bars[-20:]
    atrs = []
    for i in range(1, len(recent)):
        b = recent[i]
        prev_close = recent[i-1].close
        tr = max(b.high-b.low, abs(b.high-prev_close), abs(b.low-prev_close))
        atrs.append(tr/prev_close if prev_close > 0 else 0)
    avg_atr = sum(atrs)/len(atrs) if atrs else 0
    return avg_atr >= min_atr_pct, avg_atr

# 加载模板
tmpl_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'library', 'high_potential_templates.jsonl')
active_templates = []
with open(tmpl_path, 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        if datetime.now().year - int(t['end_date'][:4]) <= SCAN_WINDOW_YEARS:
            active_templates.append(t)
print(f'模板库: {len(active_templates)} 条活跃模板')
if active_templates:
    t0 = active_templates[0]
    print(f'模板示例: {t0.get("symbol")} {t0.get("end_date")} invariants={bool(t0.get("invariants"))}')

# 扫描
password = os.getenv('MYSQL_PASSWORD', '')
loader = MySQLLoader(host='localhost', user='root', password=password, db='sina_futures')
config = CompilerConfig(min_amplitude=0.02, min_duration=3, zone_bandwidth=0.01)

pwd_part = f":{password}" if password else ""
engine = create_engine(f"mysql+pymysql://root{pwd_part}@localhost/sina_futures?charset=utf8")
tables = inspect(engine).get_table_names()
symbols = [t for t in tables if not t.endswith('m5') and not t.startswith('test')]
print(f'MySQL 品种: {len(symbols)}')

opportunities = []
no_data, no_active, no_structure, no_match, errors, structures_found = 0, 0, 0, 0, 0, 0

for sym in symbols[:15]:
    try:
        bars = loader.get(symbol=sym, freq='1d')
        if len(bars) < 50:
            no_data += 1
            continue
        
        is_act, avg_atr = _is_active(bars)
        if not is_act:
            no_active += 1
            print(f'  INACT: {sym} ATR={avg_atr:.4f}')
            continue
        
        result = compile_full(bars, config)
        if not result.structures:
            no_structure += 1
            print(f'  NO_STRUCT: {sym} bars={len(bars)}')
            continue
        
        structures_found += 1
        current_st = result.structures[-1]
        current_inv = current_st.invariants or {}
        current_price = bars[-1].close
        confirmed_at = getattr(current_st, 't_end', None) or str(bars[-1].timestamp)
        
        scored = []
        for tmpl in active_templates:
            inv_tmpl = tmpl.get('invariants', {})
            if not inv_tmpl:
                continue
            dist, diff = _distance(current_inv, inv_tmpl)
            if dist < MAX_DIST_THRESHOLD:
                scored.append((dist, diff, tmpl))
        
        if not scored:
            no_match += 1
            sample_dists = [_distance(current_inv, tmpl.get('invariants', {}))[0] 
                          for tmpl in active_templates[:20] if tmpl.get('invariants')]
            min_dist = min(sample_dists) if sample_dists else 99
            print(f'  NO_MATCH: {sym} min_dist={min_dist:.2f} inv={list(current_inv.keys())[:5]}')
            continue
        
        scored.sort(key=lambda x: x[0])
        top = scored[:TOP_K]
        top_matches = [TemplateMatch(
            symbol=t['symbol'], symbol_name=t.get('symbol_name') or symbol_name(t['symbol']),
            end_date=t['end_date'],
            outcome_start=t.get('outcome', {}).get('outcome_start_date', 'N/A'),
            direction=t.get('primary_direction', t.get('outcome', {}).get('direction', 'unclear')),
            up_move=t.get('outcome', {}).get('up_move', 0.0),
            down_move=t.get('outcome', {}).get('down_move', 0.0),
            days_to_peak=t.get('outcome', {}).get('days_to_peak', 0),
            days_to_trough=t.get('outcome', {}).get('days_to_trough', 0),
            bundle_id=t.get('bundle_id'),
            diff_detail=diff, distance=round(d, 4), similarity=round(1/(1+d), 4),
        ) for d, diff, t in top]
        
        evidence = {'data_cutoff': datetime.now().strftime('%Y-%m-%d'), 'config_hash': 'test'}
        opp = aggregate_opportunity(sym, symbol_name(sym), round(current_price, 2),
                                    str(confirmed_at), current_inv, top_matches, evidence)
        if opp:
            opportunities.append(opp)
            print(f'  OPP: {sym} score={opp.attention_score:.1f} dir={opp.direction} pot={opp.potential_median:.2%}')
    
    except Exception as e:
        errors += 1
        print(f'  ERROR: {sym} {type(e).__name__}: {e}')

print(f'\n=== 统计 (前15品种) ===')
print(f'无数据: {no_data}, 非活跃: {no_active}, 无结构: {no_structure}, 无匹配: {no_match}, 错误: {errors}')
print(f'识别到结构: {structures_found}, 机会数量: {len(opportunities)}')
if opportunities:
    opportunities.sort(key=lambda o: o.attention_score, reverse=True)
    print(f'\nTop 机会:')
    for o in opportunities[:5]:
        print(f'  {o.symbol} ({o.symbol_name}) score={o.attention_score:.1f} dir={o.direction} pot={o.potential_median:.2%} trigger={o.trigger_price}')sina_futures