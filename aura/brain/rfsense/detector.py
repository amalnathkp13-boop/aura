"""Multi-link fusion around the ported upstream classifier (Aura-original;
upstream attribution: NOTICE.md).

Each WiFi link (plus the connected-link stream) is treated as one
"receiver": features are extracted per link, each link is classified with the
other links passed as other_receiver_results (upstream's own cross-receiver
agreement), and the final decision is a stability-weighted vote. A single noisy
link cannot outvote several quiet ones; a dead-flat channel is skipped entirely.
"""
import numpy as np

from aura.brain.rfsense.features import RssiFeatureExtractor
from aura.brain.rfsense.classifier import MotionLevel, PresenceClassifier

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


ZONE_MAX_DIST = 1.5     # log-feature Euclidean ceiling: farther than this from every zone -> no label
ZONE_MIN_MARGIN = 0.2   # runner-up must be at least this much farther than the winner

DRIFT_DB = 8.0          # link level this far from the calibration-time median = geometry changed
STALE_AFTER_S = 60.0    # sustained (empty-room) drift for this long -> calibration declared stale


class RFDetector:
    def __init__(self, cal=None):
        rv = (cal or {}).get("rv") or {}
        self.var_thresh = rv.get("var_thresh") or {}
        self.motion_thresh = rv.get("motion_thresh") or {}
        self.act_floor = rv.get("act_floor", AUTO_ACT_FLOOR)
        self.act_ceil = rv.get("act_ceil", AUTO_ACT_CEIL)
        self.zones = (cal or {}).get("zones") or {}
        # per-channel empty-room variance p95: the floor above which live energy
        # carries zone information (below it, the room could just be empty)
        self._zone_floor = {lid: s["var_p95"]
                            for lid, s in ((cal or {}).get("rv_empty") or {}).items()}
        self._extractor = RssiFeatureExtractor()
        self._last_motion_ts = None
        self._last_zone = None    # sticky across still periods while presence holds
        # calibration-time link RSSI median: the anchor for staleness detection
        # (the hotspot phone moving re-shapes every path and silently blinds the
        # calibrated thresholds - measured 19 dB on 2026-08-23)
        self._rssi_base = {lid: s["rssi_med"]
                           for lid, s in ((cal or {}).get("rv_empty") or {}).items()
                           if "rssi_med" in s}
        self._drift_since = None
        self.cal_stale = False
        self.last_detail = None   # per-channel breakdown of the latest update (for the dashboard)

    def _match_zone(self, feats_by_lid):
        """Nearest calibrated zone by Euclidean distance over log-scaled
        (variance, motion_band_power) per shared channel. Magnitude is part of
        the metric on purpose: with channels sharing one physical path, zones
        separate by how HARD the paths are bent, not by cross-channel pattern
        (measured 2026-08-23: two real zone signatures were cosine-0.997
        parallel but 3x apart in magnitude). Known confound, stated in the UI:
        motion vigour also scales magnitude. Returns (name, distance);
        (None, best_distance) when no zone wins clearly."""
        best, second, best_name = None, None, None
        for name, sig in self.zones.items():
            shared = [lid for lid in sig if lid in feats_by_lid]
            # 1 shared channel is enough: discrimination is magnitude-driven and
            # the link stream alone carries it; the scan channel flickers out of
            # the live set whenever two consecutive scans agree (dead-flat skip).
            if len(shared) < 1:
                continue
            a, b = [], []
            for lid in shared:
                f = feats_by_lid[lid]
                a += [np.log1p(f.variance), np.log1p(f.motion_band_power)]
                b += [np.log1p(sig[lid]["var"]), np.log1p(sig[lid]["mbp"])]
            dist = float(np.linalg.norm(np.array(a) - np.array(b))) / np.sqrt(len(shared))
            if best is None or dist < best:
                best, second, best_name = dist, best, name
            elif second is None or dist < second:
                second = dist
        if (best_name is not None and best <= ZONE_MAX_DIST
                and (second is None or second - best >= ZONE_MIN_MARGIN)):
            return best_name, best
        return None, best

    def update(self, frames, link_ids, ts, frame_hz=4.0):
        if len(frames) >= 2 and frames[-1].ts > frames[0].ts:
            rate = (len(frames) - 1) / (frames[-1].ts - frames[0].ts)
        else:
            rate = frame_hz

        channels, weights = [], []
        med_by_lid = {}
        for lid in list(link_ids) + [LINK_STREAM]:
            series, w = raw_series(frames, lid)
            if len(series):
                # level median even for dead-flat channels: a flat link parked
                # 20 dB from its calibrated level is still drift evidence
                med_by_lid[lid] = float(np.median(series))
            if len(series) < MIN_SAMPLES or w <= 0 or float(np.std(series)) < 1e-9:
                continue   # missing or dead-flat channel: no information, no vote
            feats = self._extractor.extract_from_array(series, rate)
            clf = PresenceClassifier(
                presence_variance_threshold=self.var_thresh.get(lid, AUTO_VAR_THRESH),
                motion_energy_threshold=self.motion_thresh.get(lid, AUTO_MOTION_THRESH))
            channels.append((lid, clf, feats, float(series[-1])))
            weights.append(w)
        if not channels:
            self.last_detail = None
            return None

        prelim = [clf.classify(feats) for _, clf, feats, _ in channels]
        sensing = [clf.classify(feats,
                                other_receiver_results=[r for j, r in enumerate(prelim) if j != i])
                   for i, (_, clf, feats, _) in enumerate(channels)]

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

        # Calibration staleness: judged only on empty-room windows (a person
        # shadowing the link shifts its level too, so occupied windows neither
        # accumulate toward stale nor clear an existing verdict).
        base = self._rssi_base.get(LINK_STREAM)
        link_med = med_by_lid.get(LINK_STREAM)
        if base is not None and link_med is not None and not presence:
            if abs(link_med - base) > DRIFT_DB:
                if self._drift_since is None:
                    self._drift_since = ts
                if ts - self._drift_since >= STALE_AFTER_S:
                    self.cal_stale = True
            else:
                self._drift_since = None
                self.cal_stale = False

        fused_mbp = sum(w * r.motion_band_energy for w, r in zip(weights, sensing)) / wsum
        confidence = sum(w * r.confidence for w, r in zip(weights, sensing)) / wsum

        zone_dist = None
        if self.zones:
            feats_by_lid = {lid: f for lid, _, f, _ in channels}
            # match whenever the live energy rises above the calibrated empty
            # floor on any channel (a full motion vote is stricter than zone
            # matching needs); the label then sticks while presence persists
            # (a still person emits no zone information).
            energetic = any(f.variance > self._zone_floor.get(lid, AUTO_VAR_THRESH)
                            for lid, f in feats_by_lid.items())
            if presence and (motion or energetic):
                z, zone_dist = self._match_zone(feats_by_lid)
                if z is not None:
                    self._last_zone = z
            if not presence:
                self._last_zone = None
        self.last_detail = {
            "links": [{"id": lid, "rssi": round(rssi_last, 1),
                       "variance": round(r.rssi_variance, 4),
                       "var_thresh": round(self.var_thresh.get(lid, AUTO_VAR_THRESH), 4),
                       "band_energy": round(r.motion_band_energy, 4),
                       "motion_thresh": round(self.motion_thresh.get(lid, AUTO_MOTION_THRESH), 4),
                       "vote": r.motion_level.value,
                       "confidence": round(r.confidence, 3),
                       "weight": round(w, 3),
                       "change_points": feats.n_change_points}
                      for (lid, _, feats, rssi_last), r, w in zip(channels, sensing, weights)],
            "present_frac": round(present_frac, 3),
            "active_frac": round(active_frac, 3),
            "fused_band_energy": round(fused_mbp, 4),
            "fused_breathing_energy": round(
                sum(w * r.breathing_band_energy for w, r in zip(weights, sensing)) / wsum, 4),
        }
        state = {"presence": presence, "motion": motion,
                 "activity": round(self._activity(fused_mbp), 1),
                 "confidence": round(float(confidence), 3),
                 "cal_stale": self.cal_stale}
        self.last_detail["cal_stale"] = self.cal_stale
        if self.zones:
            state["zone"] = self._last_zone
            self.last_detail["zone"] = self._last_zone
            self.last_detail["zone_dist"] = round(zone_dist, 3) if zone_dist is not None else None
        return state

    def _activity(self, energy):
        lo, hi = self.act_floor, self.act_ceil
        if hi <= lo:
            return min(100.0, 100.0 * energy / max(hi, 1e-9))
        x = (np.log(energy + 1e-9) - np.log(lo + 1e-9)) / (np.log(hi + 1e-9) - np.log(lo + 1e-9))
        return float(100.0 * min(1.0, max(0.0, x)))
