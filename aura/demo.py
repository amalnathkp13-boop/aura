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


_REPLAY_SPEED = 1.0   # 1x only (faithful dynamics). Tests override to fast-forward a fixture.


def banner(session: Path, start_s: float, full: bool) -> str:
    lead = "from the very beginning (about 57 minutes, including the long empty phase)" if full \
        else f"from {int(start_s // 60)} min {int(start_s % 60)} s in - the first doorway entry arrives in about 90 s"
    return "\n".join([
        "",
        "  Aura demo - the production detector on the real recording",
        f"  session : {session.name}",
        f"  replay  : {lead}",
        "  what you will see: a stable EMPTY room, the walk-in flip to PRESENT, four doorway",
        "                     entries, then a person sitting still (presence held by hysteresis).",
        "  dashboard: http://localhost:8080   (Ctrl+C stops everything)",
        "  nothing here is simulated - the frames are the 23 Aug 2026 validation session, replayed at 1x.",
        "",
    ])


def run_demo(session: Path = DEFAULT_SESSION, home: Path = DEFAULT_HOME,
             start_s: float = DEFAULT_START_S, open_browser: bool = True,
             full: bool = False, port: int = 8080, serve: bool = True):
    session, home = Path(session), Path(home)
    if not session.exists():
        raise SystemExit(f"session not found: {session}")
    os.environ["AURA_HOME"] = str(seed_home(home))     # must precede Config.load()
    from aura.config import Config
    from aura.ear.ear import replay
    from aura.brain.brain import run_brain
    from aura.face.server import create_app
    cfg = Config.load()
    frames_path = cfg.aura_home / "frames.jsonl"
    offset = 0.0 if full else start_s
    stop = threading.Event()

    def _replay_forever():
        while not stop.is_set():
            replay(session, frames_path, speed=_REPLAY_SPEED, start_s=offset)
            if _REPLAY_SPEED != 1.0:      # test mode: one pass is enough
                return

    threading.Thread(target=_replay_forever, name="aura-demo-replay", daemon=True).start()
    threading.Thread(target=run_brain, args=(cfg, frames_path, stop),
                     name="aura-demo-brain", daemon=True).start()
    print(banner(session, start_s, full), flush=True)
    if not serve:
        return cfg
    if open_browser:
        threading.Timer(2.0, webbrowser.open, args=(f"http://localhost:{port}",)).start()
    try:
        create_app(cfg).run(host="127.0.0.1", port=port)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
    return cfg
