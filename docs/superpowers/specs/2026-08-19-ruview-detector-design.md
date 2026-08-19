# Aura × RuView — No-Training Detector on the UNO Q

**Design spec · 2026-08-19** · extends `2026-08-13-aura-rf-sensing-design.md`

## 1. Goal

Ship Aura without training a model. The 1D-CNN (old Task 16: collect → label → train → deploy)
leaves the critical path. In its place, the deterministic RSSI-sensing algorithms from the
open-source **RuView** project become Aura's primary detector, fed by Aura's own multi-link RF
frames and tuned per-room by the existing on-device "Learn my room" calibration.

**User constraints (unchanged):** Arduino UNO Q only — no ESP32, no CSI, no extra hardware.
No dependence on previously recorded data. Maximize accuracy within those bounds.

## 2. Why this shape (alternatives ruled out)

- **RuView's pretrained models** (`ruvnet/wifi-densepose-pretrained`) take CSI input — 56
  subcarriers per link captured by ESP32 firmware. The UNO Q's WiFi chip cannot produce CSI and
  adding an ESP32 violates the hardware constraint. Ruled out by physics, not effort.
- **RuView's datasets:** none shipped; it references the external MM-Fi dataset, which is also
  CSI-shaped. Unusable for an RSSI pipeline.
- **Running RuView's stack as-is on the board:** its `LinuxWifiCollector` reads only the single
  connected link from `/proc/net/wireless` and would contend with aura-ear for the radio. Weaker
  input, duplicate stack, weak originality story.
- **Chosen:** port RuView's *algorithms* (feature extractor + rule-based classifier) into Aura's
  brain, where they receive strictly richer input (all visible APs + high-rate link samples).

## 3. Upstream provenance & licensing

- Repo: `https://github.com/ruvnet/RuView` (MIT license), pinned at commit
  **`81cc241b9ebf8ccfb7cffd8e2e086e16c81f8a22`** (2026-04-26).
- Files ported: `archive/v1/src/sensing/feature_extractor.py` (331 lines),
  `archive/v1/src/sensing/classifier.py` (201 lines). Their `rssi_collector.py` is **not** used —
  aura-ear remains the only process touching the radio.
- Attribution: a `NOTICE.md` at repo root records the upstream repo, commit, files, MIT license
  text, and a summary of local modifications. The submission write-up credits RuView explicitly.

## 4. Architecture

New package `aura/brain/ruview/` (vendored-and-adapted, not pip-installed):

