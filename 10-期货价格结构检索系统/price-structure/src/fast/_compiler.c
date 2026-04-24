/*
 * _compiler.c — 编译器核心 C 加速
 *
 * 替代 pipeline.py / zones.py / features.py 中的热循环。
 *
 * 功能：
 *   1. 二分查找 bar 时间过滤 — O(log n) 替代 O(n) 线性扫描
 *   2. 批量结构不变量计算 — 向量化替代 Python 逐属性调用
 *   3. 批量几何相似度 — 矩阵化欧氏距离
 *   4. 批量关系相似度 — 向量化一致性检查
 *   5. 批量特征提取 — 结构→特征向量
 *   6. Zone 聚类 — 贪心合并
 *
 * 编译：python setup_fast.py build_ext --inplace
 */

#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <float.h>

/* ═══════════════════════════════════════════════════════════
 * 1. 二分查找 — Bar 时间戳过滤
 * ═══════════════════════════════════════════════════════════ */

/*
 * 在已排序的 timestamps 数组中，找到第一个 >= target 的索引
 * 如果所有值都 < target，返回 n
 */
int bsearch_lower_bound(const int64_t *timestamps, int n, int64_t target) {
    int lo = 0, hi = n;
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (timestamps[mid] < target)
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo;
}

/*
 * 在已排序的 timestamps 数组中，找到第一个 > target 的索引
 * 如果所有值都 <= target，返回 n
 */
int bsearch_upper_bound(const int64_t *timestamps, int n, int64_t target) {
    int lo = 0, hi = n;
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (timestamps[mid] <= target)
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo;
}

/*
 * 批量时间窗口过滤 — 一次调用过滤多个窗口
 *
 * 参数：
 *   timestamps    — 已排序的 bar 时间戳（epoch seconds）[n_bars]
 *   n_bars        — bar 数量
 *   win_starts    — 每个窗口的起始时间 [n_windows]
 *   win_ends      — 每个窗口的结束时间 [n_windows]
 *   margins       — 每个窗口的边距（秒）[n_windows]
 *   n_windows     — 窗口数量
 *
 * 输出：
 *   out_starts    — 每个窗口在 timestamps 中的起始索引 [n_windows]
 *   out_ends      — 每个窗口在 timestamps 中的结束索引（不含）[n_windows]
 */
void batch_time_filter(
    const int64_t *timestamps,
    int n_bars,
    const int64_t *win_starts,
    const int64_t *win_ends,
    const int64_t *margins,
    int n_windows,
    int *out_starts,
    int *out_ends
) {
    for (int i = 0; i < n_windows; i++) {
        int64_t lo = win_starts[i] - margins[i];
        int64_t hi = win_ends[i] + margins[i];
        out_starts[i] = bsearch_lower_bound(timestamps, n_bars, lo);
        out_ends[i] = bsearch_upper_bound(timestamps, n_bars, hi);
    }
}

/*
 * 单窗口二分过滤（Python 调用入口）
 *
 * 返回 (start_idx, end_idx)
 */
void binary_filter_bars(
    const int64_t *timestamps,
    int n_bars,
    int64_t t_start,
    int64_t t_end,
    int64_t margin_sec,
    int *out_start,
    int *out_end
) {
    int64_t lo = t_start - margin_sec;
    int64_t hi = t_end + margin_sec;
    *out_start = bsearch_lower_bound(timestamps, n_bars, lo);
    *out_end = bsearch_upper_bound(timestamps, n_bars, hi);
}


/* ═══════════════════════════════════════════════════════════
 * 2. 批量结构不变量计算
 * ═══════════════════════════════════════════════════════════ */

/*
 * 从扁平化的 Cycle 数据批量计算不变量
 *
 * 参数：
 *   speed_ratios   — 每个 cycle 的速度比 [total_cycles]
 *   time_ratios    — 每个 cycle 的时间比 [total_cycles]
 *   log_speed_ratios — 每个 cycle 的对数速度比 [total_cycles]
 *   abs_deltas     — 每个 cycle 的绝对振幅 [total_cycles]
 *   cycle_offsets  — 每个结构的 cycle 起始偏移 [n_structures+1]
 *   n_structures   — 结构数量
 *
 * 输出：
 *   out_avg_sr     — 平均速度比 [n_structures]
 *   out_avg_tr     — 平均时间比 [n_structures]
 *   out_avg_lsr    — 平均对数速度比 [n_structures]
 *   out_std_sr     — 速度比标准差 [n_structures]
 *   out_cycle_count — cycle 数量 [n_structures]
 */
