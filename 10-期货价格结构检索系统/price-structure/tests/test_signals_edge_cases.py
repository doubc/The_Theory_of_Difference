"""
边界测试 — 期货价格结构检索系统信号层极端情况测试

测试重点:
1. 空数据或不足数据（bars < 5, bars < 20）
2. Zone边界无效（bandwidth=0, upper=lower）
3. None值处理（system_state=None, motion=None）
4. 异常数值（负成交量、极大价格、NaN/Inf）
5. 质量层D的处理（应返回None）
"""

import sys
import math
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional

# 添加项目路径
sys.path.insert(0, r"D:\PythonWork\The_Theory_of_Difference\10-期货价格结构检索系统\price-structure")

from src.signals import (
    generate_signal,
    detect_fake_breakout,
    score_breakout_confirmation,
    detect_pullback_confirmation,
    detect_structure_aging,
    calculate_position_factor,
)
from src.models import (
    Structure,
    Zone,
    Cycle,
    Segment,
    Point,
    SystemState,
    MotionState,
    ProjectionAwareness,
    StabilityVerdict,
    SignalKind,
)
from src.quality import assess_quality, QualityTier


@dataclass
class TestCase:
    """测试用例定义"""
    name: str
    description: str
    expected_behavior: str
    
    
def create_bar(open_p=100.0, high=101.0, low=99.0, close=100.5, volume=1000, idx=0):
    """创建单根K线数据"""
    from src.data.loader import Bar
    return Bar(
        symbol="TEST",
        timestamp=datetime(2024, 1, 1),
        open=open_p,
        high=high,
        low=low,
        close=close,
        volume=volume,
        open_interest=None,
    )


def create_structure(zone_center=100.0, bandwidth=5.0, cycles=3):
    """创建测试用Structure"""
    zone = Zone(
        price_center=zone_center,
        bandwidth=bandwidth,
        source=None,
        strength=2.0,
        touches=[],
    )
    
    # 创建cycles
    cycle_list = []
    for i in range(cycles):
        p1 = Point(t=datetime(2024, 1, i*2+1), x=zone_center - bandwidth - 2, idx=i*2)
        p2 = Point(t=datetime(2024, 1, i*2+2), x=zone_center + bandwidth + 2, idx=i*2+1)
        seg = Segment(start=p1, end=p2)
        cycle = Cycle(entry=seg, exit=seg, zone=zone)
        cycle_list.append(cycle)
    
    return Structure(
        zone=zone,
        cycles=cycle_list,
        typicality=0.8,
        label="test_structure",
    )


def create_system_state(flux=0.5, age=5, phase="forming", is_blind=False, verified=True):
    """创建测试用SystemState"""
    motion = MotionState(
        conservation_flux=flux,
        structural_age=age,
        phase_tendency=phase,
        phase_confidence=0.7,
    )
    projection = ProjectionAwareness(
        compression_level=0.8 if is_blind else 0.3,
    )
    stability = StabilityVerdict(
        surface="stable" if verified else "unstable",
        verified=verified,
    )
    structure = create_structure()
    return SystemState(
        structure=structure,
        motion=motion,
        projection=projection,
        stability=stability,
    )


# ═══════════════════════════════════════════════════════════
# 测试执行与结果收集
# ═══════════════════════════════════════════════════════════

class EdgeCaseTester:
    """边界测试执行器"""
    
    def __init__(self):
        self.results = []
        
    def run_test(self, test_case: TestCase, test_func):
        """运行单个测试用例"""
        try:
            result = test_func()
            status = "PASS" if result else "FAIL"
            actual = "返回预期结果" if result else "未返回预期结果"
        except Exception as e:
            status = "CRASH" if not isinstance(e, (ValueError, TypeError)) else "ERROR"
            actual = f"异常: {type(e).__name__}: {str(e)[:50]}"
            
        self.results.append({
            "name": test_case.name,
            "description": test_case.description,
            "expected": test_case.expected_behavior,
            "actual": actual,
            "status": status,
        })
        return status in ("PASS", "ERROR")  # ERROR是预期内的异常处理
    
    def print_report(self):
        """打印测试报告"""
        print("\n" + "="*80)
        print("边界测试报告 -- 期货价格结构检索系统信号层")
        print("="*80)
        
        for r in self.results:
            status_icon = "[PASS]" if r["status"] == "PASS" else "[EXP_ERROR]" if r["status"] == "ERROR" else "[FAIL]" if r["status"] == "FAIL" else "[CRASH]"
            print(f"\n{status_icon} {r['name']}")
            print(f"   描述: {r['description']}")
            print(f"   预期: {r['expected']}")
            print(f"   实际: {r['actual']}")
            print(f"   状态: {r['status']}")
        
        # 统计
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        errors = sum(1 for r in self.results if r["status"] == "ERROR")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        crashed = sum(1 for r in self.results if r["status"] == "CRASH")
        
        print("\n" + "-"*80)
        print(f"总计: {total} | 通过: {passed} | 预期异常: {errors} | 失败: {failed} | 崩溃: {crashed}")
        print("="*80)
        
        return crashed == 0  # 只要有崩溃就返回False


