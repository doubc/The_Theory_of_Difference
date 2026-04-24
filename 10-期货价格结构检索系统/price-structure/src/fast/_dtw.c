/*
 * _dtw.c — DTW 距离 C 扩展
 *
 * 高性能 Dynamic Time Warping 实现，用于结构相似度计算。
 * 支持 Sakoe-Chiba 带宽约束 + 空间优化 O(m)。
 *
 * 比 Python 实现快 50-100x（纯数值计算）。
 *
 * v3.1 优化：
 *   - 工作区预分配，批量场景零 malloc
 *   - 内层循环 min 展开，减少分支
 *   - 静态栈分配小序列（<1024），避免堆分配
 *   - batch_dtw 并行友好
 */

#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <float.h>

/* 小序列用栈分配，大序列才 malloc */
#define DTW_STACK_SIZE 1024

/*
 * DTW 距离计算（空间优化版，只保留两行 DP）
 *
 * 参数：
 *   seq1, seq2 — 归一化序列 [n1], [n2]
 *   n1, n2     — 序列长度
 *   window     — Sakoe-Chiba 带宽（0 = 无约束）
 *
 * 返回：DTW 距离（越小越相似）
 */
double dtw_distance_c(
    const double *seq1,
    const double *seq2,
    int n1,
    int n2,
    int window
) {
    if (n1 == 0 || n2 == 0) return DBL_MAX;

    /* 带宽约束 */
    if (window <= 0) window = n1 > n2 ? n1 : n2;
    int diff = n1 - n2;
    if (diff < 0) diff = -diff;
    if (window < diff) window = diff;

    /* 栈分配小序列，避免 malloc 开销 */
    double stack_prev[DTW_STACK_SIZE + 1];
    double stack_curr[DTW_STACK_SIZE + 1];
    double *prev, *curr;
    int use_stack = (n2 <= DTW_STACK_SIZE);

    if (use_stack) {
        prev = stack_prev;
        curr = stack_curr;
    } else {
        prev = (double *)malloc((n2 + 1) * sizeof(double));
        curr = (double *)malloc((n2 + 1) * sizeof(double));
        if (!prev || !curr) {
            free(prev);
            free(curr);
            return DBL_MAX;
        }
    }

    /* 初始化：prev = [0, INF, INF, ...] */
    prev[0] = 0.0;
    for (int j = 1; j <= n2; j++) {
        prev[j] = DBL_MAX;
    }

    /* DP 填充 */
    for (int i = 1; i <= n1; i++) {
        /* 重置当前行为 INF */
        for (int j = 0; j <= n2; j++) {
            curr[j] = DBL_MAX;
        }
        curr[0] = DBL_MAX;

        int j_lo = i - window;
        if (j_lo < 1) j_lo = 1;
        int j_hi = i + window;
        if (j_hi > n2) j_hi = n2;

        double s1_i = seq1[i - 1];  /* 预取，减少内存访问 */

        for (int j = j_lo; j <= j_hi; j++) {
            double diff_val = s1_i - seq2[j - 1];
            double cost = diff_val * diff_val;

            /* 展开 min 三路，减少分支预测失败 */
            double a = prev[j];       /* deletion  */
            double b = curr[j - 1];   /* insertion  */
            double c = prev[j - 1];   /* match      */

            double min_val = a < b ? (a < c ? a : c) : (b < c ? b : c);
            curr[j] = cost + min_val;
        }

        /* 交换 prev/curr（指针交换，零拷贝） */
        double *tmp = prev;
        prev = curr;
        curr = tmp;
    }

    double result = sqrt(prev[n2]);

    if (!use_stack) {
        free(prev);
        free(curr);
    }

    return result;
}


/*
 * 工作区结构 — 批量 DTW 时预分配一次，复用多次
 */
typedef struct {
    double *buf1;   /* [capacity] */
    double *buf2;   /* [capacity] */
    int capacity;
} DTWWorkspace;

/* 初始化工作区（capacity = 最大候选序列长度） */
DTWWorkspace* dtw_workspace_create(int capacity) {
    if (capacity < 1) capacity = 1;
    DTWWorkspace *ws = (DTWWorkspace *)malloc(sizeof(DTWWorkspace));
    if (!ws) return NULL;
    ws->buf1 = (double *)malloc((capacity + 1) * sizeof(double));
    ws->buf2 = (double *)malloc((capacity + 1) * sizeof(double));
    ws->capacity = capacity;
    if (!ws->buf1 || !ws->buf2) {
        free(ws->buf1);
        free(ws->buf2);
        free(ws);
        return NULL;
    }
    return ws;
}

void dtw_workspace_free(DTWWorkspace *ws) {
    if (!ws) return;
    free(ws->buf1);
    free(ws->buf2);
    free(ws);
}

