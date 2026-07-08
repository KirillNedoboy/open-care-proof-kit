# OpenCare Proof Kit

OpenCare Proof Kit is a privacy-first personal/family medical workspace foundation. The current repo proves that foundation with synthetic/demo-only Health/Family Vault data, deterministic provenance-preserving builders, reviewer artifacts, a read-only reviewer UI, CI, and trust metrics.

The product rule is simple: vault first, genetics second, LLM third as interface. OpenCare should be useful without DNA. The current implementation is not an AI doctor, not diagnosis, not treatment recommendation, not dosage guidance, and not clinical decision support.

The existing Medication-to-Doctor Briefing / PGx demo remains intact as the narrow reference workflow. Genetics remains a future layer. The LLM remains an interface/explanation layer, not the source of truth.

## Current Status

- Latest implemented runtime phase: V2B local user-owned vault file mode.
- Current deployment pass: self-hosted vault foundation plus local user-owned vault file mode.
- Public default branch: `main`.
- Data scope: shipped repo data is synthetic/demo-only; runtime can mount an operator-supplied local vault JSON file.
- Validation baseline: `pytest` 116 passed, `ruff` passed, `mypy` passed with no issues in 37 source files, `evals.runner` 12 passed / 0 failed, `evals.trust_metrics` passed.

See [docs/project_status.md](docs/project_status.md) for the current repo snapshot.

## Reviewer Quick Links

- Local reviewer route: `/demo/health-vault`
- Reviewer pack: [docs/final_reviewer_pack.md](docs/final_reviewer_pack.md)
- Reviewer quickstart: [docs/reviewer_quickstart.md](docs/reviewer_quickstart.md)
- Health/Family Vault demo guide: [docs/health_family_vault_demo.md](docs/health_family_vault_demo.md)
- Reviewer summary artifact: [docs/assets/health_vault/family-vault-summary.md](docs/assets/health_vault/family-vault-summary.md)
- Reviewer manifest: [docs/assets/health_vault/family-vault-manifest.json](docs/assets/health_vault/family-vault-manifest.json)
- Threat model: [docs/privacy_safety_threat_model.md](docs/privacy_safety_threat_model.md)
- Provenance semantics: [docs/provenance_semantics.md](docs/provenance_semantics.md)
- Vault artifact guarantees: [docs/vault_artifact_guarantees.md](docs/vault_artifact_guarantees.md)

## What Is Implemented Now

- Health/Family Vault Core schemas plus a synthetic family dataset.
- Deterministic loader and validation for the synthetic family vault.
- Deterministic read model with provenance coverage and safety boundary notices.
- Deterministic local reviewer artifacts: JSON read model, Markdown summary, manifest.
- Committed synthetic reviewer artifacts under `docs/assets/health_vault/`.
- Read-only local reviewer page at `/demo/health-vault`.
- Read-only active vault page at `/vault`.
- Deterministic `Context / Provenance Trace Graph` on the reviewer page.
- Privacy/safety threat model, provenance semantics, and artifact guarantee docs.
- GitHub Actions CI for tests, lint, type checks, evals, and trust metrics.
- Deterministic local trust metrics report for reviewer/demo trust checks.
- Production config validation with fail-closed checks for secrets and private mode.
- Public `/health`, `/healthz`, and `/readyz` endpoints for self-hosted checks.
- Minimal password-gated private deployment mode for non-health routes.
- Configurable runtime vault source through `OPENCARE_VAULT_SOURCE=demo|local_file`.
- Mounted local vault file support through `OPENCARE_VAULT_FILE=/path/to/vault.json`.
- Dockerfile, compose foundation, and deployment guide for self-hosted use.
- Existing Medication-to-Doctor Briefing / PGx reference workflow, report, audit, and eval path.

## What OpenCare Is

- A privacy-first personal/family medical workspace foundation.
- A local-first repo for source-grounded, fail-closed health-agent infrastructure.
- A vault-first design that is useful before any genetics layer exists.
- A deterministic provenance, safety, audit, and eval discipline around synthetic/demo health data.
- A reviewer-friendly proof kit with inspectable artifacts, docs, UI, CI, and trust metrics.

## What OpenCare Is Not

- Not an AI doctor.
- Not diagnosis.
- Not treatment recommendation.
- Not dosage guidance.
- Not medication selection advice.
- Not start/stop medication advice.
- Not clinical decision support.
- Not clinical validation.
- Not real-patient support.
- Not real-genetic-data support.
- Not a FASTQ, BAM, WGS, or production genomics pipeline.

## Why The Repo Is Vault-First

The main implemented foundation is the Health/Family Vault layer: family context, recorded medications, conditions/concerns, labs, visits, timeline events, questions, sources, provenance coverage, and reviewer artifacts. That layer is already useful without DNA and gives the project a real data model for sensitive personal context.

Genetics is still intentionally second. The current repo keeps the older Medication-to-Doctor Briefing / PGx demo because it is a good stress test for evidence, safety, audit, and eval behavior. But it is no longer the whole product story.

The LLM is intentionally third. Deterministic loaders, read models, rules, provenance checks, and safety checks come first. Any future model layer should explain or navigate that structure, not replace it.

## Implemented Surfaces

