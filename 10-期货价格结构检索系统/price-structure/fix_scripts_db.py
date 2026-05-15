import glob, re, os

proj = r'C:\Users\Administrator\Documents\the_theory_of_difference\10-期货价格结构检索系统\price-structure\scripts'
files = [f for f in glob.glob(proj + r'\*.py')]
fixed = []
for fp in files:
    name = os.path.basename(fp)
    if name == 'daily_scan.py':
        continue
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        c = content
        # db='sina' or db="sina" or db=sina -> sina_futures
        c = re.sub(r"(db[=\"'\s]+)sina(?!_futures)", r'\g<1>sina_futures', c)
        # URL /sina? -> /sina_futures?
        c = re.sub(r"/sina\?", "/sina_futures?", c)
        # @localhost/sina -> @localhost/sina_futures
        c = re.sub(r"@localhost/sina\b", "@localhost/sina_futures", c)
        if c != content:
            with open(fp, 'w', encoding='utf-8', errors='ignore') as f:
                f.write(c)
            fixed.append(name)
            print('Fixed:', name)
    except Exception as e:
        print('Error', name, str(e)[:80])
print('Total:', len(fixed))