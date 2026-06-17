python3 - <<'PY'
import cv2, numpy as np
p='/app/example_video.mp4'
cap=cv2.VideoCapture(p)
frames=[]
idxs=[0,10,20,30,40,50,60,70,80,90,100,110,119]
for i in range(int(cap.get(cv2.CAP_PROP_FRAME_COUNT))):
    ok, f = cap.read()
    if not ok: break
    if i in idxs:
        gray=cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        # simple foreground proxy against first frame
        if i==0:
            base=gray.astype(np.int16)
        diff=np.mean(np.abs(gray.astype(np.int16)-base))
        print(i, 'mean_abs_diff_from_first', round(float(diff),2), 'mean', round(float(gray.mean()),2))
cap.release()
PY