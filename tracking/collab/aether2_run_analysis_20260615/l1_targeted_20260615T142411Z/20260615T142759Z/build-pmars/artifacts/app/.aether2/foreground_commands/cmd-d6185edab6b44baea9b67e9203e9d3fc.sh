sh -lc 'cd /app/pmars-0.9.4 && cp debian/rules /tmp/rules.bak && python3 - <<"PY"
from pathlib import Path
p=Path("debian/rules")
text=p.read_text()
text=text.replace("\toverride_dh_auto_build:\n\t\tdh_auto_build --sourcedir src\n", "override_dh_auto_build:\n\tdh_auto_build --sourcedir src CFLAGS=\"-O -DEXT94 -DPERMUTATE -DRWLIMIT\" LIB=\"\"\n")
p.write_text(text)
print(p.read_text())
PY
DEB_BUILD_OPTIONS=nostrip dpkg-buildpackage -us -uc -b'