/*
 * _pivots.c — 极值提取 C 扩展
 *
 * 替代 pivots.py 中的热循环，直接操作 NumPy 数组。
 * 支持：自适应窗口 + 分形一致性 + 强制交替
 *
 * 编译：python setup.py build_ext --inplace
 * 或：   gcc -shared -fPIC -O3 -o _pivots.so _pivots.c -I$(python3 -c "import numpy; print(numpy.get_include())") $(python3-config --ldflags)
 */

#include <math.h>
#include <stdlib.h>
#include <string.h>

/* 极值点结构 */
typedef struct {
    int idx;        /* 在原始序列中的索引 */
    double price;   /* 价格 */
    int direction;  /* 1=高点, -1=低点 */
    double fractal; /* 分形一致性分数 */
} PivotPoint;

/* 自适应窗口计算 */
static int adaptive_window(
    const double *returns,    /* 收益率序列 */
    int pos,                  /* 当前位置 */
    int n,                    /* 序列长度 */
    int base_n,               /* 基础窗口半宽 */
    double volatility_scale   /* 波动率缩放系数 */
) {
    /* 计算局部波动率（20-bar 收益率标准差） */
    int lookback = 20;
    int start = pos > lookback ? pos - lookback : 0;
    int count = pos - start;
    if (count < 3) return base_n;

    double sum = 0, sum2 = 0;
    for (int i = start; i < pos; i++) {
        double r = returns[i];
        sum += r;
        sum2 += r * r;
    }
    double mean = sum / count;
    double var = sum2 / count - mean * mean;
    double vol = var > 0 ? sqrt(var) : 0;

    /* 高波动 → 缩短窗口，低波动 → 延长窗口 */
    /* 典型波动率 ~0.01-0.03, 映射到 [0.5, 3.0] 的缩放因子 */
    double scale = 1.0 / (1.0 + vol * volatility_scale * 100);
    if (scale < 0.5) scale = 0.5;
    if (scale > 3.0) scale = 3.0;

    int w = (int)(base_n * scale);
    int min_w = base_n / 2 > 1 ? base_n / 2 : 1;
    int max_w = base_n * 3;
    if (w < min_w) w = min_w;
    if (w > max_w) w = max_w;
    return w;
}

/* 分形一致性验证：多窗口确认 */
static double fractal_consistency(
    const double *prices,
    int idx,
    int n,
    int window,
    int is_high  /* 1=检查高点, 0=检查低点 */
) {
    double score = 0;
    int checks = 0;
    int scales[] = {window / 2, window, window * 2};

    for (int s = 0; s < 3; s++) {
        int w = scales[s];
        if (w < 1) w = 1;
        int lo = idx - w > 0 ? idx - w : 0;
        int hi = idx + w < n - 1 ? idx + w : n - 1;

        int is_extreme = 1;
        for (int i = lo; i <= hi; i++) {
            if (i == idx) continue;
            if (is_high && prices[i] > prices[idx]) {
                is_extreme = 0;
                break;
            }
            if (!is_high && prices[i] < prices[idx]) {
                is_extreme = 0;
                break;
            }
        }
        if (is_extreme) score += 1.0;
        checks++;
    }

    return checks > 0 ? score / checks : 0;
}

/*
 * 主函数：提取极值点
 *
 * 参数：
 *   prices       — 价格数组 [n]
 *   returns      — 收益率数组 [n] (close-to-close)
 *   n            — 数组长度
 *   min_amplitude — 最小摆动幅度（相对比例）
 *   base_window  — 基础窗口半宽
 *   noise_filter — 噪声过滤阈值
 *   adaptive     — 是否启用自适应窗口
 *   fractal_threshold — 分形一致性阈值
 *   vol_scale    — 波动率缩放系数
 *
 * 输出：
 *   out_idx      — 极值点索引数组 [max_pivots]
 *   out_dir      — 极值点方向数组 [max_pivots] (1=高, -1=低)
 *   out_fractal  — 分形一致性分数 [max_pivots]
 *
 * 返回：极值点数量
 */
