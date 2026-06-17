python3 - <<'PY'
import subprocess, time, os, signal
# Use x11vnc's vncsnapshot-like capability via import? fallback to a simple viewer log isn't enough.
# Instead, use ffmpeg if present? Let's inspect available capture tools.
for c in ['vncsnapshot','ffmpeg','import','xwd']:
    r=subprocess.run(['sh','-lc',f'command -v {c}'],capture_output=True,text=True)
    print(c, r.stdout.strip() or 'missing')
PY