import sys
from pathlib import Path
import cv2
import numpy as np


def toml_escape_int(v: int) -> str:
    return str(int(v))


def largest_nonborder_component(mask: np.ndarray):
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    h, w = mask.shape
    best = None
    best_area = 0
    for i in range(1, num):
        x, y, bw, bh, area = stats[i]
        if area <= 0:
            continue
        # Skip components that touch the image border; these are usually compression/background artifacts.
        if x <= 0 or y <= 0 or x + bw >= w or y + bh >= h:
            continue
        if area > best_area:
            best_area = area
            best = (x, y, bw, bh, area)
    return best


def detect_jump_frames(video_path: str):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f'Could not open video: {video_path}')

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        raise RuntimeError('Video has no frames')

    ret, first = cap.read()
    if not ret:
        raise RuntimeError('Could not read first frame')

    bg = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
    h, w = bg.shape
    kernel = np.ones((5, 5), np.uint8)

    bottoms = []
    valid_idx = []

    # Read remaining frames and compute a stable foreground-bottom signal.
    for idx in range(1, frame_count):
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray, bg)
        diff = cv2.GaussianBlur(diff, (5, 5), 0)
        _, th = cv2.threshold(diff, 35, 255, cv2.THRESH_BINARY)
        th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
        th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)

        comp = largest_nonborder_component(th)
        if comp is None:
            continue
        x, y, bw, bh, area = comp
        bottom = y + bh - 1
        bottoms.append(bottom)
        valid_idx.append(idx)

    if len(bottoms) < 5:
        # Fallback to trivial output rather than fail; but this should not happen on the task videos.
        return 0, max(1, frame_count - 1)

    bottoms = np.asarray(bottoms, dtype=np.float32)

    # Median smoothing over a small window to suppress detection flicker.
    smooth = bottoms.copy()
    win = 5
    half = win // 2
    for i in range(len(bottoms)):
        a = max(0, i - half)
        b = min(len(bottoms), i + half + 1)
        smooth[i] = float(np.median(bottoms[a:b]))

    # Estimate a baseline from the earliest stable motion frames.
    # We use the upper quartile of the smoothed bottoms as the standing/running contact level.
    baseline = float(np.percentile(smooth[: max(10, len(smooth) // 3)], 75))
    low_threshold = baseline - 60.0

    low = smooth < low_threshold

    # Merge tiny gaps in the low interval caused by segmentation flicker.
    merged = low.copy()
    i = 0
    n = len(merged)
    while i < n:
        if not merged[i]:
            j = i
            while j < n and not merged[j]:
                j += 1
            gap = j - i
            left = i - 1 >= 0 and merged[i - 1]
            right = j < n and merged[j]
            if left and right and gap <= 2:
                merged[i:j] = True
            i = j
        else:
            i += 1

    # Choose the longest low run after the runner has entered the scene.
    best_start = best_end = None
    best_len = -1
    i = 0
    while i < n:
        if merged[i]:
            j = i
            while j < n and merged[j]:
                j += 1
            # Ignore very early spurious detections.
            if valid_idx[i] >= 10:
                length = j - i
                if length > best_len:
                    best_len = length
                    best_start, best_end = i, j - 1
            i = j
        else:
            i += 1

    if best_start is None:
        # Fallback: pick the strongest downward excursion.
        jump_i = int(np.argmin(smooth))
        takeoff = valid_idx[max(0, jump_i - 1)]
        landing = valid_idx[jump_i]
        return takeoff, landing

    takeoff = valid_idx[best_start]

    # Landing is the first valid frame after the low interval that returns to the baseline/contact level.
    landing = valid_idx[best_end]
    for k in range(best_end + 1, n):
        if smooth[k] >= low_threshold + 25.0:
            landing = valid_idx[k]
            break
    else:
        landing = valid_idx[best_end]

    if landing <= takeoff:
        landing = min(frame_count - 1, takeoff + 1)

    return int(takeoff), int(landing)


def write_output(path: str, takeoff: int, landing: int):
    text = (
        f'jump_takeoff_frame_number = {toml_escape_int(takeoff)}\n'
        f'jump_land_frame_number = {toml_escape_int(landing)}\n'
    )
    Path(path).write_text(text, encoding='utf-8')


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python3 jump_analyzer.py <input.mp4>')
    video_path = sys.argv[1]
    takeoff, landing = detect_jump_frames(video_path)
    write_output('/app/output.toml', takeoff, landing)


if __name__ == '__main__':
    main()
