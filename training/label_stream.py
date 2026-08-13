"""Training-phase tool: label an IP-camera MJPEG stream (DroidCam etc.) into labels.jsonl.

Parses the MJPEG HTTP stream directly (urllib + socket timeouts) instead of
cv2.VideoCapture/ffmpeg, whose blocking reads and opaque open failures caused
silent stalls. Reconnects forever; a busy/absent camera is retried every 5 s.
Runs person detection + writes one label per second.
Usage: python training/label_stream.py <stream_url> <out_labels.jsonl>
"""
import sys, time, urllib.request
from pathlib import Path

import cv2
import numpy as np

from aura.labeler.labeler import write_label

SOI, EOI = b"\xff\xd8", b"\xff\xd9"  # JPEG start/end markers


def mjpeg_frames(url: str, read_timeout: float = 5.0, max_buf: int = 4_000_000):
    """Yield decoded BGR frames from an MJPEG HTTP stream. Raises on any
    connection problem or stall (socket timeout) — caller reconnects."""
    resp = urllib.request.urlopen(url, timeout=read_timeout)
    ctype = resp.headers.get("Content-Type", "")
    if "multipart" not in ctype and "jpeg" not in ctype:
        raise ConnectionError(f"not an MJPEG stream (Content-Type: {ctype!r})")
    buf = b""
    read1 = getattr(resp, "read1", None)
    while True:
        # read1 = "whatever is available now" (read(n) would block for n full bytes);
        # both honor the socket timeout -> stalls raise
        chunk = read1(65536) if read1 else resp.read(4096)
        if not chunk:
            raise ConnectionError("stream ended")
        buf += chunk
        while True:  # drain every complete frame already buffered
            start = buf.find(SOI)
            end = buf.find(EOI, start + 2) if start != -1 else -1
            if start == -1 or end == -1:
                break
            jpg, buf = buf[start:end + 2], buf[end + 2:]
            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                yield frame
        if len(buf) > max_buf:
            buf = b""  # garbage guard: resync


def main(url: str, out_path: Path):
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prev, last_label = None, 0.0
    print(f"labeling {url} -> {out_path}", flush=True)
    while True:
        try:
            for frame in mjpeg_frames(url):
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
        except Exception as e:
            print(f"stream unavailable ({type(e).__name__}), retrying in 5s", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
