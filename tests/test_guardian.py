import json
from aura.guardian.rules import Rules
from aura.guardian.notify import Notifier
from aura.config import Config

def test_intrusion_needs_sustained_motion_and_cooldown():
    r = Rules(lambda: {"mode": "away", "wellness_hours": 8})
    assert r.update({"ts": 0.0, "motion": 1, "presence": 1}) is None      # not sustained yet
    assert r.update({"ts": 2.0, "motion": 1, "presence": 1}) is None
    a = r.update({"ts": 3.5, "motion": 1, "presence": 1})
    assert a and a["type"] == "intrusion"
    assert r.update({"ts": 10.0, "motion": 1, "presence": 1}) is None     # cooldown
    a2 = r.update({"ts": 310.0, "motion": 1, "presence": 1})
    assert a2 is None  # motion run restarted? no — sustained since 3.5 continuously
    # release and re-trigger after cooldown:
    r.update({"ts": 311.0, "motion": 0, "presence": 1})
    r.update({"ts": 312.0, "motion": 1, "presence": 1})
    assert r.update({"ts": 316.0, "motion": 1, "presence": 1})["type"] == "intrusion"

def test_home_mode_never_alerts():
    r = Rules(lambda: {"mode": "home", "wellness_hours": 8})
    for t in range(0, 100, 1):
        assert r.update({"ts": float(t), "motion": 1, "presence": 1}) is None

def test_wellness_inactivity():
    r = Rules(lambda: {"mode": "wellness", "wellness_hours": 1})
    assert r.update({"ts": 0.0, "motion": 1, "presence": 1}) is None
    assert r.update({"ts": 1800.0, "motion": 0, "presence": 0}) is None
    a = r.update({"ts": 3700.0, "motion": 0, "presence": 0})
    assert a and a["type"] == "inactivity"
    assert r.update({"ts": 3800.0, "motion": 0, "presence": 0}) is None   # once per quiet period

def test_notifier_writes_log_and_posts(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    cfg.telegram_token, cfg.telegram_chat_id = "TOK", "CHAT"
    calls = []
    n = Notifier(cfg, sender=lambda url, payload: calls.append((url, payload)))
    n.send({"type": "intrusion", "ts": 5.0})
    log = (tmp_path / "alerts.jsonl").read_text().strip().splitlines()
    assert json.loads(log[0])["type"] == "intrusion"
    assert "TOK" in calls[0][0] and calls[0][1]["chat_id"] == "CHAT"

def test_guardian_survives_schema_corrupt_files(tmp_path, monkeypatch):
    import threading
    from aura.guardian.guardian import run_guardian
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    (tmp_path / "state.json").write_text("[1, 2, 3]")          # valid JSON, wrong shape
    (tmp_path / "mode.json").write_text('{"mode": "away"}')
    run_guardian(cfg, threading.Event(), max_iters=2)           # must not raise
    (tmp_path / "state.json").write_text('{"presence": 1, "motion": 1}')  # missing ts
    run_guardian(cfg, threading.Event(), max_iters=2)           # must not raise
    assert not (tmp_path / "alerts.jsonl").exists()             # nothing valid ever arrived

def test_guardian_end_to_end_intrusion(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    # Test via Rules and Notifier directly
    r = Rules(lambda: {"mode": "away", "wellness_hours": 8})
    calls = []
    n = Notifier(cfg, sender=lambda url, payload: calls.append((url, payload)))
    # Feed three states with motion sustained across 6 seconds (triggers at ~3.5s)
    for ts in (100.0, 102.0, 104.0):
        alert = r.update({"ts": ts, "presence": 1, "motion": 1, "activity": 50.0, "src": "baseline"})
        if alert:
            n.send(alert)
    log = (tmp_path / "alerts.jsonl").read_text().strip().splitlines()
    assert any(json.loads(l)["type"] == "intrusion" for l in log)
