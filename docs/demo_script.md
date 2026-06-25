# Demo Script

This is a practical 2-3 minute demo for a grant reviewer or technical evaluator.

## Prerequisites

- Python 3.12.
- A terminal in the repository root.
- No external services required for the deterministic demo.

## 0:00-0:20 - Position The Project

Say:

> OpenCare Proof Kit is a local-first open-source proof layer for private, evidence-grounded health AI agents. This demo is not medical advice. It shows how synthetic health data, demo genotype-like data, local evidence packs, deterministic rules, safety policy, and audit metadata can produce a clinician-reviewable briefing.

Show:

```bash
ls
```

Point out:

- `app/` for pipeline code;
- `data/` for synthetic/demo inputs;
- `evals/` for safety/evidence evals;
- `docs/` for reviewer materials.

## 0:20-0:50 - Install And Validate

Run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
```

Windows PowerShell equivalent:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
```

Expected output:

- pytest passes;
- ruff passes;
- mypy passes;
- eval runner reports 3 passed cases and 0 failed cases.

Say:

> The checks verify deterministic unit behavior, linting, strict typing, and synthetic safety/evidence evals. These evals are not clinical validation; they are guardrails against unsafe demo output.

## 0:50-1:20 - Generate Demo Artifacts

Run:

```bash
python -m app.cli demo-report --drug sertraline --out-dir reports
```

Expected output:

```txt
Wrote reports/demo-sertraline-briefing.md
Wrote reports/demo-sertraline-audit.json
```

Show:

```bash
cat reports/demo-sertraline-briefing.md
cat reports/demo-sertraline-audit.json
```

Say:

> The Markdown report is written for clinician review. It includes sources, limitations, evidence level, safety language, and clinician questions. The audit JSON records app version, report ID, pipeline steps, policy status, evidence pack version, and that raw health or genetic data was not exported.

## 1:20-2:10 - Show The API

Run:

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

Show:

- `/` frames the project, architecture, and reviewer links.
- `/demo` shows the synthetic patient card, the sertraline question, and the deterministic pipeline stages.
- `/demo/report-view` renders the briefing as readable HTML with policy status, findings count, and audit summary.
- `/demo/report` returns report plus audit JSON.
- `/demo/report.md` returns plain Markdown.
- `/demo/audit` returns audit only.

Say:

> The API and CLI use the same deterministic demo pipeline service, so the same safety and audit path is used from both entrypoints.

Optional browser-first path:

- Start at `/` for positioning.
- Click through to `/demo`.
- Use `Generate Briefing` to open `/demo/report-view?drug=sertraline`.
- Open `/demo/report.md` and `/demo/audit` from the report page to show the raw artifacts behind the presentation layer.

## 2:10-2:40 - Emphasize Boundaries

Show the safety note in the report.

Say:

> This project deliberately avoids diagnosis, dosage recommendation, treatment plans, start/stop medication advice, real patient data, and WGS-style interpretation. The first workflow is a narrow pharmacogenomics briefing demo that helps prepare a clinician conversation.

## Fallback If Web Server Fails

If Uvicorn or the browser fails, use the CLI-only demo:

```bash
python -m app.cli demo-report --drug sertraline --out-dir reports
python -m evals.runner
```

Then inspect:

```txt
reports/demo-sertraline-briefing.md
reports/demo-sertraline-audit.json
evals/results/latest.json
```

Fallback message:

> The web server is only a presentation layer. The core demo is the deterministic local pipeline, generated Markdown, audit JSON, and eval runner.