void batch_structure_invariants(
    const double *speed_ratios,
    const double *time_ratios,
    const double *log_speed_ratios,
    const double *abs_deltas,
    const int *cycle_offsets,
    int n_structures,
    double *out_avg_sr,
    double *out_avg_tr,
    double *out_avg_lsr,
    double *out_std_sr,
    int *out_cycle_count
) {
    for (int s = 0; s < n_structures; s++) {
        int start = cycle_offsets[s];
        int end = cycle_offsets[s + 1];
        int n = end - start;

        out_cycle_count[s] = n;

        if (n == 0) {
            out_avg_sr[s] = 0.0;
            out_avg_tr[s] = 0.0;
            out_avg_lsr[s] = 0.0;
            out_std_sr[s] = 0.0;
            continue;
        }

        double sum_sr = 0, sum_tr = 0, sum_lsr = 0;
        double sum_sr2 = 0;
        for (int i = start; i < end; i++) {
            double sr = speed_ratios[i];
            sum_sr += sr;
            sum_sr2 += sr * sr;
            sum_tr += time_ratios[i];
            sum_lsr += log_speed_ratios[i];
        }

        double inv_n = 1.0 / n;
        double avg_sr = sum_sr * inv_n;
        out_avg_sr[s] = avg_sr;
        out_avg_tr[s] = sum_tr * inv_n;
        out_avg_lsr[s] = sum_lsr * inv_n;

        double var = sum_sr2 * inv_n - avg_sr * avg_sr;
        out_std_sr[s] = var > 0 ? sqrt(var) : 0.0;
    }
}


/* ═══════════════════════════════════════════════════════════
 * 3. 批量几何相似度 — 向量化欧氏距离
 * ═══════════════════════════════════════════════════════════ */

/*
 * 一个查询向量 vs N 个候选向量的归一化欧氏距离相似度
 *
 * 参数：
 *   q_vec          — 查询不变量向量 [dim]
 *   c_matrix       — 候选不变量矩阵 [n_candidates * dim]
 *   dim            — 向量维度
 *   n_candidates   — 候选数量
 *
 * 输出：
 *   out_scores     — 相似度 [n_candidates]，1 = 完全相同，0 = 完全不同
 */
void batch_geometric_similarity(
    const double *q_vec,
    const double *c_matrix,
    int dim,
    int n_candidates,
    double *out_scores
) {
    double inv_sqrt_dim = 1.0 / sqrt((double)dim);

    for (int i = 0; i < n_candidates; i++) {
        const double *c_vec = c_matrix + i * dim;
        double sum = 0.0;
        for (int d = 0; d < dim; d++) {
            double diff = q_vec[d] - c_vec[d];
            sum += diff * diff;
        }
        double dist = sqrt(sum);
        double sim = 1.0 - dist * inv_sqrt_dim;
        out_scores[i] = sim < 0.0 ? 0.0 : sim;
    }
}


/* ═══════════════════════════════════════════════════════════
 * 4. 批量关系相似度
 * ═══════════════════════════════════════════════════════════ */

/*
 * 关系相似度：zone_source, cycle_count, speed_ratio_dir, time_ratio_dir
 *
 * 参数：
 *   q_rel          — 查询关系特征 [4]: (zone_source, cycle_count, sr_dir, tr_dir)
 *   c_rel          — 候选关系特征 [n_candidates * 4]
 *   n_candidates   — 候选数量
 *
 * 输出：
 *   out_scores     — 关系相似度 [n_candidates]
 */
void batch_relational_similarity(
    const double *q_rel,
    const double *c_rel,
    int n_candidates,
    double *out_scores
) {
    double q_zone = q_rel[0];
    double q_cycles = q_rel[1];
    double q_sr = q_rel[2];
    double q_tr = q_rel[3];

    for (int i = 0; i < n_candidates; i++) {
        const double *cr = c_rel + i * 4;
        double score = 0.0;

        /* Zone source 一致 */
        if (q_zone == cr[0]) score += 0.25;

        /* Cycle count 相近 */
        double dn = q_cycles - cr[1];
        if (dn < 0) dn = -dn;
        double cyc_sim = 1.0 - dn / 5.0;
        if (cyc_sim < 0) cyc_sim = 0;
        score += cyc_sim * 0.25;

        /* 速度比方向一致 */
        if ((q_sr > 1.0) == (cr[2] > 1.0)) score += 0.25;

        /* 时间比方向一致 */
        if ((q_tr > 1.0) == (cr[3] > 1.0)) score += 0.25;

        out_scores[i] = score;
    }
}


