# Demo Video Script

Target length: 90-120 seconds.

Use only the local demo server and synthetic/demo data. Do not show bookmarks, secrets, private desktop paths, real patient data, real genetic data, or generated files outside the ignored `reports/` directory.

## Script

### 0:00-0:12 - Opening

"OpenCare Proof Kit is not a medical chatbot. It is a privacy-first personal and family medical workspace foundation. The current rule is vault first, genetics second, LLM third as interface."

### 0:12-0:25 - Landing Page

Show:

```txt
http://127.0.0.1:8000/
```

Talking points:

- synthetic/demo-only current repo;
- Health/Family Vault is the main implemented foundation;
- no diagnosis, no treatment recommendation, no dosage guidance, no clinical decision support.

### 0:25-0:55 - Health/Family Vault Reviewer Route

Show:

```txt
http://127.0.0.1:8000/demo/health-vault
```

Talking points:

- read-only reviewer page;
- safety banner is visible at the top;
- family overview and provenance coverage are shown directly;
- committed manifest trust flags are used on purpose for reviewer trust checks.

### 0:55-1:15 - Context / Provenance Trace Graph

Keep showing `/demo/health-vault`.

Talking points:

- the `Context / Provenance Trace Graph` is deterministic;
- it links recorded items to people, sources, safety boundaries, and reviewer artifacts;
- it is provenance and traceability only, not medical interpretation and not clinical validation.

### 1:15-1:30 - Trust Metrics

Show terminal command:

```powershell
.\.venv\Scripts\python.exe -m evals.trust_metrics
```

Talking points:

- trust metrics report eval totals plus Health/Family Vault manifest safety flags;
- CI runs the same checks on `push` and `pull_request`;
- these are engineering trust checks, not clinical validation.

### 1:30-1:48 - Existing Medication-to-Doctor Briefing Reference Workflow

Show:

```txt
http://127.0.0.1:8000/demo/report-view?drug=sertraline
```

Talking points:

- the older Medication-to-Doctor Briefing / PGx path still works;
- it remains the narrow reference workflow;
- it includes sources, limitations, safety language, and audit metadata.

### 1:48-2:00 - Closing

"Today the repo is synthetic/demo-only. It does not provide medical advice, diagnosis, treatment recommendation, dosage guidance, or clinical validation. What it does provide is an inspectable, local-first foundation for sensitive health-agent workflows."

## Capture Checklist

- Use local pages only.
- Show synthetic/demo content only.
- Keep private paths and secrets out of frame.
- Do not imply real-patient support or real-genetic-data support.
- Do not imply clinical validation or medical approval.
