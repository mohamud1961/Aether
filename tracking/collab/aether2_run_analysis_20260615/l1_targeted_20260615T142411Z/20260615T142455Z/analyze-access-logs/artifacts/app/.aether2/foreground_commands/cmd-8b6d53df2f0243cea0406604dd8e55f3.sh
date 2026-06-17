python3 - <<'PY'
from collections import Counter
from pathlib import Path
import re
lines = Path('/app/access_log').read_text(errors='replace').splitlines()
ips = []
urls = []
errors404 = 0
pat = re.compile(r'"\S+\s+(\S+)\s+HTTP/[^\"]+"\s+(\d{3})\s+')
for line in lines:
    parts = line.split()
    if parts:
        ips.append(parts[0])
    m = pat.search(line)
    if m:
        urls.append(m.group(1))
        if m.group(2) == '404':
            errors404 += 1
c = Counter(urls)
report = []
report.append(f'Total requests: {len(lines)}')
report.append(f'Unique IP addresses: {len(set(ips))}')
report.append('Top 3 URLs:')
for url, count in c.most_common(3):
    report.append(f'  {url}: {count}')
report.append(f'404 errors: {errors404}')
Path('/app/report.txt').write_text('\n'.join(report) + '\n')
print('\n'.join(report))
PY