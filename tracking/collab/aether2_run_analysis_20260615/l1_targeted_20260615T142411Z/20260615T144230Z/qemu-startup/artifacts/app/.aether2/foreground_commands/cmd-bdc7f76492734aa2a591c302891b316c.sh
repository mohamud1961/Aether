sh -lc 'python3 - <<"PY"
import os, signal
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline","rb").read().replace(b"\0",b" ")
    except Exception:
        continue
    if b"qemu-system-x86_64" in cmd and b"alpine-disk.qcow2" in cmd:
        print(pid, cmd.decode("utf-8","ignore"))
        os.kill(int(pid), signal.SIGKILL)
PY
sleep 1
python3 - <<"PY"
import os
found=False
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline","rb").read().replace(b"\0",b" ")
    except Exception:
        continue
    if b"qemu-system-x86_64" in cmd and b"alpine-disk.qcow2" in cmd:
        found=True
        print("still_alive", pid, cmd.decode("utf-8","ignore"))
print("done", found)
PY'