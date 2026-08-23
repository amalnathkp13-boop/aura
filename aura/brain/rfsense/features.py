"""RSSI feature extraction, ported from an MIT-licensed upstream project.
Full attribution, pinned upstream commit, and license text: NOTICE.md.
Upstream file: archive/v1/src/sensing/feature_extractor.py
Local changes (see NOTICE.md): numpy-only (scipy.fft -> np.fft; skewness/kurtosis
dropped - never read by the classifier); WifiSample/window-trim path removed - Aura's
brain owns windowing and calls extract_from_array() directly.
"""
from dataclasses import dataclass, field
from typing import List

import numpy as np


@dataclass
class RssiFeatures:
    mean: float = 0.0
    variance: float = 0.0
    std: float = 0.0
    range: float = 0.0
    iqr: float = 0.0
    dominant_freq_hz: float = 0.0
    breathing_band_power: float = 0.0   # 0.1 - 0.5 Hz
    motion_band_power: float = 0.0      # 0.5 - 3.0 Hz
    total_spectral_power: float = 0.0
    change_points: List[int] = field(default_factory=list)
    n_change_points: int = 0
    n_samples: int = 0
    duration_seconds: float = 0.0
    sample_rate_hz: float = 0.0


def _band_power(freqs, psd, low_hz, high_hz):
    mask = (freqs >= low_hz) & (freqs <= high_hz)
    return float(np.sum(psd[mask]))


def cusum_detect(signal, target, threshold, drift):
    """CUSUM change-point detection (both directions), verbatim from upstream."""
    s_pos = s_neg = 0.0
    change_points = []
    for i in range(len(signal)):
        deviation = signal[i] - target
        s_pos = max(0.0, s_pos + deviation - drift)
        s_neg = max(0.0, s_neg - deviation - drift)
        if s_pos > threshold or s_neg > threshold:
            change_points.append(i)
            s_pos = s_neg = 0.0
    return change_points


class RssiFeatureExtractor:
    def __init__(self, cusum_threshold: float = 3.0, cusum_drift: float = 0.5):
        self._cusum_threshold = cusum_threshold
        self._cusum_drift = cusum_drift

    def extract_from_array(self, rssi, sample_rate_hz: float) -> RssiFeatures:
        rssi = np.asarray(rssi, dtype=np.float64)
        if len(rssi) < 4:
            return RssiFeatures(n_samples=len(rssi))
        f = RssiFeatures(n_samples=len(rssi),
                         duration_seconds=float(len(rssi) / sample_rate_hz),
                         sample_rate_hz=float(sample_rate_hz))
        self._time_domain(rssi, f)
        self._frequency_domain(rssi, sample_rate_hz, f)
        self._change_points(rssi, f)
        return f

    @staticmethod
    def _time_domain(rssi, f):
        f.mean = float(np.mean(rssi))
        f.variance = float(np.var(rssi, ddof=1))
        f.std = float(np.std(rssi, ddof=1))
        f.range = float(np.ptp(rssi))
        q75, q25 = np.percentile(rssi, [75, 25])
        f.iqr = float(q75 - q25)

    @staticmethod
    def _frequency_domain(rssi, sample_rate, f):
        n = len(rssi)
        signal = rssi - np.mean(rssi)
        windowed = signal * np.hanning(n)   # Hann window against spectral leakage
        fft_vals = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
        psd = (np.abs(fft_vals) ** 2) / n
        if len(freqs) <= 1:
            return
        freqs, psd = freqs[1:], psd[1:]     # drop DC
        f.total_spectral_power = float(np.sum(psd))
        f.dominant_freq_hz = float(freqs[int(np.argmax(psd))])
        f.breathing_band_power = _band_power(freqs, psd, 0.1, 0.5)
        f.motion_band_power = _band_power(freqs, psd, 0.5, 3.0)

    def _change_points(self, rssi, f):
        std_val = np.std(rssi, ddof=1)
        if std_val < 1e-12:
            return
        cps = cusum_detect(rssi, float(np.mean(rssi)),
                           self._cusum_threshold * std_val,
                           self._cusum_drift * std_val)
        f.change_points = cps
        f.n_change_points = len(cps)
