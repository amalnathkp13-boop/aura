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
