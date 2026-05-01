/*
 * _similarity.c — 核心相似度计算 C 扩展
 *
 * 加速：
 *   1. geometric_distance — 不变量向量归一化欧氏距离
 *   2. batch_geometric — 批量向量距离（候选池 vs 查询）
 *   3. compute_motion_votes — 运动态投票逻辑
 *
 * 编译: python setup.py build_ext --inplace
 */

#include <math.h>
#include <stdlib.h>
#include <string.h>

#define INVARIANT_DIM 10
#define MAX_CYCLES 64

/* ─── 1. 归一化欧氏距离 ─── */

/*
 * 计算两个归一化不变量向量的欧氏距离
 * v1, v2: 长度 n 的向量
 * scales: 每个维度的归一化因子
 * 返回: 欧氏距离 (未归一化到 [0,1])
 */
double geometric_distance(const double *v1, const double *v2,
                          const double *scales, int n) {
    double sum = 0.0;
    for (int i = 0; i < n; i++) {
        double a = v1[i] / (scales[i] > 1e-12 ? scales[i] : 1.0);
        double b = v2[i] / (scales[i] > 1e-12 ? scales[i] : 1.0);
        double d = a - b;
        sum += d * d;
    }
    return sqrt(sum);
}

/*
 * 批量计算: query 向量 vs candidates 矩阵
 * query: [n]
 * candidates: [m × n] (行优先)
 * scales: [n]
 * distances: [m] 输出
 */
void batch_geometric(const double *query, const double *candidates,
                     const double *scales, int n, int m,
                     double *distances) {
    for (int i = 0; i < m; i++) {
        distances[i] = geometric_distance(query, candidates + i * n, scales, n);
    }
}

/* ─── 2. 运动态投票 ─── */

/*
 * compute_motion_votes — 从 cycle 速度比序列计算 phase_tendency
 *
 * speed_ratios: [n_cycles]
 * n_cycles: cycle 数量
 * flux: 守恒通量
 * density_ratio: 试探密集度比 (0 = 不可用)
 * dist_trend: exit 距离趋势 (0 = 不可用)
 *
 * 返回: 写入 tendency (0=→breakout, 1=→confirmation, 2=stable, 3=→inversion, 4=forming)
 *        写入 confidence
 */
void compute_motion_votes(const double *speed_ratios, int n_cycles,
                          double flux, double density_ratio,
                          double dist_trend,
                          int *tendency, double *confidence) {
    if (n_cycles < 1) {
        *tendency = 4;  // forming
        *confidence = 0.3;
        return;
    }

    double votes[5] = {0, 0, 0, 0, 0};  // breakout, confirmation, stable, inversion, forming

    if (n_cycles >= 3) {
        /* 信号 A: 速度比趋势 (权重 0.35) */
        double sr_trend = speed_ratios[n_cycles - 1] - speed_ratios[0];
        if (sr_trend > 0.5) {
            double strength = sr_trend / 2.0;
            if (strength > 1.0) strength = 1.0;
            votes[0] += 0.35 * strength;
        } else if (sr_trend < -0.3) {
            double strength = (-sr_trend) / 1.0;
            if (strength > 1.0) strength = 1.0;
            votes[1] += 0.35 * strength;
        } else {
            /* 检查是否方向翻转 */
            int first_above = speed_ratios[0] > 1.0;
            int last_above = speed_ratios[n_cycles - 1] > 1.0;
            if (first_above != last_above) {
                votes[3] += 0.35 * 0.7;
            } else {
                votes[2] += 0.35 * 0.5;
            }
        }

        /* 信号 B: 试探密集度 (权重 0.25) */
        if (density_ratio > 1.5) {
            double strength = density_ratio / 3.0;
            if (strength > 1.0) strength = 1.0;
            votes[0] += 0.25 * strength;
        } else if (density_ratio > 0.0 && density_ratio < 0.67) {
            votes[1] += 0.25 * 0.5;
        } else if (density_ratio > 0.0) {
            votes[2] += 0.25 * 0.4;
        }

        /* 信号 C: Zone 带宽变化 (权重 0.20) */
        if (dist_trend > 1.0) {
            double strength = dist_trend / 3.0;
            if (strength > 1.0) strength = 1.0;
            votes[0] += 0.20 * strength;
        } else if (dist_trend < -0.5) {
            votes[1] += 0.20 * 0.4;
        }

        /* 信号 D: 守恒通量 (权重 0.20) */
        if (flux > 0.3) {
            double strength = flux;
            if (strength > 1.0) strength = 1.0;
            votes[0] += 0.20 * strength;
        } else if (flux < -0.3) {
            double strength = (-flux);
            if (strength > 1.0) strength = 1.0;
            votes[1] += 0.20 * strength;
        } else {
            votes[2] += 0.20 * 0.3;
        }

        /* 取最高票 */
        int best = 0;
        for (int i = 1; i < 5; i++) {
            if (votes[i] > votes[best]) best = i;
        }
        *tendency = best;
        *confidence = votes[best];
        if (*confidence > 1.0) *confidence = 1.0;
    } else {
        *tendency = 4;  // forming
        *confidence = 0.3;
    }
}

/* ─── 3. 批量规则匹配 ─── */

/*
 * rule_check — 检查单条规则的约束
 * values: [n_fields] 结构不变量值
 * specs_lo, specs_hi: [n_fields] 约束区间 (lo==hi 表示精确匹配, 都为 -999 表示无约束)
 * n_fields: 字段数
 * 返回: 通过的约束数
 */
int rule_check(const double *values, const double *specs_lo,
               const double *specs_hi, int n_fields) {
    int passed = 0;
    for (int i = 0; i < n_fields; i++) {
        if (specs_lo[i] < -900) continue;  // 无约束
        double v = values[i];
        if (v >= specs_lo[i] && v <= specs_hi[i]) {
            passed++;
        }
    }
    return passed;
}
