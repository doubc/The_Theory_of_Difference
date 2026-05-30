"""tests/test_threshold_proximity_sigmoid.py

验证 threshold_proximity 的 sigmoid 平滑聚合是否正确工作。

对比：
- 旧版（纯几何平均）：当任一阈值远低于目标时，结果趋近 0
- 新版（sigmoid + geo 混合）：给予"接近达标"的部分信用
"""

import sys
import os
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from engine.organizational_density_index import OrganizationalDensityIndex
from engine.six_threshold_detector import SixThresholdResult, ThresholdStatus


def make_threshold_result(values: list, thresholds: list) -> SixThresholdResult:
    """构造一个 SixThresholdResult 用于测试"""
    statuses = [
        ThresholdStatus(
            threshold_id=f"3.{i+1}",
            name=f"threshold_{i}",
            value=float(v),
            threshold=float(t),
            is_met=float(v) >= float(t),
        )
        for i, (v, t) in enumerate(zip(values, thresholds))
    ]
    return SixThresholdResult(
        all_met=all(s.is_met for s in statuses),
        threshold_statuses=statuses,
        n_met=sum(1 for s in statuses if s.is_met),
    )


def test_sigmoid_vs_geometric():
    """对比 sigmoid 混合方案 vs 纯几何平均在不同场景下的表现"""
    odi = OrganizationalDensityIndex()

    # 场景1：所有阈值刚好达标（ratio=1.0）
    result1 = make_threshold_result([1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                                     [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    prox1 = odi._compute_threshold_proximity(result1)
    print(f"场景1（全达标）: proximity={prox1:.4f}  (期望≈0.99)")

    # 场景2：大部分达标，一个略低（5/6 通过）
    result2 = make_threshold_result([1.0, 1.0, 1.0, 1.0, 1.0, 0.5],
                                     [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    prox2 = odi._compute_threshold_proximity(result2)
    print(f"场景2（5/6达标, 1个=0.5）: proximity={prox2:.4f}  (期望>0.5)")

    # 场景3：exp_75 实际数据模拟（多数阈值远低于目标）
    # seed 42: coupling_density=0.72, stability=0.69, firewall=1.0, temporal=1.0,
    #          threshold_proximity=0.0, resonance=0.0
    # 模拟六阈值：假设 A1=0.8达标, A2=0.3未达标, A3=0.6未达标, A4=0.9达标, A5=0.2未达标, A6=0.7未达标
    result3 = make_threshold_result([0.8, 0.3, 0.6, 0.9, 0.2, 0.7],
                                     [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    prox3 = odi._compute_threshold_proximity(result3)
    print(f"场景3（exp_75模拟, 2/6达标）: proximity={prox3:.4f}  (期望>0，旧版=0)")

    # 场景4：全未达标但接近（所有 ratio=0.8）
    result4 = make_threshold_result([0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
                                     [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    prox4 = odi._compute_threshold_proximity(result4)
    print(f"场景4（全=0.8）: proximity={prox4:.4f}  (期望>0.5)")

    # 场景5：全未达标且很低（所有 ratio=0.2）
    result5 = make_threshold_result([0.2, 0.2, 0.2, 0.2, 0.2, 0.2],
                                     [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    prox5 = odi._compute_threshold_proximity(result5)
    print(f"场景5（全=0.2）: proximity={prox5:.4f}  (期望接近0)")

    # 验证：当存在 ratio=0 时，新版应显著优于几何平均
    # 场景6：exp_75 真实瓶颈 — 某些阈值 value=0（几何平均=0）
    result6 = make_threshold_result([0.8, 0.0, 0.6, 0.9, 0.0, 0.7],
                                     [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    prox6 = odi._compute_threshold_proximity(result6)
    print(f"场景6（exp_75真实瓶颈, 2个=0）: proximity={prox6:.4f}  (期望>0，旧版=0)")

    # 对比：纯几何平均在存在 0 时必然=0
    ratios = [0.8, 0.0, 0.6, 0.9, 0.0, 0.7]
    log_sum = sum(np.log(max(r, 1e-10)) for r in ratios)
    geo_mean = np.exp(log_sum / len(ratios))
    print(f"\n对比验证（场景6）:")
    print(f"  纯几何平均: {geo_mean:.6f}  (因含0而坍缩)")
    print(f"  新版混合:   {prox6:.6f}")
    print(f"  增益:       {prox6 - geo_mean:.6f}")
    assert prox6 > geo_mean, f"新版应大于几何平均: {prox6} vs {geo_mean}"
    assert prox6 > 0.1, f"新版应给予部分信用: {prox6}"

    print("\n[PASS] 所有测试通过")


if __name__ == "__main__":
    test_sigmoid_vs_geometric()
