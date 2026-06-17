python3 - <<'PY'
import ensurepip, os, zipfile, sysconfig, glob
site = sysconfig.get_paths()['purelib']
wheel = glob.glob(os.path.join(os.path.dirname(ensurepip.__file__), '_bundled', 'pip-*.whl'))[0]
print('site', site)
print('wheel', wheel)
with zipfile.ZipFile(wheel) as z:
    for name in z.namelist():
        if name.startswith('pip/') or name.startswith('pip-'):
            z.extract(name, site)
print('done')
PY