import numpy as np
from aura.brain.ruview.features_rv import RssiFeatureExtractor, cusum_detect

FS = 4.0

def test_too_few_samples_returns_empty():
    f = RssiFeatureExtractor().extract_from_array(np.array([-60.0, -61.0, -60.0]), FS)
    assert f.n_samples == 3 and f.variance == 0.0 and f.n_change_points == 0

def test_motion_band_tone_lands_in_motion_band():
    t = np.arange(60) / FS
    rssi = -60 + 3.0 * np.sin(2 * np.pi * 1.0 * t)  # 1 Hz tone = human-motion band
    f = RssiFeatureExtractor().extract_from_array(rssi, FS)
    assert f.motion_band_power > 10 * max(f.breathing_band_power, 1e-9)
    assert abs(f.dominant_freq_hz - 1.0) < 0.2
    assert f.variance > 1.0

def test_flat_signal_zero_everything():
    f = RssiFeatureExtractor().extract_from_array(np.full(60, -60.0), FS)
    assert f.variance == 0.0
    assert f.total_spectral_power < 1e-9
    assert f.n_change_points == 0

def test_cusum_flags_step():
    rng = np.random.default_rng(0)
    sig = np.concatenate([np.full(30, -60.0), np.full(30, -50.0)]) + rng.normal(0, 0.3, 60)
    f = RssiFeatureExtractor().extract_from_array(sig, FS)
    assert f.n_change_points >= 1

def test_cusum_quiet_signal_no_changes():
    assert cusum_detect(np.zeros(50), 0.0, 3.0, 0.5) == []
