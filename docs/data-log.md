# Aura data collection log

Recording mechanism: the `aura-ear` systemd service writes the live spool `/home/arduino/.aura/frames.jsonl` 24/7 (4 Hz). An hourly board cron archives rotated chunks into `~/aura-src/data/sessions/live_archive/frames_<epoch>.jsonl`. The PC pulls sessions with `scp -r arduino@192.168.63.60:~/aura-src/data/sessions data/`.

Ground truth comes from (a) the PC webcam labeler (`aura.labeler`) during attended periods — camera must see the same room the board is in; PC and board clocks are both NTP-synced (verified 2026-08-13), and (b) user-declared occupancy windows recorded in this table for unattended periods.

| Session / period (IST) | Frames | Ground truth | Notes |
|---|---|---|---|
| bank1 · 2026-08-13 ~13:10–13:20 | 2,102 | UNKNOWN — ask user | Ad-hoc pre-service recording; usable only if user recalls room occupancy |
| live spool · 2026-08-13 13:16 → ongoing | 4 Hz continuous | pending labeler + user log | aura-ear service; archived hourly |

Open items:
- [ ] User confirms board placement room + that it stays powered
- [ ] Labeler camera connected (webcam / phone-as-webcam) → start labeler on PC
- [ ] User declares tonight's occupancy (empty overnight ⇒ gold empty labels)
- [ ] Target by day 9 of plan: ≥20 h total, ≥4 empty + ≥4 occupied periods
