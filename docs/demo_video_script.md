# Demo Video Script

Target length: 90-120 seconds.

Use only the local demo server and synthetic/demo data. Do not show browser bookmarks, private desktop paths, terminals containing secrets, real patient data, real genetic data, or generated files outside the ignored `reports/` directory.

## Script

### 0:00-0:15 - Opening

"OpenCare Proof Kit is an open-source, local-first trust, evidence, safety, audit, and eval kit for private health AI agents. The reference workflow is Medication-to-Doctor Briefing: a clinician-reviewable report generated from synthetic demo data, local evidence rules, and safety checks."

### 0:15-0:30 - Landing Page

Show:

```txt
http://127.0.0.1:8000/
```

Talking points:

- local-first health AI proof layer;
- deterministic evidence and safety checks before report writing;
- explicit non-goals: no diagnosis, no dosage recommendation, no start/stop medication advice.

### 0:30-0:45 - Demo Patient And Pipeline

Show:

```txt
http://127.0.0.1:8000/demo
```

Talking points:

- synthetic demo patient only;
- local health vault and demo genotype-like data;
- local evidence pack, deterministic rule matching, safety policy, Markdown report, and JSON audit.

### 0:45-1:05 - Sertraline Report

Show:

```txt
http://127.0.0.1:8000/demo/report-view?drug=sertraline
```

Talking points:

- sertraline has a matched demo evidence-pack rule;
- the report includes safety note, limitations, sources, clinician-review questions, and audit metadata;
- audit records policy status and that raw health/genetic data was not exported.

### 1:05-1:25 - Aspirin Safe No-Claim Report

Show:

```txt
http://127.0.0.1:8000/demo/report-view?drug=aspirin
```

Talking points:

- aspirin is unsupported by the local demo evidence pack;
- the system returns safe no-claim output instead of inventing a clinical claim;
- coverage status explains that this is demo evidence-pack coverage, not clinical coverage.

### 1:25-1:45 - Evals

Show terminal command:

```powershell
.\.venv\Scripts\python.exe -m evals.runner
```

Expected metrics:

```txt
total_cases: 12
static_text_cases: 7
pipeline_cases: 5
passed_cases: 12
failed_cases: 0
unsafe_advice_rate: 0.0
missing_source_rate: 0.0
uncertainty_missing_rate: 0.0
audit_missing_rate: 0.0
pipeline_failure_rate: 0.0
```

Talking points:

- static-text evals catch unsafe wording patterns;
- pipeline-backed evals execute the real local demo pipeline;
- evals are engineering guardrails, not clinical validation.

### 1:45-2:00 - Closing

"This is not an AI doctor, diagnostic system, medication recommendation engine, or clinical decision-support product. It is a local-first proof kit for making sensitive health-agent workflows inspectable, source-grounded, safety-checked, and auditable."

## Capture Checklist

- Use local pages only.
- Keep address bar and private desktop paths out of frame where possible.
- Show synthetic/demo data only.
- Do not show secrets, tokens, `.env` files, private health records, or real genetic files.
- Do not imply clinical validation or medical approval.
