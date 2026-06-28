# Project Status

OpenCare Proof Kit is a local-first, synthetic-data-only proof kit for evidence-grounded health AI agents. The reference workflow remains Medication-to-Doctor Briefing: deterministic demo inputs, demo evidence-pack matching, safety policy enforcement, clinician-reviewable Markdown, and JSON audit output.

## Current commits

- `f380cd6` baseline
- `b46e336` web demo
- `dda7958` evidence hardening

## Current capabilities

- Local CLI generation of Markdown briefings and JSON audits for the demo workflow.
- FastAPI endpoints and server-rendered pages for landing, demo, report, and audit inspection.
- Deterministic evidence-pack matching for the supported `sertraline` demo path.
- Safe unsupported-drug behavior for queries such as `aspirin`, with no clinical claim and explicit demo-only coverage limits.
- Strict evidence-pack validation for source domains, limitations, demo-only behavior, and no unauthorized clinical-action flags.
- Static-text eval guardrails plus pipeline-backed evals that execute the real local demo pipeline.

## Current non-goals

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

## Validation commands

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports
.\.venv\Scripts\python.exe -m app.cli demo-report --drug aspirin --out-dir reports
```

## Next safe roadmap

- Add lightweight CI or a local `make check` equivalent for reviewer-visible repeatability.
- Expand demo evidence-pack coverage only with explicit sources, explicit limitations, and preserved fail-closed unsupported-drug behavior.
- Add more pipeline-backed eval cases when new demo drugs or evidence-pack states are introduced.
- Improve reviewer ergonomics without changing the deterministic-first, local-first, non-medical-advice boundaries.
