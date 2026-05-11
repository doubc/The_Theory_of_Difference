# Legacy 代码

此目录存放**脱离当前开发主线**的历史代码。

## 文件说明

| 文件 | 原位置 | 说明 |
|------|--------|------|
| `legacy_axiom_adapter.py` | `engine/axiom_adapter.py` | 早期公理适配器，已被 AxiomEngine.evaluate() 统一接口取代 |

## 注意事项

- 这些文件**不参与当前测试套件**，不应被 import
- 保留存档用途，不影响主干开发
- 如需恢复，参考 PROJECT_MAP.md 中的说明
