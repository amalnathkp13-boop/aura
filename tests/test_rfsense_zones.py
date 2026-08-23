import numpy as np
import pytest
from aura.frames import RFFrame
from aura.brain.calibrate import calibrate_zone
from aura.brain.rfsense.detector import RFDetector

LINK_IDS = ["aaaaaaaa", "bbbbbbbb"]


def _frames(n, jitters, link_jitter=0.0, seed=0, hz=4.0, t0=0.0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        wifi = {bid: -60 + j * np.sin(i / 3.0) + rng.normal(0, j / 2 + 1e-6)
                for bid, j in jitters.items()}
        link = [-50 + link_jitter * np.sin(i / 3.0) + rng.normal(0, link_jitter / 2 + 1e-6)]
        out.append(RFFrame(ts=t0 + i / hz, wifi=wifi, link=link, ble={}))
    return out


# Two zones with opposite disturbance RATIOS. A person anywhere in the room
# bends every path somewhat (so the fusion vote still reaches motion=1); the
# zone information is in which path is bent hardest.
def _corridor_frames(seed=0, t0=0.0):
    return _frames(160, {"aaaaaaaa": 2.5, "bbbbbbbb": 2.5}, link_jitter=8.0, seed=seed, t0=t0)


def _window_frames(seed=0, t0=0.0):
    return _frames(160, {"aaaaaaaa": 8.0, "bbbbbbbb": 8.0}, link_jitter=2.5, seed=seed, t0=t0)


def _cal_with_zones():
    cal = {"link_ids": LINK_IDS}
    cal = calibrate_zone(_corridor_frames(seed=1), cal, "corridor")
    cal = calibrate_zone(_window_frames(seed=2), cal, "window")
    return cal


def test_calibrate_zone_builds_signature():
    cal = calibrate_zone(_corridor_frames(), {"link_ids": LINK_IDS}, "corridor")
    sig = cal["zones"]["corridor"]
    assert "__link__" in sig and set(sig["__link__"]) == {"var", "mbp"}
    # the link stream is the disturbed one in this zone
    assert sig["__link__"]["var"] > sig["aaaaaaaa"]["var"]


def test_calibrate_zone_appends_not_replaces():
    cal = _cal_with_zones()
    assert set(cal["zones"]) == {"corridor", "window"}


def test_calibrate_zone_rejects_empty_capture():
    with pytest.raises(ValueError):
        calibrate_zone([], {"link_ids": LINK_IDS}, "nowhere")


def test_zone_matched_on_motion():
    det = RFDetector(_cal_with_zones())
    r = det.update(_corridor_frames(seed=3)[-60:], LINK_IDS, ts=15.0)
    assert r["motion"] == 1
    assert r["zone"] == "corridor"
    assert det.last_detail["zone"] == "corridor"
    r2 = det.update(_window_frames(seed=4)[-60:], LINK_IDS, ts=30.0)
    assert r2["zone"] == "window"


def test_zone_sticky_while_still_then_cleared():
    det = RFDetector(_cal_with_zones())
    det.update(_corridor_frames(seed=5)[-60:], LINK_IDS, ts=15.0)
    # quiet window: still present (decay), no motion -> zone label sticks
    quiet = _frames(60, {"aaaaaaaa": 0.05, "bbbbbbbb": 0.05}, link_jitter=0.05, seed=6)
    r = det.update(quiet, LINK_IDS, ts=30.0)
    assert r["presence"] == 1 and r["motion"] == 0
    assert r["zone"] == "corridor"
    # long after decay: absent -> zone cleared
    r2 = det.update(quiet, LINK_IDS, ts=500.0)
    assert r2["presence"] == 0
    assert r2["zone"] is None


def test_no_zones_means_no_zone_key():
    det = RFDetector(None)
    r = det.update(_corridor_frames(seed=7)[-60:], LINK_IDS, ts=15.0)
    assert "zone" not in r
