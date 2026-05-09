# 上下文交接文档

版本：V1.0 ｜ 更新：2026-05-08 12:06

---

## 当前状态

**Phase 2 已完成，已推送 GitHub。** 下一步是参数调优和文档补全。

---

## 本次会话完成的工作

### 代码变更（已推送）

**commit c73ce81 — Phase 2 实现**

- `transfer.py` → `transfer_and_transform()`：变形链引擎
- `entity.py` → `generate_feedback_differences()`：反馈差异生成
- `futures_rules.py` → `ExchangeIntervention` 三重干预 + 副作用差异
- `runner.py` → `_run_transfers_with_chain()`：集成变形链+反馈+干预
- `markdown_report.py`：报告新增变形链、反馈差异、干预记录章节
- `docs/拓扑即智慧对话.md`：David 与 Claude 的主体性对话

**commit b9386e9 — 守恒检查 + bug 修复**

- `difference.py`：`accumulate()` 不再自增 magnitude
- `runner.py`：实体吸收同步减少差异压力、破缺检查移到守恒之前
- `conservation.py`：步级压力守恒（tolerance=20.0）
- `break_event.py`：破缺释放压力追踪
- `exp_001`：新增 basis→price 通道

### 已验证的功能

| 功能          | 状态 | 说明                                          |
|-------------|----|---------------------------------------------|
| 变形链         | ✅  | inventory→basis→price→margin→liquidity 完整链路 |
| 反馈循环        | ✅  | margin/liquidity 差异从承接体正确生成                 |
| 干预多动作       | ✅  | 降低差异生成率/扩大通道容量/释放承接力 + 副作用差异                |
| 守恒检查        | ⚠️ | 基本通过，tolerance=20.0，已知偏差来自 transform 效率计算   |
| exp_001~005 | ✅  | 全部跑通                                        |

---

## 已知问题

### 1. 守恒检查偏差

- **现象**：部分步骤的"未解释"压力差 > 0
- **原因**：transform 效率计算用的是通道拥堵度的近似值，实际损耗更复杂
- **修复方向**：精确追踪每一步的 transform 效率，或改用差异级别的压力守恒

### 2. exp_005 参数问题

- **现象**：inventory_shortage 的 recurrent_rate=0.35 + magnitude=120 导致每步生成 42 压力
- **仓库容量**：warehouse_receipt_channel=35 + delivery_channel=45 = 80
- **结论**：生成 > 排放，系统永远无法收敛到稳态
- **修复方向**：降低 recurrent_rate 或增大通道容量，让系统有机会达到稳态

### 3. 变形差异无持续 drain

- **现象**：exp_001 中 basis 类型的变形差异无通道可走，压力保持不动
- **原因**：exp_001 只有 inventory→X 的通道，没有 basis→X 的通道
- **修复方向**：确保每个实验的通道覆盖变形链的每个环节

---

## 下一步计划

| 优先级 | 事项                          | 说明                                           |
|-----|-----------------------------|----------------------------------------------|
| P0  | 参数调优                        | 调整 exp_005 的 recurrent_rate 和通道容量，让系统能收敛     |
| P0  | `docs/08_phase2_results.md` | Phase 2 验证结果文档，记录每个实验的变形链轨迹                  |
| P1  | 守恒检查精确化                     | 精确计算 transform 效率损耗                          |
| P1  | 新实验设计                       | 专门验证反馈+干预组合效果（如：干预能否让系统从 unstable 走向 stable） |
| P2  | 心血来潮机制                      | 在心跳机制之外增加自发回溯，10%-15% 概率触发                   |
| P2  | 多品种支持                       | Phase 3 的前置：不同品种的差异可以互相转移                    |

---

## 关键文件索引

```
10-期货价格结构检索系统/期货市场概念的推理机分支/
├── real_world/
│   ├── core/
│   │   ├── difference.py    # 差异源（含 recurrent 机制）
│   │   ├── entity.py        # 承接体（含 generate_feedback_differences）
│   │   ├── channel.py       # 通道
│   │   └── world.py         # 世界容器
│   ├── engine/
│   │   ├── runner.py        # 主运行器（_run_transfers_with_chain）
│   │   ├── transfer.py      # 转移引擎（transfer_and_transform）
│   │   ├── conservation.py  # 守恒检查（步级压力守恒）
│   │   ├── break_event.py   # 破缺检查
│   │   ├── nearest_stable.py # 稳态判定
│   │   └── lock_in.py       # 锁定更新
│   ├── domains/futures/
│   │   ├── futures_rules.py # 变形规则 + ExchangeIntervention 三重干预
│   │   ├── commodity.py     # 商品
│   │   ├── contract.py      # 合约
│   │   └── region.py        # 现货地区
│   ├── io/
│   │   ├── yaml_loader.py   # YAML 配置加载
│   │   └── result_writer.py # 结果写出
│   └── reporting/
│       └── markdown_report.py # Markdown 报告（含变形链/反馈/干预章节）
├── experiments/futures/
│   ├── exp_001_inventory_basis.yaml    # 库存→基差
│   ├── exp_002_margin_pressure.yaml    # 保证金压力
│   ├── exp_003_near_month_squeeze.yaml # 近月逼仓
│   ├── exp_004_exchange_rule.yaml      # 规则调整
│   └── exp_005_full_topology.yaml      # 完整拓扑验证
├── docs/
│   ├── 00_project_book.md ~ 07_phase2_design.md
│   └── 拓扑即智慧对话.md
└── outputs/
    ├── traces/   # 轨迹 YAML
    ├── states/   # 状态 YAML
    └── reports/  # 报告 Markdown
```

---

## 铁律（不可违反）

- 不改第一性定义
- 不改写为价格预测/交易信号系统
- 不引入真实下单
- 不把差异清零
- 不只给结论必给路径
- 不把最近稳态解释为最优
- 不把模拟解释为现实预测

---

## 运行命令

```bash
cd 10-期货价格结构检索系统/期货市场概念的推理机分支

# 运行单个实验
python3 -m Real_world experiments/futures/exp_001_inventory_basis.yaml

# 运行全部实验
for exp in exp_001 exp_002 exp_003 exp_004 exp_005; do
  python3 -m Real_world "experiments/futures/${exp}_"*.yaml --quiet
done

# 运行测试
python3 -m pytest tests/ -v

# 推送（需设置 http 超时）
git config http.postBuffer 524288000
git config http.lowSpeedLimit 1000
git config http.lowSpeedTime 60
git push origin main
```

---

*下次接续时，读这个文件 + MEMORY.md + memory/2026-05-08.md 即可。*
