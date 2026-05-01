# 知识库 — L1/L2/L3 三层知识体系

> 知识不替代图谱。图谱承载拓扑，知识承载语义。

## 三层结构

| 层 | 文件 | 回答 | 示例 |
|----|------|------|------|
| L1 判定知识 | `L1_conditions.yaml` | 这个结构该信多少 | 趋势可靠性递增、高质量结构 |
| L2 失效知识 | `L2_invalidation.yaml` | 什么条件下判断作废 | 趋势通量背离、结构老化 |
| L3 市场知识 | `L3_wisdom.yaml` | 有什么值得注意的 | 铜 Zone 带宽常识、慢涨急跌 |

## 使用方式

```python
from src.knowledge import KnowledgeEngine

engine = KnowledgeEngine("knowledge")
result = engine.evaluate(structure=s, motion=m, symbol="CU")

# 判定知识
for r in result.conditions:
    print(f"✅ {r.verdict}")

# 失效警告
for r in result.invalidations:
    print(f"🔴 {r.invalidate}")

# 市场智慧
for r in result.wisdoms:
    print(f"💡 {r.wisdom}")

# 置信度调整
print(f"confidence_boost: {result.confidence_boost:+.2f}")
```

## 与质量评估集成

```python
from src.quality import assess_quality_with_knowledge

qa, kr = assess_quality_with_knowledge(structure, system_state)
print(qa.tier, qa.score)
print(kr.summary())
```

## 添加新知识

在对应 YAML 文件中添加规则条目即可。字段说明见 `docs/16_知识注入系统.md`。

## 知识来源

- 公理体系（A0-A10）
- 历史回测
- 品种经验
- DSL 规则
- ContrastType 定义
