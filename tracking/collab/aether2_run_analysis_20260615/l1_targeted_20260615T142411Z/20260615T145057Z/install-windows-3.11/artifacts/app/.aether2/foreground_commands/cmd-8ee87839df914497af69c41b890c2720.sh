python3 - <<'PY'
from pathlib import Path
import subprocess, time, socket, os
# start a headless X server for vncviewer capture
xvfb = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1024x768x24'])
os.environ['DISPLAY'] = ':99'
time.sleep(1)
# connect viewer
viewer = subprocess.Popen(['xtigervncviewer','-viewonly','-Shared','127.0.0.1:1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)
viewer.terminate()
out, err = viewer.communicate(timeout=5)
print('viewer_rc', viewer.returncode)
print(err.decode('utf-8','ignore')[:1000])
# qmp keyboard control
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.connect('run/qmp.sock')
print(s.recv(4096).decode('utf-8','ignore'))
s.sendall(b'{"execute":"qmp_capabilities"}\n')
print(s.recv(4096).decode('utf-8','ignore'))
s.sendall(b'{"execute":"send-key","arguments":{"keys":[{"type":"qcode","data":"ret"}]}}\n')
print(s.recv(4096).decode('utf-8','ignore'))
s.close()
# cleanup xvfb
xvfb.terminate()
PY