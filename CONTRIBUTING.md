# Contributing

OpenCare Proof Kit welcomes contributions that strengthen local-first, evidence-grounded, safety-checked health AI infrastructure without expanding the project into clinical decision-making.

## Project Boundaries

This project is not an AI doctor, diagnostic system, treatment planner, medication recommendation engine, or dosage tool.

Do not contribute changes that add:

- diagnosis;
- dosage recommendation;
- start/stop medication instruction;
- treatment planning;
- real patient data;
- FASTQ, BAM, WGS, or clinical genomics interpretation;
- SaaS auth, payments, Telegram, or blockchain;
- cloud upload of raw health or genetic data by default;
- clinical claims beyond the local demo evidence pack.

## Welcome Contributions

Useful contributions include:

- stronger eval cases for unsafe wording and missing evidence;
- evidence-pack validation improvements;
- safer report and audit formatting;
- clearer reviewer documentation;
- CI or local validation automation;
- synthetic/demo data improvements that do not resemble real patient records;
- local-first privacy and audit tooling.

## Out Of Scope Contributions

The following are out of scope for the current MVP:

- real clinical advice features;
- medication choice or dosage guidance;
- real patient import workflows;
- genomic pipeline expansion into FASTQ/BAM/WGS;
- cloud-first raw genotype processing;
- user accounts, payments, bots, or production SaaS deployment.

## Development Setup

Use Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints/python312.txt -e ".[dev]"
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints/python312.txt -e ".[dev]"
```

## Required Checks

Run before opening a PR:

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
python -m app.cli demo-report --drug sertraline --out-dir reports
python -m app.cli demo-report --drug aspirin --out-dir reports
```

Windows PowerShell without activating:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports
.\.venv\Scripts\python.exe -m app.cli demo-report --drug aspirin --out-dir reports
```

Generated files under `reports/` must remain ignored and must not be committed.

## Evidence-Pack Rules

Evidence-pack changes must:

- include explicit source metadata;
- use allowed source domains enforced by the local validator;
- include limitations;
- remain demo-only unless a future phase explicitly changes the project scope;
- keep `clinician_review_required=true`;
- keep `clinical_action_allowed=false`;
- avoid source-less medical claims.

If an evidence source is not represented in the local pack, the system must fail closed with no clinical claim.

## No Real Patient Data

Do not put real patient data in:

- commits;
- issues;
- pull requests;
- screenshots;
- generated reports;
- eval cases;
- demo fixtures.

Use synthetic/demo data only. If you accidentally include sensitive data, remove it immediately and disclose the mistake privately rather than in a public issue.
