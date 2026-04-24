"""
src/fast/__init__.py — C 扩展 Python 包装器

自动检测 C 扩展是否可用：
- 有 C 扩展 → 使用高性能 C 实现
- 无 C 扩展 → fallback 到纯 Python 实现

用法：
    from src.fast import extract_pivots_fast, dtw_similarity_fast

    # 自动选择最优实现
    pivots = extract_pivots_fast(prices, ...)
    dist = dtw_similarity_fast(seq1, seq2)
"""

from __future__ import annotations

import math

# ─── 检测 C 扩展 ──────────────────────────────────────────

_C_AVAILABLE = False
_C_MODULE = None

try:
    from src.fast import _pivots as _C_MODULE
    from src.fast import _dtw as _C_DTW
    _C_AVAILABLE = True
except ImportError:
    pass

if not _C_AVAILABLE:
    # 尝试从同目录加载
    try:
        import importlib.util
        ext_dir = Path(__file__).parent
        for name in ["_pivots", "_dtw"]:
            # 支持 .so (Linux) 和 .pyd (Windows)
            so_path = list(ext_dir.glob(f"{name}*.so"))
            pyd_path = list(ext_dir.glob(f"{name}*.pyd"))
            file_path = so_path + pyd_path
            if file_path:
                spec = importlib.util.spec_from_file_location(name, file_path[0])
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if name == "_pivots":
                    _C_MODULE = mod
                else:
                    _C_DTW = mod
                _C_AVAILABLE = True
    except Exception:
        pass


def has_c_extension() -> bool:
    """C 扩展是否可用"""
    return _C_AVAILABLE


def performance_info() -> dict:
    """性能信息"""
    return {
        "c_extension": _C_AVAILABLE,
        "module": "C" if _C_AVAILABLE else "Python fallback",
    }


# ─── NumPy 数组工具 ───────────────────────────────────────

def _to_numpy_float(data):
    """将 list/array 转为 float64 numpy array"""
    import numpy as np
    if isinstance(data, np.ndarray):
        return data.astype(np.float64, copy=False)
    return np.array(data, dtype=np.float64)


def _to_numpy_int(data):
    """将 list/array 转为 int32 numpy array"""
    import numpy as np
    if isinstance(data, np.ndarray):
        return data.astype(np.int32, copy=False)
    return np.array(data, dtype=np.int32)


# ═══════════════════════════════════════════════════════════
# 极值提取
# ═══════════════════════════════════════════════════════════

def extract_pivots_fast(
    prices,
    returns=None,
    min_amplitude: float = 0.02,
    base_window: int = 3,
    noise_filter: float = 0.005,
    adaptive: bool = True,
    fractal_threshold: float = 0.34,
    vol_scale: float = 0.3,
    max_pivots: int = 10000,
) -> list[dict]:
    """
    快速极值提取（C 加速 + Python fallback）

    Args:
        prices: 价格序列 (list 或 numpy array)
        returns: 收益率序列（可选，自动计算）
        min_amplitude: 最小摆动幅度
        base_window: 基础窗口半宽
        noise_filter: 噪声过滤阈值
        adaptive: 是否启用自适应窗口
        fractal_threshold: 分形一致性阈值
        vol_scale: 波动率缩放系数
        max_pivots: 最大极值点数

    Returns:
        [{"idx": int, "price": float, "direction": int, "fractal": float}, ...]
    """
    import numpy as np

    prices_np = _to_numpy_float(prices)
    n = len(prices_np)

    if n < 3:
        return []

    # 自动计算收益率
    if returns is None:
        returns_np = np.zeros(n, dtype=np.float64)
        for i in range(1, n):
            if prices_np[i - 1] > 0:
                returns_np[i] = (prices_np[i] - prices_np[i - 1]) / prices_np[i - 1]
    else:
        returns_np = _to_numpy_float(returns)

    if _C_AVAILABLE and _C_MODULE is not None:
        # ── C 实现 ──
        out_idx = np.zeros(max_pivots, dtype=np.int32)
        out_dir = np.zeros(max_pivots, dtype=np.int32)
        out_fractal = np.zeros(max_pivots, dtype=np.float64)

        count = _C_MODULE.extract_pivots_c(
            prices_np, returns_np,
            float(min_amplitude), int(base_window), float(noise_filter),
            int(1 if adaptive else 0),
            float(fractal_threshold), float(vol_scale),
            out_idx, out_dir, out_fractal,
            int(max_pivots),
        )

        return [
            {
                "idx": int(out_idx[i]),
                "price": float(prices_np[out_idx[i]]),
                "direction": int(out_dir[i]),
                "fractal": float(out_fractal[i]),
            }
            for i in range(count)
        ]
    else:
        # ── Python fallback ──
        return _extract_pivots_python(
            prices_np, returns_np, min_amplitude, base_window,
            noise_filter, adaptive, fractal_threshold, max_pivots,
        )


