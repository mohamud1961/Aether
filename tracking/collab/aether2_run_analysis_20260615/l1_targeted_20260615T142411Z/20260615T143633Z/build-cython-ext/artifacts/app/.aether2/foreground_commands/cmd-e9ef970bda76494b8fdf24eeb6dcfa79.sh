python3 - <<'PY'
from pathlib import Path
root = Path('/app/pyknotid/pyknotid')
for p in root.rglob('*.py'):
    txt = p.read_text()
    new = txt.replace('n.float', 'float').replace('np.float', 'float').replace('n.int', 'int').replace('np.int', 'int')
    if new != txt:
        p.write_text(new)
        print('patched', p)
PY