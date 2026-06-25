# SESSION_NOTES.md

This file records what actually happened in each work session.

It is not a roadmap. It is the operational memory for future Codex sessions.

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
