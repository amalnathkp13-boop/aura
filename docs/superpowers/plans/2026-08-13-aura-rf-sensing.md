# Aura Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a bare Arduino UNO Q into a camera-free presence/intrusion/wellness sensor using only its own WiFi/BT radios + on-device AI, submitted to the Arduino Physical AI Challenge India 2026.

**Architecture:** File-based pipeline of four daemons on the board's Linux side (RF Ear → Aura Brain → Face + Guardian) plus an LED-matrix sketch on the M33 core. All Python is developed and unit-tested on the Windows PC against recorded/synthetic fixtures, then deployed to the board. Training (PyTorch → ONNX) happens on the PC; inference (ONNX Runtime) on the board.

**Tech Stack:** Python 3.9+ (numpy, flask, requests, onnxruntime, pyserial), PyTorch + ONNX (PC only), ultralytics YOLO (PC labeling only), Arduino sketch (C++) for the M33, systemd, pytest.

## Global Constraints

- **Shipped product = Arduino UNO Q only.** No external sensors/boards. USB webcam is a training-phase labeling tool only and runs on the PC.
- **Honest claims:** "RF sensing with imaging-style visualization" — never "through-wall imaging". No CSI (unavailable on this chip).
- **Privacy by design:** all MAC addresses salted-SHA1-hashed at capture; no raw MACs ever written to disk.
- **All processing on-device / LAN-only**, except opt-in Telegram alerts.
- **IPC is file-based** via a spool dir (`AURA_HOME`, default `~/.aura`): `frames.jsonl`, `state.json` (atomic replace), `features.jsonl`, `mode.json`, `alerts.jsonl`, `calibration.json`. No sockets/websockets.
- **Model input contract:** float32 matrix `(17, 60)` = 16 top-stable WiFi links + 1 connected-link stream, resampled to 60 samples over a 15 s window, median-centered, ÷5.0, clipped ±4.
- **Frame cadence:** target 4 Hz, design tolerates ≥1 Hz (window resampling decouples model from cadence).
- **Feature-freeze gate: day 13.** Cut-list order: BLE fusion first, Wellness mode second. Intrusion + dashboard + matrix are core.
- Dev on Windows PC (`C:\Users\ASUS\aura`), deploy to board over SSH/scp. Commit after every task; never `git add -A` (stage explicit paths).
- Python must run on both Windows (tests) and Debian (board): use `pathlib`, no OS-specific calls outside `aura/ear/` pollers and `deploy/`.

---

### Task 1: Repo scaffold + Python package + test harness

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `README.md`, `aura/__init__.py`, `aura/config.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `aura.config.Config` dataclass with `.load(path=None)` → fields `aura_home: Path`, `salt: str`, `frame_hz: float`, `scan_interval: float`, `top_k: int` (=16), `window_seconds: float` (=15), `telegram_token: str`, `telegram_chat_id: str`, `serial_port: str`, `gateway_ip: str`. `Config.load()` creates `AURA_HOME` and a persisted random salt on first run.

- [ ] **Step 1: Write scaffold files**

`pyproject.toml`:
```toml
[project]
name = "aura"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = ["numpy", "flask", "requests"]

[project.optional-dependencies]
board = ["onnxruntime", "pyserial"]
train = ["torch", "onnx", "onnxruntime", "ultralytics", "opencv-python"]
dev = ["pytest"]

[project.scripts]
aura = "aura.cli:main"

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["aura*"]
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
data/sessions/
*.npz
.pytest_cache/
```

`README.md`: one paragraph — the one-line pitch from the spec + "see docs/superpowers/specs/ for design".

`aura/__init__.py`: empty. Also create empty `tests/__init__.py` (later tasks import helpers across test modules, e.g. `from tests.test_training import _make_session`).

- [ ] **Step 2: Write the failing test**

`tests/test_config.py`:
```python
import json
from pathlib import Path
from aura.config import Config

def test_load_creates_home_and_salt(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path / "home"))
    cfg = Config.load()
    assert cfg.aura_home.is_dir()
    assert len(cfg.salt) >= 16
    cfg2 = Config.load()
    assert cfg2.salt == cfg.salt  # persisted

