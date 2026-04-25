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
