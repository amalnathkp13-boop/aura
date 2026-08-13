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

def test_index_served(tmp_path, monkeypatch):
    _, c = _client(tmp_path, monkeypatch)
    assert b"Aura" in c.get("/").data