/* ═══════════════════════════════════════════════════════════
 * 5. 批量运动相似度
 * ═══════════════════════════════════════════════════════════ */

/*
 * 运动相似度：phase_tendency, flux, stable_distance, contrast_type
 *
 * 参数：
 *   q_mot          — 查询运动特征 [4]
 *   c_mot          — 候选运动特征 [n_candidates * 4]
 *   n_candidates   — 候选数量
 *
 * 输出：
 *   out_scores     — 运动相似度 [n_candidates]
 */
void batch_motion_similarity(
    const double *q_mot,
    const double *c_mot,
    int n_candidates,
    double *out_scores
) {
    double q_phase = q_mot[0];
    double q_flux = q_mot[1];
    double q_stable = q_mot[2];
    double q_contrast = q_mot[3];

    for (int i = 0; i < n_candidates; i++) {
        const double *cm = c_mot + i * 4;
        double score = 0.0;

        /* 阶段趋势一致 */
        if (q_phase == cm[0]) {
            score += 0.25;
        } else {
            /* 都含 breakdown 或都不含 */
            int q_bd = (q_phase > 0.5);  /* 简化：>0.5 表示 breakdown 方向 */
            int c_bd = (cm[0] > 0.5);
            if (q_bd == c_bd) score += 0.125;
        }

        /* 守恒通量方向一致 */
        double flux_prod = q_flux * cm[1];
        if (flux_prod > 0) {
            score += 0.25;
        } else if (fabs(q_flux) < 0.1 && fabs(cm[1]) < 0.1) {
            score += 0.2;
        }

        /* 稳态距离相近 */
        double dd = q_stable - cm[2];
        if (dd < 0) dd = -dd;
        score += (1.0 - dd) * 0.25;
        if (score < 0) score = 0;  /* clamp */

        /* 反差类型一致 */
        if (q_contrast == cm[3]) {
            score += 0.25;
        } else if (q_contrast == 0 || cm[3] == 0) {
            score += 0.125;
        }

        out_scores[i] = score;
    }
}


/* ═══════════════════════════════════════════════════════════
 * 6. 综合相似度 — 一层调用完成四层评分
 * ═══════════════════════════════════════════════════════════ */

/*
 * 综合相似度：几何 + 关系 + 运动 + 族
 *
 * 参数：
 *   q_geo, c_geo       — 几何不变量 [dim], [n * dim]
 *   q_rel, c_rel       — 关系特征 [4], [n * 4]
 *   q_mot, c_mot       — 运动特征 [4], [n * 4]
 *   family_scores      — 族相似度 [n]（由 Python 端预计算）
 *   dim                — 不变量维度
 *   n                  — 候选数量
 *   w_geo, w_rel, w_mot, w_fam — 权重
 *
 * 输出：
 *   out_scores         — 综合相似度 [n]
 */
void batch_total_similarity(
    const double *q_geo,
    const double *c_geo,
    const double *q_rel,
    const double *c_rel,
    const double *q_mot,
    const double *c_mot,
    const double *family_scores,
    int dim,
    int n,
    double w_geo,
    double w_rel,
    double w_mot,
    double w_fam,
    double *out_scores
) {
    /* 分配临时数组 */
    double *geo_scores = (double *)malloc(n * sizeof(double));
    double *rel_scores = (double *)malloc(n * sizeof(double));
    double *mot_scores = (double *)malloc(n * sizeof(double));

    if (!geo_scores || !rel_scores || !mot_scores) {
        free(geo_scores);
        free(rel_scores);
        free(mot_scores);
        /* fallback: 均为 0 */
        for (int i = 0; i < n; i++) out_scores[i] = 0;
        return;
    }

    batch_geometric_similarity(q_geo, c_geo, dim, n, geo_scores);
    batch_relational_similarity(q_rel, c_rel, n, rel_scores);
    batch_motion_similarity(q_mot, c_mot, n, mot_scores);

    for (int i = 0; i < n; i++) {
        out_scores[i] = w_geo * geo_scores[i]
                      + w_rel * rel_scores[i]
                      + w_mot * mot_scores[i]
                      + w_fam * family_scores[i];
    }

    free(geo_scores);
    free(rel_scores);
    free(mot_scores);
}


/* ═══════════════════════════════════════════════════════════
 * 7. Zone 聚类 — 贪心合并
 * ═══════════════════════════════════════════════════════════ */

