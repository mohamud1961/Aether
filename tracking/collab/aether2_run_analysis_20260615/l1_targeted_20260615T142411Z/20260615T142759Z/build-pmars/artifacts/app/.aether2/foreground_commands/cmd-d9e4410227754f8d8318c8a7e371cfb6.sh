sh -lc 'python3 - <<"PY"
from pathlib import Path
p=Path("/etc/apt/sources.list.d/debian-src.list")
p.write_text("deb-src http://deb.debian.org/debian trixie main\ndeb-src http://deb.debian.org/debian trixie-updates main\ndeb-src http://deb.debian.org/debian-security trixie-security main\n")
print(p.read_text())
PY
apt-get update && apt-get source pmars