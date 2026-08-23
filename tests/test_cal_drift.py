"""Calibration-drift detection: when the room reads empty but the link RSSI
level sits far from the level recorded at calibration time, the calibration
is stale (the hotspot phone moved) and the detector must say so instead of
going silently blind (2026-08-23: a 19 dB phone move left the link channel
unable to see a person walk in)."""
import numpy as np
from aura.frames import RFFrame
from aura.brain.calibrate import calibrate_empty
from aura.brain.ruview.detector import RuViewDetector, DRIFT_DB, STALE_AFTER_S

LINK_IDS = ["aaaaaaaa", "bbbbbbbb"]


def _quiet_frames(n, link_level, seed=0, hz=4.0, t0=0.0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        wifi = {bid: -60 + rng.normal(0, 0.1) for bid in LINK_IDS}
        link = [link_level + rng.normal(0, 0.1)]
        out.append(RFFrame(ts=t0 + i / hz, wifi=wifi, link=link, ble={}))
    return out


def _noisy_frames(n, link_level, seed=0, hz=4.0, t0=0.0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        wifi = {bid: -60 + 6.0 * np.sin(i / 3.0) + rng.normal(0, 3.0) for bid in LINK_IDS}
        link = [link_level + 6.0 * np.sin(i / 3.0) + rng.normal(0, 3.0)]
        out.append(RFFrame(ts=t0 + i / hz, wifi=wifi, link=link, ble={}))
    return out


def _cal(link_level=-50.0):
    return {
        "link_ids": LINK_IDS,
        "rv": {"var_thresh": {lid: 5.0 for lid in LINK_IDS + ["__link__"]},
               "motion_thresh": {lid: 50.0 for lid in LINK_IDS + ["__link__"]}},
        "rv_empty": {"__link__": {"var_p95": 0.1, "mbp_p95": 0.1,
                                  "rssi_med": link_level}},
    }


def _drive(det, frames, win_s=15.0, step_s=0.5):
    """Slide 15-s windows over frames at the brain's cadence; return last state."""
    state = None
    t = frames[0].ts + win_s
    while t <= frames[-1].ts:
        w = [f for f in frames if t - win_s <= f.ts <= t]
        if len(w) >= 8:
            r = det.update(w, LINK_IDS, ts=t)
            if r is not None:
                state = r
        t += step_s
    return state


def test_calibrate_empty_stores_rssi_median():
    frames = _quiet_frames(160, link_level=-50.0)
    cal = calibrate_empty(frames, k=4)
    assert abs(cal["rv_empty"]["__link__"]["rssi_med"] - (-50.0)) < 1.0


def test_no_drift_at_calibrated_level():
    det = RuViewDetector(_cal(-50.0))
    n = int((STALE_AFTER_S + 40) * 4)
    state = _drive(det, _quiet_frames(n, link_level=-50.0))
    assert state["presence"] == 0
    assert state["cal_stale"] is False


def test_sustained_empty_drift_flags_stale():
    det = RuViewDetector(_cal(-50.0))
    n = int((STALE_AFTER_S + 40) * 4)
    state = _drive(det, _quiet_frames(n, link_level=-50.0 + DRIFT_DB + 12))
    assert state["presence"] == 0
    assert state["cal_stale"] is True


def test_drift_clears_when_level_returns():
    det = RuViewDetector(_cal(-50.0))
    n = int((STALE_AFTER_S + 40) * 4)
    shifted = _quiet_frames(n, link_level=-30.0)
    assert _drive(det, shifted)["cal_stale"] is True
    back = _quiet_frames(160, link_level=-50.0, t0=shifted[-1].ts + 0.25)
    assert _drive(det, back)["cal_stale"] is False


def test_presence_freezes_drift_clock():
    """A person shadowing the link can shift its level; occupied windows must
    neither accumulate toward stale nor clear an existing verdict."""
    det = RuViewDetector(_cal(-50.0))
    n = int((STALE_AFTER_S + 60) * 4)
    state = _drive(det, _noisy_frames(n, link_level=-30.0))
    assert state["presence"] == 1
    assert state["cal_stale"] is False
