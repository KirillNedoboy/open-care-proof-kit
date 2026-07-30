# OpenCare Current Project Status

This is the canonical description of the repository as inspected on
2026-07-30. Historical chronology remains in `CHECKPOINT.md` and
`SESSION_NOTES.md`; those files are not current status sources.

## Repository snapshot

- Branch: `codex/opencare-product-integration`
- Inspected starting commit: `296a6d8daa7b399224995507387f85ffeb8348f1`
- Inspection date: 2026-07-30
- Starting working tree: clean
- Current repository: OpenCare foundation with demo/reference and trust
  components, not a complete editable Personal and Family Health Workspace.

## Runtime routes

Verified in `app/main.py`:

- `GET /` redirects to `/workspace`.
- `GET /chat` renders the guarded chat workspace.
- `POST /api/chat` accepts a bounded same-origin JSON question and returns a
  validated structured answer.
- `GET /access` and `POST /access` implement the optional private access gate.
- `GET /demo` renders the existing synthetic patient/demo surface.
- `GET /demo/health-vault` renders the synthetic read-only reviewer page.
- `GET /vault` renders the active configured vault in read-only mode.
- `GET /reviewer-quickstart` serves reviewer documentation.
- `GET /demo/report-view`, `/demo/report`, `/demo/report.md`, and
  `/demo/audit` expose the PGx briefing reference outputs.
- `GET /health`, `/healthz`, and `/readyz` expose health/readiness checks.

## Implemented capabilities

- Pydantic Health/Family Vault schemas, validation, deterministic read model,
  artifacts, and trace graph in `app/health_vault/`.
- Synthetic family dataset in `data/demo_patients/demo_family_vault.json`.
- Read-only reviewer and active-vault HTML surfaces in `app/main.py` and
  `app/templates/health_vault.html`.
- Guarded chat policy, deterministic demo provider, answer validation,
  metadata-only audit, portable context export, and answer validation in
  `app/agent/`.
- Deterministic citation, safety, report, audit, evaluation, and trust-check
  components in `app/agent/`, `app/safety/`, `app/reports/`, and `evals/`.
- Product Core medication lifecycle in `app/product_core/`: SQLite
  migrations, immutable source storage, candidate review, canonical records,
  timeline events, and deterministic Visit Brief output.
- Persistent Product Core Visits and user-authored Visit Questions with versioned
  API and workspace controls. Questions are scoped to one Visit and use explicit
  ordering; generated answers are not stored.
- Versioned Product Core JSON API under `/api/product-core/v1`, wired through
  the existing FastAPI application with startup migrations and stable scoped
  error responses.
- Person-scoped portable vault ZIP export with canonical `vault.json`, checksum
  manifest, reachable immutable sources, Brief-integrity verification, and a
  Workspace warning before download. It creates no persistent export artifact.
- Operator-only Product Core backup/recovery CLI that creates a staged
  SQLite/source snapshot with canonical manifest and `COMPLETE` marker,
  verifies supplied backups offline, preflights explicit targets read-only, and
  fail-closed recovers only to absent or empty installation roots. Backups are
  sensitive plaintext artifacts.
- Existing synthetic PGx briefing reference workflow in `app/demo_pipeline.py`,
  `app/pgx/`, `app/genetics/`, and `data/evidence_packs/`.

See [the capability matrix](capability-matrix.md) for status by capability and
repository evidence paths.

## Partial capabilities

- Local JSON vault loading supports demo data and an operator-supplied
  `OPENCARE_VAULT_FILE`, but the runtime pages are read-only and there is no
  editable persistence layer.
- External Responses mode exists behind explicit configuration and provider
  validation, but it is optional and not required by the default demo path.
- Product Core has medication lifecycle UI, persisted active people profiles,
  Visits, Visit Questions, and Visit-scoped persisted editable Brief revisions
  with selected confirmed evidence, computed freshness, and audited Markdown
  export. It also has Person-scoped portable export and operator-only
  installation backup verification and empty-target recovery, but no import,
  merge, encryption, per-person authorization, or broader fact types.
- Deployment artifacts cover local Docker and a documented single-node
  Compose/Caddy path; they do not establish production readiness.
- Portable agent support exports redacted context and validates answers; it is
  not a general read-only Product Core tool API.

## Demo-only capabilities

People, family relationships, medications, conditions, labs, visits, timeline
events, questions, sources, and provenance are represented in a synthetic
Health/Family Vault and rendered as read-only context. PGx and genetics code
supports the narrow synthetic Medication-to-Doctor Briefing reference path.

