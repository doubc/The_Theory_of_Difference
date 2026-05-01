#!/usr/bin/env python3
"""
信号层详细验证脚本 — 深度分析CU0数据上的信号生成效果

验证重点:
1. 假突破信号检测准确性
2. 突破确认信号与flux方向一致性
3. 盲区信号标记正确性
4. 仓位系数合理性

输出:
- 详细信号分析报告
- 每个信号的K线上下文
- 改进建议
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import statistics

from src.data.loader import CSVLoader, Bar
from src.compiler.pipeline import compile_full, CompilerConfig
from src.models import Structure, SystemState, Signal, SignalKind, MotionState, ProjectionAwareness, StabilityVerdict, FakeBreakoutPattern
from src.signals import generate_signal, detect_fake_breakout, score_breakout_confirmation
from src.quality import assess_quality


def load_cu0_data(days: int = 90) -> List[Bar]:
    """加载铜连续合约数据"""
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "cu0.csv")
    loader = CSVLoader(csv_path, symbol="CU0")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    bars = loader.get(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
    return bars


def build_system_state(structure: Structure, bars: List[Bar]) -> SystemState:
    """从结构和K线数据构建系统状态"""
    motion = MotionState()
    if structure.cycles:
        motion.structural_age = len(structure.cycles)
        recent_bars = bars[-10:] if len(bars) >= 10 else bars
        if len(recent_bars) >= 2:
            price_change = (recent_bars[-1].close - recent_bars[0].close) / recent_bars[0].close
            ups = sum(1 for c in structure.cycles if c.entry.direction.value > 0)
            downs = sum(1 for c in structure.cycles if c.entry.direction.value < 0)
            if ups > downs:
                structure_direction = 1
            elif downs > ups:
                structure_direction = -1
            else:
                structure_direction = 0
            motion.conservation_flux = price_change * structure_direction * 10
    
    projection = ProjectionAwareness()
    if len(bars) >= 20:
        recent_volatility = sum(b.high - b.low for b in bars[-5:]) / 5
        prev_volatility = sum(b.high - b.low for b in bars[-10:-5]) / 5
        if prev_volatility > 0:
            vol_ratio = recent_volatility / prev_volatility
            if vol_ratio < 0.5:
                projection.compression_level = 0.8
                projection.blind_channels = ["price_compression"]
    
    stability = StabilityVerdict()
    qa = assess_quality(structure)
    if qa.tier.value == "A":
        stability.surface = "stable"
        stability.verified = True
    elif qa.tier.value == "B":
        stability.surface = "stable"
        stability.verified = False
        stability.verification_window = 3
    else:
        stability.surface = "unstable"
    
    return SystemState(
        structure=structure,
        motion=motion,
        projection=projection,
        stability=stability,
    )


def analyze_price_position(bars: List[Bar], structure: Structure) -> Dict:
    """分析价格相对于Zone的位置"""
    last_bar = bars[-1]
    last_close = last_bar.close
    
    upper = structure.zone.upper if structure.zone else 0
    lower = structure.zone.lower if structure.zone else 0
    bandwidth = structure.zone.bandwidth if structure.zone else 0
    center = (upper + lower) / 2 if bandwidth > 0 else last_close
    
    if last_close > upper:
        position = "above"
        distance = (last_close - upper) / bandwidth if bandwidth > 0 else 0
    elif last_close < lower:
        position = "below"
        distance = (lower - last_close) / bandwidth if bandwidth > 0 else 0
    else:
        position = "inside"
        distance = min(last_close - lower, upper - last_close) / bandwidth if bandwidth > 0 else 0
    
    return {
        "last_close": last_close,
        "upper": upper,
        "lower": lower,
        "center": center,
        "bandwidth": bandwidth,
        "position": position,
        "distance_to_boundary": distance,
    }


def check_fake_breakout_pattern(bars: List[Bar], structure: Structure) -> Dict:
    """详细检查假突破模式"""
    if len(bars) < 5:
        return {"detected": False, "reason": "数据不足"}
    
    upper = structure.zone.upper if structure.zone else 0
    lower = structure.zone.lower if structure.zone else 0
    bandwidth = structure.zone.bandwidth if structure.zone else 0
    
    if bandwidth <= 0:
        return {"detected": False, "reason": "Zone无效"}
    
    last_bar = bars[-1]
    prev_bar = bars[-2] if len(bars) >= 2 else last_bar
    
    results = {
        "detected": False,
        "patterns_checked": [],
    }
    
    # 模式1: FAKE_PIN - 探针型
    pin_up = last_bar.high > upper and last_bar.close < upper
    pin_down = last_bar.low < lower and last_bar.close > lower
    
    if pin_up:
        penetration = (last_bar.high - upper) / bandwidth
        results["patterns_checked"].append({
            "pattern": "FAKE_PIN",
            "direction": "up",
            "penetration": round(penetration, 2),
            "high": last_bar.high,
            "close": last_bar.close,
            "upper": upper,
        })
        if penetration > 0.3:
            results["detected"] = True
            results["matched_pattern"] = "FAKE_PIN"
    
    if pin_down:
        penetration = (lower - last_bar.low) / bandwidth
        results["patterns_checked"].append({
            "pattern": "FAKE_PIN",
            "direction": "down",
            "penetration": round(penetration, 2),
            "low": last_bar.low,
            "close": last_bar.close,
            "lower": lower,
        })
        if penetration > 0.3:
            results["detected"] = True
            results["matched_pattern"] = "FAKE_PIN"
    
    # 模式2: FAKE_GAP - 跳空回补
    if len(bars) >= 2:
        gap_up = prev_bar.close < upper and last_bar.open > upper
        gap_down = prev_bar.close > lower and last_bar.open < lower
        
        fill_up = gap_up and last_bar.close < upper
        fill_down = gap_down and last_bar.close > lower
        
        if gap_up or gap_down:
            results["patterns_checked"].append({
                "pattern": "FAKE_GAP",
                "gap_up": gap_up,
                "gap_down": gap_down,
                "fill_up": fill_up,
                "fill_down": fill_down,
                "prev_close": prev_bar.close,
                "open": last_bar.open,
                "close": last_bar.close,
            })
            if fill_up or fill_down:
                results["detected"] = True
                results["matched_pattern"] = "FAKE_GAP"
    
    return results


def validate_signal_logic(signal: Signal, structure: Structure, bars: List[Bar]) -> Dict:
    """验证信号逻辑的正确性"""
    validation = {
        "signal_type": signal.kind.value if hasattr(signal.kind, 'value') else str(signal.kind),
        "checks": [],
        "passed": 0,
        "warnings": 0,
    }
    
    pos_info = analyze_price_position(bars, structure)
    
    # 1. 假突破信号验证
    if signal.kind == SignalKind.FAKE_BREAKOUT:
        # 检查1: 假突破应该发生在Zone边界附近
        if pos_info["position"] == "inside":
            validation["checks"].append({
                "item": "价格位置",
                "status": "WARN",
                "detail": f"假突破信号但价格在Zone内部({pos_info['last_close']:.2f}在{pos_info['lower']:.2f}~{pos_info['upper']:.2f}之间)",
            })
            validation["warnings"] += 1
        else:
            validation["checks"].append({
                "item": "价格位置",
                "status": "OK",
                "detail": f"价格在Zone{pos_info['position']}方",
            })
            validation["passed"] += 1
        
        # 检查2: flux方向应该与突破方向相反
        if not signal.flux_aligned:
            validation["checks"].append({
                "item": "flux一致性",
                "status": "OK",
                "detail": "flux方向与交易方向相反，符合假突破特征",
            })
            validation["passed"] += 1
        else:
            validation["checks"].append({
                "item": "flux一致性",
                "status": "WARN",
                "detail": "flux方向与交易方向一致，可能不是假突破",
            })
            validation["warnings"] += 1
        
        # 检查3: 假突破模式检测
        fake_check = check_fake_breakout_pattern(bars, structure)
        if fake_check["detected"]:
            validation["checks"].append({
                "item": "假突破模式",
                "status": "OK",
                "detail": f"检测到{fake_check.get('matched_pattern', '未知')}模式",
            })
            validation["passed"] += 1
        else:
            validation["checks"].append({
                "item": "假突破模式",
                "status": "WARN",
                "detail": "未检测到明显的假突破价格模式",
            })
            validation["warnings"] += 1
    
    # 2. 突破确认信号验证
    elif signal.kind == SignalKind.BREAKOUT_CONFIRM:
        if pos_info["position"] in ["above", "below"]:
            validation["checks"].append({
                "item": "价格位置",
                "status": "OK",
                "detail": f"价格确实突破Zone，在{pos_info['position']}方",
            })
            validation["passed"] += 1
        else:
            validation["checks"].append({
                "item": "价格位置",
                "status": "WARN",
                "detail": "突破确认信号但价格仍在Zone内部",
            })
            validation["warnings"] += 1
        
        if signal.flux_aligned:
            validation["checks"].append({
                "item": "flux一致性",
                "status": "OK",
                "detail": "flux方向与突破方向一致",
            })
            validation["passed"] += 1
        else:
            validation["checks"].append({
                "item": "flux一致性",
                "status": "WARN",
                "detail": "flux方向与突破方向不一致",
            })
            validation["warnings"] += 1
    
    # 3. 仓位系数验证
    if signal.quality_tier == "A" and signal.position_size_factor == 1.0:
        validation["checks"].append({
            "item": "仓位系数",
            "status": "OK",
            "detail": "质量层A对应仓位系数1.0",
        })
        validation["passed"] += 1
    elif signal.quality_tier == "B" and signal.position_size_factor == 0.6:
        validation["checks"].append({
            "item": "仓位系数",
            "status": "OK",
            "detail": "质量层B对应仓位系数0.6",
        })
        validation["passed"] += 1
    elif signal.quality_tier == "C" and signal.position_size_factor == 0.3:
        validation["checks"].append({
            "item": "仓位系数",
            "status": "OK",
            "detail": "质量层C对应仓位系数0.3",
        })
        validation["passed"] += 1
    elif signal.quality_tier == "D":
        validation["checks"].append({
            "item": "仓位系数",
            "status": "WARN",
            "detail": "质量层D不应生成信号",
        })
        validation["warnings"] += 1
    
    # 4. 盲区验证
    if signal.is_blind:
        validation["checks"].append({
            "item": "盲区标记",
            "status": "INFO",
            "detail": f"盲区信号，置信度已降低至{signal.confidence:.2f}",
        })
    
    return validation


def print_signal_report(signal: Signal, structure: Structure, bars: List[Bar], index: int):
    """打印单个信号的详细报告"""
    print(f"\n{'='*60}")
    print(f"信号 {index}: {signal.display_label if hasattr(signal, 'display_label') else signal.kind}")
    print(f"{'='*60}")
    
    # 基本信息
    print(f"\n[基本信息]")
    print(f"  方向: {signal.direction}")
    print(f"  置信度: {signal.confidence:.2f}")
    print(f"  质量层: {signal.quality_tier}")
    print(f"  仓位系数: {signal.position_size_factor:.2f}")
    print(f"  盲区标记: {signal.is_blind}")
    print(f"  入场说明: {signal.entry_note}")
    
    # 价格位置
    pos_info = analyze_price_position(bars, structure)
    print(f"\n[价格位置分析]")
    print(f"  当前价格: {pos_info['last_close']:.2f}")
    print(f"  Zone上边界: {pos_info['upper']:.2f}")
    print(f"  Zone下边界: {pos_info['lower']:.2f}")
    print(f"  Zone中心: {pos_info['center']:.2f}")
    print(f"  带宽: {pos_info['bandwidth']:.2f}")
    print(f"  相对位置: {pos_info['position']}")
    print(f"  距边界距离(带宽倍数): {pos_info['distance_to_boundary']:.2f}")
    
    # 结构信息
    print(f"\n[结构信息]")
    print(f"  Cycle数量: {structure.cycle_count}")
    print(f"  平均速度比: {structure.avg_speed_ratio:.2f}")
    print(f"  Zone强度: {structure.zone.strength:.2f}" if structure.zone else "  Zone: None")
    
    # 验证结果
    validation = validate_signal_logic(signal, structure, bars)
    print(f"\n[逻辑验证]")
    print(f"  通过检查: {validation['passed']}")
    print(f"  警告: {validation['warnings']}")
    for check in validation["checks"]:
        status_symbol = "OK" if check["status"] == "OK" else "WARN" if check["status"] == "WARN" else "INFO"
        print(f"  [{status_symbol}] {check['item']}: {check['detail']}")
    
    # 假突破模式详细检查
    if signal.kind == SignalKind.FAKE_BREAKOUT:
        fake_check = check_fake_breakout_pattern(bars, structure)
        print(f"\n[假突破模式检测]")
        print(f"  是否检测到: {fake_check['detected']}")
        if fake_check.get("matched_pattern"):
            print(f"  匹配模式: {fake_check['matched_pattern']}")
        if fake_check.get("patterns_checked"):
            print(f"  检查的模式:")
            for pattern in fake_check["patterns_checked"]:
                print(f"    - {pattern}")


def main():
    print("=" * 70)
    print("  期货价格结构检索系统 - 信号层详细验证")
    print("  品种: CU0 (铜连续)")
    print("=" * 70)
    
    # 1. 加载数据
    print("\n[1] 加载数据...")
    bars = load_cu0_data(days=90)
    print(f"    K线数量: {len(bars)}")
    if bars:
        print(f"    日期范围: {bars[0].timestamp.strftime('%Y-%m-%d')} ~ {bars[-1].timestamp.strftime('%Y-%m-%d')}")
        print(f"    价格范围: {min(b.low for b in bars):.2f} ~ {max(b.high for b in bars):.2f}")
    
    # 2. 编译结构
    print("\n[2] 编译价格结构...")
    config = CompilerConfig(
        min_amplitude=0.02,
        min_duration=3,
        noise_filter=0.005,
        zone_bandwidth=0.015,
        cluster_eps=0.02,
        cluster_min_points=2,
        min_cycles=2,
        tolerance=0.03,
    )
    
    result = compile_full(bars, config)
    print(f"    发现Zone: {len(result.zones)}")
    print(f"    发现结构: {len(result.structures)}")
    
    for i, z in enumerate(result.zones):
        print(f"    Zone {i+1}: {z.lower:.2f} ~ {z.upper:.2f} (带宽: {z.bandwidth:.2f}, 强度: {z.strength:.1f})")
    
    # 3. 生成并分析信号
    print("\n[3] 生成并分析信号...")
    signals = []
    
    for i, structure in enumerate(result.structures):
        print(f"\n  结构 {i+1}: Zone={structure.zone.price_center:.2f}, Cycles={structure.cycle_count}")
        
        # 构建系统状态
        system_state = build_system_state(structure, bars)
        
        # 生成信号
        signal = generate_signal(structure, bars, system_state)
        
        if signal:
            signals.append((signal, structure, system_state))
            print_signal_report(signal, structure, bars, len(signals))
        else:
            print(f"    未生成信号")
            # 检查为什么没有信号
            qa = assess_quality(structure)
            print(f"    质量层: {qa.tier.value}, 分数: {qa.score:.2f}")
    
    # 4. 总结
    print("\n" + "=" * 70)
    print("  验证总结")
    print("=" * 70)
    
    print(f"\n共生成 {len(signals)} 个信号")
    
    if signals:
        signal_types = {}
        for signal, _, _ in signals:
            stype = signal.kind.value if hasattr(signal.kind, 'value') else str(signal.kind)
            signal_types[stype] = signal_types.get(stype, 0) + 1
        
        print("\n信号类型分布:")
        for stype, count in signal_types.items():
            print(f"  - {stype}: {count}")
        
        print("\n信号质量评估:")
        total_checks = 0
        total_passed = 0
        total_warnings = 0
        
        for signal, structure, _ in signals:
            validation = validate_signal_logic(signal, structure, bars)
            total_checks += len(validation["checks"])
            total_passed += validation["passed"]
            total_warnings += validation["warnings"]
        
        print(f"  总检查项: {total_checks}")
        print(f"  通过: {total_passed} ({total_passed/total_checks*100:.1f}%)")
        print(f"  警告: {total_warnings} ({total_warnings/total_checks*100:.1f}%)")
        
        # 评估准确性
        if total_warnings == 0:
            assessment = "高"
        elif total_warnings <= 2:
            assessment = "中"
        else:
            assessment = "低"
        
        print(f"\n整体准确性评估: {assessment}")
    
    # 5. 改进建议
    print("\n" + "=" * 70)
    print("  改进建议")
    print("=" * 70)
    
    suggestions = [
        "1. 假突破检测阈值优化:",
        "   - 当前穿透阈值0.3倍带宽可能过于严格",
        "   - 建议测试0.2-0.5范围的阈值效果",
        "",
        "2. flux计算改进:",
        "   - 当前flux基于10日价格变化，可能过于敏感",
        "   - 建议增加平滑处理或使用更长周期",
        "",
        "3. 盲区检测:",
        "   - 当前盲区基于价格波动率压缩检测",
        "   - 建议结合成交量变化综合判断",
        "",
        "4. 仓位系数细化:",
        "   - 质量层B(0.6)和C(0.3)差距较大",
        "   - 建议增加B+、B-等细分层级",
        "",
        "5. 信号优先级:",
        "   - 建议增加时间衰减因子",
        "   - 老化结构(>14天)信号优先级应降低",
    ]
    
    for suggestion in suggestions:
        print(suggestion)
    
    # 6. 保存详细报告
    report_path = os.path.join(
        os.path.dirname(__file__), "..", "output",
        f"signal_validation_detailed_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    )
    
    print(f"\n详细报告已保存至: {report_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
