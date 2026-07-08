# CHECKPOINT.md

## Project

OpenCare Proof Kit

## Current product version

v0.1 vault-first proof kit.

## Current phase

V2B local user-owned vault file mode

## Current status

The latest implemented runtime phase is V2B local user-owned vault file mode. This phase keeps the synthetic/demo reviewer surfaces and the narrow PGx reference workflow intact while adding a read-only runtime vault route, mounted local JSON file support, and operator-facing deployment/docs updates on top of the V2A self-hosted foundation.

- Health/Family Vault remains the main implemented foundation.
- The repo remains useful without DNA.
- Genetics remains a later layer.
- The LLM remains an interface/explanation layer, not the source of truth.
- The read-only reviewer route remains `/demo/health-vault`.
- The active runtime vault route is `/vault`.
- The deterministic context/provenance trace graph remains part of that reviewer route.
- Public health endpoints now include `/health`, `/healthz`, and `/readyz`.
- Production mode now validates `OPENCARE_SECRET_KEY` and private-mode password requirements.
- Private self-hosted mode can password-gate non-health routes with a signed cookie.
- Runtime vault source is configurable through `OPENCARE_VAULT_SOURCE=demo|local_file`.
- Local-file mode requires `OPENCARE_VAULT_FILE` and is intended for read-only operator-mounted JSON files.
- Dockerfile, `.dockerignore`, `docker-compose.yml`, and `docs/deployment.md` now exist for self-hosted MVP deployment.
- Existing Medication-to-Doctor Briefing / PGx behavior remains unchanged.
- Docker/runtime validation passed for demo mode and private local-file mode in this session.

## Last validated state

V2B code baseline:

- pytest: 116 passed;
- ruff: passed;
- mypy: passed with no issues in 37 source files;
- eval runner: 12 passed cases, 0 failed cases;
- eval runner metrics: `total_cases=12`, `static_text_cases=7`, `pipeline_cases=5`, `pipeline_failure_rate=0.0`;
- trust metrics: passed and reported eval metrics plus Health/Family Vault artifact safety flags;
- reviewer route baseline: `/demo/health-vault`;
- active vault route baseline: `/vault`;
- health endpoints baseline: `/health`, `/healthz`, `/readyz`;
- private gate baseline: `/access` plus signed cookie on successful unlock;
- Docker demo-mode checks: `docker build`, `docker compose up -d`, `/healthz`, `/readyz`, `/demo/health-vault`, and `/vault` passed;
- Docker private local-file checks: `docker run` with mounted synthetic JSON, public `/healthz`, public `/readyz`, `/vault` redirect without cookie, `401` on invalid `/access`, `303` plus cookie on valid `/access`, and unlocked `/vault` passed;
- generated `reports/` artifacts remain ignored.

## Product definition

OpenCare Proof Kit is a local-first, synthetic/demo-only foundation for a privacy-first personal/family medical workspace.

The main implemented foundation is the Health/Family Vault layer: deterministic schemas, loader/validation, read model, reviewer artifacts, a read-only reviewer UI, and a deterministic context/provenance trace graph.

The first narrow reference workflow remains Medication-to-Doctor Briefing: a clinician-reviewable PGx briefing from demo health context, demo genotype-like data, local evidence packs, deterministic rules, safety policy, and audit output.

This project is not an AI doctor, not a diagnostic system, not a treatment recommendation engine, and not clinical decision support.

## Grant direction

Target: Sentient Foundation open-source AI grant.

Positioning:

- open-source infrastructure;
- local-first;
- private by default;
- empowering and public-good oriented;
- reusable provenance/safety/audit layer for sensitive personal agents.

## Current repo capabilities

- Load a synthetic family vault dataset.
- Validate deterministic person/family medical context and provenance links.
- Build a deterministic Health/Family Vault read model.
- Build deterministic local reviewer artifacts.
- Serve a read-only local reviewer page at `/demo/health-vault`.
- Serve a read-only active vault page at `/vault`.
- Build a deterministic context/provenance trace graph over the reviewer surface.
- Load a mounted local vault JSON file in read-only mode when configured.
- Validate deployment configuration for development vs production mode.
- Serve public liveness/readiness endpoints for self-hosted checks.
- Run a minimal password-gated private deployment mode for non-health routes.
- Provide Docker and compose deployment artifacts plus a deployment guide.
- Run deterministic local trust metrics.
- Run GitHub Actions CI for tests, lint, type checks, evals, and trust metrics.
- Keep the existing Medication-to-Doctor Briefing / PGx demo path intact.

## Hard boundaries

Do not implement without explicit approval:

- diagnosis;
- treatment recommendation;
- dosage recommendation or dosage adjustment;
- medication selection advice;
- start/stop medication advice;
- real patient data;
- real genetic data;
- `genome_profile` implementation;
- FASTQ/BAM/WGS pipeline;
- AlphaMissense as clinical decision layer;
- SaaS/auth/payments;
- Telegram interface;
- blockchain;
- cloud raw genotype upload by default.

## Required commands

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.trust_metrics
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Current next step

Inspect the final diff, commit V2B if it stays minimal, and then choose the next conservative vault-first step without changing genetics, LLM, PGx, or medical-safety boundaries.
