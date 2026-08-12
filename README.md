# OpenCare Proof Kit

OpenCare is an open-source, self-hosted Personal and Family Health Workspace.
This repository is the main OpenCare foundation: it contains a
synthetic/demo Health/Family Vault, persistent Product Core medication and
visit-planning records, reusable trust components, a guarded Question Workspace
precursor, local Actor sessions with explicit Person permissions, a frozen PGx
reference workflow, and reviewer artifacts. Live `/workspace`, `/vault`, and
`/chat` are Person-scoped; synthetic reviewer surfaces remain separate under
`/demo`.

The product rule is simple: vault first, genetics second, LLM third as interface. OpenCare should be useful without DNA. The current implementation is not an AI doctor, not diagnosis, not treatment recommendation, not dosage guidance, and not clinical decision support.

The existing Medication-to-Doctor Briefing / PGx demo remains intact as the narrow reference workflow. Genetics remains a future layer. The LLM remains an interface/explanation layer, not the source of truth.

## Canonical Documents

- [Product direction ADR](docs/adr/0001-opencare-product-direction.md)
- [Current project status](docs/project-status.md)
- [Capability matrix](docs/capability-matrix.md)
- [Changelog](CHANGELOG.md)
- [Private-alpha release notes](docs/releases/v0.1.0-private-alpha.md)
- [Private-alpha operator checklist](docs/private-alpha-operator-checklist.md)
- [Security reporting](SECURITY.md)
- [Product Core roadmap](docs/roadmap/product-core-roadmap.md)
- [Module boundaries](docs/architecture/module-boundaries.md)
- [Family identity ADR](docs/adr/0005-family-identity-access-boundary.md)
- [Family authorization matrix](docs/security/family-access-authorization-matrix.md)
- [Family access threat model](docs/security/family-access-threat-model.md)
- [Agent direction summary](AGENTS.product-direction.md)

`CHECKPOINT.md` and `SESSION_NOTES.md` are historical chronology, not current
status sources. Grant and reviewer documents are supporting evidence, not the
product roadmap.

## Release status

`v0.1.0` is the published controlled private-alpha baseline. Phase 2 Family
Identity and Access Boundary is implemented on the current feature branch and
is not a new release or tag. Neither status is a production-readiness or
clinical-readiness claim.

Production Compose requires explicit persistent Product Core and backup host
paths. Development Compose remains synthetic/demo-only and is not suitable for
sensitive private-alpha data. See the private-alpha operator checklist before
handling any non-synthetic installation data.

## Portable Health-Agent Skill

The current runtime includes two guarded surfaces: the hosted/self-hosted web chat and the
portable skill at [skills/opencare-health-agent](skills/opencare-health-agent/).
The portable skill accepts a redacted context packet, requires structured
source-backed answers, and uses the existing policy and validation rules.

```powershell
.\.venv\Scripts\python.exe -m app.agent.cli export-context --vault-source demo --output context.json
.\.venv\Scripts\python.exe -m app.agent.cli validate-answer --context context.json --answer answer.json
.\.venv\Scripts\python.exe -m app.agent.cli demo-ask --vault-source demo --question "Which medications are recorded?"
```

Installation is manual and workspace-scoped. OpenCare does not automatically
modify agent instruction files or install global skills. There is no MCP,
document ingestion, genetics support, diagnosis, treatment advice, or
dosage-change advice in this phase. External agents remain responsible for
their own model and provider security. OpenCare validates output but cannot
guarantee medical correctness.

## Sentient G1 Trust Envelope

Sentient G1 adds a deterministic, local Trust Envelope at the boundary between
authorized sensitive OpenCare state and a later agent-capable execution
context. It binds one authenticated actor, explicit Person, controlled
purpose/action, minimal evidence and provenance, live authorization snapshot,
safety decision, tools, disclosure constraints, and expiry. G1 does not run an
agent or provider; G2 must reauthorize before execution.

```powershell
.\.venv\Scripts\python.exe -m app.agent_trust.cli export-envelope --demo --person-id person-alice --purpose visit_preparation --action summarize_records --requested-action "Summarize selected records." --evidence-id evidence-medication-alice --tool context.read --tool source.read --output envelope.json
.\.venv\Scripts\python.exe -m app.agent_trust.cli verify-envelope --envelope envelope.json
.\.venv\Scripts\python.exe -m app.agent_trust.cli inspect-envelope --envelope envelope.json
.\.venv\Scripts\python.exe -m app.agent_trust.cli verify-receipt --receipt receipt.json --envelope envelope.json
```

