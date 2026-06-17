sh -lc 'python3 - <<"PY"
from collections import Counter
from pathlib import Path
import re
p=Path("/app/access_log")
lines=p.read_text(errors="replace").splitlines()
print("lines", len(lines))
for i,l in enumerate(lines[:3],1):
    print(i, l)
PY'