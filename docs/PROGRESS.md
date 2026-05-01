# PROGRESS — 实盘增强改造进度

> 基于 10 年期货交易者内审意见的改造记录
> 审查日期: 2026-04-26

---

## ✅ 已完成

### B-01 假突破拆分增强 (v4.1)

**原状态**: 5 种假突破模式 (FAKE_PIN / FAKE_DSPIKE / FAKE_VOLDIV / FAKE_BLIND_WHIP / FAKE_GAP)
**现状态**: 7 种模式，优先级调度

新增:
- `FAKE_WICK_CLUSTER` (连续影线簇): 3-5 根 K 线影线探出 Zone 外、实体在 Zone 内，盘整末期常见
- `FAKE_TIME_TRAP` (时间陷阱): 突破后 Zone 外停留 2-5 天无后续动能，再回归

优先级顺序:
```
FAKE_GAP > FAKE_PIN > FAKE_DSPIKE > FAKE_VOLDIV > FAKE_WICK_CLUSTER > FAKE_TIME_TRAP > FAKE_BLIND_WHIP
```

文件: `src/signals.py` — `_detect_fake_wick_cluster()`, `_detect_fake_time_trap()`
配置: `src/config/__init__.py` — `FAKE_WICK_*`, `FAKE_TIME_TRAP_*`

### B-03 入场价增强 (v4.1)

**原状态**: Signal 只有 `entry_price`
**现状态**: 新增入场偏差容忍度

- `entry_limit_upper`: 做多时可接受的最高入场价 (Zone下沿 + 0.2×bandwidth)
- `entry_limit_lower`: 做空时可接受的最低入场价 (Zone上沿 - 0.2×bandwidth)
- 假突破入场 = Zone 边界，其他信号入场 = last_close

文件: `src/signals.py` — `generate_signal()` 中各信号创建块
配置: `src/config/__init__.py` — `ENTRY_TOLERANCE_RATIO = 0.2`

### B-04 交易计划增强 (v4.1)

**原状态**: 单行格式 `品种 方向 | 入场 | 止损 | 目标 | 仓位 | 盈亏比`
**现状态**: 4 行实盘格式

```
CU000 60min | 📈做多·假突破反向(PIN)
入场 77500(Zone边界) | 可接受 ≤77540 | 当前 77620 | 止损 77200(-0.4%) | 目标 79000(+1.9%)
仓位 60%(B层) | 盈亏比 3.0:1 | 🟢 绿灯
⚠️ 有效期: 2根K线内 | 通量方向一致 ✅ | ATR=150.0
```

新增参数: `current_price` (当前市价，用于对比入场价)

文件: `src/signals.py` — `generate_trade_plan()`

### 止损逻辑 ATR 化 (v4.1)

**原状态**: 硬编码 `0.3×bandwidth`
**现状态**: ATR 驱动，按质量层调整

| 质量层 | ATR 倍数 | 含义 |
|--------|---------|------|
| A | 1.5 | 紧止损 |
| B | 2.0 | 标准 |
| C | 2.5 | 宽松 |

无 ATR 数据时 fallback 到 bandwidth 方式。

文件: `src/signals.py` — `compute_atr()`, `_compute_risk_reward()`
配置: `src/config/__init__.py` — `ATR_MULTIPLIER`, `ATR_PERIOD = 14`

### 信号时效 (TTL) (v4.1)

Signal 新增字段:
- `timeframe`: 时间框架标记 ("60min" / "15min" / "daily")
- `ttl_bars`: 信号有效期 (K 线根数)
- `signal_bars_index`: 信号生成时的 K 线索引
- `atr_value`: 信号生成时的 ATR 值

各信号类型 TTL:
```
假突破: 2 根 | 突破确认: 5 根 | 回踩确认: 5 根 | 盲区突破: 3 根 | 结构老化: 0 (即时)
```

### 测试

- `tests/test_signals.py`: 11/11 通过 (含 5 个新增用例)
- `tests/test_signals_edge_cases.py`: 25/25 通过
- GitHub Actions CI: `.github/workflows/test.yml` 已创建并推送

### Git 提交

```
be596c1 feat(signals): 实盘增强 — ATR止损/入场偏差/TTL/交易计划/7种假突破模式
617d1b8 ci: 添加 signal 层测试 workflow
```

---

## ❌ 未做 (下次接力)

### 🔴 高优先级

1. **多周期共振**
   - 日线 + 60min 方向一致 → 置信度提升
   - 需要 `multitimeframe/comparator.py` 与 `signals.py` 联动
   - 目前 `tab_multitime.py` 有跨周期展示，但没有参与信号过滤

2. **品种级参数差异化**
   - 铜、螺纹、豆粕波动率差异巨大，目前 ATR 倍数是全局统一的
   - 建议: `config/` 下按品种加 `symbol_overrides.yaml`
   - 或者根据 ATR 自动调整倍数（ATR 高的品种自动收紧）

3. **滑点和手续费纳入盈亏比**
   - 当前 `rr_ratio` 是理论值，没扣滑点和手续费
   - 建议: `_compute_risk_reward` 加 `slippage_ticks` 和 `commission_per_lot` 参数
   - 不同品种的手续费差异很大（股指 vs 农产品）

### 🟡 中优先级

4. **持仓量 (open interest) 辅助过滤**
   - `Bar.open_interest` 字段已有但未参与信号判断
   - 增仓突破 vs 减仓突破含义完全不同
   - 可作为 FAKE_VOLDIV 的增强条件

5. **信号有效期的实盘执行**
   - `ttl_bars` 和 `signal_bars_index` 已加到 Signal 对象
   - 但 `generate_signal()` 没有检查"当前信号是否已过期"
   - 需要加一个 `is_expired(current_bars_index)` 方法

6. **FAKE_NEWS_SPIKE (消息面脉冲)**
   - 重大数据发布导致的瞬间突破，15-30 分钟内回归
   - 需要分钟级数据才能识别，当前基于日线/小时线抓不到
   - 等有分钟数据源再做

### 🟢 低优先级

7. **B-02 术语优化** — 对交易决策无影响，最后做
8. **品种特性文档** — 每个品种的波动特征、交易时段、保证金率
9. **回测验证** — 用历史数据验证 7 种假突破模式的胜率

---

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/config/__init__.py` | 新增 | ATR/TTL/入场偏差/新模式参数 |
| `src/models.py` | 修改 | FakeBreakoutPattern +7种, Signal +6字段, +signal_type_label |
| `src/signals.py` | 重写 | ATR止损, 2个新模式, 入场偏差, TTL, 交易计划 |
| `src/workbench/tab_scan.py` | 修改 | 传入 timeframe="daily" |
| `tests/test_signals.py` | 修改 | +5个测试用例 (新模式/ATR/偏差/TTL/交易计划) |
| `.github/workflows/test.yml` | 新增 | CI 测试 workflow |
