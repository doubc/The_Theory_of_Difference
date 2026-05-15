import pymysql
conn = pymysql.connect(host='localhost', user='root', password='')
cur = conn.cursor()
cur.execute('SHOW DATABASES LIKE "sina_futures"')
exists = cur.fetchone()
print('sina_futures exists:', exists is not None)
cur.execute('USE sina_futures')
cur.execute('SHOW TABLES')
tables = [r[0] for r in cur.fetchall()]
print('Tables:', len(tables))
cur.execute('SELECT COUNT(*) FROM cu0')
print('cu0 rows:', cur.fetchone()[0])
cur.execute('SELECT date, close FROM cu0 ORDER BY date DESC LIMIT 2')
for r in cur.fetchall():
    print(' ', r)
conn.close()
print('OK')