python3 - <<'PY'
from pathlib import Path
root = Path('/app/pyknotid/pyknotid')
repls = {'np.float':'float','np.int':'int','np.complex':'complex','np.bool':'bool','np.object':'object'}
for p in root.rglob('*.py'):
    txt = p.read_text()
    new = txt
    for a,b in repls.items():
        new = new.replace(a,b)
    if new != txt:
        p.write_text(new)
        print('patched', p)
PY