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
    (tmp_path / "config.json").write_text('{"detector": "baseline"}')
    cfg = Config.load()
    (tmp_path / "calibration.json").write_text(json.dumps(
        {"link_ids": ["aaaaaaaa"], "empty_p995": 0.05, "activity_scale": 0.5}))
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    stop = threading.Event()
    run_brain(cfg, frames_path, stop, model_path=None, max_iters=1)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "baseline"
    assert state["motion"] == 1 and state["presence"] == 1
    feats = (tmp_path / "features.jsonl").read_text().strip().splitlines()
    assert len(feats) >= 1
    assert len(json.loads(feats[0])["channels"]) == 2  # 1 link + link-stream
    spectrum = json.loads(feats[-1])["spectrum"]
    assert len(spectrum) == 30
    assert all(v >= 0 for v in spectrum)

def test_brain_cnn_path(tmp_path, monkeypatch):
    from training.dataset import build_dataset
    from training.train import train
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text('{"detector": "cnn"}')
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
    run_brain(cfg, frames_path, threading.Event(), model_path=model, max_iters=1)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "cnn"
    assert set(state) == {"ts", "presence", "motion", "activity", "src"}

def test_brain_auto_calibration_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text('{"detector": "baseline"}')
    cfg = Config.load()
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    run_brain(cfg, frames_path, threading.Event(), model_path=None, max_iters=1)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "baseline"
    assert set(state) == {"ts", "presence", "motion", "activity", "src"}

def test_auto_cal_recovers_when_wifi_appears(tmp_path, monkeypatch):
    # Regression for the boot-race bug: run_brain's auto-calibration fallback used to
    # derive link_ids ONCE (on the very first inference) and cache it in the closure
    # for the rest of the process's life. On a real board the brain starts before
    # WiFi associates, so that first window has empty `wifi` dicts -> select_links
    # returns [] -> the brain ran forever with zero WiFi channels even after WiFi came
    # up. This drives a single long-running run_brain() (background thread, matching
    # test_brain_stops_when_idle's pattern) through exactly that boot-then-recover
    # sequence and asserts the SAME continuous run re-derives link_ids once WiFi
    # frames start streaming in via the live tail_frames path.
    import time as _time
    from aura.frames import RFFrame, append_frame
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    frames_path = tmp_path / "frames.jsonl"
    now = _time.time()
    for i in range(40):  # boot phase: no wifi visible yet
        append_frame(frames_path, RFFrame(ts=now - 40 + i * 0.25, wifi={}, link=[-50.0], ble={}))
    stop = threading.Event()
    t = threading.Thread(target=run_brain, args=(cfg, frames_path, stop), kwargs={"model_path": None})
    t.start()
    _time.sleep(0.6)  # let the initial preload inference (boot-phase window) land
    feats = [json.loads(l) for l in (tmp_path / "features.jsonl").read_text().splitlines()]
    assert len(feats[-1]["channels"]) == 1  # link stream only, as expected during boot

    rng = np.random.default_rng(0)
    live_now = _time.time()
    for i in range(80):  # wifi comes up mid-run, streamed live into the SAME running brain
        append_frame(frames_path, RFFrame(ts=live_now + i * 0.05,
                     wifi={"aaaaaaaa": -60 + rng.normal(0, 2), "bbbbbbbb": -70 + rng.normal(0, 2)},
                     link=[-50.0], ble={}))
    _time.sleep(1.5)  # give the running thread time to poll, re-window, and re-infer
    stop.set()
    t.join(timeout=5)
    assert not t.is_alive()
    feats = [json.loads(l) for l in (tmp_path / "features.jsonl").read_text().splitlines()]
    assert len(feats[-1]["channels"]) == 3  # 2 wifi links + link stream: selection recovered

def test_brain_stops_when_idle(tmp_path, monkeypatch):
    import time as _time
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    (tmp_path / "calibration.json").write_text(json.dumps(
        {"link_ids": ["aaaaaaaa"], "empty_p995": 0.05, "activity_scale": 0.5}))
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    stop = threading.Event()
    t = threading.Thread(target=run_brain, args=(cfg, frames_path, stop))
    t.start(); _time.sleep(0.5); stop.set(); t.join(timeout=3)
    assert not t.is_alive()
