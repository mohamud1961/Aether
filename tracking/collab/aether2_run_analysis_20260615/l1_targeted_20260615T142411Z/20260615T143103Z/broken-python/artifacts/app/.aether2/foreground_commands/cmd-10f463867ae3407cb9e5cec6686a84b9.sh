python3 - <<'PY'
import ensurepip, os, subprocess, sys, glob
wheel = glob.glob(os.path.join(os.path.dirname(ensurepip.__file__), '_bundled', 'pip-*.whl'))[0]
print('wheel', wheel)
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-index', '--force-reinstall', wheel])
PY