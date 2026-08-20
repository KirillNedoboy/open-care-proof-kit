# Final Reviewer Pack (Supporting Evidence)

> This pack helps reviewers inspect verified runtime surfaces. It is not the
> canonical product roadmap or current status. Use [the Direction ADR](adr/0001-opencare-product-direction.md),
> [project status](project-status.md), and [the capability matrix](capability-matrix.md)
> for those questions.

This is the fastest path for a reviewer who wants to inspect the current repo state without guessing where to start.

## What To Inspect First

1. Open `/workspace` for the actor-scoped Health Workspace.
2. Open `/family-access` for explicit Person and Family authorization.
3. Open `/genetics` for the Genetics Workspace and Research Studio.
4. Open `/demo/health-vault` for the synthetic read-only reviewer surface.
5. Read [docs/p3-reviewer-guide.md](p3-reviewer-guide.md).
6. Read [docs/security/family-access-authorization-matrix.md](security/family-access-authorization-matrix.md).
7. Read [docs/privacy_safety_threat_model.md](privacy_safety_threat_model.md).
8. Read [docs/provenance_semantics.md](provenance_semantics.md).

## Local Routes

- `/workspace` — actor-scoped Health Workspace.
- `/family-access` — explicit Family Access and consent.
- `/genetics` — Genetics Workspace, PGx, comparison, and Research Studio.
- `/demo/health-vault` — synthetic read-only reviewer page.
- `/chat` — guarded source-constrained chat.
- `/demo/report-view?drug=sertraline` — frozen supported PGx reference path.
- `/demo/report-view?drug=aspirin` — frozen unsupported-drug safe no-claim path.

## Key Docs

- [README.md](../README.md)
- [Current project status](project-status.md)
- [Capability matrix](capability-matrix.md)
- [P3 reviewer guide](p3-reviewer-guide.md)
- [Reviewer quickstart](reviewer_quickstart.md)
- [Final submission checklist](final_submission_checklist.md)

## Key Artifacts

- `docs/assets/health_vault/family-vault-read-model.json`
- `docs/assets/health_vault/family-vault-summary.md`
- `docs/assets/health_vault/family-vault-manifest.json`

## Key Commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.trust_metrics
.\.venv\Scripts\python.exe -m evals.g5_review
.\.venv\Scripts\python.exe -m evals.p1_review
.\.venv\Scripts\python.exe -m evals.p2_review
.\.venv\Scripts\python.exe -m evals.d1_review
.\.venv\Scripts\python.exe -m evals.p3_review
.\.venv\Scripts\python.exe -m pip check
git diff --check
node --check app/static/product_core_workspace.js
node --check app/static/genetics.js
```

## What Is Implemented

- Actor-scoped `/workspace`, `/family-access`, `/genetics`, `/vault`, and
  `/chat` surfaces.
- Product Core schema v9 with medications, conditions, labs, Visits, Visit
  Briefs, document evidence, genetics datasets/findings, export, backup, and
  recovery.
- D1 authenticated PDF/TXT evidence ingest with immutable bytes, bounded
  extraction, provenance, review, and Family Access v3 document grants.
- P3 selective consumer-genotype indexing, reviewed evidence, PGx associations,
  family comparison, explicit genetics grants, Genetics Export, and
  Evidence/Explore Research Mode.
- G1-G5 trust infrastructure and deterministic final-phase reviewers.

## Portable Skill Commands

```powershell
.\.venv\Scripts\python.exe -m app.agent.cli export-context --vault-source demo --output context.json
.\.venv\Scripts\python.exe -m app.agent.cli validate-answer --context context.json --answer answer.json
.\.venv\Scripts\python.exe -m app.agent.cli demo-ask --vault-source demo --question "Which medications are recorded?"
```

The skill is manually copied into another agent workspace. OpenCare does not
perform universal installation or provide MCP. Product Core document ingest and
Genetics Research Studio are separate authenticated Workspace surfaces.
Diagnosis, treatment, dosage, medication selection, and start/stop advice remain
outside the product boundary.

## What Is Explicitly Not Implemented

- diagnosis;
- treatment recommendation;
- dosage guidance;
- medication selection advice;
- start/stop medication advice;
- clinical decision support;
- clinical validation or clinical authority;
- real patient/genetic fixtures in the public repository;
- upload or user-input surface on the synthetic `/demo/health-vault` page.

## Grant Reviewer Summary

OpenCare is best reviewed as an open-source, self-hosted personal/family health
workspace with a synthetic reviewer surface and authenticated live Product Core.
Reviewers can inspect `/workspace`, `/family-access`, `/genetics`, and
`/demo/health-vault`, plus the authorization matrix, threat models, CI, and
deterministic reviewers. Genetics is a secondary, bounded workspace layer. The
LLM remains an interface layer. The repository does not claim medical authority.

Chat answers are source-constrained, policy-checked, and validated before display. They fail closed when checks fail, but they do not guarantee medical correctness or clinical safety. Demo conversations are not persisted. If an operator enables external Responses mode, compact vault context leaves OpenCare for that configured endpoint; the public synthetic demo remains deterministic and local.
