# 稳定性检测和盲区检测失效调试方案

## 调试目标

1. **为什么 90.6% 结构的稳定性状态为 "unknown"？**
2. **为什么所有盲区占比为 0%？**

---

## 根因假设

### 假设1: detect_stability_illusion 未被正确调用
- `detect_stability_illusion` 函数在 `build_system_state` 中被调用
- 但 `compile_full` 中构建 `system_states` 时，可能没有正确传播结果到 `Structure`

### 假设2: 数据在传递过程中丢失
- `build_system_state` 中设置了 `s.stability_verdict = stability`
- 但 `compile_full` 返回的 `structures` 列表中的对象可能不是同一个引用

### 假设3: 盲区检测条件过于严格
- `compute_projection` 中 `is_blind` 的判断条件是 `compression_level > 0.7`
- 但 `compression_level` 的计算可能有问题

### 假设4: pipeline 中 system_states 和 structures 不匹配
- `compile_full` 返回的 `system_states` 和 `structures` 是分开的列表
- 可能存在索引错位或数据不一致

---

## 关键检查点列表

### 检查点1: detect_stability_illusion 返回值
**位置**: `src/relations.py:detect_stability_illusion()`

**检查内容**:
```python
verdict = detect_stability_illusion(structure, bars)
# 检查:
# - verdict.surface ("stable" | "unstable")
# - verdict.verified (True | False)
# - verdict.pending_channels (列表)
# - verdict.verdict_label (字符串)
```

**预期行为**:
- 如果 `zone.relative_bandwidth < 0.015`，`surface` 应该为 `"stable"`
- 如果有 `pending_channels`，`verified` 应该为 `False`

**常见问题**:
- 函数返回了正确的 `StabilityVerdict`，但调用者没有使用

---

### 检查点2: build_system_state 中 s.stability_verdict 赋值
**位置**: `src/relations.py:build_system_state()`

**检查内容**:
```python
# 在 build_system_state 函数末尾
s.stability_verdict = stability  # 这行是否执行？
return SystemState(...)
```

**预期行为**:
- `structure.stability_verdict` 应该被正确赋值
- 返回的 `SystemState.stability` 应该与 `structure.stability_verdict` 一致

**常见问题**:
- `structure` 对象在赋值后没有被保存，导致数据丢失
- `SystemState` 中的 `stability` 是重新创建的，不是 `detect_stability_illusion` 返回的

---

### 检查点3: compile_full 返回的 structures
**位置**: `src/compiler/pipeline.py:compile_full()`

**检查内容**:
```python
# 在 compile_full 函数中
for st in structures:
    ss = build_system_state(st, window_bars)
    system_states.append(ss)
    # 检查: st.stability_verdict 是否被设置？
```

**预期行为**:
- 每个 `structure` 在 `build_system_state` 调用后应该有 `stability_verdict`
- `result.structures` 中的对象应该保留这些赋值

**常见问题**:
- `structures` 列表在 `assemble_structures` 中创建
- `build_system_state` 修改了 `st`，但如果 `st` 是值类型或拷贝，修改不会保留

---

### 检查点4: generate_signal 接收的 ss.stability
**位置**: `src/signals.py:generate_signal()`

**检查内容**:
```python
stability = ss.stability if ss and ss.stability else StabilityVerdict()
stability_ok = stability.surface not in ["ILLUSION", "UNSTABLE"]
```

**预期行为**:
- `ss.stability` 应该有正确的 `surface` 值
- `stability_ok` 应该基于实际的稳定性状态

**常见问题**:
- 如果 `ss.stability` 是默认值 `StabilityVerdict()`，`surface` 会是 `"unstable"`
- 这可能导致所有信号都被标记为不稳定

---

## 调试脚本设计

### 脚本位置
`debug_stability_blind.py`

### 运行方式
```bash
cd D:\PythonWork\The_Theory_of_Difference\10-期货价格结构检索系统\price-structure
python debug_stability_blind.py
```

### 脚本功能

1. **创建最小测试用例**
   - 60根K线的价格序列
   - 形成明显的Zone结构（3次试探）
   - 最后10天模拟高压缩场景

