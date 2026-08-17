# P1: Evidence-Grounded Ingest (Conditions + Labs)

- Status: Proposed (design checkpoint — no implementation yet)
- Branch: `codex/p1-evidence-grounded-ingest` (from `e8d2d680ea07cf3fb0b1712618bfc641aad2a606`)
- Decision owners: OpenCare maintainers
- Scope: generalize the existing medication-only evidence lifecycle (Source → CandidateFact → human review → canonical record → timeline/downstream) into ONE reusable lifecycle for three fact families — `medication`, `condition`, `lab` — with typed, strongly validated detail, preserving full medication backward compatibility.

This document is the implementation contract for P1. Every acceptance criterion at the end is judged against the concrete decisions below.

---

## 1. Problem

OpenCare Product Core implements a single medication-only evidence lifecycle:

```
immutable Source → medication CandidateFact → human review
  (pending/confirmed/corrected/rejected) → canonical medication record
  → timeline events → Visit Brief evidence
```

The lifecycle is correct but structurally medication-shaped:

- `CandidateFact` carries medication columns (`display_name`, `normalized_name`, `schedule_text`, `note`) and `fact_type` is constrained to exactly `'medication'` (DB CHECK).
- The canonical table is named `canonical_medication_records` and is the FK target of `timeline_events` and `visit_brief_evidence_selections`.
- Family Access scopes, the workspace, agent context, export, backup, verify, preflight, and recovery all assume medication-only records.

P1 generalizes this ONE lifecycle to `medication | condition | lab` with typed strongly-validated data while preserving medication behavior byte-for-byte at the API/behavior level. P1 adds **no** extraction, **no** OCR/upload, **no** FHIR, **no** diagnosis/treatment/dosage interpretation. Human review remains mandatory: no source becomes canonical by ingestion alone.

## 2. Goals

- One reusable lifecycle (source → candidate → review → canonical → timeline/downstream) for medication, condition, and lab facts; not three product architectures.
- Typed, strongly validated candidate and canonical detail for every fact family (Pydantic + SQLite CHECK constraints). No unvalidated arbitrary JSON blob as the domain model.
- Immutable source provenance for every candidate: reviewer-answerable "where did this fact come from".
- Full medication backward compatibility: existing People, Sources, candidates, canonical medications, timeline, Visits, Briefs, evidence selections, Family Access, G2 consents/receipts, audit — byte/semantically intact through migration v7.
- Family Access extension with **no silent privilege expansion** (the P1 security checkpoint).
- Deterministic P1 metrics and security counters with zero tolerance for lifecycle-violation counters.

## 3. Non-goals (explicitly out of scope for P1)

- PDF upload, browser upload, OCR, image extraction, or model extraction of any kind.
- FHIR / HL7 / EHR synchronization or import adapters; new provider adapters.
- Genetics ingestion or PGx expansion.
- Diagnosis; treatment or dosage recommendation; condition "resolved/active" inference.
- Reference-range interpretation; unit conversion; derived ranges; high/low classification; abnormality inference.
- MCP adapters; EvoSkill; any new Trust Envelope contract version.
- P2 UX redesign of the workspace.
- Only manual structured ingest and plain-text ingest are added; source registration never implies confirmation.

## 4. Current state analysis — the eight coupling points

All line numbers are on `main`/`e8d2d680` unless noted.

### 4.1 Medication-specific schema coupling

- `app/product_core/models.py:10` — `FactType = Literal["medication"]`; the type is a single literal.
- `app/product_core/models.py:95-124` — `CandidateFact` embeds medication columns `display_name`, `normalized_name`, `schedule_text`, `note`, and its validator at `:120` hard-requires `normalized_name == normalize_medication_name(display_name)`.
- `app/product_core/models.py:131-154` — `CanonicalMedicationRecord` repeats the same medication columns and validator (`:152`).
- `app/product_core/models.py:303-317` — `VisitBriefMedication`; `VisitBrief.records: list[VisitBriefMedication]` (`:321`) makes even the transient Brief medication-only.
- `app/product_core/migrations.py:40` — `fact_type TEXT NOT NULL CHECK (fact_type = 'medication')`; `:61` — `canonical_medication_records` table; `:146` — same check in the v2 rebuild.

### 4.2 Candidate lifecycle coupling

- `app/product_core/services.py:477` — `MedicationLifecycleService` is the only lifecycle; `create_candidate` (`:489`), `confirm` (`:546`), `correct` (`:602`), `reject` (`:650`) all build medication-typed models and medication titles (`:434` `"Medication confirmed: …"`).
- `app/product_core/services.py:333-340` — the manual source payload is medication-shaped: `{"schema_version": 1, "source_type": "manual_entry", "medication": {…}}`.
- `app/product_core/repositories.py:280-299` — `SQLiteCandidateRepository.insert` writes medication columns; `_candidate_from_row` (`:745-765`) reads them unconditionally.

### 4.3 Canonical-record coupling

- `app/product_core/repositories.py:303-350` — `SQLiteCanonicalRepository` is bound to `canonical_medication_records` by table name and medication columns.
- `app/product_core/services.py:415-436` — `confirm` constructs a `CanonicalMedicationRecord` from candidate medication fields and inserts it; canonical is the single point where the record's data is fixed.
- `app/product_core/migrations.py:61-74` — `canonical_medication_records` table with `candidate_id UNIQUE REFERENCES candidate_facts(id)`.

### 4.4 Timeline FK coupling

- `app/product_core/migrations.py:78` — `timeline_events.canonical_record_id TEXT NOT NULL REFERENCES canonical_medication_records(id)`; the FK target is the medication table.
- `app/product_core/models.py:157-172` — `TimelineEvent.canonical_record_id` typed against canonical records (medication by construction).
- `app/product_core/services.py:426-433` — `confirm` inserts the timeline event referencing the canonical medication record.
- `app/product_core/installation_backup.py:477-481` — backup validation joins `timeline_events → canonical_medication_records`.

### 4.5 Visit Brief evidence FK coupling

