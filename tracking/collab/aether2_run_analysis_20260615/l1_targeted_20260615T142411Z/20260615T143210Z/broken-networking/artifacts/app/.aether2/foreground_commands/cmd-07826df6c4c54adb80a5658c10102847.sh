python3 - <<'PY'
import socket
host='example.com'
ip=socket.getaddrinfo(host, 80, type=socket.SOCK_STREAM)[0][4][0]
print('resolved', host, ip)
with socket.create_connection((ip, 80), timeout=10) as s:
    s.sendall(b'HEAD / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n')
    data=s.recv(200)
    print(data.decode('latin1', 'replace').splitlines()[0])
PY