int extract_pivots_c(
    const double *prices,
    const double *returns,
    int n,
    double min_amplitude,
    int base_window,
    double noise_filter,
    int adaptive,
    double fractal_threshold,
    double vol_scale,
    int *out_idx,
    int *out_dir,
    double *out_fractal,
    int max_pivots
) {
    if (n < 3 || max_pivots < 1) return 0;

    PivotPoint *candidates = (PivotPoint *)malloc(n * sizeof(PivotPoint));
    int n_candidates = 0;

    /* 第一遍：候选极值点提取 */
    for (int i = 1; i < n - 1; i++) {
        int w = adaptive ?
            adaptive_window(returns, i, n, base_window, vol_scale) :
            base_window;

        int lo = i - w > 0 ? i - w : 0;
        int hi = i + w < n - 1 ? i + w : n - 1;

        /* 检查是否为局部高点 */
        int is_high = 1, is_low = 1;
        for (int j = lo; j <= hi; j++) {
            if (j == i) continue;
            if (prices[j] >= prices[i]) is_high = 0;
            if (prices[j] <= prices[i]) is_low = 0;
        }

        if (!is_high && !is_low) continue;

        /* 幅度过滤 */
        double mid_price = (prices[lo] + prices[hi]) / 2;
        double amp = mid_price > 0 ? fabs(prices[i] - mid_price) / mid_price : 0;
        if (amp < min_amplitude) continue;

        /* 噪声过滤 */
        if (amp < noise_filter) continue;

        /* 分形一致性 */
        double fc = fractal_consistency(prices, i, n, w, is_high);
        if (fc < fractal_threshold) continue;

        candidates[n_candidates].idx = i;
        candidates[n_candidates].price = prices[i];
        candidates[n_candidates].direction = is_high ? 1 : -1;
        candidates[n_candidates].fractal = fc;
        n_candidates++;
    }

    /* 第二遍：强制交替 + 幅度竞争 */
    int n_pivots = 0;
    if (n_candidates == 0) {
        free(candidates);
        return 0;
    }

    /* 第一个候选点 */
    out_idx[0] = candidates[0].idx;
    out_dir[0] = candidates[0].direction;
    out_fractal[0] = candidates[0].fractal;
    n_pivots = 1;

    for (int i = 1; i < n_candidates && n_pivots < max_pivots; i++) {
        int last_dir = out_dir[n_pivots - 1];

        if (candidates[i].direction != last_dir) {
            /* 方向不同，直接添加 */
            out_idx[n_pivots] = candidates[i].idx;
            out_dir[n_pivots] = candidates[i].direction;
            out_fractal[n_pivots] = candidates[i].fractal;
            n_pivots++;
        } else {
            /* 方向相同，选择更极端的 */
            int last_idx = out_idx[n_pivots - 1];
            if (candidates[i].direction == 1) {
                /* 高点：选更高的 */
                if (candidates[i].price > prices[last_idx]) {
                    out_idx[n_pivots - 1] = candidates[i].idx;
                    out_fractal[n_pivots - 1] = candidates[i].fractal;
                }
            } else {
                /* 低点：选更低的 */
                if (candidates[i].price < prices[last_idx]) {
                    out_idx[n_pivots - 1] = candidates[i].idx;
                    out_fractal[n_pivots - 1] = candidates[i].fractal;
                }
            }
        }
    }

    free(candidates);
    return n_pivots;
}


/*
 * 批量编译辅助：从 OHLCV 数组直接提取所有品种的极值点
 *
 * 用于全市场扫描，减少 Python/C 边界调用开销。
 *
 * 参数：
 *   all_prices   — 所有品种价格 [total_bars]
 *   all_returns  — 所有品种收益率 [total_bars]
 *   offsets      — 每个品种在 all_prices 中的起始偏移 [n_symbols+1]
 *   n_symbols    — 品种数量
 *   ...（其他参数同上）
 *
 * 输出：
 *   pivot_offsets — 每个品种的极值点在输出数组中的起始偏移 [n_symbols+1]
 *   out_idx, out_dir, out_fractal — 全部极值点的扁平数组
 *
 * 返回：总极值点数量
 */
