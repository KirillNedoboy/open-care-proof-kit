# SESSION_NOTES.md

This file records what actually happened in each work session.

It is not a roadmap. It is the operational memory for future Codex sessions.

## 2026-07-08 - V2C production/VPS deployment pack

### Changed
- Added `docker-compose.prod.yml` for the single validated VPS deployment path:
  - app service stays on an internal compose network;
  - Caddy is the only public-facing service on `80/443`;
  - app runtime is fixed to `OPENCARE_ENV=production`, `OPENCARE_DEMO_MODE=false`, `OPENCARE_VAULT_SOURCE=local_file`, and `OPENCARE_VAULT_FILE=/vault/local-family-vault.json`;
  - the vault file mount is read-only;
  - restart policy and container healthcheck are included.
- Added `deploy/Caddyfile.example`:
  - placeholder domain `opencare.example.com`;
  - HTTPS/TLS termination at Caddy;
  - reverse proxy to `opencare:8000`.
- Added `deploy/env.production.example`:
  - `OPENCARE_SECRET_KEY`;
  - `OPENCARE_ACCESS_PASSWORD`;
  - `OPENCARE_LOCAL_VAULT_PATH`.
- Added `scripts/smoke_check.py` using Python standard library only:
  - checks `/healthz` and `/readyz`;
  - checks `/vault` public behavior in demo/public mode;
  - checks `/vault` redirect behavior in private mode;
  - when a password is supplied, verifies the `/access` login flow and unlocked `/vault`;
  - exits non-zero on failure without printing the password.
- Added `tests/test_smoke_check.py` with RED->GREEN coverage for:
  - base URL normalization;
  - public `/vault` acceptance;
  - private redirect detection;
  - private login-flow validation.
- Updated docs for the new deployment pack:
  - `README.md`;
  - `docs/deployment.md`;
  - `docs/production_deployment.md`;
  - `CHECKPOINT.md`.
- Updated ignore rules:
  - `.gitignore` ignores uncommitted `deploy/env.production` and `deploy/Caddyfile`;
  - `.dockerignore` excludes those operator files from build context.

### Validation
- RED phase: `.\.venv\Scripts\python.exe -m pytest tests/test_smoke_check.py -q` failed with `ModuleNotFoundError: No module named 'scripts'`.
- GREEN phase: `.\.venv\Scripts\python.exe -m pytest tests/test_smoke_check.py -q` - 8 passed.
- `.\.venv\Scripts\python.exe -m pytest` - 124 passed.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals scripts` - passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 37 source files.
- `.\.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- `.\.venv\Scripts\python.exe -m evals.trust_metrics` - passed.

### Docker
- `docker build -t opencare-proof-kit:local .` - passed.
- `docker compose up -d --build` - passed in demo mode.
- Demo-mode checks passed:
  - `GET /healthz` returned `200`;
  - `GET /readyz` returned `200`;
  - `GET /demo/health-vault` returned `200`;
  - `GET /vault` returned `200`.
- `docker compose down` - completed cleanly.
- Safe production-compose validation passed with disposable local values and the synthetic template vault:
  - copied `deploy/env.production.example` to ignored `deploy/env.production`;
  - copied `deploy/Caddyfile.example` to ignored `deploy/Caddyfile`;
  - `docker compose -f docker-compose.prod.yml config` passed after loading disposable env values;
  - `docker compose --env-file deploy/env.production -f docker-compose.prod.yml up -d --build opencare` passed;
  - `docker compose ... ps` reported the `opencare` service healthy;
  - internal `GET /healthz` and `GET /readyz` returned `200`;
  - internal `GET /vault` redirected to `/access`;
  - valid `POST /access` returned `303`, set the signed cookie, and unlocked `/vault`;
  - unlocked `/vault` rendered the synthetic template data and did not expose `/vault/local-family-vault.json`;
  - service logs did not expose secrets or full mounted paths;
  - `docker compose --env-file deploy/env.production -f docker-compose.prod.yml down` completed cleanly.
- The full local Caddy/TLS path was not started in this session because the documented production path depends on a real public domain and DNS, which is not appropriate for local disposable validation.

### Product boundaries
- No product/runtime behavior changed.
- No diagnosis, treatment recommendation, dosage guidance, medication selection advice, or start/stop medication advice were added.
- No upload support, database persistence, accounts, payments, LLM generation, or genetics support were added.
- Existing PGx behavior and `build_demo_briefing("sertraline")` remained unchanged.
- Safety/evals were preserved.
- No real personal/patient data was committed.

### Next safe step
- Inspect the final diff, commit V2C on the feature branch if it stays minimal, and stop unless a new narrowly scoped deployment or vault-first task is explicitly approved.

## 2026-07-08 - V2B local user-owned vault file mode

### Changed
- Added runtime vault source config in `app/config.py`:
  - `OPENCARE_VAULT_SOURCE=demo|local_file`;
  - `OPENCARE_VAULT_FILE`;
  - validation for invalid source, missing file, unreadable file, and production local-file private-mode requirements.
- Split Health/Family Vault validation between:
  - generic schema validation for operator-supplied local files;
  - retained demo-only constraints for the shipped synthetic demo loader path.
- Added `app/health_vault/runtime_loader.py`:
  - `ActiveVault`;
  - `load_active_vault(settings)` for demo or mounted local-file source.
- Added `GET /vault` in `app/main.py`:
  - renders the active configured vault source;
  - keeps the page read-only;
  - shows source labeling and provenance coverage;
  - avoids exposing full mounted file paths in HTML.
- Kept `/demo/health-vault` unchanged as the reviewer/demo route with trace graph and committed trust flags.
- Updated `app/templates/health_vault.html` so it can render either:
  - the reviewer/demo view with trace graph and trust flags;
  - the runtime vault view without those demo-only sections.
- Added `docs/examples/local-family-vault.template.json` as a synthetic/template-only mounted-file example.
- Updated ignore and deploy artifacts:
  - `.gitignore` ignores `private/` and `vault.local.json`;
  - `.dockerignore` ignores `private` and `vault.local.json`;
  - `docker-compose.yml` documents local-file env vars and a read-only bind-mount example;
  - `.env.example` documents `OPENCARE_VAULT_SOURCE` and `OPENCARE_VAULT_FILE`.
- Updated `README.md`, `docs/deployment.md`, and `CHECKPOINT.md` for V2B runtime behavior and deployment flow.

