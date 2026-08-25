# One-paste Demo (`aura demo`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `aura demo` on a fresh laptop opens the RF Sensing Console in the browser and live-replays the published 23-Aug session through the production detector — no board, no configuration, one Ctrl+C to stop.

**Architecture:** A new `aura/demo.py` owns a scratch `AURA_HOME` (`.demo-home/`, gitignored) seeded with the published calibration, then runs three existing pieces in one process: `replay()` (ear) in a looping daemon thread, `run_brain()` in a daemon thread, and the Flask face app on the main thread bound to localhost. `replay()` gains a `start_s` offset so the viewer sees a stable EMPTY, then the first doorway entry ~90 s in. The CLI dispatches `demo` *before* `Config.load()` so the scratch home is in effect.

**Tech Stack:** Python stdlib (`threading`, `webbrowser`, `shutil`), existing Flask app, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-23-one-paste-demo-design.md`. Deviation recorded here: the spec's instruction to propagate the new test count into `docs/submission/report.html`, the PDF, `video-script.md` and `notebooklm-source.md` is **dropped** — those mirror the submitted report and are frozen (user decision 2026-08-25). README, CONTRIBUTING and CHANGELOG are updated instead.
- Plain commit messages, no trailers. No personal emails.
- **1× replay only** — no speed flag on `aura demo`. `replay()` keeps its `speed` parameter for the existing `aura replay` command and tests.
- Demo binds `127.0.0.1:8080`, makes no network calls, never starts the guardian, never touches `~/.aura`.
- Narration text must not say "through-wall", "imaging", or "sees you".
- Default offset **1757 s** (confirmed 2026-08-25 by `offset_scan.py`: fresh detector from +1757 reads EMPTY for all 15 lead-in windows and flips PRESENT at +1867, 20 s after entry 1 at +1847; offsets ≤ +1600 walk into an unlabeled presence stretch).
- Suite: 106 → 110 tests; every "106" in README/CONTRIBUTING becomes "110" in the same commit.

---

### Task 1: `replay(start_s=...)` — trim and re-base pacing

**Files:**
- Modify: `aura/ear/ear.py:35-46` (`replay`)
- Test: `tests/test_ear.py` (append)

**Interfaces:**
- Produces: `replay(session_path: Path, out_path: Path, speed: float = 1.0, start_s: float = 0.0) -> None`. Frames whose `ts - frames[0].ts < start_s` are dropped; pacing re-bases on the first kept frame; output frames are re-stamped to wall-clock (unchanged behaviour).

- [ ] **Step 1: Write the failing test** — append to `tests/test_ear.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_ear.py::test_replay_start_s_trims_and_rebases -q`
Expected: FAIL — `TypeError: replay() got an unexpected keyword argument 'start_s'`

- [ ] **Step 3: Implement** — replace `replay` in `aura/ear/ear.py`:

```python
def replay(session_path: Path, out_path: Path, speed: float = 1.0, start_s: float = 0.0):
    """Stream a recorded session into out_path, re-stamped to wall-clock.

    start_s: skip frames earlier than this many seconds after the recording's
    first frame; pacing re-bases on the first kept frame so playback begins
    immediately at the offset."""
    frames = read_frames(session_path)
    if not frames:
        return
    origin = frames[0].ts
    frames = [f for f in frames if f.ts - origin >= start_s]
    if not frames:
        return
    base = frames[0].ts
    start = time.time()
    for f in frames:
        delay = (f.ts - base) / speed - (time.time() - start)
        if delay > 0:
            time.sleep(delay)
        append_frame(out_path, RFFrame(ts=time.time(), wifi=f.wifi, link=f.link, ble=f.ble))
        _rotate(out_path)
```

- [ ] **Step 4: Run the test file to verify it passes**

Run: `python -m pytest tests/test_ear.py tests/test_cli.py -q`
Expected: all pass (existing replay tests unaffected — `start_s` defaults to 0).

- [ ] **Step 5: Commit**

```bash
git add aura/ear/ear.py tests/test_ear.py
git commit -m "feat: replay() accepts a start_s offset (trim + re-base pacing)"
```

---

### Task 2: `aura/demo.py` — scratch home seeding

**Files:**
- Create: `aura/demo.py`
- Create: `tests/test_demo.py`
- Modify: `.gitignore` (add `.demo-home/`)

**Interfaces:**
- Produces: `seed_home(home: Path, cal_path: Path = DEFAULT_CAL) -> Path` — creates `home`, copies the calibration to `home/calibration.json`, deletes stale `frames.jsonl`, `state.json`, `sense.json`, `features.jsonl`; idempotent. Constants `REPO`, `DEFAULT_SESSION`, `DEFAULT_CAL`, `DEFAULT_HOME`, `DEFAULT_START_S = 1757.0`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_demo.py`:

