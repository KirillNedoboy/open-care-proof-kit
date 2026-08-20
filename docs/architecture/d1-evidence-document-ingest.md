# D1: Evidence Document Ingest

- Historical design status: binding contract for the D1 implementation.
- Current implementation status: implemented and published on public `main` at
  `c6ae91e40f02582c0e07c1bca8c95765970c93ff`.
- Current runtime: authenticated Person-scoped PDF/TXT upload, immutable Source
  bytes, bounded extraction, provenance/review, document grants, export v4,
  backup, and recovery.
- Historical branch/base context below is preserved for auditability.

This document is the implementation contract for D1. A document registration never confirms a fact and never silently grants access.

## 1. Problem

P1 established a source-backed candidate/review/canonical lifecycle, and P2 made provenance usable in the Family Workspace, but the only source inputs are structured manual entries and plain text without a document-ingest contract. Real evidence commonly arrives as PDFs or text files. Without a bounded document path, users must copy text manually, lose page-level provenance, or bypass immutable-source and review invariants.

D1 adds conservative PDF and text document transport and extraction while retaining the existing rule: raw evidence is immutable, extraction is derived and reproducible, and only explicitly authorized human review can create a canonical record.

## 2. Goals

- Accept `application/pdf` and `text/plain` as authenticated, Person-scoped raw byte bodies.
- Preserve exact uploaded bytes, SHA-256, size, media type, and source ownership.
- Extract source text deterministically, retaining page/character locators and extraction metadata.
- Make extracted text and candidate provenance inspectable in the Workspace without exposing filesystem paths.
- Permit reviewer-created candidates only from validated extracted text; ingestion itself creates no candidate and no canonical record.
- Enforce bounded resource use, fail closed on corruption, and keep security-sensitive mutations in existing Product Core transactions.
- Extend export, backup, verification, and recovery so every authorized Person-owned document remains restorable and integrity-checked.

## 3. Non-goals

- OCR, image-only PDF interpretation, handwriting recognition, tables-to-structured-data conversion, or layout reconstruction.
- Diagnosis, treatment, dosage, unit conversion, reference-range interpretation, or clinical inference.
- Automatic candidate creation, automatic confirmation, deduplication of facts, or LLM/model extraction.
- FHIR/HL7/EHR synchronization, cloud storage, remote ingestion, browser filesystem access, or background upload workers.
- Password cracking/decryption of encrypted PDFs, PDF rendering, embedded-file extraction, or execution of PDF JavaScript/actions.
- Import/merge into an existing installation; D1 remains compatible with the existing empty-target recovery boundary.
- Silent Family Access scope expansion or changing the Trust Envelope contract.

## 4. Supported MIME and document classes

D1 supports exactly `application/pdf` and `text/plain` (case-insensitive media type; parameters ignored for comparison). The body MUST match the declared class: PDFs MUST begin with the PDF signature; text MUST decode as strict UTF-8. A client-provided MIME type is not trusted as proof of content.

A PDF must contain usable embedded text. A valid PDF with no usable text MUST be rejected before durable Source registration; D1 does not retain a failed or empty PDF Source. D1 has no OCR path. A text document is one normalized page. Its source type is exactly `document`; the existing `text/plain` source type for legacy plain-text registration remains unchanged.

## 5. Raw-body transport

The API adds a Person-scoped endpoint:

```text
POST /api/product-core/v1/people/{person_id}/documents
Content-Type: application/pdf | text/plain
X-CSRF-Token: <existing CSRF token>
Content-Length: <required decimal byte count>

<raw document bytes>
```

The endpoint requires the current Actor's `document.write` and the selected Person's visibility. It MUST not accept a JSON base64 wrapper, multipart form, URL, redirect, or server-side path. `Content-Length` is required and must be within the applicable upload limit before reading; a streaming implementation still aborts if received bytes exceed the limit. The server reads only through a bounded stream, validates and extracts before durable Source registration, then publishes the verified bytes with the existing same-directory temporary-file + flush/fsync + no-overwrite hard-link strategy. Database/filesystem compensation follows existing source publication conventions.

D1 has no raw-document download endpoint. `document.read` exposes authorized metadata and persisted extracted text only. The response returns source/document metadata and extraction status, never raw bytes.

## 6. Exact conservative limits

These are the only D1 resource limits, measured before durable registration unless stated otherwise:

| Limit | Exact value | Behavior |
|---|---:|---|
| Maximum upload bytes | 10,485,760 bytes (10 MiB) | reject if `Content-Length > 10 MiB`; reject streaming overflow |
| Maximum PDF pages | 200 | reject with `page_limit_exceeded` |
| Maximum decoded content bytes per page | 200,000 bytes | reject with `decoded_page_bytes_limit_exceeded` |
| Maximum extracted characters per page | 100,000 Unicode code points | reject with `page_chars_limit_exceeded` |
| Maximum total extracted characters | 1,000,000 Unicode code points | reject with `total_chars_limit_exceeded` |

