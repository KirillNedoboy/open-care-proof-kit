# ADR 0003: Persisted Visit Briefs and immutable revisions

- Status: Proposed
- Date: 2026-07-30
- Decision owners: OpenCare maintainers

## Context

Phase 1E-A introduced persistent Person-scoped Visits and ordered
VisitQuestions. The current `VisitBriefService` is intentionally different: it
creates a deterministic, transient Markdown document from active canonical
medication records. It accepts a Person ID and a temporary title, does not use
a persisted Visit or its questions, and does not save user edits.

The next lifecycle must connect a selected Visit, its user-authored questions,
and confirmed evidence without treating a Brief as a medical record or letting
later generation replace text written by the user. Existing canonical records,
timeline events, sources, and candidate facts retain their present ownership.
They are not revised by Brief operations.

## Decision

### Brief ownership and revisions

Each Visit has at most one logical `VisitBrief`. A Brief has an immutable,
append-only sequence of numbered `VisitBriefRevision` records and a nullable
`current_revision_id` pointer. A newly initialized Brief may have no revision.

A revision has one of three origins:

- `deterministic_generation` for the first generated draft;
- `regeneration` for later drafts generated from current selections;
- `user_edit` for a new revision containing edited preparation notes.

Generation always appends a revision. It never replaces an existing generated
or user-edited revision. Saving an edit also appends a revision; it does not
update a row in place. Previous revisions remain readable. Restoring a previous
revision moves `current_revision_id` to that existing revision after a
concurrency check; it does not create a copy. A later edit from a restored
revision becomes a new `user_edit` revision with that revision as its parent.

Hard deletion, revocation, and archival controls are deferred. A Visit Brief is
a preparation artifact, not a clinical approval or a canonical record.

### Content and reproducibility

A revision stores both a structured content snapshot and the Markdown rendered
from it. The structured snapshot has a versioned schema and separates
system-owned sections from the single user-editable preparation-notes section.
System-owned sections include Visit metadata, selected evidence, derived
timeline events, Visit Questions, source references, known gaps, and boundary
text. The user cannot change source-linked facts by editing Brief notes; they
change those facts through their original Product Core lifecycle and generate a
new revision when ready.

Every revision records:

- `content_schema_version`, the version of its persisted JSON snapshot;
- `render_version`, the deterministic Markdown renderer version;
- `content_hash`, the SHA-256 digest of a canonical UTF-8 JSON envelope;
- the rendered Markdown used for copy/download.

The canonical JSON envelope contains `content_schema_version`, the complete
structured snapshot, explicit evidence order, and user-authored notes. Object
keys are sorted and encoded with fixed JSON separators. The rendered Markdown
and the calculated live state are excluded from the hash. At read or export,
the service recomputes the hash before returning the artifact. A mismatch is an
integrity failure, not a reason to return altered content.

New snapshot or renderer formats apply only to newly created revisions. Readers
retain compatibility adapters and deterministic renderers for supported
historical versions. Database migrations may change storage layout but must not
rewrite historical content solely to advance a schema or render version.

### Evidence boundaries

The only independently selectable evidence in this MVP is an active confirmed
canonical medication record belonging to the Person who owns the Visit.
Pending, corrected, and rejected candidates are ineligible. Each selection
retains the canonical record ID, its source reference, confirmation metadata,
and a display/provenance snapshot.

Timeline events are not selected independently. The renderer derives the
events associated with selected canonical records, snapshots them in
`event_at, id` order, and includes their source references. Source references
are deduplicated in selected-evidence order. The current source model has no
source-span representation, so source spans are not introduced. Raw source
content and local source paths are never copied into Brief content or audit
events.

Questions are included in their stable Visit position order. They are
user-authored planning context, not clinical evidence.

### Derived freshness state

`current`, `stale`, and `unavailable` are calculated at read time; no mutable
stale flag is stored. A revision snapshot records the Visit `updated_at`, an
ordered question fingerprint (`question_id`, position, `updated_at`, text
hash), selected canonical/source/timeline fingerprints, and an
`evidence_selection_fingerprint`.

- `unavailable` takes precedence when selected evidence is missing, inactive,
  corrupt, unavailable, or belongs to a different Person.
- `stale` applies when all selected evidence remains available but a live
  Visit, ordered question collection, selected canonical record, derived
  timeline event, source fingerprint, or selection fingerprint differs from
  the snapshot.
- `current` applies only when those values still match.

Changing a Visit, a question, or evidence does not mutate historical content.
It can change this calculated state. A stale revision may still receive a new
user-notes revision, which retains its source snapshot; regeneration is the
explicit operation that produces a fresh system snapshot.

### Atomicity and concurrency

Revision creation, evidence insertion, metadata-only audit insertion, and the
current-pointer update run in one `BEGIN IMMEDIATE` Unit of Work transaction.
The transaction reads and checks the supplied current revision number before
writing. A changed pointer returns a `409` conflict and writes no revision.

The future `visit_briefs.current_revision_id` is nullable and references
`visit_brief_revisions`. Initialization writes a NULL pointer. Revision
creation inserts the revision and its selections, verifies that the target
belongs to the Brief, then updates the pointer. Foreign keys remain enabled;
deferred foreign-key checking is used only inside the transaction where it is
needed. Restore uses the same `IMMEDIATE` transaction and ownership check.

### Audit

The repository's current `app/agent/audit.py` emits logging records for guarded
chat. Its required fields describe a provider, policy decision, citation list,
question length, and latency. It is neither a Product Core Unit of Work nor a
durable transaction-bound audit mechanism, so it cannot truthfully represent
Brief lifecycle events.

Phase 1E-B should therefore add a narrow Product Core Brief audit store in the
same SQLite transaction boundary. It records entity identifiers, action,
revision number when applicable, timestamp, outcome, and a bounded reason code
for initialization, generation, evidence selection, save, current-pointer
change, export, and stale-write conflict. It stores no Brief Markdown, source
text, medication notes, question text, names, browser state, or session data.

## Rejected alternatives

- Multiple independent Brief documents per Visit. This duplicates planning
  context and leaves no clear current document.
- Mutable rows for generated or edited drafts. This loses a reliable history
  and permits silent overwrite.
- Markdown as the only persisted representation. It would require parsing
  arbitrary user text to support future structured or HTML rendering.
- Direct TimelineEvent selection. Timeline events are already derived from the
  selected canonical records and would create duplicate, confusing evidence
  choices.
- A persistent stale boolean. It cannot explain why a revision changed state
  or remain correct when evidence becomes available again.
- Reusing Agent audit logging for Product Core Brief actions. Its schema and
  transaction model are incompatible with the required lifecycle guarantees.

## Consequences

The next implementation phase will add SQLite persistence, repositories,
services, public API schemas, workspace controls, and tests for this bounded
lifecycle. The transient `POST /people/{person_id}/visit-briefs:generate`
endpoint and its current workspace behavior remain unchanged until that phase
is implemented.

The next migration will be version 4. It must support fresh databases and
upgrade from version 3 transactionally, retain all existing data, enforce
foreign keys and ordering constraints, and never invent historical persisted
Briefs from transient output.

## Explicit non-goals

- JSON vault export, backup, or recovery;
- PDF generation;
- upload, extraction, or OCR;
- AI-generated Briefs, questions, or answers;
- external providers;
- identity, caregiver permissions, or family relationships;
- Sentient adapter or EvoSkill benchmark;
- changes to PGx/genetics, medication lifecycle semantics, shared password
  gate, dependencies, or deployment.
