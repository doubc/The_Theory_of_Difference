# MySQL 行情数据同步功能说明

## 功能概述

基于现有的 `sina_fetcher.py`，新增了一套完整的 MySQL 数据同步和查询功能，包括：

1. **数据抓取**：从新浪 API 获取期货行情（日线/5分钟线）
2. **数据存储**：自动创建数据库和表，批量写入 MySQL
3. **数据查询**：通过 `MySQLLoader` 读取数据进行分析
4. **增量更新**：支持重复运行，自动合并新旧数据

## 新增文件

### 核心脚本

| 文件 | 说明 |
|------|------|
| `scripts/sina_to_mysql.py` | 主同步脚本，支持命令行参数 |
| `scripts/quick_sync.py` | 快速同步脚本，使用更简单 |
| `scripts/test_mysql_connection.py` | MySQL 连接测试 |
| `scripts/demo_sync_and_query.py` | 完整演示脚本 |
| `scripts/mysql_query_example.py` | 查询示例代码 |

### 文档

| 文件 | 说明 |
|------|------|
| `docs/MySQL数据同步指南.md` | 详细使用文档 |
| `MySQL同步功能说明.md` | 本文档 |

## 快速开始

### 1. 安装依赖

```bash
pip install pymysql pandas sqlalchemy requests
```

### 2. 配置 MySQL 密码

编辑以下文件，将 `password='root'` 改为你的实际密码：
- `scripts/sina_to_mysql.py`
- `scripts/quick_sync.py`
- `scripts/demo_sync_and_query.py`
- `scripts/mysql_query_example.py`
- `scripts/test_mysql_integration.py`（已有）

### 3. 测试连接

```bash
python scripts/test_mysql_connection.py --password your_password
```

### 4. 同步数据

```bash
# 同步单个合约
python scripts/quick_sync.py cu0

# 同步多个合约
python scripts/quick_sync.py cu0 rb0 al0

# 同步所有合约
python scripts/quick_sync.py --all
```

### 5. 查询数据

```python
from src.data.loader import MySQLLoader

loader = MySQLLoader(
    host='localhost',
    user='root',
    password='your_password',
    db='sina_futures'
)

# 获取数据
bars = loader.get(symbol='cu0', freq='1d')
```

## 数据库结构

### 数据库
- **名称**: `sina_futures`
- **字符集**: `utf8mb4`

### 数据表

**日线表**: `{symbol}`
```sql
CREATE TABLE cu0 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL,
    open DECIMAL(18, 6) NOT NULL,
    high DECIMAL(18, 6) NOT NULL,
    low DECIMAL(18, 6) NOT NULL,
    close DECIMAL(18, 6) NOT NULL,
    vol BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_date (date)
);
```

**5分钟线表**: `{symbol}_m5`
```sql
CREATE TABLE cu0_m5 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    datetime DATETIME NOT NULL,
    open DECIMAL(18, 6) NOT NULL,
    high DECIMAL(18, 6) NOT NULL,
    low DECIMAL(18, 6) NOT NULL,
    close DECIMAL(18, 6) NOT NULL,
    vol BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_datetime (datetime)
);
```

## 支持的合约

### 国内期货主力合约
- **上期所**: cu0, al0, zn0, pb0, ni0, sn0, au0, ag0, rb0, hc0, ss0, bu0, ru0, fu0, sp0
- **大商所**: i0, j0, jm0, m0, y0, p0, a0, b0, c0, cs0, l0, v0, pp0, eg0, eb0, pg0
- **郑商所**: ma0, sr0, cf0, oi0, ta0, rm0, fg0, zc0, sf0, sm0, ur0, sa0
- **广期所**: lc0, si0

### 外盘期货
- cad, nid, snd, pbd, zsd, ahd, cl, s, sm, bo, trb, ng, si, gc, oil, ct, hg

### 外汇
- usdcny, eurusd, gbpusd, usdjpy, audusd, usdcad, usdchf

## 命令行用法

### sina_to_mysql.py

```bash
# 同步指定合约
python scripts/sina_to_mysql.py --contracts cu0
python scripts/sina_to_mysql.py --contracts cu0,rb0,al0

# 同步5分钟线
python scripts/sina_to_mysql.py --contracts cu0 --freq 5m

# 同步所有合约
python scripts/sina_to_mysql.py --all

# 强制全量更新
python scripts/sina_to_mysql.py --contracts cu0 --force

# 查看已同步的表
python scripts/sina_to_mysql.py --list

# 指定密码
python scripts/sina_to_mysql.py --contracts cu0 --password your_password
```

### quick_sync.py

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

## 与现有代码集成

### 在结构编译中使用

```python
from src.data.loader import MySQLLoader
from src.compiler.pipeline import compile_full, CompilerConfig

# 加载数据
loader = MySQLLoader(host='localhost', user='root', password='your_password', db='sina_futures')
bars = loader.get(symbol='cu0', freq='1d')

# 编译结构
config = CompilerConfig(min_amplitude=0.02, min_duration=3)
result = compile_full(bars, config)
```

### 在检索引擎中使用

```python
from src.data.loader import MySQLLoader
from src.retrieval.engine import RetrievalEngine

loader = MySQLLoader(host='localhost', user='root', password='your_password', db='sina_futures')
engine = RetrievalEngine()

# 加载样本库数据
for symbol in ['cu0', 'rb0', 'al0']:
    bars = loader.get(symbol=symbol, freq='1d')
    engine.index_structure(bars, metadata={'symbol': symbol})
```

## 注意事项

1. **密码安全**: 脚本中硬编码了默认密码 `root`，请在生产环境中修改
2. **数据量**: 5分钟线数据量较大，建议只同步活跃合约
3. **网络限制**: 新浪 API 可能有访问频率限制，大量同步时请适当间隔
4. **数据修正**: 支持重复运行，新数据会覆盖旧数据（基于日期唯一索引）

## 故障排除

### 连接失败
```bash
# 测试连接
python scripts/test_mysql_connection.py --password your_password
```

### 表不存在
- 脚本会自动创建表，确保 MySQL 用户有 CREATE 权限

### 数据重复
- 表结构包含唯一索引，重复数据会自动更新

## 后续计划

- [ ] 支持更多数据源（东方财富、同花顺等）
- [ ] 添加数据校验和质量报告
- [ ] 支持自动定时同步（cron/任务计划程序）
- [ ] 添加数据导出功能（CSV/Excel）
