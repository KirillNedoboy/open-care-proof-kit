# OpenCare current project status

This is the canonical status for the public `main` branch as of 2026-08-04.
The published `v0.1.0` tag remains the controlled private-alpha baseline.
Phase 2 Family Identity and Access Boundary is implemented on `main` and
published as `v0.2.0`.

## Implemented boundary

- Product Core schema v5 preserves the Medication/Visit lifecycle and adds
  durable Actors, versioned scrypt credentials, installation administrators,
  Families, memberships, relationships, append-only consent, explicit Person
  assignments, one-to-one own-Person links, hash-only invitations, and
  metadata-only access audit.
- A centralized `family-access-v1` policy protects live `/workspace`, `/vault`,
  `/api/product-core/v1`, `/chat`, and `/api/chat`. Resource ownership is
  resolved server-side and authorization is deny-by-default.
- Installation administration grants no Person access. The final active owner
  of each Person and the final active installation administrator are protected
  by independent service and database invariants.
- Eight-hour Actor sessions live at `OPENCARE_SESSION_DB_PATH`, outside Product
  Core storage, export, backup, and recovery. Production Compose uses
  `/run/opencare/sessions.sqlite3` on mode-`0700` tmpfs with no session volume.
- Authenticated mutations require same-origin and CSRF proof. Successful
  sensitive mutations share a transaction with their audit; audit failure
  rolls the mutation back. A denial-audit failure preserves the original
  privacy-safe denial.
- Owner grants require explicit full-access confirmation and always use the
  fixed complete owner scope set. Caregivers receive the fixed base set plus
  only bounded optional scopes and cannot manage access or become owners by
  revision.
- Authenticated Person creation requires `confirm_owner_assignment: true` and
  atomically creates the Person, self-consent, full owner assignment, optional
  valid identity link, and access audit. Installation-admin status is not
  required.
- Invitation codes are random 256-bit bearer secrets accepted only in POST
  bodies. Plaintext is returned once and never persisted, logged, audited,
  exported, backed up, or placed in a URL.
- Person export v2 contains only the authorized Person's Product Core graph and
  relevant non-secret Family/consent/assignment history. Credentials, sessions,
  invitation state, access audit, unrelated identities, and installation totals
  are excluded.
- Offline `backup`, `verify`, `preflight`, and `recover` remain operator
  workflows with no Actor session or Person impersonation. They preserve and
  verify durable schema v5 access state. Recovery restores credentials and
  revocations but no sessions, so every Actor logs in again.
- `/demo/health-vault`, reviewer routes, and the frozen PGx workflow remain
  synthetic and separate from live actor-scoped data.

## HTTP privacy contract

- no valid Actor session: `401`;
- invalid CSRF or high-risk confirmation: `403`;
- visible Person but missing known action scope: `403`;
- hidden/guessed Person or nested resource: `404`;
- invalid, expired, revoked, or replayed invitation: one generic response;
- lists contain no hidden names, IDs, Family members, hidden counts, or
  installation totals.

The complete policy is in
[the authorization matrix](security/family-access-authorization-matrix.md) and
[ADR 0005](adr/0005-family-identity-access-boundary.md).

## Validation baseline

The most recent full validation run recorded for the Phase 2 implementation
reported:

- pytest: `399 passed, 2 skipped`;
- Ruff: all checks passed;
- mypy: no issues in `77` source files;
- focused recovery/credential/smoke tests: passed;
- JavaScript syntax and live browser flows: passed earlier in the six-commit
  implementation sequence.

Final evals, trust metrics, package installation, Uvicorn/production Compose
smoke, and clean-worktree evidence are recorded in the implementation report,
not projected here before execution.

## Sentient G3 provider portability (working branch)

