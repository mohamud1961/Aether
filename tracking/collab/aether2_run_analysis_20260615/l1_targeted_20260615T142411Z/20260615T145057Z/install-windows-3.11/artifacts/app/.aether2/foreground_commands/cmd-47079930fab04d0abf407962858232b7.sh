kill 1292 || true; sleep 1; ss -ltnp | grep 5901 || true; cat > launch_win311.sh <<'SH'
#!/bin/sh
set -eu
mkdir -p run
rm -f run/qmp.sock run/qemu.pid run/qemu.log
nohup qemu-system-i386 \
  -m 32 \
  -cpu 486 \
  -drive file=isos/win311.img,format=raw,if=ide,snapshot=on \
  -vnc 127.0.0.1:1 \
  -qmp unix:run/qmp.sock,server,nowait \
  -serial none \
  -parallel none \
  -display none \
  -net none \
  -rtc base=localtime \
  >run/qemu.log 2>&1 &
 echo $! > run/qemu.pid
SH
chmod +x launch_win311.sh
sh ./launch_win311.sh
sleep 2
python3 - <<'PY'
import socket, time
for _ in range(50):
    try:
        s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        s.connect('run/qmp.sock')
        print('qmp_connected')
        print(s.recv(4096).decode('utf-8','ignore'))
        s.sendall(b'{"execute":"qmp_capabilities"}\n')
        print(s.recv(4096).decode('utf-8','ignore'))
        s.sendall(b'{"execute":"cont"}\n')
        print(s.recv(4096).decode('utf-8','ignore'))
        s.sendall(b'{"execute":"send-key","arguments":{"keys":[{"type":"qcode","data":"ret"}]}}\n')
        print(s.recv(4096).decode('utf-8','ignore'))
        s.close()
        break
    except Exception:
        time.sleep(0.2)
else:
    print('qmp_failed')
PY
ss -ltnp | grep 5901 || true
