# signals.py 工程设计文档

## 1. 模块定位

- **文件路径**: `src/signals.py`
- **职责**: 交易信号判断逻辑，独立于扫描逻辑，不发起额外市场数据请求
- **输入**: 现有扫描数据（Structure、SystemState、Bar序列）
- **输出**: Signal对象或None

## 2. 核心函数签名

```python
from dataclasses import dataclass
from typing import List, Optional, Tuple
from src.models import Structure, SystemState, Signal, SignalKind, FakeBreakoutPattern
from src.data.loader import Bar

def generate_signal(
    structure: Structure,
    bars: List[Bar],
    system_state: Optional[SystemState] = None,
) -> Optional[Signal]:
    """
    主入口：为给定结构生成交易信号
    
    逻辑流程:
    1. 前置过滤（质量层D/盲区/红灯 → 返回None或降级信号）
    2. 检测假突破5模式（优先级最高）
    3. 检测突破确认
    4. 检测回踩确认
    5. 检测结构老化
    6. 返回最高优先级信号
    """
    ...

def detect_fake_breakout(
    structure: Structure,
    bars: List[Bar],
    ss: SystemState,
) -> Tuple[bool, Optional[FakeBreakoutPattern], float]:
    """
    检测假突破及模式识别
    
    Returns:
        (是否假突破, 模式类型, 置信度)
    """
    ...

def score_breakout_confirmation(
    structure: Structure,
    bars: List[Bar],
    ss: SystemState,
) -> Tuple[float, str]:
    """
    5维突破评分
    
    Returns:
        (评分0-1, 评分说明)
        
    5维度权重:
        - 收盘穿透深度: 0.25
        - 量能扩张比: 0.25
        - 通量一致性: 0.15
        - 压缩蓄势度: 0.20
        - 驻留时间比: 0.15
    """
    ...

def detect_pullback_confirmation(
    structure: Structure,
    bars: List[Bar],
    ss: SystemState,
) -> Tuple[bool, float, str]:
    """
    检测回踩确认
    
    Returns:
        (是否确认, 置信度, 说明)
    """
    ...

def detect_structure_aging(
    structure: Structure,
    ss: SystemState,
) -> Tuple[bool, float, str]:
    """
    检测结构老化/失效
    
    Returns:
        (是否老化, 置信度, 说明)
    """
    ...

def calculate_position_factor(quality_tier: str, is_blind: bool) -> float:
    """
    计算仓位系数
    
    A=1.0, B=0.6, C=0.3, D=0
    盲区额外×0.5
    """
    ...
```

## 3. 假突破5模式判定规则

### FAKE_PIN (探针型)
```
触发条件:
    1. 最近1根K线盘中穿透Zone边界 (high > upper 或 low < lower)
    2. 收盘价回到Zone内 (close < upper 且 close > lower)
    3. conservation_flux方向与穿透方向相反
    4. 穿透幅度 > 0.3 * bandwidth

置信度: 0.7-0.9 (flux反向确认时0.9)
```

### FAKE_DSPIKE (单K极端)
```
触发条件:
    1. 单根K线产生极端价格 (影线长度 > 2 * 实体长度)
    2. 该K线大部分时间在Zone内 (open和close都在Zone内)
    3. 成交量 > 近期均值 * 1.5 (量能峰值)
    4. conservation_flux绝对值 < 阈值 (通量弱)

置信度: 0.6-0.8
```

### FAKE_VOLDIV (量能背离)
```
触发条件:
    1. 价格突破Zone边界 (close > upper 或 close < lower)
    2. 突破日成交量 < 近期中位数 * 0.8 (量能萎缩)
    3. conservation_flux方向与突破方向相反或接近0

置信度: 0.65-0.85
```

### FAKE_BLIND_WHIP (盲区抽鞭)
```
触发条件:
    1. is_blind == True
    2. 快速突破Zone边界后无后续 (突破后N根K线价格回归)
    3. 突破后conservation_flux迅速衰减或反向
    4. 突破K线后成交量快速萎缩

置信度: 0.55-0.75
```

### FAKE_GAP (跳空回补)
```
触发条件:
    1. 跳空突破Zone边界 (gap up > upper 或 gap down < lower)
    2. 当日回补缺口 (close回到Zone内或接近)
    3. conservation_flux方向与跳空方向相反

置信度: 0.7-0.9
```

## 4. 5维突破评分计算

