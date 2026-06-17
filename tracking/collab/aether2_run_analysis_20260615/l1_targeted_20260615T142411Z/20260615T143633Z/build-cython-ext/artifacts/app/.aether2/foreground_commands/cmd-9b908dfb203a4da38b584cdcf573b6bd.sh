python3 - <<'PY'
import importlib
for m in ['pyknotid.spacecurves.chelpers','pyknotid.spacecurves.ccomplexity','pyknotid.cinvariants']:
    mod = importlib.import_module(m)
    print(m, '->', mod.__file__)
PY