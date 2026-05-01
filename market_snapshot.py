#!/usr/bin/env python3
"""
期货行情 + 知识图谱背景 快照脚本
从 Sina 抽实时行情，从 config/products 抽背景，合并输出市场轮廓
"""
import json
import os
import urllib.request
import urllib.parse
import re
import sys

# ============================================================
# 配置
# ============================================================
CONFIG_DIR = "/root/.openclaw/workspace/The_Theory_of_Difference/config/products"

# Sina 期货代码映射 (品种 -> Sina代码)
SINA_MAP = {
    "copper": "CU0", "aluminum": "AL0", "nickel": "NI0", "zinc": "ZN0",
    "tin": "SN0", "lead": "PB0", "gold": "AU0", "silver": "AG0",
    "rebar": "RB0", "hot_coil": "HC0", "iron_ore": "I0",
    "coke": "J0", "coking_coal": "JM0", "ferrosilicon": "SF0", "silicon": "SM0",
    "crude_oil": "SC0", "fuel_oil": "FU0", "lpg": "PG0",
    "methanol": "MA0", "pta": "TA0", "eg": "EG0", "pp": "PP0",
    "plastic": "L0", "pvc": "V0", "asphalt": "BU0",
    "soda_ash": "SA0", "glass": "FG0", "urea": "UR0",
    "lithium_carbonate": "LC0", "industrial_silicon": "SI0",
    "corn": "C0", "soybean": "A0", "soybean_meal": "M0",
    "soybean_oil": "Y0", "palm_oil": "P0", "rapeseed_meal": "RM0",
    "rapeseed_oil": "OI0", "cotton": "CF0", "sugar": "SR0",
    "apple": "AP0", "starch": "CS0",
}

# 分类
SECTORS = {
    "有色金属": ["copper", "aluminum", "nickel", "zinc", "tin", "lead"],
    "黑色系": ["rebar", "hot_coil", "iron_ore", "coke", "coking_coal", "ferrosilicon", "silicon"],
    "贵金属": ["gold", "silver"],
    "能源化工": ["crude_oil", "fuel_oil", "lpg", "methanol", "pta", "eg", "pp", "plastic", "pvc", "asphalt", "soda_ash", "glass", "urea"],
    "新能源": ["lithium_carbonate", "industrial_silicon"],
    "农产品": ["corn", "soybean", "soybean_meal", "soybean_oil", "palm_oil", "rapeseed_meal", "rapeseed_oil", "cotton", "sugar", "apple", "starch"],
}

# ============================================================
# Sina 行情获取
# ============================================================
def fetch_sina_quotes(symbols):
    """批量获取 Sina 期货行情"""
    # 分批请求，每批最多10个
    results = {}
    symbol_list = list(symbols.items())
    for i in range(0, len(symbol_list), 8):
        batch = symbol_list[i:i+8]
        codes = ",".join([s[1] for s in batch])
        names = [s[0] for s in batch]
        
        try:
            url = f"https://hq.sinajs.cn/list={codes}"
            req = urllib.request.Request(url)
            req.add_header("Referer", "https://finance.sina.com.cn")
            req.add_header("User-Agent", "Mozilla/5.0")
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("gbk", errors="replace")
            
            for line in raw.strip().split("\n"):
                m = re.match(r'var hq_str_(\w+)="(.*)";', line.strip())
                if m:
                    code = m.group(1)
                    fields = m.group(2).split(",")
                    if len(fields) >= 15:
                        # 找到对应的产品名
                        product = None
                        for name, scode in batch:
                            if scode == code:
                                product = name
                                break
                        if product:
                            try:
                                results[product] = {
                                    "name": fields[0],
                                    "time": fields[1],
                                    "open": float(fields[2]) if fields[2] else 0,
                                    "prev_close": float(fields[3]) if fields[3] else 0,
                                    "high": float(fields[4]) if fields[4] else 0,
                                    "low": float(fields[5]) if fields[5] else 0,
                                    "last": float(fields[8]) if fields[8] else 0,
                                    "change": float(fields[9]) if fields[9] else 0,
                                    "volume": int(fields[14]) if fields[14] else 0,
                                    "hold": int(fields[13]) if fields[13] else 0,
                                    "date": fields[17] if len(fields) > 17 else "",
                                }
                            except (ValueError, IndexError):
                                pass
        except Exception as e:
            print(f"  [WARN] Sina batch error: {e}")
        
        import time
        time.sleep(0.3)
    
    return results

