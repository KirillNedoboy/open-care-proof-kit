# ADR 0001: OpenCare Product Direction

- Status: Accepted
- Date: 2026-07-26
- Decision owners: OpenCare maintainers

## Current implementation status

The deferred Product Core sequence described by this historical ADR is now
implemented on public `main`: G1-G5, P1, P2, D1, and P3. The original thesis
remains unchanged: vault first, AI bounded, genetics secondary. This note does
not rewrite the historical decision or claim clinical validation.

## Context

The repository contains a useful Health/Family Vault data model, deterministic
provenance and safety components, guarded chat, a portable agent skill, and a
PGx reference workflow. Its documentation has accumulated several phase
labels and product framings. The repository needs one product direction that
separates the usable product core from the trust mechanisms and demonstrations.

The current implementation is still mostly read-only and demo-oriented. The
approved direction below is future architecture, not a claim that the complete
workspace already exists.

## Problem statement

Without a canonical direction, chat, PGx, reviewer artifacts, deployment
packaging, and trust metrics can be mistaken for the product itself. That
creates scope drift and makes it difficult to distinguish verified runtime
behavior from planned work.

## Approved product thesis

OpenCare is an open-source, self-hosted Personal and Family Health Workspace.
It turns fragmented medical documents and user-entered information into a
user-confirmed, source-linked longitudinal health record.

The product must be useful without genetics. AI is a constrained interface over
records and questions, not the source of truth.

## Target user

The primary user is a person or family organizing private health context before
and between clinical appointments. The initial workflow is useful to a
caregiver or family member who needs to gather records, verify extracted facts,
track changes, and prepare questions for a clinician.

## Repository role

The existing repository remains the main OpenCare foundation. It is not a
disposable proof kit and it is not replaced by a new repository. The repository
contains four separated concerns:

1. Product Core.
2. Trust Foundation.
3. Reference Workflows.
4. Reviewer and grant artifacts.

## Primary workflow

The first primary workflow is:

`Prepare for next appointment`

The intended lifecycle is:

`Source -> CandidateFact -> User Review -> CanonicalRecord -> TimelineEvent -> VisitBrief`

## Architectural module boundaries

### Product Core

- people and family profiles;
- medical sources;
- candidate extracted facts;
- user review;
- canonical confirmed records;
- timeline;
- visits;
- questions;
- visit preparation briefs;
- export and backup.

### Trust Foundation

- provenance;
- policy and safety;
- citation validation;
- audit;
- deterministic artifacts;
- evaluations;
- deployment baseline.

### Reference Workflows

- PGx Medication Briefing as a frozen reference workflow demonstrating
  provenance and safety.

### Reviewer and grant artifacts

- reviewer pages;
- grant evidence;
- synthetic demonstrations.

Detailed dependency rules are in
[module boundaries](../architecture/module-boundaries.md).

## Data ownership rules

- Raw source files are owned by the vault and remain immutable.
- Candidate facts are derived claims awaiting user review.
- Canonical records are owned by the user and become the trusted editable
  record only after explicit confirmation or manual entry.
- Timeline events and visit briefs are derived from canonical records and
  source references.
- AI outputs are artifacts or views and never silently mutate canonical
  records.
- Derived views must be rebuildable from owned source and canonical data.

## Source-of-truth hierarchy

1. Immutable source files and explicit user-entered records.
2. User-confirmed canonical records with provenance links.
3. Deterministic derived views, timeline events, and briefs.
4. Candidate facts awaiting review.
5. AI-generated explanations, summaries, and questions.

An item at a lower level must not silently override an item at a higher level.
Unknown or unsupported states remain explicit.

## AI role

AI may help with query-scoped navigation, explanations, summaries, question
drafting, and future candidate extraction. It may not create medical truth,
silently mutate canonical records, remove provenance, or provide diagnosis,
treatment, dosage, medication-selection, or start/stop instructions.

Guarded chat remains a future nested feature inside a Question Workspace. It
does not define the product identity.

## Family role

People and family relationships are first-class Product Core entities. The
workspace should support family context and caregiver use, while access
permissions remain future work and must be explicit before shared access is
implemented.

## Genetics role

Genetics is deferred until the non-genetic Product Core is usable and
validated. The existing PGx workflow remains a frozen reference workflow. Do
not expand genetics during this phase.

## Persistence direction

The approved future persistence direction is:

- SQLite for structured application data;
- immutable local source files for original documents;
- repository interfaces around persistence;
- JSON only for fixtures, import, export, backup, and migration.

This ADR does not implement that migration.

## Decisions

- The canonical product identity is OpenCare Personal and Family Health
  Workspace.
- The primary workflow is Prepare for next appointment.
- The current repository remains the main foundation.
- Trust functionality is an embedded product guarantee.
- Chat is nested future functionality.
- PGx is a frozen reference workflow.
- Genetics is deferred behind the non-genetic product core.
- The first implementation slice is medication-only and deterministic-first.

## Rejected alternatives

- Standalone trust and evaluation product.
- Generic medical chatbot.
- PGx-first product.
- Separate replacement repository.
- Large rewrite in another programming language.
- Multi-tenant SaaS before the self-hosted product is validated.

## Consequences

This direction keeps the current trust, safety, provenance, audit, evaluation,
deployment, chat, and PGx code reusable without letting any of them define the
product. It also means the next work must add user-controlled record lifecycle
capabilities before expanding AI, genetics, or infrastructure.

The current repository will continue to look incomplete as a user workspace
until it has editable persistence, source ingestion, review, canonical
records, and visit preparation. That is an explicit gap, not a reason to
overstate current capability.

## Explicit non-goals

This phase does not implement:

- SQLite persistence or migrations;
- document upload or OCR;
- a new LLM provider;
- genetics expansion;
- chat rewrite or deletion;
- PGx deletion or extension;
- multi-user SaaS or family permissions;
- autonomous record mutation;
- deployment or VPS changes;
- a new repository or programming-language rewrite;
- clinical advice, diagnosis, treatment, or dosage functionality.

## Next implementation vertical slice

Implement only:

`Source -> CandidateFact -> User Review -> CanonicalRecord -> TimelineEvent -> VisitBrief`

The first fact type is medication data from manual entry or an optional
text-based source. The slice must be deterministic, source-linked,
user-correctable, and testable without an external LLM. It must include
correction and rejection states and a deterministic Visit Brief.