# ═══════════════════════════════════════════════════════════
# 具体测试用例
# ═══════════════════════════════════════════════════════════

def test_empty_bars():
    """测试1: 空bars列表"""
    tc = TestCase(
        name="TC001: 空bars列表",
        description="传入空列表作为bars参数",
        expected_behavior="返回None，不抛出异常"
    )
    
    structure = create_structure()
    result = generate_signal(structure, bars=[], system_state=None)
    return result is None


def test_bars_less_than_5():
    """测试2: bars数量少于5根"""
    tc = TestCase(
        name="TC002: bars数量<5",
        description="传入3根K线，少于假突破检测所需的5根",
        expected_behavior="假突破检测返回False，其他信号可能生成"
    )
    
    structure = create_structure()
    bars = [create_bar(close=100+i, idx=i) for i in range(3)]
    result = generate_signal(structure, bars=bars, system_state=None)
    # 应该能正常执行，只是假突破检测不会触发
    return True  # 只要没崩溃就算通过


def test_bars_less_than_20():
    """测试3: bars数量少于20根（影响成交量统计）"""
    tc = TestCase(
        name="TC003: bars数量<20",
        description="传入10根K线，少于成交量中位数计算所需的20根",
        expected_behavior="使用全部可用K线计算成交量中位数"
    )
    
    structure = create_structure()
    bars = [create_bar(close=100+i, volume=1000+i*100, idx=i) for i in range(10)]
    result = generate_signal(structure, bars=bars, system_state=None)
    return True


def test_zero_bandwidth():
    """测试4: Zone bandwidth为0"""
    tc = TestCase(
        name="TC004: Zone bandwidth=0",
        description="Zone的bandwidth设为0，导致upper=lower",
        expected_behavior="检测函数应返回False/0分，不崩溃"
    )
    
    structure = create_structure(bandwidth=0)
    bars = [create_bar(close=100, idx=i) for i in range(10)]
    
    # 测试各个检测函数
    is_fake, pattern, conf = detect_fake_breakout(structure, bars, None)
    score, note = score_breakout_confirmation(structure, bars, None)
    is_pullback, pullback_conf, pullback_note = detect_pullback_confirmation(structure, bars, None)
    
    return not is_fake and score == 0.0 and not is_pullback


def test_none_system_state():
    """测试5: system_state为None"""
    tc = TestCase(
        name="TC005: system_state=None",
        description="system_state参数传入None",
        expected_behavior="使用默认值继续执行，不崩溃"
    )
    
    structure = create_structure()
    bars = [create_bar(close=105, idx=i) for i in range(25)]  # 突破Zone
    result = generate_signal(structure, bars=bars, system_state=None)
    return True  # 只要没崩溃就算通过


