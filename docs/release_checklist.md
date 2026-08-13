# Release Checklist

Use this checklist before tagging a release, opening a grant review branch, or publishing a demo package.

## Validation

- [ ] Run `.venv\Scripts\python.exe -m pytest`.
- [ ] Run `.venv\Scripts\python.exe -m ruff check app tests evals`.
- [ ] Run `.venv\Scripts\python.exe -m mypy app evals`.
- [ ] Run `.venv\Scripts\python.exe -m evals.runner`.
- [ ] Confirm eval metrics include 0 failed cases.

## CLI Demos

- [ ] Run `.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports`.
- [ ] Run `.venv\Scripts\python.exe -m app.cli demo-report --drug aspirin --out-dir reports`.
- [ ] Confirm generated reports include sources, limitations, safety note, clinician-review note, and audit metadata.
- [ ] Confirm aspirin remains a safe unsupported-drug no-claim path.

## Web Demo Smoke

- [ ] Start `.venv\Scripts\python.exe -m uvicorn app.main:app --reload`.
- [ ] Open `/`.
- [ ] Open `/demo`.
- [ ] Open `/demo/report-view?drug=sertraline`.
- [ ] Open `/demo/report-view?drug=aspirin`.
- [ ] Open `/demo/report.md?drug=sertraline`.
- [ ] Open `/demo/audit?drug=sertraline`.

## Repository Hygiene

- [ ] Run `git status --short`.
- [ ] Run `git diff --stat`.
- [ ] Run `git status --short --ignored reports`.
- [ ] Confirm generated reports are ignored.
- [ ] Confirm no generated report or audit file is staged.
- [ ] Confirm no secrets are staged.
- [ ] Confirm `.env` is not staged.
- [ ] Confirm no real patient data is present.

## Documentation

- [ ] README reflects current commands, eval metrics, and boundaries.
- [ ] `docs/project-status.md` reflects latest release and validation state.
- [ ] `CHECKPOINT.md` reflects current phase and next step.
- [ ] `SESSION_NOTES.md` records what changed.
- [ ] `CONTRIBUTING.md` and `SECURITY.md` remain accurate.

## Optional Demo Assets

- [ ] Capture screenshots listed in `docs/screenshots.md`.
- [ ] Record a short demo video.
- [ ] Verify screenshots/video contain only synthetic/demo data.
