import json, os
from collections import deque
from pathlib import Path
import numpy as np
from aura.frames import read_frames, tail_frames
from aura.brain.features import select_links, build_matrix, summary
from aura.brain.baseline import Baseline

def _atomic_write(path: Path, obj: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj))
    os.replace(tmp, path)

def _load_cal(home: Path):
    p = home / "calibration.json"
    if p.exists():
        return json.loads(p.read_text())
    return None

def _sig(z):
    return 1.0 / (1.0 + np.exp(-float(z)))

def run_brain(cfg, frames_path: Path, stop_event, model_path: Path = None, max_iters=None):
    sess = None
    if model_path and Path(model_path).exists():
        import onnxruntime as ort
        sess = ort.InferenceSession(str(model_path))
    cal = _load_cal(cfg.aura_home)
    baseline = None
    window = deque(maxlen=int(cfg.window_seconds * cfg.frame_hz * 2))
    for f in read_frames(frames_path)[-window.maxlen:]:
        window.append(f)
    n = 0
    last_infer = 0.0

    def infer(now):
        nonlocal cal, baseline, n, last_infer
        w = [x for x in window if x.ts >= now - cfg.window_seconds]
        if len(w) < 8:
            return False
        if cal is None:
            cal = {"link_ids": select_links(w, cfg.top_k), "empty_p995": 0.05, "activity_scale": 0.5}
        if baseline is None:
            baseline = Baseline(cal)
        m = build_matrix(w, cal["link_ids"])
        s = summary(m, window_seconds=cfg.window_seconds)
        state = baseline.update(s, ts=now)
        src = "baseline"
        if sess is not None:
            lp, lm, la = sess.run(None, {"rf": m[None].astype(np.float32)})
            state = {"presence": int(_sig(lp[0]) > 0.5), "motion": int(_sig(lm[0]) > 0.5),
                     "activity": round(max(0.0, min(100.0, float(la[0]))), 1)}
            src = "cnn"
        _atomic_write(cfg.aura_home / "state.json", {"ts": now, **state, "src": src})
        with open(cfg.aura_home / "features.jsonl", "a", encoding="utf-8") as fh:
            chans = np.std(np.diff(m, axis=1), axis=1).round(4).tolist()
            fh.write(json.dumps({"ts": now, **s, "channels": chans}) + "\n")
        last_infer = now
        n += 1
        return True

    if window:
        infer(window[-1].ts)
    if max_iters is not None and n >= max_iters:
        return
    gen = tail_frames(frames_path, poll_s=0.25, from_end=True, stop_event=stop_event)
    while not stop_event.is_set():
        try:
            f = next(gen)
        except StopIteration:
            break
        window.append(f)
        if f.ts - last_infer >= 0.5:
            infer(f.ts)
        if max_iters is not None and n >= max_iters:
            break
