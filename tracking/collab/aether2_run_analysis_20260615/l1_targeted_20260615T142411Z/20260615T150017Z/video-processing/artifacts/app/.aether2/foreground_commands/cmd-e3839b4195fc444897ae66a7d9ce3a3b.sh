python3 - <<'PY'
import cv2, os
p='/app/example_video.mp4'
cap=cv2.VideoCapture(p)
print('opened', cap.isOpened())
print('frames', int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
print('fps', cap.get(cv2.CAP_PROP_FPS))
print('size', int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
cap.release()
PY