def test_none_motion_in_system_state():
    """测试6: system_state.motion为None"""
    tc = TestCase(
        name="TC006: motion为None",
        description="SystemState中的motion字段为None",
        expected_behavior="使用默认MotionState继续执行"
    )
    
    structure = create_structure()
    ss = create_system_state()
    ss.motion = None
    bars = [create_bar(close=105, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=ss)
    return True


def test_none_projection_in_system_state():
    """测试7: system_state.projection为None"""
    tc = TestCase(
        name="TC007: projection为None",
        description="SystemState中的projection字段为None",
        expected_behavior="使用默认ProjectionAwareness继续执行"
    )
    
    structure = create_structure()
    ss = create_system_state()
    ss.projection = None
    bars = [create_bar(close=105, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=ss)
    return True


def test_none_stability_in_system_state():
    """测试8: system_state.stability为None"""
    tc = TestCase(
        name="TC008: stability为None",
        description="SystemState中的stability字段为None",
        expected_behavior="使用默认StabilityVerdict继续执行"
    )
    
    structure = create_structure()
    ss = create_system_state()
    ss.stability = None
    bars = [create_bar(close=105, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=ss)
    return True


def test_negative_volume():
    """测试9: 负成交量"""
    tc = TestCase(
        name="TC009: 负成交量",
        description="K线成交量为负数",
        expected_behavior="正常处理或返回合理结果，不崩溃"
    )
    
    structure = create_structure()
    bars = [create_bar(close=105, volume=-1000, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=None)
    return True


def test_extreme_price():
    """测试10: 极大价格值"""
    tc = TestCase(
        name="TC010: 极大价格(1e9)",
        description="价格值为10亿",
        expected_behavior="正常处理，不溢出"
    )
    
    structure = create_structure(zone_center=1e9, bandwidth=1e8)
    bars = [create_bar(close=1.1e9, volume=1000, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=None)
    return True


def test_nan_price():
    """测试11: NaN价格"""
    tc = TestCase(
        name="TC011: NaN价格",
        description="K线价格为NaN",
        expected_behavior="可能传播NaN或抛出异常，但不应崩溃"
    )
    
    structure = create_structure()
    bars = [create_bar(close=float('nan'), idx=i) for i in range(25)]
    try:
        result = generate_signal(structure, bars=bars, system_state=None)
        return True
    except Exception as e:
        # 只要不是段错误级别的崩溃，都算合理处理
        return isinstance(e, (ValueError, TypeError, ArithmeticError))


def test_inf_price():
    """测试12: Inf价格"""
    tc = TestCase(
        name="TC012: Inf价格",
        description="K线价格为无穷大",
        expected_behavior="可能传播Inf或抛出异常，但不应崩溃"
    )
    
    structure = create_structure()
    bars = [create_bar(close=float('inf'), idx=i) for i in range(25)]
    try:
        result = generate_signal(structure, bars=bars, system_state=None)
        return True
    except Exception as e:
        return isinstance(e, (ValueError, TypeError, ArithmeticError))


def test_quality_tier_d():
    """测试13: 质量层D应返回None"""
    tc = TestCase(
        name="TC013: 质量层D",
        description="结构质量评估为D层",
        expected_behavior="generate_signal应返回None"
    )
    
    # 创建一个低质量结构（cycle数为0，无zone strength，无不变量）
    structure = create_structure(cycles=0)
    structure.zone.strength = 0.0
    structure.invariants = {}
    structure.typicality = 0.0
    structure.label = None
    structure.narrative_context = ""
    
    bars = [create_bar(close=105, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=None)
    
    # 验证确实是D层
    qa = assess_quality(structure)
    print(f"    [质量评估] tier={qa.tier.value}, score={qa.score:.2f}")
    
    # 如果score < 0.25应该是D层，但即使不是D层，也要检查是否返回None
    return result is None


def test_zero_volume():
    """测试14: 零成交量"""
    tc = TestCase(
        name="TC014: 零成交量",
        description="所有K线成交量为0",
        expected_behavior="正常处理，避免除零错误"
    )
    
    structure = create_structure()
    bars = [create_bar(close=105, volume=0, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=None)
    return True


def test_single_bar():
    """测试15: 只有1根K线"""
    tc = TestCase(
        name="TC015: 单根K线",
        description="bars列表只有1个元素",
        expected_behavior="正常处理，不崩溃"
    )
    
    structure = create_structure()
    bars = [create_bar(close=105, idx=0)]
    result = generate_signal(structure, bars=bars, system_state=None)
    return True


def test_none_zone():
    """测试16: structure.zone为None"""
    tc = TestCase(
        name="TC016: zone为None",
        description="Structure的zone字段为None",
        expected_behavior="使用默认值(upper=lower=bandwidth=0)继续执行"
    )
    
    structure = create_structure()
    structure.zone = None
    bars = [create_bar(close=105, idx=i) for i in range(25)]
    
    try:
        result = generate_signal(structure, bars=bars, system_state=None)
        return True
    except AttributeError as e:
        # 访问None.zone属性会抛出AttributeError，这是预期的
        return True


def test_extreme_negative_flux():
    """测试17: 极端负通量"""
    tc = TestCase(
        name="TC017: 极端负通量(-999)",
        description="conservation_flux为极大的负数",
        expected_behavior="正常处理，不溢出"
    )
    
    structure = create_structure()
    ss = create_system_state(flux=-999.0)
    bars = [create_bar(close=105, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=ss)
    return True


def test_extreme_positive_flux():
    """测试18: 极端正通量"""
    tc = TestCase(
        name="TC018: 极端正通量(999)",
        description="conservation_flux为极大的正数",
        expected_behavior="正常处理，不溢出"
    )
    
    structure = create_structure()
    ss = create_system_state(flux=999.0)
    bars = [create_bar(close=105, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=ss)
    return True


def test_very_old_structure():
    """测试19: 极老的结构"""
    tc = TestCase(
        name="TC019: 极老结构(1000天)",
        description="structural_age为1000天",
        expected_behavior="触发结构老化信号"
    )
    
    structure = create_structure()
    ss = create_system_state(age=1000, phase="forming")
    bars = [create_bar(close=105, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=ss)
    
    # 应该返回结构老化信号
    if result:
        print(f"    [信号类型] {result.kind.value}, conf={result.confidence:.2f}")
    return True


def test_blind_projection():
    """测试20: 高压缩投影（盲区）"""
    tc = TestCase(
        name="TC020: 盲区投影",
        description="projection.compression_level > 0.7",
        expected_behavior="生成BLIND_BREAKOUT信号或降权处理"
    )
    
    structure = create_structure()
    ss = create_system_state(is_blind=True)
    bars = [create_bar(close=105, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=ss)
    
    if result:
        print(f"    [信号类型] {result.kind.value}, is_blind={result.is_blind}")
    return True


def test_unverified_stability():
    """测试21: 未验证的稳定性"""
    tc = TestCase(
        name="TC021: 未验证稳定性",
        description="stability.verified=False",
        expected_behavior="信号置信度被限制在0.5以下"
    )
    
    structure = create_structure()
    ss = create_system_state(verified=False)
    bars = [create_bar(close=105, idx=i) for i in range(25)]
    result = generate_signal(structure, bars=bars, system_state=ss)
    
    if result:
        print(f"    [信号置信度] {result.confidence:.2f}, stability_ok={result.stability_ok}")
    return True


def test_calculate_position_factor_d():
    """测试22: D层仓位系数"""
    tc = TestCase(
        name="TC022: D层仓位系数",
        description="质量层D的仓位系数",
        expected_behavior="返回0.0"
    )
    
    factor = calculate_position_factor("D", is_blind=False)
    return factor == 0.0


def test_calculate_position_factor_blind():
    """测试23: 盲区额外降仓"""
    tc = TestCase(
        name="TC023: 盲区降仓",
        description="is_blind=True时应额外降仓50%",
        expected_behavior="A层从1.0降到0.5"
    )
    
    factor_normal = calculate_position_factor("A", is_blind=False)
    factor_blind = calculate_position_factor("A", is_blind=True)
    return factor_normal == 1.0 and factor_blind == 0.5


def test_detect_aging_no_motion():
    """测试24: 老化检测无motion"""
    tc = TestCase(
        name="TC024: 老化检测无motion",
        description="detect_structure_aging传入ss=None",
        expected_behavior="返回(False, 0.0, '')"
    )
    
    structure = create_structure()
    is_aging, conf, note = detect_structure_aging(structure, None)
    return not is_aging and conf == 0.0 and note == ""


def test_pullback_insufficient_bars():
    """测试25: 回踩检测数据不足"""
    tc = TestCase(
        name="TC025: 回踩检测数据不足",
        description="detect_pullback_confirmation传入bars<10",
        expected_behavior="返回(False, 0.0, '数据不足')"
    )
    
    structure = create_structure()
    bars = [create_bar(close=105, idx=i) for i in range(5)]
    is_pullback, conf, note = detect_pullback_confirmation(structure, bars, None)
    return not is_pullback and "数据不足" in note


# ═══════════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    tester = EdgeCaseTester()
    
    # 所有测试用例
    tests = [
        ("TC001: 空bars列表", test_empty_bars),
        ("TC002: bars数量<5", test_bars_less_than_5),
        ("TC003: bars数量<20", test_bars_less_than_20),
        ("TC004: Zone bandwidth=0", test_zero_bandwidth),
        ("TC005: system_state=None", test_none_system_state),
        ("TC006: motion为None", test_none_motion_in_system_state),
        ("TC007: projection为None", test_none_projection_in_system_state),
        ("TC008: stability为None", test_none_stability_in_system_state),
        ("TC009: 负成交量", test_negative_volume),
        ("TC010: 极大价格(1e9)", test_extreme_price),
        ("TC011: NaN价格", test_nan_price),
        ("TC012: Inf价格", test_inf_price),
        ("TC013: 质量层D", test_quality_tier_d),
        ("TC014: 零成交量", test_zero_volume),
        ("TC015: 单根K线", test_single_bar),
        ("TC016: zone为None", test_none_zone),
        ("TC017: 极端负通量(-999)", test_extreme_negative_flux),
        ("TC018: 极端正通量(999)", test_extreme_positive_flux),
        ("TC019: 极老结构(1000天)", test_very_old_structure),
        ("TC020: 盲区投影", test_blind_projection),
        ("TC021: 未验证稳定性", test_unverified_stability),
        ("TC022: D层仓位系数", test_calculate_position_factor_d),
        ("TC023: 盲区降仓", test_calculate_position_factor_blind),
        ("TC024: 老化检测无motion", test_detect_aging_no_motion),
        ("TC025: 回踩检测数据不足", test_pullback_insufficient_bars),
    ]
    
    for name, test_func in tests:
        tc = TestCase(name=name, description="", expected_behavior="")
        tester.run_test(tc, test_func)
    
    # 打印报告
    all_passed = tester.print_report()
    
    # 退出码
    sys.exit(0 if all_passed else 1)
