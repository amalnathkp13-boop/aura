# RuView No-Training Detector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the CNN-training requirement with a deterministic detector ported from RuView (MIT), fused across Aura's multi-link RF frames, selectable via `detector: ruview | baseline | cnn` (default `ruview`).

**Architecture:** New package `aura/brain/ruview/` holds a numpy-only port of RuView's `RssiFeatureExtractor` + `PresenceClassifier` plus a multi-link fusion detector. `brain.py` dispatches on a new `Config.detector` field; the `state.json` contract is unchanged for baseline/cnn and gains a `confidence` key on the ruview path. Calibration (`calibrate_empty`/`calibrate_walk`) additionally derives per-link RuView thresholds. A PC-side `training/validate.py` computes the metrics table from a recorded session + declared truth timeline.

**Tech Stack:** Python 3.9+, numpy only (no scipy — deliberate), pytest, existing Aura frame/window machinery.

**Spec:** `docs/superpowers/specs/2026-08-19-ruview-detector-design.md`

## Global Constraints

- Arduino UNO Q only — no ESP32, no CSI, no new hardware, no new Python dependencies (numpy/flask/requests stay the whole core set).
- Upstream provenance is pinned: `github.com/ruvnet/RuView` commit `81cc241b9ebf8ccfb7cffd8e2e086e16c81f8a22`, files `archive/v1/src/sensing/feature_extractor.py` and `classifier.py`, MIT license. `NOTICE.md` must record this and all local modifications.
- `state.json` schema for baseline/cnn paths must not change: `{ts, presence, motion, activity, src}`. The ruview path adds exactly one key: `confidence`.
- Default detector is `ruview`; auto-mode (no `calibration.json`) must work with upstream default thresholds (variance 0.5 dBm², motion-band 0.1).
- TDD: every task = failing test → implement → pass → commit. Run tests with `.venv\Scripts\python -m pytest <file> -v` from `C:\Users\ASUS\aura` (PowerShell) — plain `pytest` also works inside the venv.
- Board deploy only via `sh deploy/push.sh arduino@192.168.63.60`; ssh commands end with `< /dev/null`; never store the board password anywhere.
- Windows note: `git add` explicit paths (repo convention), commit after every task.

---

### Task 1: Port `features_rv.py` (RuView feature extractor, numpy-only) + NOTICE.md

**Files:**
- Create: `aura/brain/ruview/__init__.py` (empty)
- Create: `aura/brain/ruview/features_rv.py`
- Create: `NOTICE.md` (repo root)
- Test: `tests/test_ruview_features.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `RssiFeatures` dataclass (fields: `mean, variance, std, range, iqr, dominant_freq_hz, breathing_band_power, motion_band_power, total_spectral_power, change_points, n_change_points, n_samples, duration_seconds, sample_rate_hz`); `RssiFeatureExtractor(cusum_threshold=3.0, cusum_drift=0.5)` with `.extract_from_array(rssi: np.ndarray, sample_rate_hz: float) -> RssiFeatures`; `cusum_detect(signal, target, threshold, drift) -> list[int]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ruview_features.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_ruview_features.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aura.brain.ruview'`

- [ ] **Step 3: Write the implementation**

Create empty `aura/brain/ruview/__init__.py`, then:

```python
# aura/brain/ruview/features_rv.py
"""RSSI feature extraction, ported from RuView (MIT).

Upstream: https://github.com/ruvnet/RuView @ 81cc241b9ebf8ccfb7cffd8e2e086e16c81f8a22
File: archive/v1/src/sensing/feature_extractor.py
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
```

And the attribution file:

```markdown
# NOTICE

## RuView (MIT)

`aura/brain/ruview/features_rv.py` and `aura/brain/ruview/classifier_rv.py` are ports of
code from the RuView project:

- Repository: https://github.com/ruvnet/RuView
- Commit: 81cc241b9ebf8ccfb7cffd8e2e086e16c81f8a22 (2026-04-26)
- Files: archive/v1/src/sensing/feature_extractor.py, archive/v1/src/sensing/classifier.py
- License: MIT

Local modifications:
- numpy-only: `scipy.fft` replaced with `np.fft` (identical rFFT math); skewness/kurtosis
  removed (never read by the classifier); `scipy.stats` dependency removed.
- The `WifiSample`-based `extract()` path and window trimming were removed — Aura's brain
  owns windowing and feeds plain arrays via `extract_from_array()`.
- Logging and upstream package imports removed.
- `classifier.py` rules and confidence model kept verbatim; per-link thresholds are
  injected by Aura's calibration; multi-link fusion around it is Aura-original.
- Upstream's `rssi_collector.py` is NOT used — Aura's ear daemon owns all radio access.

MIT License

Copyright (c) RuView contributors (https://github.com/ruvnet/RuView)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_ruview_features.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add aura/brain/ruview/__init__.py aura/brain/ruview/features_rv.py NOTICE.md tests/test_ruview_features.py
git commit -m "feat: port RuView RSSI feature extractor (numpy-only) + NOTICE"
```

---

### Task 2: Port `classifier_rv.py` (rule-based presence/motion classifier)

**Files:**
- Create: `aura/brain/ruview/classifier_rv.py`
- Test: `tests/test_ruview_classifier.py`

