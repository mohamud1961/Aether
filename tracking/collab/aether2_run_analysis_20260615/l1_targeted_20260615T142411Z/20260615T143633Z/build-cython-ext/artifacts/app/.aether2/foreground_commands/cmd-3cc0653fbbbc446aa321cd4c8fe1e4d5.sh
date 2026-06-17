python3 - <<'PY'
from pathlib import Path
p = Path('/app/pyknotid/setup.py')
text = p.read_text()
old = """    ext_modules = cythonize(ext_modules)\n    include_dirs = [numpy.get_include()]\n"""
new = """    ext_modules = cythonize(ext_modules, compiler_directives={'language_level': '3'})\n    include_dirs = [numpy.get_include()]\n"""
if old in text:
    text = text.replace(old, new)
else:
    print('pattern not found')
p.write_text(text)
print('patched', p)
PY