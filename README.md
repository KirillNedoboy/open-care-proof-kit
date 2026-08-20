# OpenCare Proof Kit

OpenCare is an open-source, self-hosted Personal and Family Health Workspace
plus reusable trust infrastructure for sensitive personal AI agents.

The product sequence is:

```text
vault first
  -> source provenance and human review
  -> Family Workspace
  -> document evidence
  -> bounded AI
  -> Genetics Research Studio
```

OpenCare is useful without DNA. It is not an AI doctor, diagnostic authority,
treatment planner, dosage recommender, medication start/stop authority, clinical
decision-support system, or clinically validated software.

Public repository content, fixtures, tests, screenshots, and reviewer artifacts
are synthetic/de-identified only. A self-hosted runtime is designed to store
user-owned health, document, and genetic data locally behind Person isolation,
provenance, explicit consent, review, and export boundaries.

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
- [Sentient G4 design](docs/architecture/sentient-g4-portable-trust-package.md)
- [Trust Envelope protocol](docs/protocol/opencare-trust-envelope.md)
- [Agent trust integration guide](docs/integrations/agent-trust-integration-guide.md)

`CHECKPOINT.md` and `SESSION_NOTES.md` are historical chronology, not current
status sources. Grant and reviewer documents are supporting evidence, not the
product roadmap.

## Release status

`v0.1.0` and `v0.2.0` are the only published release tags. Public `main`
contains the completed G1-G5, P1, P2, D1, and P3 implementation. The P3-final
implementation baseline was `0937d352cc74a3050609e826baa6bad82f6ac9ee`;
public `main` is mutable. These releases and the current
unreleased development line are not production-readiness or clinical-readiness
claims.
Package/runtime identity is `0.3.0.dev0`, an unreleased development version;
no `v0.3.0` tag exists.

## Current capabilities

- Actor-scoped Family Workspace at `/workspace` with Person isolation.
- Medication, recorded-condition, and lab records with source provenance,
  human review, correction history, timeline, Visits, and Visit Briefs.
- Bounded PDF/TXT evidence-document ingest with immutable Source bytes and
  extraction provenance.
- G1 Trust Envelope, consent-gated G2 runtime, G3 provider portability, G4
  portable trust package, and G5 ecosystem validation.
- Local/self-hosted model portability with explicit external-provider consent.
- Product Core schema v9, Family Access v1/v2 frozen plus v3 document scopes,
  and separate genetics grants: `genetics.read`, `genetics.write`,
  `genetics.research`, `genetics.compare`, `genetics.export`.
- Genetics Workspace at `/genetics`, bounded consumer-genotype import, selective
  indexing, reviewed evidence, PGx associations, family comparison, and
  separate Genetics Export.
- Research Studio Evidence Mode and Explore Mode with epistemic labels,
  counterevidence, citation validation, and no canonical-record mutation path.
- Installation backup/recovery and ordinary Person portable vault export v4.

Development Compose, `/demo/health-vault`, and committed reviewer artifacts are
synthetic/demo surfaces. They are separate from live actor-scoped Product Core.

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
modify agent instruction files or install global skills. There is no MCP.
The portable skill is one bounded agent surface; authenticated Product Core
document ingestion and Genetics Research Studio are available through the
Workspace and versioned APIs. External agents remain responsible for their own
model and provider security. OpenCare validates output but cannot guarantee
medical correctness.

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

## Sentient G2 Consent-Gated Runtime

The repository now registers ten named G2 trust-evaluation fixtures covering
minimal disclosure, exact consent binding and replay refusal, provider/tool
allow-lists, output refusal, receipt/audit linkage, stale recovery,
wrong-Person isolation, TOCTOU refusal, and injection refusal. These are
registration/evaluation fixtures; this note does not claim provider integration
or deployment behavior.

## Sentient G2.5 Optional Compatibility Spike

Sentient G2.5 is an optional spike proving Sentient Chat event compatibility
over the existing G2 consent-gated runtime. It runs synthetic/demo data only:
a fixed demo context (actor-alice / person-alice), a deterministic local
provider, and Sentient event rendering with validated answers and redacted
Execution Receipts. It is a compatibility spike, not a production Sentient
integration.

Requires the optional extra:

```bash
pip install -e ".[sentient]"
```

Development-only demo command (localhost, synthetic data only, never opens the
live Product Core database; non-production):

```bash
python -m app.integrations.sentient.demo
```

