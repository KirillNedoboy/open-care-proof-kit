# Grant Application Pack

## Project Title

OpenCare Proof Kit: Local-first evidence, safety, audit, and eval infrastructure for private health AI agents.

## Related Submission Docs

- `docs/grant_submission_answers.md` contains copy-paste-ready application answers.
- `docs/grant_short_pitch.md` contains 15-second, 30-second, and 60-second pitches.
- `docs/grant_milestones.md` contains conservative 30/60/90-day grant milestones.

## Short Pitch

OpenCare Proof Kit is open-source infrastructure for building private, evidence-grounded health AI agents. It provides a local-first reference pipeline, deterministic evidence matching, safety policy checks, Markdown reports, JSON audit trails, and evals that catch unsafe medical-advice drift.

## Long Pitch

Health AI agents will increasingly operate around sensitive personal context: medications, symptoms, labs, family history, and genetics. Closed, cloud-first LLM workflows make it difficult for users, clinicians, and reviewers to inspect what evidence was used, what data moved, and whether safety boundaries were preserved.

OpenCare Proof Kit offers a small, runnable, local-first proof kit for a safer pattern. The current reference workflow is Medication-to-Doctor Briefing. It uses synthetic health vault data, demo genotype-like data, a local demo evidence pack, deterministic PGx rule matching, safety policy checks, and a report writer to produce a clinician-reviewable briefing plus JSON audit metadata.

The project is deliberately scoped. It is not a doctor, diagnostic system, medication recommendation engine, or genomic interpretation pipeline. Its value is in reusable infrastructure for source-grounded, auditable, safety-checked health-agent workflows.

## Problem

Health-agent builders need patterns that:

- keep sensitive data local by default;
- make sources and limitations visible;
- run deterministic evidence tools before prose generation;
- prevent unsafe medical advice;
- produce inspectable audit metadata;
- provide evals that catch regressions.

Generic LLM wrappers do not provide enough structure for this domain. Closed systems also make it hard to verify privacy and evidence behavior.

## Solution

OpenCare Proof Kit provides:

- synthetic/demo-only local data fixtures;
- deterministic parsers and evidence matching;
- strict evidence-pack validation;
- safe unsupported-drug no-claim behavior;
- report generation with sources, limitations, safety notes, and clinician-review language;
- JSON audit metadata with policy status and raw-export status;
- static-text and pipeline-backed evals.

## Why Open Source

The project is infrastructure, not a closed health chatbot. Open source lets reviewers and downstream builders inspect:

- data flow;
- evidence-pack rules;
- safety policy;
- eval cases;
- report and audit generation;
- local-first defaults.

This makes the work reusable by other teams building sensitive-data agents.

## Why Private And Local-First

Medication and genetic context are sensitive. The reference workflow runs locally so reviewers can inspect outputs without sending raw health or genetic data to a cloud service. Audit metadata records `raw_health_or_genetic_data_exported=false` for the demo.

Any future confidential compute or private inference adapter should be optional, explicitly reviewed, and based on official documentation and current research.

## Current Demo

The current demo supports:

- `sertraline`: matched demo evidence-pack rule path;
- `aspirin`: unsupported-drug safe no-claim path.

Outputs:

- clinician-reviewable Markdown briefing;
- JSON audit metadata;
- FastAPI JSON/Markdown endpoints;
- server-rendered local web pages;
- eval result JSON.

## Technical Architecture

```txt
Synthetic demo health vault
  -> Demo genotype parser
  -> Local evidence pack loader
  -> Deterministic PGx rule matcher
  -> Demo evidence-pack coverage summary
  -> Markdown report renderer
  -> Safety policy checker
  -> JSON audit builder
  -> Static-text and pipeline-backed eval runner
```

The report writer is not the source of medical truth. It summarizes deterministic findings, limitations, sources, and clinician-review questions.

## Safety Model

The system must not generate:

- diagnosis;
- treatment plan;
- dosage adjustment;
- medication start/stop instruction;
- source-less medical claim;
- actionable claim from VUS or weak/model-only association;
- unsupported-drug clinical claim;
- hidden uncertainty.

Every report must include:

- safety note;
- clinician review note;
- evidence level;
- limitations;
- sources;
- audit metadata;
- demo evidence-pack coverage summary.

## Evals And Audit Trail

The eval suite currently reports:

```txt
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

Static-text evals check known unsafe wording patterns. Pipeline evals execute the real local demo pipeline and validate report text plus nested audit fields such as `coverage.coverage_status`, `coverage.matched_findings`, `policy_passed`, and `raw_health_or_genetic_data_exported`.

The audit trail records report ID, app version, pipeline steps, evidence-pack version, coverage status, safety policy status, and raw-export status.

## Milestones

### Completed

- Deterministic local demo pipeline.
- CLI report/audit generation.
- FastAPI endpoints and local web demo.
- Evidence-pack validation and coverage reporting.
- Safe unsupported-drug no-claim behavior.
- Static-text and pipeline-backed evals.
- GitHub/grant readiness documentation.

### Next

- Add CI or a local `make check` equivalent.
- Improve evidence-pack tooling.
- Add more pipeline-backed evals for demo evidence states.
- Improve structured exports for clinician review.
- Research optional confidential compute adapters after official docs and current research review.

## Requested Support / Use Of Funds

Requested support would fund:

- maintainer time for evidence-pack tooling;
- stronger synthetic eval coverage;
- CI and release hygiene;
- reviewer-facing demo assets;
- audit schema documentation;
- privacy-preserving adapter research;
- documentation and contributor onboarding.

This placeholder should be replaced with a concrete funding amount, budget, and timeline for the target grant.

## Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Unsafe medical advice drift | Safety policy, report constraints, and evals that fail on unsafe wording. |
| Source-less claims | Evidence-pack validation and no-source no-claim behavior. |
| Privacy leakage | Local-first default, synthetic demo data, ignored generated reports, and no raw cloud upload by default. |
| Overclaiming clinical validity | Docs explicitly state evals are engineering guardrails, not clinical validation. |
| Scope creep | Hard non-goals for diagnosis, dosage, WGS, SaaS, payments, bots, and blockchain. |

## Non-Goals

OpenCare Proof Kit does not aim to provide:

- diagnosis;
- medication recommendation;
- dosage guidance;
- start/stop medication instructions;
- real patient data processing in the demo;
- FASTQ/BAM/WGS interpretation;
- SaaS auth or payments;
- Telegram or bot workflows;
- blockchain features;
- cloud raw genotype upload by default;
- clinical validation claims.

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
