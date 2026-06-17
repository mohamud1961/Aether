python3 - <<'PY'
from pathlib import Path
p=Path('launch_win311.sh')
s=p.read_text()
s=s.replace('-monitor unix:run/qmp.sock,server,nowait','-qmp unix:run/qmp.sock,server,nowait')
p.write_text(s)
print(p.read_text())
PY
sh ./launch_win311.sh
sleep 2
ss -ltnp | grep -E ':5901|:80' || true
