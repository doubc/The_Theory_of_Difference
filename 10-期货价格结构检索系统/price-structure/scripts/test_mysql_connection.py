"""
MySQL 连接测试脚本

用于验证：
1. MySQL 是否安装并运行
2. 数据库连接是否正常
3. 数据表是否能正常创建
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pymysql
from pymysql.cursors import DictCursor


def test_connection(host='localhost', user='root', password=None, port=3306):
    """测试 MySQL 连接"""
    import os
    if password is None:
        password = os.getenv('MYSQL_PASSWORD', 'root')
    
    print("=" * 60)
    print("MySQL 连接测试")
    print("=" * 60)
    
    config = {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'charset': 'utf8mb4',
    }
    
    print(f"\n连接配置:")
    print(f"  主机: {host}")
    print(f"  端口: {port}")
    print(f"  用户: {user}")
    print(f"  密码: {'*' * len(password)}")
    
    try:
        # 尝试连接
        print(f"\n正在连接 MySQL...")
        conn = pymysql.connect(**config, cursorclass=DictCursor)
        print("✓ 连接成功!")
        
        # 获取服务器信息
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION() as version")
            result = cursor.fetchone()
            print(f"✓ MySQL 版本: {result['version']}")
            
            # 查看所有数据库
            cursor.execute("SHOW DATABASES")
            databases = [row['Database'] for row in cursor.fetchall()]
            print(f"\n现有数据库 ({len(databases)} 个):")
            for db in databases:
                prefix = "  → " if db == 'sina' else "    "
                print(f"{prefix}{db}")
                
            # 检查 sina 数据库
            if 'sina' in databases:
                print(f"\n✓ sina 数据库已存在")
                cursor.execute("USE sina")
                cursor.execute("SHOW TABLES")
                tables = [row[f"Tables_in_sina"] for row in cursor.fetchall()]
                print(f"✓ 数据表数量: {len(tables)}")
                if tables:
                    print(f"  表列表:")
                    for table in sorted(tables)[:10]:  # 只显示前10个
                        print(f"    - {table}")
                    if len(tables) > 10:
                        print(f"    ... 还有 {len(tables)-10} 个表")
            else:
                print(f"\n✗ sina 数据库不存在")
                print("  运行同步脚本会自动创建")
                
        conn.close()
        print("\n" + "=" * 60)
        print("✓ 测试完成，连接正常!")
        print("=" * 60)
        return True
        
    except pymysql.err.OperationalError as e:
        print(f"\n✗ 连接失败!")
        print(f"  错误: {e}")
        
        if "Access denied" in str(e):
            print(f"\n可能原因: 密码错误")
            print(f"解决方法: 修改脚本中的 password 参数")
        elif "Can't connect" in str(e):
            print(f"\n可能原因: MySQL 服务未启动")
            print(f"解决方法: 启动 MySQL 服务")
            print(f"  1. 按 Win+R，输入 services.msc")
            print(f"  2. 找到 MySQL80，右键启动")
        
        print("\n" + "=" * 60)
        return False
        
    except Exception as e:
        print(f"\n✗ 未知错误: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='测试 MySQL 连接')
    parser.add_argument('--host', default='localhost', help='MySQL 主机')
    parser.add_argument('--user', '-u', default='root', help='用户名')
    parser.add_argument('--password', '-p', default='root', help='密码')
    parser.add_argument('--port', type=int, default=3306, help='端口')
    
    args = parser.parse_args()
    
    success = test_connection(
        host=args.host,
        user=args.user,
        password=args.password,
        port=args.port
    )
    
    if not success:
        print("\n请检查 MySQL 安装和配置后重试")
        sys.exit(1)


if __name__ == "__main__":
    main()