def _extract_pivots_python(
    prices, returns, min_amplitude, base_window,
    noise_filter, adaptive, fractal_threshold, max_pivots,
) -> list[dict]:
    """Python fallback 实现"""
    n = len(prices)
    candidates = []

    for i in range(1, n - 1):
        # 自适应窗口
        if adaptive:
            lookback = min(20, i)
            if lookback >= 3:
                vol = _stddev(returns[i - lookback:i])
                scale = 1.0 / (1.0 + vol * 0.3 * 100)
                scale = max(0.5, min(3.0, scale))
                w = int(base_window * scale)
                w = max(base_window // 2, min(base_window * 3, w))
            else:
                w = base_window
        else:
            w = base_window

        lo = max(0, i - w)
        hi = min(n - 1, i + w)

        # 检查极值
        is_high = all(prices[j] < prices[i] for j in range(lo, hi + 1) if j != i)
        is_low = all(prices[j] > prices[i] for j in range(lo, hi + 1) if j != i)

        if not is_high and not is_low:
            continue

        # 幅度过滤
        mid = (prices[lo] + prices[hi]) / 2
        amp = abs(prices[i] - mid) / mid if mid > 0 else 0
        if amp < min_amplitude or amp < noise_filter:
            continue

        # 分形一致性
        fc = _fractal_check(prices, i, n, w, is_high)
        if fc < fractal_threshold:
            continue

        candidates.append({
            "idx": i,
            "price": float(prices[i]),
            "direction": 1 if is_high else -1,
            "fractal": fc,
        })

    # 强制交替
    if not candidates:
        return []

    result = [candidates[0]]
    for c in candidates[1:]:
        if c["direction"] != result[-1]["direction"]:
            result.append(c)
        else:
            # 选更极端的
            if c["direction"] == 1 and c["price"] > result[-1]["price"]:
                result[-1] = c
            elif c["direction"] == -1 and c["price"] < result[-1]["price"]:
                result[-1] = c

    return result[:max_pivots]


def _stddev(arr) -> float:
    if len(arr) < 2:
        return 0
    mean = sum(arr) / len(arr)
    var = sum((x - mean) ** 2 for x in arr) / len(arr)
    return math.sqrt(var)


def _fractal_check(prices, idx, n, window, is_high) -> float:
    score = 0
    checks = 0
    for scale in [window // 2, window, window * 2]:
        if scale < 1:
            scale = 1
        lo = max(0, idx - scale)
        hi = min(n - 1, idx + scale)
        is_extreme = True
        for i in range(lo, hi + 1):
            if i == idx:
                continue
            if is_high and prices[i] >= prices[idx]:
                is_extreme = False
                break
            if not is_high and prices[i] <= prices[idx]:
                is_extreme = False
                break
        if is_extreme:
            score += 1
        checks += 1
    return score / checks if checks > 0 else 0


# ═══════════════════════════════════════════════════════════
# DTW 相似度
# ═══════════════════════════════════════════════════════════

def dtw_similarity_fast(
    seq1,
    seq2,
    window: int | None = None,
) -> float:
    """
    快速 DTW 相似度（C 加速 + Python fallback）

    Args:
        seq1, seq2: 归一化价格序列
        window: Sakoe-Chiba 带宽（None = 自动）

    Returns:
        相似度 [0, 1]，1 = 完全相同
    """
    import numpy as np

    s1 = _to_numpy_float(seq1)
    s2 = _to_numpy_float(seq2)

    if len(s1) == 0 or len(s2) == 0:
        return 0.0

    # 归一化
    s1 = _normalize_series(s1)
    s2 = _normalize_series(s2)

    if window is None:
        window = max(len(s1), len(s2)) // 2

    if _C_AVAILABLE:
        # ── C 实现 ──
        return _C_DTW.dtw_similarity_c(s1, s2, len(s1), len(s2), window)
    else:
        # ── Python fallback ──
        return _dtw_similarity_python(s1, s2, window)


def dtw_distance_fast(seq1, seq2, window: int | None = None) -> float:
    """快速 DTW 距离"""
    import numpy as np

    s1 = _to_numpy_float(seq1)
    s2 = _to_numpy_float(seq2)

    if len(s1) == 0 or len(s2) == 0:
        return float("inf")

    s1 = _normalize_series(s1)
    s2 = _normalize_series(s2)

    if window is None:
        window = max(len(s1), len(s2)) // 2

    if _C_AVAILABLE:
        return _C_DTW.dtw_distance_c(s1, s2, len(s1), len(s2), window)
    else:
        return _dtw_distance_python(s1, s2, window)


def segment_shape_similarity_fast(sig1, sig2) -> float:
    """快速段形状相似度（编辑距离）"""
    import numpy as np

    s1 = _to_numpy_int(sig1)
    s2 = _to_numpy_int(sig2)

    if len(s1) == 0 and len(s2) == 0:
        return 1.0
    if len(s1) == 0 or len(s2) == 0:
        return 0.0

    if _C_AVAILABLE:
        return _C_DTW.segment_shape_similarity_c(s1, s2, len(s1), len(s2))
    else:
        return _segment_shape_python(s1.tolist(), s2.tolist())


def _normalize_series(values) -> "np.ndarray":
    """Min-max 归一化到 [0, 1]"""
    import numpy as np
    arr = np.asarray(values, dtype=np.float64)
    lo, hi = arr.min(), arr.max()
    if hi - lo < 1e-12:
        return np.full_like(arr, 0.5)
    return (arr - lo) / (hi - lo)


def _dtw_similarity_python(seq1, seq2, window) -> float:
    """Python fallback DTW 相似度"""
    dist = _dtw_distance_python(seq1, seq2, window)
    if dist == float("inf"):
        return 0.0
    max_len = max(len(seq1), len(seq2))
    normalized = dist / math.sqrt(max_len)
    return 1.0 / (1.0 + normalized)


def _dtw_distance_python(seq1, seq2, window) -> float:
    """Python fallback DTW 距离"""
    n, m = len(seq1), len(seq2)
    if n == 0 or m == 0:
        return float("inf")

    INF = float("inf")
    prev = [INF] * (m + 1)
    prev[0] = 0.0

    for i in range(1, n + 1):
        curr = [INF] * (m + 1)
        j_lo = max(1, i - window)
        j_hi = min(m, i + window)
        for j in range(j_lo, j_hi + 1):
            cost = (seq1[i - 1] - seq2[j - 1]) ** 2
            curr[j] = cost + min(prev[j], curr[j - 1], prev[j - 1])
        prev = curr

    return math.sqrt(prev[m])


def _segment_shape_python(sig1, sig2) -> float:
    """Python fallback 段形状相似度"""
    n, m = len(sig1), len(sig2)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if sig1[i - 1] == sig2[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    max_len = max(n, m)
    return 1.0 - dp[n][m] / max_len if max_len > 0 else 1.0


# ═══════════════════════════════════════════════════════════
# 批量操作
# ═══════════════════════════════════════════════════════════

def batch_dtw_similarity(query_seq, candidate_seqs, window: int | None = None) -> list[float]:
    """
    批量 DTW 相似度：一个查询 vs 多个候选

    Args:
        query_seq: 查询序列
        candidate_seqs: 候选序列列表
        window: Sakoe-Chiba 带宽

    Returns:
        相似度列表 [0, 1]
    """
    results = []
    for cs in candidate_seqs:
        results.append(dtw_similarity_fast(query_seq, cs, window=window))
    return results


def batch_extract_pivots(all_prices, offsets, **kwargs) -> list[list[dict]]:
    """
    批量极值提取：多个品种的价格序列

    Args:
        all_prices: 扁平化的价格数组
        offsets: 每个品种的起始偏移 [n+1]
        **kwargs: 传给 extract_pivots_fast 的参数

    Returns:
        每个品种的极值点列表
    """
    results = []
    for i in range(len(offsets) - 1):
        start, end = offsets[i], offsets[i + 1]
        prices = all_prices[start:end]
        pivots = extract_pivots_fast(prices, **kwargs)
        results.append(pivots)
    return results


# ═══════════════════════════════════════════════════════════
# 编译器 C 加速 (_compiler 模块)
# ═══════════════════════════════════════════════════════════

_COMPILER_AVAILABLE = False
try:
    from src.fast import _compiler as _COMPILER
    _COMPILER_AVAILABLE = True
except ImportError:
    pass


def has_compiler_extension() -> bool:
    return _COMPILER_AVAILABLE


def binary_filter_bars(timestamps, t_start: int, t_end: int, margin: int = 0) -> tuple[int, int]:
    """
    二分查找过滤 bar 时间范围 — O(log n)

    Args:
        timestamps: int64 numpy array，已排序的 epoch seconds
        t_start: 窗口起始 epoch seconds
        t_end: 窗口结束 epoch seconds
        margin: 边距（秒）

    Returns:
        (start_idx, end_idx) — 切片区间 [start_idx:end_idx]
    """
    import numpy as np
    ts = np.asarray(timestamps, dtype=np.int64)
    if _COMPILER_AVAILABLE:
        return _COMPILER.binary_filter_bars(ts, int(t_start), int(t_end), int(margin))
    else:
        # Python fallback
        lo = t_start - margin
        hi = t_end + margin
        start = np.searchsorted(ts, lo, side='left')
        end = np.searchsorted(ts, hi, side='right')
        return int(start), int(end)


def batch_geometric_similarity_fast(query_vec, candidate_matrix) -> list[float]:
    """
    批量几何相似度（C 加速）

    Args:
        query_vec: 查询不变量向量 (list/array, length=dim)
        candidate_matrix: 候选不变量矩阵 (2D array, shape=[n, dim])

    Returns:
        相似度列表 [0, 1]
    """
    import numpy as np
    q = np.asarray(query_vec, dtype=np.float64)
    c = np.asarray(candidate_matrix, dtype=np.float64)
    n, dim = c.shape
    out = np.zeros(n, dtype=np.float64)

    if _COMPILER_AVAILABLE:
        _COMPILER.batch_geometric_similarity(q, c, int(dim), int(n), out)
    else:
        # Python fallback
        inv_sqrt_dim = 1.0 / math.sqrt(dim)
        for i in range(n):
            d = c[i] - q
            dist = math.sqrt(float(np.dot(d, d)))
            out[i] = max(0.0, 1.0 - dist * inv_sqrt_dim)

    return out.tolist()


def batch_total_similarity_fast(
    query_geo, cand_geo,
    query_rel, cand_rel,
    query_mot, cand_mot,
    family_scores,
    weights=(0.35, 0.35, 0.15, 0.15),
) -> list[float]:
    """
    批量综合相似度（C 加速 + Python fallback）

    Args:
        query_geo: 查询几何向量 [dim]
        cand_geo: 候选几何矩阵 [n, dim]
        query_rel: 查询关系向量 [4]
        cand_rel: 候选关系矩阵 [n, 4]
        query_mot: 查询运动向量 [4]
        cand_mot: 候选运动矩阵 [n, 4]
        family_scores: 族相似度 [n]
        weights: (几何, 关系, 运动, 族) 权重

    Returns:
        综合相似度列表 [0, 1]
    """
    import numpy as np
    qg = np.asarray(query_geo, dtype=np.float64)
    cg = np.asarray(cand_geo, dtype=np.float64)
    qr = np.asarray(query_rel, dtype=np.float64)
    cr = np.asarray(cand_rel, dtype=np.float64)
    qm = np.asarray(query_mot, dtype=np.float64)
    cm = np.asarray(cand_mot, dtype=np.float64)
    fam = np.asarray(family_scores, dtype=np.float64)
    n = len(fam)
    dim = qg.shape[0] if qg.ndim > 0 else 1
    out = np.zeros(n, dtype=np.float64)
    w_g, w_r, w_m, w_f = weights

    if _COMPILER_AVAILABLE:
        _COMPILER.batch_total_similarity(
            qg, cg, qr, cr, qm, cm, fam,
            int(dim), int(n), float(w_g), float(w_r), float(w_m), out, float(w_f)
        )
    else:
        # Python fallback
        geo_scores = batch_geometric_similarity_fast(qg, cg)
        for i in range(n):
            # 关系
            rel = 0.0
            if qr[0] == cr[i * 4]: rel += 0.25
            dn = abs(qr[1] - cr[i * 4 + 1])
            rel += max(0, 1.0 - dn / 5.0) * 0.25
            if (qr[2] > 1) == (cr[i * 4 + 2] > 1): rel += 0.25
            if (qr[3] > 1) == (cr[i * 4 + 3] > 1): rel += 0.25
            # 运动
            mot = 0.0
            if qm[0] == cm[i * 4]: mot += 0.25
            if qm[1] * cm[i * 4 + 1] > 0: mot += 0.25
            dd = abs(qm[2] - cm[i * 4 + 2])
            mot += max(0, 1.0 - dd) * 0.25
            if qm[3] == cm[i * 4 + 3]: mot += 0.25
            out[i] = w_g * geo_scores[i] + w_r * rel + w_m * mot + w_f * fam[i]

    return out.tolist()


def batch_extract_features_fast(
    structures_data: dict,
) -> "np.ndarray":
    """
    批量特征提取（C 加速 + Python fallback）

    Args:
        structures_data: 包含以下 numpy arrays 的 dict:
            - speed_ratios, time_ratios, log_speed_ratios, amplitude_ratios
            - abs_deltas_entry, abs_deltas_exit, durations_entry, durations_exit
            - directions_entry
            - cycle_offsets [n_structures+1]
            - zone_bw_rel, zone_strength, high_cluster_cv [n_structures]

    Returns:
        features matrix [n_structures, 13]
    """
    import numpy as np
    n = len(structures_data['zone_bw_rel'])
    out = np.zeros((n, 13), dtype=np.float64)

    if _COMPILER_AVAILABLE:
        _COMPILER.batch_extract_features(
            structures_data['speed_ratios'],
            structures_data['time_ratios'],
            structures_data['log_speed_ratios'],
            structures_data['amplitude_ratios'],
            structures_data['abs_deltas_entry'],
            structures_data['abs_deltas_exit'],
            structures_data['durations_entry'],
            structures_data['durations_exit'],
            structures_data['directions_entry'].astype(np.int32),
            structures_data['cycle_offsets'].astype(np.int32),
            int(n),
            structures_data['zone_bw_rel'],
            structures_data['zone_strength'],
            structures_data['high_cluster_cv'],
            out,
        )
    else:
        # Python fallback: 逐结构调用
        from src.learning.features import extract_features
        for i, s in enumerate(structures_data.get('_structures', [])):
            out[i] = extract_features(s)

    return out
