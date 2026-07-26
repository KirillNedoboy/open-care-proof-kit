# OpenCare Current Project Status

This is the canonical description of the repository as inspected on
2026-07-26. Historical chronology remains in `CHECKPOINT.md` and
`SESSION_NOTES.md`; those files are not current status sources.

## Repository snapshot

- Branch: `codex/opencare-portable-agent-skill`
- Inspected starting commit: `496117fa5b97a7bedb8ce1b1d71750af27523a0a`
- Inspection date: 2026-07-26
- Starting working tree: clean
- Current repository: OpenCare foundation with demo/reference and trust
  components, not a complete editable Personal and Family Health Workspace.

## Runtime routes

Verified in `app/main.py`:

- `GET /` redirects to `/chat`.
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

- No SQLite persistence or migration layer.
- No editable vault or canonical-record workflow.
- No source-file storage for uploaded originals.
- No document upload, extraction, OCR, or review inbox.
- No candidate-fact, correction, confirmation, or rejection lifecycle.
- No Product Core timeline rebuild from canonical records.
- No deterministic Product Core Visit Brief.
- No vault backup/export workflow.
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

The current runtime reads structured data from JSON through
`app/health_vault/loader.py`, `app/health_vault/runtime_loader.py`, and
`app/vault/loader.py`. There is no SQLite database, ORM, migration, or editable
application persistence. Chat content is not persisted. Generated files under
`reports/` remain ignored. The approved future direction is SQLite plus
immutable local source files, with JSON retained for fixtures, import, export,
backup, and migration.

## Deployment model

The repository supports local Uvicorn execution, Docker Compose development,
and a documented single-node VPS path using Docker Compose and Caddy examples.
The runtime has health/readiness endpoints and an optional password gate for
non-health routes. No deployment or infrastructure was changed in this phase.

## Validation executed on 2026-07-26

- `.\.venv\Scripts\python.exe -m pytest` -> `178 passed` in 2.32s.
- `.\.venv\Scripts\python.exe -m ruff check app tests evals` -> passed.
- `.\.venv\Scripts\python.exe -m mypy app evals` -> no issues in `47 source files`.
- `.\.venv\Scripts\python.exe -m evals.runner` -> `14 total, 14 passed, 0 failed`;
  `9` static-text cases and `5` pipeline cases.
- `.\.venv\Scripts\python.exe -m evals.trust_metrics` -> passed; all reported
  eval and artifact safety flags were true/zero as applicable.
- Repository documentation search -> no configured Markdown lint or docs
  validation command found; the search itself returned only references to
  Markdown content and documentation terms.
- `git diff --check` -> passed after documentation edits.

## Deferred work

The next implementation task is the medication-only vertical slice in
[the Product Core roadmap](roadmap/product-core-roadmap.md). SQLite, uploads,
OCR, genetics expansion, new providers, family permissions, multi-user SaaS,
and deployment changes remain deferred.

## Canonical references

- [Direction ADR](adr/0001-opencare-product-direction.md)
- [Capability matrix](capability-matrix.md)
- [Product Core roadmap](roadmap/product-core-roadmap.md)
- [Module boundaries](architecture/module-boundaries.md)