On the `codex/sentient-g3-model-portability` working branch, the agent
provider is a portability slot below the G1 Trust Envelope: a provider-
independent G2 execution contract (`AgentProvider` Protocol plus
`ProviderDescriptor` / `ProviderExecutionRequest` / `ProviderExecutionResult`
in `app/agent/providers/`), a deterministic baseline provider, and one
self-hosted Ollama adapter (`app/agent/providers/ollama.py`) over stdlib
`urllib` with zero new dependencies, JSON-schema `format` structured output,
model-identity checking, no-redirect, and fail-closed behavior. Loopback
endpoints are `external=false`; non-loopback endpoints are `external=true` and
require the G2 disclosure-preview and exact per-call consent flow (owning a
remote server is not a consent exemption). Every provider passes the same
G1/G2 validation, and `ExecutionReceipt` records `provider_id`, `model_id`,
`provider_kind`, and `external` with no separate model receipt. Provider
configuration is operator-only (`OPENCARE_AGENT_MODE=ollama` and
`OPENCARE_OLLAMA_*`); the default stays deterministic/local and no model
runtime is required for startup.

G3 proves provider portability and security compatibility, not model medical
correctness; it adds no model-quality or diagnostic benchmarking. The result
is `READY_FOR_LIVE_SMOKE` because Ollama is not installed locally; the smoke
never auto-installs or downloads a runtime. This branch work is not part of
the published `v0.2.0` main baseline described elsewhere in this document.

## Sentient G4 portable trust package (working branch)

On the `codex/sentient-g4-portable-trust-package` working branch, the
G1/G2/G3 trust contract is packaged for portable use. G4 is packaging and
interface stabilization, not a new security model; the G1 `contract_version`
literals (`opencare-trust-envelope/1`, `opencare-execution-receipt/1`) are
unchanged.

- Generic trust layer with a stable public API (`app/agent_trust/api.py`) and
  zero OpenCare coupling: contract models, canonicalization/hashing,
  validation, trusted builders, controlled identifiers, and the generic
  `AuthorizationAdapter` Protocol (no FastAPI, Product Core, Family Access,
  SessionStore, Ollama, or Sentient imports).
- The OpenCare authorization adapter moved to `app/agent/trust_adapter.py`;
  it implements the generic Protocol against live Family Access state and is
  the only health-specific authority bridge.
- Deterministic JSON Schema export at `schemas/agent-trust/`
  (`trust-envelope.schema.json`, `execution-receipt.schema.json`,
  `authorization-snapshot.schema.json`) via
  `scripts/export_agent_trust_schemas.py` or `opencare-trust export-schemas`,
  with a drift test. No new schema version is invented.
- Synthetic, offline, not-authorization fixture corpus at
  `fixtures/agent-trust/` (allowed / refused / unsupported), fixed fixture
  clock `2027-08-02T10:00:00Z`, deterministic regeneration via
  `opencare-trust regenerate-fixtures`, and a drift test.
- `opencare-trust` console entry (`pyproject.toml` `[project.scripts]`) plus
  `python -m app.agent_trust.cli`, deterministic exit codes, schema export and
  fixture regeneration as pure artifact generation, and no live-authorization
  minting path.
- An Agent Plugins v1 **skill-only** package at
  `agent-plugins/opencare-trust/` (strict 1.0.0 `plugin.json` plus its
  `skills/` tree, including the canonical `opencare-health-agent` skill and an
  `opencare-trust-envelope` inspection skill), packaged deterministically from
  the canonical skill sources with a drift test, no symlinks, package
  containment and secret/path scans, and no `mcp.json` (explicit MCP
  deferral).

G4 makes no MCP claim and no multi-client validation claim; multi-client
ecosystem validation is Sentient G5. This branch work is not part of the
published `v0.2.0` main baseline described elsewhere in this document.

## Preserved boundaries

- published `v0.1.0` controlled private-alpha baseline and current `v0.2.0`
  Phase 2 implementation;
- deterministic Medication and Visit lifecycle, exports, and offline recovery;
- guarded answer validation and medical-safety restrictions;
- no new runtime dependency;
- no Phase 3 ingest, OCR, Conditions/Labs lifecycle, FHIR, Sentient, EvoSkill,
  genetics expansion, cloud synchronization, or public SaaS identity.

## Remaining product limits

OpenCare is not a diagnostic system, treatment or dosage recommender, clinical
decision-support system, public identity service, encrypted backup system, or
populated-installation import/merge tool. Phase 2 does not make the documented
self-hosted path production-ready or clinically validated.
