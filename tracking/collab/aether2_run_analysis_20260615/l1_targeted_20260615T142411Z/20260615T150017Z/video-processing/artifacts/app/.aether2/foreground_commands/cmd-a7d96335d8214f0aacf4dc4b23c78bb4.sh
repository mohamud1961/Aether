python3 /app/jump_analyzer.py /app/example_video.mp4 && python3 - <<'PY'
import toml
with open('/app/output.toml','r') as f:
    data=toml.load(f)
print(data)
print(type(data['jump_takeoff_frame_number']), type(data['jump_land_frame_number']))
PY