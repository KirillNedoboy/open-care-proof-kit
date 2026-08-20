# Changelog

## [Unreleased]

### Added
- D1 evidence document ingest is implemented in the current baseline:
  authenticated Person-scoped PDF/TXT upload, immutable source bytes, bounded
  embedded-text extraction, and human-reviewed medication/condition/lab
  provenance. OCR and automated clinical/model extraction remain out of scope.
  Family Access v1/v2/v3 behavior and portable export v4 are integrated.

- P3 Genetics Research Studio is implemented on
  `codex/p3-genetics-research-studio`: schema v9 immutable local consumer
  genotype sources, bounded selective indexing, genome-build and coverage
  provenance, versioned synthetic genetics evidence, reviewed findings,
  explicit revocable genetics grants, the `/genetics` workspace, deterministic
  family comparison, Evidence/Explore Research Mode with epistemic labels and
  counterevidence, explicit genetics export, and offline `python -m
  evals.p3_review`. VCF remains demo-only; no clinical genetics, diagnosis,
  autonomous treatment, dosage, or mandatory external genetics service.

- Sentient P1 evidence-grounded ingest (integrated on public `main` after the
  `v0.2.0` boundary; no separate P1 release tag): one generic evidence
  lifecycle for medication/condition/lab facts — migration v7 (generic
  `candidate_facts` and `canonical_records` with typed detail tables,
  `unsupported` review status, correction supersession lineage, provenance
  locators, `scope_generation` on assignments); source-backed condition and
  lab lifecycles with validated immutable-source provenance and deterministic
  timeline events; Family Access scope generations (`family-access-v1` frozen,
  `family-access-v2` current); Visit Brief content schema v2 with condition/lab
  evidence selections while v1 revisions remain readable; confirmed
  condition/lab records in the agent context; portable export format v3; and
  backup/verify/preflight/recover on schema v7. P1 adds no OCR/upload/model
  extraction, no FHIR/EHR sync, and no diagnosis/treatment/interpretation.


- Optional Sentient Agent Framework compatibility spike (`[sentient]` extra,
  `sentient-agent-framework==0.3.0`): synthetic/demo-only OpenCare agent over
  the G2 consent-gated runtime, deterministic local provider, and Sentient
  event rendering with validated answers and redacted Execution Receipts.
  Spike only; not a production integration and no live-vault access.
- Sentient G3 model portability: provider-independent G2 execution contract
  (`AgentProvider` Protocol plus `ProviderDescriptor` /
  `ProviderExecutionRequest` / `ProviderExecutionResult` and a shared
  `build_provider_execution_request` in `app/agent/providers/`), a
  deterministic baseline provider, and one self-hosted Ollama adapter
  (`app/agent/providers/ollama.py`) built on stdlib `urllib` with zero new
  Python dependencies, JSON-schema `format` structured output, model-identity
  check, no-redirect, and fail-closed behavior. Operator-only provider
  configuration via `OPENCARE_AGENT_MODE=ollama` and the `OPENCARE_OLLAMA_*`
  variables; the default stays deterministic/local and no model runtime is
- Provider-portability conformance, trust, endpoint, and
  live-smoke suites under `tests/provider_*`.
- Sentient G4 portable trust package: generic trust layer with a stable public
  API (`app/agent_trust/api.py`) and zero OpenCare coupling; the generic
  `AuthorizationAdapter` Protocol with the OpenCare adapter moved to
  `app/agent/trust_adapter.py`; deterministic JSON Schema export
  (`schemas/agent-trust/` via `scripts/export_agent_trust_schemas.py` or
  `opencare-trust export-schemas`) with a drift test; and a synthetic, offline,
  not-authorization fixture corpus (`fixtures/agent-trust/`) with
  deterministic regeneration (`opencare-trust regenerate-fixtures`) and a
  drift test. G1 `contract_version` literals are unchanged; no new schema
  version is invented.
- Agent Plugins v1 skill-only package at `agent-plugins/opencare-trust/`
  (strict 1.0.0 `plugin.json` plus its `skills/` tree, including the canonical
  `opencare-health-agent` skill), packaged deterministically from the
  canonical skill sources with a drift test, no symlinks, package containment
  and secret/path scans, and no `mcp.json` (explicit MCP deferral).
- `opencare-trust` console entry (`pyproject.toml` `[project.scripts]`) plus
  the existing `python -m app.agent_trust.cli`; deterministic exit codes;
  schema export and fixture regeneration are pure artifact generation with no
  live-authorization minting path.
