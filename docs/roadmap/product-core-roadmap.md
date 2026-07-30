# Product Core Roadmap

This roadmap describes the next implementation sequence without speculative
dates or estimates. It is subordinate to
[ADR 0001](../adr/0001-opencare-product-direction.md).

## Phase 1: first vertical slice

### Objective

Prove the core user-owned lifecycle for one non-genetic fact type:

`Source -> CandidateFact -> User Review -> CanonicalRecord -> TimelineEvent -> VisitBrief`

### Deliverables

- medication fact type only;
- manual medication entry;
- optional text-based source;
- source registration and immutable source reference;
- candidate medication facts with provenance;
- explicit review, correction, confirmation, and rejection states;
- canonical confirmed medication records;
- deterministic timeline event generation;
- deterministic Visit Brief generation;
- source references in every brief claim;
- repository interfaces that preserve a later SQLite boundary;
- standard-library SQLite persistence with explicit migration bootstrap;
- immutable local source publication and corruption checks;
- tests for lifecycle, provenance, correction, rejection, and rebuild behavior.

### Non-goals

- OCR;
- genetics or PGx expansion;
- external LLM requirement;
- multi-user SaaS;
- family permissions;
- autonomous canonical-record mutation;
- broad document ingestion;
- UI redesign;
- deployment changes.

### Acceptance criteria

- A user can create a medication record without editing runtime JSON directly.
- A text source can produce a candidate medication fact without making it
  canonical automatically.
- Review can confirm, correct, or reject the candidate.
- Only confirmed or manually entered canonical records appear in the timeline.
- The Visit Brief is deterministic and source-linked.
- Rebuilding derived views does not change canonical records.
- No external provider is required.
- `OPENCARE_PRODUCT_DB_PATH` and `OPENCARE_SOURCE_DIR` configure the local
  persistence boundary.

### Phase 1A status

The medication-only UI-free foundation is implemented under
`app/product_core/`. Confirmation creates the canonical medication record and
its `medication_confirmed` timeline event in one Unit of Work transaction.
Correction, rejection, idempotent confirmation, source deduplication, source
corruption detection, and Visit Brief selection rules are covered by focused
tests. Deactivation, HTTP routes, UI, people, and non-medication fact types
remain deferred.

### Phase 1B status

The medication-only lifecycle is exposed through the versioned
`/api/product-core/v1` JSON API. The adapter provides source registration,
candidate detail/list/review, canonical medication and timeline reads, and
deterministic Visit Brief generation. Startup migrations run through the
existing FastAPI lifespan; public schemas hide storage paths and normalized
comparison values; review timestamps are controlled by the server clock; and
Product Core errors use a scoped stable JSON envelope. The API has no UI,
people table, per-person authorization, source download, extraction, or
provider/model calls.

### Validation requirements

- focused unit tests for each state transition;
- integration test for the complete lifecycle;
- provenance tests for source linkage and missing sources;
- regression tests proving rejected candidates do not become canonical;
- `pytest`, Ruff, mypy, and existing evals;
- `git diff --check`.

### Major risks

- confusing candidate facts with confirmed records;
- allowing AI output to mutate canonical data;
- losing source identity during correction;
- creating a persistence abstraction that bypasses future SQLite ownership;
- making the Visit Brief appear clinical or prescriptive.

## Phase 1C: Visit Preparation UI

### Objective

Expose the validated medication lifecycle and deterministic Visit Brief API
through a minimal Visit Preparation UI without moving lifecycle authority out
of Product Core services.

Phase 1C serves `/workspace` as the primary entry point through external static
assets that call only the versioned Product Core API; `/chat` remains supporting.

### Non-goals

- broader fact types;
- document upload or extraction;
- family permissions;
- clinical advice or provider calls;
- deployment changes.

## Phase 1D: persistent people profiles

Phase 1D adds active people profiles, explicit workspace selection, and a migration
that backfills existing opaque IDs as non-medical `Imported profile` records before
foreign keys are enforced. The shared password gate remains installation-wide, so this
does not add accounts, family relationships, or authorization.

## Phase 1E-A: persistent Visits and Visit Questions

Phase 1E-A adds Person-scoped persisted Visits and user-authored Visit Questions
to the existing SQLite Product Core. Questions have explicit contiguous ordering
within a Visit and may be edited, moved, or removed. The workspace keeps profile
and Visit selection in page memory only.

