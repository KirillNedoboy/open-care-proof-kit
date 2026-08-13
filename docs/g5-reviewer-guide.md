# Sentient G5 — Reviewer Guide

Short guide for reviewing the G5 ecosystem-validation evidence. Full
definitions are in the [G5 design](architecture/sentient-g5-ecosystem-validation.md),
the [evaluation protocol](evals/g5-evaluation-protocol.md), and the
[threat model](security/agent-trust-threat-model.md).

## Trust thesis

OpenCare proves trust by **enforced boundaries, not prompting**: a
Person-scoped Trust Envelope, exact consent before any external provider,
live reauthorization at execution time, a fail-closed tool mediator, strict
output validation, and canonical, digest-only Receipts. G5's job is to
demonstrate — deterministically, offline, on synthetic data — that those
boundaries hold when attacked, and that the exact G4 package
(`agent-plugins/opencare-trust/`) loads unchanged in independent clients.

## Run ONE command

```text
.\.venv\Scripts\python.exe -m evals.g5_review
```

- Deterministic and offline: no network, Ollama, Sentient, external
  provider, live authorization, or real data.
- Exit `0` = all checks pass; `1` = failures listed; `2` = usage error.
- `--json` prints the full report; `--write` writes it under `reports/g5/`.

## Read the result

1. **State**: `PASS`, `READY_FOR_SECOND_CLIENT_SMOKE`, or `BLOCKED`
   (BLOCKED is reserved for P0/P1 contract defects — never for a missing
   install).
2. **Cases**: `20/20 passed` against `evals/g5/corpus.json`.
3. **Eight security invariants**: all counters must be `0`
   (unauthorized evidence exposure, external calls without consent, canonical
   mutation, provider calls after revocation/context change, invalid
   citations, unsafe prescriptive claims, receipt verification failures).
4. **Quality metrics**: measured only (precision/recall on the synthetic
   labelled subset, minimization, provenance coverage, refusal correctness,
   receipt completeness, deterministic replay) — no targets.
5. **Plugin integrity**: the committed package passes G4 conformance checks
   (strict 1.0.0 `plugin.json`, skill discovery, containment, no secrets, no
   `mcp.json`).
6. **Cross-client**: reviewer-validated evidence records; currently the
   standalone record in
   [docs/assets/g5/client-interop-evidence.md](assets/g5/client-interop-evidence.md).

## Inspect a fixture pair

- **Allowed**: `fixtures/agent-trust/allowed-envelope.json` — a valid
  synthetic Envelope that verifies.
  `python -m app.agent_trust.cli verify-envelope --envelope fixtures/agent-trust/allowed-envelope.json --at 2027-08-02T10:00:00Z`
- **Refused**: `fixtures/agent-trust/refused-before-envelope-receipt.json` —
  a `refused` Receipt: execution did not complete, no `output_sha256`, stable
  reason codes; never a look-executable Envelope.

A valid hash proves integrity and deterministic identity only — never signer
authenticity, live authorization, or a bearer credential. A fixture is a test
vector, not a capability.

## Wrong Person test (the central case)

Synthetic family: **Alice** (owner/parent), **Bob** (caregiver with bounded
child access), **Carol** (unrelated person).

- Bob → summary of the child's records: **allowed** (within his bounded
  access) — corpus g5-02/g5-04 style answered cases.
- Alice revokes Bob: the **next** request is **refused**
  (`authorization_revoked` / `context_changed`), **provider calls = 0**, and
  the **old Receipt remains verifiable but grants no access** (corpus
  g5-05/g5-06; G2 revalidates everything live before disclosure).
- Wrong Person or Carol's evidence under Alice: refused at prepare
  (`person_access_denied`, `evidence_person_mismatch`) — g5-01/g5-03.

## Provider consent gating

No provider call happens before exact external consent. Consent binds actor,
Person, Envelope, provider, and model; it is single-use and non-replayable.
Revoking consent, mutating evidence, or swapping the bound provider/model
after consent yields `context_changed` with **zero provider calls**
(g5-06/g5-07/g5-08/g5-09). A provider outage fails closed with no fallback
(g5-10).

## The canonical Receipt

Receipts record **observed execution facts only**: Envelope linkage, times,
status, provider, used evidence/tools, output digest (never raw output),
reason codes. Validate with
`python -m app.agent_trust.cli verify-receipt --receipt <path> --envelope <path> --at 2027-08-02T10:00:00Z`.
Tampering is rejected (`receipt_hash_mismatch` / `receipt_id_mismatch`) and
the runtime refuses to return a corrupted stored Receipt (g5-16); byte-tampered
Envelopes are rejected too (g5-17). Prepare-stage refusals record no Receipt
(no execution facts) — that is correct behavior, not a gap.

## Locate the Agent Plugin

`agent-plugins/opencare-trust/` — root `plugin.json`
(`$schema: https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`) plus
`skills/opencare-health-agent/` and `skills/opencare-trust-envelope/`
(immediate-child discovery, frontmatter `name` matches each directory).
Skill-only by design: **no `mcp.json`**, no hooks, no code execution.

## Cross-client evidence and limitations

Evidence: [docs/assets/g5/client-interop-evidence.md](assets/g5/client-interop-evidence.md)
(2026-08-13). **Cursor 3.0.13** loaded the exact committed package: root
`plugin.json` recognized, package bytes unmodified (all 15 files byte-identical
after load), **both** skills discovered with their exact frontmatter
descriptions, zero load failures across 4 reload cycles, cleanup verified.

Limitations (recorded, not defects):

- **A second independent client is not yet proven** → state is
  `READY_FOR_SECOND_CLIENT_SMOKE`. Codex CLI (0.141.0) and Claude Code
  (2.1.220) are installed but use native manifests
  (`.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`) and do not load
  the portable root `plugin.json`; VS Code, Kiro, and other documented
  portable-plugin clients are not installed on this machine.
- **Model behavior was not exercised**: the Cursor agent account hit its
  usage limit, so the behavioral smoke (skill guidance followed, negative
  request refused) was not run. Server-side enforcement remains the security
  boundary; skill guidance content is deterministic text from `SKILL.md`.
- The reviewer validates committed evidence records; it does not re-drive the
  clients.
