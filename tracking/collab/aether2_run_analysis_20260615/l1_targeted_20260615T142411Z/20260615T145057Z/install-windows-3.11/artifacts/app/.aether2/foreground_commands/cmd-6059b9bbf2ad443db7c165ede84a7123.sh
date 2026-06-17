python3 - <<'PY'
import socket, time, subprocess, os, signal
# capture VNC screenshot using a lightweight client if available
for cmd in [
    ['xtigervncviewer','-viewonly','-Shared','-geometry','800x600','127.0.0.1:1'],
    ['vncviewer','-viewonly','-Shared','127.0.0.1:1'],
]:
    try:
        p=subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(3)
        p.terminate()
        out, err = p.communicate(timeout=5)
        print('CMD', cmd[0], 'rc', p.returncode)
        print('STDERR', err.decode('utf-8','ignore')[:1000])
        break
    except FileNotFoundError:
        continue
# qmp keyboard control
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.connect('run/qmp.sock')
print(s.recv(4096).decode('utf-8','ignore'))
s.sendall(b'{"execute":"qmp_capabilities"}\n')
print(s.recv(4096).decode('utf-8','ignore'))
s.sendall(b'{"execute":"send-key","arguments":{"keys":[{"type":"qcode","data":"ret"}]}}\n')
print(s.recv(4096).decode('utf-8','ignore'))
s.close()
PY