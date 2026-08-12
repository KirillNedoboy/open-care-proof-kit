# Sentient G1 — OpenCare Trust Envelope

Status: **Binding for G1 implementation**  
Contract version: `opencare-trust-envelope/1`  
Receipt version: `opencare-execution-receipt/1`

## 1. Purpose and boundary

A Trust Envelope is the fail-closed contract at the boundary between authorized,
sensitive OpenCare state and an agent-capable execution context. OpenCare issues one
Envelope per trust-bound agent request/execution when sensitive context is assembled for
a constrained agent action.

The Envelope answers: **when an agent is about to receive or act on sensitive context,
what exactly is it authorized to know and do?** It binds the authenticated actor,
explicit Person, purpose, requested action, resource scopes, live authorization and
consent basis, selected evidence and provenance, safety decision, tools, prohibited
operations, disclosure constraints, and expiry. G2 may execute only within this bound.

An Envelope is not a generic wrapper around OpenCare operations. It is not required for
SQLite migrations, backup verification, deterministic timeline rebuilds, ordinary CRUD,
internal repository/service calls, document parsing, or unrelated deterministic Product
Core processing. It is not limited to clinician briefings, LLM input/output, or a single
health artifact.

G1 constructs and verifies this contract but does not execute providers or agents. G2 is
the Consent-Gated Agent Runtime that consumes it.

## 2. Security claims and non-claims

G1 provides deterministic serialization, content identity, and tamper detection:

- deterministic canonical JSON encoded as UTF-8;
- documented normalization;
- SHA-256 content hashes;
- a content-addressed Envelope ID;
- SHA-256 Receipt integrity.

G1 does **not** provide signer authenticity or non-repudiation. A valid hash proves only
that content matches the hashed bytes. It does not prove who created or approved the
content. G1 deliberately adds no digital signatures, PKI, signing-key lifecycle,
blockchain, decentralized identity, remote attestation, or transparency log.

## 3. Package boundary

`app/agent_trust/` owns the portable contract and integrity rules:

- `identifiers.py`: controlled purpose/action/tool identifiers;
- `models.py`: immutable Pydantic contract models;
- `canonical.py`: normalization, canonical JSON, hashing, content IDs;
- `validation.py`: Envelope and Receipt validation and stable reason codes;
- `builders.py`: trusted Envelope and Receipt construction;
- `authorization.py`: adapter from live OpenCare Family Access decisions;
- `cli.py`: offline export, verify, and inspect commands.

Existing Product Core, Family Access, provenance, and safety services remain authoritative.
`agent_trust` adapts their decisions; it does not become a second authorization system,
consent store, evidence store, or safety engine.

## 4. Controlled identifiers

G1 uses closed identifiers. Unknown identifiers fail validation.

Purposes:

- `visit_preparation`
- `record_explanation`
- `clinician_briefing`

Actions:

- `answer_question`
- `draft_visit_brief`
- `summarize_records`

Allowed tools:

- `context.read`
- `source.read`
- `brief.draft`

The action registry maps each action to its required resource scopes and permitted tools.
G1 starts read-only: no controlled action permits canonical-record mutation, medication
selection, dosage guidance, treatment planning, diagnosis, or start/stop advice.
Changing these registries is a contract change and requires tests and threat review.

## 5. Contract models

All models reject unknown fields and are frozen after validation. Every datetime is an
RFC 3339 UTC instant with exactly six fractional digits and suffix `Z` in canonical form.
All IDs and controlled strings are non-empty, length-bounded, and contain no leading or
trailing whitespace or control characters. Sets are represented as sorted, duplicate-free
arrays.

### 5.1 `AuthorizationSnapshot`

A point-in-time capture of the live access decision used by the trusted builder:

| Field | Type | Rule |
|---|---|---|
| `actor_id` | string | authenticated active actor |
| `credential_id` | string | active credential/session provenance; no secret |
| `person_id` | string | exact selected Person |
| `assignment_id` | string | active assignment used for authorization |
| `role` | `owner \| caregiver` | current Family Access role |
| `granted_scopes` | array[string] | sorted, valid stored scopes |
| `required_scopes` | array[string] | action registry requirements |
| `consent_event_id` | string | current grant/access-basis event |
| `authorized_at` | datetime | builder clock instant |
| `access_expires_at` | datetime or null | null only for non-expiring local grant |
| `policy_version` | string | Family Access policy version |

