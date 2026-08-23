import numpy as np
from aura.frames import RFFrame
from aura.brain.calibrate import calibrate_empty, calibrate_walk
from aura.brain.rfsense.detector import RFDetector, LINK_STREAM

def _frames(n, jitter, seed=0, hz=4.0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        wobble = jitter * np.sin(i / 3.0) + rng.normal(0, jitter / 2 + 1e-6)
        out.append(RFFrame(ts=i / hz,
                           wifi={"aaaaaaaa": -60 + wobble, "bbbbbbbb": -70 + wobble * 0.8},
                           link=[-50 + wobble], ble={}))
    return out

def test_calibration_produces_rv_thresholds_between_populations():
    cal = calibrate_empty(_frames(400, 0.3))
    assert "rv_empty" in cal and "aaaaaaaa" in cal["rv_empty"]
    assert cal["rv_empty"]["aaaaaaaa"]["var_p95"] > 0
    cal = calibrate_walk(_frames(400, 4.0, seed=1), cal)
    rv = cal["rv"]
    for lid in ("aaaaaaaa", "bbbbbbbb", LINK_STREAM):
        assert rv["var_thresh"][lid] > 0
        assert rv["motion_thresh"][lid] > 0
    assert rv["act_ceil"] > rv["act_floor"]

def test_calibrated_detector_separates_empty_from_walk():
    cal = calibrate_empty(_frames(400, 0.3))
    cal = calibrate_walk(_frames(400, 4.0, seed=1), cal)
    r_empty = RFDetector(cal).update(_frames(60, 0.3, seed=2), cal["link_ids"], ts=15.0)
    r_walk = RFDetector(cal).update(_frames(60, 4.0, seed=3), cal["link_ids"], ts=15.0)
    assert r_empty["motion"] == 0
    assert r_walk["motion"] == 1 and r_walk["presence"] == 1
    assert r_walk["activity"] > r_empty["activity"]

def test_existing_calibration_keys_untouched():
    cal = calibrate_empty(_frames(400, 0.3))
    assert set(cal) >= {"link_ids", "empty_p995"}
    cal = calibrate_walk(_frames(400, 4.0, seed=1), cal)
    assert "activity_scale" in cal
