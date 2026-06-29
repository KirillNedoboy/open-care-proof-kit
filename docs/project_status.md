# Project Status

OpenCare Proof Kit is a local-first, synthetic-data-only proof kit for evidence-grounded health AI agents. The reference workflow remains Medication-to-Doctor Briefing: deterministic demo inputs, demo evidence-pack matching, safety policy enforcement, clinician-reviewable Markdown, and JSON audit output.

## Current Branch

```txt
phase-1-github-grant-readiness
```

## Public Repository

```txt
https://github.com/KirillNedoboy/open-care-proof-kit
```

The public GitHub repository has been created and pushed.

## Current Phase

Final submission-ready packaging.

The current public branch packages the grant/reviewer docs, submission answers, visual demo assets, demo video script, and final submission checklist. It does not change runtime behavior, add medical functionality, add new clinical claims, introduce real patient data, introduce real genetic data, or enable cloud raw genotype upload.

## Current Commits

- `f380cd6 feat: prepare grant-ready local health agent proof kit`
- `b46e336 feat: add minimal local web demo`
- `dda7958 feat: harden evidence pack validation and coverage reporting`
- `608fc11 feat: add pipeline-backed evals`
- `8b2c2fb docs: prepare github and grant readiness pack`
- `ed2ac9d docs: add grant submission answer pack`
- `ba6b4f9 docs: add visual demo assets`
- `53cb7f8 docs: add visual demo assets`
- `97bb70f docs: add final submission checklist`

## Current Capabilities

- Local CLI generation of Markdown briefings and JSON audits for the demo workflow.
- FastAPI endpoints and server-rendered pages for landing, demo, report, and audit inspection.
- Deterministic evidence-pack matching for the supported `sertraline` demo path.
- Safe unsupported-drug behavior for queries such as `aspirin`, with no clinical claim and explicit demo-only coverage limits.
- Strict evidence-pack validation for source domains, limitations, demo-only behavior, and no unauthorized clinical-action flags.
- Static-text eval guardrails plus pipeline-backed evals that execute the real local demo pipeline.
- GitHub/grant readiness docs: license, contribution policy, security policy, grant pack, roadmap, release checklist, and screenshot guide.
- Grant submission docs: copy-paste application answers, short pitches, conservative milestones, and application wording guardrails.
- Visual demo screenshots and a grant/reviewer demo video script.

## Current Validation State

Phase 1.9 validation:

```txt
pytest: 35 passed
ruff: passed
mypy: passed
total_cases: 12
static_text_cases: 7
pipeline_cases: 5
passed_cases: 12
failed_cases: 0
unsafe_advice_rate: 0.0
missing_source_rate: 0.0
uncertainty_missing_rate: 0.0
audit_missing_rate: 0.0
pipeline_failure_rate: 0.0
```

Validation commands:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
```

## Current Non-Goals

- diagnosis
- dosage recommendation
- start/stop medication advice
- real patient data
- FASTQ/BAM/WGS pipeline
- SaaS/auth/payments
- Telegram
- blockchain
- cloud raw genotype upload by default
- clinical claims beyond the local demo evidence pack

## Next Safe Roadmap

- Add lightweight CI or a local `make check` equivalent for reviewer-visible repeatability.
- Improve evidence-pack tooling without adding unsupported clinical claims.
- Add more pipeline-backed eval cases when new demo drugs or evidence-pack states are introduced.
- Improve clinician-review handoff and structured exports without automating clinical action.
- Research optional confidential compute adapters only after official docs and current research review.

## Visual Demo Asset Status

- `docs/assets/screenshots/landing.png`
- `docs/assets/screenshots/demo.png`
- `docs/assets/screenshots/sertraline-report.png`
- `docs/assets/screenshots/aspirin-safe-no-claim.png`
- `docs/demo_video_script.md`

Screenshots were captured from local pages under `http://127.0.0.1:8000/` with synthetic/demo data only. They are reviewer assets and do not add clinical functionality.

## Grant Submission Pack Status

- `docs/grant_submission_answers.md` provides copy-paste-ready long-form answers.
- `docs/grant_short_pitch.md` provides short spoken/written pitch variants.
- `docs/grant_milestones.md` provides conservative 30/60/90-day milestones.
- Wording guardrails emphasize doctor briefing, clinician-reviewable outputs, demo-only evidence-pack coverage, audit trail, private/local-first design, and not-medical-advice boundaries.
