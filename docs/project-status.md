# OpenCare current project status

This is the canonical status for the public `main` branch as of 2026-08-13.
The published `v0.1.0` tag remains the controlled private-alpha baseline.
Phase 2 Family Identity and Access Boundary is implemented on `main` and
published as `v0.2.0`. The Sentient G1–G4 trust work — G1 Trust Envelope, G2
Consent-Gated Agent Runtime, G2.5 optional integration spike, G3 Model
Portability, G4 Portable Trust Package, and G5 Ecosystem Validation
are integrated on `main` **after the `v0.2.0` release boundary**; none of them
is itself a release tag.

## Implemented boundary

- Product Core schema v7 (P1 branch) preserves the Medication/Visit lifecycle and adds
  durable Actors, versioned scrypt credentials, installation administrators,
  Families, memberships, relationships, append-only consent, explicit Person
  assignments, one-to-one own-Person links, hash-only invitations,
  metadata-only access audit, the generic evidence lifecycle
  (medication/condition/lab candidates and canonical records), and versioned
  Family Access scope generations.
- A generation-aware Family Access policy protects live `/workspace`, `/vault`,
  `/api/product-core/v1`, `/chat`, and `/api/chat`: `family-access-v1` scope
  sets are frozen verbatim for legacy grants, and the current
  `family-access-v2` generation adds `condition.read/write` and
  `lab.read/write`. An assignment's generation is inferred from its stored
  scopes, so existing delegated consent never automatically gains new
  capabilities (no silent privilege expansion); upgrades are explicit
  owner/caregiver actions. Resource ownership is resolved server-side and
  authorization is deny-by-default.
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
  verify durable schema v7 access state. Recovery restores credentials and
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

The current G1–G5 validation state (2026-08-13, at G5 implementation
completion) reports: pytest `570 passed, 3 skipped, 0 failed`; the G5
reviewer (`python -m evals.g5_review`) passes with 20/20 adversarial cases
and all eight security invariants at zero violations, state
`READY_FOR_SECOND_CLIENT_SMOKE` (Cursor 3.0.13 verified; second independent
client pending).

## Sentient G3 provider portability (on main after v0.2.0)

