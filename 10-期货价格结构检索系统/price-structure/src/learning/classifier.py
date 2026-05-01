"""
结构分类器 — 基于特征工程的规则 + 可选 XGBoost

T2 任务：Structure → {type, phase}

先用规则基线，再用 XGBoost 提升。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.models import Structure
from src.learning.features import extract_features, FEATURE_NAMES


# ─── 分类结果 ──────────────────────────────────────────────

@dataclass
class ClassifyResult:
    label: str
    confidence: float
    all_scores: dict[str, float]


# ─── 规则基线分类器 ────────────────────────────────────────

class RuleClassifier:
    """
    基于不变量的规则分类 — 编译器 bundle 已有的分类逻辑
    速度比 + 时间比 → slow_up_fast_down / fast_up_slow_down / balanced / mixed
    """

    def classify(self, s: Structure) -> ClassifyResult:
        sr = s.avg_speed_ratio
        tr = s.avg_time_ratio

        scores = {}

        if sr > 1.5 and tr > 1.5:
            label = "slow_up_fast_down"
            conf = min(1.0, (sr - 1.5) / 1.5 * 0.5 + (tr - 1.5) / 1.5 * 0.5 + 0.5)
        elif sr < 0.67 and tr < 0.67:
            label = "fast_up_slow_down"
            conf = min(1.0, (0.67 - sr) / 0.67 * 0.5 + (0.67 - tr) / 0.67 * 0.5 + 0.5)
        elif 0.7 < sr < 1.4 and 0.7 < tr < 1.4:
            label = "balanced"
            conf = 1.0 - abs(sr - 1.0) - abs(tr - 1.0)
            conf = max(0.3, min(1.0, conf))
        else:
            label = "mixed"
            conf = 0.5

        scores[label] = conf
        return ClassifyResult(label=label, confidence=conf, all_scores=scores)


# ─── XGBoost 分类器（可选）────────────────────────────────

class XGBClassifier:
    """
    基于 XGBoost 的结构分类

    需要 pip install xgboost
    """

    def __init__(self):
        try:
            import xgboost as xgb
            self._xgb = xgb
        except ImportError:
            self._xgb = None
        self._model = None
        self._label_map: dict[int, str] = {}

    def fit(self, structures: Sequence[Structure], labels: Sequence[str]) -> None:
        """训练"""
        if self._xgb is None:
            raise RuntimeError("需要安装 xgboost: pip install xgboost")

        import numpy as np

        # 标签编码
        unique_labels = sorted(set(labels))
        self._label_map = {i: l for i, l in enumerate(unique_labels)}
        reverse_map = {l: i for i, l in self._label_map.items()}

        X = np.array([extract_features(s) for s in structures])
        y = np.array([reverse_map[l] for l in labels])

        self._model = self._xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            use_label_encoder=False,
            eval_metric="mlogloss",
        )
        self._model.fit(X, y)

    def classify(self, s: Structure) -> ClassifyResult:
        """预测"""
        if self._model is None:
            raise RuntimeError("模型未训练，先调用 fit()")

        import numpy as np
        X = np.array([extract_features(s)])
        probs = self._model.predict_proba(X)[0]
        pred_idx = int(self._model.predict(X)[0])

        all_scores = {self._label_map[i]: float(p) for i, p in enumerate(probs)}
        return ClassifyResult(
            label=self._label_map[pred_idx],
            confidence=float(probs[pred_idx]),
            all_scores=all_scores,
        )

    def feature_importance(self) -> dict[str, float]:
        """特征重要性"""
        if self._model is None:
            return {}
        importances = self._model.feature_importances_
        return {name: float(imp) for name, imp in zip(FEATURE_NAMES, importances)}
