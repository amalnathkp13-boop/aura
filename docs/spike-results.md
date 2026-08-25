# Task 2 — Board bring-up + RF feasibility spike results (2026-08-13)

## Access
- Board: Arduino UNO Q, hostname `xfiles`, `arduino@192.168.63.60` (SSH key auth installed; password auth exists but is not used by tooling — never store it in this repo).
- OS: Debian GNU/Linux 13 (trixie), kernel 6.16.7 aarch64, Python **3.13.5**, 4 cores, ~3.7 GB RAM (4GB variant).
- Network: WiFi `wlan0`, gateway/hotspot `192.168.63.14` (phone hotspot). `NetworkManager` active. Board clock is NTP-correct (UTC).

## WiFi sensing measurements
- `iw` was NOT preinstalled → `apt-get install iw`; binary at **/usr/sbin/iw** (not in user PATH). A sudoers drop-in `/etc/sudoers.d/aura-iw` grants the `arduino` user passwordless `sudo iw` (daemons run as root via systemd and don't need it).
- **Full scan: ~7.0 s** consistently (`sudo iw dev wlan0 scan`), sees **1–3 APs** in this environment (sparse — hotspot setting; expect more in an apartment). Back-to-back scans can return instantly with 0 BSS (radio busy) — the ScanPoller's cached-latest design tolerates this.
- **`iw dev wlan0 scan dump`: ~0.12 s** (cached results, includes `signal:` dBm lines) — cheap freshness between real scans if ever needed.
- **`station dump` (connected link): rich and fast** — with `ping -i 0.2` to the gateway running, `signal:` moved -57→-50→-44→-42→-50→-46 dBm across ~2 s of 0.3 s polls. This is the sensing workhorse; polling at ~7 Hz is sustainable.
- **Config decision:** `scan_interval: 8.0` (measured), `frame_hz: 4.0` unchanged (assembler uses cached poller values), `gateway_ip: 192.168.63.14` (per-venue; recalibrate + update when the board moves).

## BLE
- `bluetoothctl` present but controller **Powered: no** by default → scans return nothing until `bluetoothctl power on`. BLE stays cut-list item #1; if enabled, the BlePoller must power the controller on first.

## Linux ↔ M33 channel + LED matrix API (from on-board App Lab example `led-matrix-painter`)
- Mechanism is **RPC, not raw serial**: sketch side `#include <Arduino_RouterBridge.h>`; `Bridge.begin(); Bridge.provide("name", handler);` with handlers like `void draw(std::vector<uint8_t>)` running on a separate Zephyr thread (guard shared state with `K_MUTEX_DEFINE`). Python side `from arduino.app_utils import App, Bridge; Bridge.call("draw", frame_bytes)`.
- `arduino.app_utils` is **only importable inside the App Lab app runtime** (plain `python3` → ModuleNotFoundError). Apps are managed by `arduino-app-cli app new/start/stop/restart/logs` from `app.yaml` + `python/` + `sketch/`; examples live in `/var/lib/arduino-app-cli/examples/`.
- Matrix: `Arduino_LED_Matrix` library present (zephyr core 0.54.1). API: `matrix.begin()`, `matrix.setGrayscaleBits(n)` (values 0..2^n-1), `matrix.draw(const uint8_t*)` for a 104-byte (8 rows × 13 cols) grayscale framebuffer; `renderBitmap(fb, rows, cols)` macro → `loadPixels`. Our sketch's ADAPT-A include guess was correct; ADAPT-B becomes `matrix.draw((uint8_t*)fb)`.
- **Deployment decision:** python daemons (ear/brain/guardian/face) run under **systemd** as root from `~/aura-src`; the matrix face ships as a small **Arduino App** (`board-app/aura-matrix/`: app.yaml + sketch with `Bridge.provide("state", ...)` + a python main that `Bridge.call`s 4 bytes `[presence, motion, activity, alert]` at 5 Hz — wire semantics of `aura/face/bridge.py`, the PC-testable reference). **Learned during 13b:** an app's python runs in a Docker container WITHOUT `~/.aura` access — the app therefore polls the aura-face dashboard's read-only HTTP API (`/api/state`, `/api/alerts` via the framework's `HOST_IP`) instead of reading files; it degrades to zero-state (radar sweep) if aura-face is down.

## Serial devices (for reference)
- `/dev/ttyHS1`, `/dev/ttyMSM0` exist; not used — RouterBridge RPC is the sanctioned channel.

## Verdict
**PASS.** Frame cadence target holds (4 Hz assembly; scan channel refreshes every ~8 s; link channel refreshes at multi-Hz). Sparse-AP environment (1–3) means the connected-link stream carries most of the signal here — the feature pipeline's dead-channel handling (xcorr exclusion, zero-row padding) was built for exactly this. Sensing quality improves automatically in denser RF environments; calibration ("Learn my room") absorbs the difference.
