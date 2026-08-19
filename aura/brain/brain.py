import json, os
from collections import deque
from pathlib import Path
import numpy as np
from aura.frames import read_frames, tail_frames
from aura.brain.features import select_links, build_matrix, summary
from aura.brain.baseline import Baseline
from aura.brain.ruview.detector import RuViewDetector

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

# Auto-calibration mode (no calibration.json on disk) has no measured thresholds,
# so it always falls back to these constants for the Baseline. link_ids, by
# contrast, are re-derived every inference (see infer()) instead of being cached
# once - a boot-time window with no WiFi yet must not freeze the selection forever.
AUTO_EMPTY_P995 = 0.05
AUTO_ACTIVITY_SCALE = 0.5

def run_brain(cfg, frames_path: Path, stop_event, model_path: Path = None, max_iters=None):
    sess = None
    model_channels = None
    if cfg.detector == "cnn" and model_path and Path(model_path).exists():
        import onnxruntime as ort
        sess = ort.InferenceSession(str(model_path))
        shape = sess.get_inputs()[0].shape
        dim1 = shape[1] if len(shape) > 1 else None
        model_channels = dim1 if isinstance(dim1, int) else None
    cal = _load_cal(cfg.aura_home)
    auto_mode = cal is None
    if cal is not None and cfg.detector != "baseline" and "rv" not in cal:
        print("calibration.json predates ruview thresholds - re-run Learn my room; using defaults", flush=True)
    baseline = None
    rvdet = RuViewDetector(cal)   # tolerates cal=None (upstream default thresholds)
    window = deque(maxlen=int(cfg.window_seconds * cfg.frame_hz * 2))
    for f in read_frames(frames_path)[-window.maxlen:]:
        window.append(f)
    n = 0
    last_infer = 0.0

    def infer(now):
        nonlocal baseline, n, last_infer
        w = [x for x in window if x.ts >= now - cfg.window_seconds]
        if len(w) < 8:
            return False
        if auto_mode:
            link_ids = select_links(w, cfg.top_k)
            if sess is not None:
                # ONNX input channel count is fixed at export time (link count + 1 for
                # the link stream); auto-mode's live selection can vary call-to-call,
                # so pad/truncate to match. Fall back to cfg.top_k when the model's
                # channel axis is dynamic/unreadable.
                want = (model_channels - 1) if model_channels else cfg.top_k
                if len(link_ids) < want:
                    link_ids = link_ids + [f"pad{i}" for i in range(want - len(link_ids))]
                elif len(link_ids) > want:
                    link_ids = link_ids[:want]
            if baseline is None:
                baseline = Baseline({"link_ids": [], "empty_p995": AUTO_EMPTY_P995,
                                     "activity_scale": AUTO_ACTIVITY_SCALE})
        else:
            link_ids = cal["link_ids"]
            if baseline is None:
                baseline = Baseline(cal)
        m = build_matrix(w, link_ids)
        s = summary(m, window_seconds=cfg.window_seconds)
        state = baseline.update(s, ts=now)
        src = "baseline"
        if sess is not None:
            lp, lm, la = sess.run(None, {"rf": m[None].astype(np.float32)})
            state = {"presence": int(_sig(lp[0]) > 0.5), "motion": int(_sig(lm[0]) > 0.5),
                     "activity": round(max(0.0, min(100.0, float(la[0]))), 1)}
            src = "cnn"
        elif cfg.detector != "baseline":
            rv = rvdet.update(w, link_ids, ts=now, frame_hz=cfg.frame_hz)
            if rv is not None:   # None (no usable channels) -> keep baseline state
                state, src = rv, "ruview"
        _atomic_write(cfg.aura_home / "state.json", {"ts": now, **state, "src": src})
        with open(cfg.aura_home / "features.jsonl", "a", encoding="utf-8") as fh:
            chans = np.std(np.diff(m, axis=1), axis=1).round(4).tolist()
            spec = np.abs(np.fft.rfft(m, axis=1)).mean(axis=0)[1:]  # drop DC; 30 bins for out_len 60
            fh.write(json.dumps({"ts": now, **s, "channels": chans, "spectrum": spec.round(3).tolist()}) + "\n")
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
