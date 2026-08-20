# OpenCare Module Boundaries

This document defines intended ownership for the combined OpenCare foundation.
The implementation sequence through G1-G5, P1, P2, D1, and P3 is complete on
public `main`. It does not move modules or change imports.

Current runtime ownership includes Product Core schema v9, D1 document ingest,
`app/product_core/genetics.py`, separate genetics grants, `/workspace`,
`/family-access`, and `/genetics`. Historical phase notes below are retained
for architecture provenance, not as pending work.
## Product Core

Product Core owns user-facing health workspace concepts:

- people;
- family;
- sources;
- candidate facts;
- canonical records;
- review;
- document Sources/extractions and reviewer provenance;
- genetics datasets, evidence, findings, grants, research sessions, and Genetics Export.
- timeline;
- visits;
- questions;
- visit briefs;
- export and backup.

Product Core owns user intent and record lifecycle. It may call Trust
Foundation interfaces for provenance, policy, validation, audit, evaluations,
and deterministic artifact generation.

Phase 1A implements the medication-only persistence boundary in
`app/product_core/` with standard-library `sqlite3`, explicit migrations,
transaction-bound repositories, immutable source files, and deterministic
Visit Brief generation. Phase 1B adds a thin router/runtime adapter in the
same package. Handlers map validated HTTP payloads to application services;
they do not own lifecycle transitions or SQL. It deliberately does not add
UI, a people table, extraction, or external model calls.

Phase 1C adds `/workspace` as a server-rendered shell. Its browser JavaScript
uses only `/api/product-core/v1`; the workspace route does not read SQLite,
repositories, Unit of Work objects, source files, or Product Core services.
The Product Core API remains the adapter between the UI and application
services, which retain lifecycle authority. Workspace state is kept only in
page memory, with no Product Core browser persistence. `/chat` remains a
separate supporting feature. At that phase, the shared password gate protected
an installation rather than an individual Person. Phase 1D adds persisted active people profiles and explicit
workspace selection. The migration preserves legacy opaque person IDs with an
`Imported profile` placeholder and does not infer medical data. That migration
does not infer Family relationships, permissions, or Person authorization;
Phase 2 adds them only through explicit actions. Phase 1E-A adds
persisted Visits and user-authored Visit Questions. They are Person-scoped,
explicitly ordered within a Visit, and separate from the transient deterministic
Visit Brief. Phase 1E-B adds a separate Visit-scoped persisted Brief lifecycle:
immutable revisions, selected confirmed-evidence snapshots, metadata-only audit
events, integrity verification, and stale-state derivation. It does not add
generated questions or answers, family relationships, or access control.

Phase 1F-A adds `PortableVaultExportService` inside this boundary. It reads a
single Person's Product Core graph through the SQLite Unit of Work, verifies
reachable immutable sources and persisted Brief revisions, and returns a
request-scoped ZIP through the Product Core API. It does not own import,
backup, recovery, encryption, a CLI, or storage-provider integration.

Phase 1F-B adds `InstallationBackupService` and `app.product_core.backup_cli`
to this boundary. Phase 1F-C adds `InstallationRecoveryService` and target-only
recovered-installation verification. They create, verify, preflight, and
fail-closed recover local installation state offline; they do not expose HTTP/UI
behavior, import/merge, encryption, remote storage, scheduling, or deployment
integration.

Phase 2 adds `app/family_access/` as the local Actor, credential, session,
consent, Family, assignment, invitation, and centralized Person-policy façade.
Durable identity/access rows live in Product Core schema v5; runtime sessions
live at the separate `OPENCARE_SESSION_DB_PATH`. `app/product_core/access.py`
resolves each live HTTP resource to its owning Person and applies the policy
before Product Core services release data. Successful sensitive mutations
repeat authorization and write access audit inside the same SQLite transaction.
The offline backup/recovery CLI deliberately remains outside Actor-session
authorization and verifies the durable v5 state directly.

## Trust Foundation

Trust Foundation owns reusable guarantees:

- provenance;
- policy;
- validation;
- audit;
- evaluations;
- deterministic artifact generation.

Current repository evidence includes `app/health_vault/`, `app/agent/`,
`app/safety/`, `app/reports/`, `evals/`, and the related tests. Trust Foundation
must remain usable without reviewer presentation and must not depend on
reviewer UI code.

## Reference Workflows

Reference Workflows are bounded demonstrations built from Product Core and
Trust Foundation. The current reference workflow is:

- PGx Medication Briefing.

It remains synthetic/demo-only and frozen during Phase 0. It must not define
the Product Core roadmap.

## Reviewer and grant artifacts

Reviewer and grant artifacts include:

- reviewer pages;
- grant evidence;
- synthetic demonstrations;
- committed generated artifacts.

They may consume Product Core and Trust Foundation. They are evidence of
verified behavior, not the canonical product roadmap or source of runtime
truth.

## Dependency rules

1. Product Core may depend on Trust Foundation.
2. Trust Foundation must not depend on reviewer UI.
3. Reviewer and grant artifacts may consume Product Core and Trust Foundation.
4. Reference Workflows may consume Product Core and Trust Foundation.
5. Canonical records must never depend on LLM output.
6. AI artifacts must never silently mutate canonical records.
7. Raw sources must remain immutable.
8. Derived views must be rebuildable from raw sources and canonical records.
9. Unknown, rejected, and unsupported states must remain explicit.
10. A reviewer artifact must not be treated as user-owned canonical data.
11. SQLite metadata and source publication use compensation because the
    filesystem and database cannot share one atomic transaction.
12. Immutable source publication uses a same-directory temporary file,
    flush/fsync, and `os.link` no-overwrite publication; this is the selected
    same-filesystem strategy for Windows and Linux. `os.replace` is prohibited.
13. Product Core API startup migrations are composed through the existing
    FastAPI application lifespan; runtime state contains no live SQLite
    connection or request-reused Unit of Work.
14. The outer password gate provides shared-instance protection only. Live
    Person authorization requires a valid Actor session and an explicit active
    assignment evaluated under its frozen Family Access scope generation
    (`family-access-v1`, `family-access-v2`, or `family-access-v3`); document
    access uses v3 document scopes where applicable, and a `person_id`, Family link,
    relationship, own-Person link, or installation-admin role is never a grant.
    Genetics authorization is a separate explicit grants layer; ordinary
    caregiver/health scopes never imply genetics scopes.
15. Synthetic demo/reviewer routes remain separate from the actor-scoped live
    Workspace, vault, Product Core API, and chat.

## Current ownership mapping

`app/product_core` owns the live schema v9 workspace, lifecycle, document
ingest, persisted genetics service, exports, backup, and recovery.
`app/family_access` owns Actor sessions, consent, and Family Access policy.
`app/agent_trust` owns reusable Trust Envelope and receipt contracts.
`app/agent` owns bounded context, provider adapters, validation, and audit.
`app/genetics` owns pure consumer-genotype, evidence, comparison, and Research
Mode contracts. `app/pgx` remains the deterministic reference matcher.
Templates/static assets implement the live Workspace and Genetics Workspace.
`evals` contains deterministic final-phase reviewers.

Historical phase notes above describe how these boundaries evolved; they do not
describe pending implementation work.
