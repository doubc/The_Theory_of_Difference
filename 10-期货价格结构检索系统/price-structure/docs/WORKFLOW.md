# 价格结构检索系统 — 完整工作流程手册

> 一次完整迭代的标准化流程，从需求到上线。
> 本手册基于 2026-04-24 的实际工作整理。

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

### 操作步骤
1. 阅读现有代码，理解项目架构
2. 阅读 `下一步有趣的想法.md`，了解已有想法
3. 与用户确认优先级（P0/P1/P2）
4. 更新 `下一步有趣的想法.md`，标注 ✅ 已实现 / 🔲 待落地

### 检查点
- [ ] 功能是否可拆分为独立模块？
- [ ] 是否与现有模块冲突？
- [ ] 实现量是否可控（单文件 < 600 行）？

---

## Phase 2: 代码实现

### 输入
- 功能清单

### 输出
- `.py` / `.c` 源文件

### 文件放置规则

| 类型 | 目录 | 命名 |
|------|------|------|
| 核心算法 | `src/` | `snake_case.py` |
| C 扩展 | `src/fast/` | `_name.c` |
| Python 包装器 | `src/fast/` | `__init__.py` |
| 数据层 | `src/data/` | `xxx.py` |
| 多时间维度 | `src/multitimeframe/` | `xxx.py` |
| Streamlit 页面 | `src/workbench/` | `xxx_page.py` |
| 数据处理脚本 | `scripts/` | `action_target.py` |
| 交易策略 | `trading/` | `platform_strategy.py` |
| 文档 | `docs/` | `中文名.md` |
| 活文档 | 项目根目录 | `下一步有趣的想法.md` |

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
# Python
for f in $(find . -name "*.py" -not -path "./__pycache__/*"); do
    python3 -c "import ast; ast.parse(open('$f').read())" && echo "✓ $f" || echo "✗ $f"
done

# C
gcc -fsyntax-only -I$(python3 -c "import numpy; print(numpy.get_include())") file.c
```

**Layer 2: 逻辑验证**
```bash
python3 -c "
# 构造 mock 数据，验证核心逻辑
# - 正常路径：预期输入 → 预期输出
# - 边界条件：空列表、极端值、单元素
# - 评分逻辑：高质量→A层，低质量→D层
"
```

**Layer 3: 集成验证**
```bash
# 用真实数据端到端测试（如有网络）
python3 -c "
from src.data.sina_fetcher import fetch_bars
from src.compiler.pipeline import compile_full, CompilerConfig
bars = fetch_bars('cu0', freq='1d', timeout=15)
result = compile_full(bars, CompilerConfig())
print(f'{len(result.structures)} structures')
"
```

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

### 操作

**5.1 未使用导入清理**
```bash
# 检查每个 import 是否在文件中被使用
for f in $(find . -name "*.py"); do
    grep -n "^import \|^from " "$f" | while IFS= read -r line; do
        mod=$(echo "$line" | awk '{print $NF}' | sed 's/;//')
        count=$(grep -c "$mod" "$f" 2>/dev/null || echo 0)
        if [ "$count" -le 1 ]; then
            echo "⚠ $f: '$mod' 可能未使用"
        fi
    done
done
```

**5.2 重复逻辑检查**
```bash
# 检查函数名重复
grep -rn "def function_name" . --include="*.py" | grep -v __pycache__
```

**5.3 文件大小检查**
```bash
find . -name "*.py" | while read f; do
    lines=$(wc -l < "$f")
    [ "$lines" -gt 500 ] && echo "⚠ $f: ${lines}行"
done
```

### 注意事项
- PythonGO 策略文件的重复是有意的（自包含，不依赖内部模块）
- `__init__.py` 中的重复导入可以合并

### 检查点
- [ ] 无未使用的 import
- [ ] 无未使用的函数/变量
- [ ] 重复逻辑已合并或标注原因

---

## Phase 6: 推送

### 输入
- 清理后的代码

### 操作

**6.1 使用 GitHub API 推送（git clone 不通时）**
```python
import base64, requests

