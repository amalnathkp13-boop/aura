import numpy as np
from aura.frames import RFFrame
from aura.brain.features import select_links, build_matrix, summary

def _frames(n, jitter, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        wobble = jitter * np.sin(i / 3.0) + rng.normal(0, jitter / 2)
        out.append(RFFrame(ts=i * 0.25,
                           wifi={"aaaaaaaa": -60 + wobble, "bbbbbbbb": -70 + wobble * 0.8},
                           link=[-50 + wobble], ble={}))
    return out

def test_select_links_ranks_by_presence():
    frames = _frames(10, 0)
    frames[0].wifi["cccccccc"] = -80.0  # seen once
    ids = select_links(frames, k=2)
    assert ids == ["aaaaaaaa", "bbbbbbbb"]

def test_build_matrix_shape_and_norm():
    m = build_matrix(_frames(60, 1.0), ["aaaaaaaa", "bbbbbbbb"], out_len=60)
    assert m.shape == (3, 60) and m.dtype == np.float32
    assert np.all(np.abs(m) <= 4.0)
    assert abs(np.median(m[0])) < 0.1  # centered

def test_build_matrix_handles_missing_link(tmp_path):
    frames = _frames(60, 1.0)
    m = build_matrix(frames, ["aaaaaaaa", "not_seen1"], out_len=60)
    assert m.shape == (3, 60)
    assert np.all(m[1] == 0)  # absent link -> zeros

def test_summary_separates_still_from_moving():
    still = summary(build_matrix(_frames(60, 0.3), ["aaaaaaaa", "bbbbbbbb"]))
    moving = summary(build_matrix(_frames(60, 4.0, seed=1), ["aaaaaaaa", "bbbbbbbb"]))
    assert moving["motion_energy"] > 2 * still["motion_energy"]
    assert 0 <= still["band_energy"] <= 1

def test_xcorr_ignores_dead_channels():
    rng = np.random.default_rng(3)
    sig = rng.normal(0, 1, 60)
    m = np.stack([sig, sig, np.zeros(60)]).astype(np.float32)
    s = summary(m)
    assert s["xcorr"] > 0.9  # two identical live channels; dead row must not zero the metric

def test_band_energy_high_for_in_band_tone():
    t = np.arange(60) / 4.0  # fs = 4 Hz
    tone = np.sin(2 * np.pi * 1.0 * t)  # 1 Hz, inside 0.5-2.0 Hz effective band
    m = np.stack([tone, tone]).astype(np.float32)
    assert summary(m)["band_energy"] > 0.8
