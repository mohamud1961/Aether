python3 - <<'PY'
import socket
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.connect('run/qmp.sock')
print(s.recv(4096).decode('utf-8','ignore'))
s.sendall(b'{"execute":"qmp_capabilities"}\n')
print(s.recv(4096).decode('utf-8','ignore'))
s.sendall(b'{"execute":"send-key","arguments":{"keys":[{"type":"qcode","data":"ret"}]}}\n')
print(s.recv(4096).decode('utf-8','ignore'))
s.close()
PY