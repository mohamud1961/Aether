python3 - <<'PY'
from pathlib import Path
Path('launch_win311.sh').write_text('''#!/bin/sh
set -eu
mkdir -p run
rm -f run/qmp.sock run/qemu.pid run/qemu.log
nohup qemu-system-i386 \
  -m 32 \
  -cpu 486 \
  -drive file=isos/win311.img,format=raw,if=ide,snapshot=on \
  -vnc 127.0.0.1:1 \
  -monitor unix:run/qmp.sock,server,nowait \
  -serial none \
  -parallel none \
  -display none \
  -net none \
  -rtc base=localtime \
  >run/qemu.log 2>&1 &
 echo $! > run/qemu.pid
''')
Path('nginx.conf').write_text('''worker_processes  1;
error_log  run/nginx-error.log info;
pid        run/nginx.pid;
events { worker_connections  1024; }
http {
  access_log  run/nginx-access.log;
  server {
    listen 80;
    location / {
      default_type text/html;
      return 200 '<html><body>Windows 3.11 VM ready</body></html>';
    }
  }
}
''')
PY
chmod +x launch_win311.sh
start_job 'sh ./launch_win311.sh && nginx -c "$PWD/nginx.conf"'