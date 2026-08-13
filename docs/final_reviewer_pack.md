# Final Reviewer Pack (Supporting Evidence)

> This pack helps reviewers inspect verified runtime surfaces. It is not the
> canonical product roadmap or current status. Use [the Direction ADR](adr/0001-opencare-product-direction.md),
> [project status](project-status.md), and [the capability matrix](capability-matrix.md)
> for those questions.

This is the fastest path for a reviewer who wants to inspect the current repo state without guessing where to start.

## What To Inspect First

1. Open the local reviewer route: `http://127.0.0.1:8000/demo/health-vault`
2. Open the guarded chat runtime surface: `http://127.0.0.1:8000/chat`
3. Inspect the family access surface: `http://127.0.0.1:8000/family-access`
4. Read [docs/health_family_vault_demo.md](health_family_vault_demo.md)
5. Read [docs/security/family-access-authorization-matrix.md](security/family-access-authorization-matrix.md)
6. Read [docs/security/family-access-threat-model.md](security/family-access-threat-model.md)
7. Read [docs/privacy_safety_threat_model.md](privacy_safety_threat_model.md)
8. Read [docs/provenance_semantics.md](provenance_semantics.md)

## Local Routes

- `/demo/health-vault` - read-only Health/Family Vault reviewer page
- `/` and `/chat` - guarded source-constrained chat workspace
- `/family-access` - local family identity and access management surface
- `POST /api/chat` - buffered and validated structured answer API
- `/demo/report-view?drug=sertraline` - existing supported PGx briefing path
- `/demo/report-view?drug=aspirin` - existing unsupported-drug safe no-claim path

## Key Docs

- [README.md](../README.md)
- [Portable health-agent skill](../skills/opencare-health-agent/README.md)
- [Portable skill reference notes](portable_skill_reference_notes.md)
- [docs/reviewer_quickstart.md](reviewer_quickstart.md)
- [docs/health_family_vault_demo.md](health_family_vault_demo.md)
- [docs/project-status.md](project-status.md)
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

## Validation

Use the commands above and record the fresh results in
[docs/project-status.md](project-status.md). Counts in older reviewer
snapshots are historical and are not a current baseline.

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
- Phase 2 Family Identity and Access Boundary with explicit consent and person-scoped permissions
- deny-by-default authorization, access audit, person export, and offline backup/recovery boundaries
- guarded chat with deterministic demo answers and optional operator-configured Responses adapter
- portable OpenCare health-agent skill with context export and answer validation CLI

## Portable Skill Commands

```powershell
.\.venv\Scripts\python.exe -m app.agent.cli export-context --vault-source demo --output context.json
.\.venv\Scripts\python.exe -m app.agent.cli validate-answer --context context.json --answer answer.json
.\.venv\Scripts\python.exe -m app.agent.cli demo-ask --vault-source demo --question "Which medications are recorded?"
```

The skill is manually copied into another agent workspace. OpenCare does not
perform universal installation, provide MCP, ingest documents, support genetics,
or provide diagnosis, treatment, or dosage-change advice. Validation reduces
unsupported output but cannot guarantee medical correctness.

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

OpenCare is best reviewed as an open-source, self-hosted personal/family health workspace with a synthetic reviewer surface and a real Phase 2 family identity/access boundary. Reviewers can inspect artifacts, reviewer routes, the authorization matrix, threat models, CI, and trust metrics directly. Genetics is a later layer. The LLM is a later interface layer. The repo does not claim medical authority.

Chat answers are source-constrained, policy-checked, and validated before display. They fail closed when checks fail, but they do not guarantee medical correctness or clinical safety. Demo conversations are not persisted. If an operator enables external Responses mode, compact vault context leaves OpenCare for that configured endpoint; the public synthetic demo remains deterministic and local.
