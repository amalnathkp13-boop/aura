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
- Rig stays at home for the whole campaign; classroom deployment reserved for post-submission demo via on-site calibration.

Open items:
- [ ] User confirms board placement room + that it stays powered
- [ ] Labeler camera connected (webcam / phone-as-webcam) → start labeler on PC
- [ ] User declares tonight's occupancy (empty overnight ⇒ gold empty labels)
- [ ] Target by day 9 of plan: ≥20 h total, ≥4 empty + ≥4 occupied periods
