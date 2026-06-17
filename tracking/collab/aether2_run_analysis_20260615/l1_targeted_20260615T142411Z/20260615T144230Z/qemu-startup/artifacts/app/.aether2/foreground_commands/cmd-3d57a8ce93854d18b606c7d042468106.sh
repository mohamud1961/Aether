sh -lc 'python3 - <<"PY"
import socket, time
for i in range(30):
    try:
        s=socket.create_connection(("127.0.0.1",6665),timeout=1)
        s.settimeout(2)
        data=s.recv(4096)
        print(data.decode("utf-8","ignore"))
        s.close()
        break
    except Exception as e:
        time.sleep(1)
else:
    raise SystemExit("no connection/prompt")
PY'