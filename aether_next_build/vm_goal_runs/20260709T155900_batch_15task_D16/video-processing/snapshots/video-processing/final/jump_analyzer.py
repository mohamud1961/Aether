import sys
import cv2
import numpy as np


def compute_frame_metrics(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise SystemExit(f'Could not open video: {video_path}')

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ret, bg = cap.read()
    if not ret:
        raise SystemExit('Could not read first frame')

    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY).astype(np.float32)
    prev = bg_gray.copy()
    h, w = bg_gray.shape
    roi_y = int(h * 0.35)

    metrics = []
    for i in range(1, frame_count):
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        diff_bg = np.abs(gray - bg_gray)
        diff_prev = np.abs(gray - prev)

        roi_bg = diff_bg[roi_y:, :]
        roi_prev = diff_prev[roi_y:, :]
        metrics.append({
            'i': i,
            'bg_mean': float(diff_bg.mean()),
            'bg_frac': float((diff_bg > 25).mean()),
            'roi_bg_mean': float(roi_bg.mean()),
            'roi_bg_frac': float((roi_bg > 25).mean()),
            'prev_mean': float(diff_prev.mean()),
            'prev_frac': float((diff_prev > 25).mean()),
            'roi_prev_mean': float(roi_prev.mean()),
            'roi_prev_frac': float((roi_prev > 25).mean()),
        })
        prev = gray

    cap.release()
    return frame_count, metrics


def smooth(values, window=5):
    if len(values) < window:
        return np.array(values, dtype=np.float32)
    kernel = np.ones(window, dtype=np.float32) / window
    return np.convolve(np.array(values, dtype=np.float32), kernel, mode='same')


def find_event_frames(metrics):
    idx = np.array([m['i'] for m in metrics], dtype=int)
    roi_prev_frac = np.array([m['roi_prev_frac'] for m in metrics], dtype=np.float32)
    roi_bg_frac = np.array([m['roi_bg_frac'] for m in metrics], dtype=np.float32)
    prev_mean = np.array([m['prev_mean'] for m in metrics], dtype=np.float32)
    bg_mean = np.array([m['bg_mean'] for m in metrics], dtype=np.float32)

    s_prev = smooth(roi_prev_frac, 7)
    s_bg = smooth(roi_bg_frac, 7)

    # Takeoff: first strong rise in motion away from the initial running state.
    # We look for the earliest frame after a low-motion baseline where the
    # smoothed frame-to-frame ROI difference exceeds an adaptive threshold.
    base_n = min(15, len(s_prev))
    base = float(np.median(s_prev[:base_n])) if base_n else 0.0
    spread = float(np.std(s_prev[:base_n])) if base_n else 0.0
    take_thresh = max(base + 3.0 * spread, float(np.percentile(s_prev, 80)))
    take_candidates = np.where(s_prev > take_thresh)[0]
    takeoff = int(idx[take_candidates[0]]) if len(take_candidates) else int(idx[int(np.argmax(s_prev))])

    # Landing: after takeoff, find the first frame where the frame-to-frame
    # ROI difference settles back near baseline after the airborne interval.
    post = np.where(idx > takeoff + 5)[0]
    if len(post) == 0:
        landing = min(int(idx[-1]), takeoff + 1)
    else:
        post_vals = s_prev[post]
        post_base_n = min(10, len(post_vals))
        post_base = float(np.median(post_vals[:post_base_n])) if post_base_n else float(np.median(s_prev))
        post_spread = float(np.std(post_vals[:post_base_n])) if post_base_n else float(np.std(s_prev))
        land_thresh = max(post_base + 1.5 * post_spread, float(np.percentile(post_vals, 35)))
        # Find first point after the motion peak where motion has been low for a few frames.
        peak_local = int(post[np.argmax(post_vals)])
        low_run = 0
        landing = int(idx[-1])
        for j in range(np.where(idx == peak_local)[0][0], len(idx)):
            if s_prev[j] < land_thresh:
                low_run += 1
                if low_run >= 4:
                    landing = int(idx[j - 3])
                    break
            else:
                low_run = 0
        if landing <= takeoff:
            landing = int(idx[min(len(idx) - 1, np.argmax(s_prev) + 10)])
    return takeoff, landing, {
        'take_thresh': take_thresh,
        'landing_hint_thresh': float('nan')
    }


def write_toml(path, takeoff, landing):
    try:
        import toml  # type: ignore
        text = toml.dumps({
            'jump_takeoff_frame_number': int(takeoff),
            'jump_land_frame_number': int(landing),
        })
    except Exception:
        text = f'jump_takeoff_frame_number = {int(takeoff)}\n' \
               f'jump_land_frame_number = {int(landing)}\n'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def main(argv):
    if len(argv) != 2:
        raise SystemExit('Usage: jump_analyzer.py INPUT_VIDEO.mp4')
    video_path = argv[1]
    frame_count, metrics = compute_frame_metrics(video_path)
    takeoff, landing, _ = find_event_frames(metrics)
    takeoff = max(0, min(int(takeoff), frame_count - 1))
    landing = max(0, min(int(landing), frame_count - 1))
    if landing < takeoff:
        landing = takeoff
    write_toml('/app/output.toml', takeoff, landing)
    print(f'{takeoff} {landing}')


if __name__ == '__main__':
    main(sys.argv)
