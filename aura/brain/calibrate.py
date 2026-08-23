# aura/brain/calibrate.py
import numpy as np
from aura.brain.features import select_links, build_matrix, summary
from aura.brain.rfsense.features import RssiFeatureExtractor
from aura.brain.rfsense.detector import (raw_series, LINK_STREAM,
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
    stability-weighted fused motion-band power - the detector calibration inputs."""
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
    # calibration-time level anchor per channel: lets the detector notice when
    # the geometry has changed (phone moved) and the thresholds have gone stale
    for lid in cal["rv_empty"]:
        series, _ = raw_series(frames, lid)
        if len(series):
            cal["rv_empty"][lid]["rssi_med"] = float(np.median(series))
    cal["rv_act_floor"] = float(np.percentile(fused, 95)) if fused else AUTO_ACT_FLOOR
    return cal

def calibrate_zone(frames, cal: dict, name: str) -> dict:
    """Record a per-channel disturbance signature for one named zone: the user
    stands at that spot and sways/steps in place while frames are captured.
    Signature = per-channel median (variance, motion_band_power). Magnitude is
    kept deliberately - distance from each radio path changes how hard that
    path is bent, and that difference IS the zone information."""
    per_link, _ = _rv_window_stats(frames, cal["link_ids"])
    sig = {}
    for lid, stats in per_link.items():
        if len(stats) >= 3:
            sig[lid] = {"var": float(np.median([v for v, _ in stats])),
                        "mbp": float(np.median([m for _, m in stats]))}
    if len(sig) < 2:
        raise ValueError("not enough per-channel data for a zone signature - "
                         "stay in the zone and keep moving gently")
    out = {**cal}
    zones = dict(out.get("zones") or {})
    zones[name] = sig
    out["zones"] = zones
    return out

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
