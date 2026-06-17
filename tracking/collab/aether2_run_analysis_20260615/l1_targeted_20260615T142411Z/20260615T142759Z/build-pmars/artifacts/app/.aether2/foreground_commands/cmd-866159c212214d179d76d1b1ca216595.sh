sh -lc 'apt-get install -y libx11-dev && cd /app/pmars-0.9.4 && python3 - <<"PY"
from pathlib import Path
p=Path("debian/rules")
p.write_text("""#!/usr/bin/make -f

export DEB_BUILD_MAINT_OPTIONS = hardening=+all

%:
	dh $@

override_dh_auto_build:
	dh_auto_build --sourcedir src CFLAGS=\"-O -DEXT94 -DPERMUTATE -DRWLIMIT\" LIB=\"\"\n
override_dh_auto_install:
	dh_auto_install --sourcedir src
	install -D -m 0755 src/pmars debian/pmars/usr/local/bin/pmars

override_dh_auto_clean:
	dh_auto_clean --sourcedir src
	rm -f src/pmars
""")
print(p.read_text())
PY
DEB_BUILD_OPTIONS=nostrip dpkg-buildpackage -us -uc -b'