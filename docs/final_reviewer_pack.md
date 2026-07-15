# Final Reviewer Pack

This is the fastest path for a reviewer who wants to inspect the current repo state without guessing where to start.

## What To Inspect First

1. Open the local reviewer route: `http://127.0.0.1:8000/demo/health-vault`
2. Open the guarded chat product: `http://127.0.0.1:8000/chat`
3. Read [docs/health_family_vault_demo.md](health_family_vault_demo.md)
4. Read [docs/privacy_safety_threat_model.md](privacy_safety_threat_model.md)
5. Read [docs/provenance_semantics.md](provenance_semantics.md)
6. Read [docs/vault_artifact_guarantees.md](vault_artifact_guarantees.md)

## Local Routes

- `/demo/health-vault` - read-only Health/Family Vault reviewer page
- `/` and `/chat` - guarded source-constrained chat workspace
- `POST /api/chat` - buffered and validated structured answer API
- `/demo/report-view?drug=sertraline` - existing supported PGx briefing path
- `/demo/report-view?drug=aspirin` - existing unsupported-drug safe no-claim path

## Key Docs

- [README.md](../README.md)
- [docs/reviewer_quickstart.md](reviewer_quickstart.md)
- [docs/health_family_vault_demo.md](health_family_vault_demo.md)
- [docs/project_status.md](project_status.md)
- [docs/final_submission_checklist.md](final_submission_checklist.md)

## Key Artifacts

- `docs/assets/health_vault/family-vault-read-model.json`
- `docs/assets/health_vault/family-vault-summary.md`
- `docs/assets/health_vault/family-vault-manifest.json`

## Key Commands

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.trust_metrics
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Current Validation Baseline

```txt
pytest: 161 passed
ruff: passed
mypy: no issues in 45 source files
evals.runner: 14 passed cases, 0 failed cases
evals.trust_metrics: passed
```

## What Is Implemented

- synthetic Health/Family Vault Core
- deterministic loader/validation
- deterministic read model
- deterministic local reviewer artifacts
- read-only reviewer UI at `/demo/health-vault`
- deterministic context/provenance trace graph
- privacy/safety threat model
- provenance semantics
- vault artifact guarantees
- GitHub Actions CI
- deterministic local trust metrics
- existing Medication-to-Doctor Briefing / PGx reference workflow
- guarded chat with deterministic demo answers and optional operator-configured Responses adapter

## What Is Explicitly Not Implemented

- diagnosis
- treatment recommendation
- dosage guidance
- medication selection advice
- start/stop medication advice
- clinical decision support
- clinical validation
- real patient support
- real genetic data support
- upload or user-input surface for the reviewer UI

## Grant Reviewer Summary

OpenCare is best reviewed as a vault-first, privacy-first workspace foundation for sensitive health-agent workflows. The current repo is synthetic/demo-only and lets you inspect artifacts, the reviewer route, the trace graph, the threat model, CI, and trust metrics directly. Genetics is a later layer. The LLM is a later interface layer. The repo does not claim medical authority.

Chat answers are source-constrained, policy-checked, and validated before display. They fail closed when checks fail, but they do not guarantee medical correctness or clinical safety. Demo conversations are not persisted. If an operator enables external Responses mode, compact vault context leaves OpenCare for that configured endpoint; the public synthetic demo remains deterministic and local.
