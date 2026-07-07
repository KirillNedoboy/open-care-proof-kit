# Grant Short Pitch

## 15-Second Pitch

OpenCare Proof Kit is not a medical chatbot. It is an open-source, local-first foundation for a privacy-first personal/family medical workspace, with a synthetic Health/Family Vault, reviewer artifacts, a read-only reviewer UI, and deterministic trust checks.

## 30-Second Pitch

OpenCare Proof Kit is a vault-first repo for trustworthy personal health AI infrastructure. The current implementation is a synthetic/demo-only Health/Family Vault with deterministic schemas, validation, read model, reviewer artifacts, a read-only `/demo/health-vault` page, a context/provenance trace graph, CI, and trust metrics. The older Medication-to-Doctor Briefing / PGx demo still runs as a narrow reference workflow. Genetics comes later. The LLM is an interface layer, not the source of truth.

## 60-Second Pitch

OpenCare Proof Kit is not trying to be an AI doctor. It is building the foundation that should exist before that kind of claim is even discussed: a privacy-first personal/family medical workspace with provenance, safety boundaries, auditability, and visible unsupported states. Today the repo implements that foundation with synthetic/demo-only Health/Family Vault data, deterministic loaders and read models, committed reviewer artifacts, a read-only reviewer UI, a context/provenance trace graph, CI, and trust metrics. Reviewers can inspect the artifacts, UI, threat model, provenance semantics, and validation outputs directly. The existing Medication-to-Doctor Briefing / PGx path remains as the narrow demo workflow. No diagnosis, treatment recommendation, dosage guidance, medication selection, or clinical decision support is added.

## 5-Bullet Reviewer Summary

- OpenCare is a privacy-first personal/family medical workspace foundation.
- The current repo is vault-first and useful without DNA.
- Reviewers can inspect artifacts, the read-only reviewer UI, the trace graph, the threat model, CI, and trust metrics.
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
