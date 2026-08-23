# Aura — camera-free presence AI on a bare Arduino UNO Q

Every Arduino UNO Q already contains an invisible motion sensor: **its own radio**.
Aura turns it on with pure software — privacy-first presence, intrusion, and
wellness sensing for smart homes, with **zero extra hardware, zero cameras,
zero cloud, and zero training data**.

Built for the **Arduino Physical AI Challenge India 2026** (theme: *Smart Homes
& Consumer AI*).

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

## Architecture

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
when to redo it.

## Validation

`docs/validation-protocol.md` defines a scripted live session (empty /
entries / sitting / walking, with declared truth timeline);
`training/validate.py` scores recorded frames chronologically and reports
presence accuracy, entry latency, and false-alarm windows per empty hour, for
both the fused detector and a naive baseline.

## Tests

97 automated tests cover feature extraction, classification, fusion,
calibration (including the walk gate and drift detection), zones, services,
and the dashboard API:

```sh
python -m pytest tests/
```

## License

MIT (see [LICENSE](LICENSE)). Portions adapted from an MIT-licensed upstream
project — see [NOTICE.md](NOTICE.md).
