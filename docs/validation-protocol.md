# Live validation protocol (no pre-recorded data required)

Produces the honest metrics table for the submission: presence accuracy,
detection latency, false alarms. Total hands-on time ~2.5 h; the board records
by itself throughout (aura-ear service, 4 Hz).

## 0. Calibrate the room (once per venue, ~15 min)
On the dashboard press "Learn my room", or:
    aura calibrate empty --minutes 10     # leave the room first
    aura calibrate walk --minutes 5       # walk around the room
This derives the per-link RuView thresholds (calibration.json, key "rv").

## 1. Scripted session (note wall-clock times as you go)
| Phase | Duration | You do | truth label |
|---|---|---|---|
| A | 30 min | leave the room entirely (phone can stay) | empty |
| B | 10 entries | walk in, stand 30 s, walk out, wait 60 s outside | walking / empty alternating |
| C | 30 min | sit still in the room (read, no walking) | present |
| D | 10 min | move around the room continuously | walking |

Write the timeline as JSON (absolute epoch seconds; get them with
`python -c "import time; print(time.time())"` at each phase boundary):
    [{"t0": 1755600000, "t1": 1755601800, "truth": "empty"}, ...]

## 2. Pull the frames and score
    scp "arduino@192.168.63.60:~/.aura/frames.jsonl" data/validation/frames.jsonl
    .venv\Scripts\python -m training.validate data/validation/frames.jsonl ^
        data/validation/timeline.json --cal data/validation/calibration.json
(scp calibration.json from the board too: ~/.aura/calibration.json)

## 3. Targets (from the design spec)
- presence_acc >= 0.90
- entry_latency_s <= 5 (window step is 5 s; <= 10 is still reportable honestly)
- empty_motion_false_windows: report as false-alarms-per-hour of empty time
- Overnight bonus run: leave mode=Away armed all night, count alerts (< 1).

Report both the RuView detector row and the baseline row (run validate twice,
second time after setting "detector": "baseline" — or just cite state.json src).
Cite upstream RuView's own accuracy claims as upstream's, never as ours.
