# Aura — demo video script (target 4:15, limit 3–5 min)

## Recording constraints (read first)
- **The hotspot phone is the sensor** — during every LIVE segment it stays
  parked. Record live segments as **screen captures** (Win+Alt+R Game Bar or
  OBS) of the dashboard, and film physical shots with a second device or
  laptop webcam.
- Shoot **b-roll of the board/room FIRST** (phone can move freely then),
  calibrate, then screen-record the live segments.
- Telegram alert shot: use Telegram Web/Desktop on the laptop, not the phone.
- Voiceover can be recorded last over the edit; script below reads at
  ~140 wpm.

## Shot list

| # | Time | Visual | Narration |
|---|---|---|---|
| 1 | 0:00–0:25 | B-roll: a webcam/CCTV camera, then a hand covering it. Cut to black. Title card: **AURA** | "Every smart home faces the same trade-off: to know someone's there, you point a camera at your family. Aura refuses that trade-off. No camera. No microphone. No motion sensor. In fact — no sensor at all." |
| 2 | 0:25–0:50 | B-roll: the bare UNO Q on a table, slow pan. Overlay text: "Bill of materials: 1 item" | "This is the entire system: one Arduino UNO Q. Nothing attached. Aura's insight is that the board already contains an invisible presence sensor — its own WiFi radio." |
| 3 | 0:50–1:20 | Screen: dashboard **RF Sensing Console** — the room view with the ellipse + link rays (point at them with the cursor) | "Every radio link around the board — the connection to the home hotspot, every access point it can hear — is an invisible tripwire. A human body bends these radio paths. Aura reads those disturbances: deterministic signal processing, on-device, fully explainable. No cloud, no training data, no black box." |
| 4 | 1:20–2:20 | **LIVE:** screen-record dashboard showing EMPTY, then walk into the room. Presence flips to PRESENT, motion MOVING, activity gauge rises, zone label appears. Keep the wall-clock/stopwatch visible in frame | "The room is empty — and the dashboard agrees. Now watch: I walk in… detected. Present, moving, activity level — and Aura even names the zone I'm in, from a two-minute calibration signature. Everything you see is a real detector internal: per-link votes, thresholds, live vote fractions." |
| 5 | 2:20–2:50 | **LIVE:** stand still in the room → PRESENT/STILL holds. Then film the board's **LED matrix radar** pulsing (second device), or use pre-recorded matrix b-roll | "I stop moving — and Aura keeps knowing I'm here. A still person is not an empty room. The board's second brain, the M33 microcontroller, mirrors it all on the LED matrix — the UNO Q's dual-brain design in one device." |
| 6 | 2:50–3:25 | Screen: Guardian mode switch to **Away**; walk in; Telegram Web notification pops on the laptop | "Guardian modes make it a product. Away mode: any presence raises an instant Telegram alert — a security system with nothing to point at your family. Wellness mode inverts it: no movement all morning in an elderly parent's home? That's the alert." |
| 7 | 3:25–3:55 | Screen: press "Learn my room"; cut to the **red drift banner**; then the calibrated dashboard | "Aura calibrates itself to your room in fifteen minutes — and it's honest about its limits. A quality gate rejects a calibration that can't actually see you walk, and if the radio geometry ever changes — say the router moves — Aura detects the drift and tells you to recalibrate, instead of silently going blind." |
| 8 | 3:55–4:15 | Terminal: `97 passed`. Architecture diagram. End card: GitHub URL + "Aura — your home already senses you. Privately." | "Ninety-seven automated tests, a replayable flight-recorder pipeline, fully open source under MIT. Aura: privacy-first presence AI, from hardware you already own." |

## Edit notes
- Overlay a small caption on live shots: "real-time screen recording — no cuts".
- Keep shot 4 as ONE continuous take (walk-in + flip on screen) — it is the
  40-point Functionality proof.
- Never say "through-wall", "imaging", or "sees you" — the pitch is
  "RF sensing with imaging-style visualization".
- Export 1080p, MP4; keep under 5:00 hard.
