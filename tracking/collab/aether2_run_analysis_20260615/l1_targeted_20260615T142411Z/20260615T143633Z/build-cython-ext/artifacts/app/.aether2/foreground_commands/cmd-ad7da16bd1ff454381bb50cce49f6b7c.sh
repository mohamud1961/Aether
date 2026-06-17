python3 - <<'PY'
from pathlib import Path
p = Path('/app/pyknotid/pyknotid/make/torus.py')
text = p.read_text()
text = text.replace('from fractions import gcd\n', 'from math import gcd\n')
p.write_text(text)
print('patched', p)
PY