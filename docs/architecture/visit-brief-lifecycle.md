# Persisted Visit Brief lifecycle

## Status and scope

Phase 1E-B implements this Visit-scoped persisted lifecycle in Product Core
schema v4. People, Visits, Questions, immutable Brief revisions, evidence
selections, and metadata-only audit events are transaction-bound. The existing
Person-scoped transient Brief endpoint remains unchanged for compatibility.

The target flow is:

```text
Person -> Visit -> ordered Visit Questions -> confirmed medication selections
       -> deterministic Brief revision -> optional user notes revision
       -> current revision Markdown copy/download
```

The Brief remains a clinician-discussion preparation document. It does not
interpret evidence, make medical recommendations, or write to canonical health
records.

## Logical model

`Visit` remains the persisted appointment-planning container. `VisitQuestion`
remains a user-authored, ordered child of that Visit. A `VisitBrief` is one
logical document for one Visit. Its `VisitBriefRevision` records are immutable
snapshots, not revisions of a medication, timeline event, source, or candidate.

Each revision contains:

- identity and monotonic revision number;
- origin and optional parent revision;
- Visit snapshot;
- ordered question snapshot;
- selected canonical-medication and source-provenance snapshots;
- derived timeline-event snapshots;
- user-authored preparation notes;
- `content_schema_version`, `render_version`, and `content_hash`;
- rendered Markdown and creation time.

The content snapshot is structured JSON. Markdown is stored as the exact export
artifact, while structured content remains the source for future deterministic
HTML rendering. User-provided notes are data, not Markdown to be parsed into
domain fields.

## Evidence selection and deterministic rendering

The evidence picker lists only active confirmed canonical medication records
for the selected Visit's Person. A selected record provides its label,
schedule/note snapshot, confirmation time, source ID, source type, source
content hash, and provenance method. The selection is ordered deterministically
by the canonical-record ordering already used by Product Core; duplicate IDs
are invalid.

For each selected record, the Brief derives related Timeline Events. Those
events are ordered by `event_at, id`. Source references are deduplicated in
evidence-selection order. Questions are rendered by `position, question_id`.
The minimum Brief sections are:

1. Visit metadata.
2. Selected confirmed medications.
3. Derived timeline changes.
4. Visit Questions.
5. User preparation notes.
6. Evidence references and unavailable/unknown information.
7. Revision and generated-at metadata plus the non-advisory boundary.

No source span is represented because the current source model does not expose
one. Raw source files, source text, and filesystem locations are not Brief
content.

## Version, hash, and freshness rules

`content_schema_version` selects the content reader and compatibility adapter.
`render_version` selects an immutable deterministic renderer. A renderer takes
only the versioned structured snapshot and produces Markdown; it does not query
live health data. The stored Markdown is checked by rendering the same snapshot
with its declared renderer version. Unsupported historic versions fail closed
until a compatible renderer is supplied.

`content_hash` is SHA-256 over canonical UTF-8 JSON of:

```text
{
  content_schema_version,
  visit_snapshot,
  question_snapshot,
  evidence_selection_snapshot,
  derived_timeline_snapshot,
  user_preparation_notes,
  fixed_boundary_content
}
```

Canonical JSON uses sorted keys and fixed separators. The Markdown string,
`render_version`, timestamps generated outside the content snapshot, and
calculated freshness state do not affect the digest. Hash verification is
required before a revision is displayed or exported.

Freshness is a live calculated response property, never a stored flag:

| State | Condition |
|---|---|
| `current` | Visit, ordered question fingerprint, selected-record/source/timeline fingerprints, and evidence-selection fingerprint all match their snapshots. |
| `stale` | All selected evidence remains eligible and available, but one or more saved and live fingerprints differ. |
| `unavailable` | A selected record, its source, or a derived event is missing, inactive, corrupt, unavailable, or belongs to another Person. This overrides `stale`. |

The question fingerprint includes IDs, positions, `updated_at`, and text hashes;
the Visit fingerprint includes `visit_id` and `updated_at`. Evidence fingerprints
include stable IDs and snapshot fields needed to detect change. The selection
fingerprint is a canonical hash of the ordered evidence identifiers and their
provenance fingerprints. Editing a question, changing a Visit, deactivating a
record, or changing a source can therefore make an existing revision stale or
unavailable without rewriting it. If the live state again matches the snapshot,
the revision is current again.

## Writes, revision history, and concurrency

Initialize creates the single Brief for a Visit with no current revision.
Generate validates live eligibility and creates a deterministic revision. Save
notes creates a `user_edit` revision from an existing immutable base snapshot.
Regenerate validates a newly supplied selection and creates a `regeneration`
revision. None of these operations overwrite an existing revision.

