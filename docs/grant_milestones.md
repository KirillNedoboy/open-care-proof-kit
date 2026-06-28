# Grant Milestones

These milestones are conservative and infrastructure-focused. They do not promise clinical deployment, diagnosis, treatment, medication choice, dosage guidance, real patient upload, or whole genome interpretation.

## Month 1: Public Repo Hardening And Evidence/Eval Depth

Goals:

- Add CI or a local `make check` equivalent for repeatable validation.
- Improve evidence-pack authoring documentation and schema examples.
- Add local validation helpers for evidence-pack contributors.
- Expand pipeline-backed evals for no-source, unsupported-drug, coverage-limited, and report-safety paths.
- Create a short demo video and screenshot set using synthetic/demo data only.
- Keep generated reports ignored and public release hygiene documented.

Acceptance signals:

- Tests, ruff, mypy, and evals run from one documented command or CI workflow.
- New evals preserve zero unsafe-advice, missing-source, uncertainty, audit, and pipeline failure rates.
- Demo video and screenshots contain no real patient data, real genetic data, secrets, or private records.

## Month 2: Broader Local Health-Agent Trust Workflows

Goals:

- Add one or two adjacent demo-only trust workflows that reuse the same pattern: local inputs, explicit evidence, safety policy, report, audit, evals.
- Improve structured export for clinician-review handoff.
- Improve local audit visualization in the web demo.
- Document audit schema fields and evidence-pack lifecycle.
- Add regression evals for structured export and audit display behavior.

Acceptance signals:

- New workflow examples remain demo-only and source-grounded.
- Structured export is clearly labeled for clinician review, not automated action.
- Audit display makes policy status, evidence-pack version, coverage status, and raw-export status easy to inspect.

## Month 3: Optional Adapter Research

Goals:

- Review official docs and current research for open-source local models and Sentient ecosystem compatibility.
- Identify whether an optional local model adapter can improve report-writing without changing deterministic-first architecture.
- Draft privacy, safety, and audit requirements for any adapter before implementation.
- Prototype only if official docs are stable and the adapter can preserve local/private defaults.
- Add adapter-specific eval requirements before public use.

Acceptance signals:

- Written adapter design exists before implementation.
- No raw health or genetic data is uploaded to cloud services by default.
- Deterministic evidence tools remain upstream of any model output.
- The report writer remains an explanation layer only.

## Explicit Non-Promises

The grant roadmap does not promise:

- clinical deployment;
- diagnosis;
- treatment recommendation;
- medication choice recommendation;
- dosage guidance;
- medication start/stop instruction;
- real patient upload;
- real genetic data processing in the demo;
- FASTQ/BAM/WGS pipeline;
- whole genome interpretation;
- AlphaMissense clinical interpretation.

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
