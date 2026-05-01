# 金融知识图谱配置

## 核心思路：配置即知识

每个品种拥有独立目录，统一导入引擎按需加载。添加新品种只需新建文件夹 + 填 JSON + 注册到 registry.yaml，无需改任何 Python 代码。

## 目录结构

```
config/
├── keywords/                    # 全局关键词库
│   └── all.json                 # 431 条投研关键词
└── products/
    ├── registry.yaml            # 品种注册表
    ├── _template/               # 新品种模板（5 个空 JSON）
    ├── _shared/                 # 跨品种共享知识
    │   ├── entities.json        # 211 通用实体
    │   ├── relations.json       # 192 通用关系
    │   ├── chains.json          # 39 通用传导链
    │   └── polarity.json        # 30 通用极值
    ├── copper/                  # 铜
    │   ├── entities.json        # 35 铜实体
    │   ├── relations.json       # 23 铜关系
    │   ├── chains.json          # 7 铜传导链
    │   ├── polarity.json        # 7 铜极值
    │   └── pricing_models.json  # 5 铜定价模型
    ├── lithium_carbonate/       # 碳酸锂
    │   └── ...
    └── {新品种}/                # 以此类推
```

## 日常操作

### 添加新品种

```bash
# 方式一：复制模板
cp -r config/products/_template config/products/crude_oil
# 编辑每个 JSON 文件，填入 commodity、symbol 和数据

# 方式二：通过 ingester 代码
# 在 registry.yaml 中注册后，ingester 会自动加载
```

### 编辑数据

直接用文本编辑器改对应 JSON 文件：
- 改铜实体 → `config/products/copper/entities.json`
- 改通用关系 → `config/products/_shared/relations.json`
- 添加新关键词 → `config/keywords/all.json`

### 导入到图谱

```python
from src.graph.store import GraphStore
from src.graph.product_ingester import ProductKnowledgeIngester

store = GraphStore("data/graph")
ingester = ProductKnowledgeIngester(store)

# 全量导入（首次或强制刷新）
stats = ingester.ingest_all_active_products(force=True)

# 增量导入（仅更新有变化的品种）
stats = ingester.ingest_all_active_products(force=False)

# 重新导入单个品种
stats = ingester.reload_product("copper")
```

### 冒烟测试

```bash
python3 scripts/smoke_test_finance_graph.py
```

## registry.yaml 格式

```yaml
products:
  copper:
    symbol: "CU"
    name: "电解铜"
    status: "active"          # active / draft / deprecated
    last_updated: "2026-05-01"
    tags: ["base_metal", "macro_sensitive"]
    files:
      entities: "copper/entities.json"
      relations: "copper/relations.json"
      chains: "copper/chains.json"
      polarity: "copper/polarity.json"
      pricing_models: "copper/pricing_models.json"
```

- `status: active` → 每次导入都会加载
- `status: draft` → 导入时跳过，可手动 reload
- `status: deprecated` → 永久跳过

## JSON 文件格式

### entities.json

```json
{
  "commodity": "铜",
  "symbol": "CU",
  "version": "1.3.0",
  "entities": [
    {
      "id": "GEO_066",
      "name": "智利Escondida铜矿",
      "type": "资源节点",
      "groundBase": "natural",
      "importance": 10,
      "description": "...",
      "controlledBy": ["BHP"],
      "vulnerabilities": ["工会罢工风险"],
      "trackingVariables": ["年度产量"]
    }
  ]
}
```

### relations.json

```json
{
  "commodity": "铜",
  "symbol": "CU",
  "version": "1.3.0",
  "relations": [
    {
      "id": "R_201",
      "type": "产业链传导",
      "from": "铜矿罢工",
      "to": "铜精矿供应",
      "strength": 0.85,
      "direction": "反向",
      "groundBase": "natural",
      "description": "..."
    }
  ]
}
```

### chains.json

```json
{
  "commodity": "铜",
  "symbol": "CU",
  "version": "1.3.0",
  "chains": [
    {
      "id": "C_041",
      "name": "铜矿罢工供给冲击链",
      "domain": "有色金属",
      "triggerEvent": "铜矿工人罢工",
      "steps": [
        {"seq": 1, "from": "铜矿罢工", "to": "铜精矿供应下降", "confidence": "高", "lag": "即时", "mechanism": "..."}
      ],
      "reversalNode": "复工",
      "reversalCondition": "...",
      "polarityTensionThreshold": 0.8
    }
  ]
}
```

### polarity.json

```json
{
  "commodity": "铜",
  "symbol": "CU",
  "version": "1.3.0",
  "entries": {
    "LME铜价": {
      "historicalMin": 4000,
      "historicalMax": 10800,
      "recentMin": 8000,
      "recentMax": 9800,
      "reversalSignalPatterns": ["库存暴增", "中国需求放缓"]
    }
  }
}
```

### pricing_models.json

```json
{
  "commodity": "铜",
  "symbol": "CU",
  "version": "1.3.0",
  "models": [
    {
      "id": "M_001",
      "name": "铜的实际利率定价模型",
      "domain": "宏观金融定价",
      "formula": "Δln(Cu) = α + β1*Δln(1/RealRate) + β2*Δln(DXY) + β3*Δln(PMI) + ε",
      "variables": [...],
      "linkToEntities": ["VAR_004", "VAR_003"]
    }
  ]
}
```

## ID 编号规则

品种专属实体以品种前缀命名空间隔离（如 `cu:GEO_066`），避免冲突。

| 类型 | 前缀 | 当前最大ID | 新增从 |
|------|------|-----------|--------|
| 地理节点 | GEO_ | 072 | 073+ |
| 权力机构 | POW_ | 067 | 068+ |
| 规则框架 | RUL_ | 032 | 033+ |
| 共识叙事 | CUL_ | 032 | 033+ |
| 核心变量 | VAR_ | 072 | 073+ |
| 关系 | R_ | 215 | 216+ |
| 传导链 | C_ | 046 | 047+ |
| 定价模型 | M_ | 005 | 006+ |

## 品种间联动

`_shared/relations.json` 中可定义跨品种关系，导入时自动识别带 `:` 前缀的节点 ID：

```json
{"id": "R_XXX", "type": "跨品种联动", "from": "copper:LME铜价", "to": "_shared:原油价格", "strength": 0.6}
```

## 数据规模参考

| 品种 | 实体 | 关系 | 传导链 | 极值 | 模型 |
|------|------|------|--------|------|------|
| _shared | 211 | 192 | 39 | 30 | — |
| copper | 35 | 23 | 7 | 7 | 5 |
| lithium | 5 | 0 | 0 | 1 | — |
