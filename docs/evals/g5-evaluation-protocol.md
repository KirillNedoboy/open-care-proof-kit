# Sentient G5 — Evaluation Protocol

Status: defines what G5 measures **before** results are reported.
Scope: the G5 reviewer (`python -m evals.g5_review`), the 20-case adversarial
corpus (`evals/g5/corpus.json`), and the observed metrics recorded for
2026-08-13 at HEAD `e7d1d9b` on branch
`codex/sentient-g5-ecosystem-validation`.

The G5 design (boundaries, invariant families, result states) is binding in
[the G5 architecture document](../architecture/sentient-g5-ecosystem-validation.md).
This protocol defines the measurement contract: what is measured, the exact
numerator/denominator of each metric, what evidence is deterministic vs
model-dependent, what is excluded, and how the numbers are interpreted.

## 1. Synthetic corpus

- Location: `evals/g5/corpus.json` (schema `opencare-g5-corpus/1`).
- **20 cases**, each with: fixed synthetic actor/credential/person IDs,
  controlled purpose/action, requested tools, evidence IDs, a question, a
  scripted provider (`deterministic`, `echo`, `unavailable`,
  `mutation_write`, `unknown_tool`, `invalid_citation`,
  `unsafe_prescriptive`), an expected binary outcome (`refused_prepare` /
  `refused` / `answered`), expected reason codes, expected and forbidden
  evidence IDs, `provider_must_be_called`, `mutation_allowed`, and optional
  phase operations (`revoke_actor`, `revoke_consent`, `mutate_evidence`,
  `swap_provider`, `swap_model`) applied after consent.
- Fixed synthetic clock `2027-08-02T10:00:00Z` (same as the G4 fixtures);
  synthetic actors Alice/Bob/Carol with synthetic evidence IDs only. No real
  person, record, clinician, consent event, or health payload appears.
- Case categories exercised: identity_boundary, evidence_isolation,
  context_integrity, authorization_revocation, consent_revocation,
  provider_identity, provider_availability, tool_boundary,
  citation_integrity, provenance, safety, receipt_integrity,
  envelope_integrity, replay_determinism, minimization, fixture_isolation.

## 2. Deterministic vs model-dependent evidence

- **All enforcement evidence is deterministic.** Providers are scripts with
  fixed behavior; the clock is fixed; outcomes and reason codes are produced
  by the existing G1–G4 validation/authorization code, never by a model.
  No network, Ollama, Sentient, external provider, or live authorization
  participates (the reviewer runs offline).
- **Relevance labels are synthetic.** The per-case expected/forbidden
  evidence sets define the labelled subset; `relevance_labels_are_synthetic`
  is always `true` in the report. Precision/recall therefore measure the
  system against synthetic ground truth, not against real task semantics.
- **Model behavior is not evidence.** A client's model behavior (e.g., a
  Cursor agent following skill guidance) was not exercised (account usage
  limit) and is excluded from the enforcement matrix. Client-loading
  evidence is observational, not model-behavioral.

## 3. What is measured

### 3.1 Eight security invariants (binary violation counts)

Each counter counts violating observations across the corpus; all are
expected to be `0`. Any nonzero counter is a P0 contract defect.

| Counter | Definition |
|---|---|
| `unauthorized_evidence_exposures` | provider evidence payloads containing any forbidden evidence ID (per case) |
| `external_calls_without_consent` | provider invocations observed without active consent |
| `canonical_mutations_via_agent_path` | cases where agent-path execution changed canonical evidence state |
| `provider_calls_after_revocation` | provider calls in cases whose phases include `revoke_actor`/`revoke_consent` |
| `provider_calls_after_context_change` | provider calls in cases whose phases include `mutate_evidence`/`swap_provider`/`swap_model` |
| `accepted_invalid_citations` | citations in answered outputs whose source is not an Envelope source |
| `accepted_unsupported_prescriptive_claims` | answered outputs matching the unsafe-prescriptive patterns |
| `receipt_verification_failures_for_valid_receipts` | valid Receipts that failed integrity/subset validation |

### 3.2 Quality metrics (observed, no targets)

| Metric | Numerator / Denominator | Notes |
|---|---|---|
| Context precision | `disclosed_relevant` ÷ `disclosed_total` | answered cases only; per-case values also reported |
| Context recall | `disclosed_relevant` ÷ `expected_relevant_total` | answered cases only; expected = synthetic labelled subset |
| Context minimization | `selected_evidence_count` ÷ `eligible_evidence_count`; byte reduction = 1 − `provider_projection_bytes` ÷ `eligible_serialized_bytes` | byte accounting is over **serialized evidence identifiers** (deterministic, privacy-safe proxy), not raw payload content |
| Provenance coverage | `used_evidence_with_source_linkage` ÷ `used_evidence_total` | every disclosed item must be source-backed |
| Refusal correctness | `correctly_refused_cases` ÷ `expected_refusal_cases` | g2_flow scenarios whose expected outcome is not `answered`; `incorrectly_answered_cases` reported separately |
| Receipt completeness | completed: `completed_receipts_complete` ÷ `completed_executions`; refused: `refused_receipts_recorded` ÷ `refused_executions` | see interpretation §5 |
| Deterministic replay | corpus run twice: identical Envelope bytes/IDs, Receipt bytes, and reason codes | pass/fail, not a percentage |