### 4.1 `features_rv.py` — per-link feature extraction
Port of `RssiFeatureExtractor`, adapted:
- **Input:** a 1-D numpy RSSI series for one link (one row of Aura's existing window matrix)
  plus the frame rate (4 Hz), via the upstream `extract_from_array()` path. No `WifiSample`
  objects, no window trimming (Aura's brain already owns windowing).
- **numpy-only:** `scipy.fft.rfft` → `np.fft.rfft` (identical math); `scipy.stats.skew/kurtosis`
  dropped — the classifier never reads them (recorded in NOTICE.md). Retained features: mean,
  variance, std, range, IQR, dominant frequency, breathing-band power (0.1–0.5 Hz),
  motion-band power (0.5–3.0 Hz), total spectral power, CUSUM change points.
- CUSUM detector (`cusum_detect`) ported verbatim.
- Window: Aura's existing 15 s window (60 samples @ 4 Hz) — upstream default is 30 s but its
  math is window-agnostic; 60 samples gives 0.066 Hz FFT resolution, adequate for the
  0.5–3 Hz motion band that drives classification. (Breathing band 0.1–0.5 Hz is retained but
  under-resolved at 15 s; it only contributes to a confidence term, never to classification.)

### 4.2 `classifier_rv.py` — per-link classification + multi-link fusion
Port of `PresenceClassifier` (rules verbatim: variance ≥ threshold ⇒ presence; motion-band
energy ≥ threshold ⇒ ACTIVE vs PRESENT_STILL; 60/20/20 confidence model), plus a fusion layer
upstream doesn't have:
- Each of the top-K stable links (existing link-selection logic in `features.py`) is classified
  independently, passing the other links' results as upstream's `other_receiver_results` — RuView's
  own cross-receiver agreement mechanism, repurposed link-as-receiver.
- **Fused decision:** stability-weighted vote across links. Presence is declared when the
  weighted fraction of links voting PRESENT_STILL-or-ACTIVE exceeds 0.5; motion likewise for
  ACTIVE. A single noisy link cannot outvote several quiet ones — this is the accuracy
  mechanism (coherent multi-link disturbance = person; isolated fluctuation = noise).
- **Activity 0–100:** fused (stability-weighted mean) motion-band energy, log-scaled between the
  calibrated empty-room floor and walking ceiling, clamped.

### 4.3 Brain integration
- `config.yaml`: new key `detector: ruview | baseline | cnn`, default **`ruview`**.
  `brain.py` dispatches on it; unknown/missing model file for `cnn` falls back to `ruview`.
- The output contract is unchanged: brain keeps writing `state.json` with its existing schema
  (presence, motion, activity, plus per-detector detail fields) — the dashboard, Guardian,
  Telegram alerts, and LED matrix require **zero changes**.
- The variance baseline stays computed alongside (existing behavior) as the safety net and the
  comparison row in the metrics table.

### 4.4 Calibration = the no-training story
"Learn my room" (existing flow: ~10 min empty + ~5 min walking) additionally derives the RuView
thresholds per link:
- `presence_variance_threshold[link]` = p95 of empty-window per-window variance × 1.5 (margin
  constant, tunable in config).
- `motion_energy_threshold[link]` = geometric midpoint between p95 empty motion-band energy and
  median walking motion-band energy.
- Activity scale floor/ceiling from the same two captures.
Upstream defaults (0.5 dBm², 0.1) serve as pre-calibration fallbacks. Stored in the existing
calibration JSON; recalibratable at any venue in ~15 min. No gradient descent anywhere.

## 5. Error handling

- Link with <4 valid samples in a window → skipped (upstream guard), weight 0.
- All links skipped → detector reports the baseline's decision with `confidence=0`, and the
  existing dead-channel handling (dashboard fault surfacing) applies.
- Config `detector: cnn` without a model file → log once, run `ruview`.

## 6. Testing

TDD per project convention:
1. **Port fidelity:** synthetic still (flat + small noise) vs. moving (0.5–3 Hz modulated)
  series → correct ABSENT/ACTIVE per link; CUSUM flags an injected step; numpy FFT band powers
  match hand-computed values.
2. **Fusion:** one noisy link among four quiet ones → fused ABSENT; three-of-four disturbed →
  fused presence. Stability weighting respected.
3. **Calibration:** threshold derivation from synthetic empty/walking captures lands between the
  two populations.
4. **Brain-level:** existing replay harness runs with `detector: ruview` and produces the same
  state.json schema; CNN and baseline paths still pass their existing tests.
5. **Live validation (no recorded data required):** scripted at-home protocol — ≥30 min empty
  room, 10 stopwatch-timed entries, ≥30 min present-still, ≥10 min walking → metrics table
  (presence accuracy, detection latency, false alarms). Success targets unchanged from the base
  spec (§7): ≥90% presence accuracy, <1 false alarm/night, ≤5 s entry latency. If the board's
  6-day auto-archive turns out intact, replay validation is a free bonus, not a dependency.

## 7. Out of scope

- CNN training (kept in-repo as an optional upgrade path; one honest line in the write-up).
- RuView's server/API/dashboard/collector, CSI, ESP32, pose, vital signs.
- BLE fusion (unchanged cut-list position).

## 8. Submission-story note

Pitch line: "Aura's detector builds on the MIT-licensed RuView sensing algorithms, extended with
multi-link fusion and on-device room calibration — no training data, no cloud, calibrates to any
room in 15 minutes." Honesty framing per base spec §2 applies (no through-wall/pose claims;
upstream's accuracy figures are cited as upstream's, ours come from our own live protocol).