This phase does not persist or change the deterministic Visit Brief, add an
evidence/source drawer, export or backup, identity or caregiver permissions,
family relationships, or AI-generated questions or answers.

## Phase 1E-B: persisted editable Visit Briefs

Phase 1E-B is implemented according to [ADR 0003](../adr/0003-persisted-visit-briefs.md)
and the [Visit Brief lifecycle](../architecture/visit-brief-lifecycle.md). One
persisted Brief belongs to a Visit; immutable revisions retain selected confirmed
medication evidence and ordered Visit Questions. Deterministic Markdown,
separately editable preparation notes, restoration, integrity checks, derived
stale state, and metadata-only export auditing are implemented.

The implementation calculates freshness from snapshots and live evidence; it
does not overwrite user edits during regeneration. Evidence, revisions, and
current-pointer changes are transaction-bound and source-linked. The phase
does not add JSON vault export, backup/recovery, PDF, upload/OCR, AI or external
providers, identity/permissions, family relationships, Sentient work, or
EvoSkill.

## Phase 1F: vault export, installation backup, and recovery

Phase 1F is defined in [ADR 0004](../adr/0004-vault-export-backup-recovery.md).
Phase 1F-A is implemented: a deterministic Person-scoped portable ZIP contains
the supported Product Core graph, only reachable immutable sources, canonical
JSON, manifest checksums, and a Workspace download warning. It verifies source
payloads and persisted Brief integrity before responding, creates no persistent
artifact, and does not add import or encryption.

Installation backup and fail-closed recovery remain proposed. Installation
backup uses a consistent SQLite snapshot and all source payloads referenced by
that snapshot.

The implementation sequence is 1F-A portable export, 1F-B backup/verification,
and 1F-C empty-target recovery with rollback. It does not add portable import,
merge, cloud storage, schedules, encryption, sharing, credentials, Identity,
family access, uploads/OCR or deployment changes.

## Phase 2: broader workspace

### Objective

Extend the verified lifecycle to the minimum useful non-genetic workspace.

### Deliverables

- additional fact types;
- limited document ingest;
- review inbox;
- improved timeline;
- visit preparation UI;
- export and backup.

### Non-goals

- genetics expansion;
- autonomous medical advice;
- external LLM dependence;
- multi-tenant SaaS;
- caregiver permissions before an explicit authorization model exists.

### Acceptance criteria

- Each new fact type has the same source, review, canonical, and derived-view
  boundaries as medications.
- Ingested documents remain recoverable as immutable sources.
- Review status is visible and auditable.
- Timeline and Visit Brief outputs can be rebuilt from canonical data.
- Export and backup preserve sources, canonical records, provenance, and
  explicit unsupported states.

### Validation requirements

- per-fact-type unit and integration tests;
- import/export round-trip tests;
- backup restore tests;
- provenance completeness checks;
- browser or HTTP smoke tests for the review and visit-preparation flows;
- full repository validation.

### Major risks

- broad ingest creating unsupported extraction claims;
- accidental loss of raw sources during export or migration;
- UI implying that recorded context is clinical interpretation;
- scope expansion before the medication lifecycle is stable.

## Phase 3: constrained assistance

### Objective

Add bounded assistance after the deterministic workspace is usable without AI.

### Deliverables

- query-scoped AI assistance;
- explicit provider consent;
- context preview before external transmission;
- family caregiver permissions;
- read-only agent tools;
- improved ingestion adapters.

### Non-goals

- diagnosis;
- treatment or dosage recommendation;
- autonomous record mutation;
- broad chatbot positioning;
- multi-tenant SaaS before self-hosted validation.

### Acceptance criteria

- Provider use is opt-in and visible.
- The user can inspect the exact context selected for an AI request.
- AI output remains an artifact or view and cannot write canonical records.
- Agent tools are read-only and scope-checked.
- Family permissions are enforced at the tool and data boundary.
- Unsupported and uncertain outputs remain explicit.

### Validation requirements

- provider consent and context-preview tests;
- authorization tests for every read-only tool;
- tests proving AI output cannot mutate canonical data;
- privacy tests for paths, secrets, and raw sources;
- deterministic fallback tests when a provider is unavailable;
- full repository validation and threat-model review.

### Major risks

- transmitting more health context than the query requires;
- treating fluent AI output as a canonical record;
- permission failures across family members;
- increasing operational complexity before the local workflow is trustworthy.
