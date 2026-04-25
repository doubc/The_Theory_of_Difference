# MySQL 期货数据同步指南

> 将新浪期货行情数据同步到本地 MySQL 数据库，以及数据查询和分析。

---

## 一、环境准备

### 1. 安装依赖

```bash
pip install pymysql pandas sqlalchemy
```

### 2. 安装 MySQL

从官方下载页面获取对应平台的安装包：https://dev.mysql.com/downloads/mysql/

安装后验证：
```bash
mysql -u root -p
# 输入密码后进入 MySQL 命令行即表示成功
```

### 3. 配置密码

在项目根目录创建 `.env` 文件（参考 `.env.example`）：

```
MYSQL_PASSWORD=your_actual_password
```

> **重要**：所有脚本通过环境变量 `MYSQL_PASSWORD` 读取密码，不要在代码中硬编码。

设置环境变量：
```bash
# Linux / macOS
export MYSQL_PASSWORD=your_actual_password

# 或在 .env 文件中配置后，脚本会自动读取
```

---

## 二、配置数据库

### 自动配置

运行同步脚本时会自动：
1. 创建数据库 `sina_futures`
2. 创建数据表（每个合约一张表）
3. 建立索引优化查询

### 手动配置（可选）

```sql
CREATE DATABASE IF NOT EXISTS sina_futures 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE sina_futures;
SHOW TABLES;
```

---

## 三、同步数据

### 使用主脚本

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
```

### 使用快速同步脚本

```bash
# 同步单个合约
python scripts/quick_sync.py cu0

# 同步多个合约
python scripts/quick_sync.py cu0 rb0 al0

# 同步所有合约
python scripts/quick_sync.py --all

# 查看已同步的表
python scripts/quick_sync.py --list
```

### 预置合约列表

**国内期货主力合约**：
- 上期所: cu0(铜), al0(铝), zn0(锌), pb0(铅), ni0(镍), sn0(锡), au0(金), ag0(银), rb0(螺纹), hc0(热卷)
- 大商所: i0(铁矿), j0(焦炭), jm0(焦煤), m0(豆粕), y0(豆油), p0(棕榈), c0(玉米)
- 郑商所: ma0(甲醇), sr0(白糖), cf0(棉花), ta0(PTA), rm0(菜粕)
- 广期所: lc0(碳酸锂), si0(工业硅)

**外盘期货**：cad(铜), nid(镍), cl(原油), gc(黄金), si(白银)

**外汇**：usdcny, eurusd, gbpusd, usdjpy

---

## 四、数据查询

### 在 Python 中查询

```python
from src.data.loader import MySQLLoader
import os

loader = MySQLLoader(
    host='localhost',
    user='root',
    password=os.getenv('MYSQL_PASSWORD'),
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
```

### 直接 SQL 查询

```sql
-- 查看铜日线最新 10 条
SELECT * FROM cu0 ORDER BY date DESC LIMIT 10;

-- 查看铜5分钟线最新 10 条
SELECT * FROM cu0_m5 ORDER BY datetime DESC LIMIT 10;

-- 统计各表数据量
SELECT table_name, table_rows
FROM information_schema.tables 
WHERE table_schema = 'sina_futures';

-- 查看数据时间范围
SELECT MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as total_rows
FROM cu0;
```

---

## 五、数据结构

### 日线表（`{symbol}`）

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

### 5分钟线表（`{symbol}_m5`）

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

## 六、常见问题

### Q1: 连接 MySQL 失败？

检查以下几点：
1. MySQL 服务是否启动
2. 环境变量 `MYSQL_PASSWORD` 是否正确设置
3. 端口是否被占用（默认 3306）

```bash
# 测试连接
mysql -u root -p -h localhost
```

### Q2: 同步时提示表不存在？

脚本会自动创建表，但如果权限不足会失败。确保 root 用户有创建数据库和表的权限。

### Q3: 如何修改数据库配置？

编辑脚本中的 `DB_CONFIG`，密码通过环境变量读取：

```python
import os
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': os.getenv('MYSQL_PASSWORD'),
}
```

### Q4: 数据量大时如何优化？

- 使用 `--contracts` 只同步需要的合约
- 日线数据每天只同步一次即可
- 5分钟线数据量大，建议只同步活跃合约

---

*相关文件：`src/data/loader.py` · `scripts/sina_to_mysql.py` · `scripts/quick_sync.py` · `.env.example`*
