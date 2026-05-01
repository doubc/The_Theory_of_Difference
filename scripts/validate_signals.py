#!/usr/bin/env python3
"""
信号层验证脚本 — 使用真实市场数据测试信号生成效果

验证步骤:
1. 选择3-5个活跃品种（CU0、AU0、RB0等）
2. 加载最近30-60天的日线数据
3. 编译结构并生成信号
4. 人工检查信号合理性

输出:
- 每个品种的样本信号描述
- 信号准确性评估（高/中/低）
- 发现的问题或改进建议
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

from src.data.loader import CSVLoader, MySQLLoader, Bar
from src.compiler.pipeline import compile_full, CompilerConfig, CompileResult
from src.models import Structure, SystemState, Signal, SignalKind, MotionState, ProjectionAwareness, StabilityVerdict
from src.signals import generate_signal
from src.quality import assess_quality


@dataclass
class ValidationResult:
    """单个品种的验证结果"""
    symbol: str
    symbol_name: str
    data_range: str
    bar_count: int
    structures_found: int
    signals: List[Signal]
    signal_details: List[Dict]
    assessment: str  # 高/中/低
    notes: List[str]


def load_symbol_data(symbol: str, days: int = 60) -> Tuple[List[Bar], str]:
    """加载指定品种的最近N天数据"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days + 30)  # 多取一些用于编译
    
    # 尝试从MySQL加载
    try:
        password = os.getenv('MYSQL_PASSWORD', '')
        if password:
            loader = MySQLLoader(host="localhost", user="root", password=password, db="sina")
            bars = loader.get(symbol=symbol, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), freq="1d")
            if bars and len(bars) >= 30:
                return bars, f"{bars[0].timestamp.strftime('%Y-%m-%d')} ~ {bars[-1].timestamp.strftime('%Y-%m-%d')}"
    except Exception as e:
        print(f"  MySQL加载失败: {e}")
    
    # 尝试从CSV加载
    csv_map = {
        "CU0": "cu0.csv",
        "AU0": "au0.csv", 
        "RB0": "rb0.csv",
        "AG0": "ag0.csv",
        "AL0": "al0.csv",
    }
    
    if symbol in csv_map:
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", csv_map[symbol])
        if os.path.exists(csv_path):
            loader = CSVLoader(csv_path, symbol=symbol)
            bars = loader.get(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
            if bars:
                return bars, f"{bars[0].timestamp.strftime('%Y-%m-%d')} ~ {bars[-1].timestamp.strftime('%Y-%m-%d')}"
    
    return [], "无数据"


def build_system_state(structure: Structure, bars: List[Bar]) -> SystemState:
    """从结构和K线数据构建系统状态"""
    # 构建 MotionState
    motion = MotionState()
    if structure.cycles:
        motion.structural_age = len(structure.cycles)
        # 计算 conservation_flux: 基于最近价格变化与结构方向的关系
        recent_bars = bars[-10:] if len(bars) >= 10 else bars
        if len(recent_bars) >= 2:
            price_change = (recent_bars[-1].close - recent_bars[0].close) / recent_bars[0].close
            # 根据结构cycle方向判断flux
            ups = sum(1 for c in structure.cycles if c.entry.direction.value > 0)
            downs = sum(1 for c in structure.cycles if c.entry.direction.value < 0)
            if ups > downs:
                structure_direction = 1
            elif downs > ups:
                structure_direction = -1
            else:
                structure_direction = 0
            motion.conservation_flux = price_change * structure_direction * 10  # 放大以便检测
    
    # 构建 ProjectionAwareness
    projection = ProjectionAwareness()
    # 检测盲区：如果最近价格波动很小但成交量变化大，可能是盲区
    if len(bars) >= 20:
        recent_volatility = sum(b.high - b.low for b in bars[-5:]) / 5
        prev_volatility = sum(b.high - b.low for b in bars[-10:-5]) / 5
        if prev_volatility > 0:
            vol_ratio = recent_volatility / prev_volatility
            if vol_ratio < 0.5:
                projection.compression_level = 0.8
                projection.blind_channels = ["price_compression"]
    
    # 构建 StabilityVerdict
    stability = StabilityVerdict()
    # 基于结构质量判断稳定性
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


def compile_and_generate_signals(bars: List[Bar], symbol: str) -> Tuple[CompileResult, List[Signal], List[SystemState]]:
    """编译结构并生成信号"""
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
    
    signals = []
    system_states = []
    
    # 为每个结构生成信号
    for structure in result.structures:
        # 构建SystemState
        system_state = build_system_state(structure, bars)
        system_states.append(system_state)
        
        # 生成信号
        signal = generate_signal(structure, bars, system_state)
        if signal:
            signals.append(signal)
    
    return result, signals, system_states


def analyze_signal(signal: Signal, structure: Structure, bars: List[Bar]) -> Dict:
    """详细分析单个信号"""
    last_bar = bars[-1]
    
    detail = {
        "signal_type": signal.kind.value if hasattr(signal.kind, 'value') else str(signal.kind),
        "direction": signal.direction,
        "confidence": round(signal.confidence, 2),
        "flux_aligned": signal.flux_aligned,
        "stability_ok": signal.stability_ok,
        "is_blind": signal.is_blind,
        "quality_tier": signal.quality_tier,
        "position_factor": round(signal.position_size_factor, 2),
        "entry_note": signal.entry_note,
        "stop_loss": signal.stop_loss_hint,
        "current_price": last_bar.close,
        "days_since_formation": signal.days_since_formation,
    }
    
    # 添加假突破模式详情
    if hasattr(signal, 'fake_pattern') and signal.fake_pattern:
        detail["fake_pattern"] = signal.fake_pattern.value if hasattr(signal.fake_pattern, 'value') else str(signal.fake_pattern)
    
    # 添加突破评分
    if hasattr(signal, 'breakout_score') and signal.breakout_score:
        detail["breakout_score"] = round(signal.breakout_score, 2)
    
    return detail


def assess_signal_validity(signal: Signal, structure: Structure, bars: List[Bar]) -> List[str]:
    """评估信号合理性，返回问题列表"""
    issues = []
    
    # 获取关键价格信息
    last_bar = bars[-1]
    last_close = last_bar.close
    
    upper = structure.zone.upper if structure.zone else 0
    lower = structure.zone.lower if structure.zone else 0
    bandwidth = structure.zone.bandwidth if structure.zone else 0
    center = (upper + lower) / 2 if bandwidth > 0 else last_close
    
    # 1. 假突破信号检查
    if signal.kind == SignalKind.FAKE_BREAKOUT:
        # 检查价格位置是否与信号方向一致
        if signal.direction == "short" and last_close < upper:
            issues.append("OK 假突破做空信号：价格在上边界下方，合理")
        elif signal.direction == "long" and last_close > lower:
            issues.append("OK 假突破做多信号：价格在下边界上方，合理")
        else:
            issues.append("WARN 假突破信号方向与价格位置可能不符")
        
        # 检查flux方向
        if not signal.flux_aligned:
            issues.append("OK flux方向与交易方向相反，符合假突破特征")
        else:
            issues.append("WARN flux方向与交易方向一致，可能不是假突破")
    
    # 2. 突破确认信号检查
    elif signal.kind == SignalKind.BREAKOUT_CONFIRM:
        if signal.direction == "long" and last_close > upper:
            issues.append("OK 向上突破确认：价格在上边界上方")
        elif signal.direction == "short" and last_close < lower:
            issues.append("OK 向下突破确认：价格在下边界下方")
        else:
            issues.append("WARN 突破确认但价格未在Zone外")
        
        if signal.flux_aligned:
            issues.append("OK flux方向与突破方向一致")
        else:
            issues.append("WARN flux方向与突破方向不一致")
    
    # 3. 盲区信号检查
    if signal.is_blind:
        issues.append("WARN 盲区信号，置信度已降低")
    
    # 4. 仓位系数检查
    if signal.position_size_factor < 0.3:
        issues.append(f"WARN 仓位系数较低({signal.position_size_factor})，建议轻仓")
    elif signal.position_size_factor > 0.8:
        issues.append(f"OK 仓位系数较高({signal.position_size_factor})，可正常建仓")
    
    # 5. 质量层检查
    if signal.quality_tier == "D":
        issues.append("WARN 质量层D，不应生成信号（检查过滤逻辑）")
    elif signal.quality_tier == "A":
        issues.append("OK 质量层A，结构质量优秀")
    
    return issues


def validate_symbol(symbol: str, symbol_name: str, days: int = 60) -> ValidationResult:
    """验证单个品种的信号生成"""
    print(f"\n{'='*60}")
    print(f"验证品种: {symbol} ({symbol_name})")
    print(f"{'='*60}")
    
    # 1. 加载数据
    print(f"\n[1] 加载最近{days}天数据...")
    bars, data_range = load_symbol_data(symbol, days)
    
    if not bars or len(bars) < 30:
        return ValidationResult(
            symbol=symbol,
            symbol_name=symbol_name,
            data_range=data_range,
            bar_count=0,
            structures_found=0,
            signals=[],
            signal_details=[],
            assessment="低",
            notes=["数据不足，无法验证"]
        )
    
    print(f"    数据范围: {data_range}")
    print(f"    K线数量: {len(bars)}")
    print(f"    价格区间: {min(b.low for b in bars):.2f} ~ {max(b.high for b in bars):.2f}")
    
    # 2. 编译结构
    print(f"\n[2] 编译价格结构...")
    result, signals, system_states = compile_and_generate_signals(bars, symbol)
    print(f"    发现结构: {len(result.structures)}")
    print(f"    生成信号: {len(signals)}")
    
    if result.zones:
        print(f"    关键Zone: {len(result.zones)}")
        for i, z in enumerate(result.zones[:3]):
            print(f"      Zone {i+1}: {z.lower:.2f} ~ {z.upper:.2f} (带宽: {z.bandwidth:.2f})")
    
    # 3. 分析信号
    print(f"\n[3] 信号详情分析...")
    signal_details = []
    all_issues = []
    
    for i, (signal, structure, ss) in enumerate(zip(signals, result.structures, system_states)):
        print(f"\n  信号 {i+1}: {signal.kind.value if hasattr(signal.kind, 'value') else signal.kind}")
        print(f"    方向: {signal.direction}, 置信度: {signal.confidence:.2f}")
        print(f"    flux一致: {signal.flux_aligned}, 稳定性: {signal.stability_ok}")
        print(f"    质量层: {signal.quality_tier}, 盲区: {signal.is_blind}")
        print(f"    仓位系数: {signal.position_size_factor:.2f}")
        print(f"    入场说明: {signal.entry_note}")
        
        detail = analyze_signal(signal, structure, bars)
        signal_details.append(detail)
        
        # 验证信号合理性
        issues = assess_signal_validity(signal, structure, bars)
        for issue in issues:
            print(f"    {issue}")
        all_issues.extend(issues)
    
    # 4. 综合评估
    print(f"\n[4] 综合评估...")
    if not signals:
        assessment = "中"
        notes = ["未生成信号，可能原因：", "- 无活跃结构", "- 质量层D过滤", "- 不满足信号条件"]
    else:
        # 根据问题数量评估
        error_count = sum(1 for issue in all_issues if issue.startswith("WARN"))
        ok_count = sum(1 for issue in all_issues if issue.startswith("OK"))
        
        if error_count == 0:
            assessment = "高"
        elif error_count <= 2:
            assessment = "中"
        else:
            assessment = "低"
        
        notes = [
            f"生成 {len(signals)} 个信号",
            f"合理检查通过: {ok_count}, 警告: {error_count}",
        ]
        
        # 添加具体问题
        problems = [issue for issue in all_issues if issue.startswith("WARN")]
        if problems:
            notes.append("发现问题:")
            notes.extend(problems[:5])  # 最多显示5个问题
    
    print(f"    评估结果: {assessment}")
    for note in notes:
        print(f"    - {note}")
    
    return ValidationResult(
        symbol=symbol,
        symbol_name=symbol_name,
        data_range=data_range,
        bar_count=len(bars),
        structures_found=len(result.structures),
        signals=signals,
        signal_details=signal_details,
        assessment=assessment,
        notes=notes
    )


def generate_report(results: List[ValidationResult]) -> str:
    """生成验证报告"""
    report_lines = [
        "# 期货价格结构检索系统 - 信号层验证报告",
        f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n## 验证概述",
        f"\n验证品种数: {len(results)}",
    ]
    
    # 统计
    high_count = sum(1 for r in results if r.assessment == "高")
    mid_count = sum(1 for r in results if r.assessment == "中")
    low_count = sum(1 for r in results if r.assessment == "低")
    
    report_lines.extend([
        f"高准确性: {high_count} 个",
        f"中准确性: {mid_count} 个",
        f"低准确性: {low_count} 个",
        "\n## 各品种详细结果",
    ])
    
    for result in results:
        report_lines.extend([
            f"\n### {result.symbol} ({result.symbol_name})",
            f"- 数据范围: {result.data_range}",
            f"- K线数量: {result.bar_count}",
            f"- 发现结构: {result.structures_found}",
            f"- 生成信号: {len(result.signals)}",
            f"- 准确性评估: **{result.assessment}**",
            "- 备注:",
        ])
        for note in result.notes:
            report_lines.append(f"  - {note}")
        
        if result.signal_details:
            report_lines.append("- 信号详情:")
            for i, detail in enumerate(result.signal_details):
                report_lines.append(f"  - 信号{i+1}: {detail['signal_type']}")
                report_lines.append(f"    - 方向: {detail['direction']}, 置信度: {detail['confidence']}")
                report_lines.append(f"    - flux一致: {detail['flux_aligned']}, 仓位系数: {detail['position_factor']}")
    
    # 改进建议
    report_lines.extend([
        "\n## 发现的问题与改进建议",
        "\n### 共性问题",
    ])
    
    all_notes = []
    for result in results:
        all_notes.extend(result.notes)
    
    # 统计常见问题
    problem_counts = {}
    for note in all_notes:
        if note.startswith("WARN") or "问题" in note:
            problem_counts[note] = problem_counts.get(note, 0) + 1
    
    if problem_counts:
        for problem, count in sorted(problem_counts.items(), key=lambda x: -x[1]):
            report_lines.append(f"- {problem} (出现 {count} 次)")
    else:
        report_lines.append("- 未发现明显共性问题")
    
    report_lines.extend([
        "\n### 改进建议",
        "1. **假突破检测**: 建议增加更多历史K线上下文，提高模式识别准确性",
        "2. **flux一致性**: 当前flux计算可能过于敏感，建议平滑处理",
        "3. **盲区处理**: 盲区信号的降仓系数(0.5)可能过于保守，可测试0.6-0.7",
        "4. **信号优先级**: 建议增加时间衰减因子，老化结构信号优先级降低",
        "5. **仓位系数**: 质量层B和C的系数(0.6/0.3)差距较大，建议细化分级",
    ])
    
    return "\n".join(report_lines)


def main():
    print("=" * 70)
    print("  期货价格结构检索系统 - 信号层验证")
    print("=" * 70)
    
    # 选择验证品种
    symbols_to_validate = [
        ("CU0", "铜连续"),
        ("AU0", "黄金连续"),
        ("RB0", "螺纹钢连续"),
        ("AG0", "白银连续"),
        ("AL0", "铝连续"),
    ]
    
    results = []
    
    for symbol, name in symbols_to_validate:
        try:
            result = validate_symbol(symbol, name, days=60)
            results.append(result)
        except Exception as e:
            print(f"\n验证 {symbol} 时出错: {e}")
            import traceback
            traceback.print_exc()
            results.append(ValidationResult(
                symbol=symbol,
                symbol_name=name,
                data_range="错误",
                bar_count=0,
                structures_found=0,
                signals=[],
                signal_details=[],
                assessment="低",
                notes=[f"验证出错: {str(e)}"]
            ))
    
    # 生成报告
    print("\n" + "=" * 70)
    print("  生成验证报告...")
    print("=" * 70)
    
    report = generate_report(results)
    
    # 保存报告
    report_path = os.path.join(
        os.path.dirname(__file__), "..", "output",
        f"signal_validation_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    )
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n报告已保存: {report_path}")
    
    # 打印摘要
    print("\n" + "=" * 70)
    print("  验证摘要")
    print("=" * 70)
    
    for result in results:
        status = "OK" if result.assessment == "高" else "~" if result.assessment == "中" else "X"
        print(f"{status} {result.symbol:6} ({result.symbol_name:10}): 准确性={result.assessment}, 信号数={len(result.signals)}")
    
    print("\n" + "=" * 70)
    print("  验证完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
