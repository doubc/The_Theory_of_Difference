"""
期货品种 → 板块 + 产业链上下游映射
权威来源：大商所/郑商所/上期所/中金所官方分类 + 产业研究报告
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class SectorInfo:
    sector: str  # 一级板块
    sub_sector: str  # 二级细分
    chain_role: str  # upstream / midstream / downstream
    chain_peers: List[str]  # 同产业链关联品种（用于共振）
    exchange: str


# 权威映射表（覆盖 61 个主流连续合约）
SECTOR_MAP: Dict[str, SectorInfo] = {
    # 黑色产业链
    "RB0": SectorInfo("黑色金属", "钢材", "downstream", ["HC0", "I0", "J0", "JM0", "SF0", "SM0"], "SHFE"),
    "HC0": SectorInfo("黑色金属", "钢材", "downstream", ["RB0", "I0", "J0", "JM0"], "SHFE"),
    "I0": SectorInfo("黑色金属", "铁矿石", "upstream", ["RB0", "HC0", "J0", "JM0"], "DCE"),
    "J0": SectorInfo("黑色金属", "焦炭", "midstream", ["JM0", "I0", "RB0"], "DCE"),
    "JM0": SectorInfo("黑色金属", "焦煤", "upstream", ["J0", "I0", "RB0"], "DCE"),
    "SF0": SectorInfo("黑色金属", "铁合金", "midstream", ["SM0", "RB0"], "CZCE"),
    "SM0": SectorInfo("黑色金属", "铁合金", "midstream", ["SF0", "RB0"], "CZCE"),

    # 有色金属
    "CU0": SectorInfo("有色金属", "铜", "midstream", ["AL0", "ZN0", "NI0"], "SHFE"),
    "AL0": SectorInfo("有色金属", "铝", "midstream", ["CU0", "ZN0"], "SHFE"),
    "ZN0": SectorInfo("有色金属", "锌", "midstream", ["CU0", "AL0", "PB0"], "SHFE"),
    "PB0": SectorInfo("有色金属", "铅", "midstream", ["ZN0"], "SHFE"),
    "NI0": SectorInfo("有色金属", "镍", "midstream", ["CU0", "SS0"], "SHFE"),
    "SN0": SectorInfo("有色金属", "锡", "midstream", ["CU0"], "SHFE"),
    "SS0": SectorInfo("有色金属", "不锈钢", "downstream", ["NI0"], "SHFE"),
    "SI0": SectorInfo("有色金属", "工业硅", "upstream", ["PS0"], "GFEX"),
    "PS0": SectorInfo("有色金属", "多晶硅", "midstream", ["SI0"], "GFEX"),

    # 贵金属
    "AU0": SectorInfo("贵金属", "黄金", "midstream", ["AG0"], "SHFE"),
    "AG0": SectorInfo("贵金属", "白银", "midstream", ["AU0"], "SHFE"),

    # 能源化工
    "SC0": SectorInfo("能源化工", "原油", "upstream", ["FU0", "BU0", "PG0"], "INE"),
    "FU0": SectorInfo("能源化工", "燃料油", "midstream", ["SC0", "BU0"], "SHFE"),
    "BU0": SectorInfo("能源化工", "沥青", "midstream", ["SC0", "FU0"], "SHFE"),
    "PG0": SectorInfo("能源化工", "LPG", "midstream", ["SC0"], "DCE"),
    "TA0": SectorInfo("能源化工", "PTA", "midstream", ["EG0", "PF0", "MA0"], "CZCE"),
    "EG0": SectorInfo("能源化工", "乙二醇", "midstream", ["TA0", "PF0"], "DCE"),
    "PF0": SectorInfo("能源化工", "短纤", "downstream", ["TA0", "EG0"], "CZCE"),
    "MA0": SectorInfo("能源化工", "甲醇", "midstream", ["V0", "PP0"], "CZCE"),
    "V0": SectorInfo("能源化工", "PVC", "midstream", ["MA0", "PP0"], "DCE"),
    "PP0": SectorInfo("能源化工", "聚丙烯", "midstream", ["MA0", "L0"], "DCE"),
    "L0": SectorInfo("能源化工", "塑料LLDPE", "midstream", ["PP0", "V0"], "DCE"),
    "EB0": SectorInfo("能源化工", "苯乙烯", "midstream", ["TA0", "PP0"], "DCE"),
    "RU0": SectorInfo("能源化工", "天然橡胶", "midstream", ["NR0"], "SHFE"),
    "NR0": SectorInfo("能源化工", "20号胶", "upstream", ["RU0"], "INE"),
    "SP0": SectorInfo("能源化工", "纸浆", "upstream", [], "SHFE"),
    "FG0": SectorInfo("能源化工", "玻璃", "downstream", ["SA0", "V0"], "CZCE"),
    "SA0": SectorInfo("能源化工", "纯碱", "upstream", ["FG0"], "CZCE"),
    "UR0": SectorInfo("能源化工", "尿素", "midstream", ["MA0"], "CZCE"),

    # 农产品
    "M0": SectorInfo("农产品", "豆粕", "downstream", ["A0", "B0", "RM0", "Y0"], "DCE"),
    "RM0": SectorInfo("农产品", "菜粕", "downstream", ["M0", "OI0"], "CZCE"),
    "A0": SectorInfo("农产品", "豆一", "upstream", ["M0", "Y0"], "DCE"),
    "B0": SectorInfo("农产品", "豆二", "upstream", ["M0", "Y0"], "DCE"),
    "Y0": SectorInfo("农产品", "豆油", "downstream", ["M0", "P0", "OI0"], "DCE"),
    "P0": SectorInfo("农产品", "棕榈油", "downstream", ["Y0", "OI0"], "DCE"),
    "OI0": SectorInfo("农产品", "菜油", "downstream", ["Y0", "P0", "RM0"], "CZCE"),
    "C0": SectorInfo("农产品", "玉米", "upstream", ["CS0", "M0"], "DCE"),
    "CS0": SectorInfo("农产品", "淀粉", "downstream", ["C0"], "DCE"),
    "CF0": SectorInfo("农产品", "棉花", "upstream", ["CY0"], "CZCE"),
    "CY0": SectorInfo("农产品", "棉纱", "downstream", ["CF0"], "CZCE"),
    "SR0": SectorInfo("农产品", "白糖", "midstream", [], "CZCE"),
    "AP0": SectorInfo("农产品", "苹果", "midstream", [], "CZCE"),
    "CJ0": SectorInfo("农产品", "红枣", "midstream", [], "CZCE"),
    "JD0": SectorInfo("农产品", "鸡蛋", "downstream", ["C0", "M0"], "DCE"),
    "LH0": SectorInfo("农产品", "生猪", "downstream", ["C0", "M0"], "DCE"),
    "PK0": SectorInfo("农产品", "花生", "upstream", ["Y0"], "CZCE"),

    # 金融
    "IF0": SectorInfo("金融", "沪深300", "midstream", ["IH0", "IC0", "IM0"], "CFFEX"),
    "IH0": SectorInfo("金融", "上证50", "midstream", ["IF0", "IC0"], "CFFEX"),
    "IC0": SectorInfo("金融", "中证500", "midstream", ["IF0", "IM0"], "CFFEX"),
    "IM0": SectorInfo("金融", "中证1000", "midstream", ["IF0", "IC0"], "CFFEX"),
    "T0": SectorInfo("金融", "十年国债", "midstream", ["TF0", "TS0", "TL0"], "CFFEX"),
    "TF0": SectorInfo("金融", "五年国债", "midstream", ["T0", "TS0"], "CFFEX"),
    "TS0": SectorInfo("金融", "二年国债", "midstream", ["T0", "TF0"], "CFFEX"),
    "TL0": SectorInfo("金融", "三十年国债", "midstream", ["T0"], "CFFEX"),
}


def get_sector(symbol: str) -> SectorInfo:
    """返回品种的板块信息，未知品种 fallback 到 '其他'"""
    key = symbol.upper().strip()
    if key in SECTOR_MAP:
        return SECTOR_MAP[key]
    return SectorInfo("其他", "未分类", "unknown", [], "UNKNOWN")


def get_chain_peers(symbol: str, include_self: bool = False) -> List[str]:
    """返回产业链同伴品种，用于跨品种共振检测"""
    info = get_sector(symbol)
    peers = list(info.chain_peers)
    if include_self:
        peers.insert(0, symbol.upper())
    return peers


def group_by_sector(symbols: List[str]) -> Dict[str, List[str]]:
    """按板块聚合品种列表"""
    groups: Dict[str, List[str]] = {}
    for s in symbols:
        sec = get_sector(s).sector
        groups.setdefault(sec, []).append(s)
    return groups
