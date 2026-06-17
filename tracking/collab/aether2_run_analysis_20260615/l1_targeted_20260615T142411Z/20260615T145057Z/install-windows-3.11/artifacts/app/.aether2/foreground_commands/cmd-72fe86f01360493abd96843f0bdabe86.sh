python3 - <<'PY'
from pathlib import Path
p=Path('launch_win311.sh')
s=p.read_text()
s=s.replace('-qmp unix:run/qmp.sock,server,nowait','-qmp unix:run/qmp.sock,server,nowait -S')
p.write_text(s)
print(p.read_text())
PY
sh ./launch_win311.sh
sleep 2
python3 - <<'PY'
import os, socket, time
print('qmp_exists', os.path.exists('run/qmp.sock'))
for _ in range(20):
    try:
        s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        s.connect('run/qmp.sock')
        print('qmp_connect_ok')
        print(s.recv(4096).decode('utf-8','ignore'))
        s.close()
        break
    except Exception as e:
        time.sleep(0.2)
else:
    print('qmp_connect_fail')
PY
ss -ltnp | grep 5901 || true
