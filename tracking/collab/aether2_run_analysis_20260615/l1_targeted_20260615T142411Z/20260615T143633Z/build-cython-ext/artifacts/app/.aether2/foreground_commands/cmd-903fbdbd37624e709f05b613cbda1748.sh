python3 - <<'PY'
from pathlib import Path
p = Path('pyknotid/pyknotid/spacecurves/ccomplexity.pyx')
text = p.read_text()
text = text.replace('dtype=np.int', 'dtype=np.int_')
p.write_text(text)
print('patched', p)
PY