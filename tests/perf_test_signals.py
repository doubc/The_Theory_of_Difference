"""
信号层性能测试 — 评估 signals.py 在大数据量下的运行效率

测试重点:
1. 全市场扫描时的信号生成耗时（45个品种 × 每个品种5个结构）
2. 大数据量bars时的处理效率（1000根K线 vs 100根K线）
3. 内存使用情况
4. 是否存在重复计算或可以缓存的部分
"""

from __future__ import annotations

import time
import tracemalloc
import gc
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.signals import (
    generate_signal,
    detect_fake_breakout,
    score_breakout_confirmation,
    detect_pullback_confirmation,
    detect_structure_aging,
    FAKE_PENETRATION_THRESHOLD,
    BREAKOUT_STRONG,
    BREAKOUT_WEAK,
)
from src.data.loader import Bar
from src.models import (
    Point, Segment, Zone, Cycle, Structure,
    MotionState, ProjectionAwareness, StabilityVerdict,
    SystemState, SignalKind, FakeBreakoutPattern,
    ZoneSource, Direction
)
from src.quality import assess_quality


# ═══════════════════════════════════════════════════════════
# 测试数据生成器
# ═══════════════════════════════════════════════════════════

def generate_mock_bars(
    n: int = 100,
    base_price: float = 50000.0,
    volatility: float = 0.02,
    symbol: str = "TEST",
    start_date: datetime = None,
) -> List[Bar]:
    """生成模拟K线数据"""
    if start_date is None:
        start_date = datetime(2024, 1, 1)
    
    bars = []
    price = base_price
    
    import random
    random.seed(42)  # 可复现
    
    for i in range(n):
        # 随机游走
        change = random.gauss(0, volatility)
        open_p = price
        close_p = price * (1 + change)
        high_p = max(open_p, close_p) * (1 + abs(random.gauss(0, volatility * 0.5)))
        low_p = min(open_p, close_p) * (1 - abs(random.gauss(0, volatility * 0.5)))
        volume = random.uniform(10000, 100000)
        
        bars.append(Bar(
            symbol=symbol,
            timestamp=start_date + timedelta(days=i),
            open=round(open_p, 2),
            high=round(high_p, 2),
            low=round(low_p, 2),
            close=round(close_p, 2),
            volume=round(volume, 2),
        ))
        price = close_p
    
    return bars


def generate_mock_structure(
    zone_center: float = 50000.0,
    bandwidth: float = 1000.0,
    n_cycles: int = 3,
    symbol: str = "TEST",
) -> Structure:
    """生成模拟结构"""
    # 创建Zone
    zone = Zone(
        price_center=zone_center,
        bandwidth=bandwidth,
        source=ZoneSource.PIVOT,
        strength=float(n_cycles),
        touches=[],
    )
    
    # 创建Cycles
    cycles = []
    base_date = datetime(2024, 1, 1)
    
    for i in range(n_cycles):
        # Entry segment
        entry_start = Point(t=base_date + timedelta(days=i*10), x=zone_center - bandwidth*2, idx=i*4)
        entry_end = Point(t=base_date + timedelta(days=i*10+3), x=zone_center + bandwidth*0.5, idx=i*4+1)
        entry = Segment(start=entry_start, end=entry_end)
        
        # Exit segment
        exit_start = Point(t=base_date + timedelta(days=i*10+3), x=zone_center + bandwidth*0.5, idx=i*4+2)
        exit_end = Point(t=base_date + timedelta(days=i*10+7), x=zone_center + bandwidth*2, idx=i*4+3)
        exit_seg = Segment(start=exit_start, end=exit_end)
        
        cycle = Cycle(entry=entry, exit=exit_seg, zone=zone)
        cycles.append(cycle)
    
    # 创建MotionState
    motion = MotionState(
        phase_tendency="forming",
        phase_confidence=0.7,
        conservation_flux=0.3,
        structural_age=n_cycles * 5,
    )
    
    # 创建ProjectionAwareness
    projection = ProjectionAwareness(
        compression_level=0.3,
        projection_confidence=0.8,
    )
    
    # 创建StabilityVerdict
    stability = StabilityVerdict(
        surface="stable",
        verified=True,
    )
    
    structure = Structure(
        zone=zone,
        cycles=cycles,
        symbol=symbol,
        t_start=base_date,
        t_end=base_date + timedelta(days=n_cycles*10),
        motion=motion,
        projection=projection,
        stability_verdict=stability,
        typicality=0.7,
    )
    
    return structure


