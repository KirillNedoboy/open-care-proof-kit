# OpenCare current project status

This is the canonical status for public `main` at repository update date
2026-08-20. Public `main` is a mutable Git ref. The P3-final implementation
baseline was `0937d352cc74a3050609e826baa6bad82f6ac9ee`; the R1 repository-truth
baseline is `46141e70d980fc611513e98afe251b1c611089c7`. The only published tags/releases
are `v0.1.0` and `v0.2.0`; neither is a production-readiness or clinical-
readiness claim.
- Package/runtime development identity: `0.3.0.dev0`; this is not a published
  `v0.3.0` release.

The completed sequence on public `main` is:

```text
G1 -> G2 -> G2.5 -> G3 -> G4 -> G5 -> P1 -> P2 -> D1 -> P3
```

There is no G6. G5 machine state remains exactly
`READY_FOR_SECOND_CLIENT_SMOKE`: Agent Skills interoperability is verified,
while root Agent Plugins two-independent-client validation remains external
ecosystem evidence pending.

## Implemented boundary

- Product Core schema v9 owns Person-scoped Sources, medications, recorded
  conditions, labs, Visits, Visit Questions, Visit Briefs, document
  extractions, genetics datasets, findings, grants, research sessions, export,
  backup, and recovery.
- Visit Brief content schema remains v2; v1 revisions remain readable.
- Family Access v1 and v2 are frozen. v3 adds `document.read` and
  `document.write` without silent legacy expansion.
- Genetics authority is separate from Family Access generations:
  `genetics.read`, `genetics.write`, `genetics.research`,
  `genetics.compare`, and `genetics.export`.
- D1 PDF/TXT document ingest is implemented and published on public `main`:
  immutable Source bytes, bounded embedded-text extraction, page/span
  provenance, document grants, review lifecycle, export v4, and recovery.
- P3 Genetics Research Studio is implemented and published on public `main`:
  bounded local consumer-genotype import, selective indexing, evidence-backed
  reviewed findings, PGx associations, family comparison, Genetics Workspace,
  Evidence/Explore Research Mode, and separate Genetics Export.
- Raw genome never enters provider context. Genetics Research cannot mutate
  canonical health records.
- `/demo/health-vault` and committed reviewer artifacts remain synthetic/demo
  surfaces separate from live actor-scoped Product Core.
- The self-hosted runtime is designed for user-owned sensitive local data;
  repository fixtures and public artifacts remain synthetic/de-identified.
- Normal local username/password login is the default account entry flow;
  invitations are an explicit family-sharing mechanism rather than a login
  prerequisite.
- Optional public self-registration is disabled by default and available only
  after operator bootstrap when `OPENCARE_PUBLIC_REGISTRATION=true`. It creates
  only an Actor, that Actor's own Person, its owner assignment, and own-Person
  link. It does not create installation-admin status or cross-Person access.
- Email verification, password recovery, CAPTCHA, internet-scale abuse controls,
  billing, moderation, and organizational SaaS tenancy are not implemented.

## R5.1 UI foundation (this branch)

R5.1 adds a reusable authenticated product shell and shared visual tokens for
the existing Workspace, Genetics, Vault, and Family Access pages. The shell
keeps existing page-specific content and Genetics local navigation intact.
The first UI localization foundation supports English (`en`) and Russian
(`ru`); the selected locale is stored in the dedicated `opencare_locale`
SameSite cookie and affects UI copy only. It does not change canonical health
data, identifiers, machine reason codes, audit codes, API contracts, or
authorization behavior.

Chat shell convergence and broader product-page redesign remain deferred to later
R5 passes.

## R5.2 auth and onboarding UX (this branch)

R5.2 provides a separate public/auth shell for sign-in, controlled
self-registration, one-time installation-owner bootstrap, and invitation entry.
The normal path is local username/password sign-in. Self-registration appears
only when `OPENCARE_PUBLIC_REGISTRATION=true` and the installation is already
initialized. Invitations remain a secondary family-sharing mechanism, while
bootstrap remains a one-time installation-owner operation.

Auth surfaces support English (`en`) and Russian (`ru`) through the centralized
UI catalog and dedicated locale preference cookie. UI localization does not
alter credentials, sessions, authorization, invitation tokens, Person data,
scope names, or API contracts. Full product-page localization is intentionally
incremental; R5.4 work remains deferred.

## R5.3 Workspace & Person UX

R5.3 makes `/workspace` the main authenticated product overview. It keeps the
active Person visible, uses the existing authorized Person list and
session-backed active-Person switch, and presents capability-gated counts for
real Product Core records, documents, medications, pending review items, and
timeline activity. Zero states remain explicit; no health data is inferred.

The live workspace does not seed or load synthetic reviewer/demo data. Person
switching remains a UI convenience over the existing Actor session and
assignment checks; it does not grant access or change authorization semantics.
Workspace overview and Person-selection copy is localized for English (`en`) and
Russian (`ru`). There is no new activity subsystem or analytics read model.

R5.4 remains deferred for broader authenticated-page localization, chat-shell
convergence, and further product-shell refinement. Genetics contracts and
Genetics Workspace behavior are unchanged by R5.3.

