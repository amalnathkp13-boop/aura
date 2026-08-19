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