### Health/Family Vault reviewer path

The reviewer route is:

```txt
http://127.0.0.1:8000/demo/health-vault
```

It is local and read-only. It accepts no user input, no upload, and no arbitrary file path. It renders synthetic/demo-only vault data, provenance coverage, safety boundaries, manifest trust flags, and the deterministic context/provenance trace graph.

### Active vault path

The runtime vault route is:

```txt
http://127.0.0.1:8000/vault
```

It is local and read-only. In the default `demo` source it renders the synthetic family vault. In `local_file` mode it renders the mounted local JSON file through the same deterministic loader and read-model path. The page labels the source, shows provenance coverage, keeps the safety boundary notices, and does not expose secret environment variables or the full mounted file path.

### Medication-to-Doctor Briefing reference workflow

The existing PGx demo still runs locally for the supported `sertraline` path and the safe unsupported `aspirin` no-claim path. It produces:

- clinician-reviewable Markdown;
- JSON audit metadata;
- static-text and pipeline-backed eval coverage.

This workflow remains synthetic/demo-only and does not provide diagnosis, treatment recommendation, dosage guidance, medication selection, or clinical decision support.

## Quickstart

Install in a Python 3.12 environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Core validation:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.trust_metrics
```

Start the local app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open:

```txt
http://127.0.0.1:8000/
http://127.0.0.1:8000/demo
http://127.0.0.1:8000/demo/health-vault
http://127.0.0.1:8000/vault
http://127.0.0.1:8000/healthz
http://127.0.0.1:8000/readyz
http://127.0.0.1:8000/demo/report-view?drug=sertraline
http://127.0.0.1:8000/demo/report-view?drug=aspirin
```

## Deployment

OpenCare now includes a minimal self-hosted deployment foundation.

- Development mode stays easy with `OPENCARE_ENV=development`.
- Production mode requires `OPENCARE_SECRET_KEY`.
- Private production mode also requires `OPENCARE_ACCESS_PASSWORD`.
- Non-health routes can be password-gated when `OPENCARE_DEMO_MODE=false`.
- Vault runtime source is selected with `OPENCARE_VAULT_SOURCE=demo|local_file`.
- Local-file mode requires `OPENCARE_VAULT_FILE` and should use a read-only host mount.
- The private password form is served at `/access`.
- Health checks stay public at `/health`, `/healthz`, and `/readyz`.

See [docs/deployment.md](docs/deployment.md) for:

- local run;
- Docker run;
- `docker compose` run;
- demo source vs local-file source;
- production env vars;
- private gate behavior;
- local vault template and mount pattern;
- security boundaries for this self-hosted MVP.

## Validation And Trust Metrics

GitHub Actions CI runs:

- `python -m pytest`
- `python -m ruff check app tests evals`
- `python -m mypy app evals`
- `python -m evals.runner`
- `python -m evals.trust_metrics`

Local trust metrics combine eval totals with Health/Family Vault manifest safety flags and the generated-report ignore check. They are automated reviewer/demo trust checks, not clinical validation.

Current eval metrics:

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

## Safety Boundaries

The current repo must not generate:

- diagnosis;
- treatment plan;
- dosage adjustment;
- medication selection advice;
- start/stop medication instruction;
- source-less medical claims;
- hidden uncertainty;
- clinical decision support claims.

The Health/Family Vault layer must remain:

- deterministic;
- provenance-preserving;
- read-only in the reviewer UI;
- not medical interpretation;
- not clinical validation.

The shipped repository remains synthetic/demo-only. If you run local-file mode, keep private health data outside Git and mount it at runtime. Do not commit private vault files.

Generated files under `reports/` remain ignored by Git.

## Repo Map

```txt
app/vault        health vault schemas and demo patient loading for the PGx path
app/health_vault Health/Family Vault schemas, loader, read model, artifacts, trace graph
app/genetics     demo genotype/VCF-like parsing and normalization for the PGx path
app/evidence     local evidence pack schema and loading
app/pgx          deterministic medication/genotype rule matching
app/safety       medical safety policy engine
app/ai           report-writing adapter
app/reports      Markdown and audit JSON output
evals            deterministic safety/evidence/trust checks
docs             reviewer, grant, architecture, safety, and status docs
tests            deterministic unit tests
```

## Grant And Reviewer Docs

- [docs/final_reviewer_pack.md](docs/final_reviewer_pack.md)
- [docs/grant_submission_answers.md](docs/grant_submission_answers.md)
- [docs/grant_short_pitch.md](docs/grant_short_pitch.md)
- [docs/grant_application_pack.md](docs/grant_application_pack.md)
- [docs/grant_milestones.md](docs/grant_milestones.md)
- [docs/final_submission_checklist.md](docs/final_submission_checklist.md)
- [docs/demo_video_script.md](docs/demo_video_script.md)
- [docs/screenshots.md](docs/screenshots.md)

## Roadmap

Near-term work should stay conservative:

- reviewer/package polish and public GitHub spot-checks;
- vault-first ingest and provenance improvements;
- clearer clinician-review handoff exports;
- genetics only after the vault foundation stays safe and inspectable.

See [docs/roadmap.md](docs/roadmap.md) for the full conservative roadmap.
