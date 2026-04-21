"""
每日机会扫描脚本 (Daily Opportunity Scanner)

逻辑：
1. 加载高潜力结构模板（约束机制）。
2. 扫描当前市场所有品种的实时结构。
3. 基于无量纲不变量进行相似性匹配。
4. 输出具有 >10% 波动潜力的交易机会。
"""

import sys
import os
import json
import math
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.loader import MySQLLoader
from src.compiler.pipeline import compile_full, CompilerConfig
from src.relations import structure_invariants
from sqlalchemy import create_engine, inspect
import pandas as pd

def analyze_template_move(symbol, end_date_str, lookforward_days=30):
    """分析模板结束后的实际走势、方向和幅度"""
    loader = MySQLLoader(host='localhost', user='root', password='root', db='sina')
    try:
        end_date = pd.to_datetime(end_date_str)
        start_look = end_date
        end_look = end_date + timedelta(days=lookforward_days)
        
        bars = loader.get(symbol=symbol, start=start_look.strftime('%Y-%m-%d'), 
                          end=end_look.strftime('%Y-%m-%d'), freq='1d')
        
        if not bars: return "N/A", "N/A", "N/A"
        
        start_price = bars[0].open
        max_price = max(b.high for b in bars)
        min_price = min(b.low for b in bars)
        
        up_move = (max_price - start_price) / start_price
        down_move = (start_price - min_price) / start_price
        
        if up_move > down_move:
            return f"+{up_move:.1%}", "看涨", f"{up_move:.1%}"
        else:
            return f"-{down_move:.1%}", "看跌", f"{down_move:.1%}"
    except:
        return "N/A", "N/A", "N/A"

