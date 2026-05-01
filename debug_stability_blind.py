"""
调试脚本：稳定性检测和盲区检测失效问题

调试目标：
1. 为什么 90.6% 结构的稳定性状态为 "unknown"？
2. 为什么所有盲区占比为 0%？

调试方案：
1. 设计一个最小测试用例（单个品种，少量bars）
2. 在关键位置添加打印/断点
3. 验证数据是否在传递过程中丢失
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.data.loader import Bar
from src.compiler.pipeline import compile_full, CompilerConfig
from src.relations import (
    detect_stability_illusion,
    build_system_state,
    compute_projection,
    compute_motion,
    check_conservation,
)
from src.models import Structure, StabilityVerdict, SystemState
from src.signals import generate_signal


# ═══════════════════════════════════════════════════════════
# 最小测试用例数据（模拟一个典型的价格结构）
# ═══════════════════════════════════════════════════════════

def create_test_bars() -> list[Bar]:
    """
    创建一个最小测试数据集：模拟一个具有明显Zone结构的价格序列
    
    场景：价格在100-110区间形成Zone，有多次试探
    """
    bars = []
    base_price = 100.0
    start_date = datetime(2024, 1, 1)
    
    # 生成60天的测试数据，形成明显的Zone结构
    prices = [
        # 第1-10天：形成第一个高点区域（105-108）
        102, 105, 107, 106, 108, 105, 107, 106, 104, 102,
        # 第11-20天：回落形成低点区域（98-100）
        100, 99, 98, 99, 100, 101, 100, 99, 100, 102,
        # 第21-30天：再次试探高点区域
        104, 106, 107, 108, 106, 107, 105, 104, 103, 102,
        # 第31-40天：再次回落
        101, 100, 99, 100, 101, 100, 99, 98, 99, 100,
        # 第41-50天：第三次试探高点（形成3次cycle的结构）
        103, 105, 106, 107, 108, 107, 106, 105, 104, 103,
        # 第51-60天：窄幅震荡，Zone压缩（高压缩场景）
        104, 105, 104, 105, 106, 105, 104, 105, 104, 105,
    ]
    
    for i, price in enumerate(prices):
        bar = Bar(
            timestamp=start_date + timedelta(days=i),
            symbol="TEST",
            open=price - 0.5,
            high=price + 1.0,
            low=price - 1.0,
            close=price,
            volume=1000000 + (i % 10) * 100000,  # 变化的交易量
        )
        bars.append(bar)
    
    return bars


# ═══════════════════════════════════════════════════════════
# 关键检查点函数
# ═══════════════════════════════════════════════════════════

def checkpoint_1_detect_stability_illusion(structure: Structure, bars: list[Bar]) -> dict:
    """
    检查点1：detect_stability_illusion 返回值
    
    预期：
    - 如果Zone带宽 < 1.5%，surface 应该为 "stable"
    - verified 字段应该根据 pending_channels 设置
    - verdict_label 应该包含红绿灯状态
    
    实际：记录所有字段值
    """
    print("\n" + "="*60)
    print("检查点1：detect_stability_illusion 返回值")
    print("="*60)
    
    verdict = detect_stability_illusion(structure, bars)
    
    result = {
        "surface": verdict.surface,
        "verified": verdict.verified,
        "verification_window": verdict.verification_window,
        "pending_channels": verdict.pending_channels,
        "verdict_label": verdict.verdict_label,
        "traffic_light": verdict.traffic_light,
    }
    
    print(f"  surface: {verdict.surface}")
    print(f"  verified: {verdict.verified}")
    print(f"  verification_window: {verdict.verification_window}")
    print(f"  pending_channels: {verdict.pending_channels}")
    print(f"  verdict_label: {verdict.verdict_label}")
    print(f"  traffic_light: {verdict.traffic_light}")
    
    # 诊断信息
    print("\n  诊断信息:")
    print(f"    Zone相对带宽: {structure.zone.relative_bandwidth:.4f}")
    print(f"    is_surface_stable阈值: < 0.015")
    print(f"    cycles数量: {len(structure.cycles)}")
    
    return result


def checkpoint_2_build_system_state(structure: Structure, bars: list[Bar]) -> dict:
    """
    检查点2：build_system_state 中 s.stability_verdict 赋值后
    
    预期：
    - s.stability_verdict 应该被正确赋值
    - 返回的 SystemState.stability 应该与 structure.stability_verdict 一致
    
    实际：记录赋值前后的状态
    """
    print("\n" + "="*60)
    print("检查点2：build_system_state 中 stability_verdict 赋值")
    print("="*60)
    
    # 记录赋值前状态
    print("\n  赋值前:")
    print(f"    structure.stability_verdict: {structure.stability_verdict}")
    
    # 执行 build_system_state
    ss = build_system_state(structure, bars)
    
    # 记录赋值后状态
    print("\n  赋值后:")
    print(f"    structure.stability_verdict: {structure.stability_verdict}")
    print(f"    system_state.stability: {ss.stability}")
    
    # 检查一致性
    if structure.stability_verdict and ss.stability:
        match = (
            structure.stability_verdict.surface == ss.stability.surface and
            structure.stability_verdict.verified == ss.stability.verified
        )
        print(f"\n  一致性检查: {'✓ 通过' if match else '✗ 不一致'}")
    else:
        print(f"\n  一致性检查: ✗ 存在None值")
        match = False
    
    return {
        "structure_stability": structure.stability_verdict.to_dict() if structure.stability_verdict else None,
        "system_state_stability": ss.stability.to_dict(),
        "consistent": match,
    }


def checkpoint_3_compile_full_return(bars: list[Bar]) -> dict:
    """
    检查点3：compile_full 返回的 structures
    
    预期：
    - structures 列表不为空
    - 每个 structure 应该有 stability_verdict 字段
    - 每个 structure 应该有 projection 字段
    
    实际：记录所有结构的这些字段
    """
    print("\n" + "="*60)
    print("检查点3：compile_full 返回的 structures")
    print("="*60)
    
    config = CompilerConfig(
        min_amplitude=0.01,
        min_duration=2,
        noise_filter=0.005,
        zone_bandwidth=0.02,
    )
    
    result = compile_full(bars, config=config, symbol="TEST")
    
    print(f"\n  编译结果统计:")
    print(f"    bars数量: {result.bars_count}")
    print(f"    pivots数量: {len(result.pivots)}")
    print(f"    segments数量: {len(result.segments)}")
    print(f"    zones数量: {len(result.zones)}")
    print(f"    cycles数量: {len(result.cycles)}")
    print(f"    structures数量: {len(result.structures)}")
    print(f"    system_states数量: {len(result.system_states)}")
    
    structures_info = []
    
    print(f"\n  各结构的稳定性状态:")
    for i, (st, ss) in enumerate(zip(result.structures, result.system_states)):
        info = {
            "index": i,
            "cycle_count": st.cycle_count,
            "has_stability_verdict": st.stability_verdict is not None,
            "has_projection": st.projection is not None,
            "stability_surface": st.stability_verdict.surface if st.stability_verdict else None,
            "stability_verified": st.stability_verdict.verified if st.stability_verdict else None,
            "projection_is_blind": st.projection.is_blind if st.projection else None,
            "ss_stability_surface": ss.stability.surface if ss.stability else None,
            "zone_relative_bandwidth": st.zone.relative_bandwidth,
        }
        structures_info.append(info)
        
        print(f"\n    Structure {i}:")
        print(f"      cycles: {st.cycle_count}")
        print(f"      has_stability_verdict: {info['has_stability_verdict']}")
        print(f"      has_projection: {info['has_projection']}")
        print(f"      stability_surface: {info['stability_surface']}")
        print(f"      stability_verified: {info['stability_verified']}")
        print(f"      projection_is_blind: {info['projection_is_blind']}")
        print(f"      zone_relative_bandwidth: {info['zone_relative_bandwidth']:.4f}")
    
    # 统计
    total = len(result.structures)
    with_stability = sum(1 for s in result.structures if s.stability_verdict is not None)
    with_projection = sum(1 for s in result.structures if s.projection is not None)
    stable_count = sum(1 for s in result.structures 
                      if s.stability_verdict and s.stability_verdict.surface == "stable")
    verified_count = sum(1 for s in result.structures 
                        if s.stability_verdict and s.stability_verdict.verified)
    blind_count = sum(1 for s in result.structures 
                     if s.projection and s.projection.is_blind)
    
    print(f"\n  统计:")
    print(f"    有stability_verdict: {with_stability}/{total} ({with_stability/total*100:.1f}%)")
    print(f"    有projection: {with_projection}/{total} ({with_projection/total*100:.1f}%)")
    print(f"    surface=stable: {stable_count}/{total} ({stable_count/total*100:.1f}%)")
    print(f"    verified=True: {verified_count}/{total} ({verified_count/total*100:.1f}%)")
    print(f"    is_blind=True: {blind_count}/{total} ({blind_count/total*100:.1f}%)")
    
    return {
        "total_structures": total,
        "with_stability_verdict": with_stability,
        "with_projection": with_projection,
        "stable_count": stable_count,
        "verified_count": verified_count,
        "blind_count": blind_count,
        "structures_detail": structures_info,
    }


def checkpoint_4_generate_signal_receives(st: Structure, bars: list[Bar]) -> dict:
    """
    检查点4：generate_signal 接收的 ss.stability
    
    预期：
    - generate_signal 应该正确接收到 system_state
    - ss.stability 应该有正确的值
    
    实际：记录 generate_signal 中接收到的值
    """
    print("\n" + "="*60)
    print("检查点4：generate_signal 接收的 ss.stability")
    print("="*60)
    
    # 先构建 system_state
    ss = build_system_state(st, bars)
    
    print(f"\n  传入 generate_signal 的 system_state:")
    print(f"    ss.stability: {ss.stability}")
    print(f"    ss.stability.surface: {ss.stability.surface if ss.stability else None}")
    print(f"    ss.stability.verified: {ss.stability.verified if ss.stability else None}")
    print(f"    ss.projection.is_blind: {ss.projection.is_blind if ss.projection else None}")
    
    # 调用 generate_signal
    signal = generate_signal(st, bars, ss)
    
    print(f"\n  generate_signal 返回:")
    print(f"    signal: {signal}")
    
    return {
        "input_stability_surface": ss.stability.surface if ss.stability else None,
        "input_stability_verified": ss.stability.verified if ss.stability else None,
        "input_projection_is_blind": ss.projection.is_blind if ss.projection else None,
        "signal_generated": signal is not None,
        "signal_kind": signal.kind.value if signal else None,
        "signal_stability_ok": signal.stability_ok if signal else None,
        "signal_is_blind": signal.is_blind if signal else None,
    }


def checkpoint_5_data_flow_analysis() -> dict:
    """
    检查点5：数据流分析 - 检查 pipeline 中 system_states 的构建流程
    
    重点检查 compile_full 中 system_states 的构建是否正确
    """
    print("\n" + "="*60)
    print("检查点5：compile_full 中 system_states 构建流程分析")
    print("="*60)
    
    bars = create_test_bars()
    config = CompilerConfig()
    
    result = compile_full(bars, config=config, symbol="TEST")
    
    print(f"\n  分析 compile_full 中的 system_states 构建:")
    print(f"    structures数量: {len(result.structures)}")
    print(f"    system_states数量: {len(result.system_states)}")
    
    # 检查每个 system_state 的完整性
    issues = []
    for i, (st, ss) in enumerate(zip(result.structures, result.system_states)):
        if ss.stability is None:
            issues.append(f"system_states[{i}].stability is None")
        elif ss.stability.surface == "unstable" and st.stability_verdict and st.stability_verdict.surface == "stable":
            issues.append(f"system_states[{i}] 与 structure 的 stability 不一致")
        
        if ss.projection is None:
            issues.append(f"system_states[{i}].projection is None")
    
    if issues:
        print(f"\n  发现的问题:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print(f"\n  未发现明显问题")
    
    return {
        "structures_count": len(result.structures),
        "system_states_count": len(result.system_states),
        "issues": issues,
    }


# ═══════════════════════════════════════════════════════════
# 预期 vs 实际对比方法
# ═══════════════════════════════════════════════════════════

def compare_expected_vs_actual(checkpoint_results: dict):
    """
    对比预期值和实际值，生成诊断报告
    """
    print("\n" + "="*60)
    print("预期 vs 实际对比报告")
    print("="*60)
    
    # 检查点3的统计对比
    cp3 = checkpoint_results.get("checkpoint_3", {})
    total = cp3.get("total_structures", 0)
    
    if total > 0:
        print(f"\n稳定性状态分布:")
        print(f"  预期: 大部分结构应该有明确的 stability_verdict")
        print(f"  实际: {cp3.get('with_stability_verdict', 0)}/{total} 有 stability_verdict")
        
        stable_pct = cp3.get('stable_count', 0) / total * 100
        print(f"\n  预期: 带宽压缩的结构应该有 surface='stable'")
        print(f"  实际: {cp3.get('stable_count', 0)}/{total} ({stable_pct:.1f}%) surface='stable'")
        
        if stable_pct < 10:
            print(f"  ⚠️ 警告: stable 比例过低，可能存在bug")
        
        blind_pct = cp3.get('blind_count', 0) / total * 100
        print(f"\n盲区检测:")
        print(f"  预期: 高压缩结构应该有 is_blind=True")
        print(f"  实际: {cp3.get('blind_count', 0)}/{total} ({blind_pct:.1f}%) is_blind=True")
        
        if blind_pct == 0 and total > 0:
            print(f"  ⚠️ 警告: 盲区检测可能失效，所有结构的 is_blind 都是 False")
    
    # 检查点2的一致性对比
    cp2 = checkpoint_results.get("checkpoint_2", {})
    if not cp2.get("consistent", True):
        print(f"\n⚠️ 严重: structure.stability_verdict 与 system_state.stability 不一致!")
        print(f"  这会导致信号生成时获取到错误的稳定性状态")


# ═══════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════

def main():
    print("="*60)
    print("稳定性检测和盲区检测失效调试脚本")
    print("="*60)
    
    # 创建测试数据
    bars = create_test_bars()
    print(f"\n创建测试数据: {len(bars)} 根K线")
    
    # 先编译获取结构
    config = CompilerConfig(
        min_amplitude=0.01,
        min_duration=2,
        noise_filter=0.005,
        zone_bandwidth=0.02,
    )
    result = compile_full(bars, config=config, symbol="TEST")
    
    if not result.structures:
        print("\n错误: 没有编译出任何结构，请调整测试数据或配置")
        return
    
    # 选择第一个结构进行详细检查
    test_structure = result.structures[0]
    print(f"\n选择测试结构: {test_structure}")
    
    # 执行各个检查点
    results = {}
    
    # 检查点1: detect_stability_illusion 返回值
    results["checkpoint_1"] = checkpoint_1_detect_stability_illusion(test_structure, bars)
    
    # 检查点2: build_system_state 中 stability_verdict 赋值
    # 需要先重置 structure，因为检查点1可能已经修改了它
    result2 = compile_full(bars, config=config, symbol="TEST")
    test_structure2 = result2.structures[0]
    results["checkpoint_2"] = checkpoint_2_build_system_state(test_structure2, bars)
    
    # 检查点3: compile_full 返回的 structures
    results["checkpoint_3"] = checkpoint_3_compile_full_return(bars)
    
    # 检查点4: generate_signal 接收的 ss.stability
    result4 = compile_full(bars, config=config, symbol="TEST")
    test_structure4 = result4.structures[0]
    results["checkpoint_4"] = checkpoint_4_generate_signal_receives(test_structure4, bars)
    
    # 检查点5: 数据流分析
    results["checkpoint_5"] = checkpoint_5_data_flow_analysis()
    
    # 预期 vs 实际对比
    compare_expected_vs_actual(results)
    
    # 输出完整结果到JSON文件
    output_file = project_root / "debug_stability_blind_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n\n完整调试结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
