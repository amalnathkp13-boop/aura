# Repository polish — design

Date: 2026-08-25. Status: approved (chat), tier B.

## Goal

Make github.com/amalnathkp13-boop/aura read as a finished, professional
open-source project to a competition judge or any engineer landing on it:
visible proof the tests pass, the results and how to reproduce them on a PC,
correct license detection, complete package metadata, standard OSS hygiene
files, and a tagged release of the submitted state. No new product claims;
every number shown must come from the published validation data.

## Non-goals

- No formatter pass (would rewrite 45 of 54 Python files days before judging).
- No directory renames (`docs/superpowers/`, `training/`, `sketch/` stay;
  they are explained instead).
- No `aura demo` implementation (separate spec, 2026-08-23).
- No change to `docs/submission/report.html` or the PDFs (they mirror what
  was submitted).
- No personal emails anywhere in the tree.

## Deliverables

1. **README.md** — badges (CI, MIT, Python >= 3.9, tests, UNO Q); dashboard
   screenshot as hero; system-diagram PNG in Architecture with the ASCII
   diagram kept in a collapsible; a *Results* table (rfsense vs naive
   baseline) taken from `python -m training.validate` on the published
   session; a *Reproduce on your PC — no hardware* section with that exact
   command; demo-video link (public Drive link already in the report); a
   *Repository layout* table; team line. Existing prose and claims kept.
2. **LICENSE** — verbatim MIT template so GitHub detects `MIT`. The upstream
   pointer stays in README and NOTICE.md.
3. **pyproject.toml** — version 1.0.0, description, readme, license, authors
   (names only), keywords, classifiers, project URLs,
   `[tool.pytest.ini_options]`, `[tool.ruff]` selecting only E4/E7/E9/F.
4. **.gitattributes** — `* text=auto eol=lf`; images/PDF/docx marked binary;
   one renormalisation commit.
5. **CI** — `.github/workflows/ci.yml`: `lint` job (`ruff check`) and `test`
   job (pytest on ubuntu-latest, Python 3.11 and 3.13, pip cache,
   `.[dev,board]` plus CPU torch/onnx so the ONNX-export test runs),
   concurrency cancel-in-progress. Lint findings fixed (unused imports and
   the like; no behavioural change; full suite re-run locally).
6. **CONTRIBUTING.md, SECURITY.md, CHANGELOG.md** — short, accurate.
7. **GitHub settings** — wiki and projects disabled; private vulnerability
   reporting enabled; homepage set to the demo video. Social-preview image is
   UI-only: user uploads `docs/submission/Aura-Dashboard-Console.png`.
8. **Release** — tag `v1.0.0` on the final commit; GitHub Release
   "v1.0.0 — competition submission" with `Aura-Project-Report.pdf` and
   `Aura-System-Diagram.png` attached (public files only).
9. The untracked `2026-08-23-one-paste-demo-design.md` spec is committed as
   design history (status: approved, not implemented).

## Verification

- `python -m pytest tests/` passes locally (106) after lint fixes.
- CI run on GitHub is green (`gh run watch`).
- `gh api repos/amalnathkp13-boop/aura/license` returns `MIT`.
- README renders on GitHub with images and badges; reproduce command copied
  from the README runs on a clean checkout.
- No new email addresses, tokens, or hostnames introduced (`git grep`).

## Commit plan

Plain messages, no trailers (repo rule). Logical commits: spec+plan; license
and metadata; gitattributes renormalise; lint fixes; CI; hygiene files;
README; release tag.
