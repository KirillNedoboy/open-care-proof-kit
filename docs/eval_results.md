# Eval Results

OpenCare Proof Kit includes a small deterministic eval suite for the bootstrap demo. The evals are safety and evidence-behavior checks. They are not clinical validation.

## Purpose

The eval suite checks that demo output patterns preserve the MVP safety boundary:

- no dosage recommendation;
- sources are required;
- uncertainty and limitations remain visible;
- VUS or unsupported findings are not treated as actionable;
- unsupported drugs return safe no-claim output;
- demo-only disclosure remains visible;
- coverage limitations remain explicit;
- audit-related language is present where required.

The evals are meant to fail fast if a future report writer or template drifts toward unsafe medical-advice behavior.

## Current Cases

Eval cases live in `evals/cases/`.

```txt
evals/cases/no_dosage_recommendation.json
evals/cases/coverage_limitations_required.json
evals/cases/demo_only_disclosure_required.json
evals/cases/no_source_no_claim.json
evals/cases/source_required.json
evals/cases/unsupported_drug_no_claim.json
evals/cases/vus_not_actionable.json
```

### `no_dosage_recommendation`

Checks that the sample text contains safety/evidence/audit language and does not include forbidden medication-action phrases.

### `source_required`

Checks that source language is present and unsupported diagnosis-style language is absent.

### `vus_not_actionable`

Checks that uncertain variants remain non-actionable and are not turned into treatment guidance.

### `unsupported_drug_no_claim`

Checks that unsupported drugs produce an explicit no-claim report and that coverage remains labeled as non-clinical.

### `no_source_no_claim`

Checks that missing source language collapses to a no-claim outcome rather than unsupported medical prose.

### `demo_only_disclosure_required`

Checks that demo-only and synthetic-data disclosure remains visible in the output.

### `coverage_limitations_required`

Checks that coverage limitations stay explicit and are not confused with clinical completeness.

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

Phase 1.4 target validation after evidence hardening:

```json
{
  "passed_cases": 7,
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
