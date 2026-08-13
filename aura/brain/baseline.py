class Baseline:
    PRESENCE_DECAY_S = 120.0

    def __init__(self, cal: dict):
        self.cal = cal
        self._last_motion_ts = None

    def update(self, s: dict, ts: float) -> dict:
        motion = int(s["motion_energy"] > self.cal["empty_p995"])
        if motion:
            self._last_motion_ts = ts
        presence = int(self._last_motion_ts is not None
                       and ts - self._last_motion_ts <= self.PRESENCE_DECAY_S)
        scale = self.cal.get("activity_scale") or 1.0
        activity = min(100.0, 100.0 * s["motion_energy"] / scale)
        return {"presence": presence, "motion": motion, "activity": round(activity, 1)}
