# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-08-25

State submitted to the Arduino Physical AI Challenge India 2026.

### Added
- Deterministic RF presence detector (`rfsense`): per-link features, rule
  classifier, Aura-original multi-link fusion with presence hysteresis.
- Calibration flow ("Learn my room") with walk-phase quality gate and
  calibration-drift detection.
- Zone localisation from per-channel disturbance signatures.
- Guardian modes (Home / Away / Wellness) with Telegram alerts and the
  `aura telegram-connect` one-command setup.
- Live dashboard (RF Sensing Console) and LED-matrix radar on the UNO Q's
  M33 via the Linux↔MCU bridge.
- Published, scored validation session (`data/validation/`) and the scoring
  harness (`training/validate.py`).
- 106 automated tests; CI on Python 3.11 and 3.13.

### Documented
- Validation protocol, data log, spike results, future-work analysis of
  multi-occupant behaviour and coarse occupancy routes.

[1.0.0]: https://github.com/amalnathkp13-boop/aura/releases/tag/v1.0.0
