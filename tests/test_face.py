import json
from aura.config import Config
from aura.face.server import create_app

def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    return cfg, create_app(cfg).test_client()

def test_state_empty_then_value(tmp_path, monkeypatch):
    cfg, c = _client(tmp_path, monkeypatch)
    assert c.get("/api/state").get_json() == {"src": "none"}
    (cfg.aura_home / "state.json").write_text(json.dumps({"ts": 1, "presence": 1, "motion": 0, "activity": 5.0, "src": "cnn"}))
    assert c.get("/api/state").get_json()["presence"] == 1

def test_waterfall_returns_last_n(tmp_path, monkeypatch):
    cfg, c = _client(tmp_path, monkeypatch)
    with open(cfg.aura_home / "features.jsonl", "w") as fh:
        for i in range(200):
            fh.write(json.dumps({"ts": i, "motion_energy": 0.1, "band_energy": 0.2, "xcorr": 0.3, "channels": [0.1, 0.2]}) + "\n")
    rows = c.get("/api/waterfall?n=120").get_json()
    assert len(rows) == 120 and rows[-1]["ts"] == 199

def test_mode_roundtrip_and_validation(tmp_path, monkeypatch):
    cfg, c = _client(tmp_path, monkeypatch)
    r = c.post("/api/mode", json={"mode": "away"})
    assert r.status_code == 200
    assert json.loads((cfg.aura_home / "mode.json").read_text())["mode"] == "away"
    assert c.post("/api/mode", json={"mode": "party"}).status_code == 400

def test_mode_get_defaults_home_then_reflects_post(tmp_path, monkeypatch):
    cfg, c = _client(tmp_path, monkeypatch)
    assert c.get("/api/mode").get_json() == {"mode": "home", "wellness_hours": 8}
    c.post("/api/mode", json={"mode": "away"})
    assert c.get("/api/mode").get_json()["mode"] == "away"

def test_index_served(tmp_path, monkeypatch):
    _, c = _client(tmp_path, monkeypatch)
    assert b"Aura" in c.get("/").data

def test_bad_inputs_never_500(tmp_path, monkeypatch):
    cfg, c = _client(tmp_path, monkeypatch)
    assert c.post("/api/mode", data="[1,2,3]", content_type="application/json").status_code == 400
    assert c.post("/api/mode", data="not json", content_type="application/json").status_code == 400
    assert c.post("/api/mode", json={"mode": "away", "wellness_hours": "eight"}).status_code == 400
    assert c.post("/api/calibrate", data="[]", content_type="application/json").status_code == 400
    assert c.post("/api/calibrate", json={"phase": "nope"}).status_code == 400
    assert c.get("/api/waterfall?n=abc").status_code == 200
    assert c.get("/api/waterfall?n=0").get_json() == []
    (cfg.aura_home / "state.json").write_text("{corrupt")
    assert c.get("/api/state").get_json() == {"src": "none"}
    (cfg.aura_home / "state.json").write_text("[1,2]")
    assert c.get("/api/state").get_json() == {"src": "none"}

def test_sense_endpoint_empty_then_value(tmp_path, monkeypatch):
    cfg, c = _client(tmp_path, monkeypatch)
    assert c.get("/api/sense").get_json() == {}
    (cfg.aura_home / "sense.json").write_text(json.dumps(
        {"ts": 1.0, "links": [{"id": "aaaaaaaa", "vote": "active"}],
         "present_frac": 1.0, "active_frac": 1.0, "fused_band_energy": 2.0,
         "state": {"presence": 1, "motion": 1, "activity": 80.0,
                   "confidence": 0.9, "src": "rfsense"}}))
    d = c.get("/api/sense").get_json()
    assert d["links"][0]["vote"] == "active" and d["state"]["src"] == "rfsense"
    (cfg.aura_home / "sense.json").write_text("{corrupt")
    assert c.get("/api/sense").get_json() == {}


def test_alerts_endpoint(tmp_path, monkeypatch):
    import json as _json
    cfg, c = _client(tmp_path, monkeypatch)
    with open(cfg.aura_home / "alerts.jsonl", "w") as fh:
        for i in range(5):
            fh.write(_json.dumps({"type": "intrusion", "ts": float(i)}) + "\n")
    rows = c.get("/api/alerts?n=3").get_json()
    assert len(rows) == 3 and rows[-1]["ts"] == 4.0