G3 makes the agent provider a portability slot below the G1 Trust Envelope: a
provider-independent G2 execution contract (`AgentProvider` Protocol plus
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
never auto-installs or downloads a runtime. This work is integrated on `main`
after the published `v0.2.0` baseline; it is not itself a release tag.

## Sentient G4 portable trust package (on main after v0.2.0)

G4 packages the G1/G2/G3 trust contract for portable use. G4 is packaging and
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
ecosystem validation is Sentient G5. This work is integrated on `main` after
the published `v0.2.0` baseline; it is not itself a release tag.

## Sentient G5 ecosystem validation (integrated on main after v0.2.0)

G5 evaluates the existing G1–G4 system: a deterministic, offline adversarial
corpus (`evals/g5/corpus.json`, 20 cases) covering eight security invariant
families, measured quality metrics, the single-reviewer command
`python -m evals.g5_review`, an OWASP taxonomy mapping, package supply-chain
checks, and cross-client loading evidence for the skill-only Agent Plugins
package. G5 adds no trust semantics, no schema version, no provider, and no
network surface.

Engineering and security validation is complete: the reviewer passes 20/20
cases with all eight security invariants at zero violations; deterministic
replay and package integrity pass; quality metrics are measured (context
precision/recall 1.0 on the synthetic labelled subset, minimization 20/58
eligible evidence IDs, 1222 → 375 evidence-identifier bytes, provenance
coverage 15/15, refusal correctness 13/13, completed receipts 5/5).

Agent Skills interoperability is proven on two independent real clients with
byte-identical committed Skill files: **OMP (Oh My Pi) 17.3.5** locally and
**Hermes Agent v0.19.0** on a remote VPS both discover
`opencare-trust-envelope` and `opencare-health-agent` and both pass the
Trust-positive, Trust-negative, and Health-safety behavioral smokes (evidence:
`docs/assets/g5/client-interop-evidence.md` §9; decision:
`docs/adr/0006-g5-engineering-closure.md`).

The remaining limitation is two-client root **Agent Plugins `plugin.json`**
interoperability: Cursor 3.0.13 root-plugin loading is proven but its
behavioral smoke is blocked by usage quota; Kiro's root-plugin evidence is
blocked by account/sign-in. This is documented external ecosystem validation
pending, not an internal security defect; the machine gate therefore still
reports `READY_FOR_SECOND_CLIENT_SMOKE`. This work is integrated on `main`
after the published `v0.2.0` baseline; it is not itself a release tag.

## Sentient P1 evidence-grounded ingest (implementation branch)

P1 generalizes the medication-only evidence lifecycle into ONE reusable
lifecycle for three fact families — `medication`, `condition`, `lab` — with
typed strongly-validated detail. It is implemented on the
`codex/p1-evidence-grounded-ingest` branch (not yet integrated to `main`); per
the status conventions above it is branch work until integration. Design and
acceptance contract: `docs/architecture/p1-evidence-grounded-ingest.md`;
deterministic reviewer: `python -m evals.p1_review` (guide:
`docs/p1-reviewer-guide.md`).

- **Migration v7** generalizes the schema (never edits v1–v6): generic
  `candidate_facts` and `canonical_records` with typed detail tables for
  medication/condition/lab, `timeline_events` and Visit Brief evidence
  selections retargeted to `canonical_records`, an `unsupported` review status,
  correction supersession lineage, provenance locators, and a
  `scope_generation` column on assignments (derived metadata). Populated
  v6 → v7 fixtures (People, sources, medication candidates incl. a corrected
  chain, canonical medication, timeline, Visit + Question + Brief with
  medication evidence, actors/assignments/consent history, audit, G2
  consent/receipt) survive with row identity preserved, `foreign_key_check`
  empty, and a usable medication lifecycle.
- **Condition and lab lifecycles** are source-backed records: structured
  manual sources (schema_version 2) or plain-text sources, human review
  (confirm/reject/unsupported/correct) before any canonicalization, typed
  detail (condition: display_name/status_text/onset_date/note; lab:
  test_name/result_text/unit_text/reference_range_text/observed_date/
  source_flag_text/note with source-preserving text and source-provided flags
  only), immutable-source provenance locators required and validated, and
  deterministic timeline events (`{fact_type}_confirmed`/`_corrected`).
- **Family Access generations**: `family-access-v1` frozen verbatim;
  `family-access-v2` adds `condition.read/write` and `lab.read/write`. The
  generation is inferred from the stored scopes (no silent privilege
  expansion); upgrades are explicit owner/caregiver actions with new
  append-only consent events. Existing delegated consent never automatically
  gains Conditions/Labs access.
- **Visit Brief** content schema v2 carries typed condition/lab evidence
  selections with neutral wording ("Recorded conditions", "Recent/selected lab
  records"); v1 revisions remain readable and medication-only Briefs remain
  valid.
- **Agent context** includes confirmed active condition/lab canonical records
  as bounded evidence items; pending/rejected/unsupported facts never reach
  context. No Trust Envelope contract version change.
- **Export/recovery**: portable export format v3 with condition/lab entities;
  backup/verify/preflight/recover operate on schema v7 and preserve the new
  state; sessions still do not survive.
- The deterministic P1 reviewer asserts six security counters at zero
  (canonical_without_review, canonical_without_source,
  cross_person_record_exposure, cross_person_source_exposure,
  unauthorized_confirmation, provenance_mismatch_accepted).
- P1 adds no OCR/upload/model extraction, no FHIR/EHR sync, no
  diagnosis/treatment/dosage interpretation, and no reference-range or
  abnormality inference.

## Preserved boundaries

- published `v0.1.0` controlled private-alpha baseline and current `v0.2.0`
  Phase 2 implementation;
- deterministic Medication and Visit lifecycle, exports, and offline recovery;
- guarded answer validation and medical-safety restrictions;
- no new runtime dependency;
- on `main` (P1 branch adds the source-backed Conditions/Labs lifecycle per the
  section above): no Phase 3 ingest, OCR, Conditions/Labs lifecycle, FHIR,
  Sentient, EvoSkill, genetics expansion, cloud synchronization, or public
  SaaS identity.

## Remaining product limits

OpenCare is not a diagnostic system, treatment or dosage recommender, clinical
decision-support system, public identity service, encrypted backup system, or
populated-installation import/merge tool. Phase 2 does not make the documented
self-hosted path production-ready or clinically validated.
