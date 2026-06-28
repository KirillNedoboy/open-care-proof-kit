# Grant Short Pitch

## 15-Second Pitch

OpenCare Proof Kit is an open-source, local-first trust/evidence/safety kit for private health AI agents. It turns synthetic demo health context into clinician-reviewable doctor briefings with sources, limitations, audit trails, and executable safety evals.

## 30-Second Pitch

OpenCare Proof Kit is public-good infrastructure for sensitive personal AI. The current demo is Medication-to-Doctor Briefing: synthetic health and genotype-like data run through local evidence packs, deterministic PGx rules, safety policy, a report writer, JSON audit, and evals. Deterministic tools come before the LLM; the LLM explains only. It is not medical advice, diagnosis, dosage guidance, or a medication recommendation engine.

## 60-Second Pitch

Health AI agents will touch sensitive context: medications, symptoms, labs, family history, and genetics. OpenCare Proof Kit shows a safer open-source pattern. It runs locally, uses synthetic/demo data, matches local demo evidence rules before report writing, checks safety policy, and produces a clinician-reviewable doctor briefing plus JSON audit trail. Static-text and pipeline-backed evals catch unsafe advice patterns, missing sources, missing uncertainty, missing audit behavior, and real pipeline regressions. The project is infrastructure for trustworthy private agents, not a clinical product.

## 5-Bullet Reviewer Summary

- Open-source local-first proof kit for private health AI agents.
- Reference workflow: Medication-to-Doctor Briefing from synthetic/demo data.
- Deterministic tools run before LLM explanations.
- Outputs include sources, limitations, safety language, and JSON audit metadata.
- Evals are executable engineering guardrails, not clinical validation.

## 5-Bullet Technical Summary

- Python/FastAPI project with CLI, API, and server-rendered local demo pages.
- Synthetic health vault and genotype-like demo files.
- Local evidence-pack loader, validator, and deterministic PGx rule matcher.
- Markdown report generation plus JSON audit metadata.
- Static-text and pipeline-backed eval runner with 12 passing cases.

## 5-Bullet Safety Summary

- No diagnosis, dosage guidance, or medication start/stop instruction.
- No real patient or real genetic data in the demo.
- Unsupported drugs return safe no-claim output.
- Evidence-pack coverage is demo-only, not clinical coverage.
- Generated reports include safety note, clinician-review note, sources, limitations, and audit metadata.

## Application Wording Guardrails

Use:

- "doctor briefing"
- "clinician-reviewable"
- "evidence-pack coverage"
- "demo-only evidence"
- "audit trail"
- "private/local-first"
- "not medical advice"

Avoid:

- "diagnosis"
- "treatment recommendation"
- "which medication should I take"
- "dosage guidance"
- "clinical decision support"
- "genetic consultant"
- "real patient upload"
- "whole genome interpretation"
