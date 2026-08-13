# Agent Trust Integration Guide

Status: **Downstream integration guide (Portable Trust Package, Sentient G4)**

This guide is for a developer who has a system with authenticated users and sensitive
resources and wants to hand a bounded, auditable context to an agent. It walks through
implementing a **domain adapter** for the portable trust package, step by step, and shows the
OpenCare health reference mapping as a worked example.

Reference surface: `app/agent_trust/api.py` (public API), `schemas/agent-trust/` (offline
JSON Schemas), `fixtures/agent-trust/` (synthetic test corpus), and the `opencare-trust` CLI
(`python -m app.agent_trust.cli`). Protocol semantics are defined in
[docs/protocol/opencare-trust-envelope.md](../protocol/opencare-trust-envelope.md).

## What the trust package does — and does not — do

The package provides: versioned contract models, canonical JSON serialization and SHA-256
content identity, validation with stable reason codes, trusted construction of Envelopes and
Receipts, offline schemas, synthetic fixtures, a deterministic CLI, and a portable Agent
Plugins v1 skill package. It also defines the generic `AuthorizationAdapter` Protocol — the
single seam your system plugs into.

The package does **not** authenticate users, store evidence, run agents or providers, decide
policy, or guarantee correctness of any downstream output. Your adapter supplies the
authorization truth; the package encodes, binds, verifies, and records that truth.

> **Explicit boundary:** the trust package does **not** authenticate users for downstream
> applications. You authenticate the Actor in your own system and pass opaque identifiers
> into the package. The package never accepts credentials or session tokens, and a valid hash
> is never treated as proof of who is acting.
>
> **Authorization truth:** the adapter is the only component that decides whether an Actor may
> act on a resource. The package does not grant access; it binds the decision your adapter
> produced into an Envelope, so downstream execution can be constrained and audited.

## The 10-step sequence

Implement a domain adapter in ten steps. Steps 1–7 form the **Contract**; steps 8–10 form the
**Execution**; step 10 closes the audit loop.

### Step 1 — Authenticate the Actor in your own system

Authenticate with your own mechanisms (session, credential, SSO). Do **not** pass secrets into
the trust package. Supply only the opaque, non-secret identifiers the Envelope binds:
`actor_id` and `credential_id` (an active credential/session identifier, never the secret
itself).

### Step 2 — Resolve resource/Person scope

Resolve the exact target resource (the Person) and the **minimal** set of resource scopes the
requested action requires. Never infer a resource from relationships, groups, or possession of
an ID. Validate the controlled `purpose_id` and `action_id` against the package's registries;
unknown identifiers fail closed.

### Step 3 — Produce a live AuthorizationDecision/Snapshot

Implement the `AuthorizationAdapter` Protocol (exported from `app/agent_trust/api.py`). Your
`authorize(...)` queries **your** authority at the current trusted clock instant and returns:

- `allow` with an `AuthorizationSnapshot` (role, granted scopes, required scopes, consent
  event, `authorized_at`, `access_expires_at`, `policy_version`); or
- `deny` with stable `reason_codes` and no snapshot.

The snapshot is evidence of the decision at issuance — not a durable capability. Do not mint
an Envelope from a deny.

### Step 4 — Select minimal evidence

Select the smallest evidence set that serves the request, for that resource only. Each
`EvidenceItem` carries an `evidence_id`, type, resource scope, `content_sha256` (hash of the
selected content), `source_ids`, provenance status, and the exact `selected_fields` disclosed.
Carry references and hashes — never raw payloads — inside the Envelope.

### Step 5 — Preserve provenance

Attach provenance links (`source_ids`) and an explicit `provenance_status`
(`source_backed` or `user_asserted`). Missing sources, unsupported provenance states, or
evidence whose hash no longer matches fail closed. Provenance is what lets downstream readers
trace a claim to a source instead of trusting it.

### Step 6 — Build the TrustEnvelope

Use the trusted builder (`TrustedEnvelopeBuilder` + `EnvelopeRequest`) with typed inputs and
your adapter. The builder resolves action-required scopes and permitted tools from the closed
registry, intersects requested tools (never expands), sets expiry to the earliest of requested
TTL, configured maximum TTL, and access expiry, and refuses if any decision denies. **Never**
construct an Envelope from arbitrary JSON: parsing a document never confers authorization.