**Interfaces:**
- Consumes: `RssiFeatures` from `aura.brain.ruview.features_rv` (Task 1).
- Produces: `MotionLevel` enum (`ABSENT`, `PRESENT_STILL`, `ACTIVE`); `SensingResult` dataclass (`motion_level, confidence, presence_detected, rssi_variance, motion_band_energy, breathing_band_energy, n_change_points, details`); `PresenceClassifier(presence_variance_threshold=0.5, motion_energy_threshold=0.1)` with `.classify(features, other_receiver_results=None) -> SensingResult`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ruview_classifier.py
from aura.brain.ruview.classifier_rv import PresenceClassifier, MotionLevel
from aura.brain.ruview.features_rv import RssiFeatures

def _feat(variance, motion=0.0, breathing=0.0, cps=0):
    return RssiFeatures(variance=variance, motion_band_power=motion,
                        breathing_band_power=breathing, n_change_points=cps)

def test_absent_below_variance_threshold():
    r = PresenceClassifier(0.5, 0.1).classify(_feat(0.1))
    assert r.motion_level == MotionLevel.ABSENT and not r.presence_detected

def test_active_needs_variance_and_motion_energy():
    r = PresenceClassifier(0.5, 0.1).classify(_feat(2.0, motion=0.5))
    assert r.motion_level == MotionLevel.ACTIVE and r.presence_detected

def test_present_still_high_variance_low_motion():
    r = PresenceClassifier(0.5, 0.1).classify(_feat(2.0, motion=0.01, breathing=0.2))
    assert r.motion_level == MotionLevel.PRESENT_STILL and r.presence_detected

