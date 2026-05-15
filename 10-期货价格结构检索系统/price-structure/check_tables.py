import pymysql
conn = pymysql.connect(host='localhost', user='root', password='', db='sina_futures')
cursor = conn.cursor()
cursor.execute('SHOW TABLES LIKE "ni0%"')
tables = [t[0] for t in cursor.fetchall()]
print('ni0 tables:', tables)

# Also check what timeframes are available
cursor.execute('SHOW TABLES LIKE "%m5%"')
m5_tables = [t[0] for t in cursor.fetchall()]
print('m5 tables (first 20):', m5_tables[:20])

cursor.execute('SHOW TABLES LIKE "%m1%"')
m1_tables = [t[0] for t in cursor.fetchall()]
print('m1 tables (first 20):', m1_tables[:20])