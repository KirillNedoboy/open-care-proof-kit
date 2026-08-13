# Grant Short Pitch (Supporting Grant Artifact)

> Supporting grant language only. It must not be used as the canonical product
> roadmap or current implementation status. See [ADR 0001](adr/0001-opencare-product-direction.md)
> and [project status](project-status.md).

## 15-Second Pitch

OpenCare Proof Kit is not a medical chatbot. It is an open-source, self-hosted personal and family health workspace with local-first provenance, safety, audit, and person-scoped access controls.

## 30-Second Pitch

OpenCare Proof Kit is a vault-first repo for trustworthy personal and family health-agent infrastructure. The current implementation combines a synthetic reviewer surface with live Actor sessions, explicit consent, person-scoped permissions, deny-by-default family access, audit, export, backup/recovery boundaries, CI, and trust metrics. Genetics comes later; the LLM is an interface layer, not the source of truth.

## 60-Second Pitch

OpenCare Proof Kit is not trying to be an AI doctor. It is building the foundation that should exist before that kind of claim is even discussed: a privacy-first personal/family health workspace with provenance, safety boundaries, auditability, explicit consent, and person-scoped access. Today the repo includes the Health/Family Vault reviewer surface and a Phase 2 family identity/access boundary with deny-by-default authorization, audit, export, and recovery controls. Reviewers can inspect the artifacts, UI, threat models, authorization matrix, and validation evidence directly. Genetics remains later, and no diagnosis, treatment recommendation, dosage guidance, medication selection, or clinical decision support is added.

## 5-Bullet Reviewer Summary

- OpenCare is an open-source, self-hosted personal/family health workspace.
- Phase 2 adds explicit family identity, consent, and person-scoped access.
- The current repo is vault-first and useful without DNA.
- Reviewers can inspect artifacts, reviewer routes, authorization docs, threat models, CI, and trust metrics.
- The existing Medication-to-Doctor Briefing / PGx demo remains intact as a narrow reference workflow.
- The repo is synthetic/demo-only and does not claim real-patient, real-genetic, or clinical-decision capability.

## 5-Bullet Technical Summary

- Deterministic Health/Family Vault schemas, loader/validation, read model, artifacts, and trace graph.
- FastAPI/Jinja local reviewer route at `/demo/health-vault`.
- GitHub Actions CI for tests, lint, type checks, evals, and trust metrics.
- Local trust metrics that read committed manifest safety flags and eval totals.
- Existing PGx demo pipeline for report/audit/eval coverage remains unchanged.

## 5-Bullet Safety Summary

- Synthetic/demo-only current repo state.
- No real patient support and no real genetic data support yet.
- No diagnosis, treatment recommendation, dosage guidance, medication selection, or start/stop advice.
- Reviewer trace graph is provenance/traceability only, not medical interpretation.
- Evals and trust metrics are engineering checks, not clinical validation.

## Application Wording Guardrails

Use:

- "not a medical chatbot"
- "privacy-first personal/family medical workspace foundation"
- "vault first; genetics later"
- "synthetic/demo-only"
- "read-only reviewer UI"
- "provenance trace graph"
- "CI and trust metrics"

Avoid:

- "AI doctor"
- "diagnosis"
- "treatment recommendation"
- "dosage guidance"
- "clinical decision support"
- "real patient upload"
- "real genome analysis"
