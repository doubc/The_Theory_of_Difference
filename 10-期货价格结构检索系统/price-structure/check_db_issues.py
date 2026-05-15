import os, glob
proj = r'C:\Users\Administrator\Documents\the_theory_of_difference\10-期货价格结构检索系统\price-structure'
hits = []
for fp in glob.glob(proj + '/scripts/*.py'):
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if ('db=' in line or 'database=' in line) and 'sina' in line and 'sina_futures' not in line:
                name = os.path.basename(fp)
                if name not in [os.path.basename(h) for h in hits]:
                    hits.append(fp)
                print(os.path.basename(fp), 'line', i + ':', line.rstrip()[:100])
    except Exception as e:
        print('Error', fp, e)
print('Total files with db=sina:', len(hits))