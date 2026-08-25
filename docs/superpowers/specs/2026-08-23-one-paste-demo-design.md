# One-paste demo (`aura demo`) — design

Date: 2026-08-23. Status: approved (chat), pre-implementation.

## Goal

A person with a fresh laptop — a judge, or anyone reading the repo — runs the
complete Aura experience with one copy-paste: clone, install, `aura demo`.
The dashboard (RF Sensing Console) opens in their browser, live-replaying the
published 23-Aug validation session through the exact production detector.
No board, no hardware, no configuration.

## User experience

README gains a "Run it yourself — no hardware needed" quickstart with two
4-line paste blocks:

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

`aura demo`:
1. Prints a narration banner: what session this is, that the first doorway
   entry arrives in ~90 s, and that everything shown is the production
   detector running on the real recording.
2. Starts the pipeline and opens the browser at `http://localhost:8080`.
3. Replays at 1× only (faithful; see Constraints), starting at an offset just
   before the first doorway entry so the viewer sees a stable EMPTY, then the
   walk-in flip, the 4 entries, and the sitting-still (hysteresis) phase.
4. Loops the session from the offset when it ends.
5. One Ctrl+C stops everything.

Flags: `--full` (replay from 0:00 — the entire 57-min session including the
long empty phase), `--no-browser`, `--session PATH` (defaults to the
published session).

## Internals

- New module `aura/demo.py`; `demo` subcommand dispatched in `cli.py`
  **before** the shared `Config.load()` so it can set `AURA_HOME` first.
- Scratch home: `.demo-home/` in the repo root (gitignored). Seeded on each
  run with `data/validation/calibration.json` (the calibration that produced
  the session's thresholds — required for the rv detector and zones).
  The user's real `~/.aura` is never touched.
- Threads: replay (daemon, loops) + brain (daemon) run alongside the Flask
  face server in the main thread (so Ctrl+C works naturally).
  `webbrowser.open()` fires ~2 s after startup unless `--no-browser`.
- `replay()` in `aura/ear/ear.py` gains `start_s: float = 0.0` — frames whose
  session-relative time is `< start_s` are dropped, and pacing re-bases on
  the first kept frame. Frames are re-stamped to wall-clock as today.
- Session facts (published `session-2026-08-23-frames.jsonl`): 13,623 frames,
  ts 1787494400–1787497811 (~57 min). Truth timeline (`timeline.json`):
  empty to +939 s, four walking entries at +1847/+2034/+2201/+2366 s,
  present (sitting) +2830–+3365 s. Default offset: **~1757 s** (90 s before
  entry 1) — to be confirmed empirically by replaying the frames offline and
  checking the detector reads EMPTY across the 90 s lead-in (the stretch
  between the scored empty phase and entry 1 is unlabeled). If it doesn't
  read empty there, slide the offset earlier until it does.

## Constraints

- **1× replay only.** `replay()` re-stamps frames to wall-clock; any
  speed-up compresses the dynamics inside the 15-s analysis windows and
  changes detector output. The demo never offers a speed flag.
- The demo makes no network calls except serving localhost (Telegram stays
  unconfigured; guardian is not started).
- Language rules of the submission apply to all printed narration (no
  "through-wall"/"imaging"/"sees you").

## Testing (TDD)

1. `replay(start_s=...)` trims correctly and re-bases pacing (unit, fixture
   frames).
2. Demo home seeding: calibration copied into a tmp `AURA_HOME`; idempotent.
3. Plumbing e2e (fast fixture, not the full session): replayed fixture →
   brain writes `sense.json` → Flask test client gets 200 on `/api/sense`.

The suite grows past 106; the new count is propagated in the same change to:
README, `docs/submission/report.html` (+ PDF re-export), `video-script.md`,
`notebooklm-source.md`. The report and NotebookLM source also gain a one-line
"run it yourself in one paste" reproducibility point.

## Non-goals

- No fast-forward/scrub UI, no multi-session picker, no Docker image, no
  hosted demo. YAGNI — the paste block is the product.