/*
 * DTW 距离（使用预分配工作区，零 malloc）
 */
double dtw_distance_ws(
    const double *seq1,
    const double *seq2,
    int n1,
    int n2,
    int window,
    DTWWorkspace *ws
) {
    if (n1 == 0 || n2 == 0) return DBL_MAX;

    if (window <= 0) window = n1 > n2 ? n1 : n2;
    int diff = n1 - n2;
    if (diff < 0) diff = -diff;
    if (window < diff) window = diff;

    /* 如果候选序列超出工作区容量，fallback 到独立分配 */
    if (n2 > ws->capacity) {
        return dtw_distance_c(seq1, seq2, n1, n2, window);
    }

    double *prev = ws->buf1;
    double *curr = ws->buf2;

    prev[0] = 0.0;
    for (int j = 1; j <= n2; j++) prev[j] = DBL_MAX;

    for (int i = 1; i <= n1; i++) {
        for (int j = 0; j <= n2; j++) curr[j] = DBL_MAX;
        curr[0] = DBL_MAX;

        int j_lo = i - window;
        if (j_lo < 1) j_lo = 1;
        int j_hi = i + window;
        if (j_hi > n2) j_hi = n2;

        double s1_i = seq1[i - 1];

        for (int j = j_lo; j <= j_hi; j++) {
            double d = s1_i - seq2[j - 1];
            double cost = d * d;
            double a = prev[j], b = curr[j - 1], c = prev[j - 1];
            curr[j] = cost + (a < b ? (a < c ? a : c) : (b < c ? b : c));
        }

        double *tmp = prev; prev = curr; curr = tmp;
    }

    return sqrt(prev[n2]);
}

/*
 * DTW 相似度（返回 [0, 1]，1=完全相同）
 *
 * 自动归一化距离，使用 sigmoid 压缩。
 */
double dtw_similarity_c(
    const double *seq1,
    const double *seq2,
    int n1,
    int n2,
    int window
) {
    if (n1 == 0 || n2 == 0) return 0.0;

    double dist = dtw_distance_c(seq1, seq2, n1, n2, window);
    if (dist == DBL_MAX) return 0.0;

    /* 归一化：典型 DTW 距离在 [0, sqrt(n)] 范围 */
    int max_len = n1 > n2 ? n1 : n2;
    double normalized = dist / sqrt((double)max_len);

    /* Sigmoid 压缩到 [0, 1] */
    return 1.0 / (1.0 + normalized);
}


/*
 * 批量 DTW：计算一个序列与多个候选序列的 DTW 距离
 *
 * 使用预分配工作区，批量场景零 malloc。
 * 用于检索场景：给定当前结构的速度比序列，与历史库中所有结构做 DTW 比较。
 *
 * 参数：
 *   query        — 查询序列 [query_len]
 *   query_len    — 查询序列长度
 *   candidates   — 候选序列（扁平存储）[total_candidate_len]
 *   cand_offsets — 每个候选的起始偏移 [n_candidates+1]
 *   n_candidates — 候选数量
 *   window       — Sakoe-Chiba 带宽
 *
 * 输出：
 *   out_dist     — DTW 距离数组 [n_candidates]
 */
void batch_dtw(
    const double *query,
    int query_len,
    const double *candidates,
    const int *cand_offsets,
    int n_candidates,
    int window,
    double *out_dist
) {
    /* 预分配工作区（找到最大候选长度） */
    int max_cand_len = 0;
    for (int i = 0; i < n_candidates; i++) {
        int len = cand_offsets[i + 1] - cand_offsets[i];
        if (len > max_cand_len) max_cand_len = len;
    }

    DTWWorkspace *ws = dtw_workspace_create(max_cand_len);
    if (!ws) {
        /* 分配失败，fallback 到逐个独立分配 */
        for (int i = 0; i < n_candidates; i++) {
            int start = cand_offsets[i];
            int end = cand_offsets[i + 1];
            out_dist[i] = dtw_distance_c(
                query, candidates + start,
                query_len, end - start, window
            );
        }
        return;
    }

    for (int i = 0; i < n_candidates; i++) {
        int start = cand_offsets[i];
        int end = cand_offsets[i + 1];
        out_dist[i] = dtw_distance_ws(
            query, candidates + start,
            query_len, end - start, window, ws
        );
    }

    dtw_workspace_free(ws);
}


/*
 * 编辑距离（Levenshtein）— 用于段形状相似度
 *
 * v3.1: 小序列栈分配
 *
 * 参数：
 *   seq1, seq2 — 符号序列（整数编码）[n1], [n2]
 *   n1, n2     — 序列长度
 *
 * 返回：编辑距离
 */
