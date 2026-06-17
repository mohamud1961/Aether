python3 - <<'PY'
from pathlib import Path
for p in [Path('/app/deps/clue.txt'), Path('/app/deps/frankie_preferences.txt'), Path('/app/deps/random_fact.txt')]:
    print(f'--- {p.name} ---')
    print(p.read_text())
PY