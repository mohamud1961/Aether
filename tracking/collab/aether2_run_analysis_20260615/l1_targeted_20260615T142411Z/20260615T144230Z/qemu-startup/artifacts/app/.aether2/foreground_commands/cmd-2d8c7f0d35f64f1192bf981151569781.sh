sh -lc 'python3 - <<"PY"
import socket
s=socket.socket()
s.settimeout(2)
try:
    s.connect(("127.0.0.1",6665))
    print("connected")
    print(s.recv(4096).decode("utf-8","ignore"))
finally:
    s.close()
PY'