def test_load_reads_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    (tmp_path / "config.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text(json.dumps({"frame_hz": 2.0, "gateway_ip": "192.168.1.1"}))
    cfg = Config.load()
    assert cfg.frame_hz == 2.0
    assert cfg.gateway_ip == "192.168.1.1"
    assert cfg.top_k == 16
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd C:\Users\ASUS\aura && python -m venv .venv && .venv\Scripts\pip install -e .[dev] && .venv\Scripts\python -m pytest tests/test_config.py -v`
Expected: FAIL / ImportError (`aura.config` missing)

- [ ] **Step 4: Implement `aura/config.py`**

```python
import json, os, secrets
from dataclasses import dataclass, fields
from pathlib import Path

@dataclass
class Config:
    aura_home: Path
    salt: str
    frame_hz: float = 4.0
    scan_interval: float = 3.0
    top_k: int = 16
    window_seconds: float = 15.0
    telegram_token: str = ""
    telegram_chat_id: str = ""
    serial_port: str = ""
    gateway_ip: str = ""

    @classmethod
    def load(cls, path: Path = None) -> "Config":
        home = Path(os.environ.get("AURA_HOME", Path.home() / ".aura"))
        home.mkdir(parents=True, exist_ok=True)
        salt_file = home / "salt"
        if not salt_file.exists():
            salt_file.write_text(secrets.token_hex(16))
        overrides = {}
        cfg_file = path or (home / "config.json")
        if cfg_file.exists():
            overrides = json.loads(cfg_file.read_text())
        known = {f.name for f in fields(cls)}
        overrides = {k: v for k, v in overrides.items() if k in known}
        return cls(aura_home=home, salt=salt_file.read_text().strip(), **overrides)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_config.py -v`
Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore README.md aura/__init__.py aura/config.py tests/test_config.py
git commit -m "feat: scaffold aura package with config"
```

---

### Task 2: Board bring-up + RF feasibility spike (board-side, no TDD — spike)

**Files:**
- Create: `docs/spike-results.md`, `deploy/push.sh`

**Interfaces:**
- Produces: `docs/spike-results.md` with measured values later tasks read as config: achievable `scan_interval`, link-poll rate, BLE availability, board SSH `user@host`, Linux↔M33 channel (serial device path OR App Lab Bridge API names), LED-matrix draw API (exact include + call from the on-board App Lab example).

- [ ] **Step 1: Get shell on the board.** Connect UNO Q to your WiFi using Arduino App Lab's setup flow (USB-C to PC first boot). Find its IP from your router's client list. `ssh <user>@<ip>` (user/password per App Lab's device page — record them in spike doc, NOT in git if sensitive; record only `user@ip` placeholder-free form you actually used).
- [ ] **Step 2: Inventory the OS.** Run and paste outputs into `docs/spike-results.md`:
```bash
uname -a && cat /etc/os-release | head -2
python3 --version; which iw ip ping bluetoothctl
iw dev                      # note wlan interface name
ip route | grep default     # note gateway IP → config.json gateway_ip
ls /dev/ttyACM* /dev/ttyUSB* /dev/ttyMSM* 2>/dev/null   # candidate M33 serial links
```
- [ ] **Step 3: Measure WiFi scan rate.** (replace `wlan0` with real name)
```bash
for i in 1 2 3 4 5; do /usr/bin/time -f "%e s" sudo iw dev wlan0 scan 2>&1 | tail -1; done
sudo iw dev wlan0 scan | grep -c "^BSS"     # visible AP count
```
Record: median scan seconds, AP count. Decision: `scan_interval = max(2.0, ceil(median)+0.5)`.
- [ ] **Step 4: Measure link-stats rate.**
```bash
ping -i 0.2 -c 20 <gateway_ip> > /dev/null &   # traffic generator
for i in $(seq 20); do sudo iw dev wlan0 station dump | grep "signal:"; sleep 0.1; done
```
Record: does `signal:` change across samples (yes/no), sustainable poll Hz (target ≥5 Hz).
- [ ] **Step 5: Check BLE scan.**
```bash
timeout 15 bluetoothctl scan on | grep -m 5 RSSI
```
Record: works yes/no. If no → BLE poller ships disabled (it is first on the cut-list anyway).
- [ ] **Step 6: Find the Linux↔M33 path + matrix API.** In App Lab on the board, open the built-in examples; locate (a) any example whose Python app talks to its sketch (record the exact import + call, e.g. the Bridge/RPC helper it uses), and (b) the LED-matrix example (record the exact `#include` and the frame-draw call for the 8×13 matrix). Paste both verbatim into `docs/spike-results.md`.
- [ ] **Step 7: Write `deploy/push.sh`** (PC → board sync; adjust user@ip from Step 1):
```bash
#!/bin/sh
# usage: sh deploy/push.sh <user@boardip>
set -e
DEST=${1:?user@host}
scp -r aura pyproject.toml "$DEST":~/aura-src/
ssh "$DEST" "cd ~/aura-src && pip3 install -e .[board] --break-system-packages 2>/dev/null || pip3 install -e .[board]"
```
- [ ] **Step 8: Verify frame-rate feasibility.** Compute worst-case frame cadence from measurements (frames are assembled from cached poller values, so cadence = configured `frame_hz` regardless; the real question is scan freshness). Record verdict line in spike doc: `PASS` if scan_interval ≤ 6 s and station-dump signal updates with traffic; else record fallback plan (frame_hz 1.0, longer windows).
- [ ] **Step 9: Commit**
```bash
git add docs/spike-results.md deploy/push.sh
git commit -m "docs: RF feasibility spike results + board push script"
```

---

### Task 3: RF frame model + session I/O + MAC hashing

**Files:**
- Create: `aura/frames.py`, `tests/test_frames.py`

**Interfaces:**
- Produces: `RFFrame` dataclass: `ts: float`, `wifi: dict[str, float]` (hashed-bssid → dBm), `link: list[float]`, `ble: dict[str, float]`; `hash_mac(mac: str, salt: str) -> str` (8 hex chars, uppercase-insensitive); `append_frame(path: Path, f: RFFrame) -> None`; `read_frames(path: Path) -> list[RFFrame]`; `tail_frames(path: Path, poll_s: float = 0.25)` generator yielding new frames forever (used by Brain).

- [ ] **Step 1: Write the failing test**

`tests/test_frames.py`:
```python
from aura.frames import RFFrame, hash_mac, append_frame, read_frames

def test_hash_mac_stable_and_case_insensitive():
    a = hash_mac("AA:BB:CC:DD:EE:FF", "salt1")
    b = hash_mac("aa:bb:cc:dd:ee:ff", "salt1")
    assert a == b and len(a) == 8
    assert hash_mac("AA:BB:CC:DD:EE:FF", "salt2") != a

def test_roundtrip(tmp_path):
    p = tmp_path / "frames.jsonl"
    f1 = RFFrame(ts=100.0, wifi={"ab12cd34": -60.0}, link=[-55.0, -56.0], ble={})
    f2 = RFFrame(ts=100.25, wifi={"ab12cd34": -61.0}, link=[-55.5], ble={"ffee0011": -70.0})
    append_frame(p, f1); append_frame(p, f2)
    out = read_frames(p)
    assert out == [f1, f2]

def test_read_skips_corrupt_lines(tmp_path):
    p = tmp_path / "frames.jsonl"
    append_frame(p, RFFrame(ts=1.0, wifi={}, link=[], ble={}))
    with open(p, "a") as fh:
        fh.write("{corrupt\n")
    append_frame(p, RFFrame(ts=2.0, wifi={}, link=[], ble={}))
    assert [f.ts for f in read_frames(p)] == [1.0, 2.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_frames.py -v` → FAIL (module missing)

- [ ] **Step 3: Implement `aura/frames.py`**

```python
import hashlib, json, time
from dataclasses import dataclass, asdict, field
from pathlib import Path

@dataclass
class RFFrame:
    ts: float
    wifi: dict = field(default_factory=dict)
    link: list = field(default_factory=list)
    ble: dict = field(default_factory=dict)

def hash_mac(mac: str, salt: str) -> str:
    return hashlib.sha1((mac.lower() + salt).encode()).hexdigest()[:8]

def append_frame(path: Path, f: RFFrame) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(f)) + "\n")

def _parse(line: str):
    try:
        d = json.loads(line)
        return RFFrame(ts=d["ts"], wifi=d.get("wifi", {}), link=d.get("link", []), ble=d.get("ble", {}))
    except (json.JSONDecodeError, KeyError):
        return None

def read_frames(path: Path):
    if not Path(path).exists():
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        f = _parse(line)
        if f:
            out.append(f)
    return out

def tail_frames(path: Path, poll_s: float = 0.25):
    pos = 0
    while True:
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as fh:
                fh.seek(pos)
                for line in fh:
                    if not line.endswith("\n"):
                        break
                    pos = fh.tell()
                    f = _parse(line)
                    if f:
                        yield f
        time.sleep(poll_s)
```

- [ ] **Step 4: Run tests** → 3 PASS
- [ ] **Step 5: Commit**
```bash
git add aura/frames.py tests/test_frames.py
git commit -m "feat: RF frame model, hashed MACs, JSONL session io"
```

---

### Task 4: WiFi/BLE text parsers

**Files:**
- Create: `aura/ear/__init__.py`, `aura/ear/parse.py`, `tests/test_parse.py`, `tests/fixtures/iw_scan.txt`, `tests/fixtures/station_dump.txt`

**Interfaces:**
- Produces: `parse_scan(text: str) -> dict[str, float]` (raw bssid → dBm), `parse_station_signal(text: str) -> float | None`, `parse_bluetoothctl_line(line: str) -> tuple[str, float] | None`. Raw MACs here; hashing happens in the Ear (Task 5).

- [ ] **Step 1: Create fixtures** (verbatim standard `iw` output shape; after Task 2, replace with a real capture from the board if it differs — parsers must still pass)

`tests/fixtures/iw_scan.txt`:
```
BSS aa:bb:cc:dd:ee:01(on wlan0)
	TSF: 12345 usec
	freq: 2437
	signal: -58.00 dBm
	SSID: HomeNet
BSS aa:bb:cc:dd:ee:02(on wlan0) -- associated
	freq: 5180
	signal: -71.50 dBm
	SSID: Neighbor5G
BSS aa:bb:cc:dd:ee:03(on wlan0)
	freq: 2412
	SSID: NoSignalAP
```

`tests/fixtures/station_dump.txt`:
```
Station 11:22:33:44:55:66 (on wlan0)
	inactive time:	10 ms
	rx bytes:	123456
	signal:  	-54 [-54, -60] dBm
	signal avg:	-55 dBm
	tx bitrate:	433.3 MBit/s
```

- [ ] **Step 2: Write the failing test**

`tests/test_parse.py`:
```python
from pathlib import Path
from aura.ear.parse import parse_scan, parse_station_signal, parse_bluetoothctl_line

FIX = Path(__file__).parent / "fixtures"

def test_parse_scan():
    out = parse_scan((FIX / "iw_scan.txt").read_text())
    assert out == {"aa:bb:cc:dd:ee:01": -58.0, "aa:bb:cc:dd:ee:02": -71.5}

def test_parse_scan_empty():
    assert parse_scan("") == {}

def test_parse_station_signal():
    assert parse_station_signal((FIX / "station_dump.txt").read_text()) == -54.0
    assert parse_station_signal("no stations") is None

def test_parse_ble_line():
    assert parse_bluetoothctl_line("[CHG] Device 4C:87:5D:11:22:33 RSSI: -67") == ("4c:87:5d:11:22:33", -67.0)
    assert parse_bluetoothctl_line("[NEW] Device 4C:87:5D:11:22:33 SomeName") is None
    assert parse_bluetoothctl_line("") is None
```

- [ ] **Step 3: Run** → FAIL (module missing)

- [ ] **Step 4: Implement `aura/ear/parse.py`** (and empty `aura/ear/__init__.py`)

```python
import re

_BSS = re.compile(r"^BSS ([0-9a-f:]{17})", re.M | re.I)
_SIG = re.compile(r"signal: (-?\d+(?:\.\d+)?) dBm")
_STA_SIG = re.compile(r"signal:\s+(-?\d+)")
_BLE = re.compile(r"Device ([0-9A-Fa-f:]{17}) RSSI: (-?\d+)")

def parse_scan(text: str) -> dict:
    out = {}
    blocks = _BSS.split(text)
    for i in range(1, len(blocks), 2):
        m = _SIG.search(blocks[i + 1])
        if m:
            out[blocks[i].lower()] = float(m.group(1))
    return out

def parse_station_signal(text: str):
    m = _STA_SIG.search(text)
    return float(m.group(1)) if m else None

def parse_bluetoothctl_line(line: str):
    m = _BLE.search(line)
    return (m.group(1).lower(), float(m.group(2))) if m else None
```

- [ ] **Step 5: Run** → 4 PASS
- [ ] **Step 6: Commit**
```bash
git add aura/ear/__init__.py aura/ear/parse.py tests/test_parse.py tests/fixtures/iw_scan.txt tests/fixtures/station_dump.txt
git commit -m "feat: iw/bluetoothctl output parsers"
```

---

### Task 5: RF Ear daemon (pollers + frame assembler + replay)

**Files:**
- Create: `aura/ear/ear.py`, `tests/test_ear.py`

**Interfaces:**
- Consumes: `Config`, `RFFrame`, `append_frame`, parsers.
- Produces: `Ear(cfg, wifi_poller, link_poller, ble_poller)` with `.run_forever(out_path, stop_event)` writing one frame per `1/cfg.frame_hz` s; poller protocol = object with `.latest() -> dict|list` and `.start()/.stop()`; real pollers `ScanPoller(cfg)`, `LinkPoller(cfg)`, `BlePoller(cfg)` (subprocess-based, board-only, excluded from PC unit tests); `replay(session_path, out_path, speed)` copies a recorded session onto the live spool with rewritten timestamps — the Brain cannot tell replay from live.

- [ ] **Step 1: Write the failing test** (fake pollers; verifies cadence, hashing, rolling write)

`tests/test_ear.py`:
```python
import threading, time
from pathlib import Path
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
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement `aura/ear/ear.py`**

```python
import subprocess, threading, time
from pathlib import Path
from aura.frames import RFFrame, append_frame, read_frames, hash_mac
from aura.ear.parse import parse_scan, parse_station_signal, parse_bluetoothctl_line

class Ear:
    def __init__(self, cfg, wifi_poller, link_poller, ble_poller):
        self.cfg = cfg
        self.wifi, self.link, self.ble = wifi_poller, link_poller, ble_poller

    def run_forever(self, out_path: Path, stop_event: threading.Event):
        for p in (self.wifi, self.link, self.ble):
            p.start()
        period = 1.0 / self.cfg.frame_hz
        try:
            while not stop_event.is_set():
                t0 = time.time()
                f = RFFrame(
                    ts=t0,
                    wifi={hash_mac(m, self.cfg.salt): v for m, v in (self.wifi.latest() or {}).items()},
                    link=list(self.link.latest() or []),
                    ble={hash_mac(m, self.cfg.salt): v for m, v in (self.ble.latest() or {}).items()},
                )
                append_frame(out_path, f)
                _rotate(out_path)
                stop_event.wait(max(0.0, period - (time.time() - t0)))
        finally:
            for p in (self.wifi, self.link, self.ble):
                p.stop()

def _rotate(path: Path, max_bytes: int = 50_000_000):
    if path.exists() and path.stat().st_size > max_bytes:
        path.rename(path.with_suffix(".jsonl.old"))

def replay(session_path: Path, out_path: Path, speed: float = 1.0):
    frames = read_frames(session_path)
    if not frames:
        return
    base = frames[0].ts
    start = time.time()
    for f in frames:
        delay = (f.ts - base) / speed - (time.time() - start)
        if delay > 0:
            time.sleep(delay)
        append_frame(out_path, RFFrame(ts=time.time(), wifi=f.wifi, link=f.link, ble=f.ble))

# ---- real pollers (board-only; no unit tests — exercised by `aura record` on the board) ----

class _SubprocessPoller(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._latest, self._stop = None, threading.Event()
    def latest(self): return self._latest
    def stop(self): self._stop.set()

class ScanPoller(_SubprocessPoller):
    def __init__(self, cfg):
        super().__init__(); self.cfg = cfg
    def run(self):
        while not self._stop.is_set():
            try:
                out = subprocess.run(["sudo", "iw", "dev", "wlan0", "scan"],
                                     capture_output=True, text=True, timeout=15).stdout
                self._latest = parse_scan(out)
            except Exception:
                pass
            self._stop.wait(self.cfg.scan_interval)

class LinkPoller(_SubprocessPoller):
    def __init__(self, cfg):
        super().__init__(); self.cfg = cfg; self._buf = []
        self._ping = None
    def run(self):
        if self.cfg.gateway_ip:
            self._ping = subprocess.Popen(["ping", "-i", "0.2", self.cfg.gateway_ip],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while not self._stop.is_set():
            try:
                out = subprocess.run(["sudo", "iw", "dev", "wlan0", "station", "dump"],
                                     capture_output=True, text=True, timeout=5).stdout
                s = parse_station_signal(out)
                if s is not None:
                    self._buf = (self._buf + [s])[-8:]
                    self._latest = list(self._buf)
            except Exception:
                pass
            self._stop.wait(0.15)
    def stop(self):
        super().stop()
        if self._ping:
            self._ping.terminate()

class BlePoller(_SubprocessPoller):
    def run(self):
        try:
            proc = subprocess.Popen(["bluetoothctl", "scan", "on"], stdout=subprocess.PIPE, text=True)
        except FileNotFoundError:
            return
        devices = {}
        for line in proc.stdout:
            if self._stop.is_set():
                break
            hit = parse_bluetoothctl_line(line)
            if hit:
                devices[hit[0]] = hit[1]
                self._latest = dict(devices)
        proc.terminate()
```

(`ScanPoller`/`LinkPoller` hardcode `wlan0`; if the spike found a different name, change it here and note it in `docs/spike-results.md`.)

- [ ] **Step 4: Run** → 2 PASS
- [ ] **Step 5: Smoke on board** (after `sh deploy/push.sh <user@ip>`): `ssh <user@ip> "cd ~/aura-src && python3 - <<'EOF'
import threading, time
from pathlib import Path
from aura.config import Config
from aura.ear.ear import Ear, ScanPoller, LinkPoller, BlePoller
cfg = Config.load()
stop = threading.Event()
ear = Ear(cfg, ScanPoller(cfg), LinkPoller(cfg), BlePoller())
t = threading.Thread(target=ear.run_forever, args=(cfg.aura_home/'frames.jsonl', stop)); t.start()
time.sleep(20); stop.set(); t.join()
print(sum(1 for _ in open(cfg.aura_home/'frames.jsonl')))
EOF"`
Expected: ≥ 20 lines and nonempty `wifi` dicts (open the file and eyeball).
- [ ] **Step 6: Commit**
```bash
git add aura/ear/ear.py tests/test_ear.py
git commit -m "feat: RF Ear daemon with pollers, rotation, replay"
```

---

### Task 6: Labeler (PC-side, webcam → labels.jsonl)

**Files:**
- Create: `aura/labeler/__init__.py`, `aura/labeler/labeler.py`, `tests/test_labeler.py`

**Interfaces:**
- Produces: label record JSONL `{"ts": float, "person": 0|1, "motion": float}` (motion = fraction of pixels changed, 0..1); `write_label(path, ts, person, motion)`; `read_labels(path) -> list[dict]`; `run_labeler(out_path, camera_index=0)` loop (1 Hz sampling, YOLO person detection + gray frame-diff). Time source is `time.time()` on the PC — **PC and board must both be NTP-synced** (verify: `ssh <user@ip> date +%s` vs PC `python -c "import time;print(int(time.time()))"`, offset ≤ 1 s).

- [ ] **Step 1: Write the failing test** (io only; the camera loop is smoke-tested live)

`tests/test_labeler.py`:
```python
from aura.labeler.labeler import write_label, read_labels

def test_label_roundtrip(tmp_path):
    p = tmp_path / "labels.jsonl"
    write_label(p, 100.0, 1, 0.25)
    write_label(p, 101.0, 0, 0.0)
    out = read_labels(p)
    assert out == [{"ts": 100.0, "person": 1, "motion": 0.25},
                   {"ts": 101.0, "person": 0, "motion": 0.0}]
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement `aura/labeler/labeler.py`** (+ empty `__init__.py`)

```python
import json, time
from pathlib import Path

def write_label(path: Path, ts: float, person: int, motion: float):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": ts, "person": person, "motion": round(motion, 4)}) + "\n")

def read_labels(path: Path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out

def run_labeler(out_path: Path, camera_index: int = 0):
    import cv2
    import numpy as np
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    cap = cv2.VideoCapture(camera_index)
    prev = None
    print("Labeler running — Ctrl+C to stop")
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(1); continue
        gray = cv2.cvtColor(cv2.resize(frame, (320, 240)), cv2.COLOR_BGR2GRAY)
        motion = 0.0
        if prev is not None:
            motion = float((cv2.absdiff(gray, prev) > 25).mean())
        prev = gray
        res = model.predict(frame, classes=[0], conf=0.5, verbose=False)
        person = int(len(res[0].boxes) > 0)
        write_label(out_path, time.time(), person, motion)
        time.sleep(1.0)
```

- [ ] **Step 4: Run test** → PASS. Then live smoke (webcam plugged into PC): `.venv\Scripts\pip install -e .[train] && .venv\Scripts\python -c "from aura.labeler.labeler import run_labeler; from pathlib import Path; run_labeler(Path('data/smoke_labels.jsonl'))"` — walk in/out of frame ~60 s, Ctrl+C, open the file: `person` flips 1/0 correctly, `motion` rises when moving. Delete `data/smoke_labels.jsonl`.
- [ ] **Step 5: Commit**
```bash
git add aura/labeler/__init__.py aura/labeler/labeler.py tests/test_labeler.py
git commit -m "feat: webcam labeler (training-phase only)"
```

---

### Task 7: Feature pipeline (window → model matrix + summary stats)

**Files:**
- Create: `aura/brain/__init__.py`, `aura/brain/features.py`, `tests/test_features.py`

**Interfaces:**
- Consumes: `RFFrame` list.
- Produces: `select_links(frames, k=16) -> list[str]` (ranked by presence-count desc, then id for determinism); `build_matrix(frames, link_ids, out_len=60) -> np.ndarray float32 (len(link_ids)+1, out_len)` — per-channel: forward-filled series resampled to `out_len`, median-centered, ÷5.0, clipped ±4 (last row = connected-link stream, mean of samples per frame); `summary(matrix) -> dict` with `motion_energy: float` (mean over channels of std of first-difference), `band_energy: float` (mean 0.5–3 Hz power fraction, assuming the 60 samples span 15 s), `xcorr: float` (mean abs pairwise corr of first-differences of the 5 highest-variance channels). All pure numpy, no I/O.

- [ ] **Step 1: Write the failing test** (synthetic still vs. moving separation — the core physics claim, in a test)

`tests/test_features.py`:
```python
import numpy as np
from aura.frames import RFFrame
from aura.brain.features import select_links, build_matrix, summary

def _frames(n, jitter, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        wobble = jitter * np.sin(i / 3.0) + rng.normal(0, jitter / 2)
        out.append(RFFrame(ts=i * 0.25,
                           wifi={"aaaaaaaa": -60 + wobble, "bbbbbbbb": -70 + wobble * 0.8},
                           link=[-50 + wobble], ble={}))
    return out

def test_select_links_ranks_by_presence():
    frames = _frames(10, 0)
    frames[0].wifi["cccccccc"] = -80.0  # seen once
    ids = select_links(frames, k=2)
    assert ids == ["aaaaaaaa", "bbbbbbbb"]

def test_build_matrix_shape_and_norm():
    m = build_matrix(_frames(60, 1.0), ["aaaaaaaa", "bbbbbbbb"], out_len=60)
    assert m.shape == (3, 60) and m.dtype == np.float32
    assert np.all(np.abs(m) <= 4.0)
    assert abs(np.median(m[0])) < 0.1  # centered

def test_build_matrix_handles_missing_link(tmp_path):
    frames = _frames(60, 1.0)
    m = build_matrix(frames, ["aaaaaaaa", "not_seen1"], out_len=60)
    assert m.shape == (3, 60)
    assert np.all(m[1] == 0)  # absent link -> zeros

def test_summary_separates_still_from_moving():
    still = summary(build_matrix(_frames(60, 0.3), ["aaaaaaaa", "bbbbbbbb"]))
    moving = summary(build_matrix(_frames(60, 4.0, seed=1), ["aaaaaaaa", "bbbbbbbb"]))
    assert moving["motion_energy"] > 2 * still["motion_energy"]
    assert 0 <= still["band_energy"] <= 1
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement `aura/brain/features.py`** (+ empty `__init__.py`)

```python
from collections import Counter
import numpy as np

def select_links(frames, k: int = 16):
    counts = Counter()
    for f in frames:
        counts.update(f.wifi.keys())
    return [bid for bid, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:k]]

def _series(frames, bid):
    vals, last = [], np.nan
    for f in frames:
        last = f.wifi.get(bid, last)
        vals.append(last)
    return np.array(vals, dtype=np.float64)

def _link_series(frames):
    vals, last = [], np.nan
    for f in frames:
        if f.link:
            last = float(np.mean(f.link))
        vals.append(last)
    return np.array(vals, dtype=np.float64)

def _norm(x, out_len):
    if np.all(np.isnan(x)):
        return np.zeros(out_len, dtype=np.float32)
    idx = np.arange(len(x), dtype=np.float64)
    good = ~np.isnan(x)
    x = np.interp(idx, idx[good], x[good])
    x = np.interp(np.linspace(0, len(x) - 1, out_len), idx, x)
    x = (x - np.median(x)) / 5.0
    return np.clip(x, -4, 4).astype(np.float32)

def build_matrix(frames, link_ids, out_len: int = 60):
    rows = [_norm(_series(frames, bid), out_len) for bid in link_ids]
    rows.append(_norm(_link_series(frames), out_len))
    return np.stack(rows)

def summary(matrix, window_seconds: float = 15.0):
    diffs = np.diff(matrix, axis=1)
    motion_energy = float(np.mean(np.std(diffs, axis=1)))
    fs = matrix.shape[1] / window_seconds
    freqs = np.fft.rfftfreq(matrix.shape[1], d=1.0 / fs)
    power = np.abs(np.fft.rfft(matrix, axis=1)) ** 2
    band = (freqs >= 0.5) & (freqs <= 3.0)
    total = power[:, 1:].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(total > 0, power[:, band].sum(axis=1) / total, 0.0)
    band_energy = float(np.mean(frac))
    var = np.var(diffs, axis=1)
    top = diffs[np.argsort(var)[-5:]]
    if top.shape[0] >= 2 and np.all(np.std(top, axis=1) > 0):
        c = np.corrcoef(top)
        xcorr = float(np.mean(np.abs(c[np.triu_indices_from(c, 1)])))
    else:
        xcorr = 0.0
    return {"motion_energy": motion_energy, "band_energy": band_energy, "xcorr": xcorr}
```

- [ ] **Step 4: Run** → 4 PASS
- [ ] **Step 5: Commit**
```bash
git add aura/brain/__init__.py aura/brain/features.py tests/test_features.py
git commit -m "feat: window feature pipeline (matrix + summary stats)"
```

---

### Task 8: Baseline detector + calibration

**Files:**
- Create: `aura/brain/baseline.py`, `aura/brain/calibrate.py`, `tests/test_baseline.py`

**Interfaces:**
- Produces: `calibration.json` schema `{"link_ids": [...16 ids], "empty_p995": float, "activity_scale": float}`; `calibrate_empty(frames, k=16) -> dict` (selects links, sets `empty_p995` = 99.5th percentile of `motion_energy` over 15 s windows stepped every 5 s); `calibrate_walk(frames, cal: dict) -> dict` (adds `activity_scale` = median walking `motion_energy`; raises `ValueError("walk energy not above empty threshold — recheck placement")` if median ≤ `empty_p995`); `Baseline(cal)` with `.update(matrix_summary: dict, ts: float) -> dict` returning `{"presence": 0|1, "motion": 0|1, "activity": float 0..100}` — motion = `motion_energy > empty_p995`; presence latches on motion, decays after 120 s without motion; activity = `min(100, 100 * motion_energy / activity_scale)`.

- [ ] **Step 1: Write the failing test**

`tests/test_baseline.py`:
```python
import numpy as np, pytest
from aura.frames import RFFrame
from aura.brain.calibrate import calibrate_empty, calibrate_walk
from aura.brain.baseline import Baseline

def _frames(n, jitter, seed=0):
    rng = np.random.default_rng(seed)
    return [RFFrame(ts=i * 0.25, wifi={"aaaaaaaa": -60 + jitter * np.sin(i / 3) + rng.normal(0, jitter / 2),
                                       "bbbbbbbb": -70 + rng.normal(0, jitter / 2)},
                    link=[-50.0], ble={}) for i in range(n)]

def test_calibration_flow():
    cal = calibrate_empty(_frames(400, 0.3))          # ~100 s of empty
    assert len(cal["link_ids"]) == 2 and cal["empty_p995"] > 0
    cal = calibrate_walk(_frames(400, 4.0, seed=1), cal)
    assert cal["activity_scale"] > cal["empty_p995"]

def test_calibrate_walk_rejects_no_separation():
    cal = calibrate_empty(_frames(400, 0.3))
    with pytest.raises(ValueError):
        calibrate_walk(_frames(400, 0.3, seed=2), cal)

def test_baseline_state_machine():
    cal = {"link_ids": ["aaaaaaaa", "bbbbbbbb"], "empty_p995": 0.1, "activity_scale": 1.0}
    b = Baseline(cal)
    s = b.update({"motion_energy": 0.5, "band_energy": 0.2, "xcorr": 0.3}, ts=100.0)
    assert s == {"presence": 1, "motion": 1, "activity": 50.0}
    s = b.update({"motion_energy": 0.01, "band_energy": 0.0, "xcorr": 0.0}, ts=150.0)
    assert s["motion"] == 0 and s["presence"] == 1      # latched
    s = b.update({"motion_energy": 0.01, "band_energy": 0.0, "xcorr": 0.0}, ts=100.0 + 130)
    assert s["presence"] == 0                            # decayed after 120s
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement**

`aura/brain/calibrate.py`:
```python
import numpy as np
from aura.brain.features import select_links, build_matrix, summary

def _window_energies(frames, link_ids, win_s=15.0, step_s=5.0):
    if not frames:
        return []
    t0, t1 = frames[0].ts, frames[-1].ts
    out, t = [], t0
    while t + win_s <= t1:
        w = [f for f in frames if t <= f.ts < t + win_s]
        if len(w) >= 8:
            out.append(summary(build_matrix(w, link_ids))["motion_energy"])
        t += step_s
    return out

def calibrate_empty(frames, k: int = 16) -> dict:
    link_ids = select_links(frames, k)
    e = _window_energies(frames, link_ids)
    if not e:
        raise ValueError("not enough empty-room data")
    return {"link_ids": link_ids, "empty_p995": float(np.percentile(e, 99.5))}

def calibrate_walk(frames, cal: dict) -> dict:
    e = _window_energies(frames, cal["link_ids"])
    if not e:
        raise ValueError("not enough walking data")
    med = float(np.median(e))
    if med <= cal["empty_p995"]:
        raise ValueError("walk energy not above empty threshold — recheck placement")
    return {**cal, "activity_scale": med}
```

`aura/brain/baseline.py`:
```python
class Baseline:
    PRESENCE_DECAY_S = 120.0

    def __init__(self, cal: dict):
        self.cal = cal
        self._last_motion_ts = None

    def update(self, s: dict, ts: float) -> dict:
        motion = int(s["motion_energy"] > self.cal["empty_p995"])
        if motion:
            self._last_motion_ts = ts
        presence = int(self._last_motion_ts is not None
                       and ts - self._last_motion_ts <= self.PRESENCE_DECAY_S)
        scale = self.cal.get("activity_scale") or 1.0
        activity = min(100.0, 100.0 * s["motion_energy"] / scale)
        return {"presence": presence, "motion": motion, "activity": round(activity, 1)}
```

- [ ] **Step 4: Run** → 3 PASS
- [ ] **Step 5: Commit**
```bash
git add aura/brain/baseline.py aura/brain/calibrate.py tests/test_baseline.py
git commit -m "feat: baseline detector and learn-my-room calibration"
```

---

### Task 9: Dataset builder + training + ONNX export (PC-side)

**Files:**
- Create: `training/dataset.py`, `training/train.py`, `tests/test_training.py`

**Interfaces:**
- Consumes: session dirs `data/sessions/<name>/{frames.jsonl, labels.jsonl}`, `build_matrix`, calibration `link_ids`.
- Produces: `training/dataset.py::build_dataset(session_dirs, link_ids, out_npz)` → npz with `x (N,17,60) float32`, `y_presence (N,)`, `y_motion (N,)`, `y_activity (N,)`, `session (N,) str`; windows = 15 s, stride 5 s; labels joined by timestamp (window label = majority `person`, motion = 1 if mean label-`motion` > 0.02, activity = `min(100, mean_motion*2000)`); windows with no label within 2 s of window-center are skipped. `training/train.py` CLI: `python training/train.py --npz data/dataset.npz --val-sessions night2,eve3 --out models/aura.onnx` → trains `AuraNet`, prints val metrics, exports ONNX (input name `"rf"`, output names `"presence","motion","activity"`, logits for the two classifications). Board consumes `models/aura.onnx` (committed to git).

- [ ] **Step 1: Write the failing test**

`tests/test_training.py`:
```python
import numpy as np, subprocess, sys
from pathlib import Path
from aura.frames import RFFrame, append_frame
from aura.labeler.labeler import write_label

def _make_session(root, name, jitter, person, n=300, seed=0):
    d = root / name; d.mkdir(parents=True)
    rng = np.random.default_rng(seed)
    for i in range(n):
        append_frame(d / "frames.jsonl", RFFrame(
            ts=i * 0.25, wifi={"aaaaaaaa": -60 + jitter * np.sin(i / 3) + rng.normal(0, jitter / 2)},
            link=[-50.0], ble={}))
        if i % 4 == 0:
            write_label(d / "labels.jsonl", i * 0.25, person, 0.05 if person else 0.0)
    return d

def test_build_dataset(tmp_path):
    from training.dataset import build_dataset
    s1 = _make_session(tmp_path, "empty1", 0.3, 0)
    s2 = _make_session(tmp_path, "move1", 4.0, 1, seed=1)
    out = tmp_path / "ds.npz"
    build_dataset([s1, s2], ["aaaaaaaa"], out)
    d = np.load(out, allow_pickle=True)
    assert d["x"].shape[1:] == (2, 60)      # 1 link + link-stream
    assert set(d["y_presence"]) == {0, 1}
    assert len(d["x"]) == len(d["session"])

def test_train_and_export_onnx(tmp_path):
    from training.dataset import build_dataset
    from training.train import train
    s1 = _make_session(tmp_path, "empty1", 0.3, 0)
    s2 = _make_session(tmp_path, "move1", 4.0, 1, seed=1)
    npz = tmp_path / "ds.npz"
    build_dataset([s1, s2], ["aaaaaaaa"], npz)
    onnx_path = tmp_path / "m.onnx"
    metrics = train(npz, val_sessions=["move1"], out=onnx_path, epochs=2)
    assert onnx_path.exists()
    assert 0.0 <= metrics["val_presence_acc"] <= 1.0
    import onnxruntime as ort
    sess = ort.InferenceSession(str(onnx_path))
    x = np.zeros((1, 2, 60), dtype=np.float32)
    outs = sess.run(None, {"rf": x})
    assert len(outs) == 3
```

- [ ] **Step 2: Run** → FAIL (`.venv\Scripts\python -m pytest tests/test_training.py -v`; needs `pip install -e .[train]`)
- [ ] **Step 3: Implement**

`training/dataset.py`:
```python
import numpy as np
from pathlib import Path
from aura.frames import read_frames
from aura.labeler.labeler import read_labels
from aura.brain.features import build_matrix

WIN_S, STEP_S = 15.0, 5.0

def build_dataset(session_dirs, link_ids, out_npz: Path):
    X, yp, ym, ya, names = [], [], [], [], []
    for d in session_dirs:
        d = Path(d)
        frames = read_frames(d / "frames.jsonl")
        labels = read_labels(d / "labels.jsonl")
        if not frames or not labels:
            continue
        lts = np.array([l["ts"] for l in labels])
        t = frames[0].ts
        while t + WIN_S <= frames[-1].ts:
            w = [f for f in frames if t <= f.ts < t + WIN_S]
            center = t + WIN_S / 2
            near = np.abs(lts - center) <= WIN_S / 2 + 2.0
            if len(w) >= 8 and near.any():
                sel = [labels[i] for i in np.where(near)[0]]
                X.append(build_matrix(w, link_ids))
                yp.append(int(np.mean([l["person"] for l in sel]) >= 0.5))
                mean_motion = float(np.mean([l["motion"] for l in sel]))
                ym.append(int(mean_motion > 0.02))
                ya.append(min(100.0, mean_motion * 2000.0))
                names.append(d.name)
            t += STEP_S
    np.savez(out_npz, x=np.array(X, dtype=np.float32), y_presence=np.array(yp),
             y_motion=np.array(ym), y_activity=np.array(ya, dtype=np.float32),
             session=np.array(names))
```
(Note: rename the `近` variable to `near` when writing the real file — ASCII only.)

`training/train.py`:
```python
import argparse
import numpy as np
import torch, torch.nn as nn
from pathlib import Path

class AuraNet(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv1d(channels, 32, 5, stride=2, padding=2), nn.BatchNorm1d(32), nn.ReLU(),
            nn.Conv1d(32, 64, 5, stride=2, padding=2), nn.BatchNorm1d(64), nn.ReLU(),
            nn.Conv1d(64, 64, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool1d(1), nn.Flatten())
        self.presence = nn.Linear(64, 1)
        self.motion = nn.Linear(64, 1)
        self.activity = nn.Linear(64, 1)

    def forward(self, x):
        h = self.body(x)
        return self.presence(h).squeeze(1), self.motion(h).squeeze(1), self.activity(h).squeeze(1)

def train(npz: Path, val_sessions, out: Path, epochs: int = 30, lr: float = 1e-3):
    d = np.load(npz, allow_pickle=True)
    val_mask = np.isin(d["session"], list(val_sessions))
    def tensors(mask):
        return (torch.tensor(d["x"][mask]), torch.tensor(d["y_presence"][mask], dtype=torch.float32),
                torch.tensor(d["y_motion"][mask], dtype=torch.float32),
                torch.tensor(d["y_activity"][mask], dtype=torch.float32))
    xtr, ptr, mtr, atr = tensors(~val_mask)
    xva, pva, mva, ava = tensors(val_mask)
    model = AuraNet(channels=d["x"].shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    bce, mse = nn.BCEWithLogitsLoss(), nn.MSELoss()
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(xtr))
        for i in range(0, len(perm), 64):
            idx = perm[i:i + 64]
            opt.zero_grad()
            lp, lm, la = model(xtr[idx])
            loss = bce(lp, ptr[idx]) + bce(lm, mtr[idx]) + mse(la, atr[idx]) / 1000.0
            loss.backward(); opt.step()
    model.eval()
    with torch.no_grad():
        lp, lm, la = model(xva) if len(xva) else model(xtr)
        ref_p = pva if len(xva) else ptr
        acc = float(((torch.sigmoid(lp) > 0.5).float() == ref_p).float().mean())
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(model, torch.zeros(1, d["x"].shape[1], 60), str(out),
                      input_names=["rf"], output_names=["presence", "motion", "activity"],
                      dynamic_axes={"rf": {0: "batch"}}, opset_version=17)
    metrics = {"val_presence_acc": acc, "n_train": int((~val_mask).sum()), "n_val": int(val_mask.sum())}
    print(metrics)
    return metrics

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True, type=Path)
    ap.add_argument("--val-sessions", default="", type=str)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--epochs", type=int, default=30)
    a = ap.parse_args()
    train(a.npz, [s for s in a.val_sessions.split(",") if s], a.out, a.epochs)
```
Also create empty `training/__init__.py` so tests can import it.

- [ ] **Step 4: Run** → 2 PASS (train test takes ~1 min CPU)
- [ ] **Step 5: Commit**
```bash
git add training/__init__.py training/dataset.py training/train.py tests/test_training.py
git commit -m "feat: dataset builder, AuraNet training, ONNX export"
```

---

### Task 10: Brain daemon (live inference loop)

**Files:**
- Create: `aura/brain/brain.py`, `tests/test_brain.py`

**Interfaces:**
- Consumes: `tail_frames`, `build_matrix`, `summary`, `Baseline`, `calibration.json`, optional `models/aura.onnx` (ONNX Runtime).
- Produces: atomically-replaced `AURA_HOME/state.json`: `{"ts": float, "presence": 0|1, "motion": 0|1, "activity": float, "src": "cnn"|"baseline"}`; appended `AURA_HOME/features.jsonl`: `{"ts", "motion_energy", "band_energy", "xcorr", "channels": [per-channel std of diff, len 17]}` (dashboard waterfall reads `channels`); function `run_brain(cfg, frames_path, stop_event, model_path=None, max_iters=None)`. CNN outputs are sigmoided; presence/motion threshold 0.5. If no model file → `src:"baseline"`. If no calibration → auto-selects links from buffer and uses `{"empty_p995": 0.05, "activity_scale": 0.5}` defaults (marked `"src": "baseline"`).

- [ ] **Step 1: Write the failing test** (replay-driven, no radios)

`tests/test_brain.py`:
```python
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
    cfg = Config.load()
    (tmp_path / "calibration.json").write_text(json.dumps(
        {"link_ids": ["aaaaaaaa"], "empty_p995": 0.05, "activity_scale": 0.5}))
    frames_path = tmp_path / "frames.jsonl"
    _write_live(frames_path, 120, jitter=4.0)
    stop = threading.Event()
    run_brain(cfg, frames_path, stop, model_path=None, max_iters=3)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "baseline"
    assert state["motion"] == 1 and state["presence"] == 1
    feats = (tmp_path / "features.jsonl").read_text().strip().splitlines()
    assert len(feats) >= 1
    assert len(json.loads(feats[0])["channels"]) == 2  # 1 link + link-stream
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement `aura/brain/brain.py`**

```python
import json, os, time
from collections import deque
from pathlib import Path
import numpy as np
from aura.frames import read_frames, tail_frames
from aura.brain.features import select_links, build_matrix, summary
from aura.brain.baseline import Baseline

def _atomic_write(path: Path, obj: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj))
    os.replace(tmp, path)

def _load_cal(home: Path):
    p = home / "calibration.json"
    if p.exists():
        return json.loads(p.read_text())
    return None

def run_brain(cfg, frames_path: Path, stop_event, model_path: Path = None, max_iters=None):
    sess = None
    if model_path and Path(model_path).exists():
        import onnxruntime as ort
        sess = ort.InferenceSession(str(model_path))
    cal = _load_cal(cfg.aura_home)
    window = deque(maxlen=int(cfg.window_seconds * cfg.frame_hz * 2))
    for f in read_frames(frames_path)[-window.maxlen:]:
        window.append(f)
    baseline = None
    iters = 0
    gen = tail_frames(frames_path, poll_s=0.25)
    last_infer = 0.0
    while not stop_event.is_set():
        try:
            f = next(gen)
            window.append(f)
        except StopIteration:
            break
        now = f.ts
        if now - last_infer < 0.5:
            continue
        w = [x for x in window if x.ts >= now - cfg.window_seconds]
        if len(w) < 8:
            continue
        last_infer = now
        if cal is None:
            cal = {"link_ids": select_links(w, cfg.top_k), "empty_p995": 0.05, "activity_scale": 0.5}
        if baseline is None:
            baseline = Baseline(cal)
        m = build_matrix(w, cal["link_ids"])
        s = summary(m)
        state = baseline.update(s, ts=now)
        src = "baseline"
        if sess is not None:
            lp, lm, la = sess.run(None, {"rf": m[None].astype(np.float32)})
            sig = lambda z: 1.0 / (1.0 + np.exp(-float(z)))
            state = {"presence": int(sig(lp[0]) > 0.5), "motion": int(sig(lm[0]) > 0.5),
                     "activity": round(max(0.0, min(100.0, float(la[0]))), 1)}
            src = "cnn"
        _atomic_write(cfg.aura_home / "state.json", {"ts": now, **state, "src": src})
        with open(cfg.aura_home / "features.jsonl", "a", encoding="utf-8") as fh:
            chans = np.std(np.diff(m, axis=1), axis=1).round(4).tolist()
            fh.write(json.dumps({"ts": now, **s, "channels": chans}) + "\n")
        iters += 1
        if max_iters and iters >= max_iters:
            break
```

- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Add a CNN-path test** (append to `tests/test_brain.py`; reuses the tiny ONNX from Task 9's test helper):
```python
def test_brain_cnn_path(tmp_path, monkeypatch):
    from training.dataset import build_dataset
    from training.train import train
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
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
    run_brain(cfg, frames_path, threading.Event(), model_path=model, max_iters=2)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["src"] == "cnn"
    assert set(state) == {"ts", "presence", "motion", "activity", "src"}
```
Run: `.venv\Scripts\python -m pytest tests/test_brain.py -v` → 2 PASS
- [ ] **Step 6: Commit**
```bash
git add aura/brain/brain.py tests/test_brain.py
git commit -m "feat: brain daemon — live inference with cnn/baseline fallback"
```

---

### Task 11: Guardian (modes, alert rules, Telegram)

**Files:**
- Create: `aura/guardian/__init__.py`, `aura/guardian/rules.py`, `aura/guardian/notify.py`, `aura/guardian/guardian.py`, `tests/test_guardian.py`

**Interfaces:**
- Consumes: `state.json`, `AURA_HOME/mode.json` (`{"mode": "home"|"away"|"wellness", "wellness_hours": 8}` — written by dashboard).
- Produces: `Rules(mode_getter)` with `.update(state: dict) -> dict|None` (alert dict or None): away + motion sustained ≥3 s → `{"type": "intrusion", "ts": ...}` with 300 s cooldown; wellness + no motion for `wellness_hours` → `{"type": "inactivity", "ts": ...}` (fires once per quiet period); `Notifier(cfg, sender=None)` `.send(alert)` → appends `alerts.jsonl` and POSTs Telegram `sendMessage` if token configured (injectable `sender(url, payload)` for tests); `run_guardian(cfg, stop_event, max_iters=None)` polls `state.json` at 1 Hz.

- [ ] **Step 1: Write the failing test**

`tests/test_guardian.py`:
```python
import json
from pathlib import Path
from aura.guardian.rules import Rules
from aura.guardian.notify import Notifier
from aura.config import Config

def test_intrusion_needs_sustained_motion_and_cooldown():
    r = Rules(lambda: {"mode": "away", "wellness_hours": 8})
    assert r.update({"ts": 0.0, "motion": 1, "presence": 1}) is None      # not sustained yet
    assert r.update({"ts": 2.0, "motion": 1, "presence": 1}) is None
    a = r.update({"ts": 3.5, "motion": 1, "presence": 1})
    assert a and a["type"] == "intrusion"
    assert r.update({"ts": 10.0, "motion": 1, "presence": 1}) is None     # cooldown
    a2 = r.update({"ts": 310.0, "motion": 1, "presence": 1})
    assert a2 is None  # motion run restarted? no — sustained since 3.5 continuously
    # release and re-trigger after cooldown:
    r.update({"ts": 311.0, "motion": 0, "presence": 1})
    r.update({"ts": 312.0, "motion": 1, "presence": 1})
    assert r.update({"ts": 316.0, "motion": 1, "presence": 1})["type"] == "intrusion"

def test_home_mode_never_alerts():
    r = Rules(lambda: {"mode": "home", "wellness_hours": 8})
    for t in range(0, 100, 1):
        assert r.update({"ts": float(t), "motion": 1, "presence": 1}) is None

def test_wellness_inactivity():
    r = Rules(lambda: {"mode": "wellness", "wellness_hours": 1})
    assert r.update({"ts": 0.0, "motion": 1, "presence": 1}) is None
    assert r.update({"ts": 1800.0, "motion": 0, "presence": 0}) is None
    a = r.update({"ts": 3700.0, "motion": 0, "presence": 0})
    assert a and a["type"] == "inactivity"
    assert r.update({"ts": 3800.0, "motion": 0, "presence": 0}) is None   # once per quiet period

def test_notifier_writes_log_and_posts(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    cfg.telegram_token, cfg.telegram_chat_id = "TOK", "CHAT"
    calls = []
    n = Notifier(cfg, sender=lambda url, payload: calls.append((url, payload)))
    n.send({"type": "intrusion", "ts": 5.0})
    log = (tmp_path / "alerts.jsonl").read_text().strip().splitlines()
    assert json.loads(log[0])["type"] == "intrusion"
    assert "TOK" in calls[0][0] and calls[0][1]["chat_id"] == "CHAT"
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement**

`aura/guardian/rules.py`:
```python
class Rules:
    SUSTAIN_S, COOLDOWN_S = 3.0, 300.0

    def __init__(self, mode_getter):
        self.mode_getter = mode_getter
        self._motion_since = None
        self._last_alert_ts = -1e12
        self._last_motion_ts = None
        self._inactivity_fired = False

    def update(self, state: dict):
        m = self.mode_getter()
        mode, ts = m.get("mode", "home"), state["ts"]
        if state.get("motion"):
            if self._motion_since is None:
                self._motion_since = ts
            self._last_motion_ts = ts
            self._inactivity_fired = False
        else:
            self._motion_since = None
        if mode == "away" and self._motion_since is not None \
                and ts - self._motion_since >= self.SUSTAIN_S \
                and ts - self._last_alert_ts >= self.COOLDOWN_S:
            self._last_alert_ts = ts
            return {"type": "intrusion", "ts": ts}
        if mode == "wellness" and not self._inactivity_fired and self._last_motion_ts is not None \
                and ts - self._last_motion_ts >= m.get("wellness_hours", 8) * 3600.0:
            self._inactivity_fired = True
            return {"type": "inactivity", "ts": ts}
        return None
```

`aura/guardian/notify.py`:
```python
import json

def _http_sender(url, payload):
    import requests
    requests.post(url, json=payload, timeout=10)

class Notifier:
    MSG = {"intrusion": "🚨 Aura: motion detected while armed!",
           "inactivity": "🩺 Aura: no movement detected for the configured period."}

    def __init__(self, cfg, sender=None):
        self.cfg = cfg
        self.sender = sender or _http_sender

    def send(self, alert: dict):
        with open(self.cfg.aura_home / "alerts.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(alert) + "\n")
        if self.cfg.telegram_token and self.cfg.telegram_chat_id:
            url = f"https://api.telegram.org/bot{self.cfg.telegram_token}/sendMessage"
            try:
                self.sender(url, {"chat_id": self.cfg.telegram_chat_id,
                                  "text": self.MSG.get(alert["type"], str(alert))})
            except Exception:
                pass
```

`aura/guardian/guardian.py`:
```python
import json, time

def _read_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def run_guardian(cfg, stop_event, max_iters=None):
    from aura.guardian.rules import Rules
    from aura.guardian.notify import Notifier
    rules = Rules(lambda: _read_json(cfg.aura_home / "mode.json", {"mode": "home", "wellness_hours": 8}))
    notifier = Notifier(cfg)
    iters = 0
    while not stop_event.is_set():
        state = _read_json(cfg.aura_home / "state.json", None)
        if state:
            alert = rules.update(state)
            if alert:
                notifier.send(alert)
        iters += 1
        if max_iters and iters >= max_iters:
            break
        stop_event.wait(1.0)
```
(+ empty `aura/guardian/__init__.py`)

- [ ] **Step 4: Run** → 4 PASS
- [ ] **Step 5: Commit**
```bash
git add aura/guardian tests/test_guardian.py
git commit -m "feat: guardian modes, alert rules, telegram notifier"
```

---

### Task 12: Dashboard (Flask + canvas waterfall)

**Files:**
- Create: `aura/face/__init__.py`, `aura/face/server.py`, `aura/face/static/index.html`, `aura/face/static/app.js`, `aura/face/static/style.css`, `tests/test_face.py`

**Interfaces:**
- Consumes: `state.json`, `features.jsonl`, `alerts.jsonl`, writes `mode.json`.
- Produces: Flask app factory `create_app(cfg)`; routes: `GET /` (index.html), `GET /api/state` (state.json or `{"src":"none"}`), `GET /api/waterfall?n=120` (last n features rows), `GET /api/alerts?n=20`, `POST /api/mode` body `{"mode": "...", "wellness_hours": 8}` (validates mode ∈ home/away/wellness → 400 otherwise), `POST /api/calibrate` body `{"phase": "empty"|"walk", "minutes": int}` → spawns `aura calibrate <phase> --minutes N` via `subprocess.Popen`, returns `{"started": true}`. `run_face(cfg)` serves on `0.0.0.0:8080`.

- [ ] **Step 1: Write the failing test**

`tests/test_face.py`:
```python
import json
from aura.config import Config
from aura.face.server import create_app

def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    return cfg, create_app(cfg).test_client()

def test_state_empty_then_value(tmp_path, monkeypatch):
    cfg, c = _client(tmp_path, monkeypatch)
    assert c.get("/api/state").get_json() == {"src": "none"}
    (cfg.aura_home / "state.json").write_text(json.dumps({"ts": 1, "presence": 1, "motion": 0, "activity": 5.0, "src": "cnn"}))
    assert c.get("/api/state").get_json()["presence"] == 1

def test_waterfall_returns_last_n(tmp_path, monkeypatch):
    cfg, c = _client(tmp_path, monkeypatch)
    with open(cfg.aura_home / "features.jsonl", "w") as fh:
        for i in range(200):
            fh.write(json.dumps({"ts": i, "motion_energy": 0.1, "band_energy": 0.2, "xcorr": 0.3, "channels": [0.1, 0.2]}) + "\n")
    rows = c.get("/api/waterfall?n=120").get_json()
    assert len(rows) == 120 and rows[-1]["ts"] == 199

def test_mode_roundtrip_and_validation(tmp_path, monkeypatch):
    cfg, c = _client(tmp_path, monkeypatch)
    r = c.post("/api/mode", json={"mode": "away"})
    assert r.status_code == 200
    assert json.loads((cfg.aura_home / "mode.json").read_text())["mode"] == "away"
    assert c.post("/api/mode", json={"mode": "party"}).status_code == 400

def test_index_served(tmp_path, monkeypatch):
    _, c = _client(tmp_path, monkeypatch)
    assert b"Aura" in c.get("/").data
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement `aura/face/server.py`**

```python
import json, subprocess, sys
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

STATIC = Path(__file__).parent / "static"

def _tail_jsonl(path: Path, n: int):
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()[-n:]
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            pass
    return out

def create_app(cfg):
    app = Flask(__name__)

    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/static/<path:p>")
    def static_files(p):
        return send_from_directory(STATIC, p)

    @app.get("/api/state")
    def state():
        p = cfg.aura_home / "state.json"
        if not p.exists():
            return jsonify({"src": "none"})
        return jsonify(json.loads(p.read_text()))

    @app.get("/api/waterfall")
    def waterfall():
        n = int(request.args.get("n", 120))
        return jsonify(_tail_jsonl(cfg.aura_home / "features.jsonl", n))

    @app.get("/api/alerts")
    def alerts():
        n = int(request.args.get("n", 20))
        return jsonify(_tail_jsonl(cfg.aura_home / "alerts.jsonl", n))

    @app.post("/api/mode")
    def mode():
        body = request.get_json(force=True)
        if body.get("mode") not in ("home", "away", "wellness"):
            return jsonify({"error": "bad mode"}), 400
        (cfg.aura_home / "mode.json").write_text(json.dumps(
            {"mode": body["mode"], "wellness_hours": int(body.get("wellness_hours", 8))}))
        return jsonify({"ok": True})

    @app.post("/api/calibrate")
    def calibrate():
        body = request.get_json(force=True)
        phase = body.get("phase")
        if phase not in ("empty", "walk"):
            return jsonify({"error": "bad phase"}), 400
        subprocess.Popen([sys.executable, "-m", "aura.cli", "calibrate", phase,
                          "--minutes", str(int(body.get("minutes", 10)))])
        return jsonify({"started": True})

    return app

def run_face(cfg):
    create_app(cfg).run(host="0.0.0.0", port=8080)
```

- [ ] **Step 4: Write the static UI**

`aura/face/static/index.html`:
```html
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aura</title><link rel="stylesheet" href="/static/style.css"></head><body>
<header><h1>Aura</h1><span id="srcbadge"></span></header>
<section id="statecards">
  <div class="card"><div class="k">Presence</div><div class="v" id="presence">–</div></div>
  <div class="card"><div class="k">Motion</div><div class="v" id="motion">–</div></div>
  <div class="card"><div class="k">Activity</div><div class="v" id="activity">–</div></div>
</section>
<section><h2>RF waterfall</h2><canvas id="waterfall" width="720" height="240"></canvas></section>
<section><h2>Mode</h2>
  <button data-mode="home">Home</button><button data-mode="away">Away (armed)</button>
  <button data-mode="wellness">Wellness</button>
  <button id="cal">Learn my room</button>
</section>
<section><h2>Alerts</h2><ul id="alerts"></ul></section>
<script src="/static/app.js"></script></body></html>
```

`aura/face/static/app.js`:
```javascript
const $ = id => document.getElementById(id);
async function j(url, opts) { const r = await fetch(url, opts); return r.json(); }

async function tick() {
  const s = await j('/api/state');
  $('presence').textContent = s.src === 'none' ? '–' : (s.presence ? 'PRESENT' : 'EMPTY');
  $('motion').textContent = s.src === 'none' ? '–' : (s.motion ? 'MOVING' : 'STILL');
  $('activity').textContent = s.activity ?? '–';
  $('srcbadge').textContent = s.src || '';
  document.body.classList.toggle('present', !!s.presence);
  const rows = await j('/api/waterfall?n=120');
  drawWaterfall(rows);
  const alerts = await j('/api/alerts?n=10');
  $('alerts').innerHTML = alerts.reverse().map(a =>
    `<li>${new Date(a.ts * 1000).toLocaleTimeString()} — ${a.type}</li>`).join('');
}

function drawWaterfall(rows) {
  const cv = $('waterfall'), ctx = cv.getContext('2d');
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, cv.width, cv.height);
  if (!rows.length) return;
  const chans = rows[0].channels.length, cw = cv.width / 120, ch = cv.height / chans;
  rows.forEach((r, x) => r.channels.forEach((v, y) => {
    const t = Math.min(1, v / 1.5);
    ctx.fillStyle = `rgb(${Math.round(20 + 235 * t)},${Math.round(30 + 80 * t)},${Math.round(80 + 100 * (1 - t))})`;
    ctx.fillRect(x * cw, y * ch, Math.ceil(cw), Math.ceil(ch));
  }));
}

document.querySelectorAll('button[data-mode]').forEach(b =>
  b.onclick = () => j('/api/mode', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: b.dataset.mode }) }));
$('cal').onclick = async () => {
  alert('Leave the room now. Aura will learn "empty" for 10 minutes, then ask you to walk.');
  await j('/api/calibrate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phase: 'empty', minutes: 10 }) });
};
setInterval(tick, 500); tick();
```

`aura/face/static/style.css`:
```css
:root { color-scheme: dark; }
body { margin: 0; font-family: system-ui, sans-serif; background: #0b0e14; color: #dce3f0; }
header { display: flex; align-items: baseline; gap: 1rem; padding: 1rem 1.5rem; border-bottom: 1px solid #1c2333; }
h1 { margin: 0; font-size: 1.4rem; letter-spacing: .2em; color: #7ac7ff; }
#srcbadge { font-size: .75rem; color: #6b7690; }
section { padding: 1rem 1.5rem; }
#statecards { display: flex; gap: 1rem; }
.card { background: #121826; border: 1px solid #1c2333; border-radius: 10px; padding: 1rem 1.5rem; min-width: 8rem; }
.card .k { font-size: .7rem; text-transform: uppercase; color: #6b7690; }
.card .v { font-size: 1.6rem; font-weight: 700; }
body.present .card .v { color: #7affc4; }
canvas { width: 100%; max-width: 720px; border-radius: 8px; }
button { background: #1a2340; color: #dce3f0; border: 1px solid #2a3550; border-radius: 8px; padding: .5rem 1rem; margin-right: .5rem; cursor: pointer; }
button:hover { border-color: #7ac7ff; }
ul { margin: 0; padding-left: 1.2rem; color: #ffb37a; }
```

- [ ] **Step 5: Run tests** → 4 PASS. Manual smoke: `.venv\Scripts\python -c "from aura.config import Config; from aura.face.server import run_face; run_face(Config.load())"` → open http://localhost:8080 — cards render, no console errors (waterfall empty is fine on PC).
- [ ] **Step 6: Commit**
```bash
git add aura/face tests/test_face.py
git commit -m "feat: dashboard — state cards, waterfall, modes, alerts"
```

---

### Task 13: LED matrix sketch + state bridge

**Files:**
- Create: `sketch/aura_matrix/aura_matrix.ino`, `aura/face/bridge.py`, `tests/test_bridge.py`

**Interfaces:**
- Consumes: `state.json` (bridge side).
- Produces: serial line protocol PC→M33: `S,<presence 0|1>,<motion 0|1>,<activity 0-100>,<alert 0|1>\n`; `alert=1` iff last line of `alerts.jsonl` is < 60 s old. `run_bridge(cfg, stop_event, port_factory=None, max_iters=None)` sends current state at 5 Hz over `cfg.serial_port` (pyserial). Sketch renders: empty→radar sweep, present→aura bloom radius ∝ activity, alert→4 Hz full strobe, no serial for 5 s→fault pixel blink.
- **Spike dependency:** `docs/spike-results.md` Step 6 recorded (a) the Linux↔M33 channel and (b) the matrix draw API. If the channel is a serial device (`/dev/tty*`), set it as `serial_port` in `~/.aura/config.json` and use this task as written. If the spike shows serial is NOT exposed and App Lab's Bridge/RPC is the only channel, replace `run_bridge`'s send with the recorded RPC call (same 4-field payload, same 5 Hz cadence) — the sketch's `applyState()` and all animation code stay identical, only the transport line in each side changes.

- [ ] **Step 1: Write the failing test** (bridge side only; sketch is verified on hardware)

`tests/test_bridge.py`:
```python
import json, threading, time
from aura.config import Config
from aura.face.bridge import run_bridge

class FakePort:
    def __init__(self): self.lines = []
    def write(self, b): self.lines.append(b.decode())
    def close(self): pass

def test_bridge_sends_state_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    (tmp_path / "state.json").write_text(json.dumps({"ts": time.time(), "presence": 1, "motion": 0, "activity": 42.0, "src": "cnn"}))
    (tmp_path / "alerts.jsonl").write_text(json.dumps({"type": "intrusion", "ts": time.time()}) + "\n")
    port = FakePort()
    run_bridge(cfg, threading.Event(), port_factory=lambda: port, max_iters=3)
    assert port.lines[0] == "S,1,0,42,1\n"
    assert len(port.lines) == 3

def test_bridge_no_state_sends_zeros(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_HOME", str(tmp_path))
    cfg = Config.load()
    port = FakePort()
    run_bridge(cfg, threading.Event(), port_factory=lambda: port, max_iters=1)
    assert port.lines == ["S,0,0,0,0\n"]
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement `aura/face/bridge.py`**

```python
import json, time

def _read(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def _alert_active(cfg, now):
    p = cfg.aura_home / "alerts.jsonl"
    if not p.exists():
        return 0
    lines = p.read_text().strip().splitlines()
    if not lines:
        return 0
    try:
        return int(now - json.loads(lines[-1])["ts"] < 60.0)
    except Exception:
        return 0

def run_bridge(cfg, stop_event, port_factory=None, max_iters=None):
    if port_factory is None:
        import serial
        port_factory = lambda: serial.Serial(cfg.serial_port, 115200, timeout=1)
    port = port_factory()
    iters = 0
    try:
        while not stop_event.is_set():
            now = time.time()
            s = _read(cfg.aura_home / "state.json", {"presence": 0, "motion": 0, "activity": 0})
            line = f"S,{int(s.get('presence', 0))},{int(s.get('motion', 0))},{int(round(float(s.get('activity', 0))))},{_alert_active(cfg, now)}\n"
            port.write(line.encode())
            iters += 1
            if max_iters and iters >= max_iters:
                break
            stop_event.wait(0.2)
    finally:
        port.close()
```

- [ ] **Step 4: Run** → 2 PASS
- [ ] **Step 5: Write the sketch** `sketch/aura_matrix/aura_matrix.ino` (adapt ONLY the two marked lines to the include/draw call recorded in `docs/spike-results.md`):

```cpp
// Aura LED matrix face — UNO Q M33 side.
// ADAPT LINE A: include the matrix library exactly as the on-board App Lab matrix example does.
#include <Arduino_LED_Matrix.h>   // ADAPT-A if the example differs
ArduinoLEDMatrix matrix;          // ADAPT-A

const int W = 13, H = 8;
uint8_t fb[H][W];
uint8_t presence = 0, motionF = 0, activity = 0, alertF = 0;
unsigned long lastSerialMs = 0;
float sweepX = 0;

void drawFrame() {
  // ADAPT LINE B: this is the only draw call — replace with the example's frame-render call.
  matrix.renderBitmap(fb, H, W); // ADAPT-B
}

void clearFb() { memset(fb, 0, sizeof(fb)); }

void radarSweep() {
  clearFb();
  sweepX += 0.35; if (sweepX >= W) sweepX = 0;
  int x = (int)sweepX;
  for (int y = 0; y < H; y++) {
    fb[y][x] = 1;
    if (x > 0) fb[y][x - 1] = (y % 2) ? 1 : 0;  // fading trail
  }
}

void auraBloom() {
  clearFb();
  float r = 1.0f + (activity / 100.0f) * 5.0f;
  float cx = W / 2.0f, cy = H / 2.0f;
  float pulse = motionF ? (0.5f * sinf(millis() / 150.0f)) : 0.0f;
  for (int y = 0; y < H; y++)
    for (int x = 0; x < W; x++) {
      float d = sqrtf((x - cx) * (x - cx) + (y - cy) * (y - cy));
      if (d <= r + pulse) fb[y][x] = 1;
    }
}

void alertStrobe() {
  bool on = (millis() / 125) % 2;
  memset(fb, on ? 1 : 0, sizeof(fb));
}

void faultBlink() {
  clearFb();
  fb[0][0] = (millis() / 500) % 2;
}

void applyState(uint8_t p, uint8_t m, uint8_t a, uint8_t al) {
  presence = p; motionF = m; activity = a; alertF = al;
}

void pollSerial() {
  static char buf[32]; static int n = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      buf[n] = 0; n = 0;
      int p, m, a, al;
      if (sscanf(buf, "S,%d,%d,%d,%d", &p, &m, &a, &al) == 4) {
        applyState(p, m, a, al);
        lastSerialMs = millis();
      }
    } else if (n < 30) buf[n++] = c;
  }
}

void setup() {
  Serial.begin(115200);
  matrix.begin();               // ADAPT-A if the example differs
  lastSerialMs = millis();
}

void loop() {
  pollSerial();
  if (millis() - lastSerialMs > 5000) faultBlink();
  else if (alertF) alertStrobe();
  else if (presence) auraBloom();
  else radarSweep();
  drawFrame();
  delay(33);
}
```

- [ ] **Step 6: Hardware verify.** Flash via App Lab. On the board: `python3 -c "..."` run `run_bridge` with real `serial_port` from config while `state.json` exists → matrix animates; edit `state.json` presence 0↔1 by hand → sweep↔bloom switch within 1 s; stop bridge → fault blink after 5 s. Record a phone video clip (b-roll for the demo video).
- [ ] **Step 7: Commit**
```bash
git add sketch/aura_matrix/aura_matrix.ino aura/face/bridge.py tests/test_bridge.py
git commit -m "feat: LED matrix sketch + serial state bridge"
```

---

### Task 14: `aura` CLI + systemd deploy

**Files:**
- Create: `aura/cli.py`, `tests/test_cli.py`, `deploy/systemd/aura-ear.service`, `deploy/systemd/aura-brain.service`, `deploy/systemd/aura-guardian.service`, `deploy/systemd/aura-face.service`, `deploy/systemd/aura-bridge.service`, `deploy/install.sh`

**Interfaces:**
- Produces: `aura` console entrypoint with subcommands:
  - `aura record --session NAME [--minutes N]` → runs Ear writing to `data/sessions/NAME/frames.jsonl` (board)
  - `aura run-ear | run-brain | run-guardian | run-face | run-bridge` → daemon entrypoints used by systemd
  - `aura replay --session PATH [--speed X]` → replays onto `AURA_HOME/frames.jsonl`
  - `aura calibrate empty|walk --minutes N` → captures live frames from `AURA_HOME/frames.jsonl` for N minutes, then runs Task 8 functions; `walk` merges into existing `calibration.json`
  - `aura status` → prints `state.json` + last alert.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
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
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement `aura/cli.py`**

```python
import argparse, json, threading, time
from pathlib import Path
from aura.config import Config

def main():
    ap = argparse.ArgumentParser(prog="aura")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("record"); p.add_argument("--session", required=True); p.add_argument("--minutes", type=float, default=0)
    for c in ("run-ear", "run-brain", "run-guardian", "run-face", "run-bridge", "status"):
        sub.add_parser(c)
    p = sub.add_parser("replay"); p.add_argument("--session", required=True); p.add_argument("--speed", type=float, default=1.0)
    p = sub.add_parser("calibrate"); p.add_argument("phase", choices=["empty", "walk"]); p.add_argument("--minutes", type=int, default=10)
    a = ap.parse_args()
    cfg = Config.load()

    if a.cmd == "status":
        for name in ("state.json",):
            f = cfg.aura_home / name
            print(f.read_text() if f.exists() else "{}")
        alerts = cfg.aura_home / "alerts.jsonl"
        if alerts.exists():
            lines = alerts.read_text().strip().splitlines()
            print("last alert:", lines[-1] if lines else "none")

    elif a.cmd == "replay":
        from aura.ear.ear import replay
        replay(Path(a.session), cfg.aura_home / "frames.jsonl", speed=a.speed)

    elif a.cmd in ("record", "run-ear"):
        from aura.ear.ear import Ear, ScanPoller, LinkPoller, BlePoller
        out = (Path("data/sessions") / a.session / "frames.jsonl") if a.cmd == "record" \
            else cfg.aura_home / "frames.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        stop = threading.Event()
        ear = Ear(cfg, ScanPoller(cfg), LinkPoller(cfg), BlePoller())
        t = threading.Thread(target=ear.run_forever, args=(out, stop)); t.start()
        try:
            if a.cmd == "record" and a.minutes:
                time.sleep(a.minutes * 60)
            else:
                while True:
                    time.sleep(60)
        except KeyboardInterrupt:
            pass
        stop.set(); t.join()

    elif a.cmd == "run-brain":
        from aura.brain.brain import run_brain
        model = Path(__file__).parent.parent / "models" / "aura.onnx"
        run_brain(cfg, cfg.aura_home / "frames.jsonl", threading.Event(),
                  model_path=model if model.exists() else None)

    elif a.cmd == "run-guardian":
        from aura.guardian.guardian import run_guardian
        run_guardian(cfg, threading.Event())

    elif a.cmd == "run-face":
        from aura.face.server import run_face
        run_face(cfg)

    elif a.cmd == "run-bridge":
        from aura.face.bridge import run_bridge
        run_bridge(cfg, threading.Event())

    elif a.cmd == "calibrate":
        from aura.frames import read_frames
        from aura.brain.calibrate import calibrate_empty, calibrate_walk
        print(f"Capturing {a.minutes} min of live frames for phase '{a.phase}'...")
        t0 = time.time()
        time.sleep(a.minutes * 60)
        frames = [f for f in read_frames(cfg.aura_home / "frames.jsonl") if f.ts >= t0]
        cal_path = cfg.aura_home / "calibration.json"
        if a.phase == "empty":
            cal = calibrate_empty(frames, cfg.top_k)
        else:
            cal = calibrate_walk(frames, json.loads(cal_path.read_text()))
        cal_path.write_text(json.dumps(cal))
        print("calibration written:", cal_path)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run** → 2 PASS
- [ ] **Step 5: Write systemd units + installer.** All five units share this shape — `deploy/systemd/aura-ear.service` (repeat for brain/guardian/face/bridge changing the subcommand and description):
```ini
[Unit]
Description=Aura RF Ear
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 -m aura.cli run-ear
Restart=always
RestartSec=3
User=root
Environment=AURA_HOME=/root/.aura
WorkingDirectory=/root/aura-src

[Install]
WantedBy=multi-user.target
```
`deploy/install.sh`:
```bash
#!/bin/sh
# run ON THE BOARD from ~/aura-src: sh deploy/install.sh
set -e
cp deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
for s in aura-ear aura-brain aura-guardian aura-face aura-bridge; do
  systemctl enable --now "$s"
done
systemctl --no-pager status aura-ear aura-brain | grep -E "aura-|Active:"
```
- [ ] **Step 6: Deploy + board verify:** `sh deploy/push.sh <user@ip>`, then on board `sh deploy/install.sh`. Verify: `systemctl status` all 5 active; `aura status` shows a fresh state; dashboard reachable at `http://<boardip>:8080` from your phone; kill -9 the brain PID → systemd restarts it within 5 s.
- [ ] **Step 7: Commit**
```bash
git add aura/cli.py tests/test_cli.py deploy/systemd deploy/install.sh
git commit -m "feat: aura CLI + systemd deployment"
```

---

### Task 15: Data collection campaign (ops — runs while Tasks 6–14 proceed)

**Files:**
- Create: `docs/data-log.md` (session log table: name, date, hours, ground truth, notes)

- [ ] **Step 1:** NTP-sync check PC vs board (Task 6 interface note; offset ≤ 1 s).
- [ ] **Step 2:** Start the first recording night (board): `nohup aura record --session night1 &` before bed; PC labeler NOT needed for guaranteed-empty overnight sessions — log `night1: empty` in `docs/data-log.md`. Create `data/sessions/night1/labels.jsonl` on the PC side after copying: synthesize empty labels `python -c` one-liner documented in the log: every 5 s a `{"ts": t, "person": 0, "motion": 0.0}` row spanning the session.
- [ ] **Step 3:** Evening attended sessions (webcam on PC pointed at the room, labeler running; board recording): `eve1`, `eve2`, ... ≥ 2 h/day mixing sitting/reading/walking/chores. Copy `labels.jsonl` from PC into the session dir. Target by day 9: **≥ 20 h total, ≥ 4 empty + ≥ 4 occupied sessions.**
- [ ] **Step 4:** Pull sessions to PC daily: `scp -r <user@ip>:~/aura-src/data/sessions data/` — sessions live on the PC (gitignored), backed up to an external drive or cloud.
- [ ] **Step 5:** Commit the log: `git add docs/data-log.md && git commit -m "docs: data collection log"` (repeat as it grows).

---

### Task 16: Real-model training + metrics report

**Files:**
- Create: `training/evaluate.py`, `models/aura.onnx` (artifact, committed), `docs/metrics.md`

**Interfaces:**
- Consumes: all sessions, `calibration.json` link_ids (run `aura calibrate` on the board first — 10 min empty + 5 min walk).
- Produces: `training/evaluate.py` CLI `python training/evaluate.py --npz data/dataset.npz --model models/aura.onnx --val-sessions <held-out>` printing: presence acc, motion acc, activity MAE, baseline-vs-CNN comparison, and **FP/hour** = presence-positive windows in held-out *empty* sessions ÷ hours; writes `docs/metrics.md` table.

- [ ] **Step 1: Write `training/evaluate.py`**
```python
import argparse, json
import numpy as np
import onnxruntime as ort
from pathlib import Path

def evaluate(npz: Path, model: Path, val_sessions):
    d = np.load(npz, allow_pickle=True)
    mask = np.isin(d["session"], list(val_sessions))
    x, yp, ym, ya = d["x"][mask], d["y_presence"][mask], d["y_motion"][mask], d["y_activity"][mask]
    sess = ort.InferenceSession(str(model))
    lp, lm, la = sess.run(None, {"rf": x})
    sig = lambda z: 1 / (1 + np.exp(-z))
    pp, pm = (sig(lp) > 0.5).astype(int), (sig(lm) > 0.5).astype(int)
    empty = yp == 0
    hours = empty.sum() * 5.0 / 3600.0  # 5 s stride per window
    fp_per_h = float(pp[empty].sum() / hours) if hours > 0 else float("nan")
    out = {"presence_acc": float((pp == yp).mean()), "motion_acc": float((pm == ym).mean()),
           "activity_mae": float(np.abs(la - ya).mean()), "fp_per_hour_empty": fp_per_h,
           "n_val": int(mask.sum())}
    print(json.dumps(out, indent=2))
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", type=Path, required=True)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--val-sessions", type=str, required=True)
    a = ap.parse_args()
    evaluate(a.npz, a.model, a.val_sessions.split(","))
```
- [ ] **Step 2:** Build the real dataset (link_ids from the board's `calibration.json`):
`python -c "import json,glob; from pathlib import Path; from training.dataset import build_dataset; ids=json.load(open('data/calibration.json'))['link_ids']; build_dataset([Path(p) for p in glob.glob('data/sessions/*')], ids, Path('data/dataset.npz'))"`
(copy `calibration.json` from the board into `data/` first)
- [ ] **Step 3:** Train: `python training/train.py --npz data/dataset.npz --val-sessions <1 empty + 1 occupied held out> --out models/aura.onnx --epochs 30`
- [ ] **Step 4:** Evaluate → paste JSON into `docs/metrics.md` alongside spec targets (presence ≥ 90 %, FP < 1/night ⇒ `fp_per_hour_empty` ≤ 0.125, latency measured in Step 6). If presence acc < 90 %: collect 2 more occupied sessions and retrain before touching architecture.
- [ ] **Step 5:** Deploy model: `sh deploy/push.sh <user@ip>` (models/ ships with the package dir), `ssh <user@ip> systemctl restart aura-brain`, confirm `aura status` shows `"src": "cnn"`.
- [ ] **Step 6: Live latency + soak.** Scripted entries: from outside the room, start a stopwatch on door-open, stop when dashboard flips to PRESENT — 10 trials, record median in `docs/metrics.md`. Overnight armed-empty soak: set Away mode before bed, count alerts in the morning (target 0). 24 h uptime check: `systemctl status` uptimes next day.
- [ ] **Step 7: Commit**
```bash
git add training/evaluate.py models/aura.onnx docs/metrics.md
git commit -m "feat: trained model + honest metrics report"
```

---

### Task 17: Demo video + submission package

**Files:**
- Create: `docs/video-shotlist.md`, final `README.md` (rewrite), `docs/architecture.md`

- [ ] **Step 1:** Write `docs/video-shotlist.md` — the spec's story arc as numbered shots: (1) hook line over b-roll of the bare board; (2) prop camera draped with cloth — "cameras can be covered; Aura has no lens"; (3) lights off, person walks in → matrix blooms + phone Telegram buzz (film phone + matrix in frame); (4) dashboard waterfall rippling while walking; (5) "Learn my room" montage; (6) eldercare closing frame with the honest one-liner ("RF sensing, not imaging — and that's enough").
- [ ] **Step 2:** Film with a phone; 3–4 min cut in any open-source editor (e.g., Kdenlive/Shotcut). Voiceover reads from the shotlist.
- [ ] **Step 3:** Rewrite `README.md`: pitch, architecture diagram (mermaid), quickstart (board install → calibrate → run), metrics table copied from `docs/metrics.md`, honest "What it is / What it is not" section, privacy-by-design bullets (hashed MACs, LAN-only, no cameras). Write `docs/architecture.md` with the four-unit diagram + dual-brain (A53 thinks / M33 acts) figure.
- [ ] **Step 4:** Submit on the robu.in form (video + repo link + write-up) **before the deadline** — target ≥ 2 days early.
- [ ] **Step 5: Commit**
```bash
git add README.md docs/video-shotlist.md docs/architecture.md
git commit -m "docs: submission package — README, architecture, shotlist"
```

---

## Self-review notes (resolved inline)

- Spec §5.1 rolling-buffer rotation → `_rotate` in Task 5. Spec §5.2 calibration-recomputes-normalization simplified to link-selection + thresholds (matrix is self-normalizing per window by design — recorded as a deliberate simplification, baseline still uses calibrated thresholds).
- Spec's BLE fusion ships as a poller feeding `RFFrame.ble` but is not yet a model input (cut-list item #1; `build_matrix` ignores `ble` by design — adding BLE channels is a post-freeze stretch).
- Dashboard "walk" calibration phase is reachable via `POST /api/calibrate {"phase":"walk"}`; the UI button covers only "empty" (CLI covers walk) — acceptable for v1, noted in README quickstart.
- Type consistency check: `RFFrame`/`hash_mac`/`build_matrix(frames, link_ids, out_len)`/`summary` signatures consistent across Tasks 3, 5, 7, 8, 9, 10; state.json schema identical in Tasks 10, 11, 12, 13; label schema identical in Tasks 6, 9, 15.