Sentient session/request identifiers (`processor_id`, `activity_id`,
`request_id`, `chat_id`) are Sentient correlation IDs, not OpenCare
authorization; no live-vault identity bridge exists yet. See
[docs/integrations/sentient-agent-framework-spike.md](docs/integrations/sentient-agent-framework-spike.md).

## Sentient G4 Portable Trust Package

Sentient G4 packages the G1/G2/G3 trust contract for portable use: a generic
trust layer with a stable public API (`app/agent_trust/api.py`) and zero
OpenCare coupling, a generic `AuthorizationAdapter` Protocol with the OpenCare
adapter in `app/agent/trust_adapter.py`, deterministic JSON Schemas
(`schemas/agent-trust/`, regenerated via `opencare-trust export-schemas`),
synthetic offline fixtures (`fixtures/agent-trust/` — not authorization), and
an `opencare-trust` CLI (also `python -m app.agent_trust.cli`).

G4 also ships an Agent Plugins v1 **skill-only** package at
`agent-plugins/opencare-trust/` (strict 1.0.0 `plugin.json` plus its `skills/`
tree, including the canonical `opencare-health-agent` skill), packaged
deterministically from the canonical skill at [skills/opencare-health-agent](skills/opencare-health-agent/).
The package contains no `mcp.json`: MCP support remains out of scope. G5
validates Agent Skills interoperability; the remaining root Agent Plugins
two-client gate is external evidence pending and machine state remains
`READY_FOR_SECOND_CLIENT_SMOKE`.

```powershell
.\.venv\Scripts\python.exe -m app.agent_trust.cli verify-envelope --envelope fixtures/agent-trust/allowed-envelope.json --at 2027-08-02T10:00:00Z
.\.venv\Scripts\python.exe -m app.agent_trust.cli export-schemas
.\.venv\Scripts\python.exe -m app.agent_trust.cli regenerate-fixtures
```

See the [Trust Envelope protocol](docs/protocol/opencare-trust-envelope.md)
(standalone, no health knowledge required), the
[integration guide](docs/integrations/agent-trust-integration-guide.md) for
downstream adapters, and the
[G4 design](docs/architecture/sentient-g4-portable-trust-package.md).

## Reviewer Quick Links

- Local reviewer route: `/demo/health-vault`
- P2 deterministic reviewer: `.\.venv\Scripts\python.exe -m evals.p2_review`
- P2 reviewer guide: [docs/p2-reviewer-guide.md](docs/p2-reviewer-guide.md)
- Reviewer pack: [docs/final_reviewer_pack.md](docs/final_reviewer_pack.md)
- Reviewer quickstart: [docs/reviewer_quickstart.md](docs/reviewer_quickstart.md)
- Health/Family Vault demo guide: [docs/health_family_vault_demo.md](docs/health_family_vault_demo.md)
- Reviewer summary artifact: [docs/assets/health_vault/family-vault-summary.md](docs/assets/health_vault/family-vault-summary.md)
- Reviewer manifest: [docs/assets/health_vault/family-vault-manifest.json](docs/assets/health_vault/family-vault-manifest.json)
- Threat model: [docs/privacy_safety_threat_model.md](docs/privacy_safety_threat_model.md)
- Provenance semantics: [docs/provenance_semantics.md](docs/provenance_semantics.md)
- Vault artifact guarantees: [docs/vault_artifact_guarantees.md](docs/vault_artifact_guarantees.md)
- P1/P2/D1/P3/G5 reviewers:
  `python -m evals.p1_review`, `python -m evals.p2_review`,
  `python -m evals.d1_review`, `python -m evals.p3_review`,
  `python -m evals.g5_review`
- P3 reviewer guide: [docs/p3-reviewer-guide.md](docs/p3-reviewer-guide.md)

## What Is Implemented Now

- Actor-scoped `/workspace`, `/vault`, `/chat`, `/family-access`, and
  `/genetics` surfaces.
- Product Core schema v9 with Person-scoped Sources, medications, recorded
  conditions, labs, timeline, Visits, Visit Questions, and Visit Briefs
  (content schema v2; v1 revisions readable).
- Immutable PDF/TXT evidence documents with bounded embedded-text extraction,
  page/span provenance, review lifecycle, document grants, export v4, and
  backup/recovery.
- Separate genetics Sources, bounded consumer-genotype import, selective
  indexed observations, evidence packs, reviewed findings, explicit genetics
  grants, PGx lens, family comparison, Research Studio, and Genetics Export.
