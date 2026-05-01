"""
品种元数据管理

从 symbol_meta.yaml 加载品种信息（名称、交易所、合约类型等），
提供按品种查询元数据的接口。

用法：
    meta = get_symbol_meta("cu0")
    print(meta["name"])  # "铜"
"""
from __future__ import annotations
import os
import yaml

_CACHE: dict | None = None


def load_symbol_meta() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    
    # 尝试多种路径以兼容不同的运行环境（scripts/ 或 src/data/）
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "symbol_meta.yaml"),
        os.path.join(os.path.dirname(__file__), "..", "data", "symbol_meta.yaml"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                _CACHE = yaml.safe_load(f) or {}
            return _CACHE
            
    print("Warning: symbol_meta.yaml not found.")
    return {}


def symbol_name(code: str) -> str:
    meta = load_symbol_meta().get(code.upper(), {})
    return meta.get("name") or code


def symbol_description(code: str) -> str:
    """获取品种的独立描述信息"""
    meta = load_symbol_meta().get(code.upper(), {})
    return meta.get("description", "")


# 板块映射表（前缀 -> 板块）
_SECTOR_MAP = {
    # 黑色金属
    "RB": "黑色金属", "HC": "黑色金属", "J": "黑色金属", "I": "黑色金属", "JM": "黑色金属",
    # 有色金属
    "CU": "有色金属", "AL": "有色金属", "ZN": "有色金属", "NI": "有色金属", "SN": "有色金属",
    "PB": "有色金属", "SS": "有色金属", "SI": "有色金属",
    # 贵金属
    "AU": "贵金属", "AG": "贵金属",
    # 能源化工
    "SC": "能源化工", "BU": "能源化工", "TA": "能源化工", "MA": "能源化工", "PF": "能源化工",
    "EG": "能源化工", "EB": "能源化工", "PG": "能源化工", "FU": "能源化工", "L": "能源化工",
    "PP": "能源化工", "V": "能源化工", "SA": "能源化工", "FG": "能源化工", "UR": "能源化工",
    "RU": "能源化工", "NR": "能源化工", "ZC": "能源化工",
    # 农产品
    "M": "农产品", "Y": "农产品", "P": "农产品", "CS": "农产品", "A": "农产品",
    "C": "农产品", "CF": "农产品", "SR": "农产品", "OI": "农产品", "RM": "农产品",
    "AP": "农产品", "CJ": "农产品", "PK": "农产品", "JD": "农产品", "LH": "农产品",
    # 新能源
    "LC": "新能源",
}


def get_sector(symbol: str) -> str:
    """根据合约代码返回所属板块（黑色金属/有色金属/能源化工/农产品/贵金属）"""
    # 提取前缀（去掉数字和后缀，如 rb2505 -> rb）
    prefix = ""
    for ch in symbol.upper():
        if ch.isalpha():
            prefix += ch
        else:
            break
    return _SECTOR_MAP.get(prefix, "未知")
