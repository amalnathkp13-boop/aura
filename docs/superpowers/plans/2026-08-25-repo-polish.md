# Repository Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make github.com/amalnathkp13-boop/aura present as a finished, professional open-source project: green CI badge, results + one-command reproduction in the README, MIT detected by GitHub, complete package metadata, OSS hygiene files, tidy repo settings, and a v1.0.0 release of the submitted state.

**Architecture:** Pure repository/metadata work — no runtime code changes except removing four unused imports. Each task is one logical commit that leaves the repo consistent. README is rewritten last so the tag captures it. GitHub-side settings and the release are done with the `gh` CLI.

**Tech Stack:** git, GitHub CLI (`gh`), GitHub Actions, setuptools/pyproject, pytest, ruff.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-25-repo-polish-design.md`.
- Commit messages are plain — **never** add a `Co-Authored-By` trailer in this repo.
- Never put personal email addresses in the tree (authors are names only).
- Do not touch `docs/submission/report.html`, either PDF, or the docx.
- No formatter pass; no directory renames; no `aura demo` implementation.
- Every number in the README must come from the reproduce command in Task 6 (already run: rfsense presence_acc 0.9490, motion_acc 0.9158, empty_motion_false_windows 0, entries_missed 0, entry_latency_s 18.16; baseline 0.5136 / 0.7789 / 30 / 0 / 33.16; 294 presence windows, 190 motion windows, 0.2306 empty hours, 4 truth entries).
- Full test suite must stay at 106 passed.
- Work from `C:/Users/ASUS/aura` on branch `main`; push after each task so CI history is clean.

---

### Task 1: LICENSE verbatim + pyproject metadata + ruff config

**Files:**
- Modify: `LICENSE` (replace whole file)
- Modify: `pyproject.toml` (replace whole file)

**Interfaces:**
- Produces: `[tool.ruff.lint] select = ["E9","F"]` consumed by Task 3 and the CI lint job (Task 4); `dev` extra includes `ruff` (CI installs it).

- [ ] **Step 1: Replace LICENSE with the verbatim MIT template**

```text
MIT License

Copyright (c) 2026 Amalnath K P

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

(The removed "Portions of this software are adapted…" paragraph already lives in README *License* and NOTICE.md.)

- [ ] **Step 2: Replace pyproject.toml**

```toml
[project]
name = "aura"
version = "1.0.0"
description = "Camera-free presence sensing on a bare Arduino UNO Q — the board's own radio as a privacy-first smart-home sensor"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.9"
authors = [
  { name = "Kumaravel S" },
  { name = "Amalnath K P" },
]
keywords = ["arduino", "uno-q", "wifi-sensing", "rssi", "presence-detection", "smart-home", "edge-ai", "privacy"]
classifiers = [
  "Development Status :: 4 - Beta",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: MIT License",
  "Operating System :: POSIX :: Linux",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.13",
  "Topic :: Home Automation",
  "Topic :: Scientific/Engineering",
  "Topic :: System :: Hardware",
]
dependencies = ["numpy", "flask", "requests"]

[project.urls]
Homepage = "https://github.com/amalnathkp13-boop/aura"
Repository = "https://github.com/amalnathkp13-boop/aura"
Issues = "https://github.com/amalnathkp13-boop/aura/issues"
"Demo video" = "https://drive.google.com/file/d/16GfqoFsQ8vYzgybYod_s7oeFLkfacokY/view"

[project.optional-dependencies]
board = ["onnxruntime", "pyserial"]
train = ["torch", "onnx", "onnxruntime", "ultralytics", "opencv-python", "onnxscript"]
dev = ["pytest", "ruff"]

[project.scripts]
aura = "aura.cli:main"

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["aura*"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 120
target-version = "py39"

[tool.ruff.lint]
select = ["E9", "F"]
```

- [ ] **Step 3: Verify metadata installs and ruff reads the config**

Run: `python -m pip install -e . -q && python -c "from importlib.metadata import version; print(version('aura'))"`
Expected: `1.0.0`

