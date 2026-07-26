# Project Status (Historical)

> This legacy underscore-named document is retained for chronology only. The
> canonical current status is [docs/project-status.md](project-status.md).
> Historical phase labels and validation counts below must not be used as the
> current repository baseline.

OpenCare Proof Kit is a local-first, synthetic/demo-only foundation for a privacy-first personal/family medical workspace. The latest implemented runtime phase is V1H: a read-only Health/Family Vault reviewer UI with a deterministic context/provenance trace graph. The older Medication-to-Doctor Briefing / PGx path remains intact as the narrow reference workflow.

## Current Branching State

- Public default branch: `main`
- Historical submission branch: `phase-1-github-grant-readiness`
- Local latest implementation commit: `546a1e5 feat: add health vault provenance trace graph`

## Public Repository

```txt
https://github.com/KirillNedoboy/open-care-proof-kit
```

## Current State

- Latest implemented runtime phase: V1H Health/Family Vault context/provenance trace graph.
- Current packaging phase: V1I final grant/reviewer packaging refresh.
- V1I is docs-only. It does not change runtime code, tests, evals, routes, or product boundaries.

## Current Capabilities

- Synthetic Health/Family Vault Core schemas and synthetic family dataset.
- Deterministic loader/validation for the family vault.
- Deterministic read model with provenance coverage and safety notices.
- Deterministic local reviewer artifacts: JSON read model, Markdown summary, manifest.
- Committed synthetic reviewer artifacts under `docs/assets/health_vault/`.
- Read-only local reviewer route at `/demo/health-vault`.
- Deterministic context/provenance trace graph in the reviewer UI.
- Privacy/safety threat model, provenance semantics, and artifact guarantee docs.
- GitHub Actions CI for tests, lint, type checks, evals, and trust metrics.
- Deterministic local trust metrics report.
- Existing Medication-to-Doctor Briefing / PGx demo with Markdown report, JSON audit, and eval coverage.

## Current Validation Baseline

```txt
pytest: 87 passed
ruff: passed
mypy: no issues in 36 source files
evals.runner: 12 passed cases, 0 failed cases
evals.trust_metrics: passed
```

Eval metrics:

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

Validation commands:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.trust_metrics
```

## Reviewer Surface

- Primary local reviewer route: `/demo/health-vault`
- Compact reviewer index: `docs/final_reviewer_pack.md`
- Key synthetic reviewer artifacts:
  - `docs/assets/health_vault/family-vault-read-model.json`
  - `docs/assets/health_vault/family-vault-summary.md`
  - `docs/assets/health_vault/family-vault-manifest.json`

## Product Boundaries

The current repo does not provide:

- diagnosis;
- treatment recommendation;
- dosage guidance;
- medication selection advice;
- start/stop medication advice;
- clinical decision support;
- clinical validation;
- real patient support;
- real genetic data support;
- FASTQ/BAM/WGS processing.

The reviewer route is read-only, accepts no user input, accepts no upload, and renders synthetic/demo-only vault data only.

## Current Non-Goals

- real patient data
- real genetic data
- `genome_profile` implementation
- VCF/raw genotype, FASTQ, BAM, or WGS support in the vault layer
- SaaS/auth/payments
- Telegram
- blockchain
- cloud raw genotype upload by default

## Next Safe Step

- push or merge the final branch;
- run one public GitHub spot-check for README/doc link rendering and ignored generated artifacts;
- then stop feature work before submission unless a real blocker is found.