- `app/product_core/migrations.py:299-300` — `visit_brief_evidence_selections.canonical_record_id REFERENCES canonical_medication_records(id)`.
- `app/product_core/persisted_visit_briefs.py:43` — `CONTENT_SCHEMA_VERSION = 1`; `:130-137` — `list_eligible_evidence` enumerates `canonical_records.list_active_for_person` (medication repository); `:492` — content key `"medications"`; `:606-624` — `_evidence_preview` is typed `CanonicalMedicationRecord` and stamps `record_type: "confirmed_medication"`; `:422` — staleness reason `medication_or_source_changed`.

### 4.6 Export/recovery assumptions

- `app/product_core/portable_vault_export.py:30-31` — `PORTABLE_VAULT_FORMAT_VERSION = 2` and `PRODUCT_CORE_SCHEMA_VERSION = 5` (already stale vs. migration v6; P1 must fix to track `PRODUCT_MIGRATIONS[-1].version`); `:188` — vault key `"canonical_medication_records"`; `:315` — `_canonical_record_dto` medication-typed.
- `app/product_core/installation_backup.py:14-15` — `PRODUCT_CORE_SCHEMA_VERSION = PRODUCT_MIGRATIONS[-1].version` (auto-tracks the newest migration; will become 7); `:453-520` — `_validate_lifecycle` performs medication-specific joins (candidate↔source person, canonical↔candidate↔source, confirmed-has-canonical, timeline↔canonical↔source, evidence selection↔canonical↔source); `:549` — `_validate_family_access` validates stored scopes with `valid_role_scopes` (version-sensitive after P1).
- `app/product_core/installation_recovery.py:64-77, 144-210` — recovery validates `product_core_schema_version` against the backup's recorded version and re-verifies the restored installation with the same medication-specific snapshot validators.

### 4.7 Family Access scope assumptions

- `app/family_access/policy.py:7` — `POLICY_VERSION = "family-access-v1"`; `:9-31` — `OWNER_SCOPES` (exact-set equality at `:70`), `CAREGIVER_BASE_SCOPES` (subset at `:72-75`), `CAREGIVER_OPTIONAL_SCOPES`; medication-only record scopes (`medication.read`, `medication.write`).
- `app/product_core/api.py:216-217` — route scope map uses `medication.read`/`medication.write`; `:241-243` — `product_core_confirm_candidate` requires `("candidate.review", "medication.write")`.
- `app/product_core/access.py:303-313` — `_mutation_authorizer` runs the authorization + audit inside the mutation transaction (the audit-in-mutation pattern P1 preserves).
- `app/agent/trust_adapter.py:21` — `policy_version=POLICY_VERSION` is stamped into `AuthorizationSnapshot`; `AuthorizationSnapshot.policy_version` is a free-form bounded string (`app/agent_trust/models.py`), so a policy-generation change is **data**, not a trust-contract version change.

### 4.8 Agent-context assumptions

- `app/agent/context.py:64-110` — `build_product_core_agent_context` builds context items for `medication` (`:86-92`) and `timeline` only; no condition/lab items; the demo read model (`:34-36`) already has condition/lab shapes, but the live Product Core builder does not.
- `app/agent_trust/models.py:202-269` — `TrustEnvelope` contract version `opencare-trust-envelope/1`; `allowed_evidence_ids`/`allowed_fields` are opaque ID/field lists — record *types* are not enumerated by the contract, so adding condition/lab evidence items needs no contract change (see §19).

## 5. Binding lifecycle — one lifecycle, not three

P1 restructures the lifecycle into a single generic spine with typed detail:

```
immutable Source (manual_entry | plain_text)
  → generic CandidateFact (fact_type: medication | condition | lab)
  → human review decision (pending → confirmed | rejected | unsupported | corrected)
  → generic canonical record (canonical_records + typed detail)
  → timeline events (per fact type, deterministic titles)
  → Visit Brief / agent context / export (active canonical only)
```

- The **internal** lifecycle (state machine, transactions, invariants, repositories, queries, backup validation) is generic over `fact_type`. Fact-type-specific behavior lives only in (a) typed input models, (b) typed detail tables, (c) deterministic event titles, and (d) scope names.
- Medication **keeps compatibility APIs**: `MedicationLifecycleService` remains importable and the existing product-core API routes remain addressable with unchanged request/response shapes; internally they delegate to the generic lifecycle. Medication behaves identically to today (see §7 for the canonical truth rule).
- The workspace, Visit Brief, agent context, export, and backup read through the generic canonical repository and are therefore fact-type-agnostic.

## 6. Source invariant

- Sources stay immutable: byte-stable payloads under `OPENCARE_SOURCE_DIR`, publish-via-tempfile + hard-link (`services.py` `ImmutableSourceStore.publish`), fail-closed size/hash verification on every read (`_read_verified_source_file`, `read_for_portable_export`), no symlink/reparse components, safe-path resolution.
- Every canonical record traces to exactly one immutable `Source` via `canonical_records.source_id` (unchanged invariant).
- Existing hash/size/path verification stays fail-closed (any mismatch raises `SourceCorruptionError`; the operation is denied).
- Source types remain exactly `manual_entry` and `plain_text`.
- A versioned structured manual-source payload is introduced:
  - `schema_version: 1` (today): `{"schema_version": 1, "source_type": "manual_entry", "medication": {…}}` — **unchanged, byte-immutable**, used by legacy sources.
  - `schema_version: 2` (new): `{"schema_version": 2, "source_type": "manual_entry", "fact_type": "medication"|"condition"|"lab", "data": {…typed…}}`.
  - New payloads are introduced **without rewriting old source bytes**: registration writes a brand-new source row + file; legacy files are never touched. `media_type` stays `application/json`.
- Registration dedup stays exactly content-hash-based: `UNIQUE (person_id, source_type, content_hash)` (unchanged); an identical re-registration returns the existing source with `created=False` (existing semantics).

## 7. Candidate invariant — architecture choice

**Chosen: Architecture A — generic candidate/canonical base + typed detail tables (and typed Pydantic models).**

- Generic base `candidate_facts`: `id, person_id, source_id, fact_type (CHECK IN ('medication','condition','lab')), status, created_at, reviewed_at, predecessor_candidate_id, provenance_locator_json`. No medication columns on the base.
- Typed 1:1 detail tables keyed by `candidate_id`:
  - `candidate_medication_details`: `display_name, normalized_name, schedule_text, note`.
  - `candidate_condition_details`: `display_name, normalized_name, status_text, onset_date, note` (§13).
  - `candidate_lab_details`: `test_name, normalized_test_name, result_text, unit_text, reference_range_text, observed_date, source_flag_text, note` (§14).
