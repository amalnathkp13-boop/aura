# Future work — occupancy counting and beyond

Status: **not part of the submitted system.** Written 2026-08-25, after the
submission freeze, to answer one question honestly: *does Aura detect more
than one person, and could it count?* Nothing here changes the claims in the
report; it records what the current code does with 2+ occupants and the
routes we consider viable on a bare UNO Q.

## What Aura reports today — and does not

The detector (`aura/brain/rfsense/detector.py`) emits `presence` (0/1),
`motion` (0/1), `activity` (0–100), `confidence`, and optionally one `zone`
label. There is no people-count anywhere in `aura/`.

With two or more people in the room:

- **Presence stays PRESENT** — if anything more reliably: more bodies bend
  more radio paths, so variance and motion-band energy rise. Multiple
  occupants do not break detection.
- **Activity** is log-scaled band energy clamped to 0–100
  (`RFDetector._activity`). It tracks *total* motion, which only loosely
  tracks headcount: one person pacing scores higher than two people sitting.
  A count cannot be read off it.
- **Zone** is a single nearest-match label (`RFDetector._match_zone`). Two
  people in two calibrated zones produce whichever signature dominates, or a
  flip between them — never "someone at the doorway *and* someone at the
  centre".
- **Confidence** is per-link vote agreement, not a count.

The 2026-08-23 validation session was single-operator throughout (empty /
entries / sitting / walking). Multi-person behaviour is therefore
**untested and unclaimed**, and the report's §9 wording ("presence, activity
and zones — never imaging or pose") stands.

## Why counting is hard on this radio

The UNO Q exposes RSSI only: one scalar disturbance value per link per
sample, on 2–4 links (hotspot link, 1–3 scanned APs, BLE when present).
Counting people from radio needs either channel state information
(per-subcarrier amplitude *and phase*) or many receivers with distinct
geometry; RSSI-based crowd-counting results in the literature use dozens of
links, not a handful, and still report coarse estimates. This is the same
"RSSI, not CSI" limitation stated in the report.

What *is* plausible on this hardware is a three-way answer —
**nobody / one / more than one** — via the routes below.

## Route A — multi-zone decomposition (RF-only, most Aura-native)

Today the zone matcher picks the single nearest signature. Replace it with a
non-negative decomposition: the current per-channel `(variance,
motion_band_power)` vector ≈ Σ wᵢ · zone_signatureᵢ (NNLS over the
calibrated zones). If two zones carry weight above a margin, report
`occupancy: "2+"`.

The idea that could make this work: motion **vigour scales every channel
together** (one energetic person), whereas two people in two places change
the **ratio between channels**. Count from the shape, vigour from the
magnitude.

**Honest caveat, measured on our own rig:** with channels that share one
physical path (board ↔ hotspot phone), zones separated by *magnitude*, not
by cross-channel pattern — two real zone signatures were cosine-0.997
parallel but 3× apart in magnitude (see the `_match_zone` docstring). On such
a geometry the decomposition collapses onto magnitude, which is exactly the
quantity vigour confounds. Route A therefore needs **diverse link geometry**:
three or more channels whose paths cross the room differently (an apartment
with several APs, or BLE beacons placed on different walls). On a
single-path rig it will not do better than the present zone label.

- Claim scope: `1` vs `2+`, never a number.
- Validation: a scripted **two-person** protocol (both still / one walking /
  both walking / two zones simultaneously), scored like
  `docs/validation-protocol.md`. Two team members make this runnable.
- Effort: ~1–2 days including validation. Deterministic; no training, no
  extra hardware.

## Route B — known-device BLE fusion (cheapest, strongest smart-home story)

The Ear already runs `bluetoothctl scan on` and writes salted-hash BLE MACs
into `frames.ble` (`aura/ear/ear.py`); it was empty during validation because
BLE fusion was on the feature cut-list, not because the plumbing is missing.

Pair household members' phones or watches, keep an allow-list of their hashed
identities → the dashboard reports *"home: <member>, <member>"* and a count of
**known members**. Then fuse with RF:

> RF presence **and** no known device nearby ⇒ *unknown person*.

That signal is more useful to Guardian's Away mode than any headcount
(family member vs intruder), and it is honest.

- Caveats to state in the UI: counts devices, not bodies; a phone left on the
  table counts; unpaired phones randomise their MAC (bonded devices resolve
  correctly); a member without a device is invisible to this route.
- Privacy: identities stay hashed with the existing per-install salt; members
  opt in by pairing.
- Effort: ~1 day, reusing the BLE poller and `hash_mac`.

## Route C — richer physical signal (a 30-minute spike, not a bet)

The UNO Q's Wi-Fi is a Qualcomm part driven by `ath10k` (confirm with
`readlink /sys/class/net/wlan0/device/driver`). Some ath10k firmware exposes
**spectral scan**: per-FFT-bin power across the channel (~56 bins per 20 MHz)
instead of one scalar. Frequency-selective fading differs per body, so
multi-body separation becomes conceivable. Still not CSI (no phase), but far
richer than RSSI.

Check: `ls /sys/kernel/debug/ieee80211/phy0/ath10k/` for
`spectral_scan_ctl`. Probability it is enabled on this firmware: low. Cost to
find out: half an hour.

## Route D — more receivers (the real fix)

RSSI counting works when there are many links with distinct geometry. A
multi-board room mesh with cooperative fusion — already listed in the
report's roadmap — turns counting into spatial clustering across N×M links.
Post-competition.

## Order of attack

1. **C** — half an hour, just to know what the radio can give.
2. **B** — biggest payoff per day; fits the Smart Homes theme; reuses
   existing plumbing.
3. **A** — only with diverse link geometry, and only with a two-person
   validation session behind it.
4. **D** — when there is more than one board.

Combined, the shipped story becomes: *presence → who (known members) →
1 vs 2+ → unknown-person alert.* At no stage should Aura advertise an exact
count.
