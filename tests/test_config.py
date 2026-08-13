import json
from aura.config import Config

def test_load_creates_home_and_salt(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path / "home"))
    cfg = Config.load()
    assert cfg.aura_home.is_dir()
    assert len(cfg.salt) >= 16
    cfg2 = Config.load()
    assert cfg2.salt == cfg.salt  # persisted

def test_load_reads_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "config.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text(json.dumps({"frame_hz": 2.0, "gateway_ip": "192.168.1.1"}))
    cfg = Config.load()
    assert cfg.frame_hz == 2.0
    assert cfg.gateway_ip == "192.168.1.1"
    assert cfg.top_k == 16

def test_load_ignores_reserved_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text('{"aura_home": "/evil", "salt": "x", "top_k": 8}')
    cfg = Config.load()
    assert cfg.top_k == 8
    assert cfg.salt != "x"
