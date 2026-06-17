python3 - <<'PY'
import ensurepip, os, glob
bundled = os.path.join(os.path.dirname(ensurepip.__file__), '_bundled')
print('bundled', bundled)
print(os.listdir(bundled))
PY