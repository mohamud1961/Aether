python3 - <<'PY'
import tomllib
with open('/app/output.toml','rb') as f:
    data=tomllib.load(f)
print(data)
PY