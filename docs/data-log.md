# Aura data collection log

Recording mechanism: the `aura-ear` systemd service writes the live spool `/home/arduino/.aura/frames.jsonl` 24/7 (4 Hz). An hourly board cron archives rotated chunks into `~/aura-src/data/sessions/live_archive/frames_<epoch>.jsonl`. The PC pulls sessions with `scp -r arduino@192.168.63.60:~/aura-src/data/sessions data/`.

Ground truth comes from (a) the PC webcam labeler (`aura.labeler`) during attended periods — camera must see the same room the board is in; PC and board clocks are both NTP-synced (verified 2026-08-13), and (b) user-declared occupancy windows recorded in this table for unattended periods.

| Session / period (IST) | Frames | Ground truth | Notes |
|---|---|---|---|
| bank1 · 2026-08-13 ~13:10–13:20 | 2,102 | occupied (user present, setup activity) | Ad-hoc pre-service recording during rig setup |
| live spool · 2026-08-13 13:16 → ongoing | 4 Hz continuous | labeler + declarations below | aura-ear service; archived hourly |

**Declared ground truth (user statements):**
- Board room = user's BEDROOM (someone sleeps there every night).
- 2026-08-13 ~14:20 IST onward: user in room; overnight 13→14 Aug = OCCUPIED, sleeping (person=1, motion≈0). NOT empty-room data.
- Empty windows expected during college hours — user to declare departure/return times daily.
- 2026-08-13 **14:40 IST: user declared "leaving now"** → room EMPTY from ~14:40 until user returns (phone/hotspot/camera stayed home). Labeler had silently stalled 14:19–14:45 (hung socket); labeler rewritten (direct MJPEG parser + socket timeouts). Camera labels absent while DroidCam's stale session holds the single client slot (frees on phone-side timeout or when user returns); declaration covers the window.
- 2026-08-13 **~15:15 IST: empty window CLOSED** (user back and interacting with the dashboard by ~15:40; conservative close at 15:15). Net clean EMPTY data: 14:40–15:00. 15:15 onward = OCCUPIED (user home, active).
- 2026-08-13 **~14:57–15:05 IST: POWER-CUT DRILL** (deliberate board reboot). EXCLUDE this window from training (reboot RF churn, brief recording gap). Result: 4 services + clock + recording auto-recovered; matrix app did NOT (status failed) → fixed with aura-matrix-boot.service (delayed retry at boot) + manual restart. Baseline (auto-default thresholds) showed presence=1 during empty-room drill churn — expected; CNN + real calibration replace it.
- Rig stays at home for the whole campaign; classroom deployment reserved for post-submission demo via on-site calibration.

**Appliance ground truth:** ceiling fan runs at night while sleeping (user-declared 2026-08-13) → overnight occupied data = fan ON. Needed for contrast: several hours of **fan ON + room EMPTY** (user to leave fan on when departing some day-windows) so the model learns fan ≠ person. Log fan state with each declared window.

**2026-08-20 (IST) network event + detector upgrade:** phone hotspot randomized its subnet (192.168.63.0/24 → 192.168.248.0/24); board now at 192.168.248.60 (use `arduino@xfiles.local`). Until the fix, the board's `gateway_ip` pointed at the dead old gateway → the link-RSSI stream (8-samples/frame channel) was degraded/absent for an UNKNOWN window ending **2026-08-19 19:40:36 UTC** (= 2026-08-20 01:10:36 IST), when config was corrected and aura-ear + aura-brain restarted. Treat frames in that window as scan-only (WiFi channels valid, link channel suspect). Same restart deployed the **deterministic detector** (state.json `src` then "ruview", renamed "rfsense" 2026-08-23); board is UNCALIBRATED (no calibration.json) → auto-default thresholds until "Learn my room" is run per docs/validation-protocol.md.

**2026-08-23 calibration session (~11:30–13:00 IST):** "Learn my room" completed end-to-end (calibration.json with full `rv` thresholds; brain reloaded 07:24:38 UTC). Hard-won lesson: **the hotspot phone is the far end of the sensing link** — it must sit parked and untouched in the board's room for every calibration phase AND validation. Attempt windows (UTC epochs), for anyone reusing frames.jsonl:
- empty#1 1787464775–1787465375: mostly quiet; contaminated ~+300–420 s (phone handled outside the room).
- walk#1 1787465643–1787465943 and walk#2 1787466238–1787466538: genuine walking but the user CARRIED the phone — link motion partly from the phone, not just the body. Gate correctly failed both.
- empty#2 1787466976–1787467576: heavily contaminated (user actively using the phone outside the room) — do not use as empty truth.
- board power-cycled onto a **new power supply** ~06:57 UTC; post-change static-link noise floor is var<1 (previously ≥1.3 even when quiet).
- empty#3 1787468615–1787469215: CLEAN empty (phone parked, ceiling fan OFF, user away) — `empty_p995` 0.026.
- walk#3 1787469348–1787469648: CLEAN walk (phone parked) — gate PASSED; walk/empty motion-band separation ≈3.6× on `__link__`.
Fan state for all three clean windows: OFF (the fan-ON-empty contrast item below still stands).

Open items:
- [x] Board placement: user's bedroom, stays powered (2026-08-13)
- [x] Labeler camera: DroidCam via direct MJPEG parser (2026-08-13)
- [ ] Fan-ON empty window (≥2 h) — ask user to leave fan on at next departure
- [ ] Metrics (Task 16): scripted "fan on, room empty, 1 h" false-alarm test for the report
- [ ] Target by day 9 of plan: ≥20 h total, ≥4 empty + ≥4 occupied periods
