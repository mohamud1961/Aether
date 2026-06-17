sh -lc 'python3 - <<"PY"
import os
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline","rb").read().replace(b"\0",b" ")
    except Exception:
        continue
    if b"qemu-system-x86_64" in cmd:
        print(pid, cmd.decode("utf-8","ignore"))
PY'