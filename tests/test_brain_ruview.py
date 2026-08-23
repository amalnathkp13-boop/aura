import json, threading
import numpy as np
from aura.config import Config
from aura.frames import RFFrame, append_frame
from aura.brain.brain import run_brain

def _write_live(path, n, jitter, seed=0):
    import time
    rng = np.random.default_rng(seed)
    now = time.time()
    for i in range(n):
        wobble = jitter * np.sin(i / 3) + rng.normal(0, jitter / 2 + 1e-6)
        append_frame(path, RFFrame(ts=now - (n - i) * 0.25,
                                   wifi={"aaaaaaaa": -60 + wobble},
                                   link=[-50 + wobble], ble={}))

def test_default_detector_is_ruview(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    assert cfg.detector == "ruview"
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    run_brain(cfg, frames_path, threading.Event(), model_path=None, max_iters=1)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "ruview"
    assert state["presence"] == 1 and state["motion"] == 1
    assert set(state) == {"ts", "presence", "motion", "activity", "confidence",
                          "cal_stale", "src"}

def test_detector_baseline_pinned(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text('{"detector": "baseline"}')
    cfg = Config.load()
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    run_brain(cfg, frames_path, threading.Event(), model_path=None, max_iters=1)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "baseline"
    assert set(state) == {"ts", "presence", "motion", "activity", "src"}

def test_brain_writes_ruview_detail(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    run_brain(cfg, frames_path, threading.Event(), model_path=None, max_iters=1)
    d = json.loads((tmp_path / "ruview.json").read_text())
    assert d["state"]["src"] == "ruview"
    assert len(d["links"]) >= 1 and "vote" in d["links"][0]
    assert "ts" in d and "present_frac" in d


def test_detector_cnn_without_model_falls_back_to_ruview(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text('{"detector": "cnn"}')
    cfg = Config.load()
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    run_brain(cfg, frames_path, threading.Event(), model_path=None, max_iters=1)
    assert json.loads((tmp_path / "state.json").read_text())["src"] == "ruview"

def test_stale_calibration_warns(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "calibration.json").write_text(
        json.dumps({"link_ids": ["aaaaaaaa"], "empty_p995": 0.05, "activity_scale": 0.5}))
    cfg = Config.load()
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    run_brain(cfg, frames_path, threading.Event(), model_path=None, max_iters=1)
    assert "re-run Learn my room" in capsys.readouterr().out
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "ruview"
