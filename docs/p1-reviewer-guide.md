# P1 Reviewer Guide

This guide covers the deterministic offline reviewer for the OpenCare P1
evidence-grounded ingest (Conditions + Labs) work. The design contract lives
in [`docs/architecture/p1-evidence-grounded-ingest.md`](architecture/p1-evidence-grounded-ingest.md).

## How to run

```bash
python -m evals.p1_review
```

Exit codes:

- `0` — all checks passed (`result: PASS`);
- `1` — at least one check failed (`result: FAIL`, failing checks are listed
  with `FAILED:` lines before the summary);
- `2` — usage error.

The reviewer is fully offline and deterministic: it builds a temporary SQLite
database and a temporary source directory, uses a fixed clock and sequential
IDs, and touches no network, Ollama, Sentient, browser, Docker, external
account, real health data, or LLM. It never runs the pytest suite.

## What the reviewer demonstrates

One compact scripted scenario on synthetic data:

1. **Medication regression** — the medication-only lifecycle still works
   unchanged: `manual_entry` source → medication candidate → confirmation →
   active canonical medication record.
2. **Condition lifecycle** — structured manual source (schema_version 2,
   `fact_type=condition`) → candidate with derived provenance locator →
   confirmation → canonical condition record → `condition_confirmed` timeline
   event → correction lineage (successor candidate, old canonical superseded,
   `condition_corrected` event). `reject` and `unsupported` decisions create no
   canonical record.
3. **Lab lifecycle** — same shape for labs, with `result_text` preserved as
   source text and `source_flag_text` preserved verbatim as source-provided
   (never OpenCare-derived).
4. **Provenance** — every candidate carries a validated locator: a
   `structured_field` path for manual sources, a `span` for plain-text sources.
   A missing or mismatched locator is rejected (`provenance_mismatch_accepted`
   stays zero).
5. **Wrong Person isolation** — Alice (owner of the Child), Bob (caregiver with
   explicitly granted v2 scopes), Carol (unrelated). Bob cannot read Carol's
   condition/lab scopes (no assignment → hidden, HTTP 404 at the API boundary)
   and Carol cannot read Alice's. A legacy `family-access-v1` assignment (no
   `condition.*`/`lab.*` scopes) never gains the new capabilities (no silent
   privilege expansion), and an unauthorized confirmation attempt is rejected
   (`unauthorized_confirmation` stays zero).
6. **Timeline** — deterministic events for all three fact families
   (`medication_confirmed`, `condition_confirmed`, `condition_corrected`,
   `lab_confirmed`).
7. **Visit Brief** — a content-schema-v2 revision carries condition and lab
   evidence selections; a rewritten v1-era revision (medication-only content,
   recomputed v1 hash) still verifies and reads.
8. **Export / recovery** — portable export format v3 contains the condition/lab
   entities; a full backup → verify → recover round trip preserves them
   (schema version 7).

## The six security counters

The reviewer asserts all six counters are zero and prints them:

| Counter | Meaning |
|---|---|
| `canonical_without_review` | canonical record whose candidate was not human-confirmed |
| `canonical_without_source` | canonical record with no immutable source |
| `cross_person_record_exposure` | canonical records reachable across Persons |
| `cross_person_source_exposure` | sources/candidates bound across Persons |
| `unauthorized_confirmation` | confirmation accepted without the required scope |
| `provenance_mismatch_accepted` | provenance locator accepted without source validation |

## Review state machine

`pending → confirmed | rejected | unsupported | corrected`

- `pending` — created from a source; **no** canonical record exists.
- `confirmed` — a human reviewer accepted it; exactly one canonical record is
  created atomically (authorization + transition + canonical + timeline + audit
  in one transaction).
- `rejected` — the reviewer decided the fact is wrong/not applicable from this
  source; no canonical record.
- `unsupported` — the reviewer decided the source does not sufficiently support
  the claimed fact; no canonical record. Distinct from `rejected` (wrong fact)
  and from never selecting a fact (no candidate exists).
- `corrected` — the original candidate was replaced via the explicit correction
  path; the successor is `pending` and the lineage
  (`predecessor_candidate_id`) is queryable. Correcting a confirmed record
  keeps the original `confirmed` and supersedes its canonical only when the
  successor is confirmed.

No source becomes canonical by ingestion alone: every canonical record traces
to one human-reviewed candidate and one immutable source.

## No-diagnosis / no-interpretation boundaries

- A condition is a **recorded condition** / **source-backed condition record**,
  never an OpenCare diagnosis: no ICD/SNOMED mapping, no severity, prognosis,
  treatment, or resolved/active inference.
- A lab is a **source-preserving record**: `result_text` is never forced into a
  number, no unit conversion, no derived reference ranges, and no
  normal/abnormal/concerning classification. `source_flag_text` is only ever a
  source-provided flag (e.g. "H") displayed as source-provided.
- The reviewer asserts source-backed wording only; it never performs or claims
  clinical interpretation.
