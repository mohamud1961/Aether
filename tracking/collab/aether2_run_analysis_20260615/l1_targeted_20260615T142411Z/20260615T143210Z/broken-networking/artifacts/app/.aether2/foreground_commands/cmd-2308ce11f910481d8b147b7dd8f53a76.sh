sh -lc 'python3 - <<"PY"
import socket
for host in ["example.com","pypi.org"]:
    try:
        print(host, socket.getaddrinfo(host, 80)[0][4][0])
    except Exception as e:
        print(host, "ERR", repr(e))
PY'