import json, time

def _read(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def _alert_active(cfg, now):
    p = cfg.aura_home / "alerts.jsonl"
    if not p.exists():
        return 0
    lines = p.read_text().strip().splitlines()
    if not lines:
        return 0
    try:
        return int(now - json.loads(lines[-1])["ts"] < 60.0)
    except Exception:
        return 0

def run_bridge(cfg, stop_event, port_factory=None, max_iters=None):
    if port_factory is None:
        import serial
        port_factory = lambda: serial.Serial(cfg.serial_port, 115200, timeout=1)
    port = port_factory()
    iters = 0
    try:
        while not stop_event.is_set():
            now = time.time()
            s = _read(cfg.aura_home / "state.json", {"presence": 0, "motion": 0, "activity": 0})
            line = f"S,{int(s.get('presence', 0))},{int(s.get('motion', 0))},{int(round(float(s.get('activity', 0))))},{_alert_active(cfg, now)}\n"
            port.write(line.encode())
            iters += 1
            if max_iters and iters >= max_iters:
                break
            stop_event.wait(0.2)
    finally:
        port.close()