```python
def score_breakout_confirmation(structure, bars, ss):
    # 获取最新价格和Zone边界
    last_bar = bars[-1]
    last_close = last_bar.close
    upper = structure.zone.upper
    lower = structure.zone.lower
    bandwidth = structure.zone.bandwidth
    
    # 1. 收盘穿透深度 (0.25)
    if last_close > upper:  # 向上突破
        penetration = (last_close - upper) / bandwidth
    elif last_close < lower:  # 向下突破
        penetration = (lower - last_close) / bandwidth
    else:
        penetration = 0
    score_penetration = min(penetration / 0.5, 1.0)  # 0.5带宽为满分
    
    # 2. 量能扩张比 (0.25)
    recent_volumes = [b.volume for b in bars[-20:]]
    median_vol = sorted(recent_volumes)[len(recent_volumes)//2]
    current_vol = last_bar.volume
    volume_ratio = current_vol / median_vol if median_vol > 0 else 1
    score_volume = min(volume_ratio / 2.0, 1.0)  # 2倍量为满分
    
    # 3. 通量一致性 (0.15)
    flux = ss.motion.conservation_flux if ss and ss.motion else 0
    direction = 1 if last_close > upper else -1
    flux_aligned = (flux * direction) > 0
    score_flux = 1.0 if flux_aligned and abs(flux) > 0.3 else 0.5 if flux_aligned else 0
    
    # 4. 压缩蓄势度 (0.20)
    # 使用structure.cycle_count和time_compression估算
    n_tests = structure.cycle_count
    score_compression = min(n_tests / 5, 1.0)  # 5次试探为满分
    
    # 5. 驻留时间比 (0.15)
    # 价格突破前在Zone内的时间占比
    # 简化为：结构形成天数 / 30
    days = ss.motion.structural_age if ss and ss.motion else 0
    score_dwell = min(days / 10, 1.0)  # 10天为满分
    
    # 加权总分
    total_score = (
        score_penetration * 0.25 +
        score_volume * 0.25 +
        score_flux * 0.15 +
        score_compression * 0.20 +
        score_dwell * 0.15
    )
    
    return total_score, f"穿透{score_penetration:.0%}/量能{score_volume:.0%}/通量{score_flux:.0%}/压缩{score_compression:.0%}/驻留{score_dwell:.0%}"
```

## 5. 信号优先级与阈值

```
评分区间:
    ≥0.80 → 强突破确认 (confidence=0.85-0.95)
    0.55-0.80 → 待观察突破 (confidence=0.60-0.80)
    <0.55 → 弱突破/假突破 (confidence<0.60，触发假突破检测)

信号优先级 (数字小优先):
    1. FAKE_BREAKOUT (假突破反向)
    2. BREAKOUT_CONFIRM (突破确认)
    3. PULLBACK_CONFIRM (回踩确认)
    4. BLIND_BREAKOUT (盲区突破观察)
    5. STRUCTURE_EXPIRED (结构老化)
```

## 6. 集成到tab_scan.py

在 `_scan_all_symbols()` 的结果字典中新增字段:
```python
{
    "signal": signal.to_dict() if signal else None,
    "signal_display": signal.display_label if signal else "无信号",
}
```

在卡片渲染中添加信号区块 (在fresh_tag之后):
```python
signal_html = ""
if r.get("signal"):
    sig = r["signal"]
    sig_color = "#4caf50" if sig["confidence"] >= 0.8 else "#ff9800" if sig["confidence"] >= 0.55 else "#999"
    sig_icon = "🚨" if sig["kind"] == "fake_breakout" else "✅" if sig["kind"] == "breakout_confirm" else "📍"
    signal_html = f'<div style="margin-top:4px"><span style="color:{sig_color};font-weight:600">{sig_icon} {sig["display_label"]} {sig["display_direction"]} (置信{sig["confidence"]:.0%})</span></div>'
```

## 7. 依赖导入

```python
from src.models import (
    Structure, SystemState, Signal, SignalKind, FakeBreakoutPattern,
    MotionState, StabilityVerdict, ProjectionAwareness
)
from src.data.loader import Bar
from src.quality import assess_quality
from typing import List, Optional, Tuple
import statistics
```

## 8. 实现要点

1. **前置过滤**: quality_tier为D时返回None；stability_verdict为红灯时confidence封顶0.5
2. **盲区处理**: is_blind=True时生成BLIND_BREAKOUT信号，但confidence×0.6，position_size_factor×0.5
3. **flux核心**: 所有信号必须检查flux_aligned，这是4视角共识
4. **止损提示**: 基于Zone边界生成stop_loss_hint (如"Zone.center - 0.5×bandwidth")
5. **向后兼容**: 函数签名设计允许未来扩展，如添加更多参数不改变现有调用
