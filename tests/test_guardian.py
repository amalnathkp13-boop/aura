import json
from pathlib import Path
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
