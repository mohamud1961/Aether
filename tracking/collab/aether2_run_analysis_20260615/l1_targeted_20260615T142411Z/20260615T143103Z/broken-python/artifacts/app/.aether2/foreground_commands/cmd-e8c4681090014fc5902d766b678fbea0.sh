python3 - <<'PY'
import sys, sysconfig, os, glob
print('executable', sys.executable)
print('version', sys.version)
print('prefix', sys.prefix)
print('base_prefix', sys.base_prefix)
print('paths', sys.path)
print('stdlib', sysconfig.get_paths().get('stdlib'))
print('purelib', sysconfig.get_paths().get('purelib'))
for p in ['/usr/local/lib/python3.13/site-packages','/usr/local/lib/python3.13/dist-packages','/usr/local/lib/python3.13','/usr/local/lib/python3.13/lib-dynload']:
    print(p, os.path.exists(p), os.listdir(p)[:10] if os.path.isdir(p) else None)
PY