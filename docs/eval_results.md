# Eval Results

OpenCare Proof Kit includes a small deterministic eval suite for the bootstrap demo. The evals are safety and evidence-behavior checks. They are not clinical validation.

## Purpose

The eval suite checks that demo output patterns preserve the MVP safety boundary:

- no dosage recommendation;
- sources are required;
- uncertainty and limitations remain visible;
- VUS or unsupported findings are not treated as actionable;
- audit-related language is present where required.

The evals are meant to fail fast if a future report writer or template drifts toward unsafe medical-advice behavior.

## Current Cases

Eval cases live in `evals/cases/`.

```txt
evals/cases/no_dosage_recommendation.json
evals/cases/source_required.json
evals/cases/vus_not_actionable.json
```

### `no_dosage_recommendation`

Checks that the sample text contains safety/evidence/audit language and does not include forbidden medication-action phrases.

### `source_required`

Checks that source language is present and unsupported diagnosis-style language is absent.

### `vus_not_actionable`

Checks that uncertain variants remain non-actionable and are not turned into treatment guidance.

## Metrics

The eval runner reports:

- `passed_cases`;
- `failed_cases`;
- `unsafe_advice_rate`;
- `missing_source_rate`;
- `uncertainty_missing_rate`;
- `audit_missing_rate`;
- per-case pass/failure details.

Run:

```bash
python -m evals.runner
```

## Latest Validation Result

Current latest validation from Phase 1.1/1.2 readiness work:

```json
{
  "passed_cases": 3,
  "failed_cases": 0,
  "unsafe_advice_rate": 0.0,
  "missing_source_rate": 0.0,
  "uncertainty_missing_rate": 0.0,
  "audit_missing_rate": 0.0
}
```

The command also writes `evals/results/latest.json`.

## Why Evals Are A Grant Asset

For sensitive health-agent workflows, grant value is not only in a demo report. It is in the repeatable checks that prevent regressions:

- unsafe advice checks;
- source and limitation checks;
- uncertainty checks;
- audit checks;
- deterministic local execution.

These evals make safety behavior inspectable and extensible for future contributors.

## What The Evals Do Not Claim

The eval suite does not claim:

- clinical validation;
- medication appropriateness;
- diagnosis accuracy;
- pharmacogenomics completeness;
- regulatory approval.

The evals are engineering guardrails for the demo pipeline, not medical evidence.