def test_confidence_unit_interval_and_agreement():
    clf = PresenceClassifier(0.5, 0.1)
    alone = clf.classify(_feat(2.0, motion=0.5))
    peer = clf.classify(_feat(1.5, motion=0.4))
    agreed = clf.classify(_feat(2.0, motion=0.5), other_receiver_results=[peer])
    disagreed = clf.classify(_feat(2.0, motion=0.5),
                             other_receiver_results=[clf.classify(_feat(0.0))])
    assert 0.0 <= alone.confidence <= 1.0
    assert agreed.confidence >= disagreed.confidence
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_ruview_classifier.py -v`
Expected: FAIL — `ModuleNotFoundError` on `classifier_rv`

- [ ] **Step 3: Write the implementation**

```python
# aura/brain/ruview/classifier_rv.py
"""Rule-based presence/motion classifier, ported from RuView (MIT).

Upstream: https://github.com/ruvnet/RuView @ 81cc241b9ebf8ccfb7cffd8e2e086e16c81f8a22
File: archive/v1/src/sensing/classifier.py
Rules and 60/20/20 confidence model kept verbatim; import paths and logging removed
(see NOTICE.md). Per-link thresholds are injected by Aura's calibration.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from aura.brain.ruview.features_rv import RssiFeatures


class MotionLevel(Enum):
    ABSENT = "absent"
    PRESENT_STILL = "present_still"
    ACTIVE = "active"


@dataclass
class SensingResult:
    motion_level: MotionLevel
    confidence: float                 # 0.0 to 1.0
    presence_detected: bool
    rssi_variance: float
    motion_band_energy: float
    breathing_band_energy: float
    n_change_points: int
    details: str = ""


class PresenceClassifier:
    """Presence: variance >= threshold. ACTIVE: motion-band energy >= threshold.
    Otherwise PRESENT_STILL. Confidence = 0.6*base + 0.2*spectral + 0.2*agreement."""

    def __init__(self, presence_variance_threshold: float = 0.5,
                 motion_energy_threshold: float = 0.1):
        self._var_thresh = presence_variance_threshold
        self._motion_thresh = motion_energy_threshold

    def classify(self, features: RssiFeatures,
                 other_receiver_results: Optional[List[SensingResult]] = None) -> SensingResult:
        variance = features.variance
        motion_energy = features.motion_band_power
        breathing_energy = features.breathing_band_power

        presence = variance >= self._var_thresh
        if not presence:
            level = MotionLevel.ABSENT
        elif motion_energy >= self._motion_thresh:
            level = MotionLevel.ACTIVE
        else:
            level = MotionLevel.PRESENT_STILL

        confidence = self._confidence(variance, motion_energy, breathing_energy,
                                      level, other_receiver_results)
        details = (f"var={variance:.4f} (thresh={self._var_thresh}), "
                   f"motion_energy={motion_energy:.4f} (thresh={self._motion_thresh}), "
                   f"breathing_energy={breathing_energy:.4f}, "
                   f"change_points={features.n_change_points}")
        return SensingResult(motion_level=level, confidence=confidence,
                             presence_detected=presence, rssi_variance=variance,
                             motion_band_energy=motion_energy,
                             breathing_band_energy=breathing_energy,
                             n_change_points=features.n_change_points, details=details)

    def _confidence(self, variance, motion_energy, breathing_energy, level, other_results):
        if level == MotionLevel.ABSENT:
            base = max(0.0, 1.0 - variance / self._var_thresh) if self._var_thresh > 0 else 1.0
        else:
            base = min(1.0, variance / self._var_thresh) if self._var_thresh > 0 else 1.0

        if level == MotionLevel.ACTIVE:
            spectral = min(1.0, motion_energy / max(self._motion_thresh, 1e-12))
        elif level == MotionLevel.PRESENT_STILL:
            spectral = min(1.0, breathing_energy / max(self._motion_thresh, 1e-12))
        else:
            spectral = 1.0

        agreement = 1.0
        if other_results:
            same = sum(1 for r in other_results if r.motion_level == level)
            agreement = (same + 1) / (len(other_results) + 1)

        return max(0.0, min(1.0, 0.6 * base + 0.2 * spectral + 0.2 * agreement))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_ruview_classifier.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add aura/brain/ruview/classifier_rv.py tests/test_ruview_classifier.py
git commit -m "feat: port RuView rule-based presence classifier"
```

---

### Task 3: `detector.py` — raw series extraction + multi-link fusion detector

**Files:**
- Create: `aura/brain/ruview/detector.py`
- Test: `tests/test_ruview_detector.py`

**Interfaces:**
- Consumes: `RssiFeatureExtractor` (Task 1), `PresenceClassifier`/`MotionLevel` (Task 2), `RFFrame` (existing `aura/frames.py`: fields `ts, wifi: dict, link: list, ble: dict`).
- Produces: constant `LINK_STREAM = "__link__"`; `raw_series(frames, link_id) -> (np.ndarray, weight: float)` (forward-filled dBm series starting at first reading; weight = fraction of frames with a real reading); `RuViewDetector(cal: dict | None)` with `.update(frames, link_ids, ts: float, frame_hz: float = 4.0) -> dict | None` returning `{"presence": int, "motion": int, "activity": float, "confidence": float}` or `None` when no usable channel. Constants `PRESENCE_DECAY_S = 120.0`, `AUTO_VAR_THRESH = 0.5`, `AUTO_MOTION_THRESH = 0.1`, `AUTO_ACT_FLOOR = 0.05`, `AUTO_ACT_CEIL = 2.0`. Reads calibration dict key `"rv"`: `{"var_thresh": {link: v}, "motion_thresh": {link: v}, "act_floor": f, "act_ceil": c}` (produced by Task 4).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ruview_detector.py
import numpy as np
from aura.frames import RFFrame
from aura.brain.ruview.detector import RuViewDetector, raw_series, LINK_STREAM

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
    det = RuViewDetector(None)
    r = det.update(_frames(60, {"aaaaaaaa": 0.05, "bbbbbbbb": 0.05}, link_jitter=0.05),
                   ["aaaaaaaa", "bbbbbbbb"], ts=15.0)
    assert r["presence"] == 0 and r["motion"] == 0

def test_moving_person_detected():
    det = RuViewDetector(None)
    r = det.update(_frames(60, {"aaaaaaaa": 4.0, "bbbbbbbb": 4.0}, link_jitter=4.0, seed=1),
                   ["aaaaaaaa", "bbbbbbbb"], ts=15.0)
    assert r["presence"] == 1 and r["motion"] == 1
    assert r["activity"] > 0 and 0.0 <= r["confidence"] <= 1.0

def test_single_noisy_link_outvoted():
    det = RuViewDetector(None)
    r = det.update(_frames(60, {"aaaaaaaa": 0.05, "bbbbbbbb": 0.05, "cccccccc": 4.0},
                           link_jitter=0.05, seed=2),
                   ["aaaaaaaa", "bbbbbbbb", "cccccccc"], ts=15.0)
    assert r["presence"] == 0 and r["motion"] == 0

def test_flat_channel_ignored_not_counted_as_absent_vote():
    # one live moving wifi link + a perfectly constant link stream: the dead-flat
    # channel carries no information and must not outvote the live one.
    det = RuViewDetector(None)
    frames = _frames(60, {"aaaaaaaa": 4.0}, link_jitter=0.0, seed=3)
    for f in frames:
        f.link = [-50.0]               # exactly constant
    r = det.update(frames, ["aaaaaaaa"], ts=15.0)
    assert r["presence"] == 1 and r["motion"] == 1

def test_presence_decays_after_motion_stops():
    det = RuViewDetector(None)
    moving = _frames(60, {"aaaaaaaa": 4.0}, link_jitter=4.0, seed=1)
    quiet = _frames(60, {"aaaaaaaa": 0.05}, link_jitter=0.05, t0=30.0)
    assert det.update(moving, ["aaaaaaaa"], ts=15.0)["motion"] == 1
    r_soon = det.update(quiet, ["aaaaaaaa"], ts=45.0)
    assert r_soon["motion"] == 0 and r_soon["presence"] == 1   # within 120 s decay
    r_late = det.update(quiet, ["aaaaaaaa"], ts=200.0)
    assert r_late["presence"] == 0                             # decay expired

def test_no_usable_channels_returns_none():
    det = RuViewDetector(None)
    frames = [RFFrame(ts=i / 4.0, wifi={}, link=[], ble={}) for i in range(60)]
    assert det.update(frames, [], ts=15.0) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_ruview_detector.py -v`
Expected: FAIL — `ImportError` on `detector`

- [ ] **Step 3: Write the implementation**

```python
# aura/brain/ruview/detector.py
"""Multi-link fusion around the ported RuView classifier (Aura-original).

