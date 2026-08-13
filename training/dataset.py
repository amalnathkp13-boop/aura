import numpy as np
from pathlib import Path
from aura.frames import read_frames
from aura.labeler.labeler import read_labels
from aura.brain.features import build_matrix

WIN_S, STEP_S = 15.0, 5.0

def build_dataset(session_dirs, link_ids, out_npz: Path):
    X, yp, ym, ya, names = [], [], [], [], []
    for d in session_dirs:
        d = Path(d)
        frames = read_frames(d / "frames.jsonl")
        labels = read_labels(d / "labels.jsonl")
        if not frames or not labels:
            continue
        lts = np.array([l["ts"] for l in labels])
        t = frames[0].ts
        while t + WIN_S <= frames[-1].ts:
            w = [f for f in frames if t <= f.ts < t + WIN_S]
            center = t + WIN_S / 2
            near = np.abs(lts - center) <= WIN_S / 2 + 2.0
            if len(w) >= 8 and near.any():
                sel = [labels[i] for i in np.where(near)[0]]
                X.append(build_matrix(w, link_ids))
                yp.append(int(np.mean([l["person"] for l in sel]) >= 0.5))
                mean_motion = float(np.mean([l["motion"] for l in sel]))
                ym.append(int(mean_motion > 0.02))
                ya.append(min(100.0, mean_motion * 2000.0))
                names.append(d.name)
            t += STEP_S
    np.savez(out_npz, x=np.array(X, dtype=np.float32), y_presence=np.array(yp),
             y_motion=np.array(ym), y_activity=np.array(ya, dtype=np.float32),
             session=np.array(names))
