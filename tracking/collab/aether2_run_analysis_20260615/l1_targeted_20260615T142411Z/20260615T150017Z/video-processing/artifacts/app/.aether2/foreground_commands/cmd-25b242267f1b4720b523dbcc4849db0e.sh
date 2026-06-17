python3 - <<'PY'
import cv2, numpy as np
p='/app/example_video.mp4'
cap=cv2.VideoCapture(p)
ret, prev = cap.read()
prevg=cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
vals=[]
for i in range(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))):
    ret, f = cap.read()
    if not ret: break
    g=cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    diff=np.mean(np.abs(g.astype(np.int16)-prevg.astype(np.int16)))
    vals.append(diff)
    prevg=g
cap.release()
mx=max(vals); mn=min(vals)
print('min', mn, 'max', mx, 'argmax', vals.index(mx)+1)
# print top 15 peaks
for i,v in sorted(enumerate(vals, start=1), key=lambda x:x[1], reverse=True)[:15]:
    print(i, round(v,3))
PY