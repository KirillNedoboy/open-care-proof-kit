# Sentient G2 Consent-Gated Agent Runtime

**Status:** binding implementation contract
**Parent:** Sentient G1 Trust Envelope (`opencare-trust-envelope/1`)

## Purpose and boundaries

G2 is a local-first execution gate. It consumes a verified G1 Envelope and never mints authority, broadens scope, infers a Person, or turns an LLM/provider into a source of truth. The request lifecycle is:

`session Actor → active Person → live authorization → controlled purpose/action → minimal projected evidence/provenance → G1 Envelope → disclosure preview → exact external consent → read-only provider/tools → answer validation → observed durable Receipt + metadata audit`.

All refusals are fail-closed and privacy-safe. No diagnosis, treatment, dosage, start/stop advice, canonical-record mutation, raw genotype upload, or cloud upload is introduced.

## Runtime API and state

The runtime service exposes `prepare`, `grant_disclosure_consent`, and `execute`. HTTP adapters expose only session-derived identity and request fields:

- `POST /api/chat/prepare`
- `POST /api/chat/executions/{execution_id}/consent`
- `POST /api/chat/executions/{execution_id}/execute`
- `GET /api/chat/executions/{execution_id}/receipt`

Callers cannot submit actor, Person, authorization, safety, or Envelope authority fields. Legacy `POST /api/chat` must route through the same gate and cannot bypass consent or execution policy.

Pending execution state is ephemeral in the existing SessionStore database, expires after five minutes, is single-use, and contains metadata only: execution/session identity, question and question hash, Envelope identity, provider identity/hash, and bounded lifecycle state. It is excluded from Product Core backup and recovery.

After v5, Product Core receives one sequential migration (v6) with metadata-only `agent_disclosure_consents` and `agent_execution_receipts`. These durable rows are included in Product Core backup/recovery. They contain no health payload, credentials, session tokens, raw provider output, or raw question beyond the bounded hash/metadata contract.

## Preparation and TOCTOU

`prepare` derives Actor and active Person from the authenticated session, validates the controlled purpose/action, invokes the existing G1 builder with minimum evidence fields and provenance, and stores a pending record. External disclosure produces a preview and remains non-executable until exact consent binds Actor, Person, purpose, action, Envelope ID, provider ID/hash, disclosure fields, and expiry. Consent is one-time and cannot be replayed.

`execute` re-authenticates and reauthorizes immediately before context resolution. It rebuilds the Envelope and revalidates authorization, consent, policy version, expiry, evidence hashes, provenance, provider consent, and tool allow-lists. Any session, authority, evidence, provider descriptor, policy, or pending-record hash change yields `context_changed` (or the narrow stable refusal code) and makes no provider call. The pending record is atomically consumed only after all checks pass.

## Provider and tool mediation

Providers implement a narrow Protocol plus a safe descriptor (stable provider ID, descriptor hash, disclosure mode, and capabilities). The deterministic offline provider is the default. The existing external adapter is reachable only through G2 after exact external consent; otherwise it remains disabled. Tests must prove zero external calls before consent and on every failed preflight.

Tools resolve only Envelope-allow-listed, read-only operations and only projected evidence fields. Unknown, write, prohibited, out-of-scope, or non-allow-listed tools fail closed. G2 never passes the broad `AgentContext` to a provider. Provider input is the exact projected disclosure preview; provider output is bounded and passed through existing answer validation before it can be returned.

## Receipts and audit

The runtime constructs an `ExecutionReceipt` from observed facts, not caller claims. It records Envelope identity, bounded execution times, status, provider identity, used evidence/tool IDs, output digest (never raw output), refusal/mutation flags, and stable reason codes. Receipt identity and integrity use the existing canonical G1 hashing rules. Every durable consent and execution transition has a metadata-only access audit linkage; failed or refused execution is also recorded without sensitive payloads.

No canonical Product Core record is mutated. Any attempted mutation tool is refused and the receipt marks the mutation attempt/refusal. Receipts are durable only after observed execution facts are known; pending state remains ephemeral.

## Recovery and security invariants

Product Core backup/recovery includes v6 consent and receipt metadata with schema/checksum/foreign-key validation. It excludes SessionStore pending executions, sessions, provider output, credentials, raw tokens, and external payloads. Restored receipts remain historical evidence and do not recreate pending authority or consent. A restored or stale Envelope must undergo fresh live checks.

The implementation preserves G1 invariants: exact Actor/Person match, minimal action scopes, active consent basis, strict expiry, source/provenance checks, explicit safety notices and limitations, no secrets or unselected source content, and no family-relationship-only access. Envelope hashes are integrity checks, never live authorization.

## Acceptance boundary

The implementation must cover runtime minimization, exact consent binding and replay refusal, provider/tool mediation, output validation, receipt identity and audit linkage, v6 migration/backup recovery, wrong-Person isolation followed by revocation, TOCTOU cancellation, injection/refusal cases, and ten named trust-eval cases. No dependency, network integration, deployment, release, or unrelated product capability is added.
