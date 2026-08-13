import json, threading, time
from aura.config import Config
from aura.face.bridge import run_bridge

class FakePort:
    def __init__(self): self.lines = []
    def write(self, b): self.lines.append(b.decode())
    def close(self): pass

def test_bridge_sends_state_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    (tmp_path / "state.json").write_text(json.dumps({"ts": time.time(), "presence": 1, "motion": 0, "activity": 42.0, "src": "cnn"}))
    (tmp_path / "alerts.jsonl").write_text(json.dumps({"type": "intrusion", "ts": time.time()}) + "\n")
    port = FakePort()
    run_bridge(cfg, threading.Event(), port_factory=lambda: port, max_iters=3)
    assert port.lines[0] == "S,1,0,42,1\n"
    assert len(port.lines) == 3

def test_bridge_no_state_sends_zeros(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    port = FakePort()
    run_bridge(cfg, threading.Event(), port_factory=lambda: port, max_iters=1)
    assert port.lines == ["S,0,0,0,0\n"]
