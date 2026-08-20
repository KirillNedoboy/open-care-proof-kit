# AGENTS.md

## Project overview

OpenCare Proof Kit is an open-source, self-hosted Personal and Family Health
Workspace plus reusable trust infrastructure for sensitive personal AI agents.
Public `main` includes G1-G5, P1, P2, D1, and P3. Product Core schema is v9.
The implementation supports Person-scoped records, provenance/review, PDF/TXT
evidence documents, Family Access v1-v3, separate genetics grants, a Genetics
Workspace, and bounded Evidence/Explore Research Mode.

Public repository fixtures, tests, screenshots, and reviewer artifacts are
synthetic/de-identified only. A self-hosted runtime is designed to process
user-owned sensitive health, document, and genetic data locally under explicit
authorization and provenance boundaries.

## Grant positioning

The project targets the Sentient Foundation open-source AI grant direction:

## Current boundaries and permanent non-goals

The following capabilities are implemented and must not be treated as future
work: Product Core migrations through v9, document upload/extraction,
Family Access, Genetics Workspace, separate genetics grants, and bounded
Research Mode.

Never implement:

- diagnosis;
- dosage recommendation;
- start/stop medication advice;
- clinical genetics authority or clinical validation;
- real patient/genetic data in repository fixtures;
- FASTQ/BAM/CRAM/gVCF/WGS pipelines;
- AlphaMissense clinical interpretation;
- SaaS multi-user auth, payments, Telegram, blockchain, or cloud raw-genome
  upload by default;
- autonomous canonical-record mutation.

## Setup

Use Python 3.12.

Recommended local setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints/python312.txt -e ".[dev]"
```

## Common commands

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
python -m evals.trust_metrics
python -m evals.g5_review
python -m evals.p1_review
python -m evals.p2_review
python -m evals.d1_review
python -m evals.p3_review
python -m pip check
git diff --check
uvicorn app.main:app --reload
docker compose up --build
```

## Architecture

Core pipeline:

```txt
Local UI / CLI
  -> Actor + Person authorization
  -> Immutable Source
  -> Candidate/review lifecycle
  -> Visit/Brief or document extraction
  -> Deterministic evidence/PGx/genetics rules
  -> Bounded Trust/Research context
  -> Validated output + audit
  -> Offline reviewers
```
Directory map:

```txt
app/product_core       Product Core schema v9, records, documents, genetics, export/recovery
app/family_access      Actor sessions, consent, Family Access v1-v3
app/agent_trust        Trust Envelope and execution receipt contracts
app/agent              bounded agent context, providers, validation, audit
app/genetics           consumer-genotype parsing, evidence, comparison, Research contracts
app/product_core/genetics.py  persisted genetics source/dataset/research service
app/templates/genetics.html  Genetics Workspace
app/static/genetics.js        Genetics Workspace behavior
app/vault               synthetic/local vault schemas and loaders
app/evidence            evidence pack schema and loading
app/pgx                 deterministic medication/genotype rule matching
app/safety              medical safety policy
app/reports             Markdown and audit JSON output
evals                   deterministic G5/P1/P2/D1/P3 reviewers
data                    synthetic demo data and local evidence packs
docs                    product, grant, safety, architecture documents
tests                   deterministic unit and integration tests
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
