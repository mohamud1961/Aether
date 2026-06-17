python3 - <<'PY'
import subprocess, time, os
# capture a screenshot from VNC using vncsnapshot
subprocess.run(['vncsnapshot','127.0.0.1:1','vncshot.jpg'], check=True)
print('shot_size', os.path.getsize('vncshot.jpg'))
PY
file vncshot.jpg
python3 - <<'PY'
from PIL import Image
img=Image.open('vncshot.jpg')
print(img.size, img.getbbox())
PY