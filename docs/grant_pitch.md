# Grant Pitch

## One-Liner

OpenCare Proof Kit is open-source infrastructure for private, evidence-grounded health AI agents: local-first data loading, deterministic evidence tools, safety policy checks, audit trails, and evals, with Medication-to-Doctor Briefing as the first reference workflow.

## Problem

Health AI agents will operate around some of the most sensitive personal data: medications, symptoms, labs, family history, and genetics. Generic LLM applications are not enough for this domain because they can blur evidence, omit uncertainty, invent sources, or produce unsafe medical advice.

At the same time, closed cloud-first products can require users to surrender raw health or genetic context before they see any value. That model is difficult to trust, difficult to audit, and misaligned with users who need privacy-preserving tools for sensitive decisions.

## Solution

OpenCare Proof Kit provides a reusable trust/evidence/safety layer for health AI agents:

- local-first demo execution;
- synthetic/demo data by default;
- deterministic parsers and rule matching before report writing;
- local evidence packs with source and limitation fields;
- explicit safety policy;
- Markdown report plus JSON audit;
- open eval suite for unsafe-output patterns.

The first reference workflow is pharmacogenomics Medication-to-Doctor Briefing. It uses a synthetic patient and demo genotype-like data to produce a clinician-reviewable briefing about what to discuss with a clinician. It does not recommend medication choice, dosage, or start/stop actions.

## Why This Is Open-Source Infrastructure

The project is not trying to own the patient relationship, monetize a closed chatbot, or become a SaaS workflow in v0.1. Its value is in reusable building blocks:

```txt
private/local data input
  -> deterministic normalization
  -> evidence pack
  -> rule matcher
  -> safety policy
  -> report writer
  -> audit JSON
  -> eval suite
```

Other health-agent builders can reuse the pattern for different evidence-grounded workflows while preserving the same principles: source grounding, local-first execution, safety boundaries, and auditability.

## Private-By-Default

The demo runs locally and uses synthetic/demo data. The audit trail records that raw health or genetic data was not exported. Cloud raw genotype upload is not enabled by default and is outside the MVP boundary.

Privacy is not a marketing layer added after the product works. It is part of the architecture: deterministic local data handling comes before any report-writing layer.

## Empowering, Not Extractive

The output is meant to help a person prepare a better clinician conversation. It does not replace a clinician, make a diagnosis, prescribe, recommend dosage, or instruct medication changes.

The report exposes:

- the evidence source;
- the evidence level;
- limitations;
- uncertainty;
- clinician-review language;
- safety status;
- audit metadata.

That makes the workflow inspectable instead of opaque.

## Reference Workflow

Medication-to-Doctor Briefing:

1. Load a synthetic demo health vault.
2. Parse demo genotype-like data.
3. Load a local evidence pack.
4. Match deterministic PGx rules.
5. Render a clinician-reviewable Markdown report.
6. Run safety policy checks.
7. Produce JSON audit metadata.
8. Run synthetic evals.

This is a focused pharmacogenomics demo. It is not a full clinical genetics pipeline, not WGS interpretation, and not medical advice.

## Safety Boundary

OpenCare Proof Kit must not generate:

- diagnosis;
- dosage recommendation;
- treatment plan;
- start/stop medication instruction;
- claims without source;
- actionable claims from VUS or weak/model-only associations;
- hidden uncertainty.

Every report must include sources, limitations, evidence level, safety note, clinician-review note, and audit metadata.

## Why Now

The AI ecosystem is moving quickly from chat interfaces toward agents that act on private context. Health is one of the domains where that shift is both promising and dangerous. Before health agents become normal, the open-source ecosystem needs reusable safety, evidence, audit, and privacy patterns that are easy to inspect and run locally.

OpenCare Proof Kit is intentionally small enough to review but structured enough to become a foundation for safer sensitive-data agents.

## Why This Deserves A Grant

Grant funding supports public-good infrastructure rather than a closed product wedge. The project creates a concrete, runnable reference implementation for:

- local-first sensitive-data AI;
- deterministic tools before LLMs;
- evidence packs and citations;
- safety policy enforcement;
- audit metadata;
- evals focused on unsafe medical-advice prevention.

The grant would fund infrastructure that others can fork, inspect, test, and adapt.

## What Grant Funding Unlocks

Funding would unlock:

- broader synthetic eval coverage;
- more polished demo UX and reviewer materials;
- additional local evidence-pack examples;
- improved report templates;
- stronger audit schema documentation;
- reproducible CI validation;
- privacy-preserving model adapter research without default raw-data upload;
- a public demo video and maintainer documentation.

The next work should deepen safety, evidence, and auditability. It should not expand into diagnosis, dosage recommendation, real patient data, WGS/FASTQ/BAM processing, SaaS auth, payments, Telegram, blockchain, or cloud raw genotype upload by default.
