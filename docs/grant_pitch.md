# Grant Pitch

## One-Liner

OpenCare Proof Kit is open-source trust infrastructure for private personal agents: local-first input handling, evidence packs, deterministic policy checks, constrained reporting, audit trails, and evals, with health as the reference stress-test workflow.

## Problem

Personal agents are starting to work with sensitive user context before the open-source stack has enough trust primitives around them. In domains like health, finance, legal, and identity, the hard question is not whether an LLM can produce a fluent answer. It is whether a user, reviewer, or downstream builder can inspect what data was used, which evidence supported the output, which policy checks ran, and why the system refused to make unsupported claims.

Health makes the problem visible. Medication, symptoms, labs, family history, and genetics are private, easy to misuse, and easy for a generic chatbot to overstate. A closed cloud-first workflow can also require users to surrender raw sensitive context before they can see whether the system is safe or useful.

## Solution

OpenCare Proof Kit provides a small, runnable trust/evidence/audit/safety substrate:

- synthetic/demo data by default;
- local-first execution;
- evidence packs with source, limitation, and coverage fields;
- deterministic parsers and rule matching before report writing;
- explicit safety policy with fail-closed behavior;
- constrained Markdown output plus JSON audit metadata;
- static-text and pipeline-backed evals for unsafe-output patterns.

The first reference workflow is Medication-to-Doctor Briefing. It uses a synthetic patient, demo genotype-like data, and a local demo evidence pack to produce a clinician-reviewable briefing about what to discuss with a clinician. It does not diagnose, recommend medication choice, recommend dosage, or instruct start/stop actions.

## Reusable Trust Pattern

The infrastructure pattern is intentionally simple:

```txt
private input context
  -> evidence
  -> deterministic policy
  -> report/output
  -> audit
  -> evals
```

Health is the reference implementation because it stress-tests the pattern against sensitive data, evidence requirements, safety boundaries, and uncertainty. The repo is not claiming to be a generalized cross-domain platform in production. It is a proof kit that makes the trust layer inspectable and reusable.

## Why This Fits Sentient-Style Public-Good AI

Sentient-aligned open-source AI should let users and builders inspect and control the systems that act on private context. OpenCare Proof Kit supports that direction by keeping the workflow local-first, exposing evidence and audit metadata, enforcing deterministic checks before any report-writing layer, and shipping evals that can be run by reviewers.

The grant case is infrastructure, not another health chatbot. The value is the reusable boundary around sensitive-agent behavior: no source, no claim; unsupported inputs produce safe no-claim output; report text must include limitations and clinician-review language; audits record policy status and raw-export status.

## Private-By-Default

The demo runs locally and uses synthetic/demo data. Audit metadata records that raw health or genetic data was not exported. Cloud raw genotype upload is not enabled by default and is outside the MVP boundary.

Privacy is part of the architecture, not a deployment promise added later. Local deterministic handling comes before any explanation or report-writing layer.

## Empowering, Not Extractive

The output helps a person prepare a better clinician conversation. It does not replace a clinician, make a diagnosis, prescribe, recommend dosage, or instruct medication changes.

The report exposes evidence sources, evidence level, limitations, uncertainty, clinician-review language, safety status, and audit metadata. That makes the workflow reviewable instead of opaque.

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

This is a focused pharmacogenomics reference workflow. It is not a full clinical genetics pipeline, not WGS interpretation, not clinical decision support, and not medical advice.

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

Agents are moving from chat into workflows that handle private context. Sensitive domains need open trust patterns before that shift becomes normal: local execution where possible, inspectable evidence, explicit policies, audit metadata, and evals that catch unsafe drift.

OpenCare Proof Kit is small enough to review line by line and complete enough to run end to end. That is the point of the proof kit.

## Why This Deserves A Grant

Grant funding supports public-good infrastructure rather than a closed product wedge. The project creates a concrete, runnable reference implementation for:

- local-first sensitive-data AI;
- deterministic tools before LLM explanations;
- source-grounded evidence packs;
- fail-closed safety policy enforcement;
- audit metadata;
- evals focused on unsafe medical-advice prevention.

The grant would fund infrastructure that others can fork, inspect, test, and adapt without accepting a black-box health assistant.

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

The next work should deepen safety, evidence, auditability, and reviewer confidence. It should not expand into diagnosis, dosage recommendation, real patient data, WGS/FASTQ/BAM processing, SaaS auth, payments, Telegram, blockchain, or cloud raw genotype upload by default.
