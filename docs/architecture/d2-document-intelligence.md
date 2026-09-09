# D2.1 Document Intelligence Contract

D2.1 automatically extracts only document-stated medication, condition, and lab
facts from persisted D1 page text. It creates source-backed `pending`
CandidateFacts; it never confirms canonical records, timeline events, Visit Brief
evidence, or normal agent context. Review remains explicit and unchanged.

The extraction contract is `opencare-document-facts/1`. Each suggestion must
contain an exact page number and a verbatim quote of at most 600 characters. The
server resolves exactly one Unicode occurrence and constructs the closed D1
`document_text_span` locator. Input is capped at 60,000 Unicode code points,
output at 32 facts, and there is one provider call per document (no chunking).

External providers require a truthful provider/model disclosure and explicit
per-call consent. Local real providers may execute after prepare. Deterministic
demo mode reports unavailable and never fabricates medical facts. Raw PDF bytes,
paths, credentials, unrelated records, and raw genome are never sent.

Product Core migration v10 stores run identity, bounded status/counts, provider
descriptor identity, request fingerprints, and run-to-candidate items. A
database fingerprint registry makes repeated and concurrent extraction
idempotent. Procedures, recommendations, and follow-up extraction are deferred
to D2.2.

## D2.2 — Procedures, Recommendations, and Follow-up

D2.2 extends document intelligence from three fact families to six:
`medication`, `condition`, `lab`, `procedure`, `recommendation`, and
`follow_up`. D2.2 is complete locally; it is not published or merged. The D2.1
contract above remains the historical record for `opencare-document-facts/1`
runs, and the D2.1 deferral of procedures, recommendations, and follow-up to
D2.2 above is now fulfilled by this section.

### Product Core schema v11

Migration v11 never edits v10: existing v10 rows are carried over with their
identity preserved. The candidate and canonical fact-type CHECKs are widened to
the six categories, and three new 1:1 detail-table pairs join the existing
medication/condition/lab pairs:

- `candidate_procedure_details` / `canonical_procedure_details`:
  `display_name`, `normalized_name`, `status_text`, `date_text`, `note`
  (source-text fields; no derived dates).
- `candidate_recommendation_details` / `canonical_recommendation_details`:
  `instruction_text`, `normalized_instruction`, `context_text`, `note`.
- `candidate_follow_up_details` / `canonical_follow_up_details`:
  `action_text`, `normalized_action`, `timing_text`, `destination_text`, `note`
  (source-text timing only; no due dates and no scheduling).

Identity normalization for the new families is trim/whitespace-collapse/casefold
only — the same non-semantic rule D2.1 uses for medication names. There is no
clinical normalization, terminology mapping, or deduplication against external
code systems. D1/D2 run, item, registry, consent-binding, and receipt-binding
triggers are preserved under v11, and schema v11 fully survives backup, offline
verification, and recovery without re-running the model.

### Family Access v4

`family-access-v4` adds exactly six scopes: `procedure.read`,
`procedure.write`, `recommendation.read`, `recommendation.write`,
`follow_up.read`, and `follow_up.write`. `family-access-v1`, v2, and v3 are
frozen verbatim, and existing v1/v2/v3 assignments never silently gain the new
scopes. Moving a grant from v3 to v4 is an explicit owner action recorded as a
new audited consent event through the existing access-revision mechanism; no
new access subsystem was added and historical consent events are not rewritten.

### Extraction contract v2

New runs use `opencare-document-facts/2`. Historical `.../1` runs remain valid,
readable, and exportable; their recorded `allowed_fact_types` are never
retroactively enlarged, so a completed v1 run means D2.1 categories were
analyzed under v1, not the full six. Allowed categories for a new run are
computed from the acting party's current write authority: the provider is only
ever asked for categories it could legally be materialized into, and the
disclosure lists exactly the authorized subset. Re-analyzing a D2.1 document
under v2 reuses still-matching old candidates via the deterministic fingerprint
registry and creates new-category candidates once; nothing is duplicated.

All D2.1 limits are unchanged: 60,000-code-point input cap, 32 facts per run in
total across all six categories, quotes of at most 600 characters, and exactly
one provider call per document (no chunking). No OCR is introduced: analysis
still operates only on bounded persisted D1 embedded text.

### Classification semantics

One semantic statement becomes exactly one fact. The provider instruction
encodes a fixed priority: medication instructions stay `medication`; a merely
suggested procedure is a `recommendation`; an explicitly performed, occurring,
or scheduled named procedure is a `procedure`; an explicit future recheck,
repeat, or return with timing intent is a `follow_up`; other explicit advice or
instructions are `recommendations`. Duplicate category assignments are rejected
server-side as `duplicate_fact`.

### Exact-source-only extraction

D2.2 adds no new provenance machinery: the unchanged D2.1 validation applies to
all six categories. Every suggested fact must carry an exact page number and a
verbatim quote resolving to exactly one Unicode occurrence in the persisted
page text; the server computes span offsets and `selected_text_sha256` and
builds the closed D1 `document_text_span` locator. Facts the model inferred
rather than found stated in the text fail validation and are recorded as
invalid; they never become candidates.

### Review, timeline, and agent boundary

Materialization is pending-only: extraction confirms nothing. Awaiting-review
candidates become canonical records, timeline events, or agent context only
through the unchanged explicit human Confirm / Correct / Reject / Unsupported
lifecycle. Timeline titles for the new families are neutral: "Procedure
recorded", "Recommendation recorded", "Follow-up recorded". Agent context
includes confirmed records only, gated per type on `procedure.read`,
`recommendation.read`, and `follow_up.read`, so pending items are structurally
excluded. Recommendations appear as "Recorded recommendation" source evidence
with provenance, never as OpenCare advice; OpenCare remains not a diagnostic
system and not a treatment recommender.

### Visit Brief deferral and export

Visit Brief content schema stays v2. Procedures, recommendations, and
follow-ups are explicitly not part of Brief v2 evidence selection — a bounded
limitation of D2.2; a dedicated Brief expansion is separate future work.
Portable Person export advances to v6: six typed detail collections for
candidates and canonical records, D2 run contract identity (`v1`/`v2`) in the
exported runs, and their source provenance. Historical v5 export semantics are
preserved, raw document payload is not duplicated beyond the existing document
representation, and no provider secrets are exported.

### Trust flow

The D2.1 trust flow is reused verbatim: authoritative document text into a
genuine `opencare-trust-envelope/1`, truthful disclosure, explicit per-call
external consent, execution, genuine `opencare-execution-receipt/1`, then
server-side source validation and pending-only materialization. D2.2 adds no
second consent system, receipt type, envelope, or provider layer.
