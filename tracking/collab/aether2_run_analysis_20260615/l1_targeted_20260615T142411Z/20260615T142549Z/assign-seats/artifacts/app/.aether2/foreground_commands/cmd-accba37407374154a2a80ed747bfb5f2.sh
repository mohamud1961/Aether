cat /app/results.txt && printf '\n---\n' && python3 - <<'PY'
from pathlib import Path
p=Path('/app/results.txt')
lines=p.read_text().splitlines()
print('line_count', len(lines))
print('formatted', all(', ' in line and line==', '.join(sorted(line.split(', '))) for line in lines))
PY