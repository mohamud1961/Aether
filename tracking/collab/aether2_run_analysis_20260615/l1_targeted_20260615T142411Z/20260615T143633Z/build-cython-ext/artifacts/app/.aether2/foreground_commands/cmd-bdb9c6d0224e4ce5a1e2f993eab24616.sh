python3 - <<'PY'
from pathlib import Path
for p in [Path('pyknotid/spacecurves/ccomplexity.pyx'), Path('pyknotid/spacecurves/chelpers.pyx'), Path('pyknotid/cinvariants.pyx')]:
    print('\n###', p)
    txt = p.read_text()
    for i, line in enumerate(txt.splitlines(), 1):
        if 'np.int' in line or 'np.' in line and 'dtype' in line:
            print(f'{i}: {line}')
PY