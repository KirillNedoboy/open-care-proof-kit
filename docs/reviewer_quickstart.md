# Reviewer Quickstart (Supporting Evidence)

> This is a reviewer procedure for the current demo/reference surfaces. It is
> not the product roadmap. The authoritative direction is [ADR 0001](adr/0001-opencare-product-direction.md)
> and the authoritative status is [project-status.md](project-status.md).

Goal: run OpenCare Proof Kit locally in under 3 minutes and inspect the generated report, audit JSON, Health/Family Vault reviewer UI, API endpoints, and evals.

## Prerequisites

- Python 3.12.
- Git checkout or local copy of this repository.
- Terminal in the repository root.

No database, cloud service, API key, real patient data, or model provider is required for the deterministic demo.

## Current reviewer path

The live Product Core path is:

1. `/workspace`
2. `/family-access`
3. `/genetics`

The synthetic reviewer path remains `/demo/health-vault`. The latter is
read-only and intentionally has no upload or genetics surface; that limitation
does not describe the live Product Core.

## 1. Install

Unix/macOS:

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
http://127.0.0.1:8000/demo/health-vault
http://127.0.0.1:8000/demo/report?drug=sertraline
http://127.0.0.1:8000/demo/report.md?drug=sertraline
http://127.0.0.1:8000/demo/audit?drug=sertraline
```

Expected success signals:

- `/health` returns `{"status": "ok"}`;
- `/demo/health-vault` renders a local read-only reviewer page for the synthetic family vault plus context/provenance trace graph;
- `/demo/report` returns report Markdown plus audit JSON;
- `/demo/report.md` returns Markdown;
- `/demo/audit` returns audit JSON only.

## 5. Run final reviewers

```bash
python -m evals.runner
python -m evals.trust_metrics
python -m evals.g5_review
python -m evals.p1_review
python -m evals.p2_review
python -m evals.d1_review
python -m evals.p3_review
python -m pip check
git diff --check
```

Historical P3-final local evidence at
`0937d352cc74a3050609e826baa6bad82f6ac9ee`:

- pytest: `675 passed, 4 skipped, 4 warnings`;
- `evals.runner`: `30/30`;
- G5: `20/20`, `READY_FOR_SECOND_CLIENT_SMOKE`;
- P1/P2/D1/P3: `PASS`;
- P3 security counters: all zero.

These are local verification results, not a claim that every command ran in
GitHub Actions or that the software is clinically validated.

## Health/Family Vault Reviewer Path

The Health/Family Vault layer now includes one local read-only reviewer UI route plus committed synthetic reviewer artifacts. It adds no JSON API surface, no upload path, no LLM generation, no genetics support, and no medical advice.

Recommended reviewer path:

1. Start the app and open `/demo/health-vault`.
2. Inspect the top safety banner.
3. Inspect provenance coverage.
4. Inspect the `Context / Provenance Trace Graph` section and source-linked counts.
5. Inspect artifact/trust flags.
6. Inspect the committed demo artifacts under `docs/assets/health_vault/`.
7. Read `docs/provenance_semantics.md`.
8. Read `docs/privacy_safety_threat_model.md`.
9. Run the focused Health/Family Vault tests, including the trace graph test.
10. Run the full validation sequence and trust metrics.

Inspect the source dataset:

```txt
data/demo_patients/demo_family_vault.json
```

Inspect the generated artifacts:

```txt
docs/assets/health_vault/family-vault-read-model.json
docs/assets/health_vault/family-vault-summary.md
docs/assets/health_vault/family-vault-manifest.json
```

Read the reviewer guide:

```txt
docs/health_family_vault_demo.md
```

Read the V1E provenance and artifact docs:

```txt
docs/provenance_semantics.md
docs/privacy_safety_threat_model.md
docs/vault_artifact_guarantees.md
```

Run the focused Health/Family Vault tests:

```bash
pytest tests/test_health_vault.py tests/test_health_vault_read_model.py tests/test_health_vault_artifacts.py tests/test_health_vault_trace_graph.py
```

Windows PowerShell without activating:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_health_vault.py tests\test_health_vault_read_model.py tests\test_health_vault_artifacts.py tests\test_health_vault_trace_graph.py
```

Run the full validation set if desired:

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
python -m evals.trust_metrics
```

The reviewer page is local and read-only:

- synthetic/demo-only;
- no upload;
- no LLM;
- no genetics in this layer;
- deterministic context/provenance trace graph, not medical interpretation;
- no diagnosis, treatment recommendation, dosage guidance, medication selection, or start/stop medication advice.

## Expected Success Summary

The project is running correctly when:

- tests pass;
- ruff passes;
- mypy passes;
- eval runner reports 12 passed cases and 0 failed cases;
- eval runner reports 7 static-text cases and 5 pipeline-backed cases;
- trust metrics prints eval metrics, Health/Family Vault manifest safety flags, and residual risks;
- CLI writes Markdown and audit JSON;
- API endpoints return report and audit data;
- audit has `policy_passed=true`;
- audit has `raw_health_or_genetic_data_exported=false`;
- reports and audits label coverage as demo evidence-pack coverage, not clinical coverage.
- Health/Family Vault artifacts are synthetic/demo-only and include provenance coverage plus safety boundaries.

## Boundary Reminder

This quickstart demonstrates synthetic local pipelines and committed synthetic demo artifacts. It does not diagnose, recommend dosage, recommend medication choice, tell anyone to start or stop medication, process real patient data, process real genetic data, or perform WGS/FASTQ/BAM analysis.
