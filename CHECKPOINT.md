# CHECKPOINT.md

## Project

OpenCare Proof Kit

## Current product version

v0.1 bootstrap / Codex-ready starter repo.

## Current phase

V1H context/provenance trace graph

## Current status

The public default branch is `main`, created from `phase-1-github-grant-readiness`. The historical submission branch remains pushed. The current implementation step adds V1H deterministic context/provenance trace graph for the synthetic Health/Family Vault layer.

- Master Plan added as current product direction.
- Implementation order corrected to vault-first.
- Genome Expansion remains valid but moved after Health/Family Vault foundations.
- V1A Health/Family Vault Core schemas and synthetic family demo dataset added.
- V1B Health/Family Vault read-model builder added.
- New code creates deterministic summaries from validated synthetic vault data.
- V1C Health/Family Vault local artifact builder added.
- New code creates deterministic local JSON/Markdown/manifest artifacts from validated synthetic vault read-model data.
- V1D Health/Family Vault reviewer/demo packaging added.
- Synthetic demo artifacts generated from the V1C builder.
- V1E Health/Family Vault provenance and threat-model hardening added.
- Privacy/safety threat model added.
- Provenance semantics added.
- Vault artifact guarantees added.
- V1F CI and trust metrics hardening added.
- GitHub Actions CI added for tests, lint, type checks, evals, and trust metrics.
- Deterministic local trust metrics report added.
- V1G minimal local reviewer UI added.
- One read-only local route added for the Health/Family Vault reviewer page.
- V1H deterministic context/provenance trace graph added.
- New deterministic `app/health_vault/trace_graph.py` builder added.
- README/reviewer quickstart updated.
- No LLM generation added.
- No genetics support added.
- Existing PGx flow remains backward-compatible.
- No safety boundaries changed.
- No upload or JSON API surface added for the reviewer page.
- Next recommended phase: V1I final grant packaging refresh or deeper reviewer navigation.

## Last validated state

V1H context/provenance trace graph validation baseline:

- pytest: 87 passed;
- ruff: passed;
- mypy: passed with no issues in 36 source files;
- eval runner: 12 passed cases, 0 failed cases;
- eval runner metrics: `total_cases=12`, `static_text_cases=7`, `pipeline_cases=5`, `pipeline_failure_rate=0.0`;
- trust metrics: printed eval metrics, Health/Family Vault artifact safety flags, safety boundaries, and residual risks;
- Health/Family Vault reviewer route test: passed through `GET /demo/health-vault`;
- Health/Family Vault Core focused tests: 16 passed;
- Health/Family Vault read-model focused tests: 16 passed;
- Health/Family Vault artifact focused tests: 7 passed;
- Health/Family Vault trace-graph focused tests: 7 passed;
- existing PGx briefing regression still passed through `build_demo_briefing("sertraline")`;
- no upload route, no new JSON API, no CLI, no LLM generation, and no genetics support were added for the reviewer page or trace graph.

## Product definition

OpenCare Proof Kit is an open-source, local-first toolkit for private, evidence-grounded health AI agents.

The first reference workflow is Medication-to-Doctor Briefing: generating a clinician-reviewable briefing from demo/synthetic health vault data, genotype/VCF-like data, local evidence packs, deterministic rules, safety policy, and LLM/report writing.

This project is not an AI doctor, not a diagnostic system, and not a medication recommendation engine.

## Grant direction

Target: Sentient Foundation open-source AI grant.

Positioning:

- open-source infrastructure;
- local-first;
- private by default;
- empowering and public-good oriented;
- reusable evidence/safety/audit layer for health AI agents.

## Current repo capabilities

- Load a synthetic demo health vault.
- Parse demo genotype-like data.
- Load a local demo evidence pack.
- Match deterministic PGx rules for the sertraline reference workflow.
- Summarize demo evidence-pack coverage for supported and unsupported drug queries.
- Render a clinician-reviewable Markdown briefing.
- Run safety policy checks.
- Produce JSON audit metadata with report ID, app version, pipeline steps, evidence pack version, policy status, raw-export status, and demo coverage status.
- Run static-text guardrail evals and pipeline-backed evals against the real local demo pipeline.
- Generate report/audit files from the CLI.
- Serve minimal landing/demo/report HTML pages from FastAPI.
- Serve report/audit data from FastAPI.
- Run unit tests, lint checks, strict typing checks, and synthetic evals.
- Provide GitHub/grant readiness docs for license, contribution rules, security reporting, release checks, screenshots, roadmap, and grant review.
- Provide grant submission docs with copy-paste answers, short pitches, conservative milestones, and wording guardrails.
- Provide visual demo screenshots and a 90-120 second reviewer/grant demo video script.
- Load and validate a synthetic Health/Family Vault Core demo dataset with people, family relationships, medical context, document sources, provenance links, timeline events, and question threads.
- Build deterministic Health/Family Vault read models with family/person summaries, per-person record groups, sorted timeline, question threads, provenance coverage, and safety boundary notices.
- Build deterministic Health/Family Vault local artifacts with JSON read-model output, Markdown summary output, and manifest metadata.
- Provide committed synthetic Health/Family Vault reviewer artifacts and documentation under `docs/assets/health_vault/` and `docs/health_family_vault_demo.md`.
- Serve a local read-only Health/Family Vault reviewer page from FastAPI.
- Build a deterministic context/provenance trace graph over Health/Family Vault reviewer data.
- Run deterministic local trust metrics for eval totals, Health/Family Vault manifest safety flags, generated-report ignore expectation, and residual risks.

## Hard boundaries

Do not implement without explicit approval:

- diagnosis;
- dosage recommendation;
- start/stop medication advice;
- real patient data;
- FASTQ/BAM/WGS pipeline;
- AlphaMissense as clinical decision layer;
- SaaS/auth/payments;
- Telegram interface;
- blockchain;
- cloud raw genotype upload by default.

## MVP modules

```txt
app/vault       health vault schema/load/validate
app/health_vault family/person medical vault schemas, validation, demo loader, and read model
app/genetics    genotype/VCF-like parser
app/evidence    evidence pack schema/loader
app/pgx         rule matcher
app/safety      policy engine
app/ai          report writer adapter
app/reports     markdown + audit JSON
app/demo_pipeline shared deterministic demo service
app/cli         local demo report/audit generator
evals           synthetic safety/evidence evals
tests           deterministic unit tests
docs            grant/product/architecture/safety/demo docs
```

## Required commands

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
python -m evals.trust_metrics
python -m app.cli demo-report --drug sertraline --out-dir reports
python -m app.cli demo-report --drug aspirin --out-dir reports
uvicorn app.main:app --reload
```

## First implementation milestone

A local deterministic CLI/web pipeline:

```txt
demo patient
  -> genotype parser
  -> evidence pack matcher
  -> safety policy
  -> Markdown report
  -> audit JSON
  -> eval runner
```

## Completion criteria for milestone 1

Expected:

- tests pass;
- evals pass;
- generated report contains sources, limitations, safety note, clinician questions, and audit metadata;
- generated audit records policy status and raw-export status;
- API exposes report and audit endpoints;
- FastAPI exposes landing, demo, report-view, and reviewer quickstart browser paths;
- unsupported drugs return a safe no-claim report with `coverage_status=drug_not_in_demo_pack`;
- no medical advice or dosage recommendation;
- reviewer docs are clear enough to run the demo locally;
- SESSION_NOTES.md updated.

## Current next step

Keep `main` as the public reviewer branch. Do not delete old branches or force-push. The next recommended implementation phase after V1H validation is V1I final grant packaging refresh or deeper reviewer navigation without changing safety boundaries.
