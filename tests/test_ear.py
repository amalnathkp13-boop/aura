import threading, time
from aura.config import Config
from aura.ear.ear import Ear
from aura.frames import read_frames, hash_mac

class FakePoller:
    def __init__(self, value): self.value = value
    def start(self): pass
    def stop(self): pass
    def latest(self): return self.value

def _cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    cfg.frame_hz = 20.0  # fast for test
    return cfg

def test_ear_writes_hashed_frames(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ear = Ear(cfg, FakePoller({"aa:bb:cc:dd:ee:01": -60.0}), FakePoller([-50.0]), FakePoller({}))
    out = tmp_path / "frames.jsonl"
    stop = threading.Event()
    t = threading.Thread(target=ear.run_forever, args=(out, stop)); t.start()
    time.sleep(0.5); stop.set(); t.join(timeout=2)
    frames = read_frames(out)
    assert len(frames) >= 5
    key = hash_mac("aa:bb:cc:dd:ee:01", cfg.salt)
    assert frames[0].wifi == {key: -60.0}
    assert frames[0].link == [-50.0]
    assert frames[0].ble == {}
    assert frames[1].ts > frames[0].ts

def test_replay_rewrites_timestamps(tmp_path, monkeypatch):
    from aura.ear.ear import replay
    from aura.frames import RFFrame, append_frame
    src = tmp_path / "rec.jsonl"
    for i in range(4):
        append_frame(src, RFFrame(ts=1000.0 + i * 0.25, wifi={}, link=[], ble={}))
    dst = tmp_path / "live.jsonl"
    replay(src, dst, speed=100.0)
    out = read_frames(dst)
    assert len(out) == 4
    assert out[0].ts > 1000.0 + 10  # rewritten to now
    assert abs((out[3].ts - out[0].ts) - 0.75 / 100.0) < 0.5

def test_rotate_renames_oversized_file(tmp_path):
    from aura.ear.ear import _rotate
    p = tmp_path / "frames.jsonl"
    p.write_bytes(b"x" * 1024)
    _rotate(p, max_bytes=1000)
    assert not p.exists()
    assert p.with_suffix(".jsonl.old").exists()
    p.write_bytes(b"y" * 10)
    _rotate(p, max_bytes=1000)
    assert p.exists()  # under limit -> untouched

def test_ear_tolerates_none_pollers(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ear = Ear(cfg, FakePoller(None), FakePoller(None), FakePoller(None))
    out = tmp_path / "frames.jsonl"
    stop = threading.Event()
    t = threading.Thread(target=ear.run_forever, args=(out, stop)); t.start()
    time.sleep(0.3); stop.set(); t.join(timeout=2)
    frames = read_frames(out)
    assert len(frames) >= 2
    assert frames[0].wifi == {} and frames[0].link == [] and frames[0].ble == {}

def test_replay_start_s_trims_and_rebases(tmp_path):
    from aura.ear.ear import replay
    from aura.frames import RFFrame, append_frame
    src = tmp_path / "rec.jsonl"
    for i in range(6):
        append_frame(src, RFFrame(ts=1000.0 + i * 0.25, wifi={"a": -50.0 - i}, link=[], ble={}))
    dst = tmp_path / "live.jsonl"
    replay(src, dst, speed=100.0, start_s=1.0)          # drops the first 4 frames (t=0.0..0.75)
    out = read_frames(dst)
    assert [f.wifi["a"] for f in out] == [-54.0, -55.0]  # frames 4 and 5 only
    assert abs((out[1].ts - out[0].ts) - 0.25 / 100.0) < 0.5   # pacing re-based on the first kept frame
