import json, threading
import numpy as np
from pathlib import Path
from aura.config import Config
from aura.frames import RFFrame, append_frame
from aura.brain.brain import run_brain

def _write_live(path, n, jitter, seed=0):
    import time
    rng = np.random.default_rng(seed)
    now = time.time()
    for i in range(n):
        append_frame(path, RFFrame(ts=now - (n - i) * 0.25,
                                   wifi={"aaaaaaaa": -60 + jitter * np.sin(i / 3) + rng.normal(0, jitter / 2)},
                                   link=[-50.0], ble={}))

def test_brain_baseline_only(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    (tmp_path / "calibration.json").write_text(json.dumps(
        {"link_ids": ["aaaaaaaa"], "empty_p995": 0.05, "activity_scale": 0.5}))
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    stop = threading.Event()
    run_brain(cfg, frames_path, stop, model_path=None, max_iters=3)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "baseline"
    assert state["motion"] == 1 and state["presence"] == 1
    feats = (tmp_path / "features.jsonl").read_text().strip().splitlines()
    assert len(feats) >= 1
    assert len(json.loads(feats[0])["channels"]) == 2  # 1 link + link-stream

def test_brain_cnn_path(tmp_path, monkeypatch):
    from training.dataset import build_dataset
    from training.train import train
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    (tmp_path / "calibration.json").write_text(json.dumps(
        {"link_ids": ["aaaaaaaa"], "empty_p995": 0.05, "activity_scale": 0.5}))
    from tests.test_training import _make_session
    s1 = _make_session(tmp_path / "s", "empty1", 0.3, 0)
    s2 = _make_session(tmp_path / "s", "move1", 4.0, 1, seed=1)
    npz = tmp_path / "ds.npz"
    build_dataset([s1, s2], ["aaaaaaaa"], npz)
    model = tmp_path / "m.onnx"
    train(npz, [], model, epochs=2)
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    import threading
    run_brain(cfg, frames_path, threading.Event(), model_path=model, max_iters=2)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "cnn"
    assert set(state) == {"ts", "presence", "motion", "activity", "src"}
