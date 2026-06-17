python3 /app/jump_analyzer.py /app/example_video.mp4 && cat /app/output.toml && python3 - <<'PY'
import tomllib
with open('/app/output.toml','rb') as f:
    data=tomllib.load(f)
print(data)
PY