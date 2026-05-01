"""
知识图谱查询助手 — 为研究闭环和复盘提供知识图谱数据

功能：
  - 查询品种的产业链关联
  - 查询品种的跨品种影响
  - 查询品种的关键实体和关系
  - 生成知识图谱摘要
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml


# ─── 缓存 ──────────────────────────────────────────────────

_product_cache: Dict[str, dict] = {}
_shared_cache: dict = {}
_registry: dict = {}
_loaded = False


def _load_registry() -> dict:
    """加载品种注册表"""
    global _registry
    if not _registry:
        reg_path = Path("config/products/registry.yaml")
        if reg_path.exists():
            with open(reg_path, "r", encoding="utf-8") as f:
                _registry = yaml.safe_load(f) or {}
    return _registry


def _load_product(product: str) -> dict:
    """加载单个品种的配置"""
    global _product_cache
    if product not in _product_cache:
        product_dir = Path(f"config/products/{product}")
        if product_dir.exists():
            _product_cache[product] = {}
            for fname in ["entities.json", "relations.json", "chains.json", "polarity.json", "pricing_models.json"]:
                fpath = product_dir / fname
                if fpath.exists():
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            _product_cache[product][fname.replace(".json", "")] = json.load(f)
                    except Exception:
                        pass
    return _product_cache.get(product, {})


def _load_shared() -> dict:
    """加载跨品种共享配置"""
    global _shared_cache
    if not _shared_cache:
        shared_dir = Path("config/products/_shared")
        if shared_dir.exists():
            for fname in ["entities.json", "relations.json", "chains.json", "polarity.json"]:
                fpath = shared_dir / fname
                if fpath.exists():
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            _shared_cache[fname.replace(".json", "")] = json.load(f)
                    except Exception:
                        pass
    return _shared_cache


def _symbol_to_product(symbol: str) -> Optional[str]:
    """将品种代码转换为产品目录名"""
    symbol = symbol.upper().replace("0", "").replace("000", "")
    reg = _load_registry()
    products = reg.get("products", {})
    for product_name, info in products.items():
        if product_name.startswith("_"):
            continue
        if info.get("symbol", "").upper() == symbol:
            return product_name
    # 直接匹配
    symbol_map = {
        "CU": "copper", "AL": "aluminum", "ZN": "zinc", "NI": "nickel", "SN": "tin", "PB": "lead",
        "AU": "gold", "AG": "silver", "PT": "platinum",
        "RB": "rebar", "HC": "hot_coil", "I": "iron_ore", "J": "coke", "JM": "coking_coal", "SF": "ferrosilicon",
        "SC": "crude_oil", "FU": "fuel_oil", "BU": "asphalt", "L": "plastic", "PP": "pp",
        "V": "pvc", "EG": "meg", "EB": "styrene", "PG": "propane", "MA": "methanol", "TA": "pta",
        "M": "soybean_meal", "Y": "soybean_oil", "P": "palm_oil", "A": "soybean",
        "C": "corn", "CS": "corn_starch", "SR": "sugar", "CF": "cotton",
        "OI": "rapeseed_oil", "RM": "rapeseed_meal", "AP": "apple", "CJ": "jujube",
        "FG": "glass", "SA": "soda_ash", "UR": "urea", "ZC": "thermal_coal",
        "LC": "lithium_carbonate", "SI": "industrial_silicon",
    }
    return symbol_map.get(symbol)


# ─── 查询函数 ──────────────────────────────────────────────

def get_product_knowledge(symbol: str) -> dict:
    """获取品种的完整知识图谱数据"""
    product = _symbol_to_product(symbol)
    if not product:
        return {"error": f"未找到品种 {symbol} 的知识图谱配置"}

    data = _load_product(product)
    if not data:
        return {"error": f"品种 {product} 的配置为空"}

    return {
        "product": product,
        "symbol": symbol,
        "entities": data.get("entities", {}).get("entities", []),
        "relations": data.get("relations", {}).get("relations", []),
        "chains": data.get("chains", {}).get("chains", []),
        "polarity": data.get("polarity", {}).get("entries", {}),
        "pricing_models": data.get("pricing_models", {}).get("models", []),
    }


def get_cross_variety_impacts(symbol: str) -> List[dict]:
    """获取品种的跨品种影响关系"""
    shared = _load_shared()
    relations = shared.get("relations", {}).get("relations", [])

    symbol_upper = symbol.upper().replace("0", "").replace("000", "")
    impacts = []

    for r in relations:
        r_from = r.get("from", "")
        r_to = r.get("to", "")
        # 检查是否与该品种相关
        if (symbol_upper in r_from.upper() or symbol in r_from or
            symbol_upper in r_to.upper() or symbol in r_to):
            impacts.append(r)

    return impacts


def get_chain_peers_from_kg(symbol: str) -> List[str]:
    """从知识图谱获取产业链关联品种"""
    impacts = get_cross_variety_impacts(symbol)
    peers = set()
    symbol_upper = symbol.upper().replace("0", "").replace("000", "")

    for r in impacts:
        r_from = r.get("from", "")
        r_to = r.get("to", "")
        # 提取品种代码
        for text in [r_from, r_to]:
            if symbol_upper not in text.upper():
                # 尝试提取品种代码
                for code in ["CU", "AL", "ZN", "NI", "SN", "PB", "AU", "AG", "PT",
                            "RB", "HC", "I", "J", "JM", "SF", "SS",
                            "SC", "FU", "BU", "L", "PP", "V", "EG", "EB", "PG", "MA", "TA",
                            "M", "Y", "P", "A", "C", "CS", "SR", "CF", "OI", "RM", "AP", "CJ",
                            "FG", "SA", "UR", "ZC", "LC", "SI"]:
                    if code in text.upper():
                        peers.add(code)

    return sorted(peers)


def get_sector_from_kg(symbol: str) -> dict:
    """从知识图谱获取品种板块信息"""
    product = _symbol_to_product(symbol)
    if not product:
        return {"sector": "未知", "sub_sector": "未知"}

    reg = _load_registry()
    products = reg.get("products", {})
    product_info = products.get(product, {})

    tags = product_info.get("tags", [])
    sector = product_info.get("sector", "未知")

    # 从 tags 推断细分
    sub_sector = "未知"
    for tag in tags:
        if "metal" in tag:
            sub_sector = "金属"
        elif "energy" in tag or "chemical" in tag:
            sub_sector = "能化"
        elif "agriculture" in tag or "soft" in tag:
            sub_sector = "农产品"
        elif "building" in tag:
            sub_sector = "建材"
        elif "new_energy" in tag:
            sub_sector = "新能源"

    return {"sector": sector, "sub_sector": sub_sector}


def get_key_relations(symbol: str, limit: int = 5) -> List[dict]:
    """获取品种的关键关系（按强度排序）"""
    knowledge = get_product_knowledge(symbol)
    relations = knowledge.get("relations", [])

    # 按 strength 排序
    relations.sort(key=lambda r: r.get("strength", 0), reverse=True)
    return relations[:limit]


def get_key_chains(symbol: str, limit: int = 3) -> List[dict]:
    """获取品种的关键传导链"""
    knowledge = get_product_knowledge(symbol)
    chains = knowledge.get("chains", [])
    return chains[:limit]


def get_polarity_reference(symbol: str) -> dict:
    """获取品种的极值参考"""
    knowledge = get_product_knowledge(symbol)
    return knowledge.get("polarity", {})


def generate_knowledge_summary(symbol: str) -> str:
    """生成品种知识图谱的文字摘要"""
    knowledge = get_product_knowledge(symbol)
    if "error" in knowledge:
        return knowledge["error"]

    lines = []
    lines.append(f"## 📚 {symbol} 知识图谱摘要")

    # 实体
    entities = knowledge.get("entities", [])
    if entities:
        lines.append(f"\n### 关键实体 ({len(entities)} 个)")
        for e in entities[:5]:
            name = e.get("name", "")
            desc = e.get("description", "")[:60]
            lines.append(f"- **{name}**: {desc}")

    # 关系
    relations = knowledge.get("relations", [])
    if relations:
        lines.append(f"\n### 核心关系 ({len(relations)} 条)")
        for r in relations[:5]:
            r_from = r.get("from", "")
            r_to = r.get("to", "")
            r_type = r.get("type", "")
            strength = r.get("strength", 0)
            lines.append(f"- {r_from} → {r_to} ({r_type}, 强度{strength:.0%})")

    # 传导链
    chains = knowledge.get("chains", [])
    if chains:
        lines.append(f"\n### 传导链 ({len(chains)} 条)")
        for c in chains[:3]:
            name = c.get("name", "")
            trigger = c.get("triggerEvent", "")
            lines.append(f"- **{name}**: 触发条件={trigger}")

    # 跨品种影响
    impacts = get_cross_variety_impacts(symbol)
    if impacts:
        lines.append(f"\n### 跨品种影响 ({len(impacts)} 条)")
        for r in impacts[:5]:
            r_from = r.get("from", "")
            r_to = r.get("to", "")
            r_type = r.get("type", "")
            lines.append(f"- {r_from} → {r_to} ({r_type})")

    # 定价模型
    models = knowledge.get("pricing_models", [])
    if models:
        lines.append(f"\n### 定价模型 ({len(models)} 个)")
        for m in models[:2]:
            name = m.get("name", "")
            desc = m.get("description", "")[:60]
            lines.append(f"- **{name}**: {desc}")

    return "\n".join(lines)