The snapshot is evidence of the decision at issuance, not a durable capability and not a
substitute for G2 reauthorization.

### 5.2 `AuthorizationDecision`

| Field | Type | Rule |
|---|---|---|
| `decision` | `allow \| deny` | fail closed |
| `reason_codes` | array[string] | sorted, non-empty on deny, empty on allow |
| `snapshot` | `AuthorizationSnapshot` or null | required on allow, absent on deny |

A denied authorization can be represented internally for diagnostics, but no authorized
Envelope may be minted from it.

### 5.3 `SafetyDecision`

| Field | Type | Rule |
|---|---|---|
| `decision` | `allow \| refuse` | fail closed |
| `reason_codes` | array[string] | sorted; non-empty on refusal |
| `policy_version` | string | safety policy applied |
| `evaluated_at` | datetime | trusted clock instant |
| `limitations` | array[string] | explicit output limitations |
| `required_notices` | array[string] | clinician/safety notices required downstream |

### 5.4 `FinalDecision`

| Field | Type | Rule |
|---|---|---|
| `decision` | `allow \| refuse` | allow only if authorization and safety allow |
| `reason_codes` | array[string] | union of refusal reasons |

There is no override field. A caller cannot convert a denial or refusal to allow.

### 5.5 `EvidenceItem`

| Field | Type | Rule |
|---|---|---|
| `evidence_id` | string | stable OpenCare record/artifact identifier |
| `evidence_type` | string | controlled local evidence type |
| `person_id` | string | must equal Envelope Person |
| `resource_scope` | string | must be granted and action-relevant |
| `content_sha256` | string | lowercase 64-hex digest of selected content |
| `source_ids` | array[string] | sorted, non-empty provenance links |
| `provenance_status` | `source_backed \| user_asserted` | explicit provenance strength |
| `selected_fields` | array[string] | sorted field paths disclosed to agent |
| `observed_at` | datetime | selection/validation instant |

G1 carries evidence references, hashes, and disclosed field names, not arbitrary raw
sensitive payloads. G2 resolves only these approved references and must recheck their
hashes before disclosure. Missing sources, source hash mismatch, Person mismatch, or an
unsupported provenance state fails closed.

### 5.6 `ProviderDisclosure`

| Field | Type | Rule |
|---|---|---|
| `mode` | `local_only \| external_provider` | disclosure boundary |
| `provider_id` | string or null | absent for local; required for external |
| `consent_basis_id` | string | explicit consent/access basis |
| `allowed_evidence_ids` | array[string] | exact evidence allow-list |
| `allowed_fields` | array[string] | sorted field-path allow-list |
| `prohibited_data_classes` | array[string] | explicit exclusions |
| `retention` | `request_only \| provider_policy` | visible retention basis |

An external disclosure requires an explicit provider-specific consent basis. G1 does not
contact the provider.

### 5.7 `TrustEnvelope`

The stored JSON object has these fields:

| Field | Type | Rule |
|---|---|---|
| `contract_version` | literal | `opencare-trust-envelope/1` |
| `envelope_id` | string | `sha256:<digest>` over identity payload |
| `issued_at` | datetime | trusted clock |
| `expires_at` | datetime | later than issuance and no later than access expiry |
| `actor_id` | string | equals authorization snapshot actor |
| `person_id` | string | equals snapshot and every evidence Person |
| `purpose_id` | controlled purpose | registry member |
| `action_id` | controlled action | registry member |
| `requested_action` | string | bounded human-readable action statement |
| `resource_scopes` | array[string] | exact required/minimal scopes |
| `authorization` | `AuthorizationDecision` | must allow with snapshot |
| `safety` | `SafetyDecision` | must allow |
| `final_decision` | `FinalDecision` | must allow |
| `evidence` | array[`EvidenceItem`] | minimal, duplicate-free selection |
| `provider_disclosure` | `ProviderDisclosure` | disclosure allow-list |
| `allowed_tools` | array[controlled tool] | subset permitted by action registry |
| `prohibited_operations` | array[string] | non-empty explicit deny-list |
| `disclosure_constraints` | array[string] | non-empty downstream constraints |
| `limitations` | array[string] | non-empty visible limitations |
| `safety_notices` | array[string] | includes required safety and clinician review notes |

An issued Envelope always has final decision `allow`. Refused requests return structured
refusal reason codes, not an Envelope that looks executable.