def generate_system_state(structure: Structure) -> SystemState:
    """生成系统状态"""
    return SystemState(
        structure=structure,
        motion=structure.motion or MotionState(),
        projection=structure.projection or ProjectionAwareness(),
        stability=structure.stability_verdict or StabilityVerdict(),
    )


# ═══════════════════════════════════════════════════════════
# 性能测试类
# ═══════════════════════════════════════════════════════════

@dataclass
class PerfResult:
    """性能测试结果"""
    name: str
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    memory_peak_mb: float = 0.0
    iterations: int = 1
    notes: str = ""
    
    def __str__(self):
        return (
            f"【{self.name}】\n"
            f"  总耗时: {self.total_time_ms:.2f}ms ({self.iterations}次)\n"
            f"  平均: {self.avg_time_ms:.2f}ms | 最小: {self.min_time_ms:.2f}ms | 最大: {self.max_time_ms:.2f}ms\n"
            f"  内存峰值: {self.memory_peak_mb:.2f}MB\n"
            f"  备注: {self.notes}"
        )


def run_perf_test(
    func,
    name: str,
    iterations: int = 100,
    warmup: int = 10,
    track_memory: bool = True,
    notes: str = "",
) -> PerfResult:
    """运行性能测试"""
    # Warmup
    for _ in range(warmup):
        func()
    
    gc.collect()
    
    times = []
    
    if track_memory:
        tracemalloc.start()
    
    for _ in range(iterations):
        gc.collect()
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # ms
    
    memory_peak = 0.0
    if track_memory:
        _, memory_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        memory_peak = memory_peak / 1024 / 1024  # MB
    
    return PerfResult(
        name=name,
        total_time_ms=sum(times),
        avg_time_ms=statistics.mean(times),
        min_time_ms=min(times),
        max_time_ms=max(times),
        memory_peak_mb=memory_peak,
        iterations=iterations,
        notes=notes,
    )


# ═══════════════════════════════════════════════════════════
# 具体测试场景
# ═══════════════════════════════════════════════════════════

def test_single_signal_generation():
    """测试单次信号生成"""
    structure = generate_mock_structure(n_cycles=5)
    bars = generate_mock_bars(n=100)
    ss = generate_system_state(structure)
    
    def run():
        return generate_signal(structure, bars, ss)
    
    return run_perf_test(
        run,
        name="单次信号生成(100bars, 5cycles)",
        iterations=1000,
        notes="基础性能基准",
    )


def test_large_bars_comparison():
    """测试不同K线数量的性能差异"""
    structure = generate_mock_structure(n_cycles=5)
    ss = generate_system_state(structure)
    
    results = []
    
    for n_bars in [100, 500, 1000]:
        bars = generate_mock_bars(n=n_bars)
        
        def make_run(b):
            return lambda: generate_signal(structure, b, ss)
        
        result = run_perf_test(
            make_run(bars),
            name=f"信号生成({n_bars}bars)",
            iterations=500,
            notes=f"K线数量对性能的影响",
        )
        results.append(result)
    
    return results


def test_structure_cycles_comparison():
    """测试不同cycle数量的性能差异"""
    bars = generate_mock_bars(n=100)
    
    results = []
    
    for n_cycles in [2, 5, 10]:
        structure = generate_mock_structure(n_cycles=n_cycles)
        ss = generate_system_state(structure)
        
        def make_run(s, b, state):
            return lambda: generate_signal(s, b, state)
        
        result = run_perf_test(
            make_run(structure, bars, ss),
            name=f"信号生成({n_cycles}cycles)",
            iterations=500,
            notes=f"Cycle数量对性能的影响",
        )
        results.append(result)
    
    return results


def test_full_market_scan():
    """测试全市场扫描性能（45品种 × 5结构）"""
    symbols = [f"SYM{i:02d}" for i in range(45)]
    structures_per_symbol = 5
    
    all_structures = []
    all_bars = []
    all_states = []
    
    for symbol in symbols:
        for i in range(structures_per_symbol):
            structure = generate_mock_structure(
                zone_center=50000 + i * 1000,
                n_cycles=3 + i,
                symbol=symbol,
            )
            bars = generate_mock_bars(n=100, symbol=symbol)
            ss = generate_system_state(structure)
            
            all_structures.append(structure)
            all_bars.append(bars)
            all_states.append(ss)
    
    def run():
        signals = []
        for s, b, state in zip(all_structures, all_bars, all_states):
            sig = generate_signal(s, b, state)
            signals.append(sig)
        return signals
    
    return run_perf_test(
        run,
        name="全市场扫描(45品种×5结构=225次)",
        iterations=50,
        notes="模拟全市场信号扫描",
    )