int batch_extract_pivots(
    const double *all_prices,
    const double *all_returns,
    const int *offsets,
    int n_symbols,
    double min_amplitude,
    int base_window,
    double noise_filter,
    int adaptive,
    double fractal_threshold,
    double vol_scale,
    int *pivot_offsets,
    int *out_idx,
    int *out_dir,
    double *out_fractal,
    int max_total_pivots
) {
    int total_pivots = 0;
    pivot_offsets[0] = 0;

    for (int s = 0; s < n_symbols; s++) {
        int start = offsets[s];
        int end = offsets[s + 1];
        int n = end - start;

        if (n < 3) {
            pivot_offsets[s + 1] = total_pivots;
            continue;
        }

        int remaining = max_total_pivots - total_pivots;
        if (remaining <= 0) {
            pivot_offsets[s + 1] = total_pivots;
            continue;
        }

        int count = extract_pivots_c(
            all_prices + start,
            all_returns + start,
            n,
            min_amplitude,
            base_window,
            noise_filter,
            adaptive,
            fractal_threshold,
            vol_scale,
            out_idx + total_pivots,
            out_dir + total_pivots,
            out_fractal + total_pivots,
            remaining
        );

        /* 调整索引为全局偏移 */
        for (int i = 0; i < count; i++) {
            out_idx[total_pivots + i] += start;
        }

        total_pivots += count;
        pivot_offsets[s + 1] = total_pivots;
    }

    return total_pivots;
}

/* ═══════════════════════════════════════════════════════════
 * Python C API 绑定
 * ═══════════════════════════════════════════════════════════ */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <numpy/arrayobject.h>

static PyObject* py_extract_pivots_c(PyObject* self, PyObject* args) {
    PyArrayObject *prices_arr, *returns_arr;
    double min_amplitude;
    int base_window;
    double noise_filter;
    int adaptive;
    double fractal_threshold;
    double vol_scale;
    PyArrayObject *out_idx_arr, *out_dir_arr, *out_fractal_arr;
    int max_pivots;

    /* 解析参数 */
    if (!PyArg_ParseTuple(args, "O!O!dididdiO!O!O!i",
                          &PyArray_Type, &prices_arr,
                          &PyArray_Type, &returns_arr,
                          &min_amplitude, &base_window,
                          &noise_filter, &adaptive,
                          &fractal_threshold, &vol_scale,
                          &PyArray_Type, &out_idx_arr,
                          &PyArray_Type, &out_dir_arr,
                          &PyArray_Type, &out_fractal_arr,
                          &max_pivots)) {
        return NULL;
    }

    /* 验证输入数组 */
    if (PyArray_NDIM(prices_arr) != 1 || PyArray_NDIM(returns_arr) != 1) {
        PyErr_SetString(PyExc_ValueError, "Prices and returns must be 1D arrays");
        return NULL;
    }

    int n = (int)PyArray_DIM(prices_arr, 0);
    if (n != (int)PyArray_DIM(returns_arr, 0)) {
        PyErr_SetString(PyExc_ValueError, "Array length mismatch");
        return NULL;
    }

    /* 获取数据指针 */
    double *prices = (double *)PyArray_DATA(prices_arr);
    double *returns = (double *)PyArray_DATA(returns_arr);
    int *out_idx = (int *)PyArray_DATA(out_idx_arr);
    int *out_dir = (int *)PyArray_DATA(out_dir_arr);
    double *out_fractal = (double *)PyArray_DATA(out_fractal_arr);

    /* 调用核心 C 函数 */
    int count = extract_pivots_c(
        prices, returns, n,
        min_amplitude, base_window, noise_filter,
        adaptive, fractal_threshold, vol_scale,
        out_idx, out_dir, out_fractal,
        max_pivots
    );

    /* 返回极值点数量 */
    return PyLong_FromLong(count);
}

/* 方法表 */
static PyMethodDef PivotsMethods[] = {
    {"extract_pivots_c", py_extract_pivots_c, METH_VARARGS,
     "Extract pivot points (C accelerated)"},
    {NULL, NULL, 0, NULL}
};

/* 模块定义 */
static struct PyModuleDef pivotsmodule = {
    PyModuleDef_HEAD_INIT,
    "_pivots",
    "Pivot extraction C extension module",
    -1,
    PivotsMethods
};

/* 模块初始化函数 */
PyMODINIT_FUNC PyInit__pivots(void) {
    import_array();  /* Initialize NumPy C API */
    return PyModule_Create(&pivotsmodule);
}
