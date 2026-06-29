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