- Each typed column gets DB `CHECK` constraints mirroring today's (`length(trim(display_name)) > 0`, date format checks, etc.) and every detail row requires exactly one base row via `candidate_id PRIMARY KEY REFERENCES candidate_facts(id)`.
- Pydantic models mirror the tables: a generic `CandidateFact` (base) + `MedicationCandidateDetail`, `ConditionCandidateDetail`, `LabCandidateDetail`, each with `extra="forbid"` and field validators (whitespace normalization, control-character rejection via existing `_validate_*` helpers, UTF-8 size caps).

**Why A over B (a single JSON `detail_json` column with app-layer validation):**

- B fails the requirement "typed detail must stay strongly validated (Pydantic + DB constraints)" — SQLite cannot constrain the shape of a JSON blob, so a `CHECK (json_valid(detail_json))` alone would not enforce per-field type/length/date-format rules; the DB would be a storage bag rather than an integrity boundary. A keeps every constraint in the schema, matches the existing codebase style (v1–v6 use typed columns + CHECKs everywhere, never JSON blobs for domain data; JSON is used only for provenance/consent/audit metadata), and makes row-level queries/indexes trivial.
- A is also the established rebuild pattern in this repo (migration v2 restructured tables the same way).
- **Why one lifecycle, not three copies:** the state machine, transactions, invariants (review-before-canonical, one-canonical-per-confirmed-candidate, correction lineage, person/source binding), repositories, backup validation, and scopes are fact-type-independent. Three parallel implementations would triple the security surface (three confirm paths, three export paths, three scope maps) and would drift; A guarantees the same code path enforces the same invariants for all three fact families.

## 8. Review state machine

`CandidateStatus = pending | confirmed | corrected | rejected | unsupported`.

- `pending` — created from a source; **no canonical record exists**.
- `confirmed` — human reviewer accepted. Exactly one canonical record is created atomically (§10). A confirmed candidate always has exactly one canonical (`candidate_id UNIQUE` + service invariant + backup validation).
- `rejected` — human reviewer decided the fact is wrong/not applicable from this source. No canonical record.
- `unsupported` — **new, added**: the reviewer decides the source does not sufficiently support the claimed fact (e.g., a candidate raised from a plain-text sentence the reviewer concludes does not state it). No canonical record. Distinct from `rejected` (fact is wrong) and from "never selected" (no candidate exists). Semantics are unambiguous: both are terminal reviewer decisions with the same persistence shape as `rejected` (reviewed_at set, no canonical), differing only in reason code.
- `corrected` — original candidate replaced via the explicit correction path (§11). Correction of a pending candidate marks it `corrected`; correction of a confirmed candidate keeps the confirmed candidate's status and expresses the replacement through the successor candidate + canonical supersession (see §11).
- Transitions: only `pending → confirmed | rejected | unsupported | corrected`. All terminal decisions require `reviewed_at`; `pending` requires `reviewed_at IS NULL` (existing CHECK preserved on the rebuilt table, extended with `unsupported`).

## 9. Canonical record invariant

Generic `canonical_records`:

```
id, person_id, candidate_id (UNIQUE → candidate_facts), source_id (→ sources),
fact_type (CHECK IN ('medication','condition','lab')),
confirmed_at, is_active (0|1), superseded_by_record_id (nullable FK, ≠ id)
CHECK (is_active = 1 AND superseded_by_record_id IS NULL)
   OR (is_active = 0 AND superseded_by_record_id IS NOT NULL)
```

- Typed 1:1 detail tables: `canonical_medication_details`, `canonical_condition_details`, `canonical_lab_details` (same columns as the candidate detail tables), each `record_id PRIMARY KEY REFERENCES canonical_records(id)`.
- **Exactly ONE canonical source of truth** for all fact families: the `canonical_records` tables. No competing old/new medication truth:
  - The old `canonical_medication_records` table is **removed** in v7 after its rows are copied into `canonical_records` + `canonical_medication_details`.
  - Medication compatibility exists only at the Python/API layer (`MedicationLifecycleService` facade, unchanged response models), which reads and writes through the generic tables. No retained compatibility table or view claims authority; if a read-only view is ever introduced it must be named/`CREATE VIEW ... AS SELECT` from `canonical_records` and documented as non-authoritative — P1 does not plan one, since the facade is provably a thin adapter over the single truth.
- Same invariant set as today, generalized: candidate↔source same person, canonical↔candidate↔source same person, confirmed⇒canonical, canonical⇒confirmed candidate, timeline⇒canonical, all re-checked by `_validate_lifecycle` in backup/verify and by the P1 migration tests.

## 10. Transactional review invariant

`confirm(candidate_id)` executes in ONE `BEGIN IMMEDIATE` transaction (pattern at `services.py:546-570` + `access.py:303-313`):

1. `authorize(uow.connection)` — server-derived Actor, scope checked **inside** the transaction against the assignment, and the allowed-audit row written on the same connection (existing `_mutation_authorizer`).
2. Candidate load + transition check (pending, no canonical yet).
3. Source integrity re-verification via `ImmutableSourceStore.read` (fail-closed) — the reviewer-visible provenance locator is validated against source bytes (§12).
4. Insert canonical record + typed detail, insert timeline event, update candidate status to `confirmed` with `reviewed_at = now` (deterministic system timestamp).
5. Commit; any failure → rollback of **everything** (authorization, transition, canonical, timeline, audit) by the existing `UnitOfWork.__exit__`.

Invariants enforced:

- No partial canonical record (single transaction).
- No canonical row without a reviewed (confirmed) candidate — service order + `candidate_id UNIQUE` + backup validation.
- No timeline event without a canonical record (`REFERENCES canonical_records(id)`).
- Duplicate confirmation cannot create a second canonical or timeline row: `candidate_id UNIQUE` + the existing short-circuit that returns the already-created canonical for a `confirmed` candidate. **Compatibility decision:** the idempotent-return semantics of today's `confirm` (asserted by `tests/test_product_core_lifecycle.py::test_confirmation_atomically_creates_canonical_and_timeline_and_is_idempotent`) are preserved for medication and extended identically to condition/lab; "duplicate confirmation rejected" is satisfied by the impossibility of a second canonical/timeline (UNIQUE + short-circuit), which is the load-bearing invariant. The `unauthorized_confirmation` and `canonical_without_review` counters stay zero.
- Authorization scope is fact-type-typed: `confirm` requires `candidate.review` plus `medication.write | condition.write | lab.write` matched to the candidate's `fact_type` (see §15).

