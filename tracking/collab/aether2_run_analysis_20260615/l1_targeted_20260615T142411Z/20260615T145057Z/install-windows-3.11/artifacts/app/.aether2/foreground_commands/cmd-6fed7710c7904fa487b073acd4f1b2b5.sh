python3 - <<'PY'
import socket, time
s=socket.create_connection(('127.0.0.1',5901),timeout=5)
print(s.recv(12).decode('ascii','ignore').strip())
s.close()
PY