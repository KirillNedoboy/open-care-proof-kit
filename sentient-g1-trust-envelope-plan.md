# Sentient G1 Trust Envelope Implementation Plan

## Goal

Implement the binding `opencare-trust-envelope/1` and `opencare-execution-receipt/1`
contracts without creating a second authorization authority or an agent runtime.

## Tasks

- [ ] Add closed identifier registries and frozen, extra-forbid Pydantic models under
  `app/agent_trust/` → Verify invalid identifiers, cross-Person evidence, inconsistent
  decisions, times, scopes, tools, disclosure, and Receipt states fail model validation.
- [ ] Add strict JSON loading, canonical normalization/serialization, content IDs, and
  Receipt hashes → Verify committed UTF-8 test vector and mutation/duplicate-key/BOM/CRLF
  cases produce the specified deterministic result on Windows and Linux semantics.
- [ ] Add pure Envelope/Receipt validators with stable privacy-safe reason codes → Verify
  expiry, tampering, non-canonical bytes, evidence/tool/provider subset violations, and
  status/output inconsistencies fail closed.
- [ ] Add trusted builders and authority protocols → Verify callers cannot provide allow
  decisions or IDs, builders select the earliest expiry, enforce minimal evidence and
  provenance, and never return an Envelope on refusal.
- [ ] Adapt existing `FamilyAccessService` live decisions and repository state without
  duplicating policy → Verify wrong Person, Carol isolation, revoked/malformed/expired
  access, missing scope, and consent-event linkage.
- [ ] Add `export-envelope`, `verify-envelope`, `inspect-envelope`, and `verify-receipt`
  commands following existing JSON/exit-code conventions → Verify export uses only trusted
  synthetic OpenCare inputs and inspect output contains no evidence payload or secret.
- [ ] Commit synthetic fixtures and focused tests for every G1 acceptance-matrix row →
  Verify `pytest tests/test_agent_trust_*.py` and CLI subprocess/smoke scenarios.
- [ ] Align runtime/package documentation and run repository gates → Verify `pytest`,
  `ruff check app tests evals`, `mypy app evals`, `python -m evals.runner`, and
  `git diff --check`.

## Done When

- [ ] Every acceptance row in `docs/architecture/sentient-g1-trust-envelope.md` has an
  executable passing test or explicit G2 boundary assertion.
- [ ] A valid hash is never treated as live authorization, and arbitrary JSON cannot mint
  an authorized Envelope.
- [ ] No G1 code sends data to a provider, mutates canonical health records, or adds
  signatures, keys, blockchain, attestation, or genetics work.
