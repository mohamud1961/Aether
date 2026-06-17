python3 - <<'PY'
import os, glob
base='/usr/local/lib/python3.13/site-packages'
for p in sorted(glob.glob(base+'/pip*')):
    print(p, 'dir' if os.path.isdir(p) else 'file')
    if os.path.isdir(p):
        print('  sample', os.listdir(p)[:20])
PY