# OpenCare Module Boundaries

This document defines intended ownership for the combined OpenCare foundation.
It does not move modules or change imports.

## Product Core

Product Core owns user-facing health workspace concepts:

- people;
- family;
- sources;
- candidate facts;
- canonical records;
- review;
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
Visit Brief generation. It deliberately does not add routes, UI, a people
table, extraction, or external model calls.

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

## Current-to-intended mapping

The current `app/health_vault` package is a read-only/demo foundation for
future Product Core work. The current `app/agent` package is a bounded
Question Workspace precursor, not the product entry point. The current
`app/pgx` and `app/genetics` packages are Reference Workflow components. The
current report, eval, deployment, and reviewer documents belong to Trust
Foundation or reviewer/grant artifacts according to their ownership above.
