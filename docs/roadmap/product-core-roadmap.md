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
