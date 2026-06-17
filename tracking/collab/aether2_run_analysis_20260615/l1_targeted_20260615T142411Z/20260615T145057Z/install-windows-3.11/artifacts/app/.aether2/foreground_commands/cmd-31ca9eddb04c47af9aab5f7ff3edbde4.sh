python3 - <<'PY'
import socket, json, time
sock='run/qmp.sock'
for _ in range(50):
    try:
        s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        s.connect(sock)
        break
    except Exception:
        time.sleep(0.1)
else:
    raise SystemExit('no qmp')
print(s.recv(4096).decode())
s.sendall(b'{"execute":"qmp_capabilities"}\n')
print(s.recv(4096).decode())
s.sendall(b'{"execute":"send-key","arguments":{"keys":[{"type":"qcode","data":"ret"}]}}\n')
print(s.recv(4096).decode())
s.close()
PY