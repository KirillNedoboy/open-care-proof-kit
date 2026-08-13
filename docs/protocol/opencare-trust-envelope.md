# OpenCare Trust Envelope Protocol

Status: **Standalone protocol (Portable Trust Package, Sentient G4)**
Contract versions: `opencare-trust-envelope/1` (TrustEnvelope), `opencare-execution-receipt/1` (ExecutionReceipt)

This document is self-contained: it defines the wire-visible contract and execution semantics
of the OpenCare Trust Envelope without requiring health-domain knowledge. Any system with
authenticated users and sensitive resources can apply it. The reference implementation surface
is `app/agent_trust/api.py`; offline schemas live in `schemas/agent-trust/`; synthetic fixtures
live in `fixtures/agent-trust/`; the CLI is `opencare-trust` (or `python -m app.agent_trust.cli`).

## 1. Two artifacts and one flow

The protocol has two versioned artifacts and one flow:

- **`TrustEnvelope`** (contract version `opencare-trust-envelope/1`) — the bound,
  fail-closed authorization-and-disclosure contract issued before any agent execution.
  It answers: *when an agent is about to receive or act on sensitive context, what exactly is
  it authorized to know and do?*
- **`ExecutionReceipt`** (contract version `opencare-execution-receipt/1`) — the observed,
  immutable record of what happened during one bounded execution.
- **Flow: Contract → Execution.** An Envelope is minted only from live authorization; a Receipt
  is minted only from observed execution facts. Neither can be converted into the other, and a
  Receipt never upgrades into an Envelope.

Everything in the protocol is deterministic canonical UTF-8 JSON with SHA-256 content identity.
The protocol does not sign, encrypt, or record anything on a blockchain.

## 2. Contract — the TrustEnvelope

The Envelope binds eight semantic inputs. These are exactly the content of the artifact:

| Semantic input | Envelope fields | Role |
|---|---|---|
| Actor identity | `actor_id`, `credential_id` | who is acting, as established by the issuing system; opaque, non-secret identifiers |
| Person/resource scope | `person_id`, `resource_scopes` | the exact resource (Person) and the minimal scopes the action requires |
| Purpose/action | `purpose_id`, `action_id`, `requested_action` | the controlled purpose and action being authorized |
| Authorization snapshot | `authorization.snapshot` (`AuthorizationSnapshot`: `role`, `granted_scopes`, `required_scopes`, `consent_event_id`, `authorized_at`, `access_expires_at`, `policy_version`) | point-in-time evidence of the live decision at issuance, not a durable capability |
| Evidence/provenance | `evidence[]` (`EvidenceItem`: `evidence_id`, `evidence_type`, `person_id`, `resource_scope`, `content_sha256`, `source_ids`, `provenance_status`, `selected_fields`, `observed_at`) | references plus content hashes plus disclosed field names; never raw payloads |
| Policy decision | `safety` (`SafetyDecision`), `final_decision` (`FinalDecision`) | fail-closed allow/refuse with stable reason codes, limitations, and notices |
| Allowed/prohibited operations | `allowed_tools`, `prohibited_operations` | the closed tool allow-list and the explicit, non-empty deny-list |
| Disclosure metadata | `provider_disclosure` (`ProviderDisclosure`: `mode`, `provider_id`, `consent_basis_id`, `allowed_evidence_ids`, `allowed_fields`, `prohibited_data_classes`, `retention`) | where and under what consent the evidence may be disclosed |

Plus envelope identity and timing: `contract_version`, `envelope_id`, `issued_at`,
`expires_at`. `envelope_id` is `sha256:` over the canonical bytes of the validated Envelope
with `envelope_id` omitted — a content address, not a signature.

Contract rules:

- Models are closed: unknown fields, duplicate JSON keys, BOMs, non-canonical forms, and
  unknown controlled identifiers fail validation.
- Set-like arrays are sorted and duplicate-free; datetimes are RFC 3339 UTC instants.
- Decisions fail closed. An issued Envelope always has `final_decision = allow`; refusals
  produce stable reason codes, never an executable-looking Envelope.
- Expiry is strictly after issuance and cannot outlive the authorization snapshot's access
  expiry.

## 3. Execution — from Envelope to Receipt

Execution is a constrained pipeline:

1. **Live reauthorization.** Immediately before any use, the runtime revalidates actor,
   credential, Person, consent, policy version, evidence hashes, provider consent, and expiry.
   A valid hash is not live authority.
2. **Constrained execution.** The executing component receives only an Envelope **projection**:
   evidence references plus selected fields, allowed tools/fields, the output contract, system
   instructions, disclosure constraints, and prohibited operations. It never receives storage,
   repositories, database handles, credentials, session stores, or an unrestricted context.
3. **Tool mediation.** Only Envelope-allow-listed, read-only operations resolve; unknown,
   write, prohibited, or out-of-scope tools fail closed.
4. **Output validation.** Provider output is untrusted. It passes strict structural validation
   against the output contract before it can be returned; failure produces a refusal with
   reason codes.
5. **Receipt.** The `ExecutionReceipt` is constructed from observed facts only: `receipt_id`,
   `envelope_id`, `started_at`/`completed_at`, `status` (`completed` | `refused` | `failed`),
   `provider_id`, `used_evidence_ids`, `used_tools`, `output_sha256` (a digest, never raw
   output), `reason_codes`, and `receipt_sha256` (integrity hash over the Receipt payload).
   `receipt_id` is the content-addressed identity.