G1 uses canonical UTF-8 JSON and SHA-256 content identity for deterministic
integrity and tamper detection. It does not provide signer authenticity,
digital signatures, PKI, blockchain, remote attestation, or encryption. The
binding contract is
[docs/architecture/sentient-g1-trust-envelope.md](docs/architecture/sentient-g1-trust-envelope.md).

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
- Actor-scoped live vault and Workspace at `/vault` and `/workspace`.
- Actor-scoped chat at `/chat`; the browser sends only the question and the
  server builds context for the authorized active Person.
- Schema v5 Actors, scrypt credentials, Families, relationships, append-only
  consent, assignments, hash-only invitations, and metadata-only access audit.
- Eight-hour server-side sessions in a separate runtime database, same-origin
  checks, and CSRF enforcement for authenticated mutations.
- Fixed owner/caregiver scopes, independent last-owner and last-administrator
  guards, explicit high-risk owner grants, and atomic confirmed Person creation.
- Family/access management UI plus a generic body-only `/invite` flow.
- Deterministic `Context / Provenance Trace Graph` on the reviewer page.
- Privacy/safety threat model, provenance semantics, and artifact guarantee docs.
- GitHub Actions CI for tests, lint, type checks, evals, and trust metrics.
- Deterministic local trust metrics report for reviewer/demo trust checks.
- Production config validation with fail-closed checks for secrets and private mode.
- Public `/health`, `/healthz`, and `/readyz` endpoints for self-hosted checks.
- Legacy password-gated private mode for non-Actor routes; its cookie never
  substitutes for an Actor session or Person assignment.
- Configurable runtime vault source through `OPENCARE_VAULT_SOURCE=demo|local_file`.
- Mounted local vault file support through `OPENCARE_VAULT_FILE=/path/to/vault.json`.
- Product Core SQLite persistence through `OPENCARE_PRODUCT_DB_PATH`.
- Runtime-only session storage through `OPENCARE_SESSION_DB_PATH`, outside
  Product Core backup and recovery.
- Immutable Product Core source files through `OPENCARE_SOURCE_DIR`.
- Deterministic medication lifecycle, persistent Visits and Visit Questions,
  persisted Visit Briefs, and deterministic Person export v2 under
  `app/product_core/`.
- Versioned Product Core JSON API under `/api/product-core/v1` for source
registration, candidate review, canonical medications, timeline, Visits, Visit
Questions, Visit Brief generation, and portable vault export.
- Dockerfile, compose foundation, and deployment guide for self-hosted use.
- Single-node VPS deployment pack with production compose, Caddy example, env template, and smoke check script.
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

### Guarded chat workspace

The `/chat` route remains a guarded Question Workspace precursor for
questions about the active Person. A valid Actor session, selected accessible
Person, and `chat.use` scope are required. The browser sends a question only;
OpenCare resolves Product Core context server-side, applies an intent policy,
obtains either a
deterministic demo response or an optional external response, and validates the
completed structure before display. Chat messages stay in page memory and are
not persisted.

The default is `OPENCARE_AGENT_MODE=demo`. It supports questions about clinician preparation, changes in the recorded timeline, source-backed information, and missing information. It does not diagnose, recommend treatment, select medication, calculate or modify a dose, or interpret genetics. Recorded medication or dosage context may be shown only when it is already source-backed in the vault.

Set `OPENCARE_AGENT_MODE=openai_responses` only with `OPENCARE_AGENT_ALLOW_EXTERNAL_LLM=true`, `OPENCARE_LLM_RESPONSES_URL`, `OPENCARE_LLM_API_KEY`, and `OPENCARE_LLM_MODEL`. `OPENCARE_LLM_RESPONSES_URL` is the complete HTTP(S) endpoint, such as `https://api.example.com/v1/responses`; it must not include credentials, a query string, or a fragment. Production operators should use HTTPS. In this mode, compact vault context leaves the OpenCare server for the operator-configured external endpoint. The UI does not reveal the endpoint, key, or model details.

Responses are buffered, policy-checked, source-validated, and fail closed when validation fails. This reduces unsupported output, but it cannot guarantee medical correctness or clinical safety.

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

It is the live Actor-scoped Product Core vault for the active Person. It never
falls back to demo or mounted reviewer JSON. The synthetic read-only vault
remains at `/demo/health-vault`.

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
python -m pip install -c constraints/python312.txt -e ".[dev]"
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints/python312.txt -e ".[dev]"
```

`pyproject.toml` declares direct dependencies. `constraints/python312.txt`
reproduces the validated CPython 3.12 runtime and test environment. Regenerate
the constraints and run the full validation suite whenever dependencies change.
Pip build isolation resolves the declared build backend separately, so this does
not claim byte-for-byte reproducible wheels.

Core validation:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.trust_metrics
git diff --check
```

