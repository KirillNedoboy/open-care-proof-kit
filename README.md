# OpenCare Proof Kit

OpenCare Proof Kit is a local-first, open-source proof layer for private, evidence-grounded health AI agents.

The reference demo is **Medication-to-Doctor Briefing**: a deterministic local pipeline that turns synthetic health vault data, demo genotype-like data, a local evidence pack, safety policy checks, and a report writer into a clinician-reviewable Markdown briefing plus JSON audit trail.

This project is not an AI doctor, not a diagnostic system, and not a medication recommendation engine.

## What It Is

- Open-source infrastructure for trust, evidence, safety, and auditability in health AI agents.
- A local-first demo pipeline that runs on synthetic/demo data.
- A deterministic tool chain before any report-writing layer.
- A reusable pattern for source-cited health briefings.
- A safety and eval scaffold for catching unsafe medical-advice patterns.

## What It Is Not

- Not medical advice.
- Not diagnosis.
- Not treatment planning.
- Not dosage recommendation.
- Not start/stop medication instruction.
- Not a real-patient data repository.
- Not a FASTQ, BAM, WGS, or clinical genomics pipeline.
- Not SaaS, auth, payments, Telegram, or blockchain.
- Not cloud upload of raw health or genetic data by default.

## Why Local-First

Health agents may touch medications, symptoms, lab context, family history, and genetics. Those are high-sensitivity data categories. OpenCare Proof Kit keeps the reference workflow local-first and private-by-default so reviewers can inspect the full path from demo input to generated report without a cloud dependency or hidden data transfer.

The current demo uses only synthetic/demo files in `data/`. Audit metadata records that raw health or genetic data was not exported.

## Why This Is Not An AI Wrapper

An AI wrapper sends user context to a model and returns prose. OpenCare Proof Kit makes the model a report-writing layer, not the source of medical truth.

The reference workflow is:

```txt
Synthetic demo health vault
  -> Demo genotype parser
  -> Local evidence pack loader
  -> Deterministic PGx rule matcher
  -> Markdown report renderer
  -> Safety policy checker
  -> JSON audit builder
  -> Eval runner
```

The LLM/report writer may summarize deterministic findings, limitations, sources, and clinician-review questions. It must not invent sources, diagnose, recommend medication choice, recommend dosage, or override safety policy.

## Demo In 60 Seconds

Install in a Python 3.12 environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Generate the demo report and audit:

```bash
python -m app.cli demo-report --drug sertraline --out-dir reports
```

Expected generated files:

```txt
reports/demo-sertraline-briefing.md
reports/demo-sertraline-audit.json
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Open:

```txt
http://127.0.0.1:8000/
http://127.0.0.1:8000/demo
http://127.0.0.1:8000/demo/report-view?drug=sertraline
http://127.0.0.1:8000/demo/report?drug=sertraline
http://127.0.0.1:8000/demo/report.md?drug=sertraline
http://127.0.0.1:8000/demo/audit?drug=sertraline
```

## Local Web Demo

The local web demo is server-rendered with FastAPI + Jinja2. It is a presentation layer over the same deterministic briefing pipeline used by the CLI and JSON/Markdown API endpoints.

Browser path:

- `/`: landing page with project framing, boundaries, architecture summary, and reviewer links.
- `/demo`: synthetic patient card, sertraline question, and pipeline overview.
- `/demo/report-view?drug=sertraline`: readable HTML report with policy status, findings count, audit summary, and links to raw Markdown and JSON.

## Safety Boundaries

The generated report must include:

- safety note;
- clinician review note;
- evidence level;
- limitations;
- sources;
- audit metadata.

The system must not generate:

- diagnosis;
- treatment plan;
- dosage adjustment;
- start/stop medication instruction;
- source-less medical claim;
- actionable claim from VUS or weak/model-only association;
- hidden uncertainty.

## Evals

Run the deterministic eval suite:

```bash
python -m evals.runner
```

Current eval focus:

- no dosage recommendation;
- sources required;
- variants of uncertain significance are not actionable.

Current validation state:

```txt
passed_cases: 3
failed_cases: 0
unsafe_advice_rate: 0.0
missing_source_rate: 0.0
uncertainty_missing_rate: 0.0
audit_missing_rate: 0.0
```

These evals are safety and evidence-behavior checks for the demo pipeline. They are not clinical validation.

## Local Run Commands

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
python -m app.cli demo-report --drug sertraline --out-dir reports
uvicorn app.main:app --reload
```

## Generated Demo Artifacts

- `reports/demo-sertraline-briefing.md`: clinician-reviewable Markdown briefing from synthetic/demo data.
- `reports/demo-sertraline-audit.json`: audit metadata with report ID, app version, pipeline steps, evidence pack version, safety policy status, and generated file paths.
- `/demo/report-view`: server-rendered HTML viewer for the same briefing and audit summary.
- `/demo/report.md`: API Markdown report response.
- `/demo/audit`: API audit-only JSON response.

See `docs/demo_artifacts.md` for what each artifact proves.

## Repository Map

```txt
app/vault       health vault schemas, loaders, validators
app/genetics    genotype/VCF-like parsing and normalization
app/evidence    evidence pack schema and loading
app/pgx         deterministic medication/genotype rule matching
app/safety      medical safety policy engine
app/ai          report drafting layer
app/reports     Markdown and audit JSON output
evals           synthetic safety/evidence evals
data            demo-only data and local evidence packs
docs            product, grant, safety, architecture documents
tests           deterministic unit tests
```

## Roadmap

Phase 1: deterministic local MVP.

- Synthetic demo patient.
- Demo genotype parser.
- Local evidence pack.
- PGx matcher.
- Safety policy.
- Markdown report.
- JSON audit.
- Eval runner.
- CLI/API demo path.
- Local web demo path.

Phase 1.2: grant/demo readiness.

- Reviewer-ready README.
- Grant pitch.
- Practical demo script.
- Demo artifact docs.
- Eval result docs.
- Reviewer quickstart.

Next safe steps:

- Add a lightweight CI workflow or `make check` equivalent.
- Expand eval cases without weakening safety boundaries.
- Improve report presentation further while preserving clinician-review and non-medical-advice language.
- Add more demo evidence packs only when sources and limitations are explicit.

Non-goals for the current MVP remain: diagnosis, dosage recommendation, treatment planning, real patient data, WGS/FASTQ/BAM support, SaaS/auth/payments, Telegram, blockchain, or cloud raw genotype upload by default.

## Grant Positioning

OpenCare Proof Kit is grant-aligned open-source AI infrastructure:

- open-source and inspectable;
- local-first and private-by-default;
- empowering to users and clinicians rather than extractive;
- reusable trust/evidence/safety layer for health AI agents;
- demo workflow grounded in synthetic data, deterministic rules, sources, limitations, and audit metadata.

The grant case is not "another health chatbot." The grant case is reusable infrastructure for making sensitive health-agent workflows inspectable, source-grounded, safety-checked, and locally runnable.
