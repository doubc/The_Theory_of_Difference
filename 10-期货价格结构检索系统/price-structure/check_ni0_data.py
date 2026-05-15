import pymysql
conn = pymysql.connect(host='localhost', user='root', password='', db='sina_futures')
cursor = conn.cursor()

# Check what columns ni0 table has
cursor.execute('DESCRIBE ni0')
cols = cursor.fetchall()
print('ni0 columns:', [(c[0], c[1]) for c in cols])

# Check recent data
cursor.execute('SELECT * FROM ni0 ORDER BY date DESC LIMIT 10')
rows = cursor.fetchall()
print('\nRecent 10 rows:')
for r in rows:
    print(r)