Product Core migration smoke test:

```powershell
.\.venv\Scripts\python.exe -c "from app.config import get_settings; from app.product_core.sqlite import SQLiteDatabase; s=get_settings(); SQLiteDatabase(s.product_db_path).migrate()"
```

Product Core persists medication lifecycle records, active people profiles,
Visits, user-authored Visit Questions, and schema v5 Family identity/access
state. The API uses the same
SQLite metadata and immutable UTF-8 source payloads configured through
`OPENCARE_PRODUCT_DB_PATH` and `OPENCARE_SOURCE_DIR`. Migrations run during
application startup. The API has persisted active people profiles; legacy opaque
person IDs are retained through non-medical `Imported profile` placeholders during
migration. The outer shared password gate is not Person authorization: every
live Product Core request resolves the Actor session, resource owner, and fixed
scope server-side.

Family identity and access endpoints use `/api/family-access/v1`. They cover
bootstrap, login/logout, password replacement, current Actor and active Person,
explicit Person creation, Actor deactivation, Families, memberships,
relationships, assignments, consent/audit views, and body-only invitations.
See the [authorization matrix](docs/security/family-access-authorization-matrix.md).

Product Core API lifecycle endpoints include:

```txt
POST /api/product-core/v1/sources/manual-medication
POST /api/product-core/v1/sources/plain-text
POST /api/product-core/v1/candidates/medications
POST /api/product-core/v1/candidates/{candidate_id}/confirm
POST /api/product-core/v1/candidates/{candidate_id}/correct
POST /api/product-core/v1/candidates/{candidate_id}/reject
POST /api/product-core/v1/people/{person_id}/vault-export
POST /api/product-core/v1/people
GET  /api/product-core/v1/people
GET  /api/product-core/v1/people/{person_id}
PATCH /api/product-core/v1/people/{person_id}
GET  /api/product-core/v1/people/{person_id}/medications
GET  /api/product-core/v1/people/{person_id}/timeline
POST /api/product-core/v1/people/{person_id}/visit-briefs:generate
POST /api/product-core/v1/visits
GET /api/product-core/v1/people/{person_id}/visits
GET/PATCH /api/product-core/v1/visits/{visit_id}
POST/GET /api/product-core/v1/visits/{visit_id}/questions
PATCH/DELETE /api/product-core/v1/visit-questions/{question_id}
```

The API returns stable safe error envelopes for Product Core routes only.
Review timestamps are server-controlled; `VisitBrief.generated_at` is the
only client-supplied generation timestamp. No source-content download,
extraction, provider call, or clinical/advisory behavior is exposed.

## Installation backup and recovery

Phase 1F adds operator-only local plaintext backup, offline verification, and
fail-closed recovery. It is not an HTTP route, Workspace feature, import, or
merge mechanism. A backup contains a SQLite snapshot and every persisted
immutable Source payload; treat its directory as sensitive health data.

```powershell
.\.venv\Scripts\python.exe -m app.product_core.backup_cli backup --database <sqlite> --source-dir <sources> --destination <new-backup-directory>
.\.venv\Scripts\python.exe -m app.product_core.backup_cli verify --backup <backup-directory>
.\.venv\Scripts\python.exe -m app.product_core.backup_cli preflight --backup <backup-directory> --target-root <installation-root>
.\.venv\Scripts\python.exe -m app.product_core.backup_cli recover --backup <backup-directory> --target-root <installation-root> --confirm-maintenance
```

`backup` may use `OPENCARE_PRODUCT_DB_PATH` and `OPENCARE_SOURCE_DIR` when the
two path options are omitted. `verify`, `preflight`, and `recover` use only
their explicit paths and never load runtime defaults. Recovery requires an
absent or real empty target and `--confirm-maintenance`; this acknowledges that
no OpenCare process uses the target, which the CLI cannot prove. It stages,
verifies, atomically activates, verifies again, and rolls back handled failures.
It cannot guarantee crash- or power-loss safety between filesystem operations;
exact abandoned recovery artifacts block subsequent recovery until inspected.

Recovery restores durable Actor credentials and the complete v5 access state,
including revocations. It restores neither `.env`, plaintext passwords,
invitation codes, `OPENCARE_SECRET_KEY`, provider keys, cookies, sessions, TLS
files, nor deployment configuration. Every Actor logs in again and creates a
new runtime session. Import, merge, encryption, and populated-target recovery
remain unsupported.

Start the local app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