Receipt claims are subsets of the Envelope: every used evidence ID and tool must be on the
Envelope allow-list, provider identity must match the disclosure metadata, and the execution
interval must fall within Envelope validity; otherwise verification fails with
`receipt_exceeds_envelope` or the matching reason code.

## 4. What the hash proves — and what it does not

**The hash proves:**

- **Integrity.** The bytes are the canonical serialization of the validated semantic content.
  Any mutation, reordering, duplicate key, BOM, alternate escaping, or platform-newline change
  alters the digest and fails verification.
- **Deterministic identity.** The same validated semantic content always produces the same
  canonical bytes and the same digest on every platform, OS, and locale. `envelope_id` and
  `receipt_id` are stable content addresses for the artifacts.

**The hash does NOT prove:**

- **Signer identity** — who created or approved the artifact.
- **Current authorization** — the artifact may be expired, revoked, superseded, or its
  evidence changed; live reauthorization is mandatory before every use.
- **Encryption** — hashing is integrity, not confidentiality.
- **Authenticity from a trusted issuer** — there are no digital signatures, certificates,
  PKI, or issuer identity.
- **Blockchain state** — no chain, ledger, consensus, or transparency log is involved.
- **Remote attestation** — no hardware, enclave, or TPM evidence is produced.

## 5. Critical authorization rule

**A historical Envelope or Receipt is not a bearer credential.**

Presenting a valid Envelope proves only that those bytes were once minted. It grants nothing
now. Replay of an expired, revoked, superseded, or evidence-changed Envelope must fail closed.
The committed fixtures under `fixtures/agent-trust/` are explicitly NOT authorization:
they are synthetic, offline test vectors with a fixed clock, and constructing or replaying a
Snapshot, Envelope, or Receipt from them has no authority whatsoever. Only a fresh,
live-validated execution may use an Envelope, and every use rechecks everything.

## 6. Security rule

**The agent receives an authorized context artifact, not unrestricted storage access.**

The executing agent or provider receives the projection — evidence references plus selected
fields, bounded by the allow-lists — not storage. No repositories, database connections,
session stores, credentials, vault paths, or broad context are ever handed over. Tool use is
restricted to the Envelope allow-list; output is bounded and validated; any attempted
prohibited or mutating operation is refused and recorded in the Receipt. An Envelope narrows
what may be seen and done; it never opens a wider door.

## 7. Artifacts and tooling

- **Public API:** `app/agent_trust/api.py` re-exports the contract models (`TrustEnvelope`,
  `ExecutionReceipt`, `AuthorizationSnapshot`, `AuthorizationDecision`, `SafetyDecision`,
  `FinalDecision`, `EvidenceItem`, `ProviderDisclosure`), the trusted builder
  (`TrustedEnvelopeBuilder`), canonical helpers (`canonical_bytes`, `sha256_hex`,
  `strict_json_loads`, `envelope_id`, `receipt_id`, `receipt_sha256`), validators
  (`validate_envelope_bytes`, `validate_receipt_bytes`), the `AuthorizationAdapter` Protocol,
  and the controlled identifiers (purposes, actions, tools).
- **Schemas:** `schemas/agent-trust/trust-envelope.schema.json`,
  `execution-receipt.schema.json`, `authorization-snapshot.schema.json` — deterministic
  exports from the models (regenerate with `opencare-trust export-schemas`; never hand-edit).
- **Fixtures:** `fixtures/agent-trust/` — allowed, refused, and unsupported artifacts;
  synthetic, offline, and not authorization; fixed fixture clock
  `2027-08-02T10:00:00Z` (pass `--at` when verifying).
- **CLI:** `opencare-trust` or `python -m app.agent_trust.cli` — `verify-envelope`,
  `inspect-envelope`, `verify-receipt`, `export-envelope` (synthetic demo authority only),
  `export-schemas`, `regenerate-fixtures`. Exit codes: `0` success, `1` verification failure
  or refusal, `2` usage error. No command mints live authorization.
- **Reference docs:** G1 design
  ([docs/architecture/sentient-g1-trust-envelope.md](../architecture/sentient-g1-trust-envelope.md)),
  G2 runtime
  ([docs/architecture/sentient-g2-consent-runtime.md](../architecture/sentient-g2-consent-runtime.md)),
  G3 provider portability
  ([docs/architecture/sentient-g3-model-portability.md](../architecture/sentient-g3-model-portability.md)),
  G4 design
  ([docs/architecture/sentient-g4-portable-trust-package.md](../architecture/sentient-g4-portable-trust-package.md)),
  and the downstream integration guide
  ([docs/integrations/agent-trust-integration-guide.md](../integrations/agent-trust-integration-guide.md)).

## 8. Non-claims and boundaries

- The protocol does **not** authenticate users; downstream systems authenticate, and the
  adapter supplies the authorization decision.
- The protocol provides no MCP server or `mcp.json` (explicitly deferred) and makes no
  multi-client validation claim (that is Sentient G5).
- The protocol provides no signatures, PKI, attestation, transparency infrastructure,
  encryption at rest, or encryption in transit.
- The protocol carries evidence references and hashes, not raw sensitive payloads, and never
  claims medical correctness.
