# AGENTS.md

## Project overview

OpenCare Proof Kit is an open-source, local-first toolkit for building private, evidence-grounded health AI agents.

The reference MVP workflow is Medication-to-Doctor Briefing: a local pipeline that uses synthetic/demo health vault data, demo genotype/VCF-like data, deterministic evidence rules, safety policy checks, and an LLM report writer to produce clinician-reviewable Markdown/JSON reports.

This project is not an AI doctor, not a diagnostic system, and not a medication recommendation engine.

## Grant positioning

The project targets the Sentient Foundation open-source AI grant direction:

- open-source infrastructure;
- local-first and private-by-default;
- useful for sensitive health data;
- empowering, not extractive;
- reusable trust/evidence/safety layer for health AI agents.

## Non-goals for MVP

Do not implement in v0.1 unless explicitly approved:

- diagnosis;
- dosage recommendation;
- start/stop medication advice;
- real patient data in demo;
- FASTQ/BAM/WGS pipeline;
- AlphaMissense clinical interpretation;
- SaaS multi-user auth;
- payments;
- Telegram bot;
- blockchain;
- cloud upload of raw health/genetic data by default.

## Setup

Use Python 3.12.

Recommended local setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Common commands

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
uvicorn app.main:app --reload
docker compose up --build
```

## Architecture

Core pipeline:

```txt
Local UI / CLI
  -> Health Vault Loader
  -> Genotype Parser
  -> Evidence Pack Loader
  -> PGx Rule Matcher
  -> Safety Policy Engine
  -> LLM Report Writer
  -> Markdown Report + JSON Audit
  -> Eval Runner
```

Directory map:

```txt
app/vault       health vault schemas, loaders, validators
app/genetics    genotype/VCF-like parsing and normalization
app/evidence    evidence pack schema and loading
app/pgx         deterministic medication/genotype rule matching
app/safety      medical safety policy engine
app/ai          LLM adapter and report drafting
app/reports     Markdown and audit JSON output
evals           synthetic safety/evidence evals
data            demo-only data and local evidence packs
docs            product, grant, safety, architecture documents
tests           deterministic unit tests
```

## Boundaries

| Area | Allowed | Ask first | Never |
|---|---|---|---|
| app/vault | edit | schema-breaking changes | store real patient data |
| app/genetics | edit | adding WGS/FASTQ support | infer medical meaning in parser |
| app/evidence | edit | new evidence source format | source-less medical claims |
| app/pgx | edit | phenotype inference changes | unsupported clinical action |
| app/safety | edit | relaxing safety rules | bypass safety policy |
| app/ai | edit | cloud model adapter | send raw genotype to cloud by default |
| app/reports | edit | report structure changes | omit sources/safety note |
| evals | edit | deleting eval categories | weaken safety evals silently |
| data/demo_patients | edit synthetic data | add realistic sensitive examples | commit real patient data |
| .env* | read examples only | changing env schema | commit secrets |
| docs | edit | grant positioning changes | claim medical approval |

## Medical safety rules

The system must not generate:

- diagnosis;
- treatment plan;
- dosage adjustment;
- start/stop medication instruction;
- claims without source;
- actionable claim from VUS;
- actionable claim from AlphaMissense-only or weak association;
- hidden uncertainty.

Every report must include:

- safety note;
- clinician review note;
- evidence level;
- limitations;
- sources;
- audit metadata.

## AI layer rules

The LLM is an explanation/reporting layer only.

It may:

- summarize deterministic findings;
- explain limitations;
- draft clinician-reviewable reports;
- generate questions for clinician discussion.

It must not:

- invent sources;
- infer clinical meaning from raw variants without evidence rules;
- recommend medication choice;
- recommend dosage;
- override safety policy.

## Testing requirements

Before marking a task complete, run the relevant subset:

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
```

For changes in safety, evidence, PGx, or report generation, update tests and evals.

## Review checklist

A change is acceptable only if:

- it preserves local-first default;
- it does not introduce real patient data;
- it keeps deterministic tools before LLM;
- it keeps safety policy enforced;
- it includes tests for changed behavior;
- generated reports include sources and audit metadata;
- README/docs stay aligned with non-medical-advice positioning.
