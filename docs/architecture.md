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

## Risk controls

- No real patient data in repo.
- No cloud upload by default.
- No raw genotype in logs.
- No medical advice.
- Deterministic tools before LLM.
- Evals for unsafe output patterns.