def generate_html_report(opportunities, filename="daily_scan_report.html"):
    """生成 HTML 格式的扫描报告"""
    html_content = f"""
    <html>
    <head>
        <title>每日高潜力结构机会扫描 - {datetime.now().strftime('%Y-%m-%d')}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h2 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #3498db; color: white; }}
            tr:hover {{ background-color: #f1f1f1; }}
            .bull {{ color: #e74c3c; font-weight: bold; }}
            .bear {{ color: #27ae60; font-weight: bold; }}
            .high-sim {{ background-color: #fff3cd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🚀 每日高潜力结构机会扫描报告</h2>
            <p>扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 活跃参照系: 近3年</p>
            <table>
                <thead>
                    <tr>
                        <th>品种</th>
                        <th>相似度</th>
                        <th>匹配模板日期</th>
                        <th>当前中枢</th>
                        <th>模板后期走势</th>
                        <th>方向判断</th>
                        <th>潜在幅度</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for opp in opportunities:
        row_class = "high-sim" if opp['similarity'] > 0.9 else ""
        dir_class = "bull" if "涨" in opp['direction'] else "bear"
        
        html_content += f"""
                    <tr class="{row_class}">
                        <td><strong>{opp['symbol']}</strong></td>
                        <td>{opp['similarity']:.3f}</td>
                        <td>{opp['template_date']}</td>
                        <td>{opp['current_zone']:.2f}</td>
                        <td>{opp['hist_move']}</td>
                        <td class="{dir_class}">{opp['direction']}</td>
                        <td>{opp['potential_move']}</td>
                    </tr>
        """
    
    html_content += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    
    output_path = os.path.join(os.path.dirname(__file__), "..", "output", filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"\nHTML 报告已生成: {output_path}")

def load_templates():
    """加载高潜力结构模板"""
    template_path = os.path.join(os.path.dirname(__file__), "..", "data", "library", "high_potential_templates.jsonl")
    templates = []
    with open(template_path, 'r', encoding='utf-8') as f:
        for line in f:
            templates.append(json.loads(line))
    return templates

def calculate_distance(inv1, inv2):
    """计算两个结构不变量之间的欧氏距离（归一化）"""
    features = ['avg_speed_ratio', 'avg_time_ratio', 'zone_rel_bw', 'high_dispersion']
    dist_sq = sum((inv1.get(f, 0) - inv2.get(f, 0)) ** 2 for f in features)
    return math.sqrt(dist_sq)

def get_all_symbols():
    """获取数据库中所有日线级别的表名"""
    engine = create_engine('mysql+pymysql://root:root@localhost/sina?charset=utf8')
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return [t for t in tables if not t.endswith('m5') and not t.startswith('test')]

def is_opportunity_viable(symbol, current_price, lookback_years=2):
    """倒推验证：检查当前是否仍处于可建仓的‘机会窗口’"""
    loader = MySQLLoader(host='localhost', user='root', password='root', db='sina')
    try:
        end_date = datetime(2026, 4, 20)
        start_date = end_date.replace(year=end_date.year - lookback_years)
        
        bars = loader.get(symbol=symbol, start=start_date.strftime('%Y-%m-%d'), 
                          end=end_date.strftime('%Y-%m-%d'), freq='1d')
        
        if not bars: return False
        
        # 计算过去 N 年的波动范围
        max_h = max(b.high for b in bars)
        min_l = min(b.low for b in bars)
        total_range = (max_h - min_l) / min_l
        
        # 计算当前位置在区间中的比例 (0-1)
        current_pos = (current_price - min_l) / (max_h - min_l) if max_h != min_l else 0.5
        
        # 约束1：如果过去 N 年波动率太小（<5%），说明品种不活跃，放弃
        if total_range < 0.05: return False
        
        # 约束2：如果价格已经处于区间极值（>90% 或 <10%），说明行情可能已走完，放弃
        # 我们寻找的是中间态（酝酿期或突破初期）
        if current_pos > 0.95 or current_pos < 0.05: return False
        
        return True
    except:
        return False

def daily_scan(scan_window_years=3, lookback_validation_years=2):
    print(f"--- 每日机会扫描 [{datetime.now().strftime('%Y-%m-%d %H:%M')}] ---")
    
    # 1. 加载全量约束模板（历史都是有效的）
    templates = load_templates()
    current_year = datetime.now().year
    
    # 2. 筛选近 N 年的高潜力模板作为“活跃参照系”
    active_templates = []
    for t in templates:
        tmpl_year = int(t['end_date'].split('-')[0])
        if current_year - tmpl_year <= scan_window_years:
            active_templates.append(t)
            
    print(f"已加载 {len(templates)} 个全量模板，其中 {len(active_templates)} 个为近{scan_window_years}年活跃参照系。")
    
    # 2. 初始化编译器与数据源
    loader = MySQLLoader(host='localhost', user='root', password='root', db='sina')
    config = CompilerConfig(min_amplitude=0.02, min_duration=3, zone_bandwidth=0.01)
    symbols = get_all_symbols()
    
    opportunities = []
    
    # 3. 扫描全市场
    for symbol in symbols:
        try:
            bars = loader.get(symbol=symbol, freq='1d')
            if len(bars) < 50: continue
            
            result = compile_full(bars, config)
            if not result.structures: continue
            
            # 取最新的一个结构进行比对
            current_st = result.structures[-1]
            current_inv = current_st.invariants
            
            # 4. 倒推验证：确保当前仍处于可建仓的“机会窗口”
            if not is_opportunity_viable(symbol, current_st.zone.price_center, lookback_validation_years):
                continue

            # 5. 寻找最相似的历史模板（仅匹配近3年的活跃参照系）
            best_match = None
            min_dist = float('inf')
            
            for tmpl in active_templates:
                dist = calculate_distance(current_inv, tmpl['invariants'])
                if dist < min_dist:
                    min_dist = dist
                    best_match = tmpl
            
            if best_match and min_dist < 0.5:
                similarity = 1 / (1 + min_dist)
                hist_move, direction, potential = analyze_template_move(
                    best_match['symbol'], best_match['end_date']
                )
                opportunities.append({
                    "symbol": symbol,
                    "similarity": similarity,
                    "template_date": best_match['end_date'],
                    "current_zone": current_st.zone.price_center,
                    "hist_move": hist_move,
                    "direction": direction,
                    "potential_move": potential
                })
                
        except Exception as e:
            continue

    # 5. 输出结果
    if not opportunities:
        print("今日未发现符合高潜力约束的市场机会。")
        return

    print(f"\n发现 {len(opportunities)} 个潜在机会，正在生成 HTML 报告...")
    opportunities.sort(key=lambda x: x['similarity'], reverse=True)
    generate_html_report(opportunities)

if __name__ == "__main__":
    daily_scan()
