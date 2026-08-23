# Validation run — day-of checklist

Full protocol: `docs/validation-protocol.md`. This is the condensed run card.

## Before the session
0. **Phone (hotspot) parked in the board's room, untouched, for the whole
   session** — it is the far end of the sensing link. Never carry or use it
   during any phase. Fans near the sensing path OFF (log fan state).
1. Board on + hotspot up; find it: `ssh arduino@xfiles.local` (mDNS), else
   ping-sweep the PC's /24 and match the ssh host key.
2. Calibrate (once): dashboard "Learn my room", or
   `aura calibrate empty --minutes 10` (leave room) then
   `aura calibrate walk --minutes 5`.
3. Restart brain to load thresholds (real terminal, needs board password):
   `ssh -t arduino@xfiles.local "sudo systemctl restart aura-brain"`
4. Confirm: `state.json` has `src:"rfsense"`; `calibration.json` has `"rv"` keys.

## Session phases (record epoch at each boundary)
Get epoch: `python -c "import time; print(time.time())"`

| Phase | Duration | Action | truth |
|---|---|---|---|
| A | 30 min | leave room entirely | empty |
| B | 10 entries | in, stand 30 s, out, wait 150 s | walking / empty (empty starts 135 s after exit) |
| C | 30 min | sit still | present |
| D | 10 min | move continuously | walking |

During Phase B entries: stopwatch the dashboard/LED reaction — that is the
spec's <= 5 s latency evidence (the tool's floor is ~15 s).

## After the session
    scp "arduino@xfiles.local:~/.aura/frames.jsonl" data/validation/frames.jsonl
    scp "arduino@xfiles.local:~/.aura/calibration.json" data/validation/calibration.json
    .venv\Scripts\python -m training.validate data/validation/frames.jsonl data/validation/timeline.json --cal data/validation/calibration.json
    .venv\Scripts\python -m training.validate data/validation/frames.jsonl data/validation/timeline.json --cal data/validation/calibration.json --detector baseline

Fill `timeline.json` from `timeline.example.json` (absolute epoch seconds).

## Targets
- presence_acc >= 0.90
- latency: report tool median (floor ~15 s stated) + stopwatch median for <= 5 s claim
- false alarms: empty_motion_false_windows / empty_hours; overnight Away run < 1 alert