Each WiFi link (plus the connected-link stream) is treated as one RuView
"receiver": features are extracted per link, each link is classified with the
other links passed as other_receiver_results (upstream's own cross-receiver
agreement), and the final decision is a stability-weighted vote. A single noisy
link cannot outvote several quiet ones; a dead-flat channel is skipped entirely.
"""
import numpy as np

from aura.brain.ruview.features_rv import RssiFeatureExtractor
from aura.brain.ruview.classifier_rv import MotionLevel, PresenceClassifier

LINK_STREAM = "__link__"
PRESENCE_DECAY_S = 120.0     # mirrors Baseline.PRESENCE_DECAY_S
MIN_SAMPLES = 4              # upstream guard
AUTO_VAR_THRESH = 0.5        # upstream defaults, used until calibration runs
AUTO_MOTION_THRESH = 0.1
AUTO_ACT_FLOOR = 0.05
AUTO_ACT_CEIL = 2.0


def raw_series(frames, link_id):
    """Raw dBm series for one channel: starts at the first real reading,
    forward-fills gaps. Returns (series, weight) where weight is the fraction
    of frames carrying a real reading (0 -> channel unusable)."""
    vals, last, seen = [], None, 0
    for f in frames:
        if link_id == LINK_STREAM:
            if f.link:
                last = float(np.mean(f.link))
                seen += 1
        elif link_id in f.wifi:
            last = float(f.wifi[link_id])
            seen += 1
        if last is not None:
            vals.append(last)
    return np.array(vals, dtype=np.float64), seen / max(1, len(frames))


class RuViewDetector:
    def __init__(self, cal=None):
        rv = (cal or {}).get("rv") or {}
        self.var_thresh = rv.get("var_thresh") or {}
        self.motion_thresh = rv.get("motion_thresh") or {}
        self.act_floor = rv.get("act_floor", AUTO_ACT_FLOOR)
        self.act_ceil = rv.get("act_ceil", AUTO_ACT_CEIL)
        self._extractor = RssiFeatureExtractor()
        self._last_motion_ts = None

    def update(self, frames, link_ids, ts, frame_hz=4.0):
        if len(frames) >= 2 and frames[-1].ts > frames[0].ts:
            rate = (len(frames) - 1) / (frames[-1].ts - frames[0].ts)
        else:
            rate = frame_hz

        channels, weights = [], []
        for lid in list(link_ids) + [LINK_STREAM]:
            series, w = raw_series(frames, lid)
            if len(series) < MIN_SAMPLES or w <= 0 or float(np.std(series)) < 1e-9:
                continue   # missing or dead-flat channel: no information, no vote
            feats = self._extractor.extract_from_array(series, rate)
            clf = PresenceClassifier(
                presence_variance_threshold=self.var_thresh.get(lid, AUTO_VAR_THRESH),
                motion_energy_threshold=self.motion_thresh.get(lid, AUTO_MOTION_THRESH))
            channels.append((clf, feats))
            weights.append(w)
        if not channels:
            return None

        prelim = [clf.classify(feats) for clf, feats in channels]
        sensing = [clf.classify(feats,
                                other_receiver_results=[r for j, r in enumerate(prelim) if j != i])
                   for i, (clf, feats) in enumerate(channels)]

        wsum = float(sum(weights))
        present_frac = sum(w for w, r in zip(weights, sensing) if r.presence_detected) / wsum
        active_frac = sum(w for w, r in zip(weights, sensing)
                          if r.motion_level == MotionLevel.ACTIVE) / wsum
        motion = int(active_frac > 0.5)
        if motion:
            self._last_motion_ts = ts
        presence = int(present_frac > 0.5
                       or (self._last_motion_ts is not None
                           and ts - self._last_motion_ts <= PRESENCE_DECAY_S))

        fused_mbp = sum(w * r.motion_band_energy for w, r in zip(weights, sensing)) / wsum
        confidence = sum(w * r.confidence for w, r in zip(weights, sensing)) / wsum
        return {"presence": presence, "motion": motion,
                "activity": round(self._activity(fused_mbp), 1),
                "confidence": round(float(confidence), 3)}

    def _activity(self, energy):
        lo, hi = self.act_floor, self.act_ceil
        if hi <= lo:
            return min(100.0, 100.0 * energy / max(hi, 1e-9))
        x = (np.log(energy + 1e-9) - np.log(lo + 1e-9)) / (np.log(hi + 1e-9) - np.log(lo + 1e-9))
        return float(100.0 * min(1.0, max(0.0, x)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_ruview_detector.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add aura/brain/ruview/detector.py tests/test_ruview_detector.py
git commit -m "feat: RuView multi-link fusion detector (link-as-receiver voting)"
```

---

### Task 4: Calibration derives per-link RuView thresholds

**Files:**
- Modify: `aura/brain/calibrate.py` (whole file shown below)
- Test: `tests/test_ruview_calibrate.py`

**Interfaces:**
- Consumes: `RssiFeatureExtractor` (Task 1); `raw_series`, `LINK_STREAM`, `RuViewDetector`, `AUTO_ACT_FLOOR`, `AUTO_ACT_CEIL` (Task 3); existing `select_links/build_matrix/summary`.
- Produces: `calibrate_empty(frames, k=16)` now ALSO writes `cal["rv_empty"]` (`{link: {"var_p95": v, "mbp_p95": m}}`) and `cal["rv_act_floor"]`; `calibrate_walk(frames, cal)` now ALSO writes `cal["rv"] = {"var_thresh", "motion_thresh", "act_floor", "act_ceil"}` — the exact dict `RuViewDetector` reads. Existing keys (`link_ids`, `empty_p995`, `activity_scale`) unchanged. Constant `RV_VAR_MARGIN = 1.5`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ruview_calibrate.py
import numpy as np
from aura.frames import RFFrame
from aura.brain.calibrate import calibrate_empty, calibrate_walk
from aura.brain.ruview.detector import RuViewDetector, LINK_STREAM

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
    r_empty = RuViewDetector(cal).update(_frames(60, 0.3, seed=2), cal["link_ids"], ts=15.0)
    r_walk = RuViewDetector(cal).update(_frames(60, 4.0, seed=3), cal["link_ids"], ts=15.0)
    assert r_empty["motion"] == 0
    assert r_walk["motion"] == 1 and r_walk["presence"] == 1
    assert r_walk["activity"] > r_empty["activity"]

def test_existing_calibration_keys_untouched():
    cal = calibrate_empty(_frames(400, 0.3))
    assert set(cal) >= {"link_ids", "empty_p995"}
    cal = calibrate_walk(_frames(400, 4.0, seed=1), cal)
    assert "activity_scale" in cal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_ruview_calibrate.py -v`
Expected: FAIL — `KeyError: 'rv_empty'` (or missing `rv`)

- [ ] **Step 3: Write the implementation** — replace `aura/brain/calibrate.py` entirely with:

```python
# aura/brain/calibrate.py
import numpy as np
from aura.brain.features import select_links, build_matrix, summary
from aura.brain.ruview.features_rv import RssiFeatureExtractor
from aura.brain.ruview.detector import (raw_series, LINK_STREAM,
                                        AUTO_ACT_FLOOR, AUTO_ACT_CEIL)

RV_VAR_MARGIN = 1.5   # presence threshold = empty p95 variance x this margin

def _window_energies(frames, link_ids, win_s=15.0, step_s=5.0):
    if not frames:
        return []
    t0, t1 = frames[0].ts, frames[-1].ts
    out, t = [], t0
    while t + win_s <= t1:
        w = [f for f in frames if t <= f.ts < t + win_s]
        if len(w) >= 8:
            out.append(summary(build_matrix(w, link_ids))["motion_energy"])
        t += step_s
    return out

def _rv_window_stats(frames, link_ids, win_s=15.0, step_s=5.0):
    """Per-link per-window (variance, motion_band_power) plus the per-window
    stability-weighted fused motion-band power - the RuView calibration inputs."""
    ex = RssiFeatureExtractor()
    per_link = {lid: [] for lid in list(link_ids) + [LINK_STREAM]}
    fused = []
    if not frames:
        return per_link, fused
    t0, t1 = frames[0].ts, frames[-1].ts
    t = t0
    while t + win_s <= t1:
        w = [f for f in frames if t <= f.ts < t + win_s]
        t += step_s
        if len(w) < 8:
            continue
        rate = (len(w) - 1) / max(1e-9, w[-1].ts - w[0].ts)
        mbps, wts = [], []
        for lid in per_link:
            series, wt = raw_series(w, lid)
            if len(series) < 4 or wt <= 0 or float(np.std(series)) < 1e-9:
                continue
            f = ex.extract_from_array(series, rate)
            per_link[lid].append((f.variance, f.motion_band_power))
            mbps.append(f.motion_band_power)
            wts.append(wt)
        if mbps:
            fused.append(float(np.average(mbps, weights=wts)))
    return per_link, fused

def calibrate_empty(frames, k: int = 16) -> dict:
    link_ids = select_links(frames, k)
    e = _window_energies(frames, link_ids)
    if not e:
        raise ValueError("not enough empty-room data")
    cal = {"link_ids": link_ids, "empty_p995": float(np.percentile(e, 99.5))}
    per_link, fused = _rv_window_stats(frames, link_ids)
    cal["rv_empty"] = {lid: {"var_p95": float(np.percentile([v for v, _ in s], 95)),
                             "mbp_p95": float(np.percentile([m for _, m in s], 95))}
                       for lid, s in per_link.items() if s}
    cal["rv_act_floor"] = float(np.percentile(fused, 95)) if fused else AUTO_ACT_FLOOR
    return cal

def calibrate_walk(frames, cal: dict) -> dict:
    e = _window_energies(frames, cal["link_ids"])
    if not e:
        raise ValueError("not enough walking data")
    med = float(np.median(e))
    if med <= cal["empty_p995"]:
        raise ValueError("walk energy not above empty threshold — recheck placement")
    out = {**cal, "activity_scale": med}
    per_link, fused = _rv_window_stats(frames, cal["link_ids"])
    empty = cal.get("rv_empty") or {}
    var_thresh, motion_thresh = {}, {}
    for lid, stats in empty.items():
        var_thresh[lid] = stats["var_p95"] * RV_VAR_MARGIN
        walk_m = [m for _, m in per_link.get(lid, [])]
        if walk_m:
            # geometric midpoint between empty p95 and walking median band power
            motion_thresh[lid] = float(np.sqrt(max(1e-12, stats["mbp_p95"])
                                               * max(1e-12, float(np.median(walk_m)))))
    out["rv"] = {"var_thresh": var_thresh, "motion_thresh": motion_thresh,
                 "act_floor": cal.get("rv_act_floor", AUTO_ACT_FLOOR),
                 "act_ceil": float(np.median(fused)) if fused else AUTO_ACT_CEIL}
    return out
```

- [ ] **Step 4: Run new AND existing calibration tests**

Run: `.venv\Scripts\python -m pytest tests/test_ruview_calibrate.py tests/test_baseline.py -v`
Expected: all PASS (existing `test_baseline.py` exercises `calibrate_empty`/`calibrate_walk` — its assertions must still hold)

- [ ] **Step 5: Commit**

```bash
git add aura/brain/calibrate.py tests/test_ruview_calibrate.py
git commit -m "feat: Learn-my-room now derives per-link RuView thresholds"
```

---

### Task 5: `Config.detector` field + `brain.py` dispatch

**Files:**
- Modify: `aura/config.py` (add one dataclass field)
- Modify: `aura/brain/brain.py:30-88` (`run_brain` setup + `infer`)
- Modify: `tests/test_brain.py` (pin `detector` in 3 existing tests)
- Test: `tests/test_brain_ruview.py`

**Interfaces:**
- Consumes: `RuViewDetector` (Task 3).
- Produces: `Config.detector: str = "ruview"`; `run_brain` writes `state.json` with `src` ∈ `{"ruview", "baseline", "cnn"}`; ruview-path schema `{ts, presence, motion, activity, confidence, src}`; baseline/cnn schemas unchanged. `detector: "cnn"` without a model file falls back to ruview; ruview returning `None` (no usable channels) falls back to baseline for that inference.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_brain_ruview.py
import json, threading
import numpy as np
from aura.config import Config
from aura.frames import RFFrame, append_frame
from aura.brain.brain import run_brain

def _write_live(path, n, jitter, seed=0):
    import time
    rng = np.random.default_rng(seed)
    now = time.time()
    for i in range(n):
        wobble = jitter * np.sin(i / 3) + rng.normal(0, jitter / 2 + 1e-6)
        append_frame(path, RFFrame(ts=now - (n - i) * 0.25,
                                   wifi={"aaaaaaaa": -60 + wobble},
                                   link=[-50 + wobble], ble={}))

def test_default_detector_is_ruview(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    assert cfg.detector == "ruview"
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    run_brain(cfg, frames_path, threading.Event(), model_path=None, max_iters=1)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "ruview"
    assert state["presence"] == 1 and state["motion"] == 1
    assert set(state) == {"ts", "presence", "motion", "activity", "confidence", "src"}

def test_detector_baseline_pinned(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text('{"detector": "baseline"}')
    cfg = Config.load()
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    run_brain(cfg, frames_path, threading.Event(), model_path=None, max_iters=1)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "baseline"
    assert set(state) == {"ts", "presence", "motion", "activity", "src"}

def test_detector_cnn_without_model_falls_back_to_ruview(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text('{"detector": "cnn"}')
    cfg = Config.load()
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    run_brain(cfg, frames_path, threading.Event(), model_path=None, max_iters=1)
    assert json.loads((tmp_path / "state.json").read_text())["src"] == "ruview"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_brain_ruview.py -v`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'detector'`

- [ ] **Step 3: Implement**

In `aura/config.py`, add one field to the dataclass after `window_seconds` (the `Config.load` known-fields filter picks it up automatically):

```python
    window_seconds: float = 15.0
    detector: str = "ruview"          # ruview | baseline | cnn
```

In `aura/brain/brain.py`: add the import, gate ONNX loading on `detector == "cnn"`, create the detector once, and dispatch inside `infer`. The changed regions:

```python
from aura.brain.baseline import Baseline
from aura.brain.ruview.detector import RuViewDetector
```

```python
def run_brain(cfg, frames_path: Path, stop_event, model_path: Path = None, max_iters=None):
    sess = None
    model_channels = None
    if cfg.detector == "cnn" and model_path and Path(model_path).exists():
        import onnxruntime as ort
        sess = ort.InferenceSession(str(model_path))
        shape = sess.get_inputs()[0].shape
        dim1 = shape[1] if len(shape) > 1 else None
        model_channels = dim1 if isinstance(dim1, int) else None
    cal = _load_cal(cfg.aura_home)
    auto_mode = cal is None
    baseline = None
    rvdet = RuViewDetector(cal)   # tolerates cal=None (upstream default thresholds)
```

and inside `infer`, replace the block from `state = baseline.update(...)` through `src = "cnn"` with:

```python
        state = baseline.update(s, ts=now)
        src = "baseline"
        if sess is not None:
            lp, lm, la = sess.run(None, {"rf": m[None].astype(np.float32)})
            state = {"presence": int(_sig(lp[0]) > 0.5), "motion": int(_sig(lm[0]) > 0.5),
                     "activity": round(max(0.0, min(100.0, float(la[0]))), 1)}
            src = "cnn"
        elif cfg.detector != "baseline":
            rv = rvdet.update(w, link_ids, ts=now, frame_hz=cfg.frame_hz)
            if rv is not None:   # None (no usable channels) -> keep baseline state
                state, src = rv, "ruview"
```

In `tests/test_brain.py`, pin the detector in the three tests whose `src` assertions would otherwise flip — add one line right after `monkeypatch.setenv("AURA_HOME", str(tmp_path))` in each:

- `test_brain_baseline_only`: `(tmp_path / "config.json").write_text('{"detector": "baseline"}')`
- `test_brain_cnn_path`: `(tmp_path / "config.json").write_text('{"detector": "cnn"}')`
- `test_brain_auto_calibration_fallback`: `(tmp_path / "config.json").write_text('{"detector": "baseline"}')`

(`test_auto_cal_recovers_when_wifi_appears` and `test_brain_stops_when_idle` assert only `features.jsonl`/thread behavior, which is unchanged — leave them alone. Each line must be inserted BEFORE the `cfg = Config.load()` call in its test.)

- [ ] **Step 4: Run the full suite**

Run: `.venv\Scripts\python -m pytest tests -q`
Expected: all PASS (55 existing + 22 new so far)

- [ ] **Step 5: Commit**

```bash
git add aura/config.py aura/brain/brain.py tests/test_brain.py tests/test_brain_ruview.py
git commit -m "feat: detector dispatch (ruview default) in brain; Config.detector"
```

---

### Task 6: `training/validate.py` — session + truth timeline → metrics table

**Files:**
- Create: `training/validate.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `RuViewDetector`, `LINK_STREAM` (Task 3), `select_links` (existing), `read_frames` (existing).
- Produces: `validate(frames, timeline, cal=None, win_s=15.0, step_s=5.0, top_k=16) -> dict` with keys `windows, presence_acc, n_presence, motion_acc, n_motion, empty_motion_false_windows, entry_latency_s`. `timeline` is a list of `{"t0": float, "t1": float, "truth": "empty"|"present"|"walking"}` (absolute epoch seconds matching frame timestamps). CLI: `python -m training.validate <frames.jsonl> <timeline.json> [--cal calibration.json]` prints the dict as JSON.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validate.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'training.validate'`

- [ ] **Step 3: Write the implementation**

```python
# training/validate.py
"""Offline metrics: recorded frames + declared truth timeline -> submission table.

