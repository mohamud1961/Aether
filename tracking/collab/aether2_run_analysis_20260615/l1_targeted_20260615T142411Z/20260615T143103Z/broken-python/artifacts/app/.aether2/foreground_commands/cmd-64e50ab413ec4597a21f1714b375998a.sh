python3 - <<'PY'
import sysconfig, glob, os
for p in glob.glob('/usr/local/lib/python3.13/site-packages/*pip*'):
    print(p)
PY