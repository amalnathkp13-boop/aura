# Aura — Camera-Free Room Sensing on a Bare Arduino UNO Q

**Design spec · 2026-08-13**
Competition: Arduino Physical AI Challenge India 2026 (robu.in + Arduino + Qualcomm)
Theme: **Smart Homes & Consumer AI** · Submission deadline: **~31 Aug 2026** (extended)

## 1. One-line pitch

Every Arduino UNO Q already contains an invisible motion sensor — its own radio. Aura turns it on with pure software and AI: privacy-first presence, intrusion, and wellness sensing with **zero extra hardware and zero cameras**.

## 2. Goals & constraints

- **Goal:** win the challenge — maximize innovation, functionality, documentation, and presentation scores.
- **Hard constraint (user):** the shipped project uses **only the Arduino UNO Q**. No ESP32, no radar, no attached sensors. A USB webcam is permitted **during the training phase only**, as a ground-truth labeling tool; it is not part of the product.
- **Honesty constraint:** pitch as *RF sensing with an imaging-style visualization*, never literal "through-wall imaging". Judges include Qualcomm RF engineers; overclaiming loses.
- **Timeline:** ~17 working days. Data collection must start by day 5.
- Solo builder; all tools open-source.

## 3. What Aura does (user-visible)

| Face | Behavior |
|---|---|
| LED matrix (8×13, on-board) | Empty room: idle radar sweep. Person present: "aura" bloom whose size tracks activity level. Alert: strobing pattern. Linux-heartbeat-loss: distinct fault pattern. |
| Web dashboard (served from the board, LAN) | Live RF waterfall (visibly ripples when someone walks), occupancy timeline, mode switcher, alert log, "Learn my room" calibration button. Polished dark UI. |
| Modes | **Home** (passive display), **Away/armed** (motion ⇒ intrusion alert), **Wellness** (no motion for N hours ⇒ inactivity alert — eldercare use case). |
| Alerts | Telegram bot message + dashboard log entry. Software-only actuation (needs only WiFi). |

## 4. Sensing principle

Human bodies absorb/reflect 2.4/5 GHz radio waves. Movement perturbs the many ambient radio paths between the UNO Q and its RF neighborhood. The UNO Q's radios can observe, without any extra hardware:

1. **Per-AP WiFi RSSI** from periodic fast scans (all visible access points — dense in Indian urban homes, typically 10–30 APs = 10–30 independent spatial links).
2. **High-rate connected-link RSSI** (station stats on the associated AP, amplified by self-generated ping traffic to the router).
3. **BLE advertisement RSSI** per nearby device (phones, wearables, TWS earbuds).

CSI is **not** available on this chip and is explicitly out of scope. Presence/motion/activity from ambient RSSI is well-replicated published science (device-free passive sensing); fine-grained localization/pose is not attempted.

## 5. Architecture (runtime units)

Data flows one way: **RF Ear → Aura Brain → { Face, Guardian }**. Each unit is a separate process with a file/socket interface, testable in isolation via recorded-session replay.

### 5.1 RF Ear — Linux (A53), Python daemon
- Owns all radio access (`iw` scan loop, station dump poll, BlueZ BLE scan; ping generator toward the router).
- Emits one **RF frame** every ~250 ms (target; design tolerates up to ~1 s): `{ts, wifi: {bssid: rssi,...}, link: [rssi samples], ble: {mac_hash: rssi,...}}`, appended to a rolling JSONL buffer + published on a local socket.
- MAC addresses are salted-hashed at capture time (privacy by design — a talking point).
- **Replay mode:** can stream a recorded session instead of live radios.

