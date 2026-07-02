# Architecture

## Pipeline

```txt
Local UI / CLI
  -> Health Vault Loader
  -> Genotype Parser
  -> Evidence Pack Loader
  -> PGx Rule Matcher
  -> Safety Policy Engine
  -> Report Writer
  -> Markdown Report + JSON Audit
  -> Eval Runner
```

## Components

- `app/vault`: health vault schema and demo patient loading.
- `app/health_vault`: V1A Health/Family Vault Core schemas, validation, provenance links, and synthetic family demo loading.
- `app/genetics`: demo genotype/VCF-like parsing and normalization.
- `app/evidence`: evidence pack schema and loading.
- `app/pgx`: deterministic medication/genotype matching.
- `app/safety`: safety policy checks.
- `app/ai`: report-writing adapter. No clinical reasoning authority.
- `app/reports`: Markdown and audit JSON output.
- `evals`: synthetic safety/evidence eval runner.

## Data flow

1. Load synthetic patient vault.
2. Parse genotype-like data.
3. Load evidence pack.
4. Match drug-specific rules.
5. Produce findings.
6. Render report.
7. Run safety policy.
8. Export report and audit JSON.

## Health/Family Vault Core

V1A adds a separate `app/health_vault` domain for structured personal and family medical context. It models a synthetic family, people, relationships, medications, conditions/concerns, lab results, visits, timeline events, question threads, document sources, and evidence links.

The V1A loader validates the synthetic demo dataset from `data/demo_patients/demo_family_vault.json`. Records must reference known people, important facts must carry source/provenance links, and evidence links must reference known synthetic document sources.

This phase does not add genetics, `genome_profile`, VCF/raw genotype support, API routes, CLI commands, dashboard UI, or AI-generated medical decisions. Conditions represent user/demo-recorded context only; they are not OpenCare diagnoses.

## Risk controls

- No real patient data in repo.
- No cloud upload by default.
- No raw genotype in logs.
- No medical advice.
- Deterministic tools before LLM.
- Evals for unsafe output patterns.