No object-count, concurrency, or wall-time limit is part of this design contract. Implementations MUST still use bounded I/O and the project’s ordinary request/resource safety mechanisms, but adding another D1 limit requires a design update. Limits are not request- or Person-configurable; raising one is a future design change.

## 7. `pypdf` choice and security

D1 uses `pypdf>=6.13,<7`; the accepted exact version is pinned in the dependency lock placeholder as `pypdf==6.13.0` and must be resolved/recorded by the constraints workflow before implementation. It is pure Python, compatible with Python 3.12, supports page-level text extraction, and avoids a native renderer or subprocess dependency. `pypdf` is an extraction library, not a trust boundary: output is untrusted source text.

The extractor opens candidate bytes in bounded memory, never a client path. It does not execute PDF JavaScript, actions, links, attachments, forms, or embedded files. It rejects encrypted/password-protected PDFs (`encrypted_pdf`), malformed PDFs, unsupported filters, page/decoded-content/character overflow, and parser exceptions before durable Source registration. It never follows network references. Logs contain stable reason codes only, not payload text, credentials, paths, or personal metadata.

`pypdf` output is not medical truth. The only normalization is the minimal contract in §9; raw bytes and PDF text are never rewritten. Dependency upgrades require rerunning the extraction determinism fixture and recording any output-version change.

## 8. Source and extraction models

The existing immutable `sources` row remains authoritative for raw bytes. D1 adds document metadata and immutable derived extraction snapshots:

```text
DocumentSource
  source_id, person_id, source_type="document", media_type,
  content_hash, size_bytes, relative_path, created_at,
  original_filename (optional safe display name), document_kind

DocumentExtractionSnapshot
  extraction_id, source_id, person_id, extractor, extractor_version,
  status=complete, text_hash, total_chars, page_count, extracted_at

DocumentExtractionPage
  extraction_id, source_id, person_id, page_number (1-based),
  normalized_text, decoded_content_bytes, extracted_chars, page_hash
```

The Source and every snapshot/page row MUST belong to the same Person; this is checked at creation and during backup/verification. An extraction snapshot and its pages are immutable. D1 creates one successful snapshot per accepted document, but the model permits multiple future snapshots for a new extractor version; a candidate’s locator names its exact `extraction_id`, so snapshots never silently change meaning.

## 9. Normalization, hash, and locator contract

The raw `content_hash` is lowercase SHA-256 over exact uploaded bytes. `size_bytes` is exact byte count. No PDF rewrite, metadata stripping, recompression, Unicode normalization, control replacement, whitespace collapse, or trimming occurs.

For `text/plain` only, remove one leading UTF-8 BOM if present, then convert CRLF and CR to LF. No other normalization is performed. The result is one persisted page. For PDF, persisted page text is the exact usable text returned by `pypdf`, with no normalization or rewriting. Page text hashes are SHA-256 over the exact persisted UTF-8 page bytes; `text_hash` hashes the canonical concatenation of persisted pages with page boundaries.

A locator is a closed JSON object:

```json
{
  "kind": "document_text_span",
  "source_id": "<id>",
  "content_hash": "<64 lowercase hex>",
  "extraction_id": "<id>",
  "page_number": 3,
  "start_codepoint": 120,
  "end_codepoint": 151,
  "selected_text_sha256": "<64 lowercase hex>"
}
```

Offsets are Unicode code-point offsets in the exact persisted normalized page text (`text/plain` uses the §9 BOM/line-ending result; PDF uses exact extracted text). Validation requires `0 <= start_codepoint < end_codepoint <= len(page_text)`, the source and extraction belong to the candidate’s Person, the source hash matches the immutable bytes, the page hash matches, and `selected_text_sha256` equals SHA-256 of the exact UTF-8 bytes of `page_text[start_codepoint:end_codepoint]`. A stale, foreign, out-of-range, or mismatching locator rejects the operation and creates no candidate.

## 10. Candidate and review implications

Ingestion creates a durable `Source` plus one successful immutable extraction snapshot only after all validation in §14 succeeds. A reviewer explicitly selects a span and chooses a fact family/value, creating a normal P1 candidate with `source_id` and `document_text_span` provenance. Confirmation follows existing transaction and typed Family Access rules; extracted text cannot bypass human review. Separate sources remain separate candidates even when normalized values match.

