python3 - <<'PY'
import os, subprocess, textwrap, sys
img='isos/win311.img'
print('img_exists', os.path.exists(img), 'size', os.path.getsize(img))
for c in ['qemu-system-i386','qemu-system-x86_64']:
    r=subprocess.run(['sh','-lc',f'command -v {c}'],capture_output=True,text=True)
    print(c, r.stdout.strip() or 'missing')
PY