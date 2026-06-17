python3 - <<'PY'
import importlib
mods=['pyknotid.spacecurves.chelpers','pyknotid.spacecurves.ccomplexity','pyknotid.cinvariants']
for m in mods:
    mod=importlib.import_module(m)
    print(m, 'OK', mod.__file__)
PY