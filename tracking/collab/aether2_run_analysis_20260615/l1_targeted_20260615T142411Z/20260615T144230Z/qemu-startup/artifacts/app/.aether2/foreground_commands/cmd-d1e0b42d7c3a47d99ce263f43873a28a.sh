sh -lc 'python3 - <<"PY"
import socket, time
s=socket.create_connection(("127.0.0.1",6665),timeout=5)
s.settimeout(5)
chunks=[]
for _ in range(5):
    try:
        data=s.recv(4096)
        if not data:
            break
        chunks.append(data)
        if b"login:" in b"".join(chunks).lower():
            break
    except Exception:
        break
print(b"".join(chunks).decode("utf-8","ignore"))
s.close()
PY'