```python
import json
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_demo.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aura.demo'`

- [ ] **Step 3: Create `aura/demo.py` (seeding part)**

```python
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
```

- [ ] **Step 4: Add `.demo-home/` to `.gitignore`** (append one line: `.demo-home/`)

- [ ] **Step 5: Run to verify they pass**

Run: `python -m pytest tests/test_demo.py -q`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add aura/demo.py tests/test_demo.py .gitignore
git commit -m "feat: demo scratch-home seeding (calibration copied, stale state cleared)"
```

---

### Task 3: `run_demo()` — pipeline wiring + end-to-end plumbing test

**Files:**
- Modify: `aura/demo.py` (append `banner`, `run_demo`)
- Modify: `tests/test_demo.py` (append e2e test)

**Interfaces:**
- Produces: `run_demo(session: Path = DEFAULT_SESSION, home: Path = DEFAULT_HOME, start_s: float = DEFAULT_START_S, open_browser: bool = True, full: bool = False, port: int = 8080, serve: bool = True) -> "Config"`. `serve=False` (tests) wires everything and returns the Config without blocking on Flask; `serve=True` blocks in `app.run` until Ctrl+C.

- [ ] **Step 1: Write the failing e2e test** — append to `tests/test_demo.py`:

```python
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
```

Add `import os` at the top of `tests/test_demo.py`.

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_demo.py -q`
Expected: FAIL — `ImportError: cannot import name 'run_demo'`

- [ ] **Step 3: Implement** — append to `aura/demo.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_demo.py -q`
Expected: `3 passed` (the e2e test takes a few seconds while the brain thread catches up).

If `sense.json` never appears: the brain's `RFDetector.update` returned `None` because the fixture's link ids did not match `cal["link_ids"]` — check the fixture uses `cal["link_ids"][0]` and `[1]` exactly, and that ≥ 8 frames fall inside one 15-s window.

- [ ] **Step 5: Commit**

```bash
git add aura/demo.py tests/test_demo.py
git commit -m "feat: run_demo wires replay + brain + localhost dashboard into a scratch home"
```

---

### Task 4: CLI `demo` subcommand (dispatched before Config.load)

**Files:**
- Modify: `aura/cli.py:13-15` (add parser; dispatch before `cfg = Config.load()`)
- Modify: `tests/test_cli.py` (append)

- [ ] **Step 1: Write the failing test** — append to `tests/test_cli.py`:

```python
def test_demo_subcommand_dispatches_before_config_load(tmp_path, monkeypatch):
    import aura.demo
    calls = {}
    monkeypatch.setattr(aura.demo, "run_demo", lambda **kw: calls.update(kw))
    monkeypatch.setattr("aura.cli.Config.load", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Config.load must not run before demo")))
    monkeypatch.setattr(sys, "argv", ["aura", "demo", "--no-browser", "--full", "--session", str(tmp_path / "s.jsonl")])
    main()
    assert calls["open_browser"] is False and calls["full"] is True
    assert calls["session"] == tmp_path / "s.jsonl"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_demo_subcommand_dispatches_before_config_load -q`
Expected: FAIL — argparse error `invalid choice: 'demo'` (SystemExit).

- [ ] **Step 3: Implement** — in `aura/cli.py`, after the `telegram-connect` parser line (line 13) add:

```python
    p = sub.add_parser("demo", help="no hardware: replay the published validation session through the production detector and open the dashboard")
    p.add_argument("--session", type=Path, default=None, help="frames.jsonl to replay (default: the published 23-Aug session)")
    p.add_argument("--full", action="store_true", help="replay from 0:00 (whole 57-min session) instead of just before the first entry")
    p.add_argument("--no-browser", action="store_true")
```

and immediately after `a = ap.parse_args()` (before `cfg = Config.load()`):

