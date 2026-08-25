import json
import os
from pathlib import Path

def test_seed_home_copies_calibration_and_clears_stale_state(tmp_path):
    from aura.demo import seed_home, DEFAULT_CAL
    home = tmp_path / "demo-home"
    (home).mkdir()
    for stale in ("frames.jsonl", "state.json", "sense.json", "features.jsonl"):
        (home / stale).write_text("stale")
    out = seed_home(home)
    assert out == home
    assert json.loads((home / "calibration.json").read_text()) == json.loads(Path(DEFAULT_CAL).read_text())
    for stale in ("frames.jsonl", "state.json", "sense.json", "features.jsonl"):
        assert not (home / stale).exists()

def test_seed_home_is_idempotent_and_creates_missing_dir(tmp_path):
    from aura.demo import seed_home
    home = tmp_path / "nested" / "demo-home"
    seed_home(home)
    seed_home(home)
    assert (home / "calibration.json").exists()

def test_demo_pipeline_replays_into_scratch_home_and_serves_sense(tmp_path, monkeypatch):
    """Fixture session (30 s, 4 Hz, real link ids) -> replay -> brain -> /api/sense 200 with a state."""
    import time
    from aura.frames import RFFrame, append_frame, read_frames
    from aura.demo import run_demo, DEFAULT_CAL
    cal = json.loads(Path(DEFAULT_CAL).read_text())
    a, b = cal["link_ids"][0], cal["link_ids"][1]
    src = tmp_path / "fixture.jsonl"
    for i in range(120):                                  # 30 s at 4 Hz
        wobble = 3.0 if (i // 4) % 2 else 0.0             # a person-ish disturbance every other second
        append_frame(src, RFFrame(ts=1000.0 + i * 0.25,
                                  wifi={a: -48.0 - wobble, b: -78.0},
                                  link=[-49.0 - wobble] * 8, ble={}))
    home = tmp_path / "demo-home"
    monkeypatch.setattr("aura.demo._REPLAY_SPEED", 1000.0)   # test hook: replay the 30 s fixture instantly
    cfg = run_demo(session=src, home=home, start_s=0.0, open_browser=False, serve=False)
    assert Path(os.environ["AURA_HOME"]) == home
    deadline = time.time() + 10
    while time.time() < deadline and not (home / "sense.json").exists():
        time.sleep(0.1)
    assert (home / "sense.json").exists(), "brain never produced sense.json"
    assert len(read_frames(home / "frames.jsonl")) >= 8
    from aura.face.server import create_app
    r = create_app(cfg).test_client().get("/api/sense")
    assert r.status_code == 200 and "state" in r.get_json()

def test_run_demo_reports_a_clear_error_when_the_port_is_busy(tmp_path, monkeypatch):
    import pytest
    import aura.demo as demo
    from aura.frames import RFFrame, append_frame

    class _BusyApp:
        def run(self, host=None, port=None):
            raise OSError(98, "Address already in use")

    monkeypatch.setattr("aura.face.server.create_app", lambda cfg: _BusyApp())
    src = tmp_path / "tiny.jsonl"
    append_frame(src, RFFrame(ts=1.0, wifi={}, link=[], ble={}))
    with pytest.raises(SystemExit) as ei:
        demo.run_demo(session=src, home=tmp_path / "h", start_s=0.0, open_browser=False, serve=True)
    msg = str(ei.value).lower()
    assert "port" in msg and str(8080) in msg