/*
 * 基于价格排序的贪心聚类
 *
 * 参数：
 *   prices     — 已排序的价格数组 [n]
 *   indices    — 对应的原始索引 [n]
 *   n          — 点数
 *   eps        — 相对容差（如 0.015 = 1.5%）
 *   min_pts    — 最小聚类点数
 *
 * 输出：
 *   labels     — 每个点的聚类标签 [n]，-1 = 未分配
 *
 * 返回：聚类数量
 */
int cluster_by_price(
    const double *prices,
    const int *indices,
    int n,
    double eps,
    int min_pts,
    int *labels
) {
    if (n == 0) return 0;

    for (int i = 0; i < n; i++) labels[i] = -1;

    int cluster_id = 0;
    int cluster_start = 0;

    for (int i = 1; i <= n; i++) {
        int end_of_cluster = (i == n);
        if (!end_of_cluster) {
            /* 检查是否应该合并到当前簇 */
            double center = 0;
            for (int j = cluster_start; j < i; j++) center += prices[j];
            center /= (i - cluster_start);
            double tol = center * eps;

            if (prices[i] - prices[i - 1] > tol) {
                end_of_cluster = 1;
            }
        }

        if (end_of_cluster) {
            int cluster_size = i - cluster_start;
            if (cluster_size >= min_pts) {
                for (int j = cluster_start; j < i; j++) {
                    labels[j] = cluster_id;
                }
                cluster_id++;
            }
            cluster_start = i;
        }
    }

    return cluster_id;
}


/* ═══════════════════════════════════════════════════════════
 * 8. 特征提取 — 批量
 * ═══════════════════════════════════════════════════════════ */

/*
 * 从扁平 Cycle 数据批量提取结构特征向量
 *
 * 特征维度 = 13（与 features.py 对齐）
 *
 * 参数：
 *   speed_ratios, time_ratios, log_speed_ratios, amplitude_ratios
 *   abs_deltas_entry, abs_deltas_exit, durations_entry, durations_exit
 *   directions_entry    — entry 段方向 (1=UP, -1=DOWN)
 *   cycle_offsets       — [n_structures+1]
 *   n_structures
 *   zone_bw_rel         — 每个结构的 zone 相对带宽 [n_structures]
 *   zone_strength       — 每个结构的 zone 强度 [n_structures]
 *   high_cluster_cv     — 每个结构的高点聚集度 [n_structures]
 *
 * 输出：
 *   out_features        — [n_structures * 13]
 */
#define FEATURE_DIM 13

void batch_extract_features(
    const double *speed_ratios,
    const double *time_ratios,
    const double *log_speed_ratios,
    const double *amplitude_ratios,
    const double *abs_deltas_entry,
    const double *abs_deltas_exit,
    const double *durations_entry,
    const double *durations_exit,
    const int *directions_entry,
    const int *cycle_offsets,
    int n_structures,
    const double *zone_bw_rel,
    const double *zone_strength,
    const double *high_cluster_cv,
    double *out_features
) {
    for (int s = 0; s < n_structures; s++) {
        int start = cycle_offsets[s];
        int end = cycle_offsets[s + 1];
        int n = end - start;
        double *feat = out_features + s * FEATURE_DIM;

        if (n == 0) {
            for (int d = 0; d < FEATURE_DIM; d++) feat[d] = 0;
            continue;
        }

        double sum_sr = 0, sum_tr = 0, sum_lsr = 0, sum_ar = 0;
        double sum_sr2 = 0, sum_tr2 = 0;
        double total_dur = 0, total_abs = 0;
        int up_count = 0;

        for (int i = start; i < end; i++) {
            double sr = speed_ratios[i];
            double tr = time_ratios[i];
            sum_sr += sr;
            sum_tr += tr;
            sum_lsr += log_speed_ratios[i];
            sum_ar += amplitude_ratios[i];
            sum_sr2 += sr * sr;
            sum_tr2 += tr * tr;
            total_abs += abs_deltas_entry[i] + abs_deltas_exit[i];
            total_dur += durations_entry[i] + durations_exit[i];
            if (directions_entry[i] > 0) up_count++;
        }

        double inv_n = 1.0 / n;
        double avg_sr = sum_sr * inv_n;
        double avg_tr = sum_tr * inv_n;

        double var_sr = sum_sr2 * inv_n - avg_sr * avg_sr;
        double var_tr = sum_tr2 * inv_n - avg_tr * avg_tr;

        int all_segs = n * 2;  /* entry + exit per cycle */

        feat[0]  = (double)n;                          /* cycle_count */
        feat[1]  = total_dur;                          /* total_duration_days */
        feat[2]  = avg_sr;                             /* avg_speed_ratio */
        feat[3]  = avg_tr;                             /* avg_time_ratio */
        feat[4]  = var_sr > 0 ? sqrt(var_sr) : 0;     /* std_speed_ratio */
        feat[5]  = var_tr > 0 ? sqrt(var_tr) : 0;     /* std_time_ratio */
        feat[6]  = sum_lsr * inv_n;                    /* avg_log_speed_ratio */
        feat[7]  = high_cluster_cv[s];                 /* high_cluster_cv */
        feat[8]  = zone_bw_rel[s];                     /* zone_relative_bandwidth */
        feat[9]  = zone_strength[s];                   /* zone_strength */
        feat[10] = sum_ar * inv_n;                     /* avg_amplitude_ratio */
        feat[11] = total_abs;                          /* total_abs_delta */
        feat[12] = all_segs > 0 ? (double)up_count / all_segs : 0.5; /* up_segment_ratio */
    }
}


