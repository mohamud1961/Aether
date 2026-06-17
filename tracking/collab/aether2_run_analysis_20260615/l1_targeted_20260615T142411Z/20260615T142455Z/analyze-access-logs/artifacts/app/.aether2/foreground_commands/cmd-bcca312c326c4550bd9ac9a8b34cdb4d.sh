python3 - <<'PY'
from pathlib import Path
for i, line in enumerate(Path('/app/report.txt').read_text().splitlines(), 1):
    print(f'{i}: {line}')
PY