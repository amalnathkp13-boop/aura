"""Training-phase tool: label an IP-camera stream (DroidCam etc.) into labels.jsonl.

Reads the MJPEG stream continuously (so no stale-buffer lag), but runs person
detection + writes one label per second. Reconnects on stream drops forever.
Usage: python training/label_stream.py <stream_url> <out_labels.jsonl>
"""
import sys, time
from pathlib import Path

import cv2

from aura.labeler.labeler import write_label


def main(url: str, out_path: Path):
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cap, prev, last_label = None, None, 0.0
    last_ok_read = time.time()
    print(f"labeling {url} -> {out_path}", flush=True)
    while True:
        if cap is None:
            # FFMPEG-level timeouts: a dead/stalled socket must fail fast, not block forever
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG,
                                   [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000])
            if not cap.isOpened():
                cap.release(); cap = None
                print("stream down, retrying in 5s", flush=True)
                time.sleep(5)
                continue
            last_ok_read = time.time()
        ok, frame = cap.read()
        if not ok or time.time() - last_ok_read > 15.0:
            print("stream stalled, reconnecting", flush=True)
            cap.release(); cap = None
            continue
        last_ok_read = time.time()
        now = time.time()
        if now - last_label < 1.0:
            continue
        last_label = now
        gray = cv2.cvtColor(cv2.resize(frame, (320, 240)), cv2.COLOR_BGR2GRAY)
        motion = float((cv2.absdiff(gray, prev) > 25).mean()) if prev is not None else 0.0
        prev = gray
        res = model.predict(frame, classes=[0], conf=0.5, verbose=False)
        person = int(len(res[0].boxes) > 0)
        write_label(out_path, now, person, motion)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