Creating or reviewing a document-backed candidate requires `document.read` dynamically at authorization time, plus the relevant fact-family write/review scope required by the existing lifecycle. `source.read` remains the metadata authority and is not a content oracle: it does not authorize extracted text or document-backed candidate operations. Confirmation still requires `candidate.review` plus corresponding `medication.write`, `condition.write`, or `lab.write`. Sensitive mutations retain in-transaction authorization and audit.

## 11. Family Access v3: explicit upgrades only

D1 introduces policy generation `family-access-v3`; `family-access-v1` and `family-access-v2` remain frozen. Exact v3 sets are:

- Owner: `OWNER_SCOPES_V2 | {"document.read", "document.write"}`.
- Caregiver base: `CAREGIVER_BASE_SCOPES_V2 | {"document.read"}`.
- Caregiver optional: `CAREGIVER_OPTIONAL_SCOPES_V2 | {"document.write"}`.

The generation is inferred only when any v3-only scope is present; existing assignments without a v3-only scope remain v1/v2. A v1/v2 Actor gains none of these scopes, even with `source.read` or fact-family write scopes. An owner or caregiver is upgraded only through an explicit, audited assignment update recording the exact selected scopes; no role-name or policy-version inference expands access. The capability map exposes `document_read` and `document_write` only. Backend authorization remains authoritative and denies TOCTOU-revoked actions.

## 12. Workspace UX

The Health Workspace adds a Documents area under the selected Person, visible only when `document.read` is true. It shows safe filename, upload time, size, SHA-256, media type, extraction status, page count, and neutral failure text. It never renders absolute paths, hidden assignment data, raw document bytes, or another Person’s documents.

A document detail view offers page-grouped extracted text with the selected locator highlighted. There is no raw download control or endpoint. Candidate creation is an explicit reviewer action from a selected span and uses neutral language (“Create candidate”), never “confirm diagnosis.” Person switching uses P2 generation/cancellation rules; delayed Alice responses are dropped and never rendered into Bob. Empty, failed, and busy states are distinct; failed actions re-enable controls.

## 13. Backup, export, and recovery

Portable Person export advances to format v4. It includes every authorized document owned by the selected Person, whether or not a candidate uses it, plus each document’s immutable Source metadata, raw payload, successful extraction snapshot, and pages. The layout remains `manifest.json`, `manifest.sha256`, `vault.json`, and `sources/<source_id>/payload.bin`; no unrelated Person’s documents, credentials, sessions, or provider secrets are included. Export requires `vault.export`, verifies every raw/source/extraction/page hash and Person binding, and audits success before returning bytes.

Installation backup schema advances with the Product Core migration and copies every Source payload plus D1 metadata through the existing SQLite snapshot/staged-source/manifest/COMPLETE sequence. Offline verification checks every document, including unused documents, source ownership, exact hashes, locator fields, extraction-version fields, limits, and foreign keys without live configuration. Recovery remains explicit empty-target-only recovery: it restores all raw Sources and immutable extraction snapshots/pages, verifies before and after activation, and does not add import/merge or populated-target overwrite semantics. Missing/corrupt payload or extraction is an integrity failure; recovery cannot silently drop it.

## 14. Failure semantics

Upload is transactional in this order: authenticate and resolve Person; validate MIME, content length, and bounded body; validate PDF signature or strict UTF-8 text; remove a text BOM/normalize text line endings only for `text/plain`; parse PDF and extract usable text; enforce page/decoded-byte/character limits; compute hashes and immutable snapshot; publish the Source and commit metadata/snapshot together. Any unsupported, malformed, encrypted, no-usable-text, or limit failure occurs before durable Source registration and leaves no Source, snapshot, or page rows. Filesystem staging is cleaned on failure.

Failures are typed, privacy-safe, and fail closed:

- 401/403: session/capability denial; do not reveal document existence.
- 404: hidden/foreign Person or source, using existing privacy semantics.
- 409: duplicate `(person_id, source_type, content_hash)` registration returns the existing document only after authorization and source/extraction integrity verification; missing extraction is an integrity failure, not a successful dedup.
- 413: raw body exceeds 10 MiB.
- 415: unsupported media type or PDF signature.
- 422: strict UTF-8, malformed/encrypted/no-text PDF, limit, or invalid locator failure.
- 500: storage/hash/integrity failure; show “Integrity: stored evidence could not be verified.”
- 503: local storage unavailable; no durable registration is claimed.

The exact error mapping is privacy-safe: parser details, source paths, stack traces, PDF metadata, and payload text are never rendered. A duplicate is never accepted on metadata alone; its source bytes and successful extraction snapshot/pages are re-verified. If verification fails, surface the §14 integrity failure and do not return the document.

## 15. Wrong Person