# ============================================================
# 知识图谱加载
# ============================================================
def load_product_config(product):
    """加载单个品类的知识图谱配置"""
    config = {}
    for fname in ["chains.json", "entities.json", "polarity.json", "pricing_models.json", "relations.json"]:
        fpath = os.path.join(CONFIG_DIR, product, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                key = fname.replace(".json", "")
                config[key] = json.load(f)
    return config

# ============================================================
# 输出格式化
# ============================================================
def fmt_price(val, prev):
    """格式化价格变动"""
    if prev == 0:
        return f"{val:.0f}"
    chg = val - prev
    pct = chg / prev * 100
    arrow = "↑" if chg > 0 else "↓" if chg < 0 else "→"
    return f"{val:.0f} {arrow}{pct:+.2f}%"

def get_key_chains(config):
    """提取关键传导链摘要"""
    chains = config.get("chains", {}).get("chains", [])
    if not chains:
        return []
    result = []
    for c in chains[:2]:  # 取前2条
        name = c.get("name", "")
        trigger = c.get("triggerEvent", "")
        reversal = c.get("reversalNode", "")
        result.append(f"  🔗 {name}")
        result.append(f"     触发: {trigger}")
        result.append(f"     反转: {reversal}")
    return result

def get_key_entities(config):
    """提取关键实体摘要"""
    entities = config.get("entities", {}).get("entities", [])
    if not entities:
        return []
    geo = [e for e in entities if e.get("type") in ("资源节点", "冶炼加工节点")]
    var = [e for e in entities if "变量" in e.get("type", "") or "大宗商品" in e.get("type", "")]
    result = []
    for e in geo[:2]:
        result.append(f"  🌍 {e['name']}: {e.get('description', '')[:60]}")
    for e in var[:2]:
        cv = e.get("currentValue", "")
        hr = e.get("historicalRange", {})
        if cv:
            result.append(f"  📊 {e['name']}: {cv}" + (f" (历史{hr.get('min','?')}-{hr.get('max','?')})" if hr else ""))
    return result

def get_polarity(config):
    """提取极性状态"""
    pa = config.get("polarity", {}).get("polarity_archive", [])
    if not pa:
        return None
    p = pa[0]
    return {
        "variable": p.get("variable", ""),
        "bull": p.get("poles", {}).get("bull", ""),
        "bear": p.get("poles", {}).get("bear", ""),
        "state": p.get("currentState", ""),
        "tension": p.get("tension", 0),
    }

def get_top_relations(config):
    """提取核心关联关系"""
    rels = config.get("relations", {}).get("relations", [])
    if not rels:
        return []
    sorted_rels = sorted(rels, key=lambda r: r.get("strength", 0), reverse=True)
    result = []
    for r in sorted_rels[:3]:
        result.append(f"  ⚡ {r['from']} →{r['to']} ({r['type']}, 强度{r.get('strength',0)})")
    return result

# ============================================================
# 主函数
# ============================================================
def main():
    # 支持指定品类或全部
    if len(sys.argv) > 1:
        target_products = sys.argv[1:]
    else:
        target_products = None  # 全部
    
    print("=" * 70)
    print("📈 期货市场快照 = 行情 + 知识图谱背景")
    print("=" * 70)
    
    # 获取行情
    print("\n⏳ 获取 Sina 实时行情...")
    sina_symbols = {p: s for p, s in SINA_MAP.items() if target_products is None or p in target_products}
    quotes = fetch_sina_quotes(sina_symbols)
    print(f"  获取到 {len(quotes)} 个品种行情")
    
    # 按板块输出
    for sector_name, products in SECTORS.items():
        sector_products = [p for p in products if target_products is None or p in target_products]
        if not sector_products:
            continue
        
        print(f"\n{'='*70}")
        print(f"【{sector_name}】")
        print(f"{'='*70}")
        
        for product in sector_products:
            config = load_product_config(product)
            quote = quotes.get(product)
            commodity = config.get("chains", {}).get("commodity", product)
            symbol = config.get("chains", {}).get("symbol", product.upper())
            
            # 行情行
            if quote:
                last = quote["last"]
                prev = quote["prev_close"]
                chg = last - prev
                pct = (chg / prev * 100) if prev else 0
                arrow = "🔴" if chg < 0 else "🟢" if chg > 0 else "⚪"
                print(f"\n{arrow} {commodity}({symbol}) | {fmt_price(last, prev)} | 量:{quote['volume']:,} | 持仓:{quote['hold']:,}")
                print(f"   开:{quote['open']:.0f} 高:{quote['high']:.0f} 低:{quote['low']:.0f} 昨收:{prev:.0f}")
            else:
                print(f"\n⚪ {commodity}({symbol}) | 行情暂无")
            
            # 极性状态
            pol = get_polarity(config)
            if pol:
                tbar = "█" * int(pol["tension"] * 10) + "░" * (10 - int(pol["tension"] * 10))
                print(f"   极性: {pol['state']} | 张力[{tbar}] {pol['tension']:.1f}")
                print(f"   🟢 多: {pol['bull']}")
                print(f"   🔴 空: {pol['bear']}")
            
            # 核心传导链
            chains = get_key_chains(config)
            if chains:
                print(f"   关键传导链:")
                for line in chains:
                    print(f"   {line}")
            
            # 核心关联
            rels = get_top_relations(config)
            if rels:
                print(f"   核心关联:")
                for line in rels:
                    print(f"   {line}")
    
    print(f"\n{'='*70}")
    print("数据来源: Sina期货实时行情 + config/products 知识图谱")
    print("注: 行情数据可能有延迟，仅供研究参考")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
