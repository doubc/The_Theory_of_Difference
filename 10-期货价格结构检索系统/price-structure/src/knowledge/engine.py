"""
知识引擎 — KnowledgeEngine

加载 YAML 知识库，对结构进行规则匹配。
支持 L1 判定知识、L2 失效知识、L3 市场知识三层匹配。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.knowledge.result import KnowledgeResult, MatchedRule


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (ValueError, TypeError):
        return default


def _safe_str(v: Any, default: str = "") -> str:
    try:
        if v is None:
            return default
        return str(v)
    except (ValueError, TypeError):
        return default


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes")
    return bool(v) if v is not None else default


class KnowledgeEngine:
    """
    知识引擎：加载 YAML 知识库，对结构进行知识匹配。

    用法：
        engine = KnowledgeEngine("knowledge")
        result = engine.evaluate(structure, motion_state)
        print(result.summary())
    """

    def __init__(self, knowledge_dir: str = "knowledge"):
        self.knowledge_dir = Path(knowledge_dir)
        self._conditions: list[dict] = []
        self._invalidations: list[dict] = []
        self._wisdoms: list[dict] = []
        self._loaded = False

    def _load(self) -> None:
        """加载所有 YAML 知识文件"""
        if self._loaded:
            return

        self._conditions = self._load_yaml("L1_conditions.yaml")
        self._invalidations = self._load_yaml("L2_invalidation.yaml")
        self._wisdoms = self._load_yaml("L3_wisdom.yaml")
        self._loaded = True

    def _load_yaml(self, filename: str) -> list[dict]:
        """加载单个 YAML 文件的规则列表"""
        filepath = self.knowledge_dir / filename
        if not filepath.exists():
            return []
        try:
            with open(filepath, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data is None:
                return []
            return data.get("rules", [])
        except Exception:
            return []

    def reload(self) -> None:
        """强制重新加载知识文件"""
        self._loaded = False
        self._load()

    def evaluate(
        self,
        structure: Any = None,
        motion: Any = None,
        symbol: str = "",
        extra_context: dict | None = None,
    ) -> KnowledgeResult:
        """
        对一个结构执行全部知识规则，返回匹配结果。

        Args:
            structure: Structure 对象（可选）
            motion: MotionState 对象（可选）
            symbol: 品种代码（可选）
            extra_context: 额外上下文字段（可选）
        """
        self._load()

        # 构建匹配上下文
        ctx = self._build_context(structure, motion, symbol, extra_context)

        # 匹配三层知识
        matched_l1 = self._match_rules(self._conditions, ctx, level="L1")
        matched_l2 = self._match_rules(self._invalidations, ctx, level="L2")
        matched_l3 = self._match_wisdoms(ctx)

        return KnowledgeResult(
            conditions=matched_l1,
            invalidations=matched_l2,
            wisdoms=matched_l3,
        )

    def _build_context(
        self,
        structure: Any,
        motion: Any,
        symbol: str,
        extra_context: dict | None,
    ) -> dict:
        """从结构和运动态提取匹配上下文"""
        ctx: dict[str, Any] = {}

        # 从 structure 提取
        if structure is not None:
            ctx["cycle_count"] = getattr(structure, "cycle_count", 0)
            ctx["symbol"] = _safe_str(getattr(structure, "symbol", symbol))

            # 不变量
            inv = getattr(structure, "invariants", None) or {}
            ctx["avg_speed_ratio"] = _safe_float(inv.get("avg_speed_ratio"))
            ctx["avg_time_ratio"] = _safe_float(inv.get("avg_time_ratio"))
            ctx["zone_rel_bw"] = _safe_float(inv.get("zone_rel_bw"))

            # Zone
            zone = getattr(structure, "zone", None)
            if zone is not None:
                ctx["zone_center"] = _safe_float(getattr(zone, "price_center", 0))
                ctx["zone_strength"] = _safe_float(getattr(zone, "strength", 0))
                ctx["contrast_type"] = _safe_str(
                    getattr(zone, "context_contrast", None)
                )

            # 运动态
            m = motion or getattr(structure, "motion", None)
            if m is not None:
                ctx["movement_type"] = _safe_str(getattr(m, "movement_type", ""))
                ctx["phase_tendency"] = _safe_str(getattr(m, "phase_tendency", ""))
                ctx["flux"] = _safe_float(getattr(m, "conservation_flux", 0))
                ctx["flux_abs"] = abs(ctx["flux"])
                ctx["phase_confidence"] = _safe_float(
                    getattr(m, "phase_confidence", 0)
                )

                # 通量方向矛盾检测
                mt = ctx["movement_type"]
                flux = ctx["flux"]
                if mt == "trend_up" and flux < 0:
                    ctx["flux_direction_contradiction"] = True
                elif mt == "trend_down" and flux > 0:
                    ctx["flux_direction_contradiction"] = True
                else:
                    ctx["flux_direction_contradiction"] = False

            # 质量层
            ctx["tier"] = _safe_str(getattr(structure, "quality_tier", ""))
            ctx["typicality"] = _safe_float(getattr(structure, "typicality", 0))

            # 结构年龄
            ctx["structural_age"] = _safe_float(
                getattr(structure, "structural_age", 0)
            )

        # 从 motion 补充（如果 structure 没有 motion）
        if motion is not None and "movement_type" not in ctx:
            ctx["movement_type"] = _safe_str(getattr(motion, "movement_type", ""))
            ctx["phase_tendency"] = _safe_str(getattr(motion, "phase_tendency", ""))
            ctx["flux"] = _safe_float(getattr(motion, "conservation_flux", 0))
            ctx["flux_abs"] = abs(ctx["flux"])

        # symbol
        if symbol and "symbol" not in ctx:
            ctx["symbol"] = symbol

        # 稳定性相关
        ctx["stable_count"] = ctx.get("cycle_count", 0)
        ctx["stable_verified"] = _safe_bool(ctx.get("stable_verified", False))

        # 投影觉知
        ctx["compression_level"] = _safe_float(ctx.get("compression_level", 0))

        # 速度模式检测
        sr = ctx.get("avg_speed_ratio", 1.0)
        if sr > 1.5:
            ctx["speed_pattern"] = "slow_rise_fast_drop"
        elif sr < 0.67:
            ctx["speed_pattern"] = "fast_rise_slow_drop"
        else:
            ctx["speed_pattern"] = "balanced"

        # 跨 Zone 反向检测
        ctx["cross_zone_reversal"] = _safe_bool(
            ctx.get("cross_zone_reversal", False)
        )

        # 合并额外上下文
        if extra_context:
            ctx.update(extra_context)

        return ctx

    def _match_rules(
        self, rules: list[dict], ctx: dict, level: str
    ) -> list[MatchedRule]:
        """匹配一组规则"""
        matched = []
        for rule in rules:
            if self._evaluate_conditions(rule.get("when", []), ctx):
                mr = MatchedRule(
                    id=rule.get("id", ""),
                    name=rule.get("name", ""),
                    level=level,
                    verdict=rule.get("verdict", ""),
                    invalidate=rule.get("invalidate", ""),
                    wisdom=rule.get("wisdom", ""),
                    confidence=float(rule.get("confidence", 0)),
                    weight_adjust=float(rule.get("weight_adjust", 0)),
                    severity=rule.get("severity", ""),
                    action=rule.get("action", ""),
                    source=rule.get("source", ""),
                )
                matched.append(mr)
        return matched

    def _match_wisdoms(self, ctx: dict) -> list[MatchedRule]:
        """匹配 L3 市场知识（支持无条件匹配的全局知识）"""
        matched = []
        for rule in self._wisdoms:
            when_conditions = rule.get("when", [])
            if not when_conditions:
                # 无条件 = 全局知识
                mr = MatchedRule(
                    id=rule.get("id", ""),
                    name=rule.get("name", ""),
                    level="L3",
                    wisdom=rule.get("wisdom", ""),
                    source=rule.get("source", ""),
                )
                matched.append(mr)
            elif self._evaluate_conditions(when_conditions, ctx):
                mr = MatchedRule(
                    id=rule.get("id", ""),
                    name=rule.get("name", ""),
                    level="L3",
                    wisdom=rule.get("wisdom", ""),
                    source=rule.get("source", ""),
                )
                matched.append(mr)
        return matched

    def _evaluate_conditions(self, conditions: list[dict], ctx: dict) -> bool:
        """评估条件列表（AND 关系）"""
        for cond in conditions:
            field = cond.get("field", "")
            op = cond.get("op", "")
            expected = cond.get("value")

            actual = ctx.get(field)

            if not self._evaluate_single(actual, op, expected):
                return False
        return True

    def _evaluate_single(self, actual: Any, op: str, expected: Any) -> bool:
        """评估单个条件"""
        if op == "==":
            return actual == expected
        elif op == "!=":
            return actual != expected
        elif op == ">":
            return _safe_float(actual) > _safe_float(expected)
        elif op == "<":
            return _safe_float(actual) < _safe_float(expected)
        elif op == ">=":
            return _safe_float(actual) >= _safe_float(expected)
        elif op == "<=":
            return _safe_float(actual) <= _safe_float(expected)
        elif op == "in":
            if isinstance(expected, list):
                return actual in expected
            return False
        elif op == "not_in":
            if isinstance(expected, list):
                return actual not in expected
            return True
        elif op == "contains":
            if isinstance(actual, (list, str)):
                return expected in actual
            return False
        return False

    @property
    def stats(self) -> dict:
        """返回知识库统计"""
        self._load()
        return {
            "L1_conditions": len(self._conditions),
            "L2_invalidation": len(self._invalidations),
            "L3_wisdom": len(self._wisdoms),
            "total": len(self._conditions) + len(self._invalidations) + len(self._wisdoms),
        }
