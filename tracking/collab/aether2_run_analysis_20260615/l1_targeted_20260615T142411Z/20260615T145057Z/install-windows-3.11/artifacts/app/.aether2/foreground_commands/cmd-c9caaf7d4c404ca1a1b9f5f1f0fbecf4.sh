vncsnapshot -allowblank 127.0.0.1:1 vncshot.jpg && python3 - <<'PY'
from PIL import Image
img=Image.open('vncshot.jpg')
print('size', img.size)
print('bbox', img.getbbox())
PY