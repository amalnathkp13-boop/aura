class Rules:
    SUSTAIN_S, COOLDOWN_S = 3.0, 300.0

    def __init__(self, mode_getter):
        self.mode_getter = mode_getter
        self._motion_since = None
        self._last_alert_ts = -1e12
        self._last_motion_ts = None
        self._inactivity_fired = False

    def update(self, state: dict):
        m = self.mode_getter()
        mode, ts = m.get("mode", "home"), state["ts"]
        if state.get("motion"):
            if self._motion_since is None:
                self._motion_since = ts
            self._last_motion_ts = ts
            self._inactivity_fired = False
        else:
            self._motion_since = None
        if mode == "away" and self._motion_since is not None \
                and ts - self._motion_since >= self.SUSTAIN_S \
                and ts - self._last_alert_ts >= self.COOLDOWN_S \
                and self._motion_since > self._last_alert_ts:
            self._last_alert_ts = ts
            return {"type": "intrusion", "ts": ts}
        if mode == "wellness" and not self._inactivity_fired and self._last_motion_ts is not None \
                and ts - self._last_motion_ts >= m.get("wellness_hours", 8) * 3600.0:
            self._inactivity_fired = True
            return {"type": "inactivity", "ts": ts}
        return None
