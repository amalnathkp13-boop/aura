import numpy as np, pytest
from aura.frames import RFFrame
from aura.brain.calibrate import calibrate_empty, calibrate_walk
from aura.brain.baseline import Baseline

def _frames(n, jitter, seed=0):
    rng = np.random.default_rng(seed)
    return [RFFrame(ts=i * 0.25, wifi={"aaaaaaaa": -60 + jitter * np.sin(i / 3) + rng.normal(0, jitter / 2),
                                       "bbbbbbbb": -70 + rng.normal(0, jitter / 2)},
                    link=[-50.0], ble={}) for i in range(n)]

def test_calibration_flow():
    cal = calibrate_empty(_frames(400, 0.3))          # ~100 s of empty
    assert len(cal["link_ids"]) == 2 and cal["empty_p995"] > 0
    cal = calibrate_walk(_frames(400, 4.0, seed=1), cal)
    assert cal["activity_scale"] > cal["empty_p995"]

def test_calibrate_walk_rejects_no_separation():
    cal = calibrate_empty(_frames(400, 0.3))
    with pytest.raises(ValueError):
        calibrate_walk(_frames(400, 0.3, seed=2), cal)

def test_baseline_state_machine():
    cal = {"link_ids": ["aaaaaaaa", "bbbbbbbb"], "empty_p995": 0.1, "activity_scale": 1.0}
    b = Baseline(cal)
    s = b.update({"motion_energy": 0.5, "band_energy": 0.2, "xcorr": 0.3}, ts=100.0)
    assert s == {"presence": 1, "motion": 1, "activity": 50.0}
    s = b.update({"motion_energy": 0.01, "band_energy": 0.0, "xcorr": 0.0}, ts=150.0)
    assert s["motion"] == 0 and s["presence"] == 1      # latched
    s = b.update({"motion_energy": 0.01, "band_energy": 0.0, "xcorr": 0.0}, ts=100.0 + 130)
    assert s["presence"] == 0                            # decayed after 120s