/* ═══════════════════════════════════════════════════════════
 * Python C API 绑定
 * ═══════════════════════════════════════════════════════════ */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <numpy/arrayobject.h>

/* ── binary_filter_bars ── */
static PyObject* py_binary_filter_bars(PyObject* self, PyObject* args) {
    PyArrayObject *ts_arr;
    long long t_start, t_end, margin;

    if (!PyArg_ParseTuple(args, "O!LLL",
                          &PyArray_Type, &ts_arr,
                          &t_start, &t_end, &margin))
        return NULL;

    int n = (int)PyArray_DIM(ts_arr, 0);
    int64_t *timestamps = (int64_t *)PyArray_DATA(ts_arr);

    int out_start, out_end;
    binary_filter_bars(timestamps, n, t_start, t_end, margin, &out_start, &out_end);

    return Py_BuildValue("(ii)", out_start, out_end);
}

/* ── batch_geometric_similarity ── */
static PyObject* py_batch_geometric_similarity(PyObject* self, PyObject* args) {
    PyArrayObject *q_arr, *c_arr, *out_arr;
    int dim, n;

    if (!PyArg_ParseTuple(args, "O!O!iiO!",
                          &PyArray_Type, &q_arr,
                          &PyArray_Type, &c_arr,
                          &dim, &n,
                          &PyArray_Type, &out_arr))
        return NULL;

    double *q = (double *)PyArray_DATA(q_arr);
    double *c = (double *)PyArray_DATA(c_arr);
    double *out = (double *)PyArray_DATA(out_arr);

    batch_geometric_similarity(q, c, dim, n, out);
    Py_RETURN_NONE;
}

/* ── batch_total_similarity ── */
static PyObject* py_batch_total_similarity(PyObject* self, PyObject* args) {
    PyArrayObject *q_geo, *c_geo, *q_rel, *c_rel, *q_mot, *c_mot, *fam, *out_arr;
    int dim, n;
    double w_geo, w_rel, w_mot, w_fam;

    if (!PyArg_ParseTuple(args, "O!O!O!O!O!O!O!iddO!d",
                          &PyArray_Type, &q_geo,
                          &PyArray_Type, &c_geo,
                          &PyArray_Type, &q_rel,
                          &PyArray_Type, &c_rel,
                          &PyArray_Type, &q_mot,
                          &PyArray_Type, &c_mot,
                          &PyArray_Type, &fam,
                          &dim, &n,
                          &w_geo, &w_rel, &w_mot,
                          &PyArray_Type, &out_arr,
                          &w_fam))
        return NULL;

    batch_total_similarity(
        (double *)PyArray_DATA(q_geo),
        (double *)PyArray_DATA(c_geo),
        (double *)PyArray_DATA(q_rel),
        (double *)PyArray_DATA(c_rel),
        (double *)PyArray_DATA(q_mot),
        (double *)PyArray_DATA(c_mot),
        (double *)PyArray_DATA(fam),
        dim, n, w_geo, w_rel, w_mot, w_fam,
        (double *)PyArray_DATA(out_arr)
    );
    Py_RETURN_NONE;
}