### 5.8 `ExecutionReceipt`

| Field | Type | Rule |
|---|---|---|
| `contract_version` | literal | `opencare-execution-receipt/1` |
| `receipt_id` | string | `sha256:<digest>` over Receipt identity payload |
| `envelope_id` | string | exact consumed Envelope ID |
| `started_at` / `completed_at` | datetime | ordered UTC instants |
| `status` | `completed \| refused \| failed` | execution outcome |
| `provider_id` | string or null | consistent with disclosure mode |
| `used_evidence_ids` | array[string] | subset of Envelope allow-list |
| `used_tools` | array[string] | subset of Envelope tools |
| `output_sha256` | string or null | required for completed output |
| `reason_codes` | array[string] | non-empty for refused/failed |
| `receipt_sha256` | string | lowercase SHA-256 over Receipt integrity payload |

G1 can construct/verify receipts from supplied execution facts. G2 is responsible for
recording facts from actual constrained execution.

## 6. Canonicalization and identity

Canonicalization is a contract, not ordinary pretty JSON:

1. Validate into the versioned Pydantic model before hashing.
2. Reject byte-order marks, duplicate JSON object keys, unknown fields, non-finite
   numbers, floats, naive datetimes, non-UTC offsets, control characters, and invalid
   Unicode surrogate code points.
3. Normalize datetimes to UTC `YYYY-MM-DDTHH:MM:SS.ffffffZ`.
4. Preserve Unicode text as Unicode; do not apply locale-dependent transforms or Unicode
   NFC/NFD normalization. Identifiers that need normalization are validated in their
   already-normalized form.
5. Represent booleans/null with JSON literals and integers in base-10 without leading
   zeros. G1 contract models contain no floating-point fields.
6. Sort every field declared set-like lexicographically by Unicode code point and reject
   duplicates. Preserve order only for semantically ordered fields.
7. Serialize objects with keys sorted lexicographically, no insignificant whitespace,
   separators `,` and `:`, `ensure_ascii=False`, and terminal newline omitted.
8. Encode exactly as UTF-8 without BOM.

For Envelope identity, serialize the validated Envelope with `envelope_id` omitted and
compute `sha256(canonical_bytes)`. Store `envelope_id = "sha256:" + lowercase_hex`.
For Receipt identity, omit `receipt_id` and `receipt_sha256` and use the same rule.
For Receipt integrity, omit only `receipt_sha256`, then hash the canonical bytes including
`receipt_id`. Validators recompute and compare all identities using constant-time digest
comparison.

These rules are OS-, locale-, and newline-independent. The committed cross-platform vector
contains canonical UTF-8 bytes represented as text, its byte length, and expected digest;
Windows and Linux must produce the same result.

## 7. Trusted construction lifecycle

1. Receive an authenticated actor/credential from the existing access boundary.
2. Require one explicit active Person; never infer from family relationship or evidence.
3. Validate controlled purpose and action.
4. Resolve action-required scopes and maximum tools from the closed registry.
5. Query live Family Access state for the actor/Person/scopes in a consistent read.
6. Capture the active assignment and consent event in `AuthorizationSnapshot`.
7. Reject inactive/revoked/malformed access and access expiring at or before issuance.
8. Select the minimum evidence for the request from the explicit Person only.
9. Validate each evidence reference, content hash, resource scope, and provenance source.
10. Run the existing safety policy; merge required notices and limitations.
11. Resolve provider disclosure from explicit consent; deny external disclosure without it.
12. Intersect requested tools with action-permitted tools; never expand.
13. Set expiry to the earliest of requested TTL, configured maximum TTL, and access expiry.
14. Derive the final decision. Any deny/refusal stops construction.
15. Freeze the model, canonicalize, derive its content ID, and return the Envelope.

The public builder accepts typed trusted inputs and authority adapters, not a caller-supplied
`AuthorizationDecision`, `SafetyDecision`, identity, or arbitrary JSON. Only the builder
may mint an authorized Envelope. Parsing a JSON document never confers authorization.

## 8. Validation and later execution

Envelope validation is pure and offline except where explicitly described:

- **structural/integrity validation:** schema, invariants, canonical identity, evidence
  references, and expiry against a supplied clock;
- **live pre-execution validation (G2):** all offline checks plus reauthorization of actor,
  credential, Person, assignment/consent, scopes, evidence hashes, provider consent, and
  current safety policy immediately before disclosure or tool use.

