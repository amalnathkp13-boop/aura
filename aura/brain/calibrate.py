import numpy as np
from aura.brain.features import select_links, build_matrix, summary

def _window_energies(frames, link_ids, win_s=15.0, step_s=5.0):
    if not frames:
        return []
    t0, t1 = frames[0].ts, frames[-1].ts
    out, t = [], t0
    while t + win_s <= t1:
        w = [f for f in frames if t <= f.ts < t + win_s]
        if len(w) >= 8:
            out.append(summary(build_matrix(w, link_ids))["motion_energy"])
        t += step_s
    return out

def calibrate_empty(frames, k: int = 16) -> dict:
    link_ids = select_links(frames, k)
    e = _window_energies(frames, link_ids)
    if not e:
        raise ValueError("not enough empty-room data")
    return {"link_ids": link_ids, "empty_p995": float(np.percentile(e, 99.5))}

def calibrate_walk(frames, cal: dict) -> dict:
    e = _window_energies(frames, cal["link_ids"])
    if not e:
        raise ValueError("not enough walking data")
    med = float(np.median(e))
    if med <= cal["empty_p995"]:
        raise ValueError("walk energy not above empty threshold — recheck placement")
    return {**cal, "activity_scale": med}