Run: `python -m ruff check aura training tests --statistics`
Expected: exactly `4  F401  [*] unused-import` and `Found 4 errors.` (fixed in Task 3)

- [ ] **Step 4: Commit and push**

```bash
git add LICENSE pyproject.toml
git commit -m "chore: verbatim MIT license text; full package metadata (v1.0.0), pytest and ruff config"
git push origin main
```

---

### Task 2: .gitattributes, line-ending normalisation, UTF-8 taps file

**Files:**
- Create: `.gitattributes`
- Modify: `data/validation/phaseB-taps.txt` (re-encode UTF-16LE+CRLF → UTF-8+LF; content unchanged)

- [ ] **Step 1: Create .gitattributes**

```gitattributes
# LF in the repository AND on checkout: deploy scripts and systemd units run
# on the board's Linux side, so native (CRLF) checkouts on Windows would break them.
* text=auto eol=lf

# Binary assets
*.png  binary
*.jpg  binary
*.jpeg binary
*.pdf  binary
*.docx binary
*.pt   binary
*.npz  binary

# Large recorded data: keep diffs quiet
*.jsonl -diff
```

- [ ] **Step 2: Re-encode the taps file**

Run:
```bash
python - <<'PY'
p='data/validation/phaseB-taps.txt'
raw=open(p,'rb').read()
txt=raw.decode('utf-16').replace('\r\n','\n')
open(p,'w',encoding='utf-8',newline='\n').write(txt)
print(len(txt.splitlines()),'lines')
PY
file data/validation/phaseB-taps.txt
```
Expected: `file` reports ASCII/UTF-8 text, no UTF-16, no CRLF. Line count equals `git show HEAD:data/validation/phaseB-taps.txt | python -c "import sys;print(len(sys.stdin.buffer.read().decode('utf-16').splitlines()))"`.

- [ ] **Step 3: Renormalise and confirm only expected files change**

Run: `git add --renormalize . && git status --short`
Expected: only `.gitattributes` (new) and `data/validation/phaseB-taps.txt` (modified). If any other file appears, inspect with `git diff --stat` — a file that only changes line endings is fine to include; anything else is a mistake.

- [ ] **Step 4: Tests still pass**

Run: `python -m pytest tests/`
Expected: `106 passed`

- [ ] **Step 5: Commit and push**

```bash
git add .gitattributes data/validation/phaseB-taps.txt
git commit -m "chore: enforce LF line endings via .gitattributes; store stopwatch taps as UTF-8"
git push origin main
```

---

### Task 3: Lint fixes (unused imports only)

**Files:**
- Modify: `aura/labeler/labeler.py:19` (remove `import numpy as np` inside `run_labeler`)
- Modify: `tests/test_brain.py:3` (remove `from pathlib import Path`)
- Modify: `tests/test_ear.py:2` (remove `from pathlib import Path`)
- Modify: `tests/test_training.py:2` (remove `from pathlib import Path`)

- [ ] **Step 1: Confirm the exact findings**

Run: `python -m ruff check aura training tests --output-format concise`
Expected (4 lines):
```
aura/labeler/labeler.py:19:21: F401 [*] `numpy` imported but unused
tests/test_brain.py:3:21: F401 [*] `pathlib.Path` imported but unused
tests/test_ear.py:2:21: F401 [*] `pathlib.Path` imported but unused
tests/test_training.py:2:21: F401 [*] `pathlib.Path` imported but unused
```

- [ ] **Step 2: Apply the safe auto-fix (removes exactly those four import lines)**

Run: `python -m ruff check aura training tests --fix && git diff --stat`
Expected: 4 files changed, 4 deletions, 0 insertions. Inspect `git diff` — only import lines removed.

- [ ] **Step 3: Lint clean and tests green**

Run: `python -m ruff check aura training tests`
Expected: `All checks passed!`

Run: `python -m pytest tests/`
Expected: `106 passed`

