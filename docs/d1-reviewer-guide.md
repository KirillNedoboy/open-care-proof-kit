# D1 reviewer guide

D1 is implemented and published on public `main` at
`c6ae91e40f02582c0e07c1bca8c95765970c93ff`.

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
- portable v4 document inclusion and integrity boundaries.

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

Future extractor versions, OCR, or other explicitly designed extraction
capabilities remain separate design work. P3 genetics is already implemented
on public `main` and is reviewed independently by `python -m evals.p3_review`.
These boundaries do not claim clinical correctness.
