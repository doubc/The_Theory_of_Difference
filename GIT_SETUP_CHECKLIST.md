# Git 配置检查清单

## ✅ 已完成的配置

### 1. 仓库初始化
- [x] 在 `D:\PythonWork\The_Theory_of_Difference` 目录初始化了独立的 Git 仓库
- [x] 添加了远程仓库地址：`https://github.com/doubc/The_Theory_of_Difference.git`

### 2. 用户信息配置
- [x] 用户名：`doubc`
- [x] 邮箱：`doubc@163.com`

### 3. 分支配置
- [x] 本地分支：`main`
- [x] 远程跟踪：`origin/main`
- [x] 已与远程同步

### 4. .gitignore 文件
- [x] 已创建并添加，避免推送不必要的文件

---

## 📋 常用 Git 命令

### 查看状态
```powershell
git status
```

### 拉取最新代码
```powershell
git pull
```

### 提交更改
```powershell
git add .
git commit -m "你的提交信息"
git push
```

### 查看提交历史
```powershell
git log --oneline -10
```

### 查看远程仓库
```powershell
git remote -v
```

---

## ⚠️ 注意事项

### 1. 工作目录
确保在正确的目录下执行 Git 命令：
```powershell
cd D:\PythonWork\The_Theory_of_Difference
```

### 2. 避免推送的文件
以下文件已被 `.gitignore` 忽略，不会被推送：
- Python 缓存文件（`__pycache__/`, `*.pyc`）
- IDE 配置（`.idea/`, `.vscode/`）
- 虚拟环境（`venv/`, `env/`）
- 日志文件（`*.log`, `logs/`）
- 临时文件

### 3. 大文件处理
如果有大文件（>100MB），建议使用 Git LFS：
```powershell
git lfs install
git lfs track "*.png"
git lfs track "*.jpg"
```

### 4. 冲突解决
如果推送时遇到冲突：
```powershell
# 先拉取远程更改
git pull --rebase

# 解决冲突后
git add .
git rebase --continue
git push
```

---

## 🔧 常见问题

### Q1: 提示 "not a git repository"
**解决方案：** 确保在 `D:\PythonWork\The_Theory_of_Difference` 目录下

### Q2: 推送失败 "rejected"
**解决方案：** 先拉取远程更改
```powershell
git pull origin main
git push origin main
```

### Q3: 需要输入 GitHub 账号密码
**解决方案：** 使用 Personal Access Token (PAT)
1. 访问 https://github.com/settings/tokens
2. 生成新的 token
3. 使用 token 作为密码

或者配置 SSH 密钥（推荐）：
```powershell
ssh-keygen -t ed25519 -C "doubc@163.com"
# 将公钥添加到 GitHub
git remote set-url origin git@github.com:doubc/The_Theory_of_Difference.git
```

### Q4: 误提交了敏感信息
**解决方案：** 立即更改密码，并使用 BFG Repo-Cleaner 清理历史

---

## 📊 当前状态检查

运行以下命令验证配置：

```powershell
# 检查当前分支
git branch

# 检查远程仓库
git remote -v

# 检查用户配置
git config user.name
git config user.email

# 检查工作树状态
git status
```

预期输出：
- 当前分支：`main`
- 远程：`origin  https://github.com/doubc/The_Theory_of_Difference.git`
- 用户名：`doubc`
- 邮箱：`doubc@163.com`
- 工作树：干净或只有预期的更改

---

## 🚀 下一步

1. **测试拉取**：`git pull`
2. **测试推送**：修改一个文件，提交并推送
3. **配置 SSH**（可选但推荐）：避免每次都输入密码

如有问题，请检查：
- 网络连接
- GitHub 账号权限
- 仓库地址是否正确
