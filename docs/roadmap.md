# Roadmap

This roadmap is conservative. It deepens evidence, safety, audit, and review infrastructure without expanding OpenCare Proof Kit into diagnosis, treatment recommendation, dosage guidance, or real patient clinical decision-making.

## Completed Foundation

- Deterministic local demo pipeline.
- Synthetic/demo health vault and genotype-like inputs.
- Local demo evidence pack.
- PGx rule matcher for the reference workflow.
- Safe unsupported-drug no-claim behavior.
- Markdown report and JSON audit output.
- FastAPI API and server-rendered local web demo.
- Static-text and pipeline-backed evals.
- GitHub/grant readiness documentation.

## Phase 2: Evidence-Pack Tooling And Better Pipeline Evals

Goals:

- add validation helpers for local evidence-pack authoring;
- document evidence-pack schema and examples more clearly;
- add more pipeline-backed eval cases for supported, unsupported, no-source, and coverage-limited paths;
- add CI or a local `make check` equivalent;
- keep all evidence examples demo-only unless a future reviewed phase changes scope.

Boundaries:

- no new clinical claims without explicit local demo evidence;
- no dosage or medication-action recommendations;
- no real patient data.

## Phase 3: Clinician-Review Workspace And Structured Export

Goals:

- improve the local reviewer workflow for reading reports and audits;
- add structured export formats for clinician-review handoff;
- make audit metadata easier to inspect and compare;
- improve documentation for report sections and limitations.

Boundaries:

- structured export is for review, not automated clinical action;
- no diagnosis, treatment planning, or medication recommendation;
- no SaaS auth or production multi-user workflow in the MVP.

## Phase 4: Optional Confidential Compute Adapter Research

Goals:

- review official docs and current research on confidential compute and private inference;
- design an optional adapter that keeps raw sensitive data protected by default;
- document threat model, limitations, and operational risks before implementation.

Boundaries:

- no cloud raw genotype upload by default;
- no adapter implementation before a reviewed privacy/security design;
- no promise of clinical diagnosis or treatment recommendations.

## Explicit Non-Promises

This roadmap does not promise:

- real patient diagnosis;
- medication choice recommendations;
- dosage recommendations;
- start/stop medication instructions;
- WGS/FASTQ/BAM processing;
- clinical validation;
- regulatory approval.