/* ── batch_extract_features ── */
static PyObject* py_batch_extract_features(PyObject* self, PyObject* args) {
    PyArrayObject *sr_arr, *tr_arr, *lsr_arr, *ar_arr;
    PyArrayObject *ade_arr, *adx_arr, *due_arr, *dux_arr, *dir_arr;
    PyArrayObject *offsets_arr, *bw_arr, *str_arr, *cv_arr, *out_arr;
    int n_structures;

    if (!PyArg_ParseTuple(args, "O!O!O!O!O!O!O!O!O!O!iO!O!O!O!",
                          &PyArray_Type, &sr_arr,
                          &PyArray_Type, &tr_arr,
                          &PyArray_Type, &lsr_arr,
                          &PyArray_Type, &ar_arr,
                          &PyArray_Type, &ade_arr,
                          &PyArray_Type, &adx_arr,
                          &PyArray_Type, &due_arr,
                          &PyArray_Type, &dux_arr,
                          &PyArray_Type, &dir_arr,
                          &PyArray_Type, &offsets_arr,
                          &n_structures,
                          &PyArray_Type, &bw_arr,
                          &PyArray_Type, &str_arr,
                          &PyArray_Type, &cv_arr,
                          &PyArray_Type, &out_arr))
        return NULL;

    batch_extract_features(
        (double *)PyArray_DATA(sr_arr),
        (double *)PyArray_DATA(tr_arr),
        (double *)PyArray_DATA(lsr_arr),
        (double *)PyArray_DATA(ar_arr),
        (double *)PyArray_DATA(ade_arr),
        (double *)PyArray_DATA(adx_arr),
        (double *)PyArray_DATA(due_arr),
        (double *)PyArray_DATA(dux_arr),
        (int *)PyArray_DATA(dir_arr),
        (int *)PyArray_DATA(offsets_arr),
        n_structures,
        (double *)PyArray_DATA(bw_arr),
        (double *)PyArray_DATA(str_arr),
        (double *)PyArray_DATA(cv_arr),
        (double *)PyArray_DATA(out_arr)
    );
    Py_RETURN_NONE;
}

/* ── batch_structure_invariants ── */
static PyObject* py_batch_structure_invariants(PyObject* self, PyObject* args) {
    PyArrayObject *sr_arr, *tr_arr, *lsr_arr, *ad_arr, *off_arr;
    PyArrayObject *out_sr, *out_tr, *out_lsr, *out_std, *out_cnt;
    int n_structures;

    if (!PyArg_ParseTuple(args, "O!O!O!O!O!iO!O!O!O!O!",
                          &PyArray_Type, &sr_arr,
                          &PyArray_Type, &tr_arr,
                          &PyArray_Type, &lsr_arr,
                          &PyArray_Type, &ad_arr,
                          &PyArray_Type, &off_arr,
                          &n_structures,
                          &PyArray_Type, &out_sr,
                          &PyArray_Type, &out_tr,
                          &PyArray_Type, &out_lsr,
                          &PyArray_Type, &out_std,
                          &PyArray_Type, &out_cnt))
        return NULL;

    batch_structure_invariants(
        (double *)PyArray_DATA(sr_arr),
        (double *)PyArray_DATA(tr_arr),
        (double *)PyArray_DATA(lsr_arr),
        (double *)PyArray_DATA(ad_arr),
        (int *)PyArray_DATA(off_arr),
        n_structures,
        (double *)PyArray_DATA(out_sr),
        (double *)PyArray_DATA(out_tr),
        (double *)PyArray_DATA(out_lsr),
        (double *)PyArray_DATA(out_std),
        (int *)PyArray_DATA(out_cnt)
    );
    Py_RETURN_NONE;
}

/* 方法表 */
static PyMethodDef CompilerMethods[] = {
    {"binary_filter_bars", py_binary_filter_bars, METH_VARARGS,
     "Binary search bar filtering by timestamp range"},
    {"batch_geometric_similarity", py_batch_geometric_similarity, METH_VARARGS,
     "Batch geometric similarity (vectorized Euclidean)"},
    {"batch_total_similarity", py_batch_total_similarity, METH_VARARGS,
     "Batch total similarity (geo+rel+motion+family)"},
    {"batch_extract_features", py_batch_extract_features, METH_VARARGS,
     "Batch feature extraction from cycle data"},
    {"batch_structure_invariants", py_batch_structure_invariants, METH_VARARGS,
     "Batch structure invariant computation"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef compilermodule = {
    PyModuleDef_HEAD_INIT,
    "_compiler",
    "Compiler core C acceleration",
    -1,
    CompilerMethods
};

PyMODINIT_FUNC PyInit__compiler(void) {
    import_array();
    return PyModule_Create(&compilermodule);
}
