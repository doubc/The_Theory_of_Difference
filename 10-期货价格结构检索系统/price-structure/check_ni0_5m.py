from src.data.loader import MySQLLoader

loader = MySQLLoader(host='localhost', user='root', password='', db='sina_futures')

# Get 5-minute data for ni0 today
bars = loader.get('ni0', start='2026-04-25', end='2026-04-25', freq='5m')
print(f'Got {len(bars)} 5m bars for ni0 today')

if bars:
    print(f'First: {bars[0].timestamp} O:{bars[0].open} H:{bars[0].high} L:{bars[0].low} C:{bars[0].close}')
    print(f'Last:  {bars[-1].timestamp} O:{bars[-1].open} H:{bars[-1].high} L:{bars[-1].low} C:{bars[-1].close}')
    
    # Show recent 10 bars
    print('\nRecent 10 bars:')
    for b in bars[-10:]:
        ts = b.timestamp.strftime('%H:%M')
        print(f'{ts} O:{b.open:.0f} H:{b.high:.0f} L:{b.low:.0f} C:{b.close:.0f} V:{b.volume}')