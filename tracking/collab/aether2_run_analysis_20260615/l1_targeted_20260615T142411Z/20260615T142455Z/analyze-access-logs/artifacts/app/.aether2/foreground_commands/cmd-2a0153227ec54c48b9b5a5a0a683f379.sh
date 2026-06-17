sh -lc 'python3 - <<"PY"
from collections import Counter
from pathlib import Path
import re
lines=Path("/app/access_log").read_text(errors="replace").splitlines()
ips=[]
urls=[]
errors404=0
for line in lines:
    parts=line.split()
    if parts:
        ips.append(parts[0])
    m=re.search(r'"\S+\s+(\S+)\s+HTTP/[^\"]+"\s+(\d{3})\s+', line)
    if m:
        urls.append(m.group(1))
        if m.group(2)=="404":
            errors404 += 1
    else:
        # fallback for malformed lines
        pass
c=Counter(urls)
print(len(lines))
print(len(set(ips)))
print(errors404)
for url,count in c.most_common(3):
    print(url, count)
PY'