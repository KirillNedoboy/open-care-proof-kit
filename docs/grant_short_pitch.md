# Grant Short Pitch (Supporting Grant Artifact)

> Supporting grant language only. It must not be used as the canonical product
> roadmap or current implementation status. See [ADR 0001](adr/0001-opencare-product-direction.md)
> and [project status](project-status.md).

## 15-Second Pitch

OpenCare Proof Kit is not a medical chatbot. It is an open-source, self-hosted personal and family health workspace with local-first provenance, safety, audit, and person-scoped access controls.

## 30-Second Pitch

OpenCare Proof Kit is a vault-first repo for trustworthy personal and family
health-agent infrastructure. The current implementation combines a synthetic
reviewer surface with live Actor sessions, explicit consent, person-scoped
permissions, deny-by-default family access, D1 document evidence, P3 Genetics
Research Studio, audit, export, backup/recovery boundaries, CI, and trust
metrics. Genetics remains secondary; the LLM is an interface layer, not the
source of truth.

## 60-Second Pitch

OpenCare Proof Kit is not trying to be an AI doctor. It is building a
privacy-first personal/family health workspace with provenance, safety
boundaries, auditability, explicit consent, and person-scoped access. Public
fixtures are synthetic, while the self-hosted runtime is designed for
user-owned local health, document, and genetic data. Reviewers can inspect
`/workspace`, `/family-access`, `/genetics`, `/demo/health-vault`, threat models,
authorization docs, CI, and validation evidence. No diagnosis, treatment,
dosage, medication selection, or clinical decision support is claimed.

## 5-Bullet Reviewer Summary

- OpenCare is an open-source, self-hosted personal/family health workspace.
- P1/P2/D1/P3 are implemented with explicit consent and Person isolation.
- The repo is vault-first and useful without DNA.
- `/workspace`, `/family-access`, `/genetics`, and `/demo/health-vault` are
  distinct reviewer paths.
- D1 documents and P3 Genetics Research are bounded, deterministic, and
  source/provenance driven.
- The repo is synthetic/de-identified and makes no clinical-authority claim.

## 5-Bullet Technical Summary

- Product Core schema v9 with records, documents, review, Visit Briefs, export,
  backup, and recovery.
- FastAPI/Jinja `/workspace`, `/family-access`, `/genetics`, and
  `/demo/health-vault` surfaces.
- D1 immutable PDF/TXT evidence and P3 selective genetics/research boundaries.
- G1-G5 trust infrastructure and GitHub Actions CI.
- Deterministic P1/P2/D1/P3 reviewers and trust metrics.

## 5-Bullet Safety Summary

- Public fixtures and reviewer artifacts are synthetic/de-identified only.
- Self-hosted runtime data is local, sensitive, authorized, and provenance-bound.
- No diagnosis, treatment recommendation, dosage guidance, medication selection,
  or start/stop advice.
- Raw genome never enters provider context; Explore hypotheses remain labelled.
- Evals and trust metrics are engineering checks, not clinical validation.

## Application Wording Guardrails

Use:

- "not a medical chatbot"
- "privacy-first personal/family medical workspace foundation"
- "synthetic/demo-only"
- "vault first; genetics secondary"
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