A structurally valid but expired, revoked, superseded, or evidence-changed Envelope is not
executable. G1's authorization snapshot is deliberately time-bound. G2 must never treat a
valid content hash as live authority.

Receipt validation checks schema, both hashes, time ordering, status/output consistency,
and—when the Envelope is supplied—Envelope identity plus subset constraints for evidence,
tools, provider, and execution interval.

## 9. Invariants

Every authorized Envelope satisfies all of the following:

1. Actor and Person match the live authorization snapshot exactly.
2. All required scopes are granted; Envelope scopes are exactly the action's minimal
   required scopes, not all actor scopes.
3. The assignment and consent basis are active at issuance.
4. Expiry is strictly after issuance and cannot outlive access.
5. Purpose/action/tool IDs are controlled and mutually compatible.
6. Authorization, safety, and final decisions all allow.
7. Every evidence item belongs to the explicit Person and is within scope.
8. Every evidence item has validated provenance and a selected-content hash.
9. Disclosure allow-lists contain only selected evidence/fields.
10. Allowed tools are a subset of the action registry; prohibited operations remain
    explicit and cannot be negated by an allowed tool.
11. Safety/clinician notices, limitations, and disclosure constraints are non-empty.
12. Content identity matches canonical content.
13. No secret, credential material, raw session token, filesystem path, or unselected raw
    source content appears in the Envelope.
14. A family relationship alone grants no cross-Person access. Carol's records cannot be
    selected under another Person's Envelope.

## 10. Refusal and error semantics

Construction and verification fail closed. Stable machine reason codes are returned in a
privacy-safe result; diagnostics must not disclose whether an unauthorized Person or
resource exists.

Core codes:

- `authentication_required`
- `actor_inactive`
- `person_access_denied`
- `person_mismatch`
- `authorization_revoked`
- `authorization_expired`
- `required_scope_missing`
- `unsupported_purpose`
- `unsupported_action`
- `tool_not_allowed`
- `consent_basis_missing`
- `provider_disclosure_denied`
- `evidence_person_mismatch`
- `evidence_scope_invalid`
- `provenance_missing`
- `evidence_hash_mismatch`
- `safety_refused`
- `envelope_expired`
- `non_canonical_document`
- `envelope_id_mismatch`
- `receipt_id_mismatch`
- `receipt_hash_mismatch`
- `receipt_exceeds_envelope`
- `invalid_contract`

CLI and library validators return all safe deterministic validation codes where possible;
builders stop before returning sensitive context. Unexpected internal errors map to
`trust_envelope_failed` at external boundaries and are logged without sensitive payloads.

## 11. CLI contract

CLI convention: `python -m app.agent_trust.cli <command>`. Success exits `0`; verification
or refusal exits `1`; argument/usage errors exit `2`. Machine output is JSON.

- `export-envelope`: constructs an Envelope only from trusted OpenCare runtime state plus
  controlled purpose/action request arguments. It cannot accept an authorization decision,
  final decision, Envelope identity, or arbitrary Envelope JSON. Initial G1 supports only
  the repository's synthetic/demo authority and explicit output path; local real-data
  support is not enabled by this milestone.
- `verify-envelope --envelope PATH [--at UTC]`: rejects duplicate keys/non-canonical input,
  validates schema/invariants/identity/expiry, and prints `{valid,status,reason_codes,
  envelope_id}`. It verifies integrity, not live authority.
- `inspect-envelope --envelope PATH`: first verifies integrity, then prints a redacted
  summary: contract/identity/times, actor and Person opaque IDs, purpose/action, scopes,
  evidence IDs/types/hashes, disclosure mode, tools, constraints, decisions, and notices.
  It never prints source payloads or credential material.
- `verify-receipt --receipt PATH --envelope PATH [--at UTC]`: validates Receipt integrity
  and Envelope subset constraints.

Export writes canonical JSON plus a terminal newline for POSIX-friendly files. The newline
is not part of the hashed canonical bytes. Verifiers accept that one terminal LF but reject
BOM, CRLF, indentation, alternate escaping, reordered set-like arrays, or other byte-level
non-canonical representations.

## 12. Threat model

### In scope