- Sentient G5 ecosystem validation: deterministic offline adversarial corpus
  (`evals/g5/corpus.json`, 20 cases, eight security-invariant families),
  quality metrics, the `python -m evals.g5_review` single-reviewer route, an
  OWASP taxonomy mapping, and plugin supply-chain checks. Agent Skills
  interoperability is verified on OMP 17.3.5 (local) and Hermes Agent v0.19.0
  (remote VPS) with byte-identical committed Skills. Root Agent Plugins
  `plugin.json` two-client validation remains pending external ecosystem
  evidence (Cursor quota; Kiro account).

### Security

- Adds loopback disclosure classification for self-hosted providers: loopback
  (`127.0.0.1` / `localhost` / `::1`) is `external=false`; non-loopback is
  `external=true` and requires the G2 disclosure-preview and exact per-call
  consent flow, and owning a remote server is not a consent exemption.
- Binds executed provider/model identity to the G2 disclosure and Receipt
  flow, keeps provider configuration operator-owned (never chat-request
  supplied), rejects embedded endpoint credentials, and fails closed on
  unavailable, refused, timed-out, malformed, or unsupported provider output
  with no cloud or second-provider fallback. Provider output is untrusted and
  passes the existing G2 validation; `ExecutionReceipt` records
  `provider_id`, `model_id`, `provider_kind`, and `external` with no separate
  model receipt.
- G4 packaging rules: strict Agent Plugins 1.0.0 manifest conformance, skills
  discovered only from immediate child directories, skill name matching its
  directory, package containment (no path or symlink escape), secret/path
  scans, deterministic builds, and no live-authority CLI minting. A historical
  Envelope or Receipt remains a non-credential, and the committed fixtures are
  explicitly not authorization.

## [0.2.0] - 2026-08-04

### Added

- Product Core schema v5 with local Actors, versioned scrypt credentials,
  installation administrators, Families, relationships, append-only consent,
  Person assignments, hash-only invitations, own-Person links, and access audit.
- Central deny-by-default Person policy for live Workspace, vault, Product Core
  API, and chat, with fixed owner/caregiver scopes and privacy-safe
  `401`/`403`/`404` behavior.
- Server-side eight-hour Actor sessions in a separate runtime database,
  same-origin checks, CSRF enforcement, login/bootstrap, Person switching, and
  Family/access management flows.
- Deterministic Person export v2 and schema v5 offline backup/recovery checks,
  including restored credentials and revocations without restored sessions.
- Focused scrypt validation on Windows and Linux CPython 3.12 CI paths.
- Sentient G1 Trust Envelope contract and `app/agent_trust/` implementation:
  frozen versioned models, controlled actions, canonical UTF-8 JSON, SHA-256
  content identities, trusted builders, integrity validators, OpenCare Family
  Access adapter, synthetic fixtures/evals, and export/verify/inspect CLI tools.
- Ten named Sentient G2 trust-evaluation fixtures and eval-registration
  coverage for consent, mediation, refusal, isolation, TOCTOU, and audit
  acceptance categories. These fixtures do not claim external integration.

### Security

- Independently protects the final active Person owner and final active
  installation administrator.
- Makes owner grants and Person creation explicit high-risk atomic operations;
  required audit failure rolls back sensitive mutations.
- Keeps invitation codes out of URLs, persistence, logs, audits, exports, and
  backups; only a hash is durable.
- Keeps `/demo/health-vault` and reviewer routes synthetic and separate from
  actor-scoped live surfaces.
- Treats Envelope hashes as tamper detection only, never live authorization;
  arbitrary JSON cannot mint an authorized Envelope, and G2 must reauthorize
  actor, Person, consent, evidence, safety, provider, and expiry before use.

## [0.1.0] - 2026-07-31

Published as tag `v0.1.0`, the controlled private-alpha baseline. It is not
production-ready, clinically validated, or clinical software. The Phase 2
Family Identity and Access Boundary is published separately as `v0.2.0` and
does not change the claims or limitations of this baseline.

### Included

- Persistent People and a Medication source, candidate, review, canonical, and
  timeline lifecycle.
- Visits, Questions, and persisted editable Visit Brief revisions.
- Deterministic Person vault export plus installation backup, verify, preflight,
  and fail-closed recovery.
- Product Core Workspace UI and wheel-packaged runtime assets.
- Production Compose Product Core persistence through explicit bind mounts.
- Python 3.12 constraints and deterministic tests, evals, and trust checks.

### Limitations

This candidate does not provide diagnosis, treatment advice, clinical
validation, production readiness, import/merge, populated-target recovery,
destructive overwrite, encryption, or cloud backup.