- G1 Trust Envelope, G2 consent-gated runtime, G2.5 compatibility spike, G3
  provider portability, G4 portable trust package, and G5 ecosystem reviewer.
- Deterministic reviewers and GitHub Actions CI for tests, lint, types, evals,
  trust metrics, and final phase gates.
- Synthetic/demo Health/Family Vault artifacts at `/demo/health-vault`, kept
  separate from live actor-scoped Product Core.

## What OpenCare Is

OpenCare is a privacy-first personal/family health workspace foundation and a
local-first source-grounded trust layer. It is useful before genetics, while
also providing an explicit secondary Genetics Research Studio for authorized
local data. Synthetic public fixtures remain separate from self-hosted runtime
data.

## What OpenCare Is Not

- Not an AI doctor.
- Not diagnosis.
- Not treatment recommendation.
- Not dosage guidance.
- Not medication selection advice.
- Not start/stop medication advice.
- Not clinical decision support.
- Not clinical validation or clinical authority.
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

An optional self-hosted provider is available via the operator configuration:
set `OPENCARE_AGENT_MODE=ollama` with `OPENCARE_OLLAMA_ENDPOINT` (default
`http://127.0.0.1:11434`), `OPENCARE_OLLAMA_MODEL`,
`OPENCARE_OLLAMA_TIMEOUT_SECONDS` (default `15.0`), and
`OPENCARE_OLLAMA_MAX_RESPONSE_BYTES` (default `1000000`). The provider is
opt-in, deterministic by default, uses only loopback disclosure by default
(`external=false`), and runs no model at startup unless an operator enables it.
Non-loopback endpoints require the G2 disclosure-preview and exact per-call
consent. This is not clinical validation of any model's output.

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

.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.trust_metrics
.\.venv\Scripts\python.exe -m evals.g5_review
.\.venv\Scripts\python.exe -m evals.p1_review
.\.venv\Scripts\python.exe -m evals.p2_review
.\.venv\Scripts\python.exe -m evals.d1_review
.\.venv\Scripts\python.exe -m evals.p3_review
.\.venv\Scripts\python.exe -m pip check
git diff --check
node --check app/static/product_core_workspace.js
node --check app/static/genetics.js
```

Product Core migration smoke test:

Product Core persists medication/condition/lab lifecycle records, active people
profiles, Visits, user-authored Visit Questions, Visit Briefs (content schema
v2 with readable v1 revisions), immutable document Sources/extractions, and
schema v9 Family identity/access state. Ordinary Person portable vault export
is v4; Genetics Export is a separate explicit package. The API uses the same
SQLite metadata and immutable UTF-8 source payloads configured through
`OPENCARE_PRODUCT_DB_PATH` and `OPENCARE_SOURCE_DIR`. Migrations run during
application startup. Every live Product Core request resolves the Actor
session, resource owner, and fixed scope server-side.

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

Recovery restores durable Actor credentials, schema v9 access/genetics state,
and revocations.
It restores neither `.env`, plaintext passwords, invitation codes,
`OPENCARE_SECRET_KEY`, provider keys, cookies, sessions, TLS files, nor
deployment configuration. Every Actor logs in again and creates a new runtime
session. Import, merge, encryption, and populated-target recovery remain
unsupported.

Start the local app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

On a fresh schema v9 installation, open `/bootstrap` while no Actor exists.
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

The current implementation roadmap through P1, P2, D1, and P3 is complete on
public `main`. Future product work requires a new explicit product decision;
this repository does not invent a next phase.

See [docs/roadmap/product-core-roadmap.md](docs/roadmap/product-core-roadmap.md)
for historical evolution and the completed current-state boundary. The older
[docs/roadmap.md](docs/roadmap.md) is historical.
## Live Product Core Workspace

`/workspace` is the primary OpenCare entry point and `/` redirects there. It
uses the versioned Product Core API for capability-aware Person switching,
medication/condition/lab review, document evidence, timeline, Visits,
Visit Questions, Visit Brief revisions, provenance, and portable vault v4.
`/genetics` provides the separate Genetics Workspace, reviewed evidence,
PGx associations, family comparison, Research Studio, and explicit Genetics
Export. `/family-access` manages explicit identity/access consent. `/chat`
remains a supporting guarded feature.

OpenCare does not delete Persons, process OCR, claim clinical authority, or
provide diagnosis, treatment, dosage, medication selection, or start/stop
instructions. Product Core can process user-owned sensitive data locally under
explicit authorization; public fixtures and reviewer artifacts remain synthetic.
