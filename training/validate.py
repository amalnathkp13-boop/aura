"""Offline metrics: recorded frames + declared truth timeline -> submission table.

Timeline truth values: "empty" (nobody home), "present" (person, mostly still),
"walking" (person moving). A window is scored only when it lies entirely inside
one timeline segment. The detector runs chronologically so presence decay
behaves exactly as it does live.
"""
import argparse, json
from pathlib import Path

import numpy as np

from aura.frames import read_frames
from aura.brain.features import select_links
from aura.brain.ruview.detector import RuViewDetector

PRESENCE_TRUTH = {"empty": 0, "present": 1, "walking": 1}
MOTION_TRUTH = {"empty": 0, "walking": 1}   # "present" (still) excluded: motion may be 0 or brief


def _truth_at(timeline, t_start, t_end):
    for seg in timeline:
        if seg["t0"] <= t_start and t_end <= seg["t1"]:
            return seg["truth"]
    return None


def validate(frames, timeline, cal=None, win_s=15.0, step_s=5.0, top_k=16):
    if not frames:
        return {"windows": 0, "presence_acc": None, "n_presence": 0,
                "motion_acc": None, "n_motion": 0,
                "empty_motion_false_windows": 0, "entry_latency_s": None}
    det = RuViewDetector(cal)
    link_ids = (cal or {}).get("link_ids") or select_links(frames, top_k)
    rows = []
    t = frames[0].ts
    while t + win_s <= frames[-1].ts:
        w = [f for f in frames if t <= f.ts < t + win_s]
        truth = _truth_at(timeline, t, t + win_s)
        if len(w) >= 8 and truth is not None:
            r = det.update(w, link_ids, ts=t + win_s)
            if r is not None:
                rows.append({"ts": t + win_s, "truth": truth, **r})
        t += step_s

    def _acc(key, truthmap):
        pairs = [(r[key], truthmap[r["truth"]]) for r in rows if r["truth"] in truthmap]
        if not pairs:
            return None, 0
        return sum(int(p == want) for p, want in pairs) / len(pairs), len(pairs)

    presence_acc, n_p = _acc("presence", PRESENCE_TRUTH)
    motion_acc, n_m = _acc("motion", MOTION_TRUTH)
    false_windows = sum(1 for r in rows if r["truth"] == "empty" and r["motion"] == 1)

    latencies = []
    for prev, nxt in zip(timeline, timeline[1:]):
        if prev["truth"] == "empty" and nxt["truth"] in ("present", "walking"):
            hit = next((r["ts"] for r in rows if r["ts"] >= nxt["t0"] and r["presence"] == 1), None)
            if hit is not None:
                latencies.append(hit - nxt["t0"])
    entry_latency = float(np.median(latencies)) if latencies else None

    return {"windows": len(rows), "presence_acc": presence_acc, "n_presence": n_p,
            "motion_acc": motion_acc, "n_motion": n_m,
            "empty_motion_false_windows": false_windows,
            "entry_latency_s": entry_latency}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("timeline")
    ap.add_argument("--cal", default=None)
    a = ap.parse_args()
    frames = read_frames(Path(a.frames))
    timeline = json.loads(Path(a.timeline).read_text())
    cal = json.loads(Path(a.cal).read_text()) if a.cal else None
    print(json.dumps(validate(frames, timeline, cal), indent=2))


if __name__ == "__main__":
    main()