## 11. Correction invariant

Two paths, both lineage-preserving and deterministic:

**A. Correct a pending candidate** (today's behavior, unchanged): original → status `corrected` + `reviewed_at`; successor candidate created (`predecessor_candidate_id = original.id`, `created_at = reviewed_at`), status `pending`. No canonical involved.

**B. Correct a confirmed canonical record** (new): `correct(confirmed_candidate)` creates a successor pending candidate (`predecessor_candidate_id = original.id`); the original candidate keeps status `confirmed` (it legitimately produced a canonical) and the existing canonical **stays active** until the successor is reviewed. When the successor is confirmed: old canonical → `is_active = 0`, `superseded_by_record_id = new.id`; new canonical active; deterministic timeline event `{fact_type}_corrected` referencing the new canonical. The previous canonical remains fully readable as historical state.

- Deterministic predecessor/successor: `predecessor_candidate_id` chain is queryable both directions; canonical records link to their candidate, so record lineage resolves through the chain.
- Previous canonical stays historical: never deleted, never rewritten (`is_active=0` + supersession link).
- Cross-Person correction forbidden: existing rule (replacement source must belong to the same person, `services.py:614-618`) is preserved; a successor candidate always inherits the original candidate's `person_id`; v7 adds a DB trigger rejecting a successor whose `person_id` differs from its predecessor's (SQLite CHECK cannot express cross-row equality; a trigger is required, and backup validation re-checks it).
- Predecessor cannot be self: `CHECK (predecessor_candidate_id IS NULL OR predecessor_candidate_id <> id)` preserved on the rebuilt table.
- No silent payload overwrite after review: reviewed candidates are never updated in place (only status/reviewed_at, and only along legal transitions); corrections always create a successor row.

## 12. Provenance contract

Every candidate answers, deterministically: **where did this fact come from?**

- `source_id` — the immutable source.
- `source.content_hash` (SHA-256), `source_type`, `size_bytes` — verified fail-closed at candidate creation and at every canonicalization/review.
- Person ownership — `candidate.person_id == source.person_id` (enforced at creation and by backup validation).
- Immutable source reference — `sources.relative_path` + archive path for export.
- **Deterministic locator** stored on the candidate in `provenance_locator_json`:
  - **Structured manual source (schema_version 2):** field/path locator — `{"kind": "structured_field", "path": "data.condition.display_name"}` (JSON-pointer style, exact). The path is validated against the immutable payload structure at candidate creation: the referenced field must exist and its value must equal the candidate's typed field value; a mismatch rejects the candidate (`provenance_mismatch_accepted` stays zero).
  - **Plain text source:** validated span locator — `{"kind": "span", "encoding": "utf-8", "start": N, "end": M}` with **Unicode code-point offsets** (Python `str` indexing semantics; explicitly NOT UTF-8 byte offsets). Validation rules: decode the hash-verified source bytes as UTF-8 (strict); `0 <= start < end <= len(text)`; the substring `text[start:end]` must equal the candidate's display/test-name field exactly (after the same trim applied at candidate creation); locator/source mismatch (source changed, offsets out of range, substring mismatch) → reject with `SourceCorruptionError`/`ValueError` and roll back. Span binds to the immutable source via its content hash.
  - **Legacy rows (schema_version 1 manual sources; plain-text rows created before P1):** the stored locator is derived deterministically where the payload structure is known and immutable — `{"kind":"structured_field","path":"medication"}` for legacy manual sources (structure is fixed and verifiable); `NULL` for legacy plain-text candidates. For `NULL`, provenance is **whole-source**: this is the permitted exception, justified by (a) legacy rows predate locator capture, (b) the complete source remains reviewer-accessible and hash-verified, and (c) no legacy source bytes are ever rewritten. New plain-text candidates MUST carry a span locator; new structured candidates MUST carry a field path.
- Never invent unsupported provenance: a locator that cannot be validated against the immutable source is rejected at creation; there is no "best-effort" provenance.

## 13. Condition data model

`condition` typed detail (candidate and canonical share the shape):

- `display_name` — reviewer-visible name, trimmed, non-empty, ≤ 200 chars, no control characters.
- `normalized_name` — `re.sub(r"\s+"," ", name).strip().casefold()` (same function as medication), used **only** for stable identity/display matching. No SNOMED/ICD/ontology mapping, no inference.
- `status_text` — optional; source text only, never a clinically normalized conclusion.
- `onset_date` — optional ISO date (`YYYY-MM-DD` with `date(date)=date` CHECK), a source record field, not an event timestamp.
- `note` — optional ≤ 2000 chars.

Explicit wording: a **recorded condition** / **source-backed condition record** — a source-backed RECORD, not an OpenCare diagnosis. No ICD/severity/prognosis/treatment/resolved-active inference. Workspace/UI/Brief copy uses "Recorded conditions"; nothing renders as a diagnosis.

## 14. Lab data model

`lab` typed detail (candidate and canonical share the shape):

- `test_name` — trimmed, non-empty, ≤ 200 chars.
- `normalized_test_name` — whitespace+casefold normalization, identity/display matching only.
- `result_text` — **source-preserving text**; the numeric value is NOT forced into a number field (a lab value may be text, a range, "<5", or blank); no unit parsing.
- `unit_text` — optional, source text.
- `reference_range_text` — optional, source text (no derived ranges).
- `observed_date` — optional ISO date, a source record field, not an event timestamp.
- `source_flag_text` — optional; ONLY a source-provided flag (e.g. "H", "high", "L") reproduced verbatim and **clearly marked source-provided** in every surface (`source_flag: "H (as reported)"` style). Never OpenCare-derived.
- `note` — optional ≤ 2000 chars.

No unit conversion, no derived reference ranges, no abnormality inference, no interpretation. Display wording: "Recent/selected lab records" with source-backed values only; no normal/abnormal/concerning/disease wording unless the source itself says so and it is visibly quoted as source-provided.

## 15. Duplication semantics

- No silent merging of separate evidence: two sources stating the same condition/lab/medication produce two distinct candidates and (if confirmed) two distinct canonical records. Canonical facts are never deduplicated by matching normalized names.
- Distinct sources remain distinguishable at every surface (source_id + locator always visible).
- The only dedup in the system remains content-hash dedup of an identical source registration: `UNIQUE (person_id, source_type, content_hash)` — two identical manual entries of the same text are one source; two different texts (even same fact) are two sources.

## 16. Migration plan — v7 only

**Rules: never edit v1–v6; v7 is the only new migration; the plan is additive-then-cutover following the repo's established v2 rebuild pattern.**

New v7 tables (created with `PRAGMA defer_foreign_keys=ON`):

1. `candidate_facts_v7` — generic base (§7) with `fact_type CHECK IN ('medication','condition','lab')`, status CHECK extended with `'unsupported'`, preserved reviewed_at invariants, preserved predecessor CHECK, new `provenance_locator_json`, new trigger: successor candidate `person_id == predecessor.person_id`.
2. `candidate_medication_details`, `candidate_condition_details`, `candidate_lab_details` — typed 1:1 detail (§7, §13, §14).
3. `canonical_records_v7` — generic base (§9) with `superseded_by_record_id`, plus `canonical_medication_details`, `canonical_condition_details`, `canonical_lab_details`.
4. `timeline_events_v7` — FK target moved to `canonical_records_v7`, new `fact_type` column, `UNIQUE (canonical_record_id, event_type)` preserved, index preserved.
5. `visit_brief_evidence_selections_v7` — FK target moved to `canonical_records_v7`, `PRIMARY KEY (revision_id, position)` and `UNIQUE (revision_id, canonical_record_id)` preserved.
6. `ALTER TABLE person_access_assignments ADD COLUMN scope_generation TEXT NOT NULL DEFAULT 'family-access-v1'` (new grants record their generation; existing rows default to v1 — see §15/§17 for why this is not a consent mutation).

Data copy (deterministic, inside the migration transaction):

- `candidate_facts_v7 ← candidate_facts` with `fact_type='medication'`, `provenance_locator_json` derived per §12 (legacy manual → `{"kind":"structured_field","path":"medication"}`; legacy plain-text → NULL) — computed by a Python step in the migration (the runner executes statements; v7's copy uses the same pattern as v2's parameterized people backfill, extended to allow a small deterministic Python data pass; no source bytes are touched).
- `candidate_medication_details ← candidate_facts` (display/normalized/schedule/note per row).
- `canonical_records_v7 ← canonical_medication_records` with `fact_type='medication'`, `superseded_by_record_id=NULL`.
- `canonical_medication_details ← canonical_medication_records`.
- `timeline_events_v7 ← timeline_events` with `fact_type='medication'`.
- `visit_brief_evidence_selections_v7 ← visit_brief_evidence_selections` (byte-identical rows).
- Rebuild indexes (`candidate_facts_person_status_idx`, canonical person-active index, `timeline_events_person_event_at_idx`, evidence revision-position index), then `DROP` the four old tables (`timeline_events`, `canonical_medication_records`, `candidate_facts`, `visit_brief_evidence_selections`), then `RENAME` the `_v7` tables into place.

Preserved byte/semantically intact: People, Sources (files + rows), medication candidates, canonical medications (now generic rows), timeline, Visits, Visit Questions, Visit Briefs, all Brief revisions (content_json/rendered_markdown/hashes untouched), evidence selections, Family Access tables (assignments gain one derived column), consent history (append-only triggers untouched, no UPDATE), access audit, G2 disclosure consents, execution receipts.

Required migration tests (all in `tests/test_product_core_migrations.py` or a new P1 migration test module):

- fresh → latest (v7 present, FK checks pass, expected table set).
- v1→latest, v2→latest, v3→latest, v4→latest, v5→latest, v6→latest — each with representative data (the existing per-version tests extended with the v7 leg).
- **Populated v6 fixture → v7**: Person; medication source (manual_entry); pending + reviewed (confirmed + rejected + corrected-chain) medication candidates; canonical medication; timeline event; Visit + Visit Question + persisted Brief with a medication evidence selection; actor/owner + caregiver assignment + consent history events; G2 consent + execution receipt; access audit rows. Assert after v7: all rows present with equal identity/values, FK checks empty, `foreign_key_check` empty, medication lifecycle still fully usable (create/confirm/correct/reject/list), Brief revisions still render, `_validate_lifecycle`-style integrity passes.
- Failure tests: a v7 copy that violates a constraint must roll back the whole migration and not record v7 in `schema_migrations` (existing rollback test pattern).
- No destructive migration without reconstruction + verification: the migration is transactional; the pre-migration DB is reconstructed from the backup path (operator `backup` → `recover`) — recovery tests must cover v7 DBs and populated v6→v7 backups.

## 17. Family Access evolution (SECURITY-CRITICAL — the P1 checkpoint)

### 17.1 Chosen strategy: versioned scope-set generations, stored per assignment, consent history untouched

- Introduce a **generation registry** in `app/family_access/policy.py`:

  - `family-access-v1` — the current sets, **frozen byte-identical** to today's constants (`OWNER_SCOPES_V1`, `CAREGIVER_BASE_SCOPES_V1`, `CAREGIVER_OPTIONAL_SCOPES_V1`). Adding no new scope strings changes v1 semantics.
  - `family-access-v2` (current) — v1 sets plus exactly `condition.read`, `condition.write`, `lab.read`, `lab.write` (owner set, caregiver base: read scopes; caregiver optional: write scopes). No other change.

- New column `person_access_assignments.scope_generation` records the generation under which an assignment was granted (DEFAULT `'family-access-v1'`; new grants write the current generation). Existing rows are backfilled by the column DEFAULT during migration — this is derived metadata on a mutable table (assignments are already mutated by revoke/revise), **not** a consent event change.

- `person_access_consent_history` is **not modified at all**: no new column, no UPDATE (the `consent_history_immutable_update/delete` triggers stay untouched). A consent event's generation is a **pure function of its stored `scopes_json`**: `valid_role_scopes_v1(role, scopes)` identifies v1 events exactly; anything containing a v2-only scope string is v2. Old durable consent events remain byte-identical and are never falsified.

- `valid_role_scopes(role, scopes, *, generation)` and `build_scopes(role, optional_scopes, *, generation)` become generation-aware; `PersonAccessPolicy.authorize` selects the generation from the assignment row and validates + checks `required_scope in scopes` against that generation's sets (`ALL_SCOPES` per generation; a v2-only scope string is not in any v1 set, so `authorize` denies by construction).

- **New grants** (bootstrap, person creation, `grant_assignment`, `issue_invitation`, invitation redemption, `revise_assignment`) use the current generation v2. Owner grants keep `confirm_full_owner_access` (unchanged). Caregiver optional scopes stay bounded to the v2 optional set.

- **Upgrade/revision is explicit**: an existing v1 assignment keeps v1 authority until the owner performs an explicit action. `revise_assignment` gains an explicit `policy_generation` parameter defaulting to the assignment's **current** generation (so a routine revision never silently moves the caregiver to v2); moving a v1 assignment to v2 is a separate explicit operation (`revise` with `policy_generation="family-access-v2"`), recorded as a new consent event (`event_type='revise'`, reason `caregiver_scope_generation_upgrade`) and surfaced in the UI with the full resulting scope set listed, including the new base scopes. Owner assignments upgrade via an explicit re-grant (`grant` with `confirm_full_owner_access=True`, reason `owner_generation_upgrade`); the old assignment is revoked in the same transaction, and both consent events remain in history.

### 17.2 Proof of no silent privilege expansion

1. **Consent history immutability**: `person_access_consent_history` is protected by `BEFORE UPDATE`/`BEFORE DELETE` triggers (v5); v7 adds no column and issues no UPDATE/DELETE against it. Old consent events are byte-identical; generation for old events is derived, never stored-by-mutation.
2. **Frozen v1 sets**: v1 scope sets are copied verbatim from today's constants; a v1 assignment's authority is exactly its stored `scopes_json` validated against v1 sets. v2-only scope strings (`condition.read/write`, `lab.read/write`) are absent from every v1 set, and `authorize` denies any `required_scope` not in the assignment's generation's `ALL_SCOPES`.
3. **No auto-migration of grants**: nothing in v7 or the runtime rewrites an assignment's `scopes_json`; the new column is derived metadata only. A caregiver granted in v1 cannot list, read, review, confirm, or export conditions/labs (no scope → 403; hidden Person → 404). An owner granted in v1 likewise cannot access conditions/labs until the explicit owner upgrade (§17.1) — full-access status of an old grant does not transfer to new capabilities.
4. **Revision cannot silently expand**: `revise_assignment` defaults to the assignment's current generation; upgrading to v2 requires an explicit request parameter, produces a new consent event with the complete resulting scope set, and (per existing rules) is performed only by an actor with `access.manage` on the Person. The owner's action is therefore explicit and audited, not silent.
5. **Audit**: every grant/revise/revoke/upgrade writes `access_audit_events` (existing `assignment.create` audit) and a consent event; the counter `unauthorized_confirmation` is wired to the fact-type-typed scope check.
6. **No admin bypass, membership ≠ grant**: `PersonAccessPolicy.authorize` ignores `is_installation_admin`, `has_family_membership`, `has_relationship`, `has_own_person_link` (they are `del`'d today); this behavior is preserved in the generation-aware policy.
7. **Revoked assignment immediate**: `_active_assignment_state` filters `is_active=1`; revocation is immediate for the new scopes exactly as today.

### 17.3 STOP-as-BLOCKED gate

If, during implementation, a correct generation-aware path cannot be produced without (a) mutating old consent events, (b) expanding any v1 grant's effective authority, or (c) weakening owner high-risk confirmation or caregiver optional-scope bounds, implementation STOPS and reports STOP-as-BLOCKED rather than weakening consent. This design is written so that the no-silent-expansion property is provable per §17.2; any deviation requires reopening this checkpoint.

### 17.4 Trust contract impact

`AuthorizationSnapshot.policy_version` is a bounded free-form string (`app/agent_trust/models.py`); the trust adapter stamps `POLICY_VERSION` (`trust_adapter.py:21`). v2 envelopes carry `"family-access-v2"`; v1 envelopes already stamped `"family-access-v1"` still validate. **No `opencare-trust-envelope/1` version change** (§19 keeps this explicit).

## 18. Workspace behavior

- The existing Person workspace (`app/templates/product_core_workspace.html`, `app/static/product_core_workspace.js`) gains, per fact family, without P2 redesign:
  - **Medications / Conditions / Labs sections**: add source-backed candidate (structured manual entry with fact-type-specific fields; plain-text registration unchanged), pending review list, provenance/source visibility (source_id, content hash, source type, and the locator where present), confirm / reject / **unsupported** / correct actions, active confirmed records, historical/superseded state.
  - Review inbox and history are fact-type-tagged and filterable by fact type and status.
  - **Source registration ≠ confirmation**: the "Add …" flows create sources + pending candidates only; nothing canonicalizes on upload/registration. The existing copy "New entries wait for review before they become confirmed records" is generalized.
- The workspace never renders OpenCare-derived medical interpretation: conditions render as "Recorded conditions" with source text only; labs render source-backed values with `source_flag_text` visibly marked as source-provided; no normal/abnormal/concerning/disease labels are ever computed.
- Scope gating follows the generation-aware policy: buttons for condition/lab operations are enabled only when the assignment grants the corresponding v2 scopes (hidden/disabled without disclosure, per §17).

## 19. Timeline behavior

- `timeline_events` gains `fact_type` and its FK moves to `canonical_records` (§16); the table stays generic.
- Deterministic event types: `{fact_type}_confirmed` and `{fact_type}_corrected` (medication keeps today's `medication_confirmed` string). Deterministic titles: `"Medication confirmed: {display_name}"` (unchanged), `"Condition confirmed: {display_name}"`, `"Lab confirmed: {test_name}"`, plus `_corrected` variants.
- Event identity keeps Person, canonical record, source, fact type/event type, deterministic title, and event timestamp semantics; `event_at = confirmation time` is the deterministic system timestamp (existing `clock()` contract).
- `onset_date` / `observed_date` are source record fields, never converted into event timestamps (unchanged principle, now explicit).
- Existing medication timeline behavior is preserved byte-for-byte (event rows for legacy medications are copied with `fact_type='medication'`; titles/types unchanged).

## 20. Visit Brief / downstream behavior

- Evidence eligibility (`list_eligible_evidence`, `_validated_selections`) extends to confirmed **active** canonical records of all three fact types, same Person, with provenance retained: the snapshot keeps `source_id`, `source_type`, `content_hash`, provenance method, `canonical_record_id`, `fact_type`, and typed fields (medication fields unchanged; condition: display_name/status_text/onset_date/note; lab: test_name/result_text/unit_text/reference_range_text/observed_date/source_flag_text/note).
- Content schema: `CONTENT_SCHEMA_VERSION` becomes **2** for new revisions with a generic `"records"` key (typed snapshots) replacing the medication-only `"medications"` key; the renderer emits "Recorded conditions" / "Recent/selected lab records" sections with neutral wording and visibly source-provided flags. Old v1 revisions remain readable: `verify_persisted_visit_brief_revision` accepts v1 (medication-only, unchanged rendering) and v2; **old immutable Brief revisions are never rewritten**, and medication-only Briefs remain valid.
- Staleness reasons generalize (`record_or_source_changed` replaces the medication-specific reason string; existing staleness semantics preserved).
- Transient `VisitBriefService` (`visit_brief.py`) stays medication-compatible as-is; the persisted-brief path is the P1 surface for condition/lab evidence.

## 21. Agent context integration

- Extend `build_product_core_agent_context` (`context.py:64-110`) to include confirmed **active** canonical condition and lab records as bounded evidence items: `ContextItem(kind="condition"|"lab", source_ids=[record.source_id], provenance_status="source_backed")`, active Person only, **confirmed canonical only** — no pending/rejected/unsupported, no unrelated Person, minimal text fields (condition: display_name/status_text; lab: test_name/result_text/unit_text/source_flag_text, with the source flag quoted as source-provided), matching the existing medication item pattern.
- **No new Trust Envelope contract version** for record types: `allowed_evidence_ids`/`allowed_fields` are opaque ID/field lists; `policy_version` is data (§17.4). If implementation reveals that generalizing the G1 controlled registry (PurposeId/ActionId/ToolId in `app/agent_trust/identifiers.py`) or the trust contract is required, that extension is **deferred explicitly** — Visit Brief + workspace integration suffice for P1 product completion, and the context builder is only extended if it generalizes cleanly under the existing envelope contract.

## 22. Export / recovery behavior

- Person export (`portable_vault_export.py`): `PORTABLE_VAULT_FORMAT_VERSION` → **3** (v2 meaning untouched — v2 remains the documented format for v2-era exports; there is no import path, so versioning is forward-only). New keys: `canonical_records` (generic base), `candidate_medication_details`, `candidate_condition_details`, `candidate_lab_details`, `canonical_condition_details`, `canonical_lab_details`, plus `provenance_locator` on candidate DTOs. The stale `PRODUCT_CORE_SCHEMA_VERSION = 5` constant is corrected to track `PRODUCT_MIGRATIONS[-1].version` (7).
  - Export includes only the authorized Person's entities: condition/lab candidates, canonical records, sources, timeline events, correction lineage (predecessor chains), provenance locators, plus the existing families/consent/assignment/actor scope. No unrelated Person data (existing `source_ids` collection + `person_id` checks already bound the graph).
- Backup/verify/preflight/recover (`installation_backup.py`, `installation_recovery.py`): schema version auto-tracks v7; `_validate_lifecycle` queries are generalized to the generic tables (candidate↔source, canonical↔candidate↔source, confirmed⇒canonical, timeline↔canonical↔source, evidence↔canonical↔source, predecessor same-person trigger check, provenance locator validation); `_validate_family_access` validates scopes generation-aware. Conditions/labs survive the round trip; permission state (including `scope_generation`) survives; sessions still do not survive (unchanged).

## 23. Failure semantics (transaction rollback enumeration)

- **Authorization failure** — `authorize(connection)` raises `ScopeForbiddenError`/`NotFoundError` inside the mutation transaction → rollback of all writes (none yet), denial audited best-effort on a separate connection; caller sees 403/404.
- **Constraint violation** — `sqlite3.IntegrityError` (e.g., duplicate canonical for a candidate, predecessor self-link, person mismatch trigger) → `UnitOfWork.__exit__` rolls back everything; no partial canonical, no timeline without canonical.
- **Audit failure** — the in-transaction allowed-audit insert raises (e.g., storage failure) → `AccessAuditUnavailableError` → rollback; mutation never commits without its audit (existing pattern, preserved for all new confirm/correct/unsupported/reject paths).
- **Source mismatch / corruption** — `PersonMismatchError` (source belongs to another Person) or `SourceCorruptionError` (hash/size/type verification failure) raised before any write or during canonicalization → rollback; the operation is denied and the failure counted (`source_integrity_failure_handled`).
- **Provenance mismatch** — locator validation failure (span out of range, substring mismatch, field-path mismatch) → reject the candidate/confirmation, roll back, count under `provenance_mismatch_accepted` (must stay zero).

## 24. Wrong Person threat scenario

Actors: **Alice** (Person), **Bob** (caregiver for Child with only explicitly granted scopes), **Carol** (unrelated). Requirements, all enforced through the existing `ProductCoreAccess` boundary generalized to condition/lab resources:

- Bob must never list Alice's/Carol's conditions or labs; never resolve guessed record IDs; never read provenance/source metadata; never review candidates; never confirm records; never access timeline events — without explicit authorization.
- Hidden resources: `404` with byte-identical response shape to a missing identifier (existing same-SQL-shape pattern, `access.py:_require_query_in_connection` + `tests/test_product_core_access_enforcement.py::test_hidden_and_missing_resource_checks_use_the_same_query_shape`), including condition/lab candidate and canonical ID lookups.
- Visible Person without scope: `403` (`ScopeForbiddenError`), e.g., Bob has `medication.read` but not `condition.read`.
- No hidden IDs/counts/names in list responses (existing people-list discipline extended to condition/lab lists; `"count"` never emitted).
- Server-derived Actor (session), no client-supplied Person ID grants authority (person_id is validated against the actor's assignments, never trusted alone).
- No admin bypass; membership is not a grant (policy ignores membership/relationship/link flags); revoked assignment is immediate (`is_active=1` filter).
- New route scope map entries follow the existing `_PERSON_PATH_SCOPES`/`_BODY_PERSON_SCOPES`/`_CANDIDATE_PATH_SCOPES` pattern with fact-type-typed scopes (§17).

## 25. P1 metrics and security counters

Deterministic lifecycle-correctness metrics (no clinical-quality benchmarks):

- `sources_registered` (total and by source_type)
- `candidates_created` / `candidates_confirmed` / `candidates_rejected` / `candidates_unsupported` / `candidates_corrected`
- `provenance_coverage` = candidates with a validated locator ÷ candidates (legacy whole-source rows counted with justification note)
- `canonical_records_with_valid_source_lineage` (canonical→candidate→source same-person, hash-verified)
- `source_integrity_failure_handled` (fail-closed denials, no bypass)
- `export_recovery_equivalence` (round-trip: export/backup → recover → identical state)

Security counters that **must be zero** (asserted in the P1 test suite):

- `canonical_without_review` (canonical whose candidate is not `confirmed`)
- `canonical_without_source`
- `cross_person_record_exposure`
- `cross_person_source_exposure`
- `unauthorized_confirmation` (confirm without the fact-type scope)
- `provenance_mismatch_accepted`

## 26. Acceptance criteria (spec, 35 items) → design mapping

1. Branch from `e8d2d680` — done this turn (`codex/p1-evidence-grounded-ingest` @ `e8d2d680`).
2. v1–v6 migrations unchanged — §16 (byte-identical; only v7 added).
3. v7 succeeds — §16 migration tests (fresh → latest).
4. Populated v6 → v7 succeeds — §16 fixture test.
5. Medication lifecycle unchanged — §5/§7/§8/§11 compatibility facade; existing lifecycle tests must pass unmodified.
6. Condition candidate + canonical models — §7/§13.
7. Lab candidate + canonical models — §7/§14.
8. Immutable source provenance mandatory — §6/§12.
9. Candidate/source Person mismatch rejected — §6/§23 (`PersonMismatchError`, creation-time check preserved).
10. Human review mandatory before canonicalization — §8/§10; no ingestion-path canonicalization (§18).
11. Rejected → no canonical — §8.
12. Unsupported → no canonical — §8 (new status; DB CHECK + tests).
13. Correction preserves lineage — §11 (predecessor chains; supersession for confirmed records).
14. Source corruption fails closed — §6/§23 (`SourceCorruptionError` → denial + counter).
15. Timeline supports all three fact types — §16/§19.
16. Workspace exposes reviewed condition/lab state — §18.
17. Provenance visible to reviewer — §12/§18 (source_id, hash, type, locator on candidate/record surfaces).
18. Family Access protects all new operations — §17 (generation-aware scopes on every new route).
19. No silent legacy permission expansion — §17.2 proof (checkpoint).
20. Wrong Person tests pass — §24 (extend `test_product_core_access_enforcement.py` for condition/lab resources).
21. Hidden record IDs 404 — §24.
22. Export Person-isolated — §22 (condition/lab entities bound to the authorized Person only).
23. Backup/recovery preserves new state — §22 (v7 schema, generalized validators, round-trip test).
24. Historical Visit Briefs remain valid — §20 (v1 revisions readable; old revisions never rewritten).
25. New Visit Brief can use condition/lab confirmed evidence — §20 (schema v2, eligibility includes all active canonicals).
26. Pending/rejected/unsupported facts never become agent evidence — §8/§21 (active canonical only).
27. No diagnosis/treatment/dosage interpretation — §3/§13/§14 (wording + no inference fields).
28. No OCR/upload/model extraction — §3 (non-goal; no route added).
29. G1–G5 trust/security tests remain green — §17.4/§21 (no contract version change; existing suites must pass).
30. Deterministic P1 reviewer passes — §25 counters; a deterministic reviewer (`python -m` style, mirroring `evals/g5_review.py`) over the P1 counters.
31. Documentation reflects actual capability truth — §27 (capability matrix + project status updated at implementation).
32. Worktree clean — step gate.
33. No remote mutation — step gate (no push/PR/tag this turn or during P1 without explicit request).

## 27. Open questions and risks

- **Owner upgrade UX**: an existing v1 owner grant cannot see conditions/labs until an explicit upgrade; the workspace must surface this clearly. Risk: owner confusion; mitigated by an explicit banner and one-tap upgrade with `confirm_full_owner_access`.
- **`unsupported` status**: added per §8; the reviewer guide must define the rejected/unsupported boundary (fact-wrong vs source-insufficient) to keep decisions deterministic. If semantic ambiguity surfaces during implementation, the status is dropped rather than blurred (per §8 wording "add unsupported only if introducible without semantic ambiguity" — the design currently concludes it is).
- **Span locator cost**: span capture on plain-text registration requires the UI to send offsets; the server validates them (§12). This is the one new client-data dependency; the fallback (whole-source provenance for new plain-text candidates) is NOT permitted — a new candidate without a valid locator is rejected. If this proves prohibitive, reopen the checkpoint with explicit justification rather than silently weakening.
- **Idempotent confirm**: "duplicate confirmation rejected" is implemented as no-second-canonical (UNIQUE + short-circuit, idempotent return) for medication compatibility; documented decision in §10.
- **Legacy manual-entry locator derivation**: `{"kind":"structured_field","path":"medication"}` is derived from the immutable payload structure; verified by the v7 fixture test that the derived locator validates against the stored bytes.
- **`PORTABLE_VAULT_FORMAT_VERSION`**: bump to 3 is a deliberate version change; v2 artifacts remain valid historical exports (no import path exists).
- **Stale `PRODUCT_CORE_SCHEMA_VERSION = 5`** in `portable_vault_export.py:31` predates P1 (migrations were already at v6); P1 corrects it to track the migrations tuple and adds a drift test.
