import json, sys
from aura.cli import main

def test_status_prints_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "state.json").write_text(json.dumps({"ts": 1, "presence": 1, "motion": 0, "activity": 3.0, "src": "cnn"}))
    monkeypatch.setattr(sys, "argv", ["aura", "status"])
    main()
    out = capsys.readouterr().out
    assert "presence" in out and "cnn" in out

def test_replay_subcommand(tmp_path, monkeypatch):
    from aura.frames import RFFrame, append_frame, read_frames
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    src = tmp_path / "rec.jsonl"
    for i in range(3):
        append_frame(src, RFFrame(ts=float(i), wifi={}, link=[], ble={}))
    monkeypatch.setattr(sys, "argv", ["aura", "replay", "--session", str(src), "--speed", "1000"])
    main()
    assert len(read_frames(tmp_path / "frames.jsonl")) == 3

def test_demo_subcommand_dispatches_before_config_load(tmp_path, monkeypatch):
    import aura.demo
    calls = {}
    monkeypatch.setattr(aura.demo, "run_demo", lambda **kw: calls.update(kw))
    monkeypatch.setattr("aura.cli.Config.load", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Config.load must not run before demo")))
    monkeypatch.setattr(sys, "argv", ["aura", "demo", "--no-browser", "--full", "--session", str(tmp_path / "s.jsonl")])
    main()
    assert calls["open_browser"] is False and calls["full"] is True
    assert calls["session"] == tmp_path / "s.jsonl"
