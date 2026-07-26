# MVP Scope (Historical)

> Historical MVP scope. Current capability is defined by
> [the capability matrix](capability-matrix.md); approved product direction is
> defined by [ADR 0001](adr/0001-opencare-product-direction.md).

## In scope

- Local FastAPI app.
- CLI-friendly modules.
- Synthetic demo health vault.
- Demo genotype/VCF-like parser.
- Local evidence-pack schema and loader.
- Deterministic PGx rule matcher.
- Safety policy engine.
- Markdown report generation.
- JSON audit trail.
- Synthetic eval suite.
- Docker setup.
- Docs and grant pitch.

## Out of scope

- Real patient uploads in demo.
- FASTQ/BAM/WGS processing.
- AlphaMissense clinical interpretation.
- Diagnosis.
- Dosage recommendation.
- Start/stop medication instruction.
- SaaS multi-user accounts.
- Payments.
- Telegram.
- Blockchain.
- Cloud LLM upload by default.

## Critical functions

1. Deterministic parsing/matching.
2. Safety policy enforcement.
3. Source-cited clinician-reviewable report with audit metadata.