def test_subfunction_performance():
    """测试各个子函数的性能"""
    structure = generate_mock_structure(n_cycles=5)
    bars = generate_mock_bars(n=100)
    ss = generate_system_state(structure)
    
    results = []
    
    # 假突破检测
    def run_fake():
        return detect_fake_breakout(structure, bars, ss)
    
    results.append(run_perf_test(
        run_fake,
        name="子函数:假突破检测",
        iterations=1000,
        notes="detect_fake_breakout",
    ))
    
    # 突破评分
    def run_breakout():
        return score_breakout_confirmation(structure, bars, ss)
    
    results.append(run_perf_test(
        run_breakout,
        name="子函数:突破评分",
        iterations=1000,
        notes="score_breakout_confirmation",
    ))
    
    # 回踩确认
    def run_pullback():
        return detect_pullback_confirmation(structure, bars, ss)
    
    results.append(run_perf_test(
        run_pullback,
        name="子函数:回踩确认",
        iterations=1000,
        notes="detect_pullback_confirmation",
    ))
    
    # 结构老化
    def run_aging():
        return detect_structure_aging(structure, ss)
    
    results.append(run_perf_test(
        run_aging,
        name="子函数:结构老化",
        iterations=1000,
        notes="detect_structure_aging",
    ))
    
    # 质量评估
    def run_quality():
        return assess_quality(structure, ss)
    
    results.append(run_perf_test(
        run_quality,
        name="子函数:质量评估",
        iterations=1000,
        notes="assess_quality",
    ))
    
    return results


def test_memory_usage_scalability():
    """测试内存使用随数据规模的变化"""
    results = []
    
    for n_structures in [10, 50, 100, 200]:
        structures = [generate_mock_structure(n_cycles=5) for _ in range(n_structures)]
        bars_list = [generate_mock_bars(n=100) for _ in range(n_structures)]
        states = [generate_system_state(s) for s in structures]
        
        def make_run(strs, bs, sts):
            return lambda: [generate_signal(s, b, st) for s, b, st in zip(strs, bs, sts)]
        
        result = run_perf_test(
            make_run(structures, bars_list, states),
            name=f"内存测试({n_structures}结构)",
            iterations=100,
            track_memory=True,
            notes=f"结构数量: {n_structures}",
        )
        results.append(result)
    
    return results


def test_repeated_calculation_detection():
    """检测重复计算问题"""
    structure = generate_mock_structure(n_cycles=5)
    bars = generate_mock_bars(n=100)
    ss = generate_system_state(structure)
    
    # 测试多次调用时是否有重复计算
    results = []
    
    # 单次调用
    def run_once():
        return generate_signal(structure, bars, ss)
    
    r1 = run_perf_test(run_once, "单次调用", iterations=500)
    results.append(r1)
    
    # 连续调用（检测缓存效果）
    def run_consecutive():
        for _ in range(5):
            generate_signal(structure, bars, ss)
    
    r5 = run_perf_test(run_consecutive, "连续5次调用", iterations=100)
    r5.avg_time_ms = r5.avg_time_ms / 5  # 归一化到单次
    results.append(r5)
    
    # 连续10次调用
    def run_consecutive_10():
        for _ in range(10):
            generate_signal(structure, bars, ss)
    
    r10 = run_perf_test(run_consecutive_10, "连续10次调用", iterations=50)
    r10.avg_time_ms = r10.avg_time_ms / 10  # 归一化到单次
    results.append(r10)
    
    return results


# ═══════════════════════════════════════════════════════════
# 瓶颈分析
# ═══════════════════════════════════════════════════════════