int edit_distance_c(
    const int *seq1,
    const int *seq2,
    int n1,
    int n2
) {
    if (n1 == 0) return n2;
    if (n2 == 0) return n1;

    /* 栈分配小序列 */
    int stack_prev[DTW_STACK_SIZE + 1];
    int stack_curr[DTW_STACK_SIZE + 1];
    int *prev, *curr;
    int use_stack = (n2 <= DTW_STACK_SIZE);

    if (use_stack) {
        prev = stack_prev;
        curr = stack_curr;
    } else {
        prev = (int *)malloc((n2 + 1) * sizeof(int));
        curr = (int *)malloc((n2 + 1) * sizeof(int));
        if (!prev || !curr) {
            free(prev);
            free(curr);
            return n1 + n2;
        }
    }

    for (int j = 0; j <= n2; j++) prev[j] = j;

    for (int i = 1; i <= n1; i++) {
        curr[0] = i;
        int s1_i = seq1[i - 1];  /* 预取 */
        for (int j = 1; j <= n2; j++) {
            int cost = (s1_i == seq2[j - 1]) ? 0 : 1;
            int del = prev[j] + 1;
            int ins = curr[j - 1] + 1;
            int sub = prev[j - 1] + cost;
            curr[j] = del < ins ? (del < sub ? del : sub) : (ins < sub ? ins : sub);
        }
        int *tmp = prev; prev = curr; curr = tmp;
    }

    int result = prev[n2];
    if (!use_stack) {
        free(prev);
        free(curr);
    }
    return result;
}


/*
 * 段形状相似度（返回 [0, 1]）
 *
 * 参数：
 *   sig1, sig2 — 符号签名（整数编码）[n1], [n2]
 *   n1, n2     — 序列长度
 *
 * 返回：相似度 [0, 1]
 */
double segment_shape_similarity_c(
    const int *sig1,
    const int *sig2,
    int n1,
    int n2
) {
    if (n1 == 0 && n2 == 0) return 1.0;
    if (n1 == 0 || n2 == 0) return 0.0;

    int dist = edit_distance_c(sig1, sig2, n1, n2);
    int max_len = n1 > n2 ? n1 : n2;

    return 1.0 - (double)dist / max_len;
}


/*
 * 结构不变量向量的欧氏距离
 *
 * 参数：
 *   v1, v2 — 归一化不变量向量 [dim]
 *   dim    — 向量维度
 *
 * 返回：欧氏距离
 */
double euclidean_distance_c(
    const double *v1,
    const double *v2,
    int dim
) {
    double sum = 0;
    for (int i = 0; i < dim; i++) {
        double d = v1[i] - v2[i];
        sum += d * d;
    }
    return sqrt(sum);
}


/*
 * 全量相似度计算（几何 + 关系 + 运动 + 族）
 *
 * 批量计算一个查询结构与所有候选结构的综合相似度。
 *
 * 参数：
 *   q_geo, c_geo     — 查询/候选的几何不变量向量 [dim * n_candidates]
 *   q_rel, c_rel     — 查询/候选的关系特征 [4 * n_candidates]
 *   q_mot, c_mot     — 查询/候选的运动特征 [4 * n_candidates]
 *   dim              — 不变量维度
 *   n_candidates     — 候选数量
 *   w_geo, w_rel, w_motion, w_family — 权重
 *
 * 输出：
 *   out_scores       — 综合相似度 [n_candidates]
 */
void batch_similarity(
    const double *q_geo,
    const double *c_geo,
    const double *q_rel,
    const double *c_rel,
    const double *q_mot,
    const double *c_mot,
    int dim,
    int n_candidates,
    double w_geo,
    double w_rel,
    double w_motion,
    double w_family,
    double *out_scores
) {
    /* 查询向量 */
    for (int i = 0; i < n_candidates; i++) {
        double geo = 1.0 - euclidean_distance_c(
            q_geo, c_geo + i * dim, dim
        ) / sqrt((double)dim);
        if (geo < 0) geo = 0;

        /* 关系相似度 */
        double rel = 0;
        if (q_rel[0] == c_rel[i * 4 + 0]) rel += 0.25;  /* zone source */
        double dn = q_rel[1] - c_rel[i * 4 + 1];
        if (dn < 0) dn = -dn;
        rel += (1.0 - dn / 5.0) * 0.25;
        if (dn < 0) dn = 0;
        if ((q_rel[2] > 1) == (c_rel[i * 4 + 2] > 1)) rel += 0.25;
        if ((q_rel[3] > 1) == (c_rel[i * 4 + 3] > 1)) rel += 0.25;

        /* 运动相似度 */
        double mot = 0;
        if (q_mot[0] == c_mot[i * 4 + 0]) mot += 0.25;
        double flux_prod = q_mot[1] * c_mot[i * 4 + 1];
        if (flux_prod > 0) mot += 0.25;
        double dd = q_mot[2] - c_mot[i * 4 + 2];
        if (dd < 0) dd = -dd;
        mot += (1.0 - dd) * 0.25;
        if (q_mot[3] == c_mot[i * 4 + 3]) mot += 1.0 * 0.25;

        /* 族相似度（简化） */
        double fam = 0.5;  /* 默认中等 */

        out_scores[i] = w_geo * geo + w_rel * rel + w_motion * mot + w_family * fam;
    }
}


