"""Presence hysteresis: acquiring presence needs the full calibrated variance
threshold; KEEPING it needs only KEEP_FACTOR of it, so a person sitting almost
still (micro-movements just under the acquire threshold) is not dropped once
the 120-s motion hold expires. An empty room starts from absent, where the
full threshold applies, so the false-alarm behaviour is unchanged."""
import numpy as np
from aura.frames import RFFrame
from aura.brain.rfsense.detector import RFDetector, KEEP_FACTOR

LINK_IDS = ["aaaaaaaa"]


def _cal():
    return {"link_ids": LINK_IDS,
            "rv": {"var_thresh": {"__link__": 1.0, "aaaaaaaa": 1.0},
                   "motion_thresh": {"__link__": 50.0, "aaaaaaaa": 50.0}}}


def _frames(n, amp, seed=0, hz=4.0, t0=0.0):
    rng = np.random.default_rng(seed)
    return [RFFrame(ts=t0 + i / hz,
                    wifi={"aaaaaaaa": -60 + amp * np.sin(i / 2.0) + rng.normal(0, amp / 3 + 1e-6)},
                    link=[-50 + amp * np.sin(i / 2.0) + rng.normal(0, amp / 3 + 1e-6)],
                    ble={})
            for i in range(n)]


def _drive(det, frames, win_s=15.0):
    state = None
    t = frames[0].ts + win_s
    while t <= frames[-1].ts:
        w = [f for f in frames if t - win_s <= f.ts <= t]
        if len(w) >= 8:
            r = det.update(w, LINK_IDS, ts=t)
            if r is not None:
                state = r
        t += 0.5
    return state


def _micro_amp():
    """An amplitude whose window variance lands between KEEP_FACTOR*thr and
    thr (micro-movement: keeps presence, cannot acquire it)."""
    return 1.15  # measured: variance ~0.7-0.8 for these synthetic frames, thr 1.0


def test_micro_movement_alone_cannot_acquire_presence():
    det = RFDetector(_cal())
    state = _drive(det, _frames(400, _micro_amp()))
    assert state["presence"] == 0


def test_micro_movement_keeps_presence_beyond_decay():
    det = RFDetector(_cal())
    strong = _frames(240, 6.0)                                   # 60 s walking
    micro = _frames(1300, _micro_amp(), seed=1,
                    t0=strong[-1].ts + 0.25)                     # 325 s sitting
    assert _drive(det, strong)["presence"] == 1
    state = _drive(det, micro)                                   # > 120 s decay
    assert state["presence"] == 1, "micro-movement should KEEP presence"


def test_dead_quiet_still_releases_presence():
    det = RFDetector(_cal())
    strong = _frames(240, 6.0)
    quiet = _frames(1300, 0.02, seed=2, t0=strong[-1].ts + 0.25)  # truly empty
    _drive(det, strong)
    state = _drive(det, quiet)
    assert state["presence"] == 0, "an actually-empty room must still release"


def test_keep_factor_sane():
    assert 0.3 <= KEEP_FACTOR < 1.0
