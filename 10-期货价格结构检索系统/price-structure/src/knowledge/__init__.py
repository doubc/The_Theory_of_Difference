"""
知识引擎模块 — L1/L2/L3 三层知识注入系统

L1 判定知识：Condition → Verdict（该信多少）
L2 失效知识：Condition → Invalidate（什么条件下作废）
L3 市场知识：Context → Wisdom（有什么值得注意的）
"""

from src.knowledge.engine import KnowledgeEngine
from src.knowledge.result import KnowledgeResult, MatchedRule

__all__ = ["KnowledgeEngine", "KnowledgeResult", "MatchedRule"]
