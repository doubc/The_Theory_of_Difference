# MySQL 期货数据同步指南

## 概述

本文档说明如何将新浪期货行情数据同步到本地 MySQL 数据库，以及如何进行数据查询和分析。

## 目录

1. [环境准备](#环境准备)
2. [安装 MySQL](#安装-mysql)
3. [配置数据库](#配置数据库)
4. [同步数据](#同步数据)
5. [数据查询](#数据查询)
6. [常见问题](#常见问题)

---

## 环境准备

### 1. 安装依赖

```bash
pip install pymysql pandas sqlalchemy
```

### 2. 确认项目结构

确保你的项目结构如下：

```
price-structure/
├── src/
│   ├── data/
│   │   ├── sina_fetcher.py    # 新浪数据抓取
│   │   └── loader.py           # 数据加载器（含 MySQLLoader）
│   └── ...
├── scripts/
│   ├── sina_to_mysql.py        # 主同步脚本
│   ├── quick_sync.py           # 快速同步脚本
│   └── mysql_query_example.py  # 查询示例
└── docs/
    └── MySQL数据同步指南.md    # 本文档
```

---

## 安装 MySQL

### Windows 安装

1. **下载 MySQL Installer**
   - 官网: https://dev.mysql.com/downloads/installer/
   - 选择 `mysql-installer-community-8.0.40.0.msi`

2. **安装步骤**
   - 运行 Installer，选择 **Server only**
   - 安装路径建议: `D:\MySQL`
   - 设置 root 密码（记住这个密码）
   - 完成安装

3. **验证安装**
   ```cmd
   mysql -u root -p
   # 输入密码后进入 MySQL 命令行即表示成功
   ```

### 配置说明

脚本默认使用以下配置：

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'root',  # ← 请修改为你的实际密码
}
```

**修改密码**：在脚本中搜索 `'root'` 并替换为你的 MySQL root 密码。

---

## 配置数据库

### 自动配置

运行同步脚本时会自动：
1. 创建数据库 `sina_futures`
2. 创建数据表（每个合约一张表）
3. 建立索引优化查询

### 手动配置（可选）

```sql
-- 创建数据库
CREATE DATABASE IF NOT EXISTS sina_futures 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE sina_futures;

-- 查看所有表
SHOW TABLES;
```

---

## 同步数据

### 方式一：使用主脚本（推荐）

```bash
# 同步单个合约（日线）
python scripts/sina_to_mysql.py --contracts cu0

# 同步多个合约
python scripts/sina_to_mysql.py --contracts cu0,rb0,al0

# 同步5分钟线
python scripts/sina_to_mysql.py --contracts cu0 --freq 5m

# 同步所有预置合约（约 40+ 个）
python scripts/sina_to_mysql.py --all

# 强制全量更新（覆盖已有数据）
python scripts/sina_to_mysql.py --contracts cu0 --force

# 查看已同步的表
python scripts/sina_to_mysql.py --list

# 指定 MySQL 密码
python scripts/sina_to_mysql.py --contracts cu0 --password your_password
```

### 方式二：使用快速同步脚本

```bash
# 同步单个合约
python scripts/quick_sync.py cu0

# 同步多个合约
python scripts/quick_sync.py cu0 rb0 al0

# 同步5分钟线
python scripts/quick_sync.py cu0 --freq 5m

# 同步所有合约
python scripts/quick_sync.py --all

# 查看已同步的表
python scripts/quick_sync.py --list
```

### 预置合约列表

**国内期货主力合约**：
- 上期所: cu0(铜), al0(铝), zn0(锌), pb0(铅), ni0(镍), sn0(锡), au0(金), ag0(银), rb0(螺纹), hc0(热卷)...
- 大商所: i0(铁矿), j0(焦炭), jm0(焦煤), m0(豆粕), y0(豆油), p0(棕榈), c0(玉米)...
- 郑商所: ma0(甲醇), sr0(白糖), cf0(棉花), ta0(PTA), rm0(菜粕)...
- 广期所: lc0(碳酸锂), si0(工业硅)

**外盘期货**：
- cad(铜), nid(镍), cl(原油), gc(黄金), si(白银)...

**外汇**：
- usdcny, eurusd, gbpusd, usdjpy...

---

## 数据查询

### 在 Python 中查询

```python
from src.data.loader import MySQLLoader

# 初始化加载器
loader = MySQLLoader(
    host='localhost',
    user='root',
    password='your_password',
    db='sina_futures'
)

# 获取全部数据
bars = loader.get(symbol='cu0', freq='1d')

# 获取指定日期范围
bars = loader.get(
    symbol='cu0',
    start='2024-01-01',
    end='2024-12-31',
    freq='1d'
)

# 遍历数据
for bar in bars:
    print(f"{bar.timestamp.date()}: 开={bar.open}, 收={bar.close}")
```

### 运行查询示例

```bash
python scripts/mysql_query_example.py
```

示例包含：
1. 基础查询（最近 30 天数据）
2. 批量查询（多个合约统计）
3. 涨跌幅计算
4. 移动平均线计算

### 直接 SQL 查询

```sql
-- 查看铜日线最新 10 条
SELECT * FROM cu0 ORDER BY date DESC LIMIT 10;

-- 查看铜5分钟线最新 10 条
SELECT * FROM cu0_m5 ORDER BY datetime DESC LIMIT 10;

-- 统计各表数据量
SELECT 
    table_name,
    table_rows
FROM information_schema.tables 
WHERE table_schema = 'sina_futures';

-- 查看数据时间范围
SELECT 
    MIN(date) as start_date,
    MAX(date) as end_date,
    COUNT(*) as total_rows
FROM cu0;
```

---

## 数据结构

### 日线表结构（{symbol}）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 自增主键 |
| date | DATE | 交易日期 |
| open | DECIMAL(18,6) | 开盘价 |
| high | DECIMAL(18,6) | 最高价 |
| low | DECIMAL(18,6) | 最低价 |
| close | DECIMAL(18,6) | 收盘价 |
| vol | BIGINT | 成交量 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 5分钟线表结构（{symbol}_m5）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 自增主键 |
| datetime | DATETIME | 交易时间 |
| open | DECIMAL(18,6) | 开盘价 |
| high | DECIMAL(18,6) | 最高价 |
| low | DECIMAL(18,6) | 最低价 |
| close | DECIMAL(18,6) | 收盘价 |
| vol | BIGINT | 成交量 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

---

## 常见问题

### Q1: 连接 MySQL 失败？

**A**: 检查以下几点：
1. MySQL 服务是否启动（任务管理器 → 服务 → MySQL80）
2. 密码是否正确
3. 端口是否被占用（默认 3306）

```bash
# 测试连接
mysql -u root -p -h localhost
```

### Q2: 同步时提示表不存在？

**A**: 脚本会自动创建表，但如果权限不足会失败。确保 root 用户有创建数据库和表的权限。

### Q3: 如何修改数据库配置？

**A**: 编辑脚本中的 `DB_CONFIG`：

```python
# scripts/sina_to_mysql.py 或 scripts/quick_sync.py
DB_CONFIG = {
    'host': 'localhost',      # MySQL 主机
    'port': 3306,             # 端口
    'user': 'root',           # 用户名
    'password': 'your_pass',  # 密码
}
```

### Q4: 如何定时自动同步？

**A**: 使用 Windows 任务计划程序：

1. 创建批处理文件 `sync.bat`：
```batch
@echo off
cd /d D:\PythonWork\The_Theory_of_Difference\10-期货价格结构检索系统\price-structure
python scripts\quick_sync.py --all
```

2. 打开任务计划程序 → 创建基本任务
3. 设置触发器（每天 15:30，收盘后）
4. 操作 → 启动程序 → 选择 `sync.bat`

### Q5: 数据量大时如何优化？

**A**: 
- 使用 `--contracts` 只同步需要的合约
- 日线数据每天只同步一次即可
- 5分钟线数据量大，建议只同步活跃合约

---

## 下一步

同步完成后，你可以：

1. **运行结构编译**：使用 `test_mysql_integration.py` 分析价格结构
2. **构建样本库**：将历史结构保存到数据库
3. **实时检索**：基于 MySQL 数据运行检索引擎

```bash
# 测试结构编译
python scripts/test_mysql_integration.py
```

---

## 附录：常用命令速查

```bash
# 同步数据
python scripts/quick_sync.py cu0                    # 单个合约
python scripts/quick_sync.py cu0 rb0 al0            # 多个合约
python scripts/quick_sync.py --all                  # 全部合约
python scripts/quick_sync.py --list                 # 查看已同步

# 查询示例
python scripts/mysql_query_example.py               # 运行查询示例

# MySQL 命令行
mysql -u root -p                                    # 登录
SHOW DATABASES;                                     # 查看数据库
USE sina_futures;                                   # 切换数据库
SHOW TABLES;                                        # 查看表
SELECT * FROM cu0 ORDER BY date DESC LIMIT 5;       # 查看最新5条
```
