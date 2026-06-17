python3 - <<'PY'
import socket, ssl
host='example.com'
port=443
ip=socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0][4][0]
print('resolved', host, ip)
ctx=ssl.create_default_context()
with socket.create_connection((ip, port), timeout=10) as s:
    with ctx.wrap_socket(s, server_hostname=host) as ss:
        ss.sendall(b'HEAD / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n')
        data=ss.recv(200)
        print(data.decode('latin1', 'replace').splitlines()[0])
PY