TOKEN = "ghp_xxx"
REPO = "owner/repo"
H = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"}

def push_file(local_path, github_path, message):
    with open(local_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    url = f"https://api.github.com/repos/{REPO}/contents/{github_path}"
    r = requests.get(url, headers=H, params={"ref": "main"})
    sha = r.json().get("sha") if r.status_code == 200 else None

    payload = {"message": message, "content": b64, "branch": "main"}
    if sha:
        payload["sha"] = sha
        payload["message"] = message.replace("add", "update")

    r = requests.put(url, headers=H, json=payload)
    return r.status_code in (200, 201)
```

**6.2 批量推送**
```python
FILES = {
    "local/path.py": "github/path.py",
    # ...
}
for local, github in FILES.items():
    push_file(local, github, f"v3.0: add {os.path.basename(local)}")
```

**6.3 移动文件（先删后建）**
```python
# 删除旧位置
sha = get_sha(old_path)
requests.delete(f".../contents/{old_path}", json={"message": "move to new/", "sha": sha, "branch": "main"})

# 创建新位置
push_file(local, new_path, "move from old/")
```

### 检查点
- [ ] 文件路径正确
- [ ] 提交信息清晰（`v3.0: add XXX` / `v3.0: update XXX`）
- [ ] 推送后验证文件存在

---

## Phase 7: 归档

### 输入
- 推送完成

### 操作

**7.1 更新记忆文件**
```bash
cat >> memory/YYYY-MM-DD.md << 'EOF'
### 第N轮：简要描述
新增文件：...
修改文件：...
EOF
```

**7.2 更新想法文档**
- 标记已完成的条目为 ✅
- 新增发现的改进方向
- 调整优先级

**7.3 更新变更记录**
- `docs/CHANGELOG_v3.0.md` 记录所有变更
- 包含：决策日志、文件清单、测试清单

### 检查点
- [ ] 记忆文件已更新
- [ ] 想法文档状态已同步
- [ ] 变更记录已更新

---

## 快速参考

### 一键语法检查
```bash
find . -name "*.py" -not -path "./__pycache__/*" -exec python3 -c "import ast; ast.parse(open('{}').read()); print('✓ {}')" \;
```

### 一键推送
```bash
python3 push_to_github.py <token>
```

### 一键测试
```bash
python3 -c "
import ast, os
for f in [f for f in os.listdir('.') if f.endswith('.py')]:
    ast.parse(open(f).read()); print(f'✓ {f}')
"
```

### GitHub API 常用操作
```bash
# 查看目录
curl -s "https://api.github.com/repos/OWNER/REPO/contents/PATH" -H "Authorization: token TOKEN"

# 查看文件
curl -s "https://api.github.com/repos/OWNER/REPO/contents/PATH?ref=main" -H "Authorization: token TOKEN"

# 验证推送
curl -s "https://api.github.com/repos/OWNER/REPO/contents/PATH" | python3 -c "import json,sys; print(json.load(sys.stdin).get('name','?'))"
```

---

## 本次迭代清单 (2026-04-24)

| 轮次 | 内容 | 文件数 | 状态 |
|------|------|--------|------|
| 1 | 数据层+C扩展+多时间维度 | 11 | ✅ |
| 2 | Streamlit集成+想法+变更记录 | 3 | ✅ |
| 3 | 质量分层+P0三模块+统一集成 | 6 | ✅ |
| 4 | 测试+复核+推送 | 19 | ✅ |
| 5 | 作业流程+PythonGO信号工具 | 2 | ✅ |
| 6 | 假突破反转信号+跨品种共振 | 1 | ✅ |
| 7 | 全流程测试+复核+去重+推送 | 4 | ✅ |
| 8 | v3.1 C扩展优化+扫描修复 | 12 | ✅ |
| 9 | 品种描述交易导向+时效标签+安全修复 | 9 | ✅ |

**总计：43 个文件推送到 GitHub，~7,800 行代码**

---

*手册版本: v1.2 · 2026-04-24*