```python
    if a.cmd == "demo":
        import aura.demo
        kw = {"open_browser": not a.no_browser, "full": a.full}
        if a.session is not None:
            kw["session"] = a.session
        aura.demo.run_demo(**kw)
        return
```

- [ ] **Step 4: Run the CLI tests**

Run: `python -m pytest tests/test_cli.py -q`
Expected: all pass.

- [ ] **Step 5: Smoke-run the real thing for 20 s (no browser)**

Run (PowerShell/bash): `python -m aura.cli demo --no-browser` — leave it ~20 s, then Ctrl+C. While it runs, in another shell: `curl -s http://127.0.0.1:8080/api/state`.
Expected: banner printed; `.demo-home/frames.jsonl` growing at ~4 lines/s; `/api/state` returns JSON with `"src": "rfsense"` within ~20 s. (If running non-interactively, use `timeout`/`Start-Process` and `Stop-Process` after 20 s.)

- [ ] **Step 6: Commit**

```bash
git add aura/cli.py tests/test_cli.py
git commit -m "feat: aura demo subcommand (dispatched before Config.load)"
```

---

### Task 5: Docs — README paste blocks, test counts, changelog

**Files:**
- Modify: `README.md` (Reproduce section; every `106` → `110`)
- Modify: `CONTRIBUTING.md` (`106 tests` → `110 tests`)
- Modify: `CHANGELOG.md` (add Unreleased section)

- [ ] **Step 1: Replace the README "Reproduce on your PC — no hardware" section body** with:

```markdown
## Reproduce on your PC — no hardware

**One paste** — clone, install, `aura demo`. The RF Sensing Console opens in
your browser and live-replays the published 23-Aug validation session through
the exact production detector: a stable EMPTY room, the walk-in flip, four
doorway entries, then a person sitting still. Replay is 1× (faithful — the
detector's 15-s windows must see real dynamics). Ctrl+C stops it.

```powershell
# Windows (PowerShell)
git clone https://github.com/amalnathkp13-boop/aura.git; cd aura
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\aura demo
```

```bash
# macOS / Linux
git clone https://github.com/amalnathkp13-boop/aura.git && cd aura
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/aura demo
```

`aura demo --full` replays from 0:00 (the whole 57-minute session, long empty
phase included); `--no-browser` just serves `http://localhost:8080`. Everything
runs in a scratch `.demo-home/` — your real `~/.aura` is never touched.

**Re-score the session** — the same recording, calibration and truth timeline,
scored by the validation harness:

```sh
pip install -e ".[dev]"
python -m training.validate data/validation/session-2026-08-23-frames.jsonl data/validation/timeline.json --cal data/validation/calibration.json
python -m training.validate data/validation/session-2026-08-23-frames.jsonl data/validation/timeline.json --cal data/validation/calibration.json --detector baseline
python -m pytest tests/        # 110 tests
```

`frames.jsonl` is also a flight recorder: `aura replay --session <file>` streams
any recording back through the live pipeline, so an incident can be re-run
offline through the same code that made the decision.
```

- [ ] **Step 2: Update counts** — `sed -i 's/106 tests/110 tests/g; s/tests-106%20passing/tests-110%20passing/; s/106 automated tests/110 automated tests/' README.md CONTRIBUTING.md`, then `grep -n 106 README.md CONTRIBUTING.md` must return nothing.

- [ ] **Step 3: CHANGELOG** — insert above `## [1.0.0]`:

```markdown
## [Unreleased]

### Added
- `aura demo` — one-paste, no-hardware demo: replays the published validation
  session through the production detector into a scratch home and opens the
  dashboard on localhost (`--full`, `--no-browser`, `--session`).
- `replay(start_s=…)` offset for the ear's session replay.

```

- [ ] **Step 4: Full suite + link check**

Run: `python -m pytest tests/ -q` → `110 passed`; `python -m ruff check aura training tests` → clean.

- [ ] **Step 5: Commit and push; watch CI**

```bash
git add README.md CONTRIBUTING.md CHANGELOG.md
git commit -m "docs: one-paste demo quickstart; test count 110"
git push origin main
gh run watch --exit-status $(gh run list --workflow ci.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```
Expected: green. Then report: the paste block, what a judge will see, and that the submission docs were deliberately not touched.
