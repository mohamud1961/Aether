python3 - <<'PY'
import ensurepip, os
print(ensurepip.__file__)
print(os.listdir(os.path.dirname(ensurepip.__file__)))
PY