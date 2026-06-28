# Reviewer Quickstart

Goal: run OpenCare Proof Kit locally in under 3 minutes and inspect the generated report, audit JSON, API endpoints, and evals.

## Prerequisites

- Python 3.12.
- Git checkout or local copy of this repository.
- Terminal in the repository root.

No database, cloud service, API key, real patient data, or model provider is required for the deterministic demo.

## 1. Install

Unix/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Expected success signal:

```txt
Successfully installed open-care-proof-kit
```

## 2. Run Tests

```bash
pytest
ruff check app tests evals
mypy app evals
```

Windows PowerShell without activating:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
```

Expected success signals:

- pytest reports all tests passed;
- ruff reports all checks passed;
- mypy reports no issues.

## 3. Generate Report And Audit

```bash
python -m app.cli demo-report --drug sertraline --out-dir reports
```

Windows PowerShell without activating:

```powershell
.\.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports
```

Expected success signal:

```txt
Wrote reports/demo-sertraline-briefing.md
Wrote reports/demo-sertraline-audit.json
```

Inspect:

```txt
reports/demo-sertraline-briefing.md
reports/demo-sertraline-audit.json
```

Look for:

- safety note;
- sources;
- limitations;
- clinician questions;
- `policy_passed: true`;
- `raw_health_or_genetic_data_exported: false`.

## 4. Start API

```bash
uvicorn app.main:app --reload
```

Windows PowerShell without activating:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open:

```txt
http://127.0.0.1:8000/
http://127.0.0.1:8000/demo/report?drug=sertraline
http://127.0.0.1:8000/demo/report.md?drug=sertraline
http://127.0.0.1:8000/demo/audit?drug=sertraline
```

Expected success signals:

- `/health` returns `{"status": "ok"}`;
- `/demo/report` returns report Markdown plus audit JSON;
- `/demo/report.md` returns Markdown;
- `/demo/audit` returns audit JSON only.

## 5. Run Evals

```bash
python -m evals.runner
```

Windows PowerShell without activating:

```powershell
.\.venv\Scripts\python.exe -m evals.runner
```

Expected success signal:

```txt
"total_cases": 12
"static_text_cases": 7
"pipeline_cases": 5
"passed_cases": 12
"failed_cases": 0
"pipeline_failure_rate": 0.0
```

Interpretation:

- static-text evals are wording/safety guardrails;
- pipeline evals execute the real local demo pipeline for supported and unsupported drug paths;
- neither mode is clinical validation.

## Expected Success Summary

The project is running correctly when:

- tests pass;
- ruff passes;
- mypy passes;
- eval runner reports 12 passed cases and 0 failed cases;
- eval runner reports 7 static-text cases and 5 pipeline-backed cases;
- CLI writes Markdown and audit JSON;
- API endpoints return report and audit data;
- audit has `policy_passed=true`;
- audit has `raw_health_or_genetic_data_exported=false`;
- reports and audits label coverage as demo evidence-pack coverage, not clinical coverage.

## Boundary Reminder

This quickstart demonstrates a synthetic local pipeline. It does not diagnose, recommend dosage, recommend medication choice, tell anyone to start or stop medication, process real patient data, or perform WGS/FASTQ/BAM analysis.