Every upload takes an explicit URL `person_id`; the server resolves that Person from the current Actor assignment and ignores IDs in JSON, filename, PDF metadata, or client state. Source, extraction snapshot/page, candidate, export, and audit rows must agree on that Person. A missing/changed assignment fails closed. The selected Person is never an authorization source; switching Alice→Bob cancels Alice requests and clears document selection, extracted text, candidate draft, and export state. Tests must prove delayed Alice responses cannot render in Bob and Alice source IDs cannot be used under Bob’s route.

## 16. Agent boundary

Raw documents and raw extracted text are never placed in agent context. A future explicit action may request a bounded, separately approved excerpt only when the Actor has `document.read`, Person/session authorization and consent permit it, and the Trust Envelope’s `allowed_evidence_ids` and `allowed_fields` name the exact source/extraction/page span. The normal agent context contains no raw document text, PDF bytes, paths, credentials, or hidden metadata. Agent output is advisory and cannot mutate canonical records. The Trust Envelope contract remains unchanged.

## 17. Dependency impact

- Add `pypdf>=6.13,<7`, with exact accepted lock/constraints placeholder `pypdf==6.13.0`; no OCR engine, renderer, subprocess, browser, or frontend runtime dependency.
- Reuse standard-library `hashlib`, `sqlite3`, bounded I/O, existing API/auth/access/audit services, and existing backup/export ZIP code.
- Keep Product Core as lifecycle owner; Trust Foundation remains independent of reviewer UI. No dependency from `pypdf` into Family Access or Trust Envelope.
- Lock/constraints resolution and extraction fixtures are implementation work after this design commit; this commit changes no runtime code.

## 18. Migration plan

1. Add Product Core migration v8 only; never edit v1–v7. Add document Source/extraction snapshot/page tables, constraints, indexes, and same-Person ownership checks. Existing rows receive no invented documents or snapshots.
2. Add Family Access policy generation v3 with exact owner/base/optional sets in §11, preserve immutable v1/v2 constants, infer v3 only from a v3-only scope, and require explicit upgrades.
3. Add API models/services for bounded raw-body validation, extraction, metadata/text retrieval, dedup integrity verification, and reviewer candidate creation. Route every caller through the existing access façade; no raw download endpoint and no parallel authorization path.
4. Add portable vault format v4 and backup/recovery validation for every authorized Person-owned document, including unused documents and extraction pages. Existing v3 exports remain readable; v3 cannot claim to export D1 payloads.
5. Add Workspace Documents surface and capability-map fields, preserving P2 Person-switch privacy and error semantics.
6. Add exact-version dependency constraints, deterministic fixtures, malformed/encrypted/no-text/limit/security tests, and migration/backup/export/recovery tests. Rollout is additive: old clients continue v3 and cannot upload; no silent policy upgrade.

## 19. Acceptance criteria

- [ ] Both `application/pdf` and `text/plain` raw-body ingestion are supported; text uses source type `document`, one page, strict UTF-8, BOM removal, and CRLF/CR→LF only.
- [ ] Unsupported, malformed, encrypted, no-usable-text, and over-limit documents fail before durable Source registration; no failed Source is retained.
- [ ] Exact bytes are immutable, hash-verified, Person-bound, and never rewritten by extraction; duplicate registration verifies existing Source and extraction integrity.
- [ ] `pypdf>=6.13,<7` is used with an exact accepted lock placeholder and no unsafe parser behavior.
- [ ] Only the five §6 limits are binding: upload bytes, PDF pages, decoded content bytes/page, extracted chars/page, and total chars.
- [ ] Every document-backed candidate carries a validated `document_text_span` locator with exact extraction/page/code-point/hash fields.
- [ ] P1 review, correction, source integrity, and canonical invariants remain intact; no fact deduplication or clinical inference.
- [ ] Family Access v3 uses exact owner/base/optional upgrades; v1/v2 grants gain no document access without explicit audited upgrade.
- [ ] Document-backed candidate create/review dynamically requires `document.read`; `source.read` remains metadata-only and is not a content oracle.
- [ ] Workspace rendering is Person-safe, capability-aware, accessible, neutral, and has no raw download path.
- [ ] Portable export v4, installation backup, offline verification, and empty-target recovery include and verify every authorized Person-owned document, including unused documents.
- [ ] Wrong-Person, TOCTOU revocation, stale-response, dedup integrity, corruption, and denial paths are covered by deterministic tests.
- [ ] Normal agent context contains no raw document text; any future excerpt is explicit, bounded, consent/policy checked, and cannot mutate canonical records.
- [ ] Dependency and migration changes are isolated from this design-only commit; this commit contains no implementation code.