/* ═══════════════════════════════════════════════════════════
 * Python C API 绑定
 * ═══════════════════════════════════════════════════════════ */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <numpy/arrayobject.h>

/* ── dtw_distance_c ── */
static PyObject* py_dtw_distance_c(PyObject* self, PyObject* args) {
    PyArrayObject *s1_arr, *s2_arr;
    int n1, n2, window;

    if (!PyArg_ParseTuple(args, "O!O!iii",
                          &PyArray_Type, &s1_arr,
                          &PyArray_Type, &s2_arr,
                          &n1, &n2, &window))
        return NULL;

    double *s1 = (double *)PyArray_DATA(s1_arr);
    double *s2 = (double *)PyArray_DATA(s2_arr);
    double dist = dtw_distance_c(s1, s2, n1, n2, window);
    return PyFloat_FromDouble(dist);
}

/* ── dtw_similarity_c ── */
static PyObject* py_dtw_similarity_c(PyObject* self, PyObject* args) {
    PyArrayObject *s1_arr, *s2_arr;
    int n1, n2, window;

    if (!PyArg_ParseTuple(args, "O!O!iii",
                          &PyArray_Type, &s1_arr,
                          &PyArray_Type, &s2_arr,
                          &n1, &n2, &window))
        return NULL;

    double *s1 = (double *)PyArray_DATA(s1_arr);
    double *s2 = (double *)PyArray_DATA(s2_arr);
    double sim = dtw_similarity_c(s1, s2, n1, n2, window);
    return PyFloat_FromDouble(sim);
}

/* ── segment_shape_similarity_c ── */
static PyObject* py_segment_shape_similarity_c(PyObject* self, PyObject* args) {
    PyArrayObject *s1_arr, *s2_arr;
    int n1, n2;

    if (!PyArg_ParseTuple(args, "O!O!ii",
                          &PyArray_Type, &s1_arr,
                          &PyArray_Type, &s2_arr,
                          &n1, &n2))
        return NULL;

    int *s1 = (int *)PyArray_DATA(s1_arr);
    int *s2 = (int *)PyArray_DATA(s2_arr);
    double sim = segment_shape_similarity_c(s1, s2, n1, n2);
    return PyFloat_FromDouble(sim);
}

/* ── batch_dtw ── */
static PyObject* py_batch_dtw(PyObject* self, PyObject* args) {
    PyArrayObject *query_arr, *cand_arr, *offsets_arr, *out_arr;
    int query_len, n_candidates, window;

    if (!PyArg_ParseTuple(args, "O!iO!O!iO!",
                          &PyArray_Type, &query_arr, &query_len,
                          &PyArray_Type, &cand_arr,
                          &PyArray_Type, &offsets_arr,
                          &window,
                          &PyArray_Type, &out_arr))
        return NULL;

    double *query = (double *)PyArray_DATA(query_arr);
    double *cands = (double *)PyArray_DATA(cand_arr);
    int *offsets = (int *)PyArray_DATA(offsets_arr);
    double *out = (double *)PyArray_DATA(out_arr);
    n_candidates = (int)PyArray_DIM(offsets_arr, 0) - 1;

    batch_dtw(query, query_len, cands, offsets, n_candidates, window, out);
    Py_RETURN_NONE;
}

/* 方法表 */
static PyMethodDef DtwMethods[] = {
    {"dtw_distance_c", py_dtw_distance_c, METH_VARARGS,
     "DTW distance (C accelerated)"},
    {"dtw_similarity_c", py_dtw_similarity_c, METH_VARARGS,
     "DTW similarity [0,1] (C accelerated)"},
    {"segment_shape_similarity_c", py_segment_shape_similarity_c, METH_VARARGS,
     "Segment shape similarity via edit distance (C accelerated)"},
    {"batch_dtw", py_batch_dtw, METH_VARARGS,
     "Batch DTW distances (C accelerated, workspace reused)"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef dtwmodule = {
    PyModuleDef_HEAD_INIT,
    "_dtw",
    "DTW and edit distance C extension module",
    -1,
    DtwMethods
};

PyMODINIT_FUNC PyInit__dtw(void) {
    import_array();
    return PyModule_Create(&dtwmodule);
}
