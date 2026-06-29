# Grant Submission Answers

Copy these answers into a Sentient Open Source AGI Grant or public-goods grant application. Keep the wording conservative: this is open-source infrastructure for trustworthy private health AI agents, not a clinical product.

## A. Project Title

OpenCare Proof Kit: Local-first trust, evidence, safety, audit, and eval infrastructure for private health AI agents.

## B. One-Sentence Pitch

OpenCare Proof Kit is an open-source, local-first proof kit that helps personal health AI agents produce clinician-reviewable, evidence-grounded doctor briefings with audit trails and executable safety evals.

## C. Short Summary

OpenCare Proof Kit is open-source infrastructure for private health AI agents. It runs a local Medication-to-Doctor Briefing demo from synthetic health and genotype-like data, local demo evidence packs, deterministic PGx rules, safety policy checks, Markdown reports, JSON audit trails, and executable evals. It is not medical advice, diagnosis, dosage guidance, or a medication recommendation engine.

## D. Longer Summary

OpenCare Proof Kit is a local-first, open-source trust/evidence/safety kit for private health AI agents. The current reference workflow is Medication-to-Doctor Briefing: synthetic/demo health vault data and genotype-like data flow through a local evidence pack, deterministic PGx rule matcher, demo evidence-pack coverage summary, safety policy, report writer, Markdown briefing, JSON audit, and static-text plus pipeline-backed evals.

The core invariant is deterministic tools before LLM. The LLM/report writer explains deterministic findings, sources, limitations, uncertainty, and clinician-review questions; it does not create medical truth or override safety policy.

The project is designed as public-good infrastructure for sensitive personal AI. It helps users and builders inspect what data moved, what evidence was used, what safety checks ran, and whether outputs drift toward unsafe medical advice. The demo uses synthetic/demo data only, does not upload raw health or genetic data to the cloud by default, and explicitly avoids diagnosis, dosage guidance, start/stop medication advice, real patient data, WGS/FASTQ/BAM processing, and clinical deployment claims.

## E. Problem

Personal AI agents will increasingly help people reason around sensitive context such as medications, symptoms, labs, family history, and genetics. Generic LLM apps can blur evidence, hide uncertainty, omit sources, and produce unsafe medical-sounding text. Closed cloud-first systems can also require users to surrender sensitive health or genetic context before they can inspect what the system does.

The open-source ecosystem needs runnable patterns for private, evidence-grounded agents: local data handling, deterministic evidence tools, safety checks, audit trails, and evals that fail when outputs drift toward unsafe claims.

## F. Solution

OpenCare Proof Kit provides a concrete local reference implementation:

- synthetic/demo health vault and genotype-like inputs;
- local demo evidence packs;
- deterministic parsers and PGx rule matching;
- safe unsupported-drug no-claim behavior;
- report generation with sources, limitations, safety note, and clinician-review language;
- JSON audit metadata with policy status, evidence-pack version, coverage status, and raw-export status;
- static-text and pipeline-backed evals that execute the real local demo pipeline.

The result is a reusable pattern for health-agent builders who want private, inspectable, source-grounded workflows before adding broader agent behavior.

## G. Why This Should Be Open-Source

Trust infrastructure for sensitive AI should be inspectable. Open source lets reviewers and downstream builders audit the data flow, evidence-pack schema, deterministic rules, safety policy, report structure, audit metadata, and eval cases.

This project is not trying to own a closed patient workflow. Its value is in reusable public-good components that others can fork, test, adapt, and improve for local-first sensitive-data agents.

## H. Why This Is Local-First / Private-By-Default

Medication and genetic context are high-sensitivity data categories. OpenCare Proof Kit keeps the reference workflow local-first so users and reviewers can inspect the full path from demo input to generated report without a cloud dependency or hidden raw-data transfer.

The current demo uses only synthetic/demo data. Audit metadata records `raw_health_or_genetic_data_exported=false`. Cloud raw genotype upload is not enabled by default and is outside the MVP boundary.

## I. Who Benefits

- Users who need safer AI help preparing for clinician conversations without handing raw sensitive data to a closed service.
- Underserved users who benefit from open, locally runnable tools rather than paywalled or extractive health AI workflows.
- Clinicians and reviewers who need outputs with visible sources, limitations, and audit metadata.
- Open-source builders working on personal agents for sensitive domains.
- Grant reviewers and researchers looking for practical patterns for trustworthy private AI infrastructure.

## J. What Has Been Built So Far

- Public GitHub repository: `https://github.com/KirillNedoboy/open-care-proof-kit`
- Deterministic local demo pipeline.
- CLI report and audit generation for `sertraline` and safe unsupported-drug `aspirin`.
- FastAPI endpoints and server-rendered local web demo pages.
- Strict local evidence-pack validation.
- Demo evidence-pack coverage reporting.
- Safe no-claim behavior for unsupported drugs.
- Markdown clinician-reviewable briefing output.
- JSON audit metadata.
- Static-text and pipeline-backed evals.
- GitHub/grant readiness docs, license, contribution guide, security policy, release checklist, screenshot guide, and reviewer quickstart.
- Visual demo assets: local web screenshots and a 90-120 second demo video script using synthetic/demo data only.

## K. Technical Architecture

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

