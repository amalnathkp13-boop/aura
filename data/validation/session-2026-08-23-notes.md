# Validation session 2026-08-23 — phase boundary log (epochs, board/PC NTP-synced)

Calibration: empty_p995 0.026, rv thresholds loaded (brain restart 07:24:38Z, redeploy restart 07:29:41Z).
Conditions: phone parked in room (untouched), ceiling fan OFF, midday, user + laptop outside room.

| Phase | truth | t0 | t1 | notes |
|---|---|---|---|---|
| A | empty | 1787470377 | 1787472177 | **INVALID — phone handled/moved from ~min 11 (13:14 IST), ruined min 18–29** (link mean −53→−76→−34 dB; both channels voted active). Only min 0–10 clean. Phone ended ~19 dB closer to the board → calibration stale → afternoon walk-in test missed. Re-run after recalibration. |
| B | walking/empty | | | 10 entries; per-entry epochs + stopwatch below |

Post-mortem 16:08–17:00: replay of afternoon test entry (real in ~16:24:11, out ~16:24:37; user clock ~1 min fast)
showed scan channel active var up to 6.3 within 2 s of entry, __link__ blind (var 0.46 vs stale thr 1.43), 2-channel
majority tie discards single witness (investigated & KEPT — empty scan blips are indistinguishable from real
single-channel hits by margin/duration/vote-type). Shipped instead: calibration-drift detection (9466921).

## Phase B entries (epoch at "in" / "out"; stopwatch = doorway→dashboard-present, seconds)
| # | in | out | stopwatch s |
|---|---|---|---|
