# Contributing to Aura

Thanks for your interest. Aura is small and deliberately deterministic; the
bar for changes is "still explainable, still validated".

## Development setup

```sh
git clone https://github.com/amalnathkp13-boop/aura.git && cd aura
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev,board]"
python -m pytest tests/                            # 112 tests, ~30 s
ruff check aura training tests
```

No hardware is needed for the test suite or for reproducing the published
results (see *Reproduce on your PC* in the README). Board-side work needs an
Arduino UNO Q; `deploy/push.sh` and `deploy/install.sh` document the deploy
path.

## Ground rules

- **Tests first.** New behaviour comes with a test; bug fixes come with a
  regression test that fails before the fix.
- **Keep it deterministic.** The detector is threshold-based signal
  processing by design. Learned models are welcome as *experiments* under
  `training/`, not as replacements for the shipped path.
- **Don't inflate claims.** Anything stated in the README or docs must be
  backed by a scored session in `data/validation/` or by the validation
  protocol. Aura claims presence / motion / activity / zones — never imaging,
  pose, identity, or people counts.
- **Attribution stays.** `aura/brain/rfsense/features.py` and
  `classifier.py` are ports of an MIT-licensed upstream; `NOTICE.md` must
  remain accurate and must not be removed.
- **Calibration honesty.** Changes to calibration or fusion must be re-run
  against `data/validation/session-2026-08-23-frames.jsonl` and the numbers
  in the README updated from the tool's output, not edited by hand.

## Pull requests

1. Branch from `main`; keep PRs focused.
2. CI must be green (ruff + pytest on 3.11 and 3.13).
3. Use conventional prefixes in commit subjects: `feat:`, `fix:`, `docs:`,
   `test:`, `chore:`, `ci:`.
4. Describe *what changed in the detector's decisions* if anything did, with
   before/after numbers from `python -m training.validate`.

## Reporting problems

Bugs and questions: GitHub Issues. Security concerns: see `SECURITY.md`.
