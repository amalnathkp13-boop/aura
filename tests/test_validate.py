import numpy as np
from aura.frames import RFFrame
from training.validate import validate

def _mk(t0, n, jitter, seed=0, hz=4.0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        wobble = jitter * np.sin(i / 3.0) + rng.normal(0, jitter / 2 + 1e-6)
        out.append(RFFrame(ts=t0 + i / hz,
                           wifi={"aaaaaaaa": -60 + wobble, "bbbbbbbb": -70 + wobble * 0.8},
                           link=[-50 + wobble], ble={}))
    return out

def test_validate_metrics_on_synthetic_session():
    frames = _mk(0, 240, 0.05) + _mk(60, 240, 4.0, seed=1)   # 60 s empty, 60 s walking
    timeline = [{"t0": 0, "t1": 60, "truth": "empty"},
                {"t0": 60, "t1": 120, "truth": "walking"}]
    m = validate(frames, timeline)
    assert m["windows"] > 0
    assert m["presence_acc"] >= 0.8
    assert m["motion_acc"] >= 0.8
    assert m["empty_motion_false_windows"] <= 1
    assert m["entry_latency_s"] is not None and m["entry_latency_s"] <= 30

def test_validate_skips_windows_straddling_segments():
    frames = _mk(0, 120, 0.05)
    timeline = [{"t0": 0, "t1": 10, "truth": "empty"}]        # only 10 s covered
    m = validate(frames, timeline)
    assert m["windows"] == 0                                   # no window fits inside
