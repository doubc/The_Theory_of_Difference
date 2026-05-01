# 工作流程手册

> 一次完整迭代的标准化流程，从需求到上线。

---

## 流程总览

```
需求分析 → 代码实现 → 测试 → 复核 → 去重去冗余 → 推送 → 归档
```

每个阶段有明确的输入、输出、检查点。

---

## Phase 1: 需求分析

### 输入
- 用户口头描述 / GitHub Issue / 想法文档

### 输出
- 明确的功能清单 + 优先级排序

### 检查点
- [ ] 功能是否可拆分为独立模块？
- [ ] 是否与现有模块冲突？
- [ ] 实现量是否可控（单文件 < 600 行）？

---

## Phase 2: 代码实现

### 输入
- 功能清单

### 输出
- `.py` / `.c` / `.yaml` 源文件

### 文件放置规则

| 类型 | 目录 | 命名 |
|------|------|------|
| 核心算法 | `src/` | `snake_case.py` |
| C 扩展 | `src/fast/` | `_name.c` |
| Python 包装器 | `src/fast/` | `__init__.py` |
| 数据层 | `src/data/` | `xxx.py` |
| 编译器 | `src/compiler/` | `xxx.py` |
| 检索引擎 | `src/retrieval/` | `xxx.py` |
| 知识图谱 | `src/graph/` | `xxx.py` |
| 知识引擎 | `src/knowledge/` | `xxx.py` |
| 多时间维度 | `src/multitimeframe/` | `xxx.py` |
| 评分/信号 | `src/signals.py` `src/quality.py` | — |
| Streamlit Tab | `src/workbench/` | `tab_xxx.py` |
| Streamlit 页面 | `src/workbench/pages/` | `xxx_page.py` |
| 数据处理脚本 | `scripts/` | `action_target.py` |
| 交易策略 | `trading/` | `platform_strategy.py` |
| 品种知识配置 | `config/products/` | `{品种}/` 目录 |
| L1/L2/L3 知识 | `knowledge/` | `L{1,2,3}_xxx.yaml` |
| 文档 | `docs/` | `中文名.md` 或 `XX_名称.md` |
| 测试 | `tests/` | `test_xxx.py` |

### 代码规范
- 文件头必须有 docstring：模块职责、用法、与现有代码的关系
- 所有公共函数有类型注解
- 不修改现有文件（独立模块化，降低集成风险）
- PythonGO 策略文件必须自包含（不依赖 `src/` 内部模块）

### 检查点
- [ ] 导入路径正确（`from src.xxx import` 而非相对导入）
- [ ] 无硬编码路径（用 `Path` / 配置参数）
- [ ] 关键逻辑有注释

---

## Phase 3: 测试

### 输入
- 代码实现

### 输出
- 测试通过证据

### 三层测试

**Layer 1: 语法检查**

```bash
python3 -c "import ast; ast.parse(open('文件路径').read())"
```

**Layer 2: 逻辑验证**

构造 mock 数据，验证核心逻辑：
- 正常路径：预期输入 → 预期输出
- 边界条件：空列表、极端值、单元素
- 评分逻辑：高质量→A层，低质量→D层

**Layer 3: 集成验证**

用真实数据端到端测试：`load_bars()` → `compile_full()` → 检查结构数量。

### 检查点
- [ ] 所有文件语法检查通过
- [ ] 核心逻辑有 ≥2 个测试用例（正常+边界）
- [ ] 无 import 错误

---

## Phase 4: 复核

### 输入
- 测试通过的代码

### 复核维度

**4.1 逻辑正确性**
- 评分/分层逻辑是否符合设计意图？
- 方向判断是否正确（bullish/bearish）？
- 阈值是否合理？

**4.2 边界安全**
- 空列表处理：`len(x) == 0` 保护
- 除零保护：`if denominator > 0` / `max(denominator, 1e-9)`
- 类型错误：`float()` 转换包裹在 try/except

**4.3 性能**
- 无 O(n²) 循环（除非 n 受限）
- 大文件（>500 行）是否可以拆分？

**4.4 一致性**
- 函数命名风格与项目一致
- 数据结构与 `models.py` 对齐

### 检查点
- [ ] 空数据路径有容错
- [ ] 极端值不会崩溃
- [ ] 无明显性能问题

---

## Phase 5: 去重去冗余

### 输入
- 复核后的代码

### 检查项
- 未使用导入清理
- 重复逻辑检查
- 文件大小检查（>500 行需拆分）
- 孤立模块检查（grep 确认有引用方）

### 检查点
- [ ] 无未使用的 import
- [ ] 无未使用的函数/变量
- [ ] 重复逻辑已合并或标注原因
- [ ] 新模块已被至少一个入口文件 import

---

## Phase 6: 推送

### 输入
- 清理后的代码

### 检查点
- [ ] 文件路径正确
- [ ] 提交信息清晰
- [ ] 推送后验证文件存在

---

## Phase 7: 归档

### 输入
- 推送完成

### 操作
- 更新 `TASK_INDEX.md`（标记已完成任务）
- 更新 `CHANGELOG.md`（记录变更）
- 更新 `docs/待办事项.md`（移除已完成项）
- 如有新模块 → 更新 `docs/SUMMARY.md` 和 `README.md`

### 检查点
- [ ] TASK_INDEX.md 已同步
- [ ] CHANGELOG.md 已更新
- [ ] 文档与代码一致

---

## 模块挂载检查清单

新增模块后，用以下命令确认已正确挂载：

```bash
# 检查是否有引用
grep -rn "模块名" src/ --include="*.py" | grep -v __pycache__

# 检查孤立文件（0引用 = 可能需要删除或接入）
for f in src/workbench/*.py; do
  name=$(basename "$f" .py)
  count=$(grep -rl "$name" src/ --include="*.py" 2>/dev/null | wc -l)
  [ "$count" -eq 0 ] && echo "孤立: $f"
done
```

---

*最后更新：2026-05-01*