def analyze_bottlenecks():
    """分析代码中的潜在瓶颈"""
    print("\n" + "="*60)
    print("瓶颈分析报告")
    print("="*60)
    
    analysis = """
基于代码审查的性能瓶颈分析:

1. 【statistics.median 调用】
   - 位置: detect_fake_breakout(), score_breakout_confirmation()
   - 问题: 每次调用都重新计算 volumes 的 median
   - 影响: O(n log n) 复杂度，大数据量时较慢
   - 建议: 如果 bars 不变，可以缓存 median 结果

2. 【列表推导式循环】
   - 位置: detect_pullback_confirmation() 中的 any()
   - 问题: had_breakout_up/down 每次都要遍历 bars[-10:-1]
   - 影响: 线性扫描，但可以接受
   - 建议: 如果性能敏感，可以维护一个突破状态缓存

3. 【assess_quality 重复计算】
   - 位置: generate_signal() 开头调用 assess_quality()
   - 问题: 如果外部已经评估过质量，这里会重复计算
   - 影响: 中等，涉及5个维度的评分计算
   - 建议: 允许传入预计算的 QualityAssessment

4. 【属性访问开销】
   - 位置: structure.zone.upper/lower/bandwidth 多次访问
   - 问题: 属性访问有轻微开销
   - 影响: 极小
   - 建议: 可以本地缓存这些值（已在代码中部分实现）

5. 【Signal 对象创建】
   - 位置: 多个信号创建点
   - 问题: dataclass 创建有一定开销
   - 影响: 小
   - 建议: 如果信号不返回，可以延迟创建
"""
    print(analysis)
    return analysis


# ═══════════════════════════════════════════════════════════
# 主测试入口
# ═══════════════════════════════════════════════════════════

def run_all_tests():
    """运行所有性能测试"""
    print("="*60)
    print("信号层性能测试报告")
    print("="*60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python版本: {sys.version}")
    print()
    
    all_results = []
    
    # 1. 基础单次测试
    print("\n" + "-"*60)
    print("测试1: 单次信号生成性能")
    print("-"*60)
    r = test_single_signal_generation()
    print(r)
    all_results.append(r)
    
    # 2. 不同K线数量对比
    print("\n" + "-"*60)
    print("测试2: 不同K线数量性能对比")
    print("-"*60)
    results = test_large_bars_comparison()
    for r in results:
        print(r)
        print()
        all_results.append(r)
    
    # 3. 不同cycle数量对比
    print("\n" + "-"*60)
    print("测试3: 不同Cycle数量性能对比")
    print("-"*60)
    results = test_structure_cycles_comparison()
    for r in results:
        print(r)
        print()
        all_results.append(r)
    
    # 4. 全市场扫描
    print("\n" + "-"*60)
    print("测试4: 全市场扫描性能")
    print("-"*60)
    r = test_full_market_scan()
    print(r)
    all_results.append(r)
    
    # 5. 子函数性能
    print("\n" + "-"*60)
    print("测试5: 子函数性能分解")
    print("-"*60)
    results = test_subfunction_performance()
    for r in results:
        print(r)
        print()
        all_results.append(r)
    
    # 6. 内存使用
    print("\n" + "-"*60)
    print("测试6: 内存使用可扩展性")
    print("-"*60)
    results = test_memory_usage_scalability()
    for r in results:
        print(r)
        print()
        all_results.append(r)
    
    # 7. 重复计算检测
    print("\n" + "-"*60)
    print("测试7: 重复计算检测")
    print("-"*60)
    results = test_repeated_calculation_detection()
    for r in results:
        print(r)
        print()
        all_results.append(r)
    
    # 8. 瓶颈分析
    analyze_bottlenecks()
    
    # 汇总
    print("\n" + "="*60)
    print("性能测试汇总")
    print("="*60)
    
    summary_data = []
    for r in all_results:
        summary_data.append({
            "测试项": r.name,
            "平均耗时(ms)": f"{r.avg_time_ms:.2f}",
            "内存峰值(MB)": f"{r.memory_peak_mb:.2f}" if r.memory_peak_mb > 0 else "-",
            "迭代次数": r.iterations,
        })
    
    # 打印表格
    print(f"{'测试项':<40} {'平均耗时(ms)':<15} {'内存(MB)':<12} {'迭代':<8}")
    print("-"*75)
    for row in summary_data:
        print(f"{row['测试项']:<40} {row['平均耗时(ms)']:<15} {row['内存峰值(MB)']:<12} {row['迭代次数']:<8}")
    
    return all_results


if __name__ == "__main__":
    results = run_all_tests()