## HTTP privacy contract

- no valid Actor session on an API endpoint: `401`;
- no valid Actor session on protected browser HTML GET: safe `307` redirect to
  `/login?next=...`;
- invalid CSRF or high-risk confirmation: `403`;
- visible Person but missing known action scope: `403`;
- hidden/guessed Person or nested resource: `404`;
- invalid, expired, revoked, or replayed invitation: one generic response;
- lists contain no hidden names, IDs, Family members, hidden counts, or
  installation totals.

The complete policy is in
[the authorization matrix](security/family-access-authorization-matrix.md) and
[ADR 0005](adr/0005-family-identity-access-boundary.md).

## Historical validation baselines

The P3-final verification at `0937d352cc74a3050609e826baa6bad82f6ac9ee` was run
on Python 3.12. It is historical local evidence, not a claim that GitHub
Actions ran every command.

- pytest: `675 passed, 4 skipped, 4 warnings`;
- Ruff: all checks passed;
- mypy: no issues in `121` source files;
- `python -m evals.runner`: `30/30`;
- `python -m evals.trust_metrics`: passed;
- G5: `20/20`, `READY_FOR_SECOND_CLIENT_SMOKE`;
- P1: `PASS`;
- P2: `PASS`;
- D1: `PASS`;
- P3: `PASS`;
- all P3 security counters: `0`;
- `pip check`: no broken requirements;
- `git diff --check`: passed;

R1 repository-truth verification at `46141e70d980fc611513e98afe251b1c611089c7`
reported `677 passed, 4 skipped, 4 warnings`, G5 `20/20`, and P1/P2/D1/P3
`PASS`. That is historical R1 evidence; current R3 evidence is published only
in `docs/validation/latest-verified-baseline.md` after the validated code
baseline commit.
- runtime JavaScript syntax checks: passed.

G5 Agent Skills interoperability is verified across OMP 17.3.5 and Hermes
Agent 0.19.0. Root Agent Plugins two-independent-client interoperability
remains external ecosystem evidence pending; it is not a G5 PASS claim.

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

## Historical phase notes

## Sentient P1 evidence-grounded ingest (integrated on public main)

P1 generalizes the prior medication evidence lifecycle into one reusable
lifecycle for three fact families — `medication`, `condition`, `lab` — with
typed strongly-validated detail. It is integrated on public `main` after the
published `v0.2.0` boundary; P1 has no separate release tag. Design and
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
## P2 usable family workspace (integrated on public `main` after v0.2.0)

P2 reframes `/workspace` as the OpenCare Health Workspace with capability-aware
Person switching, all-three-type Review Inbox and Timeline surfaces,
current/history record grouping, human-readable provenance, Visit Questions,
Visit Brief content schema v2 with readable v1 revisions, and portable vault
export format v3. It adds no schema migration, family-access-v3, Visit Brief
schema v3, or new runtime dependency. The deterministic offline reviewer
(`python -m evals.p2_review`) and its focused test pass with these counters at
zero: `cross_person_workspace_exposures`,
`stale_person_render_acceptances`, `unauthorized_ui_backed_mutations`,
`hidden_record_count_exposures`, `hidden_source_metadata_exposures`, and
`legacy_scope_expansions`.

## D1 evidence document ingest (implemented and published on public `main`)

D1 is implemented and published on public `main` at
`c6ae91e40f02582c0e07c1bca8c95765970c93ff`. It accepts only authenticated
Person-scoped PDF/TXT uploads, preserves immutable source bytes, performs
bounded embedded-text extraction, and keeps review human-controlled for
medication, condition, and lab records. OCR and automated clinical/model
extraction remain out of scope. Family Access v1/v2 remain frozen; v3 adds
explicit document scopes. Portable export v4 includes authorized document
payloads and immutable extraction metadata.

## P3 Genetics Research Studio (implemented and published on public `main`)

P3 is implemented on public `main`. Its historical phase-final baseline was
`0937d352cc74a3050609e826baa6bad82f6ac9ee`. It adds schema v9 immutable local
consumer-genotype sources, selective indexed observations, versioned synthetic
evidence, reviewed genetics findings, explicit revocable genetics grants, a
responsive Genetics Workspace, deterministic family comparison, and offline
Evidence/Explore Research Mode. VCF remains demo-only. See
`docs/architecture/p3-genetics-research-studio.md` and
`python -m evals.p3_review`.

## Preserved boundaries

- `v0.1.0` and `v0.2.0` remain the only published release tags;
- deterministic tools remain before bounded AI;
- synthetic repository fixtures remain separate from local user-owned runtime
  data;
- no OCR, FHIR/EHR sync, public SaaS identity, cloud raw-genome upload, or
  clinical-authority claim;
- no diagnosis, treatment, dosage, medication selection, or start/stop advice;
- no populated-installation import/merge guarantee.

## Remaining product limits

OpenCare is not a diagnostic system, treatment or dosage recommender, clinical
decision-support system, public identity service, encrypted backup system, or
populated-installation import/merge tool. Phase 2 does not make the documented
self-hosted path production-ready or clinically validated.