- [ ] **Step 4: Commit and push**

```bash
git add aura/labeler/labeler.py tests/test_brain.py tests/test_ear.py tests/test_training.py
git commit -m "chore: drop four unused imports flagged by ruff"
git push origin main
```

---

### Task 4: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: workflow named `CI` with jobs `lint` and `test`; badge URL `https://github.com/amalnathkp13-boop/aura/actions/workflows/ci.yml/badge.svg` used by Task 6.

- [ ] **Step 1: Create the workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
    tags: ["v*"]
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: ruff
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: python -m pip install ruff
      - run: ruff check aura training tests

  test:
    name: pytest (py${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: python -m pip install --upgrade pip
      - run: python -m pip install -e ".[dev,board]"
      # CPU-only torch keeps the ONNX-export test runnable without a 2 GB CUDA wheel.
      - run: python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
      - run: python -m pip install onnx onnxscript
      - run: python -m pytest tests/
```

- [ ] **Step 2: Commit, push, watch the run**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: ruff + pytest (Python 3.11/3.13) on every push and pull request"
git push origin main
gh run watch --exit-status $(gh run list --workflow ci.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```
Expected: all three jobs green.

- [ ] **Step 3: If a job fails**

- `test_tail_frames_survives_rotation` / `test_tail_frames_rotation_no_loss_when_new_file_outgrows_old` failing on one matrix leg only: re-run once (`gh run rerun <id> --failed`). If it fails twice, read the test (it is a timing-sensitive tail/rotate test) and fix the test's wait, not the product code; do not mark it skipped.
- Import error for `torch`/`onnxscript`: check `https://download.pytorch.org/whl/cpu` has a wheel for the failing Python version; drop that version from the matrix only if no wheel exists.
- Anything else: fix the cause; never add `continue-on-error`.

---

### Task 5: CONTRIBUTING, SECURITY, CHANGELOG

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CHANGELOG.md`

- [ ] **Step 1: CONTRIBUTING.md**

````markdown
# Contributing to Aura

Thanks for your interest. Aura is small and deliberately deterministic; the
bar for changes is "still explainable, still validated".

## Development setup

```sh
git clone https://github.com/amalnathkp13-boop/aura.git && cd aura
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev,board]"
python -m pytest tests/                            # 106 tests, ~30 s
ruff check aura training tests
```

No hardware is needed for the test suite or for reproducing the published
results (see *Reproduce on your PC* in the README). Board-side work needs an
Arduino UNO Q; `deploy/push.sh` and `deploy/install.sh` document the deploy
path.

## Ground rules

- **Tests first.** New behaviour comes with a test; bug fixes come with a
  regression test that fails before the fix.
- **Keep it deterministic.** The detector is threshold-based signal
  processing by design. Learned models are welcome as *experiments* under
  `training/`, not as replacements for the shipped path.
- **Don't inflate claims.** Anything stated in the README or docs must be
  backed by a scored session in `data/validation/` or by the validation
  protocol. Aura claims presence / motion / activity / zones — never imaging,
  pose, identity, or people counts.
- **Attribution stays.** `aura/brain/rfsense/features.py` and
  `classifier.py` are ports of an MIT-licensed upstream; `NOTICE.md` must
  remain accurate and must not be removed.
- **Calibration honesty.** Changes to calibration or fusion must be re-run
  against `data/validation/session-2026-08-23-frames.jsonl` and the numbers
  in the README updated from the tool's output, not edited by hand.

## Pull requests

1. Branch from `main`; keep PRs focused.
2. CI must be green (ruff + pytest on 3.11 and 3.13).
3. Use conventional prefixes in commit subjects: `feat:`, `fix:`, `docs:`,
   `test:`, `chore:`, `ci:`.
4. Describe *what changed in the detector's decisions* if anything did, with
   before/after numbers from `python -m training.validate`.

## Reporting problems

Bugs and questions: GitHub Issues. Security concerns: see `SECURITY.md`.
````

- [ ] **Step 2: SECURITY.md**

```markdown
# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.x | yes |

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository
(*Security → Report a vulnerability*). Do not open a public issue for
security problems. You will get an acknowledgement within a few days.

## Deployment notes

- The dashboard (`aura-face`) listens on `0.0.0.0:8080` **without
  authentication** — it is designed for a trusted home LAN. Do not expose it
  to the internet; put it behind a VPN or reverse proxy with auth if you need
  remote access.
- The Telegram bot token and chat id live in `~/.aura/config.json` on the
  board. Keep that file private; rotate the token with `@BotFather` if it is
  ever exposed.
- Aura never records audio or images. The only stored radio data is RSSI
  (signal strength) with access-point identifiers salted and hashed per
  install.
```

- [ ] **Step 3: CHANGELOG.md**

```markdown
# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-08-25

State submitted to the Arduino Physical AI Challenge India 2026.

### Added
- Deterministic RF presence detector (`rfsense`): per-link features, rule
  classifier, Aura-original multi-link fusion with presence hysteresis.
- Calibration flow ("Learn my room") with walk-phase quality gate and
  calibration-drift detection.
- Zone localisation from per-channel disturbance signatures.
- Guardian modes (Home / Away / Wellness) with Telegram alerts and the
  `aura telegram-connect` one-command setup.
- Live dashboard (RF Sensing Console) and LED-matrix radar on the UNO Q's
  M33 via the Linux↔MCU bridge.
- Published, scored validation session (`data/validation/`) and the scoring
  harness (`training/validate.py`).
- 106 automated tests; CI on Python 3.11 and 3.13.

### Documented
- Validation protocol, data log, spike results, future-work analysis of
  multi-occupant behaviour and coarse occupancy routes.

[1.0.0]: https://github.com/amalnathkp13-boop/aura/releases/tag/v1.0.0
```

- [ ] **Step 4: Commit and push**

```bash
git add CONTRIBUTING.md SECURITY.md CHANGELOG.md
git commit -m "docs: contributing guide, security policy, changelog for 1.0.0"
git push origin main
```

---

### Task 6: README

**Files:**
- Modify: `README.md` (replace whole file; all prose from the current README is preserved, sections are added)

- [ ] **Step 1: Re-run the reproduce command and confirm the numbers match the Global Constraints**

Run:
```bash
python -m training.validate data/validation/session-2026-08-23-frames.jsonl data/validation/timeline.json --cal data/validation/calibration.json
python -m training.validate data/validation/session-2026-08-23-frames.jsonl data/validation/timeline.json --cal data/validation/calibration.json --detector baseline
```
Expected: `presence_acc 0.9489…`, `empty_motion_false_windows 0`, `entries_missed 0`, `entry_latency_s 18.16`; baseline `0.5136…`, `30`, `0`, `33.16`. If they differ, STOP and update the table below from the actual output.

- [ ] **Step 2: Write README.md**

Content (verbatim; the fenced blocks inside are part of the file):

````markdown
# Aura — camera-free presence AI on a bare Arduino UNO Q

[![CI](https://github.com/amalnathkp13-boop/aura/actions/workflows/ci.yml/badge.svg)](https://github.com/amalnathkp13-boop/aura/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-106%20passing-brightgreen.svg)](tests/)
[![Hardware](https://img.shields.io/badge/hardware-Arduino%20UNO%20Q%20only-00979D.svg)](#architecture)

Every Arduino UNO Q already contains an invisible motion sensor: **its own radio**.
Aura turns it on with pure software — privacy-first presence, intrusion, and
wellness sensing for smart homes, with **zero extra hardware, zero cameras,
zero cloud, and zero training data**.

Built for the **Arduino Physical AI Challenge India 2026** (theme: *Smart Homes
& Consumer AI*) by Kumaravel S and Amalnath K P.
**[▶ Demo video](https://drive.google.com/file/d/16GfqoFsQ8vYzgybYod_s7oeFLkfacokY/view)** · [Project report (PDF)](docs/submission/Aura-Project-Report.pdf) · [Validation protocol](docs/validation-protocol.md)

<p align="center">
  <img src="docs/submission/Aura-Dashboard-Console.png" width="760" alt="Aura RF Sensing Console: presence PRESENT, per-link votes, thresholds, zone map">
  <br><em>The RF Sensing Console — every decision traceable to a per-link threshold you calibrated.</em>
</p>

## Contents

- [What it does](#what-it-does)
- [Why it's different](#why-its-different)
- [Results](#results)
- [Reproduce on your PC — no hardware](#reproduce-on-your-pc--no-hardware)
- [Architecture](#architecture)
- [Detection pipeline](#detection-pipeline)
- [Quick start (on the board)](#quick-start-on-the-board)
- [Repository layout](#repository-layout)
- [Validation](#validation) · [Tests](#tests) · [Limitations & future work](#limitations--future-work)
- [Contributing](#contributing) · [License](#license) · [Competition submission](#competition-submission)

## What it does

- **Presence & motion detection** from disturbances people cause in the RF
  environment around the board — the WiFi link to the home hotspot plus every
  access point the radio can hear act as a mesh of invisible tripwires.
- **Zone localization**: after a 2-minute per-spot calibration, Aura labels
  *where* in the room the activity is (e.g. `doorway`, `center`).
- **Guardian modes**: *Home* (ambient awareness), *Away* (intrusion alerts via
  Telegram), *Wellness* (inactivity watch for elder care).
- **Live dashboard**: real detector internals — per-link votes, thresholds,
  vote fractions, an RF disturbance waterfall, a motion spectrogram, and an
  imaging-style radar visualization (deliberately abstract: RSSI carries no
  position information, and Aura never claims otherwise).
- **LED-matrix radar** on the board's front face, driven by the UNO Q's second
  brain (the STM32 M33) over the Linux↔MCU bridge.
- **Self-aware calibration**: a "Learn my room" flow derives per-link
  thresholds with a quality gate, and a drift detector raises a dashboard
  banner when the RF geometry has changed (e.g. the hotspot moved) instead of
  going silently blind.

## Why it's different

| Conventional smart-home sensing | Aura |
|---|---|
| Cameras (privacy risk, creep factor) | No optics at all — physically cannot take a picture |
| PIR / mmWave / BLE beacons (extra hardware) | Bill of materials: the UNO Q itself. Nothing else |
| Cloud AI (subscription, data exfiltration) | 100% on-device; works with the internet down |
| Black-box neural models | Deterministic, explainable signal processing — every decision traceable to a threshold you calibrated |

## Results

Scored live session, 23 Aug 2026, one operator, a real room, the hotspot
phone parked as the far end of the link (`data/validation/`). Numbers are the
output of `training/validate.py` on the published recording — not edited.

| Metric | **Aura** (fused `rfsense`) | Naive single-threshold baseline |
|---|---|---|
| Presence accuracy (294 windows) | **94.9 %** | 51.4 % |
| Motion accuracy (190 windows) | **91.6 %** | 77.9 % |
| False-motion windows in the empty room (0.23 h) | **0** | 30 |
| Doorway entries missed (4 entries) | **0** | 0 |
| Entry latency, windowed tool median | 18.2 s | 33.2 s |

The tool's latency has a ~15 s floor from the analysis window; the dashboard's
first reaction to an entry is faster (features update every ~2 s) and was
stopwatch-assessed during the session — see the report. Presence hysteresis
raised overall accuracy from 89.8 % to 94.9 % without adding a false alarm.

## Reproduce on your PC — no hardware

The scored session, its calibration and its truth timeline are in the repo.
Re-score them through the exact production detector:

```sh
git clone https://github.com/amalnathkp13-boop/aura.git && cd aura
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Aura's fused detector
python -m training.validate data/validation/session-2026-08-23-frames.jsonl data/validation/timeline.json --cal data/validation/calibration.json
# the naive baseline, same data
python -m training.validate data/validation/session-2026-08-23-frames.jsonl data/validation/timeline.json --cal data/validation/calibration.json --detector baseline

python -m pytest tests/        # 106 tests
```

`frames.jsonl` is also a flight recorder: `aura replay --session <file>` streams
any recording back through the live pipeline, so an incident can be re-run
offline through the same code that made the decision.

## Architecture

<p align="center">
  <img src="docs/submission/Aura-System-Diagram.png" width="760" alt="Aura system diagram: ear → brain → face/guardian on the Linux side; LED-matrix radar on the M33">
</p>

<details>
<summary>Text version</summary>

```
             Arduino UNO Q (single device)
┌───────────────────────────────────────────────┐
│ Linux (Debian, Qualcomm QRB)     M33 MCU      │
│                                               │
│  aura-ear ──► frames.jsonl                    │
│  (radio listener, 4 Hz)   │                   │
│                           ▼                   │
│  aura-brain ──► state.json / sense.json       │
│  (feature extraction, │                       │
│   per-link classify,  │        LED matrix     │
│   multi-link fusion)  │        radar sketch   │
│                       ▼            ▲          │
│  aura-face (dashboard) ── HTTP ────┘          │
│  aura-guardian (modes, Telegram alerts)       │
└───────────────────────────────────────────────┘
```

</details>

File-based pipeline of systemd daemons; each stage is independently
restartable and replayable. `frames.jsonl` doubles as a flight recorder — any
live incident can be re-run offline through the exact detector for forensics.

## Detection pipeline

1. **Ear**: samples the connected-link RSSI (32 samples/s via station dump
   under a keep-alive ping) and scans neighbouring APs; writes 4 Hz frames.
2. **Features** (15-s sliding window, per channel): variance, motion-band
   (0.5–2 Hz) and breathing-band (0.1–0.5 Hz) FFT power, CUSUM change-points.
3. **Per-link classification** against calibrated thresholds, with
   cross-receiver agreement.
4. **Multi-link fusion** (Aura-original): every link votes with a stability
   weight; presence needs a strict weighted majority, so one glitching channel
   cannot raise an alarm. Presence holds 120 s past the last motion so a
   still person doesn't read as an empty room.
5. **Zones**: nearest calibrated per-channel disturbance signature
   (log-scaled variance / band-power distance).

The core feature extractor and rule classifier are adapted from an
MIT-licensed upstream project — full attribution, pinned upstream commit, and
license text in [NOTICE.md](NOTICE.md).

## Quick start (on the board)

```sh
sh deploy/push.sh                 # rsync-free tar deploy to ~/aura-src + venv install
sudo deploy/install.sh            # systemd units: aura-ear, aura-brain, aura-face, aura-guardian
# open http://<board>:8080  →  press "Learn my room" (10 min empty + 5 min walk)
sudo systemctl restart aura-brain # load the new calibration
```

Calibration rules that matter (learned the hard way): the hotspot phone is the
far end of the sensor — park it at the far side of the room, at waist height,
and don't touch it afterwards; the walk-phase quality gate refuses a
calibration that can't actually see you walk, and the drift banner tells you
when to redo it. Note the sensing zone includes the doorway — someone
lingering just outside the door is legitimately detected (the zone label will
say so).

## Repository layout

| Path | What it is |
|---|---|
| `aura/` | The product. `ear/` radio listener · `brain/` features, calibration, the `rfsense/` detector · `face/` Flask dashboard + M33 bridge · `guardian/` modes and Telegram · `labeler/` optional PC-side webcam truth-labeller (training-phase only, never on the board) · `cli.py` |
| `board-app/aura-matrix/` | The shipped LED-matrix radar as an Arduino App: Linux-side Python talks to the M33 sketch over RouterBridge |
| `sketch/aura_matrix/` | Earlier standalone serial-transport variant of the same matrix animation, kept for reference |
| `deploy/` | `push.sh` (tar deploy), `install.sh` (systemd units), `fix-net.sh` (hotspot gateway one-shot), `systemd/` |
| `training/` | `validate.py` — the scoring harness behind every number above — plus the retired CNN experiment (`train.py`, `dataset.py`, `label_stream.py`); the shipped detector uses no learned model |
| `data/validation/` | The scored 23-Aug session: frames, calibration, truth timeline, stopwatch taps, run card |
| `docs/` | Validation protocol · data log · day-1 spike results · [future work](docs/future-work.md) · `submission/` (report, diagram, video script) · `superpowers/` (design specs and implementation plans — the project's design history) |
| `tests/` | 106 tests: features, classification, fusion, calibration gates, drift, zones, services, dashboard API |

## Validation

`docs/validation-protocol.md` defines a scripted live session (empty /
entries / sitting / walking, with declared truth timeline);
`training/validate.py` scores recorded frames chronologically and reports
presence accuracy, entry latency, and false-alarm windows per empty hour, for
both the fused detector and a naive baseline. The full session log with phase
boundaries and post-mortem is in [`docs/data-log.md`](docs/data-log.md).

## Tests

106 automated tests cover feature extraction, classification, fusion,
calibration (including the walk gate and drift detection), zones, services,
and the dashboard API. They run on every push (Ubuntu, Python 3.11 and 3.13):

```sh
python -m pytest tests/
```

## Limitations & future work

Aura reports presence, motion, activity and a single zone label — it does
**not** count people. Multi-person behaviour was outside the validation
protocol and is not claimed. [`docs/future-work.md`](docs/future-work.md)
records what the current detector does with 2+ occupants and lays out four
routes toward a *nobody / one / more than one* answer on a bare UNO Q
(multi-zone decomposition, known-device BLE fusion, an ath10k spectral-scan
spike, and a multi-board mesh), in order of attack.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) (setup, ground rules, PR checklist)
and [SECURITY.md](SECURITY.md) (private vulnerability reporting, deployment
notes). Release history is in [CHANGELOG.md](CHANGELOG.md).

## License

MIT (see [LICENSE](LICENSE)). Portions adapted from an MIT-licensed upstream
project — see [NOTICE.md](NOTICE.md).

## Competition submission

Built for the **Arduino Physical AI Challenge India 2026** — category
*Smart Homes & Consumer AI* — by **Kumaravel S** (team lead) and
**Amalnath K P**, Erode, Tamil Nadu. The submission bundle lives in
[`docs/submission/`](docs/submission/): the project report (PDF), the system
diagram, the demo-video script, and the console/board/alert images used in the
report.
````

- [ ] **Step 3: Check every relative link and image path exists**

Run:
```bash
grep -oE '\]\(([^)#h][^)]*)' README.md | sed 's/](//' | sort -u | while read p; do [ -e "$p" ] && echo "ok  $p" || echo "MISSING $p"; done
grep -oE 'src="[^"]+"' README.md | sed 's/src="//;s/"//' | while read p; do [ -e "$p" ] && echo "ok  $p" || echo "MISSING $p"; done
```
Expected: no `MISSING` lines.

- [ ] **Step 4: Commit and push; confirm GitHub renders it**

```bash
git add README.md
git commit -m "docs: README — badges, console hero, results table, PC reproduction, repository layout"
git push origin main
gh api repos/amalnathkp13-boop/aura/readme --jq .name
```
Expected: `README.md`. Open https://github.com/amalnathkp13-boop/aura and confirm the hero image, diagram and CI badge render.

---

### Task 7: GitHub repository settings

**Files:** none (GitHub-side).

- [ ] **Step 1: Disable unused tabs, set homepage, enable private vulnerability reporting**

```bash
gh repo edit amalnathkp13-boop/aura --enable-wiki=false --enable-projects=false --homepage "https://drive.google.com/file/d/16GfqoFsQ8vYzgybYod_s7oeFLkfacokY/view"
gh api -X PUT repos/amalnathkp13-boop/aura/private-vulnerability-reporting
```
Expected: second command returns no body (HTTP 204).

- [ ] **Step 2: Verify**

```bash
gh repo view amalnathkp13-boop/aura --json hasWikiEnabled,hasProjectsEnabled,homepageUrl,licenseInfo --jq '{wiki:.hasWikiEnabled,projects:.hasProjectsEnabled,homepage:.homepageUrl,license:.licenseInfo.name}'
gh api repos/amalnathkp13-boop/aura/private-vulnerability-reporting --jq .enabled
```
Expected: `wiki false`, `projects false`, homepage = the video URL, `license "MIT License"`, `enabled true`. (License detection can lag a few minutes after Task 1's push; re-check if still "Other".)

- [ ] **Step 3: Tell the user the one UI-only step**

Social preview image: *Settings → General → Social preview → Upload* `docs/submission/Aura-Dashboard-Console.png` (1250×1255; GitHub recommends 1280×640 — acceptable, it letterboxes).

---

### Task 8: Release v1.0.0

**Files:** none (git tag + GitHub Release).

- [ ] **Step 1: Confirm main is clean and CI is green on HEAD**

```bash
git status --short            # expect empty
git fetch origin && git rev-parse --short HEAD origin/main    # identical
gh run list --workflow ci.yml --limit 1 --json conclusion --jq '.[0].conclusion'   # success
```

- [ ] **Step 2: Tag and push**

```bash
git tag -a v1.0.0 -m "v1.0.0 — state submitted to the Arduino Physical AI Challenge India 2026"
git push origin v1.0.0
```

- [ ] **Step 3: Create the release with public assets only**

Write the notes to a scratchpad file (never into the repo):

```markdown
State submitted to the **Arduino Physical AI Challenge India 2026** (Smart Homes & Consumer AI).

**Camera-free presence sensing on a bare Arduino UNO Q** — the board's own radio, deterministic signal processing, no extra hardware, no cloud, no training data.

### Validated (live session, 23 Aug 2026)
| Metric | Aura | Naive baseline |
|---|---|---|
| Presence accuracy | **94.9 %** | 51.4 % |
| False-motion windows, empty room | **0** | 30 |
| Doorway entries detected | **4 / 4** | 4 / 4 |

Reproduce on any PC: see *Reproduce on your PC — no hardware* in the README.

### Assets
- `Aura-Project-Report.pdf` — project report
- `Aura-System-Diagram.png` — system diagram
- Demo video: https://drive.google.com/file/d/16GfqoFsQ8vYzgybYod_s7oeFLkfacokY/view

Full change list: `CHANGELOG.md`.
```

```bash
gh release create v1.0.0 --title "v1.0.0 — competition submission" --notes-file "<scratchpad>/release-notes.md" docs/submission/Aura-Project-Report.pdf docs/submission/Aura-System-Diagram.png
gh release view v1.0.0 --json tagName,assets --jq '{tag:.tagName,assets:[.assets[].name]}'
```
Expected: `assets` = the two files. **Never** attach `Aura-Project-Report-Official.pdf` or the docx (personal emails).

---

### Task 9: Final verification sweep

- [ ] **Step 1: Run the checks from the spec**

```bash
python -m pytest tests/                                   # 106 passed
python -m ruff check aura training tests                  # All checks passed!
gh api repos/amalnathkp13-boop/aura/license --jq .license.spdx_id    # MIT
gh run list --workflow ci.yml --limit 2 --json conclusion,headBranch --jq '.[]'   # success on main and on v1.0.0
git grep -nIE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' -- ':!*.jsonl' | grep -v 'arduino@xfiles.local'   # expect nothing new
git status --short && git log --oneline origin/main..HEAD   # clean, nothing unpushed
```

- [ ] **Step 2: Report to the user**

List: the release URL, CI badge status, license detection result, the social-preview manual step, and anything that deviated from this plan.
