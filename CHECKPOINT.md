# CHECKPOINT.md

## Project

OpenCare Proof Kit

## Current product version

v0.1 bootstrap / Codex-ready starter repo.

## Current phase

Phase 1.4 Evidence Pack Hardening

## Current status

Phase 1.4 hardens the demo evidence layer with strict source validation, explicit demo-only coverage reporting, and safe unsupported-drug behavior while preserving the existing local-first CLI/API/web demo boundaries.

## Last validated state

Phase 1.4 validation:

- pytest: 29 passed;
- ruff: passed;
- mypy: passed;
- eval runner: 7 passed cases, 0 failed cases;
- CLI wrote `reports/demo-sertraline-briefing.md`;
- CLI wrote `reports/demo-sertraline-audit.json`;
- CLI wrote `reports/demo-aspirin-briefing.md`;
- CLI wrote `reports/demo-aspirin-audit.json`;
- Server-rendered web pages worked:
  - `/demo/report-view?drug=sertraline`;
  - `/demo/report-view?drug=aspirin`;
- API endpoints worked:
  - `/demo/report?drug=sertraline`;
  - `/demo/report?drug=aspirin`;
  - `/demo/report.md?drug=sertraline`;
  - `/demo/audit?drug=sertraline`;
  - `/demo/audit?drug=aspirin`;
- audit recorded `policy_passed=True`;
- audit recorded `raw_health_or_genetic_data_exported=False`.

## Product definition

OpenCare Proof Kit is an open-source, local-first toolkit for private, evidence-grounded health AI agents.

The first reference workflow is Medication-to-Doctor Briefing: generating a clinician-reviewable briefing from demo/synthetic health vault data, genotype/VCF-like data, local evidence packs, deterministic rules, safety policy, and LLM/report writing.

This project is not an AI doctor, not a diagnostic system, and not a medication recommendation engine.

## Grant direction

Target: Sentient Foundation open-source AI grant.

Positioning:

- open-source infrastructure;
- local-first;
- private by default;
- empowering and public-good oriented;
- reusable evidence/safety/audit layer for health AI agents.

## Current repo capabilities

- Load a synthetic demo health vault.
- Parse demo genotype-like data.
- Load a local demo evidence pack.
- Match deterministic PGx rules for the sertraline reference workflow.
- Summarize demo evidence-pack coverage for supported and unsupported drug queries.
- Render a clinician-reviewable Markdown briefing.
- Run safety policy checks.
- Produce JSON audit metadata with report ID, app version, pipeline steps, evidence pack version, policy status, raw-export status, and demo coverage status.
- Generate report/audit files from the CLI.
- Serve minimal landing/demo/report HTML pages from FastAPI.
- Serve report/audit data from FastAPI.
- Run unit tests, lint checks, strict typing checks, and synthetic evals.

## Hard boundaries

Do not implement without explicit approval:

- diagnosis;
- dosage recommendation;
- start/stop medication advice;
- real patient data;
- FASTQ/BAM/WGS pipeline;
- AlphaMissense as clinical decision layer;
- SaaS/auth/payments;
- Telegram interface;
- blockchain;
- cloud raw genotype upload by default.

## MVP modules

```txt
app/vault       health vault schema/load/validate
app/genetics    genotype/VCF-like parser
app/evidence    evidence pack schema/loader
app/pgx         rule matcher
app/safety      policy engine
app/ai          report writer adapter
app/reports     markdown + audit JSON
app/demo_pipeline shared deterministic demo service
app/cli         local demo report/audit generator
evals           synthetic safety/evidence evals
tests           deterministic unit tests
docs            grant/product/architecture/safety/demo docs
```

## Required commands

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
python -m app.cli demo-report --drug sertraline --out-dir reports
uvicorn app.main:app --reload
```

## First implementation milestone

A local deterministic CLI/web pipeline:

```txt
demo patient
  -> genotype parser
  -> evidence pack matcher
  -> safety policy
  -> Markdown report
  -> audit JSON
  -> eval runner
```

## Completion criteria for milestone 1

Expected:

- tests pass;
- evals pass;
- generated report contains sources, limitations, safety note, clinician questions, and audit metadata;
- generated audit records policy status and raw-export status;
- API exposes report and audit endpoints;
- FastAPI exposes landing, demo, report-view, and reviewer quickstart browser paths;
- unsupported drugs return a safe no-claim report with `coverage_status=drug_not_in_demo_pack`;
- no medical advice or dosage recommendation;
- reviewer docs are clear enough to run the demo locally;
- SESSION_NOTES.md updated.

## Current next step

Add a lightweight CI workflow or local `make check` equivalent, then expand the demo evidence pack cautiously without weakening source validation, coverage disclosure, or medical-safety boundaries.
