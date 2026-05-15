import pymysql
conn = pymysql.connect(host='localhost', user='root', password='', db='sina')
cursor = conn.cursor()

# Check recent 5m data
cursor.execute('SELECT * FROM ni0_m5 ORDER BY datetime DESC LIMIT 20')
rows = cursor.fetchall()
print('Recent 20 5m bars for ni0:')
for r in rows:
    print(f'{r[1].strftime("%Y-%m-%d %H:%M")} O:{r[2]:.0f} H:{r[3]:.0f} L:{r[4]:.0f} C:{r[5]:.0f} V:{r[6]}')