The LLM/report writer is an explanation layer only. It summarizes deterministic findings, limitations, sources, and clinician-review questions. It must not invent sources, infer clinical meaning from raw variants without evidence rules, recommend medication choice, recommend dosage, or override safety policy.

## L. Safety Model

The safety model is explicit and fail-closed:

- no source, no claim;
- unsupported drugs return safe no-claim output;
- demo evidence-pack coverage is labeled as demo-only and not clinical coverage;
- every report includes safety note, clinician review note, evidence level, limitations, sources, and audit metadata;
- safety policy checks run before output is treated as valid;
- evals check unsafe wording, missing sources, missing uncertainty, audit presence, and real pipeline behavior.

The system must not generate diagnosis, treatment plans, dosage adjustments, start/stop medication instructions, source-less medical claims, actionable VUS claims, AlphaMissense-only clinical interpretation, or hidden uncertainty.

## M. Evaluation / Audit Model

The current eval suite reports:

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

Static-text evals check known safety and evidence wording. Pipeline evals execute the real local demo pipeline via `build_demo_briefing(...)` and validate report text plus nested audit fields such as `coverage.coverage_status`, `coverage.matched_findings`, `policy_passed`, and `raw_health_or_genetic_data_exported`.

The audit trail records report ID, app version, pipeline steps, evidence-pack version, coverage status, safety policy status, and raw-export status.

## N. Why Sentient / Grant Alignment

OpenCare Proof Kit aligns with open-source public-good AI because it focuses on infrastructure that makes personal agents more trustworthy, inspectable, and empowering. It is local-first and private-by-default, uses deterministic tools before LLM explanations, exposes audit trails, and ships executable evals.

For a Sentient-style ecosystem, the project demonstrates a pattern for personal AI agents that handle sensitive context without becoming extractive or opaque. It does not assume ownership, equity, or closed deployment; the work is designed to be forked, inspected, and reused.

## O. What Support Would Help

Grant support would fund:

- evidence-pack authoring and validation tooling;
- broader synthetic eval coverage;
- CI and release automation;
- clearer audit schema documentation;
- demo video and reviewer assets;
- improved local web review experience;
- structured export for clinician-review handoff;
- research into optional open-source local model or Sentient ecosystem adapters after official docs are stable.

## P. 30-Day Milestones

- Add CI or a local `make check` equivalent.
- Improve public repository hygiene and release checklist coverage.
- Add evidence-pack authoring helpers and schema examples.
- Expand pipeline-backed evals for no-source, unsupported, and coverage-limited paths.
- Produce a short demo video using synthetic/demo data only.

## Q. 60-Day Milestones

- Add broader local health-agent trust workflow examples using demo-only evidence.
- Improve structured export for clinician-review handoff.
- Improve audit visualization in the local web demo.
- Document audit schema and evidence-pack lifecycle.
- Add regression evals for report/audit presentation changes.

## R. 90-Day Milestones

- Research optional open-source local model adapters and Sentient ecosystem compatibility if official docs are stable.
- Draft privacy/security design for any optional adapter before implementation.
- Add adapter-facing eval and audit requirements.
- Improve contributor docs for adding demo-only evidence packs safely.
- Prepare a public v0.1 release tag after validation and review.

## S. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Unsafe medical-advice drift | Safety policy, report constraints, and evals that fail on unsafe wording. |
| Source-less claims | Strict evidence-pack validation and no-source no-claim behavior. |
| Privacy leakage | Local-first default, synthetic demo data, ignored generated reports, and no cloud raw upload by default. |
| Overclaiming clinical validity | Docs state evals are engineering guardrails, not clinical validation. |
| Scope creep | Hard non-goals for diagnosis, dosage, WGS/FASTQ/BAM, SaaS, payments, bots, and blockchain. |
| Weak future integrations | Optional adapters require official docs, current research review, and a privacy/security design first. |

## T. Non-Goals

OpenCare Proof Kit does not provide or promise:

- diagnosis;
- treatment recommendation;
- medication choice recommendation;
- dosage guidance;
- medication start/stop instructions;
- real patient upload;
- real genetic data processing in the demo;
- FASTQ/BAM/WGS pipeline;
- whole genome interpretation;
- AlphaMissense clinical interpretation;
- clinical decision support;
- SaaS/auth/payments/Telegram/blockchain;
- cloud raw genotype upload by default;
- clinical validation or regulatory approval.

## U. Repository / Demo Instructions

Repository:

```txt
https://github.com/KirillNedoboy/open-care-proof-kit
```

Run locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
python -m app.cli demo-report --drug sertraline --out-dir reports
python -m app.cli demo-report --drug aspirin --out-dir reports
uvicorn app.main:app --reload
```

Open:

```txt
http://127.0.0.1:8000/
http://127.0.0.1:8000/demo
http://127.0.0.1:8000/demo/report-view?drug=sertraline
http://127.0.0.1:8000/demo/report-view?drug=aspirin
```

Expected signals: tests pass, evals report 12 passed and 0 failed, generated reports stay ignored, sertraline shows a matched demo rule, and aspirin shows safe unsupported-drug no-claim behavior.

## V. Final Short Application Blurb

OpenCare Proof Kit is open-source local-first infrastructure for private health AI agents: deterministic evidence tools before LLM explanations, clinician-reviewable doctor briefings, demo-only evidence-pack coverage, audit trails, and executable safety evals. It is not medical advice and uses synthetic/demo data only.

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