- confused-deputy requests using the wrong Person;
- caregiver/family cross-Person leakage, including Carol isolation;
- stale, revoked, malformed, or expired access;
- purpose/action/scope/tool escalation;
- over-broad evidence selection or provider disclosure;
- missing or changed provenance and evidence;
- caller attempts to mint `allow` from arbitrary JSON;
- post-issuance Envelope or Receipt mutation;
- parser ambiguity from duplicate keys, BOM, Unicode surrogates, time zones, or platform
  newline differences;
- Receipt claims exceeding the Envelope.

### Out of scope / residual risk

- authenticity of the party that generated a valid hash;
- compromised OpenCare process, host, database authority, or trusted builder;
- provider behavior after authorized disclosure;
- confidentiality at rest or in transport;
- side-channel resistance beyond privacy-safe refusal messages;
- G2 runtime sandboxing, tool mediation, reauthorization, and provider transport;
- signatures, key management, attestation, and transparency infrastructure.

Content hashes are not access controls and are not encryption.

## 13. Compatibility and evolution

Versions are literal and validators reject unknown versions. Within version 1, changing
field meaning, canonicalization, controlled IDs, required invariants, or hash preimages is
breaking. Additive optional fields are also disallowed because v1 models reject extras;
a new contract version is required. Readers may support multiple explicit versions later,
but must never silently downgrade or reinterpret one version as another.

Canonical test vectors are permanent compatibility fixtures. Implementations on all
platforms must hash the same validated semantic value to the same bytes and digest.
Envelope expiry uses the verifier's explicit trusted clock; filesystem timestamps and
local timezone never participate.

## 14. Synthetic acceptance matrix

| Scenario | Expected result | Required code/check |
|---|---|---|
| allowed owner request | Envelope issued and verifies | stable Envelope ID |
| wrong explicit Person | no Envelope | `person_access_denied` or privacy-safe `person_mismatch` |
| Carol evidence under another Person | no Envelope | `evidence_person_mismatch` |
| revoked assignment/consent | no Envelope | `authorization_revoked` |
| expired access | no Envelope | `authorization_expired` |
| missing provenance source | no Envelope | `provenance_missing` |
| unsupported action | no Envelope | `unsupported_action` |
| requested mutation/tool escalation | no Envelope | `tool_not_allowed` or `unsupported_action` |
| changed evidence after selection | validation/execution denied | `evidence_hash_mismatch` |
| modified Envelope byte/content | verification denied | `non_canonical_document` or `envelope_id_mismatch` |
| modified Receipt | verification denied | `receipt_hash_mismatch`/`receipt_id_mismatch` |
| Receipt uses extra evidence/tool | verification denied | `receipt_exceeds_envelope` |
| same fixture on Windows/Linux | identical bytes and digest | committed canonical vector |
| valid hash presented as authority | not executable without G2 live checks | documented and tested adapter boundary |

G1 acceptance requires models, canonicalizer/hashes, trusted builders, validators, the
OpenCare authorization adapter, four CLI commands, all synthetic fixtures above, focused
tests, Ruff, strict mypy, existing pytest, and eval runner passing.

## 15. G2 handoff

G2 consumes a verified G1 Envelope and must implement:

1. live reauthentication/reauthorization immediately before context resolution;
2. expiry, consent, policy-version, evidence-hash, and provenance revalidation;
3. exact evidence-field projection and provider disclosure preview;
4. provider/tool mediation restricted to Envelope allow-lists;
5. runtime enforcement of prohibited operations and safety refusals;
6. no canonical-record mutation unless a future separately approved action contract exists;
7. Execution Receipt creation from observed execution facts and durable audit linkage;
8. cancellation/refusal if any bound fact changes between checks and use.

G2 must not broaden a G1 Envelope. A new purpose, Person, action, scope, evidence item,
field, provider, tool, or later expiry requires a newly authorized Envelope.

## 16. Roadmap naming

This specification defines **Sentient G1 — OpenCare Trust Envelope**, a new milestone in
the Sentient-targeted roadmap. Historical `G1` genome-profile references remain historical
session memory and are not part of this work. The active sequence is:

- Sentient G1 — OpenCare Trust Envelope;
- Sentient G2 — Consent-Gated Agent Runtime;
- Sentient G2.5 — optional Sentient integration spike;
- Sentient G3 — Model Portability;
- Sentient G4 — Portable Trust Package;
- Sentient G5 — Evaluation and Ecosystem Validation.

Genetics remains on the separate product roadmap and outside the Sentient critical path.
