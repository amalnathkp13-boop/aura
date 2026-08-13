import json, time

def _read_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def run_guardian(cfg, stop_event, max_iters=None):
    from aura.guardian.rules import Rules
    from aura.guardian.notify import Notifier
    rules = Rules(lambda: _read_json(cfg.aura_home / "mode.json", {"mode": "home", "wellness_hours": 8}))
    notifier = Notifier(cfg)
    iters = 0
    while not stop_event.is_set():
        state = _read_json(cfg.aura_home / "state.json", None)
        if state:
            alert = rules.update(state)
            if alert:
                notifier.send(alert)
        iters += 1
        if max_iters and iters >= max_iters:
            break
        stop_event.wait(1.0)
