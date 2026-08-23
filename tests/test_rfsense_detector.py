import numpy as np
from aura.frames import RFFrame
from aura.brain.rfsense.detector import RFDetector, raw_series, LINK_STREAM

def _frames(n, jitters, link_jitter=0.0, seed=0, hz=4.0, t0=0.0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        wifi = {bid: -60 + j * np.sin(i / 3.0) + rng.normal(0, j / 2 + 1e-6)
                for bid, j in jitters.items()}
        link = [-50 + link_jitter * np.sin(i / 3.0) + rng.normal(0, link_jitter / 2 + 1e-6)]
        out.append(RFFrame(ts=t0 + i / hz, wifi=wifi, link=link, ble={}))
    return out

def test_raw_series_forward_fills_and_weights():
    frames = _frames(20, {"aaaaaaaa": 1.0})
    for i in range(0, 20, 2):          # link visible only every other frame
        del frames[i].wifi["aaaaaaaa"]
    series, w = raw_series(frames, "aaaaaaaa")
    assert len(series) == 19           # starts at first real reading (frame 1)
    assert abs(w - 0.5) < 0.01

def test_quiet_room_absent():
    det = RFDetector(None)
    r = det.update(_frames(60, {"aaaaaaaa": 0.05, "bbbbbbbb": 0.05}, link_jitter=0.05),
                   ["aaaaaaaa", "bbbbbbbb"], ts=15.0)
    assert r["presence"] == 0 and r["motion"] == 0

def test_moving_person_detected():
    det = RFDetector(None)
    r = det.update(_frames(60, {"aaaaaaaa": 4.0, "bbbbbbbb": 4.0}, link_jitter=4.0, seed=1),
                   ["aaaaaaaa", "bbbbbbbb"], ts=15.0)
    assert r["presence"] == 1 and r["motion"] == 1
    assert r["activity"] > 0 and 0.0 <= r["confidence"] <= 1.0

def test_single_noisy_link_outvoted():
    det = RFDetector(None)
    r = det.update(_frames(60, {"aaaaaaaa": 0.05, "bbbbbbbb": 0.05, "cccccccc": 4.0},
                           link_jitter=0.05, seed=2),
                   ["aaaaaaaa", "bbbbbbbb", "cccccccc"], ts=15.0)
    assert r["presence"] == 0 and r["motion"] == 0

def test_flat_channel_ignored_not_counted_as_absent_vote():
    # one live moving wifi link + a perfectly constant link stream: the dead-flat
    # channel carries no information and must not outvote the live one.
    det = RFDetector(None)
    frames = _frames(60, {"aaaaaaaa": 4.0}, link_jitter=0.0, seed=3)
    for f in frames:
        f.link = [-50.0]               # exactly constant
    r = det.update(frames, ["aaaaaaaa"], ts=15.0)
    assert r["presence"] == 1 and r["motion"] == 1

def test_presence_decays_after_motion_stops():
    det = RFDetector(None)
    moving = _frames(60, {"aaaaaaaa": 4.0}, link_jitter=4.0, seed=1)
    quiet = _frames(60, {"aaaaaaaa": 0.05}, link_jitter=0.05, t0=30.0)
    assert det.update(moving, ["aaaaaaaa"], ts=15.0)["motion"] == 1
    r_soon = det.update(quiet, ["aaaaaaaa"], ts=45.0)
    assert r_soon["motion"] == 0 and r_soon["presence"] == 1   # within 120 s decay
    r_late = det.update(quiet, ["aaaaaaaa"], ts=200.0)
    assert r_late["presence"] == 0                             # decay expired

def test_no_usable_channels_returns_none():
    det = RFDetector(None)
    frames = [RFFrame(ts=i / 4.0, wifi={}, link=[], ble={}) for i in range(60)]
    assert det.update(frames, [], ts=15.0) is None
    assert det.last_detail is None


def test_update_populates_last_detail():
    det = RFDetector(None)
    frames = _frames(60, {"aaaaaaaa": 4.0, "bbbbbbbb": 0.05}, link_jitter=4.0, seed=1)
    det.update(frames, ["aaaaaaaa", "bbbbbbbb"], ts=15.0)
    d = det.last_detail
    assert {l["id"] for l in d["links"]} == {"aaaaaaaa", "bbbbbbbb", LINK_STREAM}
    for l in d["links"]:
        assert set(l) == {"id", "rssi", "variance", "var_thresh", "band_energy",
                          "motion_thresh", "vote", "confidence", "weight", "change_points"}
        assert l["vote"] in ("absent", "present_still", "active")
        assert 0.0 <= l["confidence"] <= 1.0
    assert 0.0 <= d["present_frac"] <= 1.0 and 0.0 <= d["active_frac"] <= 1.0
    assert d["fused_band_energy"] >= 0.0 and d["fused_breathing_energy"] >= 0.0