### 5.2 Aura Brain — Linux (A53), Python + ONNX Runtime
- Sliding 15 s window over RF frames → feature tensor:
  - per-link short-term variance / mean-normalized delta,
  - spectral energy of fluctuations in the 0.5–3 Hz band (human-motion rhythm),
  - cross-link disturbance correlation (true motion perturbs many links coherently; noise doesn't),
  - link-population stability metadata (top-K most stable links, K fixed).
- **Model:** 1D-CNN, ~100k params, three heads: `presence` (empty/present), `motion` (still/moving), `activity` (0–100 regression). PyTorch-trained on PC → ONNX → ONNX Runtime CPU inference on the A53 (ms-level latency), ≥2 inferences/s.
- **Baseline:** variance-threshold detector, always computed alongside the CNN. Serves as (a) demo safety net, (b) rigor comparison in the write-up.
- **Calibration ("Learn my room"):** guided 10 min empty + 5 min walking capture → recomputes per-link normalization stats and baseline thresholds on-device. Runs at any new venue.

### 5.3 Face — dashboard (Linux) + LED matrix (M33)
- **Dashboard:** small Python web server (FastAPI/Flask + vanilla JS/canvas; no build chain). Waterfall renders the raw feature stream — this is the "imaging-style" visualization.
- **LED matrix:** Arduino sketch on the STM32U585 (M33). Receives only `{presence, motion, activity, alert}` over the Arduino Bridge RPC a few times per second; renders all animation autonomously. If RPC goes silent >5 s → fault pattern. This is the dual-brain story: Qualcomm side thinks, STM32 side acts in real time.

### 5.4 Guardian — Linux, state machine
- Modes Home/Away/Wellness; debounced alert rules (e.g., motion sustained ≥3 s while armed; no motion ≥ N h in Wellness).
- Notification delivery: Telegram bot + dashboard log. Rate-limited; alert cooldown.

### 5.5 Labeler — training-time only
- USB webcam + off-the-shelf person-detection model (on PC or on the A53) writes `{ts, person_visible, motion_pixels}` alongside RF recordings.
- Produces the labeled dataset; deleted from the product story after training. No images retained — only labels.

### 5.6 Ops
- All Linux units run under systemd with auto-restart; single `aura` CLI to start/stop/record/replay/calibrate.

## 6. ML pipeline

1. **Collect (days 3–9, unattended):** 24/7 recording. Overnight/work hours ⇒ guaranteed-empty gold. Evenings ⇒ present-still and moving. Target **≥20 h** across multiple days/times (RF neighborhoods breathe; temporal diversity is the real regularizer). Optional: second-person sessions.
2. **Label:** webcam auto-labels; manual spot-check of session boundaries.
3. **Train (PC):** session-level train/val split (never window-level — leakage). Standard augmentation: link dropout (APs vanish in the wild), amplitude jitter, time warp.
4. **Deploy:** ONNX export → on-board inference; calibration recomputes normalization only (no on-device backprop).
5. **Evaluate:** metrics below, computed on held-out full sessions and scripted live runs.

## 7. Success metrics (published in the report)

- Presence accuracy **≥90%** on held-out sessions.
- False alarms **<1 per night** in armed mode (overnight scripted run).
- Detection latency **≤5 s** from door entry (stopwatch-timed scripted entries).
- End-to-end uptime: 24 h unattended run without manual intervention.

## 8. Risks & designed answers

| Risk | Answer |
|---|---|
| RSSI noisier than hoped | Coarse classes only; fluctuation features; threshold baseline as guaranteed floor. |
| WiFi driver limits scan rate | **Day-1 feasibility spike** measures achievable frame rate; window design tolerates 2–4× slower frames. Monitor-mode/per-packet capture is a bonus if the driver allows, never a dependency. |
| Venue RF ≠ home RF | "Learn my room" on-site calibration; demo video (the actual submission artifact) filmed at home. |
| New board/OS quirks | systemd auto-restart everywhere; matrix fault pattern instead of silent death; all state on disk, reboot-safe. |
| Schedule slip | Feature-freeze gate at day 13: Wellness mode and BLE fusion are the designated cut-list items (intrusion demo + dashboard + matrix are the core). |

## 9. Testing

- **Unit:** each stage of Brain's feature computation against golden recorded fixtures; Guardian state machine against scripted event sequences.
- **Replay:** full pipeline runs against recorded sessions in CI-style local runs — regressions catchable without a human in the room.
- **End-to-end:** scripted overnight armed-empty run (false-alarm count); scripted entries (latency); 24 h soak.

## 10. Submission package

- **Video (3–4 min, story arc):** camera draped with cloth → lights off → person enters → matrix blooms, phone buzzes → waterfall ripples on the dashboard → "Learn my room" montage → eldercare framing close.
- **Repo (open-source):** full code, README with architecture diagram, dataset description + collection protocol, honest metrics table (baseline vs CNN), reproduction guide.
- **Write-up:** leads with the one-line pitch; explicit "what it is / what it is not" honesty section; dual-brain utilization diagram; privacy-by-design notes (no cameras, hashed MACs, all processing on-device, nothing leaves the LAN except opt-in Telegram alerts).

## 11. Timeline (~17 days to ~Aug 31)

| Days | Work |
|---|---|
| 1–2 | Board bring-up, App Lab/SSH, **RF feasibility spike** (achievable scan rate, link-stats rate, BLE scan rate) |
| 3–5 | RF Ear + recorder + Labeler; **start 24/7 data collection** |
| 6–9 | Feature pipeline + baseline detector + dashboard skeleton (data accumulates in background) |
| 10–12 | Train CNN, ONNX deploy, calibration routine |
| 13–15 | LED matrix sketch + Guardian + Telegram + dashboard polish · **feature-freeze gate** |
| 16–17 | Metrics runs, film video, write docs · ~1 day buffer |

## 12. Out of scope (YAGNI)

- CSI, monitor-mode dependence, through-wall claims, person identification, pose/localization, multi-room, cloud services, mobile app, any additional hardware.