On a fresh schema v5 installation, open `/bootstrap` while no Actor exists.
Bootstrap creates the first local Actor and installation administrator; it
grants no implicit Person access. Any selected existing Person becomes an owner
grant only after the explicit full-access confirmation. Later sessions start at
`/login`. Creating a Person requires the visible
`confirm_owner_assignment: true` confirmation and atomically assigns the
creating Actor as owner. Invitation codes are entered only on the generic
`/invite` form and never belong in a link.

Open:

```txt
http://127.0.0.1:8000/
http://127.0.0.1:8000/login
http://127.0.0.1:8000/bootstrap
http://127.0.0.1:8000/invite
http://127.0.0.1:8000/family-access
http://127.0.0.1:8000/demo
http://127.0.0.1:8000/demo/health-vault
http://127.0.0.1:8000/vault
http://127.0.0.1:8000/healthz
http://127.0.0.1:8000/readyz
http://127.0.0.1:8000/demo/report-view?drug=sertraline
http://127.0.0.1:8000/demo/report-view?drug=aspirin
```

## Deployment

OpenCare now includes a minimal self-hosted deployment foundation plus one documented production path.

- Development mode stays easy with `OPENCARE_ENV=development`.
- Production mode requires `OPENCARE_SECRET_KEY`.
- Private production mode also requires `OPENCARE_ACCESS_PASSWORD`.
- Non-health routes can be password-gated when `OPENCARE_DEMO_MODE=false`.
- Vault runtime source is selected with `OPENCARE_VAULT_SOURCE=demo|local_file`.
- Local-file mode requires `OPENCARE_VAULT_FILE` and should use a read-only host mount.
- The private password form is served at `/access`.
- Health checks stay public at `/health`, `/healthz`, and `/readyz`.
- The validated remote deployment path is single-node VPS + Docker Compose + Caddy + TLS.
- The deployment smoke check script is `scripts/smoke_check.py`.
- Production Compose persists Product Core SQLite and immutable source payloads through
  required `OPENCARE_PRODUCT_DATA_DIR` and `OPENCARE_BACKUP_DIR` host bind mounts.
- Production Compose keeps `OPENCARE_SESSION_DB_PATH` on restrictive
  non-persistent `/run/opencare` tmpfs with no session backup volume.

See [docs/deployment.md](docs/deployment.md) for:

- local run;
- Docker run;
- `docker compose` run;
- demo source vs local-file source;
- production env vars;
- private gate behavior;
- local vault template and mount pattern;
- security boundaries for this self-hosted MVP.

See [docs/production_deployment.md](docs/production_deployment.md) for the validated single-node VPS path:

- `docker-compose.prod.yml`;
- `deploy/Caddyfile.example`;
- `deploy/env.production.example`;
- Caddy reverse proxy/TLS flow;
- `scripts/smoke_check.py`;
- persistent Product Core storage, backup destination, and recovery boundaries.

## Validation And Trust Metrics

GitHub Actions CI runs:

- `python -m pytest`
- `python -m ruff check app tests evals`
- `python -m mypy app evals`
- `python -m evals.runner`
- `python -m evals.trust_metrics`

The full validation job runs on Linux CPython 3.12. A focused credential job
also runs the scrypt/session security tests on Windows and Linux CPython 3.12
without weakening `N=2^15`, `r=8`, or `p=1`.

Local trust metrics combine eval totals with Health/Family Vault manifest safety flags and the generated-report ignore check. They are automated reviewer/demo trust checks, not clinical validation.

The current command results are recorded in
[docs/project-status.md](docs/project-status.md) and must be refreshed by
running the commands rather than copied as permanent version claims.

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
app/family_access local Actors, credentials, sessions, Family, consent, policy, invitations
app/product_core durable Person/Medication/Visit lifecycle, access enforcement, export/recovery
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

See [docs/roadmap/product-core-roadmap.md](docs/roadmap/product-core-roadmap.md)
for the canonical next-phase roadmap. The older
[docs/roadmap.md](docs/roadmap.md) is historical.
# Visit Preparation Workspace

`/workspace` is the primary OpenCare entry point and `/` redirects there. It uses the
versioned Product Core API for manual medication entry, review, confirmed records,
the Product Core timeline, persistent Visits and user-authored Visit Questions,
and Visit-scoped persisted Brief revisions with confirmed-evidence selection,
editable preparation notes, history/restore, Markdown copy/download, and an
explicit Person-scoped portable vault download. The
legacy deterministic Person-scoped Brief endpoint remains available. Profiles
and selected Visits remain only in page memory; the active Person selection is
held in the server-side Actor session.
Legacy opaque person IDs migrate to `Imported profile` records without inferred data.
`/chat` remains a supporting feature behind the same Actor and Person policy.
Family/access management and Actor deactivation are implemented. Person
deletion, uploads, extraction, OCR, and Phase 3 ingest remain out of scope.
