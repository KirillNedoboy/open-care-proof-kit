# Eval Results

OpenCare Proof Kit includes a deterministic eval suite for the local demo. The evals are safety and evidence-behavior checks. They are not clinical validation.

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

The evals are split across two modes:

- static-text guardrails check known safety/evidence phrases without running the full pipeline;
- pipeline evals execute the real local demo pipeline via `build_demo_briefing(...)` and verify report plus audit behavior for supported and unsupported drugs.

The evals are meant to fail fast if a future report writer, template, or pipeline change drifts toward unsafe medical-advice behavior.

## Current Cases

Eval cases live in `evals/cases/`.

```txt
evals/cases/no_dosage_recommendation.json
evals/cases/coverage_limitations_required.json
evals/cases/demo_only_disclosure_required.json
evals/cases/no_source_no_claim.json
evals/cases/pipeline_aspirin_unsupported_no_claim.json
evals/cases/pipeline_audit_raw_export_false.json
evals/cases/pipeline_coverage_demo_only_disclosure.json
evals/cases/pipeline_report_requires_safety_note.json
evals/cases/pipeline_sertraline_matched_demo_rule.json
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

### `pipeline_sertraline_matched_demo_rule`

Executes the real local demo pipeline for `sertraline` and verifies the report and audit show a matched demo rule with safe audit fields.

### `pipeline_aspirin_unsupported_no_claim`

Executes the real local demo pipeline for `aspirin` and verifies the unsupported-drug path stays explicit, non-prescriptive, and audit-safe.

### `pipeline_report_requires_safety_note`

Executes the real local demo pipeline and checks that required report safety language remains present.

### `pipeline_audit_raw_export_false`

Executes the real local demo pipeline and checks that the audit still records `raw_health_or_genetic_data_exported=false`.

### `pipeline_coverage_demo_only_disclosure`

Executes the real local demo pipeline and checks that demo-only and not-clinical-coverage disclosure remains visible.

## Metrics

The eval runner reports:

- `total_cases`;
- `static_text_cases`;
- `pipeline_cases`;
- `passed_cases`;
- `failed_cases`;
- `unsafe_advice_rate`;
- `missing_source_rate`;
- `uncertainty_missing_rate`;
- `audit_missing_rate`;
- `pipeline_failure_rate`;
- per-case pass/failure details.

Run:

```bash
python -m evals.runner
```

## Historical Phase 1.5 / Legacy Demo Eval Baseline

The 12-case result below is a historical demo sub-suite baseline. It is not the
latest whole-repository validation result. Current validation is recorded in
`docs/validation/latest-verified-baseline.md` with its exact code SHA.

Phase 1.5 target validation after pipeline-backed eval hardening:

```json
{
  "total_cases": 12,
  "static_text_cases": 7,
  "pipeline_cases": 5,
  "passed_cases": 12,
  "failed_cases": 0,
  "unsafe_advice_rate": 0.0,
  "missing_source_rate": 0.0,
  "uncertainty_missing_rate": 0.0,
  "audit_missing_rate": 0.0,
  "pipeline_failure_rate": 0.0
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

The evals are engineering guardrails for the demo pipeline, not medical evidence. Static-text evals and pipeline evals both protect the local demo, but neither mode claims clinical validity, medication appropriateness, or pharmacogenomic completeness.