## 4. Exclusions

G5 metrics exclude, by design:

- real data of any kind (persons, records, clinicians, family/consent
  events, health payloads);
- live or network providers, Ollama, Sentient, and any model-quality or
  diagnostic benchmarking (G3 limitation continues);
- model-dependent judgments as enforcement evidence (§2);
- MCP, A2A, ROMA, EvoSkill, Enclaves, new providers/routing/orchestration,
  signing/PKI/blockchain/attestation, and marketplace publication (G5
  exclusions in the design document);
- non-health examples (deferred per the design document);
- client-behavior claims beyond the recorded cross-client loading evidence
  (§6).

## 5. Interpretation

- **No targets are set.** Every metric is reported as an observed value with
  its numerator/denominator; `null` means "not computable on this corpus".
  Numbers recorded here are observations from one run, not thresholds.
- **Refusal-receipt accounting.** Receipts record observed execution facts.
  Prepare-stage refusals and refusals at the pre-execution revalidate gate
  (revocation, context change) record **no** Receipt by contract, so
  `refused_receipts_recorded < refused_executions` is expected; the gap is
  the count of refusals that never produced execution facts. Only
  execution-stage refusals after provider activity record refused/failed
  Receipts.
- **Result states** (binding in the design document): `PASS` = reviewer
  exit 0 with two-client evidence; `READY_FOR_SECOND_CLIENT_SMOKE` = reviewer
  exit 0 with one client verified and the second documented as pending;
  `BLOCKED` = a P0/P1 contract defect. Missing installs are never `BLOCKED`.
- **Reproducibility.** The reviewer is deterministic; identical inputs at the
  same fixed clock produce identical bytes. Report schema:
  `opencare-g5-eval/1` (`evals/g5/report.schema.json`).

## 6. Observed values (2026-08-13, HEAD e7d1d9b)

Recorded by running `python -m evals.g5_review --json` on the committed
branch:

- **Cases:** 20/20 passed, 0 failed; state
  `READY_FOR_SECOND_CLIENT_SMOKE`.
- **Security invariants:** all eight counters `0`.
- **Context precision:** 5/5 = 1.0 (answered cases: g5-02, g5-04, g5-16,
  g5-18, g5-19).
- **Context recall:** 5/5 = 1.0.
- **Context minimization:** selected 20 of 58 eligible evidence IDs (ratio
  0.3448); evidence-identifier bytes 1222 → 375 (reduction fraction 0.6931).
- **Provenance coverage:** 15/15 = 1.0.
- **Refusal correctness:** 13/13 expected refusals correctly refused;
  0 incorrectly answered.
- **Receipt completeness:** completed executions 5, complete receipts 5;
  refused executions 15, refused receipts recorded 5 (per §5: the 10
  unrecorded refusals are prepare-stage or pre-execution-gate refusals with
  no execution facts).
- **Deterministic replay:** pass. **Plugin integrity:** pass.
- **Cross-client:** reviewer records empty; the standalone evidence record
  [client-interop-evidence.md](../assets/g5/client-interop-evidence.md)
  documents that Cursor 3.0.13 loaded the exact committed package
  (`agent-plugins/opencare-trust/`, 15 files, tree hash
  `fc95079592c5f9ec088d915b7cfce33fea96f93d35a8d068d8be651e8dace4d4`) with
  both Skills discovered and zero load failures; package unmodified;
  cleanup verified. A second independent client is not yet proven →
  `READY_FOR_SECOND_CLIENT_SMOKE`. Codex CLI (0.141.0) and Claude Code
  (2.1.220) are installed but require native manifests
  (`.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`) and do not load
  the portable root `plugin.json`; VS Code, Kiro, and others are not
  installed on this machine.

## 7. Re-running

```text
.\.venv\Scripts\python.exe -m evals.g5_review          # summary
.\.venv\Scripts\python.exe -m evals.g5_review --json   # full report
.\.venv\Scripts\python.exe -m evals.g5_review --write  # write report to reports/g5/
```

Exit codes follow the repo convention: `0` pass, `1` failures listed, `2`
usage error. The reviewer must remain offline and deterministic; any future
change that adds network, live providers, or model-dependent judgments to the
corpus or reviewer is out of protocol and must be rejected.
