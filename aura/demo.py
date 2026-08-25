"""`aura demo` — the whole Aura experience on a laptop, no hardware.

Replays the published validation session through the production detector into
a scratch AURA_HOME and serves the dashboard on localhost. Never touches the
user's real ~/.aura."""
import os, shutil, threading, time, webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SESSION = REPO / "data" / "validation" / "session-2026-08-23-frames.jsonl"
DEFAULT_CAL = REPO / "data" / "validation" / "calibration.json"
DEFAULT_HOME = REPO / ".demo-home"
DEFAULT_START_S = 1757.0     # 90 s before the first doorway entry (+1847 s); verified EMPTY lead-in
_STALE = ("frames.jsonl", "state.json", "sense.json", "features.jsonl")


def seed_home(home: Path, cal_path: Path = DEFAULT_CAL) -> Path:
    """Fresh scratch home: the session's own calibration, no leftover state."""
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cal_path, home / "calibration.json")
    for name in _STALE:
        p = home / name
        if p.exists():
            p.unlink()
    return home
