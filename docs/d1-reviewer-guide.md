# D1 reviewer guide

D1 is the branch-only evidence document-ingest implementation on
`codex/d1-evidence-document-ingest`. It is implemented here but remains
pending integration into public `main`.

## Run the reviewer

From the repository root, run exactly:

```bash
python -m evals.d1_review
```

The reviewer is deterministic and offline. It uses synthetic fixtures and does
not require credentials, network access, OCR binaries, model providers, cloud
storage, or a populated installation.

## Proof scope

The reviewer proves the bounded D1 contract:

- authenticated, Person-scoped PDF and plain-text document handling;
- exact immutable source bytes, SHA-256, size, media type, and ownership;
- strict UTF-8 text handling and bounded extraction of usable embedded PDF text;
- immutable extraction snapshots/pages with page and character provenance;
- explicit review flow for document-backed candidates, with no ingestion-time
  candidate or canonical record;
- `document.read`/`document.write` authorization and explicit Family Access
  upgrades without silent scope expansion;
- wrong-Person, denial, malformed/encrypted/no-text, duplicate-integrity, and
  resource-limit fail-closed behavior;
- provenance preservation for condition, lab, and medication review; and
- branch-only portable v4 document inclusion and integrity boundaries.

## Explicit non-goals

D1 does **not** prove or provide OCR, image-only PDF interpretation, automated
clinical extraction, LLM/model extraction, diagnosis, treatment or dosage
inference, unit conversion, reference-range interpretation, or genetics
workflow. Genetics and PGx remain synthetic/demo-only capabilities and are not
expanded by D1.

The reviewer never treats extracted text as medical truth. Only an explicitly
authorized human review action can create a candidate, and canonical records
continue to require the existing fact-family review and write scopes.

## Provenance and deferred work

Every document-backed candidate must retain a validated locator tied to the
immutable source hash, extraction snapshot, page, code-point span, and selected
text hash. Raw document bytes are not exposed through a download endpoint, and
normal agent context does not contain raw document text.

Deferred work includes integration into public `main`, future extractor
versions and their determinism fixtures, OCR or other explicitly designed
extraction capabilities, and any future genetics/Product Core workflow. These
are design changes, not implicit D1 behavior.