These surfaces are evidence of domain and trust behavior. They are not
editable user-owned records, clinical interpretation, or production medical
support.

## Known gaps

- No canonical lifecycle UI or general editable vault beyond the medication
  API.
- No document upload, extraction, OCR, or general review inbox.
- No non-medication candidate-fact lifecycle.
- No Product Core timeline rebuild command; Phase 1A creates events atomically
  with confirmation.
- No portable import, merge, or populated-installation recovery workflow.
- No family permissions or caregiver authorization.
- No query-scoped AI consent and context preview workflow.

## Safety boundaries

Current code and documentation explicitly prohibit diagnosis, treatment
recommendation, dosage guidance, medication selection advice, start/stop
medication advice, clinical decision support, and claims of clinical
validation. Health/Family Vault summaries are deterministic reorganizations of
recorded context. The repository is synthetic/demo-only by default; local-file
mode accepts operator-supplied JSON but remains read-only in the UI.

## Storage model

The current demo runtime reads structured data from JSON through
`app/health_vault/loader.py`, `app/health_vault/runtime_loader.py`, and
`app/vault/loader.py`. Product Core uses standard-library SQLite
metadata and immutable local source files configured through
`OPENCARE_PRODUCT_DB_PATH` and `OPENCARE_SOURCE_DIR`; FastAPI startup applies
schema migrations through the existing lifespan. Chat content is not
persisted. Generated files under `reports/` remain ignored.

## Deployment model

The repository supports local Uvicorn execution, Docker Compose development,
and a documented single-node VPS path using Docker Compose and Caddy examples.
The runtime has health/readiness endpoints and an optional password gate for
non-health routes. No deployment or infrastructure was changed in this phase.

## Validation executed on 2026-07-31

- `.\.venv\Scripts\python.exe -m pytest` -> `286 passed`.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals` -> passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` -> no issues in `65 source files`.
- Focused backup, recovery, CLI, and source-store tests cover empty-target
  activation, rollback, offline commands, and fail-closed fallback behavior.
- Product Core migration tests -> `7 passed`, including fresh schema version `4`,
  upgrade preservation, rollback, foreign-key enforcement, and concurrent startup.
- `.\.venv\Scripts\python.exe -m evals.runner` -> `14 total, 14 passed, 0 failed`;
  `9` static-text cases and `5` pipeline cases.
- `.\.venv\Scripts\python.exe -m evals.trust_metrics` -> passed; all reported
  eval and artifact safety flags were true/zero as applicable.
- Repository documentation search -> no configured Markdown lint or docs
  validation command found; the search itself returned only references to
  Markdown content and documentation terms.
- `git diff --check` -> passed after documentation edits.
- `node --check app/static/product_core_workspace.js` -> passed.

## Visit Preparation Workspace

`/workspace` is the product entry point for the Product Core flow: manual medication
entry, review (confirm/correct/reject), confirmed records, timeline, persisted Visits,
user-authored Visit Questions, and immutable Visit-scoped Brief revisions with selected
confirmed evidence, preparation notes, restore history and audited Markdown export.
Existing opaque person IDs migrate to active `Imported profile` placeholders with no
inferred name or date of birth. Browser state is not persisted. The shared password gate
protects an installation, not individuals.

## Deferred work

Phase 1E-B persists editable evidence-linked Visit Briefs. Phase 1F implements
Person-scoped portable export, operator-only backup verification, and Phase 1F-C
operator-only `preflight` and `recover` through `InstallationRecoveryService`.
Recovery requires maintenance confirmation, stages and verifies the installation,
activates it atomically, rolls back handled failures, and writes
`RECOVERY_REPORT.json`; it accepts only an absent or empty target. ADR 0004 is
Accepted. Source/evidence drawers, portable import or merge, recovery into a
populated installation or destructive overwrite, encryption or authenticity
signatures, cloud or scheduled backup, HTTP or Workspace recovery, crash or
power-loss guarantees between filesystem operations, identity and caregiver
permissions, family relationships, uploads, OCR, genetics expansion, new
providers, multi-user SaaS, and deployment changes remain deferred.

## Canonical references

- [Direction ADR](adr/0001-opencare-product-direction.md)
- [Capability matrix](capability-matrix.md)
- [Product Core roadmap](roadmap/product-core-roadmap.md)
- [Module boundaries](architecture/module-boundaries.md)