Timeline truth values: "empty" (nobody home), "present" (person, mostly still),
"walking" (person moving). A window is scored only when it lies entirely inside
one timeline segment. The detector runs chronologically so presence decay
behaves exactly as it does live.
"""
import argparse, json
from pathlib import Path

import numpy as np

from aura.frames import read_frames
from aura.brain.features import select_links
from aura.brain.ruview.detector import RuViewDetector

PRESENCE_TRUTH = {"empty": 0, "present": 1, "walking": 1}
MOTION_TRUTH = {"empty": 0, "walking": 1}   # "present" (still) excluded: motion may be 0 or brief


def _truth_at(timeline, t_start, t_end):
    for seg in timeline:
        if seg["t0"] <= t_start and t_end <= seg["t1"]:
            return seg["truth"]
    return None


def validate(frames, timeline, cal=None, win_s=15.0, step_s=5.0, top_k=16):
    det = RuViewDetector(cal)
    link_ids = (cal or {}).get("link_ids") or select_links(frames, top_k)
    rows = []
    t = frames[0].ts
    while t + win_s <= frames[-1].ts:
        w = [f for f in frames if t <= f.ts < t + win_s]
        truth = _truth_at(timeline, t, t + win_s)
        if len(w) >= 8 and truth is not None:
            r = det.update(w, link_ids, ts=t + win_s)
            if r is not None:
                rows.append({"ts": t + win_s, "truth": truth, **r})
        t += step_s

    def _acc(key, truthmap):
        pairs = [(r[key], truthmap[r["truth"]]) for r in rows if r["truth"] in truthmap]
        if not pairs:
            return None, 0
        return sum(int(p == want) for p, want in pairs) / len(pairs), len(pairs)

    presence_acc, n_p = _acc("presence", PRESENCE_TRUTH)
    motion_acc, n_m = _acc("motion", MOTION_TRUTH)
    false_windows = sum(1 for r in rows if r["truth"] == "empty" and r["motion"] == 1)

    latencies = []
    for prev, nxt in zip(timeline, timeline[1:]):
        if prev["truth"] == "empty" and nxt["truth"] in ("present", "walking"):
            hit = next((r["ts"] for r in rows if r["ts"] >= nxt["t0"] and r["presence"] == 1), None)
            if hit is not None:
                latencies.append(hit - nxt["t0"])
    entry_latency = float(np.median(latencies)) if latencies else None

    return {"windows": len(rows), "presence_acc": presence_acc, "n_presence": n_p,
            "motion_acc": motion_acc, "n_motion": n_m,
            "empty_motion_false_windows": false_windows,
            "entry_latency_s": entry_latency}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("timeline")
    ap.add_argument("--cal", default=None)
    a = ap.parse_args()
    frames = read_frames(Path(a.frames))
    timeline = json.loads(Path(a.timeline).read_text())
    cal = json.loads(Path(a.cal).read_text()) if a.cal else None
    print(json.dumps(validate(frames, timeline, cal), indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_validate.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add training/validate.py tests/test_validate.py
git commit -m "feat: offline validation metrics from session + truth timeline"
```

---

### Task 7: Validation protocol doc

**Files:**
- Create: `docs/validation-protocol.md`

**Interfaces:**
- Consumes: `training/validate.py` CLI (Task 6), existing board recording (aura-ear service, hourly archive cron).

- [ ] **Step 1: Write the doc**

```markdown
# Live validation protocol (no pre-recorded data required)

Produces the honest metrics table for the submission: presence accuracy,
detection latency, false alarms. Total hands-on time ~2.5 h; the board records
by itself throughout (aura-ear service, 4 Hz).

## 0. Calibrate the room (once per venue, ~15 min)
On the dashboard press "Learn my room", or:
    aura calibrate empty --minutes 10     # leave the room first
    aura calibrate walk --minutes 5       # walk around the room
This derives the per-link RuView thresholds (calibration.json, key "rv").

## 1. Scripted session (note wall-clock times as you go)
| Phase | Duration | You do | truth label |
|---|---|---|---|
| A | 30 min | leave the room entirely (phone can stay) | empty |
| B | 10 entries | walk in, stand 30 s, walk out, wait 60 s outside | walking / empty alternating |
| C | 30 min | sit still in the room (read, no walking) | present |
| D | 10 min | move around the room continuously | walking |

Write the timeline as JSON (absolute epoch seconds; get them with
`python -c "import time; print(time.time())"` at each phase boundary):
    [{"t0": 1755600000, "t1": 1755601800, "truth": "empty"}, ...]

## 2. Pull the frames and score
    scp "arduino@192.168.63.60:~/.aura/frames.jsonl" data/validation/frames.jsonl
    .venv\Scripts\python -m training.validate data/validation/frames.jsonl ^
        data/validation/timeline.json --cal data/validation/calibration.json
(scp calibration.json from the board too: ~/.aura/calibration.json)

## 3. Targets (from the design spec)
- presence_acc >= 0.90
- entry_latency_s <= 5 (window step is 5 s; <= 10 is still reportable honestly)
- empty_motion_false_windows: report as false-alarms-per-hour of empty time
- Overnight bonus run: leave mode=Away armed all night, count alerts (< 1).

Report both the RuView detector row and the baseline row (run validate twice,
second time after setting "detector": "baseline" — or just cite state.json src).
Cite upstream RuView's own accuracy claims as upstream's, never as ours.
```

- [ ] **Step 2: Verify the referenced commands exist**

Run: `.venv\Scripts\python -m training.validate --help`
Expected: usage text with `frames`, `timeline`, `--cal`

- [ ] **Step 3: Commit**

```bash
git add docs/validation-protocol.md
git commit -m "docs: live validation protocol for the metrics table"
```

---

### Task 8: Deploy to the board + live smoke

**Files:**
- No file changes (deploy + verification only). Board ops per `docs/spike-results.md` and project memory: ssh key auth, append `< /dev/null` to ssh commands, never `pkill -f`.

- [ ] **Step 1: Full local suite green**

Run: `.venv\Scripts\python -m pytest tests -q`
Expected: all PASS (≈79 tests)

- [ ] **Step 2: Push to the board**

```bash
sh deploy/push.sh arduino@192.168.63.60
```

Expected: rsync/scp completes without error. (If the board is unreachable, STOP — the hotspot `192.168.63.14` must be up and the PC on the same network.)

- [ ] **Step 3: Restart the brain service and verify the ruview path live**

```bash
ssh arduino@192.168.63.60 "sudo systemctl restart aura-brain && sleep 10 && cat ~/.aura/state.json" < /dev/null
```

Expected: JSON with `"src": "ruview"` and a `confidence` key. If `src` is `baseline`, check `journalctl -u aura-brain -n 30` — likely no WiFi frames yet (boot race is handled; wait 30 s and re-cat).

- [ ] **Step 4: Verify the consumers still work**

```bash
ssh arduino@192.168.63.60 "curl -s localhost:8080/api/state" < /dev/null
```

Expected: dashboard API returns the same state (presence/motion/activity present). Check the LED matrix physically shows sweep/bloom matching room state.

- [ ] **Step 5: Commit (local git tag of the deployed point)**

```bash
git add -u
git commit -m "chore: ruview detector deployed to board (live smoke passed)" --allow-empty
```

---

## Verification checklist (after all tasks)

- [ ] `pytest tests -q` fully green on PC.
- [ ] Board `state.json` shows `src: "ruview"` continuously; dashboard + matrix behave.
- [ ] Room calibration re-run on the board (protocol §0) so `rv` thresholds exist.
- [ ] NOTICE.md present; README gets a one-line RuView credit (write-up task, not code).
- [ ] Old Task 16 (CNN training) is explicitly optional — nothing in the deploy depends on a model file.
