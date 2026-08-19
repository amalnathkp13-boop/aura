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