### Validation
- `.\.venv\Scripts\python.exe -m pytest` - 116 passed.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 37 source files.
- `.\.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- `.\.venv\Scripts\python.exe -m evals.trust_metrics` - passed.
- Focused runtime-loader/config/API subsets also passed during implementation before the final full-suite run.

### Docker
- `docker build -t opencare-proof-kit:local .` - passed.
- `docker compose up -d --build` - passed in default demo source mode.
- Demo-mode smoke checks passed:
  - `GET /healthz` returned healthy JSON;
  - `GET /readyz` returned ready JSON;
  - `GET /demo/health-vault` returned `200`;
  - `GET /vault` returned `200` and rendered demo source labeling.
- Private production local-file smoke checks passed with disposable local test values and a read-only mount of `docs/examples/local-family-vault.template.json`:
  - `GET /healthz` stayed public;
  - `GET /readyz` stayed ready;
  - `GET /vault` without cookie redirected to `/access`;
  - invalid `POST /access` returned `401`;
  - valid `POST /access` returned `303`, set the signed cookie, and unlocked `/vault`;
  - unlocked `/vault` rendered local-file source labeling and template data;
  - no secret or full mounted path leakage was found in the HTML or container logs.
- `docker compose down` and temporary private-mode container cleanup completed.

### Product boundaries
- No uploads, database persistence, accounts, LLM generation, genetics support, payments, or clinical workflows were added.
- No diagnosis, treatment recommendation, dosage guidance, medication selection advice, or start/stop medication advice were added.
- Existing PGx behavior and `build_demo_briefing("sertraline")` remained unchanged.
- Safety/evals were preserved.
- No private health data was committed; only a synthetic/template local-vault example was added.

### Next safe step
- Inspect the final diff, commit V2B on the feature branch, and stop unless a narrowly scoped next vault-first task is explicitly approved.

## 2026-07-08 - V2A deployable self-hosted vault foundation

### Changed
- Added typed deployment config validation in `app/config.py`:
  - `OPENCARE_ENV=development|production`;
  - `OPENCARE_DEMO_MODE=true|false`;
  - production requires `OPENCARE_SECRET_KEY`;
  - production private mode also requires `OPENCARE_ACCESS_PASSWORD`.
- Added public health endpoints in `app/main.py`:
  - `GET /health` kept as compatibility route;
  - `GET /healthz` for liveness;
  - `GET /readyz` for config/asset readiness.
- Added a minimal private deployment gate:
  - `GET /access`;
  - `POST /access`;
  - signed `HttpOnly` cookie for successful unlock;
  - public allowlist for `/health`, `/healthz`, `/readyz`, `/access`, and `/static/*`.
- Kept existing reviewer and PGx routes intact in development/demo mode.
- Added focused config and API regression tests for deployment behavior.
- Reworked deploy artifacts:
  - runtime-focused `Dockerfile`;
  - `.dockerignore`;
  - updated `docker-compose.yml`;
  - updated `.env.example`.
- Added `docs/deployment.md`.
- Updated `README.md` and `CHECKPOINT.md` for the self-hosted MVP foundation.

### Validation
- `.venv\Scripts\python.exe -m pytest` - 103 passed.
- `.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.venv\Scripts\python.exe -m mypy app evals` - passed.
- `.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- `.venv\Scripts\python.exe -m evals.trust_metrics` - passed.

### Docker
- `docker build -t opencare-proof-kit:local .` could not run to completion because the local Docker daemon was unavailable:
  - `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`
- Docker compose smoke checks were not run for the same reason.

### Product boundaries
- No diagnosis, treatment recommendation, dosage guidance, medication selection advice, or start/stop advice added.
- No LLM generation added.
- No real genetics, VCF/raw genotype, FASTQ/BAM/WGS, or upload flow added.
- Existing PGx behavior and eval/safety expectations were preserved.

### Next safe step
- Start the Docker daemon and re-run the blocked Docker build/compose smoke checks.
- If Docker validation passes, the next conservative phase can focus on minimal vault usability without adding uploads, accounts, databases, or clinical workflows.

## 2026-07-07 - V1I final grant/reviewer packaging refresh

### Changed
- Refreshed the public README to match the implemented V1A-V1H state instead of centering the older PGx demo alone.
- Reframed the repo as a privacy-first personal/family medical workspace foundation with the product rule: vault first, genetics second, LLM third as interface.
- Updated grant docs so they describe the implemented synthetic Health/Family Vault foundation, deterministic read model, reviewer artifacts, read-only reviewer UI, context/provenance trace graph, CI, and trust metrics.
- Updated final submission docs to the current validation baseline:
  - `pytest`: 87 passed;
  - `evals.runner`: 12 passed / 0 failed;
  - `mypy`: no issues in 36 source files;
  - trust metrics: passed.
- Added `docs/final_reviewer_pack.md` as a compact reviewer index.
- Updated roadmap/checkpoint/status docs to record V1I as docs-only and to keep V1H as the latest implemented runtime phase.

### Product boundaries
- Docs-only packaging refresh.
- No runtime code changes.
- No route changes.
- No test or eval behavior changes.
- No upload or user-input surface added.
- No LLM generation added.
- No genetics support added.
- No PGx behavior changes.
- No safety boundary changes.

### Next safe step
- Push or merge the final branch.
- Run one public GitHub spot-check for README/doc links and ignored generated artifacts.
- Stop feature work before submission unless a real blocker is found.

## 2026-06-25 - Project bootstrap package

### Done
- Defined final product direction: OpenCare Proof Kit.
- Positioned product as open-source local-first trust/evidence/safety toolkit for private health AI agents.
- Created project memory files: AGENTS.md, SESSION_NOTES.md, CHECKPOINT.md.
- Created documentation scaffold for product, grant, architecture, evidence, safety, demo and roadmap.
- Created Python/FastAPI skeleton with demo pipeline, deterministic parser/matcher/safety/report modules.
- Added synthetic demo data, evidence pack, eval cases and initial tests.

### Decisions
- Do not position the project as AI doctor or genetic consultant.
- Keep pharmacogenomics as reference workflow, not the entire product.
- Keep v0.1 local-first and demo/synthetic-data only.
- Deterministic parsers/rules must run before LLM.
- LLM is report/explanation layer only.
- Safety policy and evals are core grant assets.

### Not touched
- No real patient data.
- No FASTQ/BAM/WGS pipeline.
- No SaaS/auth/payments/Telegram.
- No cloud raw genotype upload by default.

### Next safe step
- Open this repo in Codex.
- Ask Codex to run tests, fix bootstrap issues, improve docs, and make the local demo pipeline production-clean without changing project boundaries.

## 2026-06-25 - Bootstrap validation and hardening

### Changed
- Fixed bootstrap lint/type failures:
  - sorted imports in `app/config.py`;
  - wrapped long report/safety/eval lines;
  - replaced loosely typed eval case dictionaries with a validated `EvalCase` Pydantic model.
- Hardened demo genotype parsing:
  - 23andMe-like parser now rejects non-positive positions with line-specific errors;
  - 23andMe-like parser now rejects invalid genotype tokens;
  - demo VCF-like parser now rejects unsupported chromosomes and non-positive positions.
- Hardened report/audit safety:
  - Markdown report generation rejects any finding marked `clinical_action_allowed=True`;
  - audit JSON now records `local_first`, `demo_only`, `pipeline_steps`, and `safety_policy_version`;
  - audit still hashes patient ID and does not export raw health/genetic data.
- Added regression tests for parser validation, report defense-in-depth, audit boundary metadata, and eval case schema validation.

### Files changed
- `app/config.py`
- `app/genetics/genotype_parser.py`
- `app/genetics/vcf_parser.py`
- `app/reports/markdown.py`
- `app/reports/json_audit.py`
- `app/safety/policy.py`
- `evals/runner.py`
- `tests/test_evals_runner.py`
- `tests/test_genotype_parser.py`
- `tests/test_report_generation.py`
- `SESSION_NOTES.md`

### Validation
- `py -3.12 -m venv .venv`
- `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- `.venv\Scripts\python.exe -m pytest` - 13 passed.
- `.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.venv\Scripts\python.exe -m mypy app evals` - passed.
- `.venv\Scripts\python.exe -m evals.runner` - 3 passed cases, 0 failed cases.
- Uvicorn HTTP check for `GET /demo/report?drug=sertraline` - status 200, `policy_passed=True`, `raw_health_or_genetic_data_exported=False`.

### Risks / blockers
- Workspace is not a Git repository, so branch creation, git diff, and commit checks were unavailable.
- Local `python` is 3.11.6; validation used installed Python 3.12 through `py -3.12`.
- FastAPI `TestClient` emitted a dependency deprecation warning during an auxiliary check; the Uvicorn HTTP check passed without relying on TestClient.

### Product boundaries
- No diagnosis, dosage recommendation, start/stop advice, real patient data, FASTQ/BAM/WGS pipeline, auth, payments, Telegram, blockchain, or cloud raw genotype upload was added.
- Safety policy and eval behavior were strengthened, not weakened.

### Next safe step
- Add a small API-level regression test for `/demo/report` so endpoint behavior stays covered by `pytest`.

## 2026-06-25 - Phase 1.1 demo hardening

### Changed
- Added reusable deterministic demo service in `app/demo_pipeline.py`:
  - `build_demo_briefing(drug: str)`;
  - `DemoBriefingResult` with report Markdown, audit, findings count, policy status, and policy violation codes.
- Added CLI entrypoint in `app/cli.py`:
  - `python -m app.cli demo-report --drug sertraline --out-dir reports`;
  - writes Markdown and audit JSON;
  - returns non-zero when safety policy fails.
- Refactored `app/main.py` to use the shared demo service.
- Added FastAPI endpoints:
  - `GET /demo/report.md?drug=sertraline`;
  - `GET /demo/audit?drug=sertraline`.
- Strengthened audit metadata:
  - `report_id`;
  - `app_version`;
  - required Phase 1.1 `pipeline_steps`;
  - `generated_files` when the CLI writes files.
- Added tests for the demo service, CLI behavior, and new API endpoints.
- Updated `README.md` with "Demo in 60 seconds".
- Updated `CHECKPOINT.md` current status to `validated bootstrap + demo hardening in progress`.

### Files changed
- `app/__init__.py`
- `app/cli.py`
- `app/demo_pipeline.py`
- `app/main.py`
- `app/reports/json_audit.py`
- `tests/test_api.py`
- `tests/test_cli.py`
- `tests/test_demo_pipeline.py`
- `tests/test_report_generation.py`
- `README.md`
- `CHECKPOINT.md`
- `SESSION_NOTES.md`

### Generated demo outputs
- `reports/demo-sertraline-briefing.md`
- `reports/demo-sertraline-audit.json`

### Validation
- `.venv\Scripts\python.exe -m pytest` - 18 passed.
- `.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.venv\Scripts\python.exe -m mypy app evals` - passed.
- `.venv\Scripts\python.exe -m evals.runner` - 3 passed cases, 0 failed cases.
- `.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports` - wrote both required files.
- Uvicorn HTTP check:
  - `GET /demo/report.md?drug=sertraline` - status 200, `text/markdown`;
  - `GET /demo/audit?drug=sertraline` - `policy_passed=True`, `raw_health_or_genetic_data_exported=False`.

### Risks / blockers
- Workspace is not a Git repository, so branch creation, git diff, and commit checks remain unavailable.
- Local `python` is 3.11.6; validation used the project venv with Python 3.12.

### Product boundaries
- No diagnosis, dosage recommendation, start/stop advice, real patient data, FASTQ/BAM/WGS pipeline, auth, payments, Telegram, blockchain, or cloud raw genotype upload was added.
- Safety policy and evals were not weakened.

### Next safe step
- Add a lightweight CI workflow or local `make check` equivalent once the repo is under Git, so future contributors can run the same validation sequence consistently.

## 2026-06-25 - Phase 1.2 grant/demo readiness

### Changed
- Rewrote `README.md` as a reviewer-facing GitHub landing page:
  - one-liner;
  - what it is / is not;
  - local-first rationale;
  - why this is not an AI wrapper;
  - 60-second demo;
  - text architecture diagram;
  - safety boundaries;
  - evals;
  - local run commands;
  - generated artifacts;
  - roadmap;
  - grant positioning.
- Rewrote `docs/grant_pitch.md` for open-source AI grant review:
  - open-source infrastructure;
  - private-by-default;
  - empowering, not extractive;
  - reusable trust/evidence/safety layer;
  - Medication-to-Doctor Briefing as the reference workflow;
  - explicit no-medical-advice boundary;
  - why now;
  - why grant funding is justified;
  - what funding unlocks.
- Rewrote `docs/demo_script.md` into a practical 2-3 minute demo script with exact commands, URLs, talking points, expected outputs, and fallback path.
- Created `docs/demo_artifacts.md` to explain the CLI and API report/audit artifacts and what each proves.
- Created `docs/eval_results.md` to document current eval purpose, cases, metrics, latest validation result, and limits.
- Created `docs/reviewer_quickstart.md` so a reviewer can install, test, generate reports, start the API, and run evals quickly.
- Updated `CHECKPOINT.md` with Phase 1.2 status, last validated state, current repo capabilities, and next safe step.

### Files changed
- `README.md`
- `docs/grant_pitch.md`
- `docs/demo_script.md`
- `docs/demo_artifacts.md`
- `docs/eval_results.md`
- `docs/reviewer_quickstart.md`
- `CHECKPOINT.md`
- `SESSION_NOTES.md`

### Decisions
- Kept Phase 1.2 limited to grant/demo readiness documentation.
- Did not change application behavior, data, safety policy, eval logic, or product scope.
- Explicitly labeled evals as engineering guardrails, not clinical validation.
- Preserved local-first, synthetic/demo-only positioning.

### Validation
- `.venv\Scripts\python.exe -m pytest` - 18 passed.
- `.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.venv\Scripts\python.exe -m mypy app evals` - passed.
- `.venv\Scripts\python.exe -m evals.runner` - 3 passed cases, 0 failed cases.
- `.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports` - wrote both required files.
- Generated audit check - `drug=sertraline`, `policy_passed=True`, `raw_health_or_genetic_data_exported=False`.

### Product boundaries
- No diagnosis, dosage recommendation, start/stop advice, real patient data, FASTQ/BAM/WGS pipeline, auth, payments, Telegram, blockchain, or cloud raw genotype upload was added.
- Safety policy and evals were not weakened.

### Next safe step
- Add a lightweight CI workflow or local `make check` equivalent once the repo is under Git, then expand eval coverage without changing medical-safety boundaries.

## 2026-06-25 - Phase 1.3 minimal local web demo

### Changed
- Added server-rendered FastAPI pages for the local demo:
  - `/` landing page with project framing, boundaries, architecture summary, and reviewer links;
  - `/demo` synthetic patient view with sertraline question and pipeline steps;
  - `/demo/report-view?drug=sertraline` readable HTML report view with policy status, findings count, audit summary, and raw artifact links.
- Mounted static CSS and added Jinja2 templates under `app/templates/` and `app/static/`.
- Kept existing JSON/Markdown API endpoints unchanged.
- Added API regression tests for the new HTML pages.
- Updated README and demo docs to include the browser-based path and HTML report viewer.
- Updated `CHECKPOINT.md` to move the project to Phase 1.3.

### Design input
- Used Lazyweb reference search before implementation.
- Chose a restrained reviewer-oriented UI: editorial landing framing, quick links, pipeline lists, stat cards, and a split report/audit layout.
- Did not add external frontend assets, downloaded references, or runtime dependencies beyond Jinja2.

### Files changed
- `app/main.py`
- `app/static/styles.css`
- `app/templates/index.html`
- `app/templates/demo.html`
- `app/templates/report.html`
- `tests/test_api.py`
- `pyproject.toml`
- `README.md`
- `docs/demo_script.md`
- `docs/demo_artifacts.md`
- `CHECKPOINT.md`
- `SESSION_NOTES.md`

### Validation
- RED phase: `python -m pytest tests/test_api.py` - 3 expected failures for missing HTML routes/content type.
- RED phase: `python -m pytest tests/test_api.py` - 2 expected failures for missing reviewer quickstart route/link.
- GREEN phase: `python -m pytest tests/test_api.py` - 6 passed.
- `.venv\Scripts\python.exe -m pip install -e ".[dev]"` - installed `jinja2` into the project environment after the dependency change.
- `.venv\Scripts\python.exe -m pytest` - 22 passed.
- `.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.venv\Scripts\python.exe -m mypy app evals` - passed.
- `.venv\Scripts\python.exe -m evals.runner` - 3 passed cases, 0 failed cases.
- `.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports` - wrote both required files.
- Uvicorn manual HTTP checks passed for:
  - `/`;
  - `/demo`;
  - `/demo/report-view?drug=sertraline`;
  - `/demo/report.md?drug=sertraline`;
  - `/demo/audit?drug=sertraline`;
  - `/reviewer-quickstart`.

### Product boundaries
- No diagnosis, dosage recommendation, treatment plan, start/stop advice, real patient data, FASTQ/BAM/WGS support, auth, payments, Telegram, blockchain, or cloud raw genotype upload was added.
- The HTML pages are presentation-only and use the same deterministic report/audit path.

### Next safe step
- Run the full validation sequence, then manually verify the browser routes and raw artifact endpoints under Uvicorn.

## 2026-06-25 - Phase 1.3 worktree hygiene and commit

### Changed
- Updated `.gitignore` to ignore generated `reports/*` outputs while preserving `reports/.gitkeep`.
- Removed `reports/demo-sertraline-briefing.md` and `reports/demo-sertraline-audit.json` from Git tracking with `git rm --cached` without deleting local copies.
- Kept `evals/results/*.json` ignored and did not change product behavior, safety policy, eval logic, or web demo functionality.

### Validation
- `git diff --check` - no whitespace errors; only line-ending warnings from the local Windows checkout.
- `.venv\Scripts\python.exe -m pytest` - 22 passed.
- `.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.venv\Scripts\python.exe -m mypy app evals` - passed.
- `.venv\Scripts\python.exe -m evals.runner` - 3 passed cases, 0 failed cases.
- `.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports` - wrote both report files locally.
- `git status --short` after CLI regeneration - generated report files did not appear as modified or untracked files; only the staged untracking remained.

### Commit summary
- Prepared Phase 1.3 for commit with generated runtime reports ignored and removed from version control.
- Commit message target: `feat: add minimal local web demo`.

### Product boundaries
- No diagnosis, dosage recommendation, start/stop advice, real patient data, FASTQ/BAM/WGS support, SaaS/auth/payments, Telegram, blockchain, or cloud raw genotype upload was added.

### Next safe step
- Add a lightweight CI workflow or local `make check` equivalent so validation and artifact hygiene remain repeatable for reviewers and contributors.

## 2026-06-25 - Phase 1.4 evidence pack hardening

### Changed
- Hardened evidence source validation in `app/evidence/sources.py`:
  - only `https` URLs are accepted;
  - only `cpicpgx.org`, `clinpgx.org`, `ncbi.nlm.nih.gov`, `fda.gov`, or their subdomains are accepted;
  - no network calls are performed.
- Strengthened `app/evidence/pack_schema.py`:
  - source URLs are validated through the local source validator;
  - empty `limitations` are rejected;
  - `clinical_action_allowed=true` is rejected with a clear error;
  - `clinician_review_required` must remain `true`;
  - rules inherit `demo_only` from the pack when omitted and must remain demo-only.
- Added `app/pgx/coverage.py` with demo evidence-pack coverage summaries:
  - `matched_demo_rule`;
  - `no_matching_demo_rule`;
  - `drug_not_in_demo_pack`.
- Integrated coverage through:
  - `app/demo_pipeline.py`;
  - `app/ai/report_writer.py`;
  - `app/reports/markdown.py`;
  - `app/reports/json_audit.py`;
  - `app/main.py`;
  - `app/templates/report.html`.
- Safe unsupported-drug behavior now returns a 200 no-claim report and audit for drugs like `aspirin`.
- Added regression tests for evidence validation, coverage status, unsupported-drug safety, audit/report coverage fields, and eval-case expansion.
- Added four eval cases:
  - `unsupported_drug_no_claim`;
  - `no_source_no_claim`;
  - `demo_only_disclosure_required`;
  - `coverage_limitations_required`.
- Updated reviewer docs to clarify:
  - the evidence pack is demo-only;
  - coverage is demo evidence-pack coverage, not clinical coverage;
  - no source means no claim;
  - unsupported drugs return a safe no-claim report.

### Files changed
- `app/evidence/sources.py`
- `app/evidence/pack_schema.py`
- `app/pgx/coverage.py`
- `app/demo_pipeline.py`
- `app/ai/report_writer.py`
- `app/reports/markdown.py`
- `app/reports/json_audit.py`
- `app/main.py`
- `app/templates/report.html`
- `tests/test_api.py`
- `tests/test_demo_pipeline.py`
- `tests/test_evals_runner.py`
- `tests/test_evidence_pack.py`
- `tests/test_report_generation.py`
- `evals/cases/coverage_limitations_required.json`
- `evals/cases/demo_only_disclosure_required.json`
- `evals/cases/no_source_no_claim.json`
- `evals/cases/unsupported_drug_no_claim.json`
- `README.md`
- `docs/evidence_policy.md`
- `docs/demo_artifacts.md`
- `docs/demo_script.md`
- `docs/eval_results.md`
- `CHECKPOINT.md`
- `SESSION_NOTES.md`

### Validation
- RED phase:
  - `.venv\Scripts\python.exe -m pytest tests/test_evidence_pack.py tests/test_demo_pipeline.py tests/test_report_generation.py tests/test_api.py` - failed for missing strict validation, missing coverage, and unsupported-drug 422 behavior.
  - `.venv\Scripts\python.exe -m pytest tests/test_evals_runner.py` - failed until the new eval cases were added.
- GREEN phase:
  - `.venv\Scripts\python.exe -m pytest tests/test_evidence_pack.py tests/test_demo_pipeline.py tests/test_report_generation.py tests/test_api.py tests/test_evals_runner.py` - 19 passed.
- Full validation:
  - `.venv\Scripts\python.exe -m pytest` - 29 passed.
  - `.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
  - `.venv\Scripts\python.exe -m mypy app evals` - passed.
  - `.venv\Scripts\python.exe -m evals.runner` - 7 passed cases, 0 failed cases.
  - `.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports` - wrote both sertraline artifacts.
  - `.venv\Scripts\python.exe -m app.cli demo-report --drug aspirin --out-dir reports` - wrote both aspirin artifacts.
- Manual HTTP checks passed for:
  - `/demo/report?drug=sertraline`;
  - `/demo/audit?drug=sertraline`;
  - `/demo/report-view?drug=sertraline`;
  - `/demo/report?drug=aspirin`;
  - `/demo/audit?drug=aspirin`;
  - `/demo/report-view?drug=aspirin`.

### Product boundaries
- No diagnosis, dosage recommendation, start/stop advice, real patient data, FASTQ/BAM/WGS support, SaaS/auth/payments, Telegram, blockchain, or cloud raw genotype upload was added.
- Unsupported drugs now fail closed with a safe no-claim report rather than an unsafe or misleading claim.

### Next safe step
- Add CI or a local `make check` equivalent, then expand the demo evidence pack only with explicit sources, explicit limitations, and preserved no-claim behavior for unsupported drugs.

## 2026-06-25 - Phase 1.5 pipeline-backed evals and GitHub polish

### Changed
- Extended `evals/runner.py` so eval cases support both:
  - `static_text` mode for existing wording guardrails;
  - `pipeline` mode that executes the real local demo pipeline through `build_demo_briefing(drug)`.
- Added nested audit matching for dotted paths such as `coverage.coverage_status`.
- Expanded eval metrics in `evals/metrics.py`:
  - `total_cases`;
  - `static_text_cases`;
  - `pipeline_cases`;
  - `passed_cases`;
  - `failed_cases`;
  - `unsafe_advice_rate`;
  - `missing_source_rate`;
  - `uncertainty_missing_rate`;
  - `audit_missing_rate`;
  - `pipeline_failure_rate`.
- Added five pipeline-backed eval cases:
  - `pipeline_sertraline_matched_demo_rule`;
  - `pipeline_aspirin_unsupported_no_claim`;
  - `pipeline_report_requires_safety_note`;
  - `pipeline_audit_raw_export_false`;
  - `pipeline_coverage_demo_only_disclosure`.
- Added/updated eval runner tests for:
  - preserved static-text behavior;
  - pipeline execution through `build_demo_briefing`;
  - safe unsupported-drug pipeline behavior;
  - nested audit path matching;
  - summary JSON static/pipeline counts.
- Updated reviewer-facing docs to describe pipeline-backed evals, Phase 1.5 metrics, demo-only coverage language, and current repo status.
- Added `docs/project_status.md` with current commits, capabilities, non-goals, validation commands, and next safe roadmap.

### Files changed
- `evals/metrics.py`
- `evals/runner.py`
- `evals/cases/pipeline_aspirin_unsupported_no_claim.json`
- `evals/cases/pipeline_audit_raw_export_false.json`
- `evals/cases/pipeline_coverage_demo_only_disclosure.json`
- `evals/cases/pipeline_report_requires_safety_note.json`
- `evals/cases/pipeline_sertraline_matched_demo_rule.json`
- `tests/test_evals_runner.py`
- `README.md`
- `docs/reviewer_quickstart.md`
- `docs/eval_results.md`
- `docs/demo_script.md`
- `docs/project_status.md`
- `CHECKPOINT.md`
- `SESSION_NOTES.md`

### Validation
- `.venv\Scripts\python.exe -m pytest` - 34 passed.
- `.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 29 source files.
- `.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- Eval runner metrics: `total_cases=12`, `static_text_cases=7`, `pipeline_cases=5`, `unsafe_advice_rate=0.0`, `missing_source_rate=0.0`, `uncertainty_missing_rate=0.0`, `audit_missing_rate=0.0`, `pipeline_failure_rate=0.0`.
- `.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports` - wrote `reports/demo-sertraline-briefing.md` and `reports/demo-sertraline-audit.json`.
- `.venv\Scripts\python.exe -m app.cli demo-report --drug aspirin --out-dir reports` - wrote `reports/demo-aspirin-briefing.md` and `reports/demo-aspirin-audit.json`.
- `git status --short --ignored reports` - generated report and audit artifacts remained ignored.

### Commit summary
- Phase 1.5 prepared as an uncommitted working tree on `phase-1-pipeline-evals`.
- Scope stayed limited to eval coverage, test coverage, and reviewer/status documentation.

### Product boundaries
- No diagnosis, dosage recommendation, start/stop advice, real patient data, FASTQ/BAM/WGS support, SaaS/auth/payments, Telegram, blockchain, cloud raw genotype upload, or new clinical claims beyond the demo evidence pack were added.
- Safety policy and eval boundaries were strengthened, not weakened.

### Next safe step
- Run the full Phase 1.5 validation sequence, confirm generated reports remain ignored, inspect `git diff --stat`, and only then decide whether to commit.

## 2026-06-28 - Phase 1.6 GitHub + Grant Readiness Pack

### Changed
- Created branch `phase-1-github-grant-readiness` from clean Phase 1.5 state.
- Polished `README.md` for fast reviewer understanding:
  - one-liner;
  - current status;
  - what it is / is not;
  - local-first rationale;
  - text architecture;
  - quickstart;
  - CLI demo commands;
  - web demo routes;
  - eval metrics;
  - safety boundaries;
  - roadmap;
  - grant alignment;
  - link to project status.
- Added Apache-2.0 `LICENSE`.
- Added `CONTRIBUTING.md` with contribution boundaries, validation commands, evidence-pack rules, and no-real-patient-data policy.
- Added `SECURITY.md` with no-sensitive-data policy, maintainer responsible-disclosure contact, local-first privacy model, secret handling, generated reports policy, and medical safety boundary.
- Added `docs/grant_application_pack.md` for grant reviewers.
- Rewrote `docs/roadmap.md` as a conservative roadmap:
  - Phase 2 evidence-pack tooling and better pipeline evals;
  - Phase 3 clinician-review workspace and structured export;
  - Phase 4 optional confidential compute adapter research.
- Added `docs/release_checklist.md`.
- Added `docs/screenshots.md` with exact local pages and captions.
- Updated `docs/project_status.md`, `CHECKPOINT.md`, and this session log for Phase 1.6.

### Files changed
- `README.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `docs/grant_application_pack.md`
- `docs/roadmap.md`
- `docs/release_checklist.md`
- `docs/screenshots.md`
- `docs/project_status.md`
- `CHECKPOINT.md`
- `SESSION_NOTES.md`

### Validation
- `.venv\Scripts\python.exe -m pytest` - 34 passed.
- `.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 29 source files.
- `.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- Eval runner metrics: `total_cases=12`, `static_text_cases=7`, `pipeline_cases=5`, `unsafe_advice_rate=0.0`, `missing_source_rate=0.0`, `uncertainty_missing_rate=0.0`, `audit_missing_rate=0.0`, `pipeline_failure_rate=0.0`.
- `.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports` - wrote `reports/demo-sertraline-briefing.md` and `reports/demo-sertraline-audit.json`.
- `.venv\Scripts\python.exe -m app.cli demo-report --drug aspirin --out-dir reports` - wrote `reports/demo-aspirin-briefing.md` and `reports/demo-aspirin-audit.json`.
- `git status --short --ignored reports` - generated report and audit artifacts remained ignored.

### Product boundaries
- No diagnosis, dosage recommendation, start/stop advice, real patient data, FASTQ/BAM/WGS support, SaaS/auth/payments, Telegram, blockchain, cloud raw genotype upload, new clinical claims, medical functionality, or weakened safety/evals were added.

### Next safe step
- Run the full Phase 1.6 validation sequence, confirm generated reports remain ignored, inspect `git diff --stat`, and decide whether to commit.

## 2026-06-28 - Phase 1.8 Grant Submission Answers Pack

### Changed
- Added `docs/grant_submission_answers.md` with copy-paste-ready Sentient/public-goods grant answers:
  - project title;
  - one-sentence pitch;
  - short and long summaries;
  - problem and solution;
  - open-source and local-first rationale;
  - beneficiaries;
  - built-so-far status;
  - technical architecture;
  - safety model;
  - eval/audit model;
  - grant alignment;
  - support needs;
  - 30/60/90-day milestones;
  - risks and mitigations;
  - non-goals;
  - repository/demo instructions;
  - final short blurb.
- Added `docs/grant_short_pitch.md` with 15-second, 30-second, and 60-second pitch variants plus reviewer, technical, and safety summaries.
- Added `docs/grant_milestones.md` with conservative Month 1, Month 2, and Month 3 milestones.
- Added application wording guardrails to the grant docs.
- Updated `docs/grant_application_pack.md` to link the new submission docs and include wording guardrails.
- Updated `docs/project_status.md`, `CHECKPOINT.md`, and this session log for Phase 1.8.

### Files changed
- `docs/grant_submission_answers.md`
- `docs/grant_short_pitch.md`
- `docs/grant_milestones.md`
- `docs/grant_application_pack.md`
- `docs/project_status.md`
- `CHECKPOINT.md`
- `SESSION_NOTES.md`

### Validation
- `.venv\Scripts\python.exe -m pytest` - 34 passed.
- `.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 29 source files.
- `.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- Eval runner metrics: `total_cases=12`, `static_text_cases=7`, `pipeline_cases=5`, `unsafe_advice_rate=0.0`, `missing_source_rate=0.0`, `uncertainty_missing_rate=0.0`, `audit_missing_rate=0.0`, `pipeline_failure_rate=0.0`.

### Product boundaries
- No diagnosis, dosage recommendation, start/stop advice, real patient data, real genetic data, FASTQ/BAM/WGS support, AlphaMissense clinical interpretation, SaaS/auth/payments, Telegram, blockchain, cloud raw genotype upload, new clinical claims, medical functionality, or weakened safety/evals were added.

### Next safe step
- Run Phase 1.8 validation, confirm generated reports remain ignored, inspect `git diff --stat`, and decide whether to commit.

## 2026-06-29 - Phase 1.9 Visual Demo Assets Pack

### Changed
- Created branch `phase-1-demo-assets` from clean `phase-1-github-grant-readiness` state.
- Captured local web demo screenshots from `http://127.0.0.1:8000/` using synthetic/demo data only:
  - `docs/assets/screenshots/landing.png`;
  - `docs/assets/screenshots/demo.png`;
  - `docs/assets/screenshots/sertraline-report.png`;
  - `docs/assets/screenshots/aspirin-safe-no-claim.png`.
- Added `docs/demo_video_script.md` with a 90-120 second reviewer/grant demo script.
- Updated `docs/screenshots.md` with file paths, captions, proof points, and manual capture fallback.
- Updated `README.md` with a visual demo section.
- Updated grant/status docs to reference the visual assets without changing the product pitch or scope.
- Fixed the report-view subtitle from hardcoded "sertraline demo" wording to neutral "Medication-to-Doctor Briefing demo" wording.
- Refreshed the sertraline and aspirin report screenshots after the subtitle fix.

### Validation
- `.\.venv\Scripts\python.exe -m pytest` - 35 passed.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 29 source files.
- `.\.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- Eval runner metrics: `total_cases=12`, `static_text_cases=7`, `pipeline_cases=5`, `unsafe_advice_rate=0.0`, `missing_source_rate=0.0`, `uncertainty_missing_rate=0.0`, `audit_missing_rate=0.0`, `pipeline_failure_rate=0.0`.
- Focused regression check after the subtitle fix: `.\.venv\Scripts\python.exe -m pytest tests\test_api.py -k neutral_demo_subtitle` - passed.

### Product boundaries
- No diagnosis, dosage recommendation, start/stop advice, real patient data, real genetic data, FASTQ/BAM/WGS support, SaaS/auth/payments, Telegram, blockchain, cloud raw genotype upload, new clinical claims, medical functionality, or weakened safety/evals were added.

### Next safe step
- Run validation, confirm generated reports remain ignored, inspect `git diff --stat`, and decide whether to commit the visual demo assets pack.

## 2026-06-29 - Final submission documentation drift cleanup

### Changed
- Synced `README.md` current status to final submission-ready packaging.
- Updated the visible latest commit to `97bb70f docs: add final submission checklist`.
- Updated the validation baseline to 35 tests, ruff, mypy, and evals runner 12 passed / 0 failed.
- Added direct README links for final grant/reviewer materials:
  - `docs/final_submission_checklist.md`;
  - `docs/grant_submission_answers.md`;
  - `docs/grant_short_pitch.md`;
  - `docs/grant_milestones.md`;
  - `docs/demo_video_script.md`;
  - `docs/screenshots.md`.
- Synced `docs/project_status.md` to the public branch `phase-1-github-grant-readiness` and included commits through `97bb70f`.
- Updated `CHECKPOINT.md` to record this as documentation drift cleanup.

### Product boundaries
- Documentation-only cleanup.
- No product features were added.
- No runtime behavior changed.
- No medical logic, safety policy, evidence rules, eval logic, or generated-report behavior changed.

### Validation
- `.\.venv\Scripts\python.exe -m pytest` - 35 passed.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 29 source files.
- `.\.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.

## 2026-06-29 - Final public GitHub polish

### Changed
- Updated `README.md` to show latest pushed commit `2a1b539 docs: sync final submission status`.
- Added a compact reviewer-links block near the top of `README.md`.
- Updated `docs/project_status.md` to include `2a1b539` and keep current state as final submission-ready packaging.
- Updated `docs/final_submission_checklist.md` with the recommended final public default branch: `main`, created from `phase-1-github-grant-readiness`.
- Updated `CHECKPOINT.md` to record this as final public GitHub polish.

### Product boundaries
- Documentation-only public polish.
- No runtime behavior changed.
- No product scope changed.
- No medical logic, evidence rules, safety policy, eval logic, clinical claims, real patient data, real genetic data, or cloud raw genotype upload changed.

### Validation
- `.\.venv\Scripts\python.exe -m pytest` - 35 passed.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 29 source files.
- `.\.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.

## 2026-06-29 - Set main as final public branch

### Changed
- Created `main` from `phase-1-github-grant-readiness`.
- Pushed `main` to GitHub.
- Set GitHub default branch to `main`.
- Added repository topics through `gh`.
- Updated public docs on `main` so README and project status name `main` as the public default branch.
- Kept `phase-1-github-grant-readiness` as the historical submission branch.

### Product boundaries
- Documentation and GitHub repository metadata only.
- No runtime behavior changed.
- No product scope changed.
- No medical logic, evidence rules, safety policy, eval logic, clinical claims, real patient data, real genetic data, or cloud raw genotype upload changed.

### Validation
- `.\.venv\Scripts\python.exe -m pytest` - 35 passed.
- `.\.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.

## 2026-07-02 - Genome Expansion Plan scope lock

- Added docs/genome_expansion_plan.md.
- Recorded approved direction for the future Genome Trust Console extension.
- Kept the task documentation-only.
- No runtime changes.
- No safety boundary changes.
- No tests/evals changed.
- No dependencies changed.
- Next recommended phase: G1 genome_profile schemas + demo evidence pack.

## 2026-07-02 - Open Care Master Plan integration

- Added docs/master_plan.md.
- Added docs/reference_landscape.md.
- Reframed product as a privacy-first, agent-ready personal medical & genomics workspace.
- Corrected implementation order to vault-first.
- Moved Genome Expansion after Health/Family Vault foundations.
- Kept task documentation-only.
- No runtime changes.
- No safety boundary changes.
- No tests/evals changed.
- No dependencies changed.
- Next recommended phase: V1 Health/Family Vault Core schemas + synthetic family demo dataset.

## 2026-07-02 - V1A Health/Family Vault Core

- Added Health/Family Vault Core schemas.
- Added synthetic family demo vault dataset.
- Added loader/validation tests.
- Kept task schema/data-only.
- No UI/API/CLI added.
- No genetics support added.
- Existing PGx flow remains backward-compatible.
- No safety boundary changed.
- Next recommended phase: V1B vault summary/read-model builder + tests.

## 2026-07-02 - V1B Health/Family Vault read model

- Added deterministic Health/Family Vault read-model builder.
- Added provenance-preserving summary structures.
- Added safety boundary notices.
- Added read-model tests.
- Kept task data/read-model only.
- No UI/API/CLI added.
- No LLM generation added.
- No genetics support added.
- Existing PGx flow remains backward-compatible.
- No safety boundary changed.
- Next recommended phase: V1C vault reviewer JSON endpoint or local artifact builder.

## 2026-07-02 - V1C Health/Family Vault local artifacts

- Added deterministic Health/Family Vault local artifact builder.
- Added JSON read-model artifact, Markdown summary artifact, and manifest artifact support.
- Added artifact builder tests.
- Kept task local artifact-only.
- No UI/API/CLI added.
- No LLM generation added.
- No genetics support added.
- Existing PGx flow remains backward-compatible.
- No safety boundary changed.
- Next recommended phase: V1D reviewer-facing vault route or V1D vault docs/demo packaging.

## 2026-07-03 - V1D Health/Family Vault reviewer/demo packaging

- Added V1D Health/Family Vault reviewer/demo packaging.
- Generated committed synthetic demo artifacts from the V1C builder.
- Added Health/Family Vault reviewer demo documentation.
- Updated README/reviewer quickstart with the Health/Family Vault reviewer path.
- No API/CLI/UI added.
- No LLM generation added.
- No genetics support added.
- Existing PGx flow remains backward-compatible.
- No safety boundary changed.
- Next recommended phase: V1E minimal reviewer UI or provenance/threat-model hardening.

## 2026-07-05 - V1E Health/Family Vault provenance and threat-model hardening

### Changed
- Added V1E provenance and threat-model hardening.
- Added `docs/privacy_safety_threat_model.md`.
- Added `docs/provenance_semantics.md`.
- Added `docs/vault_artifact_guarantees.md`.
- Linked the new docs from architecture, reviewer quickstart, Health/Family Vault demo docs, and roadmap.
- Updated checkpoint and session notes for V1E status.

### Product boundaries
- No runtime behavior changed.
- No API/CLI/UI added.
- No LLM generation added.
- No genetics support added.
- No `genome_profile`, VCF/raw genotype, FASTQ, BAM, or WGS support added.
- Existing PGx flow remains backward-compatible.
- No safety boundary changed.
- Next recommended phase: V1F minimal reviewer UI or CI/trust metrics.

### Validation
- `.\.venv\Scripts\python.exe -m pytest` - 74 passed.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 34 source files.
- `.\.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- Eval runner metrics: `total_cases=12`, `static_text_cases=7`, `pipeline_cases=5`, `unsafe_advice_rate=0.0`, `missing_source_rate=0.0`, `uncertainty_missing_rate=0.0`, `audit_missing_rate=0.0`, `pipeline_failure_rate=0.0`.
- Risky-wording scan found risky terms only in boundary, threat, non-goal, disclaimer, or residual-risk contexts.

## 2026-07-05 - V1F CI and trust metrics hardening

### Changed
- Added V1F CI and trust metrics hardening.
- Added `.github/workflows/ci.yml`.
- Added deterministic local trust metrics report in `evals/trust_metrics.py`.
- Added focused trust metrics tests in `tests/test_trust_metrics.py`.
- Updated README, reviewer quickstart, architecture, roadmap, vault artifact guarantees, checkpoint, and session notes for V1F.

### Product boundaries
- No runtime product behavior changed.
- No API/UI/LLM/genetics added.
- No `genome_profile`, VCF/raw genotype, FASTQ, BAM, or WGS support added.
- No dependencies added.
- Existing PGx flow remains backward-compatible.
- No safety boundary changed.
- Trust metrics are automated demo/reviewer trust checks, not clinical validation.
- Next recommended phase: V1G minimal reviewer UI or context/provenance trace graph for vault artifacts.

### Validation
- RED phase: `.\.venv\Scripts\python.exe -m pytest tests\test_trust_metrics.py -q` failed with `ModuleNotFoundError: No module named 'evals.trust_metrics'`.
- GREEN phase: `.\.venv\Scripts\python.exe -m pytest tests\test_trust_metrics.py -q` - 5 passed.
- `.\.venv\Scripts\python.exe -m pytest` - 79 passed.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 35 source files.
- `.\.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- `.\.venv\Scripts\python.exe -m evals.trust_metrics` - printed eval metrics, Health/Family Vault artifact safety flags, safety boundaries, and residual risks.
- Eval runner metrics: `total_cases=12`, `static_text_cases=7`, `pipeline_cases=5`, `unsafe_advice_rate=0.0`, `missing_source_rate=0.0`, `uncertainty_missing_rate=0.0`, `audit_missing_rate=0.0`, `pipeline_failure_rate=0.0`.

## 2026-07-07 - V1G minimal local reviewer UI

### Changed
- Added V1G minimal local reviewer UI.
- Added one read-only FastAPI/Jinja route at `/demo/health-vault`.
- The route loads the synthetic family vault through `load_demo_family_vault()`, builds the deterministic read model through `build_vault_read_model(...)`, reads committed manifest safety flags, and renders a reviewer-focused HTML page.
- Added `app/templates/health_vault.html` for:
  - safety banner;
  - family overview;
  - people;
  - relationships;
  - recorded medications;
  - recorded conditions/concerns;
  - recorded labs;
  - visits/encounters;
  - timeline;
  - question workspace;
  - provenance coverage;
  - artifact/trust flags;
  - explicit "What This Page Does Not Do" boundaries.
- Extended `app/static/styles.css` within the existing style system for dense reviewer layout and mobile-safe section rendering.
- Added focused API regression coverage for the reviewer route in `tests/test_api.py`.
- Updated README, reviewer quickstart, architecture, roadmap, Health/Family Vault demo docs, and checkpoint for the new reviewer route and its boundaries.

### Product boundaries
- No upload or arbitrary file input path added.
- No new JSON API endpoint added.
- No CLI command added.
- No LLM generation added.
- No genetics support added.
- No `genome_profile`, VCF/raw genotype, FASTQ, BAM, or WGS support added.
- Existing PGx flow remains backward-compatible.
- No safety boundary changed.

### Validation
- RED phase: `.\.venv\Scripts\python.exe -m pytest tests\test_api.py -k health_vault_reviewer_page -v` - failed with `404 == 200` before the route existed.
- GREEN phase: `.\.venv\Scripts\python.exe -m pytest tests\test_api.py -v` - 9 passed.
- `.\.venv\Scripts\python.exe -m pytest` - 80 passed.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 35 source files.
- `.\.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- `.\.venv\Scripts\python.exe -m evals.trust_metrics` - printed eval metrics, Health/Family Vault artifact safety flags, safety boundaries, and residual risks.
- Eval runner metrics: `total_cases=12`, `static_text_cases=7`, `pipeline_cases=5`, `unsafe_advice_rate=0.0`, `missing_source_rate=0.0`, `uncertainty_missing_rate=0.0`, `audit_missing_rate=0.0`, `pipeline_failure_rate=0.0`.

### Next safe step
- Validate the local reviewer route over Uvicorn and then move to V1H context/provenance trace graph or V1H final grant packaging refresh without changing the current safety boundaries.

## 2026-07-07 - V1H context/provenance trace graph

### Changed
- Added `app/health_vault/trace_graph.py`.
- Added deterministic `TraceGraph`, `TraceNode`, `TraceEdge`, `TraceGraphRecordRow`, and `TraceGraphSummary` structures.
- Added `build_vault_trace_graph(...)` over the validated Health/Family Vault read-model surface.
- The builder connects recorded demo context to:
  - people;
  - document sources;
  - safety boundary nodes;
  - reviewer artifact nodes.
- Added trace-graph integration to `/demo/health-vault`.
- Added compact reviewer UI output for:
  - graph summary counts;
  - source-linked and missing-source record counts;
  - per-record trace rows for recorded item, person, source, and safety label/category.
- Added focused regression coverage in `tests/test_health_vault_trace_graph.py`.
- Updated README, reviewer quickstart, Health/Family Vault demo docs, architecture, provenance semantics, roadmap, and checkpoint for V1H wording.

### Product boundaries
- No JSON API endpoint added.
- No upload or user input path added.
- No LLM generation added.
- No genetics support added.
- No `genome_profile`, VCF/raw genotype, FASTQ, BAM, or WGS support added.
- No diagnosis, treatment recommendation, dosage guidance, medication selection advice, or start/stop medication advice added.
- Existing PGx flow remains backward-compatible.
- Trace graph is deterministic traceability, not medical interpretation and not clinical validation.

### Validation
- RED phase: `.\.venv\Scripts\python.exe -m pytest tests\test_health_vault_trace_graph.py tests\test_api.py -v` failed with `ModuleNotFoundError: No module named 'app.health_vault.trace_graph'`.
- GREEN phase: `.\.venv\Scripts\python.exe -m pytest tests\test_health_vault_trace_graph.py tests\test_api.py -v` - 16 passed.
- `.\.venv\Scripts\python.exe -m pytest` - 87 passed.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals` - passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` - passed with no issues in 36 source files.
- `.\.venv\Scripts\python.exe -m evals.runner` - 12 passed cases, 0 failed cases.
- `.\.venv\Scripts\python.exe -m evals.trust_metrics` - printed eval metrics, Health/Family Vault artifact safety flags, safety boundaries, and residual risks.
- Eval runner metrics: `total_cases=12`, `static_text_cases=7`, `pipeline_cases=5`, `unsafe_advice_rate=0.0`, `missing_source_rate=0.0`, `uncertainty_missing_rate=0.0`, `audit_missing_rate=0.0`, `pipeline_failure_rate=0.0`.

### Next safe step
- Smoke-check the reviewer route over Uvicorn and then move to V1I final grant packaging refresh or deeper reviewer navigation without changing the current safety boundaries.