Every revision-creating operation requires the caller's
`expected_current_revision_number`. Within an `IMMEDIATE` transaction the
service reads the Brief, verifies the expected pointer, creates the revision,
inserts ordered evidence, writes the audit event, and changes the pointer. A
stale expectation returns `409` and changes nothing. Restore uses the same
transaction: it verifies the expected pointer and that the requested historical
revision belongs to the Brief before changing only the pointer.

The future schema uses a nullable `current_revision_id` FK on `visit_briefs`.
The brief is inserted with NULL, then the new revision and evidence rows are
inserted, and the pointer is updated before commit. FK checks remain enabled;
deferred checking is scoped to the transaction that needs it. Application
ownership validation prevents a valid revision from another Brief being made
current.

## Proposed API and workspace contract

All operations stay under `/api/product-core/v1` and reuse public schemas and
the Product Core error envelope. Browser-visible `/workspace` URLs, query
parameters, and history contain no Product Core IDs or user values. Internal
same-origin API requests may use `visit_id` and revision identifiers in resource
paths.

| Operation | Proposed behavior |
|---|---|
| `POST /visits/{visit_id}/brief` | Initialize once: `201`; existing Brief: `409`. |
| `GET /visits/{visit_id}/brief` | Brief metadata, current pointer, calculated state: `200`. |
| `GET /visits/{visit_id}/brief/revisions` | Ordered revision metadata: `200`. |
| `GET /visits/{visit_id}/brief/revisions/{revision_number}` | One verified snapshot and Markdown: `200`. |
| `GET /visits/{visit_id}/brief/evidence` | Eligible records and derived-preview metadata: `200`. |
| `POST /visits/{visit_id}/brief/evidence:validate` | Validates an explicit ordered selection: `200` or `422`. |
| `POST /visits/{visit_id}/brief/revisions:generate` | Creates deterministic or regeneration revision: `201`, `409`, or `422`. |
| `POST /visits/{visit_id}/brief/revisions:user-edit` | Creates a notes revision from a base/current revision: `201` or `409`. |
| `POST /visits/{visit_id}/brief/current` | Restores a revision as current after optimistic-concurrency validation: `200` or `409`. |
| `POST /visits/{visit_id}/brief/current:export` | Records an export event and returns verified current Markdown: `200`. |

Unknown Visit, Brief, or revision returns `404`. Invalid payloads and invalid,
cross-Person, duplicate, inactive, unconfirmed, or unavailable selections return
`422`. A changed expected revision returns `409`. Public responses exclude
SQLite implementation details, raw source text, source paths, and internal
normalization fields.

The workspace keeps selected Person, Visit, current revision, draft notes, and
selection only in JavaScript memory. It provides accessible evidence selection,
generation, review of evidence links, notes editing, save/cancel, revision
history, comparison, restore, and copy/download. It warns before discarding
unsaved notes, uses status regions and focus handling for conflicts, and never
uses browser storage, native prompts, unsafe HTML rendering, or automatic
regeneration. Existing medication, Review Inbox, timeline, Visit, question,
brief, root redirect, and `/chat` workflows remain available.

## Persistence and audit boundary

Migration v4 will add `visit_briefs`, `visit_brief_revisions`, and ordered
`visit_brief_evidence_selections`, with foreign keys, unique revision/order
constraints, and indexes for Visit lookup, Brief history, and evidence listing.
It will support new databases and atomic v3 upgrade under concurrent startup.
Failure rolls back the whole migration. No transient output is backfilled,
because no historical Brief was persisted.

The existing agent audit logger cannot represent this lifecycle truthfully or
atomically. Phase 1E-B therefore needs a minimal Product Core audit store in the
same SQLite Unit of Work. It records only identifiers, action, revision number,
timestamp, outcome, and bounded reason code for initialization, generation,
selection, save, restore/current-pointer changes, export, and stale conflicts.
It excludes Markdown, source content, medication notes, questions, names, and
browser/session data.

## Required implementation tests

- Fresh v4 migration, v3 upgrade preservation, rollback, FK enforcement, and
  concurrent startup.
- Deterministic content/hash/rendering, supported historical versions, evidence
  eligibility, unavailable evidence, immutable revisions, regeneration after
  edits, stale conflicts, restore, and Person/Visit isolation.
- Full API lifecycle, public schema boundaries, error envelopes, conflicts,
  OpenAPI, and verified export.
- Workspace evidence picker, notes edit/save, revision history, unsaved-change
  warning, no unsafe browser APIs/storage/visible URL identifiers, and existing
  medication/Visit/chat behavior.

JSON vault export, backup/recovery, PDF, upload/OCR, AI and external providers,
identity/permissions, family relationships, Sentient work, and EvoSkill remain
outside Phase 1E-B.
