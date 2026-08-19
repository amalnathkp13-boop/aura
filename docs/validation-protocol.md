# Live validation protocol (no pre-recorded data required)

Produces the honest metrics table for the submission: presence accuracy,
detection latency, false alarms. Total hands-on time ~2.5 h; the board records
by itself throughout (aura-ear service, 4 Hz).

## 0. Calibrate the room (once per venue, ~15 min)
On the dashboard press "Learn my room", or:
    aura calibrate empty --minutes 10     # leave the room first
    aura calibrate walk --minutes 5       # walk around the room
This derives the per-link RuView thresholds (calibration.json, key "rv").
Then restart the brain so it loads the new thresholds: `ssh -t arduino@xfiles.local "sudo systemctl restart aura-brain"` (needs the board password; run in a real terminal). Note: a calibration.json created before the RuView upgrade has no `rv` thresholds - re-run Learn my room once after deploying.

Board address: use `arduino@xfiles.local` (mDNS) — the phone hotspot randomizes
its subnet on config changes, so a hard-coded IP goes stale (it did on
2026-08-20: 192.168.63.60 → 192.168.248.60). If mDNS fails, find the board by
its ssh host key on the current subnet.

## 1. Scripted session (note wall-clock times as you go)
| Phase | Duration | You do | truth label |
|---|---|---|---|
| A | 30 min | leave the room entirely (phone can stay) | empty |
| B | 10 entries | walk in, stand 30 s, walk out, wait 150 s outside | walking / empty (label each gap empty starting 135 s AFTER you walk out — the detector intentionally holds presence for 120 s after motion; earlier gap windows would mislabel that decay as error) |
| C | 30 min | sit still in the room (read, no walking) | present |
| D | 10 min | move around the room continuously | walking |

Write the timeline as JSON (absolute epoch seconds; get them with
`python -c "import time; print(time.time())"` at each phase boundary):
    [{"t0": 1755600000, "t1": 1755601800, "truth": "empty"}, ...]

## 2. Pull the frames and score
    scp "arduino@xfiles.local:~/.aura/frames.jsonl" data/validation/frames.jsonl
    .venv\Scripts\python -m training.validate data/validation/frames.jsonl data/validation/timeline.json --cal data/validation/calibration.json
(scp calibration.json from the board too: ~/.aura/calibration.json)

## 3. Targets (from the design spec)
- presence_acc >= 0.90
- entry_latency_s: the tool scores windows at their end time, so its floor is ~15 s (win_s); report the measured median with that floor stated. The spec's <= 5 s target is assessed by stopwatch observation of the dashboard/LED matrix during Phase B entries, not by this tool.
- false alarms: report empty_motion_false_windows / empty_hours (both in the tool's output) as false-alarm windows per empty hour.
- Overnight bonus run: leave mode=Away armed all night, count alerts (< 1).

Report both the RuView detector row and the baseline row (run validate twice,
second time adding `--detector baseline`).
Cite upstream RuView's own accuracy claims as upstream's, never as ours.