### Step 7 — Validate the Envelope

Validate the resulting artifact before use: `validate_envelope_bytes` (or
`opencare-trust verify-envelope --envelope PATH [--at UTC]`). This checks schema, invariants,
canonical identity, evidence references, and expiry against your trusted clock. A structurally
valid Envelope is still not executable until live rechecks pass immediately before use.

### Step 8 — Execute through a constrained provider/tool boundary

Give the executing agent/provider only the Envelope **projection**: evidence references plus
selected fields, `allowed_tools`, `allowed_fields`, the output contract, system instructions,
`disclosure_constraints`, and `prohibited_operations`. Never pass repositories, database
handles, session stores, credentials, or the broad application context. Mediate every tool
call: only Envelope-allow-listed, read-only operations resolve; unknown, write, prohibited, or
out-of-scope tools fail closed. (OpenCare's reference implementation of this boundary is the
G2 runtime in `app/agent/g2_runtime.py` with `EnvelopeProjection` and `EnvelopeToolMediator`,
and the G3 provider contract in `app/agent/providers/contract.py`.)

### Step 9 — Validate output

Treat provider output as untrusted. Run strict structural validation against the output
contract (`answer_conforms_to_schema` in the G3 provider contract is the OpenCare pattern).
Refuse on malformed, non-conforming, or unsupported output; never surface it as valid.

### Step 10 — Produce and verify the ExecutionReceipt

Construct the `ExecutionReceipt` from **observed** execution facts only:
`build_execution_receipt` (in `app/agent_trust/builders.py`) with the consumed `envelope_id`,
bounded start/end times, status (`completed` | `refused` | `failed`), provider identity, used
evidence/tool IDs (subsets of the Envelope allow-list), `output_sha256` (digest, never raw
output), and `reason_codes`. Verify with `validate_receipt_bytes` / `opencare-trust
verify-receipt`. A Receipt is historical evidence; it is never a credential and never
re-authorizes anything.

## The OpenCare health reference mapping

The OpenCare implementation is the worked example of this guide. It wires the generic package
to the health domain through exactly one health-specific component:

| Hop | What it does | Where it lives | Must not |
|---|---|---|---|
| 1. Family Access | authenticates Actors, owns Person permissions, assignments, and consent | `app/family_access/` | grant access without an active assignment; infer Persons from relationships |
| 2. `AuthorizationAdapter` | implements the generic Protocol: queries live Family Access state and returns an `AuthorizationDecision` with snapshot | `app/agent/trust_adapter.py` | become a second policy system; accept caller-supplied decisions |
| 3. Person-scoped evidence selector | selects the minimum evidence references/hashes/fields for the explicit Person only | OpenCare runtime (G1 builder inputs) | select evidence for another Person; carry raw payloads |
| 4. `TrustEnvelope` | binds actor, Person, purpose/action, snapshot, evidence/provenance, safety, tools, disclosure, expiry | `app/agent_trust/` (`TrustedEnvelopeBuilder`) | mint from JSON; outlive access expiry |
| 5. G2 runtime | reauthorizes live, projects the Envelope, mediates tools, validates output, records the Receipt | `app/agent/g2_runtime.py` | broaden the Envelope; pass broad context to providers |

The health mapping shows the pattern in its strictest form: the Envelope carries no raw health
payload, the agent receives only the projection, and every disclosure is bound to exact consent
and recorded in a Receipt.

## Testing checklist for your adapter

- Use the synthetic corpus in `fixtures/agent-trust/` as expected-verification vectors
  (remember the fixed fixture clock `2027-08-02T10:00:00Z`; pass `--at`).
- Prove fail-closed behavior: deny → no Envelope; expired/revoked → not executable; changed
  evidence hash → refused; extra Receipt claims → `receipt_exceeds_envelope`.
- Prove the hash claims only: mutating any byte, reordering set-like arrays, or adding a
  duplicate key changes the digest and fails verification.
- Prove no-credential behavior: secrets, tokens, paths, and raw source content never appear in
  Envelope or Receipt output.
- Run `opencare-trust export-schemas` and `regenerate-fixtures` in CI to prove the committed
  schemas and fixtures never drift from the models.