2. **执行5个检查点**
   - 检查点1: `detect_stability_illusion` 返回值
   - 检查点2: `build_system_state` 中 `stability_verdict` 赋值
   - 检查点3: `compile_full` 返回的 `structures`
   - 检查点4: `generate_signal` 接收的 `ss.stability`
   - 检查点5: `compile_full` 中 `system_states` 构建流程

3. **生成对比报告**
   - 预期值 vs 实际值
   - 标记不一致的地方
   - 输出JSON格式的详细结果

---

## 预期 vs 实际对比方法

### 稳定性状态分布

| 预期 | 实际 | 诊断 |
|------|------|------|
| 大部分结构有 `stability_verdict` | ?% 有 `stability_verdict` | 如果 < 100%，检查 `build_system_state` 是否被调用 |
| 带宽压缩的结构 `surface="stable"` | ?% 为 `stable` | 如果比例过低，检查 `detect_stability_illusion` 逻辑 |
| 有 `pending_channels` 的 `verified=False` | ?% 为 `verified` | 检查验证逻辑 |

### 盲区检测

| 预期 | 实际 | 诊断 |
|------|------|------|
| 高压缩结构 `is_blind=True` | ?% 为 `True` | 如果为 0%，检查 `compute_projection` 中的压缩度计算 |
| `compression_level > 0.7` 触发盲区 | 实际压缩度分布 | 检查压缩度阈值是否合理 |

---

## 可能的修复方案

### 方案A: 修复 build_system_state 中的赋值
```python
def build_system_state(s: Structure, bars: list | None = None) -> SystemState:
    # ... 前面的计算 ...
    
    # 错觉检测
    stability = detect_stability_illusion(s, bars)
    
    # 确保赋值被保存
    s.stability_verdict = stability
    s.liquidity_stress = liq
    s.fear_index = fear
    s.time_compression = tcomp
    
    # 创建 SystemState 时传入同一个 stability 对象
    return SystemState(
        structure=s,
        motion=s.motion,
        projection=s.projection,
        stability=stability,  # 使用同一个对象
        liquidity_stress=liq,
        fear_index=fear,
        time_compression=tcomp,
    )
```

### 方案B: 修复 compile_full 中的循环
```python
# 在 compile_full 中
system_states = []
for st in structures:
    st.narrative_context = infer_narrative_context(st)
    if st.t_start and st.t_end:
        window_bars = filter_bars(bars, st.t_start, st.t_end)
    else:
        window_bars = bars
    
    ss = build_system_state(st, window_bars)
    system_states.append(ss)
    
    # 添加断言检查
    assert st.stability_verdict is not None, f"Structure {st} 没有 stability_verdict"
```

### 方案C: 修复 generate_signal 中的默认值处理
```python
def generate_signal(structure, bars, system_state=None):
    # ...
    ss = system_state
    
    # 修复：正确处理 ss.stability 为 None 的情况
    if ss and ss.stability and ss.stability.surface != "unstable":
        stability = ss.stability
    else:
        # 重新计算或标记为未验证
        stability = detect_stability_illusion(structure, bars)
    
    stability_ok = stability.surface not in ["ILLUSION", "UNSTABLE", "unstable"]
```

---

## 调试输出文件

运行脚本后会生成 `debug_stability_blind_results.json`，包含：

```json
{
  "checkpoint_1": {
    "surface": "stable",
    "verified": false,
    "pending_channels": ["shorter_timeframe", "volume"],
    ...
  },
  "checkpoint_2": {
    "structure_stability": {...},
    "system_state_stability": {...},
    "consistent": true/false
  },
  "checkpoint_3": {
    "total_structures": N,
    "with_stability_verdict": M,
    "stable_count": K,
    "blind_count": L,
    ...
  },
  ...
}
```

---

## 下一步行动

1. 运行 `python debug_stability_blind.py`
2. 查看控制台输出，定位问题检查点
3. 分析 `debug_stability_blind_results.json`
4. 根据诊断结果选择修复方案（A/B/C）
5. 验证修复后重新运行调试脚本
