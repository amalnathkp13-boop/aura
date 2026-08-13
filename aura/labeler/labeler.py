import json, time
from pathlib import Path

def write_label(path: Path, ts: float, person: int, motion: float):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": ts, "person": person, "motion": round(motion, 4)}) + "\n")

def read_labels(path: Path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out

def run_labeler(out_path: Path, camera_index: int = 0):
    import cv2
    import numpy as np
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    cap = cv2.VideoCapture(camera_index)
    prev = None
    print("Labeler running — Ctrl+C to stop")
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(1); continue
        gray = cv2.cvtColor(cv2.resize(frame, (320, 240)), cv2.COLOR_BGR2GRAY)
        motion = 0.0
        if prev is not None:
            motion = float((cv2.absdiff(gray, prev) > 25).mean())
        prev = gray
        res = model.predict(frame, classes=[0], conf=0.5, verbose=False)
        person = int(len(res[0].boxes) > 0)
        write_label(out_path, time.time(), person, motion)
        time.sleep(1.0)
